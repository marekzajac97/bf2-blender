import bpy # type: ignore
import math

from mathutils import Matrix, Vector, Quaternion # type: ignore
from .bf2.bf2_skeleton import BF2Skeleton, BF2SkeletonException
from .utils import (to_matrix, conv_bf2_to_blender,
                    conv_blender_to_bf2,
                    delete_object_if_exists)
from .exceptions import ImportException, ExportException

# BF2 hardcoded limits, binary can be easily hacked to support more if needed
MAX_ITEMS_1P = 16
MAX_ITEMS_3P = 8

def ske_set_bone_rot(bone, deg, axis):
    bone['bf2_rot_fix'] = list(Matrix.Rotation(math.radians(deg), 4, axis))

def ske_get_bone_rot(bone):
    return Matrix(bone.get('bf2_rot_fix', Matrix.Identity(4)))

def ske_weapon_part_ids(rig):
    ske_bones = rig['bf2_bones']
    ids = list()
    ske_name = rig.name.lower()
    for i, ske_bone in enumerate(ske_bones):
        if ske_name == '3p_setup':
            max_weapon_parts = MAX_ITEMS_3P
        elif ske_name == '1p_setup':
            max_weapon_parts = MAX_ITEMS_1P
        else:
            return list()
        if ske_bone.startswith('mesh') and int(ske_bone[4:]) <= max_weapon_parts:
            ids.append(i)
    return ids

def find_active_skeleton(context):
    active_obj = context.view_layer.objects.active
    if active_obj and is_bf2_skeleton(active_obj):
        return active_obj

    rigs = find_all_skeletons()
    if len(rigs) == 1:
        return rigs[0]

def find_all_skeletons():
    rig_objs = list()
    for obj in bpy.data.objects:
        if is_bf2_skeleton(obj):
            rig_objs.append(obj)
    return rig_objs

def is_bf2_skeleton(obj):
    return obj.data and 'bf2_bones' in obj.keys()

def find_animated_weapon_object(rig):
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

def find_rig_attached_to_object(obj):
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object and 'bf2_bones' in mod.object.keys():
            return mod.object
    return None

CAMER_OBJECT_NAME = 'Camerabone_Camera'

def _create_camera(context, rig):
    armature = rig.data
    camera_object = None
    if 'Camerabone' in armature.bones:
        # remove old one
        delete_object_if_exists(CAMER_OBJECT_NAME)

        # create camera
        camera_data = bpy.data.cameras.new(name=CAMER_OBJECT_NAME)
        camera_data.lens_unit = 'FOV'
        camera_data.angle = math.radians(75)
        camera_data.clip_start = 0.001
        camera_object = bpy.data.objects.new(CAMER_OBJECT_NAME, camera_data)

        # position to bone
        camerabone = armature.bones['Camerabone']
        camera_object.matrix_local = camerabone.matrix_local
        
        # create constrains to follow the camerabone position
        constraint = camera_object.constraints.new(type='CHILD_OF')
        constraint.target = rig
        constraint.subtarget = camerabone.name
        context.scene.collection.objects.link(camera_object)

    return camera_object

def import_skeleton(context, skeleton_file, reload=False):
    try:
        skeleton = BF2Skeleton(skeleton_file)
    except BF2SkeletonException as e:
        raise ImportException(str(e)) from e

    if reload:
        delete_object_if_exists(skeleton.name)

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
        # so if the bone points "up" (along Z axis) then it's the same as if it was rotated by 90 deg
        ske_set_bone_rot(bone, 90, 'X')

        if node.children and node.children[0].pos.z < 0.0:
            # quck hack to fix some bone rotations
            # right ones seem to point in the opposite direction in the BF2 skeleton export
            ske_set_bone_rot(bone, -90, 'X')

        # get the lenght, blender does not allow to create bones with length == 0 (or close to zero)
        if len(node.children) == 1:
            bone_len = node.children[0].pos.length # pos is relative to parrent
            if bone_len < 0.01:
                bone_len = 0.01
        elif node.parent and not node.children and not node.name.startswith('mesh'):    
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

    _create_camera(context, rig)
    return rig


def export_skeleton(rig, ske_file):
    armature = rig.data
    skeleton = BF2Skeleton(name=rig.name)

    nodes = dict()
    for index, bone in enumerate(armature.bones):
        parent_matrix = Matrix.Identity(4)
        if bone.parent:
            parent_matrix = bone.parent.matrix_local.copy() @ ske_get_bone_rot(bone.parent).inverted()
        matrix = parent_matrix.inverted() @ bone.matrix_local.copy() @ ske_get_bone_rot(bone).inverted()

        pos, rot, _ = matrix.decompose()
        pos, rot = conv_blender_to_bf2(pos, rot)
        nodes[bone.name] = BF2Skeleton.Node(index, bone.name, pos, rot)

    # relations
    for _, node in nodes.items():
        bone = armature.bones[node.name]
        for child in bone.children:
            node.children.append(nodes[child.name])
        if bone.parent:
            node.parent = nodes[bone.parent.name]
        else:
            skeleton.roots.append(node)

    try:
        skeleton.export(ske_file)
    except BF2SkeletonException as e:
        raise ExportException(str(e)) from e
