import bpy # type: ignore
import bmesh # type: ignore
import math
import re
import enum

from mathutils import Matrix, Vector # type: ignore
from ..utils import DEFAULT_REPORTER, delete_object_if_exists
from ..skeleton import (find_animated_weapon_object,
                       ske_weapon_part_ids)

AUTO_SETUP_ID = 'bf2_auto_setup' # identifier for custom bones and constraints

# inverse matrix to treat bones pointing 'up' as having no rotation
BONE_ROT_FIX = Matrix.Rotation(math.radians(-90), 4, 'X')

# offset of the knee/elbow IK pole
POLE_OFFSET = 0.5

# constatnts
ONES_VEC = Vector((1, 1, 1))
ZERO_VEC = Vector((0, 0, 0))

SUPPORTS_ACTION_SLOTS = hasattr(bpy.types, "ActionSlot")

class Mode(enum.IntEnum):
    ALL = 0
    MAKE_CTRLS_ONLY = 1
    APPLY_ANIMATION_ONLY = 2

class AnimationContext():
    """Used for save and restore the animation related context of the scene and object"""
    def __init__(self, scene, obj=None):
        self.scene = scene
        self.obj = obj
    def __enter__(self):
        self._frame = self.scene.frame_current
        if self.obj and self.obj.animation_data:
            self._action = self.obj.animation_data.action
            if SUPPORTS_ACTION_SLOTS:
                self._action_slot = self.obj.animation_data.action_slot
            else:
                self._action_slot = None
        else:
            self._action = self._action_slot = None
        return self
    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.scene.frame_set(self._frame)
        if self.obj and self.obj.animation_data:
            if self._action:
                self.obj.animation_data.action = self._action
            if self._action_slot:
                self.obj.animation_data.action_slot = self._action_slot


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

def _create_bone_collection(armature, name, bone_pattern, theme_idx):
    if name in armature.collections:
        coll = armature.collections[name]
        armature.collections.remove(coll)
    coll = armature.collections.new(name=name)

    for bone in armature.bones:
        if re.match(bone_pattern, bone.name):
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

def _create_bone_shapes(context):
    CUBE_SHAPE_SIZE = 0.07
    CUBE_SHAPE_NAME = '_CubeBoneShape'
    RING_SHAPE_SIZE = 0.04
    RING_SHAPE_NAME = '_RingBoneShape'
    SPHERE_SHAPE_NAME = '_SphereBoneShape'
    SPHERE_SHAPE_SIZE = 0.02

    shapes = dict()

    shapes['CUBE'] = _create_shape(name=CUBE_SHAPE_NAME, size=CUBE_SHAPE_SIZE, type='CUBE')
    shapes['SPHERE'] = _create_shape(name=SPHERE_SHAPE_NAME, size=SPHERE_SHAPE_SIZE, type='SPHERE') 
    shapes['RING'] = _create_shape(name=RING_SHAPE_NAME, size=RING_SHAPE_SIZE, type='RING')

    context.scene.collection.objects.link(shapes['CUBE'])
    context.collection.objects.link(shapes['SPHERE'])
    context.collection.objects.link(shapes['RING'])

    return shapes

def _apply_shape(bone, shape, scale=1.0):
    bone.custom_shape = shape
    bone.custom_shape_scale_xyz = (ONES_VEC / bone.length) * scale

def _calc_weapon_mesh_contoller_pos(rig):
    bone_to_pos = dict()
    obj = find_animated_weapon_object(rig)
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

def _get_active_mesh_bones(rig):
    mesh_bones = set()
    obj = find_animated_weapon_object(rig)
    if obj:
        for vg in obj.vertex_groups:
            mesh_bones.add(vg.name)
    return mesh_bones

def _get_mesh_bone_ctrls(rig):
    ske_bones = rig['bf2_bones']
    mesh_bone_ids = ske_weapon_part_ids(rig)
    mesh_bone_ctrls = set()
    for i, ske_bone in enumerate(ske_bones):
        if i in mesh_bone_ids:
            mesh_bone_ctrls.add(ske_bone + '.CTRL')
    return mesh_bone_ctrls

def _get_actions(obj):
    if SUPPORTS_ACTION_SLOTS:
        for action in bpy.data.actions:
            for slot in action.slots:
                if slot.identifier == 'OB' + obj.name:
                    yield(action, slot)
                    continue
    elif obj.animation_data:
        yield (obj.animation_data.action, None)

def _apply_action(context, obj, action, slot):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if slot:
        obj.animation_data.action_slot = slot
    context.view_layer.update()

