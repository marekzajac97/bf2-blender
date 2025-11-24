import bpy # type: ignore

from mathutils import Matrix # type: ignore
from .bf2.bf2_animation import BF2Animation, BF2KeyFrame, BF2AnimationException
from .utils import to_matrix, conv_bf2_to_blender, conv_blender_to_bf2
from .skeleton import (ske_get_bone_rot,
                       find_animated_weapon_object, ske_weapon_part_ids)
from .exceptions import ImportException, ExportException

def get_bones_for_export(rig):
    ske_bones = rig['bf2_bones']

    prev = rig.get('bones_to_export')
    if prev is not None:
        return prev # always prefer saved settings from from the previous export

    inc_mesh_bones = set()
    obj = find_animated_weapon_object(rig)
    if obj:
        vertex_group_id_to_name = dict()
        for vg in obj.vertex_groups:
            vertex_group_id_to_name[vg.index] = vg.name
        for v in obj.data.vertices:
            if len(v.groups) > 0:
                inc_mesh_bones.add(vertex_group_id_to_name[v.groups[0].group])

    inc_bones = dict()
    for i, ske_bone in enumerate(ske_bones):
        if i in ske_weapon_part_ids(rig) and ske_bone not in inc_mesh_bones:
            inc_bones[ske_bone] = False # mesh bone not part of the animated weapon
        else:
            inc_bones[ske_bone] = True
    return inc_bones

def save_bones_for_export(rig, bones_to_export):
    rig['bones_to_export'] = bones_to_export

def export_animation(context, rig, baf_file, bones_to_export=None, fstart=None, fend=None, world_space=False):
    scene = context.scene

    fstart = scene.frame_start if fstart is None else fstart
    fend = scene.frame_end if fend is None else fend

    saved_frame = scene.frame_current
    
    ske_bones = rig['bf2_bones']

    if bones_to_export is None:
        bones_to_export = ske_bones
    
    # initialize BF2 animation
    baf = BF2Animation()
    baf.frame_num = fend - fstart + 1
    for bone_idx, ske_bone in enumerate(ske_bones):
        if ske_bone in bones_to_export:
            baf.bones[bone_idx] = list()

    # for each frame...
    for frame_idx in range(fstart, fend + 1):
        scene.frame_set(frame_idx)
        context.view_layer.update()

        # for each bone...
        for bone_idx, ske_bone in enumerate(ske_bones):

            if not bone_idx in baf.bones:
                continue
            
            pose_bone = rig.pose.bones[ske_bone]

            # convert to parent space and fix rotations
            if world_space:
                parent_matrix = rig.matrix_world.inverted()
            else:
                parent_matrix = Matrix.Identity(4)

            if pose_bone.parent:
                parent_matrix = pose_bone.parent.matrix @ ske_get_bone_rot(pose_bone.parent.bone).inverted()
            matrix = parent_matrix.inverted() @ pose_bone.matrix
            matrix @= ske_get_bone_rot(pose_bone.bone).inverted()

            pos, rot, _ = matrix.decompose()
            pos, rot = conv_blender_to_bf2(pos, rot)
            frame = BF2KeyFrame(pos=pos, rot=rot)
            baf.bones[bone_idx].append(frame)

    # revert to frame before export
    scene.frame_set(saved_frame)

    try:
        baf.export(baf_file)
    except BF2AnimationException as e:
        raise ExportException(str(e)) from e


def import_animation(context, rig, baf_file, insert_at_frame=0):
    scene = context.scene
    try:
        baf = BF2Animation(baf_file)
    except BF2AnimationException as e:
        raise ImportException(str(e)) from e   

    armature = rig.data
    context.view_layer.objects.active = rig

    bpy.ops.object.mode_set(mode='POSE')
    armature.pose_position = "POSE"

    scene.frame_start = insert_at_frame
    scene.frame_end = insert_at_frame + baf.frame_num - 1
    scene.render.fps = 24 # BF2 hardcoded default

    ske_bones = rig['bf2_bones']

    # get 'rest' pose matrix in armature space
    bone_to_rest_matrix = dict()
    for ske_bone in ske_bones:
        rest_bone = armature.bones[ske_bone]
        bone_to_rest_matrix[rest_bone.name] = rest_bone.matrix_local @ ske_get_bone_rot(rest_bone).inverted()

    for bone_idx, frames in baf.bones.items():
        try:
            ske_bone = ske_bones[bone_idx]
        except IndexError as e:
            raise ImportException(f"Bone index {bone_idx} from the animation file does not exist in the skeleton")
        pose_bone = rig.pose.bones[ske_bone]

        for frame_idx in range(baf.frame_num):
            frame = frames[frame_idx]
            pos, rot = conv_bf2_to_blender(frame.pos, frame.rot)
            # bone transforms in .baf are in parent bone space
            # bone transforms in blender are in parent and 'rest' pose space (wtf seriously)

            # matrix at this frame (parent space)
            matrix = to_matrix(pos, rot) @ ske_get_bone_rot(pose_bone.bone)

            # from parent space to armature space
            parent_matrix = Matrix.Identity(4)
            if pose_bone.bone.parent:
                parent_matrix = bone_to_rest_matrix[pose_bone.bone.parent.name]
            matrix = parent_matrix @ matrix

            # back to rest bone space
            pose_bone.matrix_basis = pose_bone.bone.matrix_local.inverted() @ matrix

            pose_bone.keyframe_insert(data_path="location", frame=insert_at_frame + frame_idx)
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=insert_at_frame + frame_idx)

    bpy.ops.object.mode_set(mode='OBJECT')
