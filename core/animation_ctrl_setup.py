import bpy
import bmesh
import math

from mathutils import Matrix, Vector
from .utils import delete_object_if_exists
from .skeleton import (find_animated_weapon_object, find_active_skeleton,
                       ske_weapon_part_ids)

AUTO_SETUP_ID = 'bf2_auto_setup' # identifier for custom bones and constraints

def _create_ctrl_bone_from(armature, source_bone, name=''):
    name = name if name else source_bone
    b = armature.edit_bones[source_bone]
    cb = armature.edit_bones.new(f'{name}.CTRL')
    cb.head = b.head
    cb.tail = b.tail
    cb.matrix = b.matrix
    cb[AUTO_SETUP_ID] = source_bone
    return cb

def _create_ctrl_bone(armature, source_bone, pos, name=''):
    name = name if name else source_bone
    cb = armature.edit_bones.new(f'{name}.CTRL')
    cb.head = pos
    cb.tail = pos
    cb.tail.z += 0.03
    cb[AUTO_SETUP_ID] = source_bone
    return cb

def _is_ctrl_of(bone):
    return bone[AUTO_SETUP_ID] if AUTO_SETUP_ID in bone else None

def _create_mesh_object(name):
    delete_object_if_exists(name)
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    return obj

def _create_bone_collection(armature, name, bone_prfx, theme_idx):
    if name in armature.collections:
        coll = armature.collections[name]
        armature.collections.remove(coll)
    coll = armature.collections.new(name=name)

    for bone in armature.bones:
        if bone.name.startswith(bone_prfx):
            bone.color.palette = f'THEME{theme_idx:>02}'
            coll.assign(bone)

def _create_shape(name, type='CUBE', size=1):
    mesh_object = _create_mesh_object(name)
    mesh = mesh_object.data
    mesh_object.hide_viewport = True
    mesh_object.hide_render = True
    mesh_object.hide_select = True

    if type == 'CUBE':
        _create_cube_mesh_shape(mesh, size=size)
    elif type == 'RING':
        _create_sphere_mesh_shape(mesh, size=size, axes=[1])
    elif type == 'SPHERE':
        _create_sphere_mesh_shape(mesh, size=size, axes=[0,1,2])
    else:
        raise ValueError(f'Unknown bone shape type {type}')

    return mesh_object

def _create_cube_mesh_shape(mesh, size=1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bmesh.ops.delete( bm, geom = bm.faces, context='FACES_ONLY') # delete all faces
    bm.to_mesh(mesh)
    bm.free()

def _create_sphere_mesh_shape(mesh, size=1, axes=[0, 1, 2]):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=8, radius=size)
    bmesh.ops.delete( bm, geom = bm.faces, context='FACES_ONLY') # delete all faces
    # delete all edges except those on axes indexes contained in `rings`
    edges_do_del = list()
    for edge in bm.edges:
        for i in axes:
            if edge.verts[0].co[i] == 0.0 and edge.verts[1].co[i] == 0.0:
                break
        else:
            edges_do_del.append(edge)

    bmesh.ops.delete(bm, geom = edges_do_del, context='EDGES')
    bm.to_mesh(mesh)
    bm.free()

def _calc_weapon_mesh_contoller_pos(context):
    bone_to_pos = dict()
    obj = find_animated_weapon_object(context)
    if obj:
        bone_to_vertices = dict()
        vertex_group_id_to_name = dict()
        for vg in obj.vertex_groups:
            vertex_group_id_to_name[vg.index] = vg.name
            bone_to_vertices[vg.name] = list()
        for v in obj.data.vertices:
            if len(v.groups) == 0:
                continue
            bone_name = vertex_group_id_to_name[v.groups[0].group]
            bone_to_vertices[bone_name].append(v.co)

        # calculate center of bounding boxes for each bone
        for bone, vertices in bone_to_vertices.items():
            # TODO replace with center of volume ?
            axes  = [[ v[i] for v in vertices] for i in range(3)]
            center = [(min(axis) + max(axis)) / 2 for axis in axes]
            bone_to_pos[bone] = Vector(tuple(center))

    return bone_to_pos

def _get_active_mesh_bones(context):
    mesh_bones = set()
    obj = find_animated_weapon_object(context)
    if obj:
        for vg in obj.vertex_groups:
            mesh_bones.add(vg.name)
    return mesh_bones