def _reapply_animation_to_ctrls(context, rig, mesh_bones, ctrl_bone_to_offset):
    # rig.animation_data.action = bpy.data.actions['1p_m1garand_reload']
    for action, slot in _get_actions(rig):
        keyframes_to_delete = dict()
        with AnimationContext(context.scene):
            _apply_action(context, rig, action, slot)
            for (target, offset) in ctrl_bone_to_offset:
                source_name = _is_ctrl_of(target.bone)
                source = rig.pose.bones[source_name]
                keyframes = _keyframes_as_dict(source)
                for frame_idx, frame_data in sorted(keyframes.items()):
                    context.scene.frame_set(frame_idx)
                    context.view_layer.update()

                    target_pos = offset.normalized()
                    target_pos.rotate(source.matrix @ BONE_ROT_FIX)
                    target_pos *= offset.length
                    target_pos += source.matrix.translation

                    m = source.matrix.copy()
                    m.translation = target_pos
                    target.matrix = m

                    for data_path in ('location', 'rotation_quaternion'):
                        for data_index, _ in frame_data.get(data_path, {}).items():
                            target.keyframe_insert(data_path=data_path, index=data_index, frame=frame_idx)

                            # delete all keyframes for orignal mesh bones
                            # otherwise the CHILD_OF constraint will mess them up
                            if source_name in mesh_bones:
                                to_delete = keyframes_to_delete.setdefault(source_name, [])
                                to_delete.append({'data_path': data_path, 'index': data_index, 'frame': frame_idx})

        context.view_layer.update()
        for source_name, to_delete in keyframes_to_delete.items():
            source = rig.pose.bones[source_name]
            for kwargs in to_delete:
                source.keyframe_delete(**kwargs)


def _rollback_controllers(context, rig):
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

def setup_controllers(context, rig, step=Mode.ALL):
    # cleanup previuous
    if step != Mode.APPLY_ANIMATION_ONLY:
        _rollback_controllers(context, rig)
    else:
        _remove_mesh_mask(rig)
        _set_hide_bones_in_em(context, rig, hide=False)

    if rig.name.lower() == '3p_setup':
        _setup_3p_controllers(context, rig, step)
    elif rig.name.lower() == '1p_setup':
        _setup_1p_controllers(context, rig, step)

    if step == Mode.MAKE_CTRLS_ONLY:
        rig.show_in_front = True
        # keep only mesh CTRL bones visible
        _set_hide_bones_in_em(context, rig, hide=True, blacklist=_get_mesh_bone_ctrls(rig))

