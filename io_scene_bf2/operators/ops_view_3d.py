import bpy # type: ignore
import bmesh # type: ignore
import traceback

from bpy.props import IntProperty, BoolProperty, EnumProperty # type: ignore
from ..core.anim_utils import toggle_mesh_mask_mesh_for_active_bone, setup_controllers, reparent_bones
from ..core.skeleton import is_bf2_seketon
from ..core.mesh import AnimUv, _flip_uv
from ..core.object_template import parse_geom_type_safe, NONVIS_PRFX, COL_SUFFIX

def _bf2_setup_started(context, rig):
    context.scene['bf2_is_setup'] = rig.name
    bpy.types.VIEW3D_MT_editor_menus.append(menu_func_view3d)

def _bf2_is_setup(context):
    return context.scene.get('bf2_is_setup')

def _bf2_setup_finished(context):
    if 'bf2_is_setup' in context.scene:
        del context.scene['bf2_is_setup']
    bpy.types.VIEW3D_MT_editor_menus.remove(menu_func_view3d)


class IMPORT_OT_bf2_anim_ctrl_setup_mask(bpy.types.Operator):
    bl_idname = "bf2_animation.anim_ctrl_setup_mask"
    bl_label = "Toggle masking weapon mesh that corresponds to the active bone"

    def execute(self, context):
        try:
            toggle_mesh_mask_mesh_for_active_bone(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)


class IMPORT_OT_bf2_anim_ctrl_setup_begin(bpy.types.Operator):
    bl_idname = "bf2_animation.anim_ctrl_setup_begin"
    bl_label = "Setup controllers"
    bl_description = "Setup animation controller bones and basic IK constraints (for 1P animations only!)"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Please move each 'meshX.CTRL' bone to the desired loaction,")
        layout.label(text="it will be used as pivot for the corresponding weapon part.")
        layout.label(text="You can toggle showing only a specific weapon part that corresponds")
        layout.label(text="to the active bone with 'Mask mesh for active bone' in the top menu.")
        layout.label(text="")
        layout.label(text="When You are done, click on 'Finish setup'")

    @classmethod
    def poll(cls, context):
        rig = context.view_layer.objects.active
        return rig and is_bf2_seketon(rig)

    def execute(self, context):
        try:
            setup_controllers(context, self.rig, step=1)
            _bf2_setup_started(context, self.rig)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        self.rig = context.view_layer.objects.active
        return context.window_manager.invoke_props_dialog(self, width=500)

    def cancel(self, context):
        bpy.ops.bf2_animation.anim_ctrl_setup_begin('INVOKE_DEFAULT')


class IMPORT_OT_bf2_anim_ctrl_setup_end(bpy.types.Operator):
    bl_idname = "bf2_animation.anim_ctrl_setup_end"
    bl_label = "Finish controller setup"

    def execute(self, context):
        try:
            setup_controllers(context, self.rig, step=2)
            _bf2_setup_finished(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        rig_name = _bf2_is_setup(context)
        self.rig = bpy.data.objects[rig_name]
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)


def menu_func_view3d(self, context):
    self.layout.operator(IMPORT_OT_bf2_anim_ctrl_setup_end.bl_idname, text="Finish setup")
    self.layout.operator(IMPORT_OT_bf2_anim_ctrl_setup_mask.bl_idname, text="Mask mesh for active bone")

# --------------------------------------------------------------------

class EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix(bpy.types.Operator):
    bl_idname = "bf2_mesh.select_uv_matrix"
    bl_label = "Select Animated UV Matrix"
    bl_description = "Selects all elements with the common matrix index of the animated UVs"

    uv_matrix_index: IntProperty(
        default=0,
        options={'HIDDEN'},
        min=0,
        max=6
    ) # type: ignore

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data

        bm = bmesh.from_edit_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        layer = bm.verts.layers.int.get('animuv_matrix_index')

        for vert in bm.verts:
            if layer and vert[layer] == self.uv_matrix_index:
                vert.select_set(True)
            else:
                vert.select_set(False)

        bm.select_mode |= {'VERT'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}

class EDIT_MESH_SELECT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EDIT_MESH_SELECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        op_name = EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix.bl_idname
        self.layout.operator(op_name, text="Select Left Wheel Rotation").uv_matrix_index = AnimUv.L_WHEEL_ROTATION
        self.layout.operator(op_name, text="Select Left Wheel Translation").uv_matrix_index = AnimUv.L_WHEEL_TRANSLATION
        self.layout.operator(op_name, text="Select Right Wheel Rotation").uv_matrix_index = AnimUv.R_WHEEL_ROTATION
        self.layout.operator(op_name, text="Select Right Wheel Translation").uv_matrix_index = AnimUv.R_WHEEL_TRANSLATION
        self.layout.operator(op_name, text="Select Left Track Translation").uv_matrix_index = AnimUv.L_TRACK_TRANSLATION
        self.layout.operator(op_name, text="Select Right Track Translation").uv_matrix_index = AnimUv.R_TRACK_TRANSLATION