def rollback_controllers(context):
    ske_data = find_active_skeleton(context)
    if not ske_data:
        return

    rig, _ = ske_data
    armature = rig.data
    context.view_layer.objects.active = rig

    # delete constraints
    bpy.ops.object.mode_set(mode='POSE')
    for bone in rig.pose.bones:
        for c in bone.constraints:
            # constraints cannot have custom properties
            # our only option is to identify them by name
            if c.name.startswith(AUTO_SETUP_ID):
                bone.constraints.remove(c)

    # delete controller bones
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.edit_bones:
        if _is_ctrl_of(bone):
            armature.edit_bones.remove(bone)

    bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.update()

def setup_controllers(context, step=0):
    ske_data = find_active_skeleton(context)
    if not ske_data:
        return

    # cleanup previuous
    if step != 2:
        rollback_controllers(context)
        set_hide_all_mesh_bones_in_em(context, hide=True) # keep only CTRL bones visible
    else:
        _remove_mesh_mask(context)

    rig, skeleton = ske_data

    if skeleton.name.lower() == '3p_setup':
        _setup_3p_controllers(context, rig, step)
    elif skeleton.name.lower() == '1p_setup':
        _setup_1p_controllers(context, rig, step)

def _setup_3p_controllers(context, rig, step):
    pass # TODO