def _setup_3p_controllers(context, rig, step):
    armature = rig.data
    context.view_layer.objects.active = rig

    if step != Mode.APPLY_ANIMATION_ONLY:
        bpy.ops.object.mode_set(mode='EDIT')

        # Create new bones
        _create_ctrl_bone_from(armature, source_bone='L_wrist')
        _create_ctrl_bone_from(armature, source_bone='R_wrist')
        _create_ctrl_bone_from(armature, source_bone='left_shoulder')
        _create_ctrl_bone_from(armature, source_bone='right_shoulder')

        _create_ctrl_bone_from(armature, source_bone='right_foot')
        _create_ctrl_bone_from(armature, source_bone='left_foot')

        # Arms controllers
        left_elbow = armature.edit_bones['left_elbow']
        left_elbow_CTRL_pos = Vector((1, 0, 0))
        left_elbow_CTRL_pos.rotate(left_elbow.matrix @ BONE_ROT_FIX)
        left_elbow_CTRL_pos *= POLE_OFFSET
        left_elbow_CTRL_pos += left_elbow.head

        right_elbow = armature.edit_bones['right_elbow']
        right_elbow_CTRL_pos = Vector((1, 0, 0))
        right_elbow_CTRL_pos.rotate(right_elbow.matrix @ BONE_ROT_FIX)
        right_elbow_CTRL_pos *= -POLE_OFFSET
        right_elbow_CTRL_pos += right_elbow.head

        _create_ctrl_bone(armature, source_bone='left_elbow', pos=left_elbow_CTRL_pos)
        _create_ctrl_bone(armature, source_bone='right_elbow', pos=right_elbow_CTRL_pos)

        left_knee = armature.edit_bones['left_knee']
        left_knee_CTRL_pos = Vector((0, 1, 0))
        left_knee_CTRL_pos.rotate(left_knee.matrix @ BONE_ROT_FIX)
        left_knee_CTRL_pos *= POLE_OFFSET
        left_knee_CTRL_pos += left_knee.head

        right_knee = armature.edit_bones['right_knee']
        right_knee_CTRL_pos = Vector((0, 1, 0))
        right_knee_CTRL_pos.rotate(right_knee.matrix @ BONE_ROT_FIX)
        right_knee_CTRL_pos *= POLE_OFFSET
        right_knee_CTRL_pos += right_knee.head

        _create_ctrl_bone(armature, source_bone='left_knee', pos=left_knee_CTRL_pos)
        _create_ctrl_bone(armature, source_bone='right_knee', pos=right_knee_CTRL_pos)

        # meshX controllers
        meshbone_to_pos = _calc_weapon_mesh_contoller_pos(rig)
        mesh_bones = meshbone_to_pos.keys()

        for mesh_bone, pos in meshbone_to_pos.items():
            # dummy for COPY_TRANSFORMS constraint
            _create_ctrl_bone_from(armature, source_bone=mesh_bone, name=f'{mesh_bone}_dummy')
            # actual controller bone
            _create_ctrl_bone(armature, source_bone=f'{mesh_bone}_dummy.CTRL', name=mesh_bone, pos=pos)
    else:
        mesh_bones = _get_active_mesh_bones(rig)

    if step == Mode.MAKE_CTRLS_ONLY:
        return

    bpy.ops.object.mode_set(mode='POSE')

    L_wrist_CTRL = rig.pose.bones['L_wrist.CTRL']
    R_wrist_CTRL = rig.pose.bones['R_wrist.CTRL']
    left_shoulder_CTRL = rig.pose.bones['left_shoulder.CTRL']
    right_shoulder_CTRL = rig.pose.bones['right_shoulder.CTRL']
    right_elbow_CTRL = rig.pose.bones['right_elbow.CTRL']
    left_elbow_CTRL = rig.pose.bones['left_elbow.CTRL']
    right_foot_CTRL = rig.pose.bones['right_foot.CTRL']
    left_foot_CTRL = rig.pose.bones['left_foot.CTRL']
    right_knee_CTRL = rig.pose.bones['right_knee.CTRL']
    left_knee_CTRL = rig.pose.bones['left_knee.CTRL']

    shapes = _create_bone_shapes(context)
    _apply_shape(L_wrist_CTRL, shapes['RING'], scale=1.2)
    _apply_shape(R_wrist_CTRL, shapes['RING'], scale=1.2)
    _apply_shape(right_shoulder_CTRL, shapes['CUBE'])
    _apply_shape(left_shoulder_CTRL, shapes['CUBE'])
    _apply_shape(right_elbow_CTRL, shapes['CUBE'])
    _apply_shape(left_elbow_CTRL, shapes['CUBE'])
    _apply_shape(right_foot_CTRL, shapes['SPHERE'], scale=3)
    _apply_shape(left_foot_CTRL, shapes['SPHERE'], scale=3)
    _apply_shape(right_knee_CTRL, shapes['CUBE'])
    _apply_shape(left_knee_CTRL, shapes['CUBE'])

    _apply_shape(rig.pose.bones['root'], shapes['SPHERE'], scale=2)

    for mesh_bone in mesh_bones:
        mesh_bone_ctrl = rig.pose.bones[mesh_bone + '.CTRL']
        _apply_shape(mesh_bone_ctrl, shapes['CUBE'], scale=0.2)

    # re-apply loaded animation for controllers
    ctrl_bone_to_offset = [
        (L_wrist_CTRL, ZERO_VEC),
        (R_wrist_CTRL, ZERO_VEC),
        (right_shoulder_CTRL, ZERO_VEC),
        (left_shoulder_CTRL, ZERO_VEC),
        (right_elbow_CTRL, Vector((-POLE_OFFSET, 0, 0))),
        (left_elbow_CTRL, Vector((POLE_OFFSET, 0, 0))),
        (right_foot_CTRL, ZERO_VEC),
        (left_foot_CTRL, ZERO_VEC),
        (left_knee_CTRL, Vector((0, POLE_OFFSET, 0))),
        (right_knee_CTRL, Vector((0, POLE_OFFSET, 0))),
    ]

    # first pass: transfer keyframes from actual mesh bones to dummies
    for mesh_bone in mesh_bones:
        mesh_bone_dummy = rig.pose.bones[mesh_bone + '_dummy.CTRL']
        ctrl_bone_to_offset.append((mesh_bone_dummy, ZERO_VEC))  

    _reapply_animation_to_ctrls(context, rig, mesh_bones, ctrl_bone_to_offset)

    # second pass: transfer keyframes from dummies to actual controllers
    ctrl_bone_to_offset = list()
    dummy_mesh_ctrls = set()
    for mesh_bone in mesh_bones:
        dummy_mesh_ctrls.add(mesh_bone + '_dummy.CTRL')
        mesh_bone_ctrl = rig.pose.bones[mesh_bone + '.CTRL']
        mesh_bone_offset = mesh_bone_ctrl.bone.matrix_local.translation
        ctrl_bone_to_offset.append((mesh_bone_ctrl, mesh_bone_offset))
 
    _reapply_animation_to_ctrls(context, rig, dummy_mesh_ctrls, ctrl_bone_to_offset)

    # Constraints setup

    # meshX bones controllers
    for mesh_bone in mesh_bones:
        dummy = mesh_bone + '_dummy.CTRL'
        ctrl = mesh_bone + '.CTRL'
        cp_trans = rig.pose.bones[mesh_bone].constraints.new(type='COPY_TRANSFORMS')
        cp_trans.target = rig
        cp_trans.subtarget = dummy
        cp_trans.name = AUTO_SETUP_ID + '_COPY_TRANSFORM_' + mesh_bone

        child_of = rig.pose.bones[dummy].constraints.new(type='CHILD_OF')
        child_of.target = rig
        child_of.subtarget = ctrl
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
    ik = rig.pose.bones['left_collar'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = left_shoulder_CTRL.name
    ik.chain_count = 1
    ik.name = AUTO_SETUP_ID + '_IK_left_collar'

    ik = rig.pose.bones['left_wrist1'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = L_wrist_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = left_elbow_CTRL.name
    ik.pole_angle = 0
    ik.chain_count = 4
    ik.name = AUTO_SETUP_ID + '_IK_left_wrist1'
    ik.use_tail = False

    ik = rig.pose.bones['right_collar'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = right_shoulder_CTRL.name
    ik.chain_count = 1
    ik.name = AUTO_SETUP_ID + '_IK_right_collar'

    ik = rig.pose.bones['right_ullna'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = R_wrist_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = right_elbow_CTRL.name
    ik.pole_angle = math.radians(180)
    ik.chain_count = 3
    ik.name = AUTO_SETUP_ID + '_IK_right_ullna'
    ik.use_tail = False

    # legs
    cp_rot = rig.pose.bones['left_foot'].constraints.new(type='COPY_ROTATION')
    cp_rot.target = rig
    cp_rot.subtarget = left_foot_CTRL.name
    cp_rot.name = AUTO_SETUP_ID + '_COPY_ROTATION_left_foot'

    cp_rot = rig.pose.bones['right_foot'].constraints.new(type='COPY_ROTATION')
    cp_rot.target = rig
    cp_rot.subtarget = right_foot_CTRL.name
    cp_rot.name = AUTO_SETUP_ID + '_COPY_ROTATION_right_foot'

    ik = rig.pose.bones['left_lowerleg'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = left_foot_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = left_knee_CTRL.name
    ik.pole_angle = math.radians(-90)
    ik.chain_count = 3
    ik.name = AUTO_SETUP_ID + '_IK_left_lowerleg'

    ik = rig.pose.bones['right_lowerleg'].constraints.new(type='IK')
    ik.target = rig
    ik.subtarget = right_foot_CTRL.name
    ik.pole_target = rig
    ik.pole_subtarget = right_knee_CTRL.name
    ik.pole_angle = math.radians(-90)
    ik.chain_count = 3
    ik.name = AUTO_SETUP_ID + '_IK_right_lowerleg'

    # declutter viewport by changing bone display mode
    # and hiding all bones except controllers and finger bones
    finger_bones = [p + n + s for p in {'right_', 'left_'} for n in {'index', 'ring', 'thumb'} for s in {'1', '2', '3'}]
    whitelist = finger_bones + ['head', 'neck', 'chin', 'joint20', 'torso', 'spine3', 'spine2', 'root']
    blacklist = dummy_mesh_ctrls
    rig.show_in_front = True
    armature.display_type = 'WIRE'
    for pose_bone in rig.pose.bones:
        bone = pose_bone.bone
        if bone.name in blacklist or not _is_ctrl_of(bone) and bone.name not in whitelist:
            if hasattr(pose_bone, 'hide'):
                pose_bone.hide = True # Blender 5.0 onwards
            else:
                bone.hide = True # Blender 4.5 and earlier

    _create_bone_collection(armature, 'BF2_LEFT_FINGERS', r'^left_(index|ring|thumb)\d$', 3) # green
    _create_bone_collection(armature, 'BF2_RIGHT_FINGERS', r'^right_(index|ring|thumb)\d$', 4) # blue
    _create_bone_collection(armature, 'BF2_WEAPON_BONES', r'^mesh[1-8]', 9) # yellow
    _create_bone_collection(armature, 'BF2_KIT_BONES', r'^mesh(9|1[0-6])$', 1) # red

def _setup_1p_controllers(context, rig, step):
    armature = rig.data
    context.view_layer.objects.active = rig

    if step != Mode.APPLY_ANIMATION_ONLY:
        bpy.ops.object.mode_set(mode='EDIT')

        # Create new bones
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
        meshbone_to_pos = _calc_weapon_mesh_contoller_pos(rig)
        mesh_bones = meshbone_to_pos.keys()

        for mesh_bone, pos in meshbone_to_pos.items():
            _create_ctrl_bone(armature, source_bone=mesh_bone, pos=pos)
    else:
        mesh_bones = _get_active_mesh_bones(rig)

    if step == Mode.MAKE_CTRLS_ONLY:
        return

    bpy.ops.object.mode_set(mode='POSE')

    L_wrist_CTRL = rig.pose.bones['L_wrist.CTRL']
    R_wrist_CTRL = rig.pose.bones['R_wrist.CTRL']
    L_elbow_CTRL = rig.pose.bones['L_elbow.CTRL']
    R_elbow_CTRL = rig.pose.bones['R_elbow.CTRL']
    L_arm_CTRL = rig.pose.bones['L_arm.CTRL']
    R_arm_CTRL = rig.pose.bones['R_arm.CTRL']

    Camerabone = rig.pose.bones['Camerabone']

    shapes = _create_bone_shapes(context)

    _apply_shape(L_wrist_CTRL, shapes['RING'])
    _apply_shape(R_wrist_CTRL, shapes['RING'])
    _apply_shape(L_elbow_CTRL, shapes['CUBE'])
    _apply_shape(R_elbow_CTRL, shapes['CUBE'])
    _apply_shape(L_arm_CTRL, shapes['CUBE'])
    _apply_shape(R_arm_CTRL, shapes['CUBE'])
    _apply_shape(Camerabone, shapes['SPHERE'])

    for mesh_bone in mesh_bones:
        mesh_bone_ctrl = rig.pose.bones[mesh_bone + '.CTRL']
        _apply_shape(mesh_bone_ctrl, shapes['CUBE'], scale=0.2)

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

    # re-apply loaded animation for controllers
    _reapply_animation_to_ctrls(context, rig, mesh_bones, ctrl_bone_to_offset)

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
    finger_bones = [p + n + s for p in {'L_', 'R_'} for n in {'pink', 'index', 'point', 'ring', 'thumb'} for s in {'_1', '_2', '_3'}]
    whitelist = finger_bones + ['Camerabone', 'L_collar', 'R_collar']
    rig.show_in_front = True
    armature.display_type = 'WIRE'
    for pose_bone in rig.pose.bones:
        bone = pose_bone.bone
        if not _is_ctrl_of(bone) and bone.name not in whitelist:
            if hasattr(pose_bone, 'hide'):
                pose_bone.hide = True # Blender 5.0 onwards
            else:
                bone.hide = True # Blender 4.5 and earlier

    _create_bone_collection(armature, 'BF2_LEFT_ARM', r'^L_.*', 3) # green
    _create_bone_collection(armature, 'BF2_LEFT_FINGERS', r'^L_(pink|index|point|ring|thumb)_\d$', 3) # green
    _create_bone_collection(armature, 'BF2_RIGHT_ARM', r'^R_.*', 4) # blue
    _create_bone_collection(armature, 'BF2_RIGHT_FINGERS', r'^R_(pink|index|point|ring|thumb)_\d$', 4) # blue
    _create_bone_collection(armature, 'BF2_MESH_BONES', r'^mesh\d+', 9) # yellow

    bpy.ops.object.mode_set(mode='OBJECT')

def _set_hide_bones_in_em(context, rig, hide=True, blacklist=[]):
    armature = rig.data
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.edit_bones:
        if bone.name not in blacklist:
            bone.hide = hide

MASK_MOD_NAME = 'bf2_bone_mask'

def _remove_mesh_mask(rig):
    obj = find_animated_weapon_object(rig)
    if not obj:
        return
    
    for mod in obj.modifiers:
        if mod.name == MASK_MOD_NAME:
            obj.modifiers.remove(mod)
            break

def toggle_mesh_mask_mesh_for_active_bone(context, rig):        
    ctrl_bone = context.active_bone

    obj = find_animated_weapon_object(rig)
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

    bone_name = _is_ctrl_of(ctrl_bone)
    if bone_name is None:
        return

    bone = rig.data.edit_bones[bone_name]

    # 3P controlls a dummy
    if _is_ctrl_of(bone):
        bone_name = _is_ctrl_of(bone)

    if bone_name and active_vg != bone_name:
        mask_mod.vertex_group = bone_name
        _set_hide_bones_in_em(context, rig, hide=True, blacklist=[ctrl_bone.name])
    else:
        mask_mod.vertex_group = ""
        _set_hide_bones_in_em(context, rig, hide=False)
        _set_hide_bones_in_em(context, rig, hide=True, blacklist=_get_mesh_bone_ctrls(rig))

def _get_bone_fcurves(pose_bone, data_path):
    obj = pose_bone.id_data
    path = f'pose.bones["{bpy.utils.escape_identifier(pose_bone.name)}"].{data_path}'

    if obj.animation_data is None:
        return

    action = obj.animation_data.action
    if not SUPPORTS_ACTION_SLOTS: # < Blender 4.4, use legacy API
        fcurves = action.fcurves
    else:
        slot = obj.animation_data.action_slot
        if slot is None:
            return
        # TODO: update to support layers in 5.0
        channelbag = action.layers[0].strips[0].channelbag(slot)
        if channelbag is None:
            return
        fcurves = channelbag.fcurves

    for fcu in fcurves:
        if fcu.data_path.startswith(path):
            yield fcu

def _keyframes_as_dict(pose_bone):
    keyframes = dict()
    for data_type in ['location', 'rotation_quaternion']:
        for fcurve in _get_bone_fcurves(pose_bone, data_type):
            for kp in fcurve.keyframe_points:
                frame = keyframes.setdefault(int(kp.co[0]), dict())
                frame_data = frame.setdefault(data_type, dict())
                frame_data[fcurve.array_index] = kp
    return keyframes

def _reparent_keyframes(context, pose_bone, parent):
    rig = pose_bone.id_data
    with AnimationContext(context.scene, rig):
        for action, slot in _get_actions(rig):
            _apply_action(context, rig, action, slot)
            keyframes = _keyframes_as_dict(pose_bone)
            for frame_idx, frame_data in sorted(keyframes.items()):
                context.scene.frame_set(frame_idx)
                context.view_layer.update()

                if parent:
                    matrix_basis = pose_bone.bone.convert_local_to_pose(
                                pose_bone.matrix,
                                pose_bone.bone.matrix_local,
                                parent_matrix=parent.matrix,
                                parent_matrix_local=parent.bone.matrix_local,
                                invert=True
                            )
                else:
                    matrix_basis = pose_bone.bone.convert_local_to_pose(
                        pose_bone.matrix,
                        pose_bone.bone.matrix_local,
                        invert=True
                    )

                pos, rot, _ = matrix_basis.decompose()
                for data_path, new_data, in [('location', pos), ('rotation_quaternion', rot)]:
                    for data_index, kp in frame_data.get(data_path, {}).items():
                        delta = new_data[data_index] - kp.co[1]
                        kp.handle_right[1] += delta
                        kp.handle_left[1] += delta
                        kp.co[1] += delta

    context.view_layer.update()

def reparent_bones(context, rig, target_bones, parent_bone, reporter=DEFAULT_REPORTER):
    for target_bone in target_bones:
        if target_bone == parent_bone:
            continue

        context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='POSE')
        target_pose_bone = rig.pose.bones[target_bone]
        if parent_bone:
            parent_pose_bone = rig.pose.bones[parent_bone]
        else:
            parent_pose_bone = None

        if target_bone in rig['bf2_bones']:
            reporter.warning("Chaning parent of the BF2 skeleton bone, this will mess up your export!")

        _reparent_keyframes(context, target_pose_bone, parent_pose_bone)

        bpy.ops.object.mode_set(mode='EDIT')
        target_edit_bone = rig.data.edit_bones[target_bone]
        if parent_bone:
            parent_edit_bone = rig.data.edit_bones[parent_bone]
        else:
            parent_edit_bone = None
        target_edit_bone.parent = parent_edit_bone
        bpy.ops.object.mode_set(mode='POSE') 