def menu_func_edit_mesh_select(self, context):
    self.layout.menu(EDIT_MESH_SELECT_MT_bf2_submenu.bl_idname, text="BF2")

def _get_2d_cursor_location(context):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            return area.spaces.active.cursor_location

class EDIT_MESH_OT_bf2_set_anim_uv_rotation_center(bpy.types.Operator):
    bl_idname = "bf2_mesh.set_uv_rotation_center"
    bl_label = "Set Animated UV Roation Center"
    bl_description = "Sets the center of UV rotation for the selected elements to the 2D cursor"

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data

        uv = _flip_uv(_get_2d_cursor_location(context))
        if 'animuv_rot_center' not in mesh.attributes:
            mesh.attributes.new('animuv_rot_center', 'FLOAT2', 'POINT')
        mesh.attributes.active = mesh.attributes['animuv_rot_center']
        bpy.ops.mesh.attribute_set(value_float_vector_2d=uv)
        return {'FINISHED'}

class EDIT_MESH_OT_bf2_set_anim_uv_matrix(bpy.types.Operator):
    bl_idname = "bf2_mesh.set_uv_matrix"
    bl_label = "Set Animated UV Matrix"
    bl_description = "Sets the matrix index for the the animated UVs"

    uv_matrix_index: IntProperty(
        default=0,
        options={'HIDDEN'},
        min=0,
        max=6
    ) # type: ignore

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data
        if 'animuv_matrix_index' not in mesh.attributes:
            mesh.attributes.new('animuv_matrix_index', 'INT', 'POINT')
        mesh.attributes.active = mesh.attributes['animuv_matrix_index']
        bpy.ops.mesh.attribute_set(value_int=self.uv_matrix_index)
        return {'FINISHED'}

class EDIT_MESH_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EDIT_MESH_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        op_matrix = EDIT_MESH_OT_bf2_set_anim_uv_matrix.bl_idname
        op_rot_center = EDIT_MESH_OT_bf2_set_anim_uv_rotation_center.bl_idname
        self.layout.operator(op_rot_center, text="Set Animated UV Rotation Center")
        self.layout.operator(op_matrix, text="Clear Wheel/Track Rotation/Translation").uv_matrix_index = AnimUv.NONE
        self.layout.operator(op_matrix, text="Set Left Wheel Rotation").uv_matrix_index = AnimUv.L_WHEEL_ROTATION
        self.layout.operator(op_matrix, text="Set Left Wheel Translation").uv_matrix_index = AnimUv.L_WHEEL_TRANSLATION
        self.layout.operator(op_matrix, text="Set Right Wheel Rotation").uv_matrix_index = AnimUv.R_WHEEL_ROTATION
        self.layout.operator(op_matrix, text="Set Right Wheel Translation").uv_matrix_index = AnimUv.R_WHEEL_TRANSLATION
        self.layout.operator(op_matrix, text="Set Left Track Translation").uv_matrix_index = AnimUv.L_TRACK_TRANSLATION
        self.layout.operator(op_matrix, text="Set Right Track Translation").uv_matrix_index = AnimUv.R_TRACK_TRANSLATION

# --------------------------------------------------------------------

class POSE_OT_bf2_change_parent(bpy.types.Operator):
    bl_idname = "bf2_armature.change_parent"
    bl_label = "Change Parent"
    bl_description = "Parents all selected bones to the active bone while also adjusting all position/rotation keyframes"

    @classmethod
    def poll(cls, context):
        parent = context.active_pose_bone
        if not parent or parent not in context.selected_pose_bones_from_active_object:
            cls.poll_message_set("No active bone")
            return False
        selected = list(filter(lambda b: b.name != parent.name, context.selected_pose_bones_from_active_object))
        if not selected:
            cls.poll_message_set("No bones selected (need at least two, the active one will be the parent)")
            return False
        return True

    def execute(self, context):
        rig = context.view_layer.objects.active
        parent_bone = context.active_pose_bone.name
        bones = list(filter(lambda b: b != parent_bone, map(lambda b: b.name, context.selected_pose_bones_from_active_object)))
        reparent_bones(rig, bones, parent_bone)
        return {'FINISHED'}


class POSE_OT_bf2_clear_parent(bpy.types.Operator):
    bl_idname = "bf2_armature.clear_parent"
    bl_label = "Clear Parent"
    bl_description = "Clears parent of all selected bones while also adjusting all position/rotation keyframes"

    @classmethod
    def poll(cls, context):
        if not context.selected_pose_bones_from_active_object:
            cls.poll_message_set("No bones selected")
            return False
        return True

    def execute(self, context):
        rig = context.view_layer.objects.active
        bones = list(map(lambda b: b.name, context.selected_pose_bones_from_active_object))
        reparent_bones(rig, bones, None)
        return {'FINISHED'}

