import bpy
import math

from mathutils import Matrix
from .bf2.bf2_animation import BF2Animation, BF2KeyFrame
from .utils import to_matrix, convert_bf2_pos_rot
from .skeleton import (ske_get_bone_rot, find_active_skeleton,
                       find_animated_weapon_object, ske_weapon_part_ids)

def get_bones_for_export(context):
    ske_data = find_active_skeleton(context)
    if not ske_data:
        return dict()

    _, skeleton = ske_data

    inc_mesh_bones = set()
    obj = find_animated_weapon_object(context)
    if obj:
        vertex_group_id_to_name = dict()
        for vg in obj.vertex_groups:
            vertex_group_id_to_name[vg.index] = vg.name
        for v in obj.data.vertices:
            if len(v.groups) > 0:
                inc_mesh_bones.add(vertex_group_id_to_name[v.groups[0].group])

    inc_bones = dict()
    for i, node in enumerate(skeleton.node_list()):
        if i in ske_weapon_part_ids(skeleton) and node.name not in inc_mesh_bones:
            inc_bones[node.name] = False # mesh bone not part of the animated weapon
        else:
            inc_bones[node.name] = True
    return inc_bones

def export_animation(context, baf_file, bones_to_export=None, fstart=None, fend=None):
    scene = context.scene
    if not find_active_skeleton(context):
        raise RuntimeError("No active skeleton found!")
        
    rig, skeleton = find_active_skeleton(context)
    
    fstart = scene.frame_start if fstart is None else fstart
    fend = scene.frame_end if fend is None else fend
    
    saved_frame = scene.frame_current
    
    nodes = skeleton.node_list()

    if bones_to_export is None:
        bones_to_export = [n.name for n in nodes]
    
    # initialize BF2 animation
    baf = BF2Animation()
    baf.frame_num = fend - fstart + 1
    for bone_idx, node in enumerate(nodes):
        if node.name in bones_to_export:
            baf.bones[bone_idx] = list()

    # for each frame...
    for frame_idx in range(fstart, fend + 1):
        scene.frame_set(frame_idx)
        context.view_layer.update()

        # for each bone...
        for bone_idx, node in enumerate(nodes):

            if not bone_idx in baf.bones:
                continue
            
            pose_bone = rig.pose.bones[node.name]

            # convert to parent space and fix rotations
            parent_matrix = Matrix.Identity(4)
            if pose_bone.parent:
                parent_matrix = pose_bone.parent.matrix @ ske_get_bone_rot(pose_bone.parent.bone).inverted()
            matrix = parent_matrix.inverted() @ pose_bone.matrix
            matrix @= ske_get_bone_rot(pose_bone.bone).inverted()

            pos, rot, _ = matrix.decompose()
            convert_bf2_pos_rot(pos, rot)
            frame = BF2KeyFrame(pos=pos, rot=rot)
            baf.bones[bone_idx].append(frame)

    # revert to frame before export
    scene.frame_set(saved_frame)
    
    baf.export(baf_file)


def import_animation(context, baf_file):
    scene = context.scene

    baf = BF2Animation(baf_file)

    if not find_active_skeleton(context):
        raise RuntimeError("need to import skeleton first!")

    rig, skeleton = find_active_skeleton(context)
    armature = rig.data
 
    context.view_layer.objects.active = rig
    
    bpy.ops.object.mode_set(mode='POSE')
    armature.pose_position = "POSE"

    scene.frame_start = 0
    scene.frame_end = baf.frame_num - 1
    scene.render.fps = 24 # BF2 hardcoded default

    # fix node pos/rot
    nodes = skeleton.node_list()
    for node in nodes:
        convert_bf2_pos_rot(node.pos, node.rot)
    
    # get 'rest' pose matrix in armature space
    node_to_rest_matrix = dict()
    for n in nodes:
        rest_bone = armature.bones[n.name]
        node_to_rest_matrix[rest_bone.name] = rest_bone.matrix_local @ ske_get_bone_rot(rest_bone).inverted()

    # for each frame...
    for frame_idx in range(baf.frame_num):
        # for each bone...
        for bone_idx, frames in baf.bones.items():
            frame = frames[frame_idx]
            pos = frame.pos.copy()
            rot = frame.rot.copy()
            convert_bf2_pos_rot(pos, rot)
            node = nodes[bone_idx]
            pose_bone = rig.pose.bones[node.name]

            # bone transforms in .baf are in parent bone space
            # bone transforms in blender are in parent and 'rest' pose space (wtf seriously)

            # matrix at this frame (parent space)
            matrix = to_matrix(pos, rot) @ ske_get_bone_rot(pose_bone.bone)

            # from parent space to armature space
            parent_matrix = Matrix.Identity(4)
            if pose_bone.bone.parent:
                parent_matrix = node_to_rest_matrix[pose_bone.bone.parent.name]
            matrix = parent_matrix @ matrix

            # back to rest bone space
            pose_bone.matrix_basis = pose_bone.bone.matrix_local.inverted() @ matrix

            pose_bone.keyframe_insert(data_path="location", frame=frame_idx)
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame_idx)

    bpy.ops.object.mode_set(mode='OBJECT')
