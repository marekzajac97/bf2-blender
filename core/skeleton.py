import bpy
import math

from mathutils import Matrix, Vector, Quaternion
from .bf2.bf2_skeleton import BF2Skeleton
from .utils import to_matrix, conv_bf2_to_blender, delete_object, delete_object_if_exists
from .exceptions import ImportException


def ske_set_bone_rot(bone, deg, axis):
    bone['bf2_rot_fix'] = Matrix.Rotation(math.radians(deg), 4, axis)

def ske_get_bone_rot(bone):
    return Matrix(bone['bf2_rot_fix'])

def ske_weapon_part_ids(rig):
    ske_bones = rig['bf2_bones']
    ids = list()
    ske_name = rig.name.lower()
    for i, ske_bone in enumerate(ske_bones):
        if ske_name == '3p_setup':
            max_weapon_parts = 8
        elif ske_name == '1p_setup':
            max_weapon_parts = 16
        else:
            return list()
        if ske_bone.startswith('mesh') and int(ske_bone[4:]) <= max_weapon_parts:
            ids.append(i)
    return ids

def find_active_skeleton():
    rigs = find_all_skeletons()
    if rigs:
        return rigs[0]

def find_all_skeletons():
    rig_objs = list()
    for obj in bpy.data.objects:
        if obj.data and 'bf2_bones' in obj.keys():
            rig_objs.append(obj)
    return rig_objs

def find_animated_weapon_object():
    rig = find_active_skeleton()
    if not rig:
        return None

    for obj in bpy.data.objects:
        if obj is rig:
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == rig and 'mesh1' in obj.vertex_groups:
                # check if any vert belongs to the mesh1 group
                # (compatibility fix with older plugin version to filter out soldier meshes)
                if any([len(v.groups) and v.groups[0].group == obj.vertex_groups['mesh1'].index for v in obj.data.vertices]):
                    return obj
    return None


CAMER_OBJECT_NAME = 'Camerabone_Camera'

def _create_camera(rig):
    armature = rig.data
    camera_object = None
    if 'Camerabone' in armature.bones:
        # remove old one
        delete_object_if_exists(CAMER_OBJECT_NAME)
        
        # create camera
        camera_data = bpy.data.cameras.new(name=CAMER_OBJECT_NAME)
        camera_data.lens_unit = 'FOV'
        camera_data.angle = math.radians(75)
        camera_object = bpy.data.objects.new(CAMER_OBJECT_NAME, camera_data)

        # position to bone
        camerabone = armature.bones['Camerabone']
        camera_object.matrix_local = camerabone.matrix_local
        
        # create constrains to follow the camerabone position
        constraint = camera_object.constraints.new(type='CHILD_OF')
        constraint.target = rig
        constraint.subtarget = camerabone.name

    return camera_object

def import_skeleton(context, skeleton_file, reload=False):
    skeleton = BF2Skeleton(skeleton_file)

    if reload and find_active_skeleton():
        obj, _ = find_active_skeleton()
        delete_object(obj)

    armature = bpy.data.armatures.new(skeleton.name)
    rig = bpy.data.objects.new(skeleton.name, armature)

    context.scene.collection.objects.link(rig)
    context.view_layer.objects.active = rig

    # add skeleton bone list to rig
    rig['bf2_bones'] = [n.name for n in skeleton.node_list()]

    bpy.ops.object.mode_set(mode='EDIT')

    # fix node pos/rot
    nodes = skeleton.node_list()
    for node in nodes:
        node.pos, node.rot = conv_bf2_to_blender(node.pos, node.rot)

    for i, node in enumerate(nodes):
        
        bone = armature.edit_bones.new(node.name)
        
        # transform is in armature space, so first need to move bone to origin
        bone.head = [0, 0, 0]
        
        # this is to unfuck (and refuck during export) rotation of bone in blender
        # head/tail position is directly tied to bone rotation (exept bone roll)
        # so if the bone points "up" then it's the same as if it was rotated by 90 deg
        ske_set_bone_rot(bone, 90, 'X')

        if node.childs and node.childs[0].pos.z < 0.0:
            # quck hack to fix some bone rotations
            # right ones seem to point in the opposite direction in the BF2 skeleton export
            ske_set_bone_rot(bone, -90, 'X')

        # get the lenght
        if len(node.childs) == 1:
            bone_len = node.childs[0].pos.length # pos is relative to parrent
            if bone_len < 0.01:
                bone_len = 0.01
        elif node.parent and not node.childs and not node.name.startswith('mesh'):    
            bone_len = 0.01 # finger ends etc
        else:
            bone_len = 0.03 # 'lone' bones

        bone.tail = [0, 0, bone_len]
        
        # calculate and apply position/rotation in armature space
        armature_space_matrix = Matrix.Identity(4)
        parents = list()
        parent = node.parent
        while parent:
            parents.append(parent)
            parent = parent.parent
        parents.reverse()
        for p in parents:
            armature_space_matrix @= to_matrix(p.pos, p.rot)
        
        if i in ske_weapon_part_ids(rig):
            # have to keep all wepon parts in scene origin
            # otherwise weapon parts may not map properly later
            matrix = Matrix.Identity(4)
        else:
            matrix = armature_space_matrix @ to_matrix(node.pos, node.rot)
        
        # rotate & translate
        bone.matrix = matrix @ ske_get_bone_rot(bone)
        
        # link bones
        if node.parent:
            bone.parent = armature.edit_bones[node.parent.name]
    
    bpy.ops.object.mode_set(mode='OBJECT')

    camera = _create_camera(rig)
    if camera:
        context.scene.collection.objects.link(camera)