def menu_func_edit_mesh(self, context):
    self.layout.menu(EDIT_MESH_MT_bf2_submenu.bl_idname, text="BF2")

class POSE_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "POSE_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(POSE_OT_bf2_change_parent.bl_idname)
        self.layout.operator(POSE_OT_bf2_clear_parent.bl_idname)
        self.layout.operator(IMPORT_OT_bf2_anim_ctrl_setup_begin.bl_idname)

def menu_func_pose(self, context):
    self.layout.menu(POSE_MT_bf2_submenu.bl_idname, text="BF2")

# --------------------------------------------------------------------

class OBJECT_SHOWHIDE_OT_bf2_show_hide(bpy.types.Operator):
    bl_idname = "bf2_object.hide_col"
    bl_label = "Show/Hide Collision Meshes"
    bl_description = "Show/Hide all Collision Meshes"

    show: BoolProperty(
        name="Show CollisionMesh",
        default=False
    ) # type: ignore

    def _exec(self, obj):
        if obj is None:
            return
        if obj.name.startswith(NONVIS_PRFX):
            for col in obj.children:
                if COL_SUFFIX in col.name:
                    col.hide_set(not self.show)
        for child in obj.children:
            self._exec(child)

    def execute(self, context):
        try:
            self._exec(self.root)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        self.root = self.find_root(context.view_layer.objects.active)
        return self.execute(context)

    @classmethod
    def find_root(cls, obj):
        if obj is None:
            return None
        if parse_geom_type_safe(obj):
            return obj
        return cls.find_root(obj.parent)

    @classmethod
    def poll(cls, context):
        try:
            return cls.find_root(context.view_layer.objects.active)
        except Exception as e:
            cls.poll_message_set(str(e))
            return False

class OBJECT_SHOWHIDE_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(OBJECT_SHOWHIDE_OT_bf2_show_hide.bl_idname, text="Show Collision Meshes").show = True
        self.layout.operator(OBJECT_SHOWHIDE_OT_bf2_show_hide.bl_idname, text="Hide Collision Meshes").show = False


def menu_func_object_showhide(self, context):
    self.layout.menu(OBJECT_SHOWHIDE_MT_bf2_submenu.bl_idname, text="BF2")


def register():
    bpy.utils.register_class(POSE_OT_bf2_change_parent)
    bpy.utils.register_class(POSE_OT_bf2_clear_parent)
    bpy.utils.register_class(POSE_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_pose.append(menu_func_pose)

    bpy.utils.register_class(EDIT_MESH_OT_bf2_set_anim_uv_rotation_center)
    bpy.utils.register_class(EDIT_MESH_OT_bf2_set_anim_uv_matrix)
    bpy.utils.register_class(EDIT_MESH_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func_edit_mesh)

    bpy.utils.register_class(EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix)
    bpy.utils.register_class(EDIT_MESH_SELECT_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_select_edit_mesh.append(menu_func_edit_mesh_select)

    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_begin)
    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_mask)

    bpy.utils.register_class(OBJECT_SHOWHIDE_OT_bf2_show_hide)
    bpy.utils.register_class(OBJECT_SHOWHIDE_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_object_showhide.append(menu_func_object_showhide)

def unregister():
    bpy.types.VIEW3D_MT_object_showhide.remove(menu_func_object_showhide)
    bpy.utils.unregister_class(OBJECT_SHOWHIDE_MT_bf2_submenu)
    bpy.utils.unregister_class(OBJECT_SHOWHIDE_OT_bf2_show_hide)

    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_begin)

    bpy.types.VIEW3D_MT_select_edit_mesh.remove(menu_func_edit_mesh_select)
    bpy.utils.unregister_class(EDIT_MESH_SELECT_MT_bf2_submenu)
    bpy.utils.unregister_class(EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix)

    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func_edit_mesh)
    bpy.utils.unregister_class(EDIT_MESH_MT_bf2_submenu)
    bpy.utils.unregister_class(EDIT_MESH_OT_bf2_set_anim_uv_matrix)
    bpy.utils.unregister_class(EDIT_MESH_OT_bf2_set_anim_uv_rotation_center)

    bpy.types.VIEW3D_MT_pose.remove(menu_func_pose)
    bpy.utils.unregister_class(POSE_MT_bf2_submenu)
    bpy.utils.unregister_class(POSE_OT_bf2_clear_parent)
    bpy.utils.unregister_class(POSE_OT_bf2_change_parent)