def _setup_1p_controllers(context, rig, step):
    scene = context.scene
    armature = rig.data
    context.view_layer.objects.active = rig

    # inverse matrix to treat bones pointing 'up' as having no rotation
    BONE_ROT_FIX = Matrix.Rotation(math.radians(-90), 4, 'X')

    # offset of the elbow IK pole
    POLE_OFFSET = 0.5

    # constatnts
    ONES_VEC = Vector((1, 1, 1))
    ZERO_VEC = Vector((0, 0, 0))

    if step != 2:
        # Create new bones
        bpy.ops.object.mode_set(mode='EDIT')

        _create_ctrl_bone_from(armature, source_bone='L_wrist')
        _create_ctrl_bone_from(armature, source_bone='R_wrist')
        _create_ctrl_bone_from(armature, source_bone='L_arm')
        _create_ctrl_bone_from(armature, source_bone='R_arm')

        # Arms controllers
        L_elbowMiddleJoint = armature.edit_bones['L_elbowMiddleJoint']
        L_elbow_CTRL_pos = Vector((1, 0, 0))
        L_elbow_CTRL_pos.rotate(L_elbowMiddleJoint.matrix @ BONE_ROT_FIX)
        L_elbow_CTRL_pos *= POLE_OFFSET
        L_elbow_CTRL_pos += L_elbowMiddleJoint.head

        R_elbowJoint = armature.edit_bones['R_elbowJoint']
        R_elbow_CTRL_pos = Vector((1, 0, 0))
        R_elbow_CTRL_pos.rotate(R_elbowJoint.matrix @ BONE_ROT_FIX)
        R_elbow_CTRL_pos *= -POLE_OFFSET
        R_elbow_CTRL_pos += R_elbowJoint.head

        _create_ctrl_bone(armature, name='L_elbow', source_bone='L_elbowMiddleJoint', pos=L_elbow_CTRL_pos)
        _create_ctrl_bone(armature, name='R_elbow', source_bone='R_elbowJoint', pos=R_elbow_CTRL_pos)

        # meshX controllers
        meshbone_to_pos = _calc_weapon_mesh_contoller_pos(context)
        mesh_bones = meshbone_to_pos.keys()

        for mesh_bone, pos in meshbone_to_pos.items():
            _create_ctrl_bone(armature, source_bone=mesh_bone, pos=pos)
    else:
        mesh_bones = _get_active_mesh_bones(context)

    if step == 1:
        return

    bpy.ops.object.mode_set(mode='POSE')

    L_wrist_CTRL = rig.pose.bones['L_wrist.CTRL']
    R_wrist_CTRL = rig.pose.bones['R_wrist.CTRL']
    L_elbow_CTRL = rig.pose.bones['L_elbow.CTRL']
    R_elbow_CTRL = rig.pose.bones['R_elbow.CTRL']
    L_arm_CTRL = rig.pose.bones['L_arm.CTRL']
    R_arm_CTRL = rig.pose.bones['R_arm.CTRL']

    Camerabone = rig.pose.bones['Camerabone']

    # apply custom shapes
    CUBE_SHAPE_SIZE = 0.07
    CUBE_SHAPE_NAME = '_CubeBoneShape'
    RING_SHAPE_SIZE = 0.04
    RING_SHAPE_NAME = '_RingBoneShape'
    SPHERE_SHAPE_NAME = '_SphereBoneShape'
    SPHERE_SHAPE_SIZE = 0.02

    cube_shape = _create_shape(name=CUBE_SHAPE_NAME, size=CUBE_SHAPE_SIZE, type='CUBE')
    sphere_shape = _create_shape(name=SPHERE_SHAPE_NAME, size=SPHERE_SHAPE_SIZE, type='SPHERE') 
    ring_shape = _create_shape(name=RING_SHAPE_NAME, size=RING_SHAPE_SIZE, type='RING')

    scene.collection.objects.link(cube_shape)
    scene.collection.objects.link(sphere_shape)
    scene.collection.objects.link(ring_shape)
    
    L_wrist_CTRL.custom_shape = ring_shape
    L_wrist_CTRL.custom_shape_scale_xyz = ONES_VEC / L_wrist_CTRL.length
    R_wrist_CTRL.custom_shape = ring_shape
    R_wrist_CTRL.custom_shape_scale_xyz = ONES_VEC / R_wrist_CTRL.length
    L_elbow_CTRL.custom_shape = cube_shape
    L_elbow_CTRL.custom_shape_scale_xyz = ONES_VEC / L_elbow_CTRL.length
    R_elbow_CTRL.custom_shape = cube_shape
    R_elbow_CTRL.custom_shape_scale_xyz = ONES_VEC / R_elbow_CTRL.length
    L_arm_CTRL.custom_shape = cube_shape
    L_arm_CTRL.custom_shape_scale_xyz = ONES_VEC / L_arm_CTRL.length
    R_arm_CTRL.custom_shape = cube_shape
    R_arm_CTRL.custom_shape_scale_xyz = ONES_VEC / R_arm_CTRL.length

    Camerabone.custom_shape = sphere_shape
    Camerabone.custom_shape_scale_xyz = ONES_VEC / Camerabone.length
    
    MESH_BONE_CUBE_SCALE = 0.2
    for mesh_bone in mesh_bones:
        mesh_bone_ctrl = rig.pose.bones[mesh_bone + '.CTRL']
        mesh_bone_ctrl.custom_shape = cube_shape
        mesh_bone_ctrl.custom_shape_scale_xyz = (ONES_VEC / Camerabone.length) * MESH_BONE_CUBE_SCALE

    # ctrl to offset mapping
    ctrl_bone_to_offset = [
        (L_wrist_CTRL, ZERO_VEC),
        (R_wrist_CTRL, ZERO_VEC),
        (L_arm_CTRL, ZERO_VEC),
        (R_arm_CTRL, ZERO_VEC),
        (L_elbow_CTRL, Vector((POLE_OFFSET, 0, 0))),
        (R_elbow_CTRL, Vector((-POLE_OFFSET, 0, 0))),
    ]

    for mesh_bone in mesh_bones:
        mesh_bone_ctrl = rig.pose.bones[mesh_bone + '.CTRL']
        mesh_bone_offset = mesh_bone_ctrl.bone.matrix_local.translation
        ctrl_bone_to_offset.append((mesh_bone_ctrl, mesh_bone_offset))

    # apply loaded animation for controllers
    saved_frame = scene.frame_current
    for frame_idx in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame_idx)
        context.view_layer.update()
        for (target, offset) in ctrl_bone_to_offset:
            source_name = _is_ctrl_of(target.bone)
            source = rig.pose.bones[source_name]

            target_pos = offset.normalized()
            target_pos.rotate(source.matrix @ BONE_ROT_FIX)
            target_pos *= offset.length
            target_pos += source.matrix.translation

            m = source.matrix.copy()
            m.translation = target_pos
            target.matrix = m

            target.keyframe_insert(data_path="location", frame=frame_idx)
            target.keyframe_insert(data_path="rotation_quaternion", frame=frame_idx)
            
            # delete all keyframes for orignal mesh bones
            # otherwise the CHILD_OF constraint will mess them up
            if source_name in mesh_bones:
                source.keyframe_delete(data_path="location", frame=frame_idx)
                source.keyframe_delete(data_path="rotation_quaternion", frame=frame_idx)

    # Constraints setup

    # meshX bones controllers
    for mesh_bone in mesh_bones:
        child_of = rig.pose.bones[mesh_bone].constraints.new(type='CHILD_OF')
        child_of.target = rig
        child_of.subtarget = mesh_bone + '.CTRL'
        child_of.name = AUTO_SETUP_ID + '_CHILD_OF_' + mesh_bone

    # wrist rotation
    cp_rot = rig.pose.bones['L_wrist'].constraints.new(type='COPY_ROTATION')
    cp_rot.target = rig
    cp_rot.subtarget = L_wrist_CTRL.name
    cp_rot.name = AUTO_SETUP_ID + '_COPY_ROTATION_L_wrist'

    cp_rot = rig.pose.bones['R_wrist'].constraints.new(type='COPY_ROTATION')
    cp_rot.target = rig
    cp_rot.subtarget = R_wrist_CTRL.name
    cp_rot.name = AUTO_SETUP_ID + '_COPY_ROTATION_R_wrist'

    # IK
    ik = rig.pose.bones['L_collar'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = L_arm_CTRL.name
    ik.chain_count = 1
    ik.name = AUTO_SETUP_ID + '_IK_L_collar'

    ik = rig.pose.bones['L_ullna'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = L_wrist_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = L_elbow_CTRL.name
    ik.pole_angle = 0
    ik.chain_count = 4
    ik.name = AUTO_SETUP_ID + '_IK_L_ullna'

    ik = rig.pose.bones['R_collar'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = R_arm_CTRL.name
    ik.chain_count = 1
    ik.name = AUTO_SETUP_ID + '_IK_R_collar'

    ik = rig.pose.bones['R_ullna'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = R_wrist_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = R_elbow_CTRL.name
    ik.pole_angle = math.radians(180)
    ik.chain_count = 4
    ik.name = AUTO_SETUP_ID + '_IK_R_ullna'

    # declutter viewport by changing bone display mode
    # and hiding all bones except controllers and finger bones
    UNHIDE_BONE = ['Camerabone', 'L_collar', 'R_collar'] # exception list
    rig.show_in_front = True
    armature.display_type = 'WIRE'
    FINGER_PREFIXES = {'L_', 'R_'}
    FINGER_NAMES = {'pink', 'index', 'point', 'ring', 'thumb'}
    FINGER_SUFFIXES = {'_1', '_2', '_3'}
    finger_bones = [p + n + s for p in FINGER_PREFIXES for n in FINGER_NAMES for s in FINGER_SUFFIXES]
    for pose_bone in rig.pose.bones:
        bone = pose_bone.bone
        if bone.name not in finger_bones and not _is_ctrl_of(bone) and bone.name not in UNHIDE_BONE:
            bone.hide = True # hidden in Pose and Object modes

    _create_bone_collection(armature, 'BF2_LEFT_ARM', 'L_', 3)
    _create_bone_collection(armature, 'BF2_RIGHT_ARM', 'R_', 4)
    _create_bone_collection(armature, 'BF2_MESH_BONES', 'mesh', 9)
    _create_bone_collection(armature, 'BF2_CAMERABONE', 'Camerabone', 1)

    bpy.ops.object.mode_set(mode='OBJECT')
    scene.frame_set(saved_frame)
    context.view_layer.update()

def set_hide_all_mesh_bones_in_em(context, hide=True):
    ske_data = find_active_skeleton(context)
    if not ske_data:
        return
    rig, skeleton = ske_data
    mesh_bone_ids = ske_weapon_part_ids(skeleton)
    mesh_bones = set()
    for i, node in enumerate(skeleton.node_list()):
        if i in mesh_bone_ids:
            mesh_bones.add(node.name)

    armature = rig.data
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.edit_bones:
        if bone.name in mesh_bones:
            bone.hide = hide

MASK_MOD_NAME = 'bf2_bone_mask'

def _remove_mesh_mask(context):
    obj = find_animated_weapon_object(context)
    if not obj:
        return
    
    for mod in obj.modifiers:
        if mod.name == MASK_MOD_NAME:
            obj.modifiers.remove(mod)
            break

def toggle_mesh_mask_mesh_for_active_bone(context):        
    ctrl_bone = context.active_bone

    obj = find_animated_weapon_object(context)
    if not obj:
        return
    
    mask_mod = None
    active_vg = None

    for mod in obj.modifiers:
        if mod.name == MASK_MOD_NAME:
            mask_mod = mod
            active_vg = mod.vertex_group
            break
    
    if mask_mod is None:
        mask_mod = obj.modifiers.new(MASK_MOD_NAME, 'MASK')

    bone = _is_ctrl_of(ctrl_bone)
    if bone is None:
        return

    if bone and active_vg != bone:
        mask_mod.vertex_group = bone
    else:
        mask_mod.vertex_group = ""
