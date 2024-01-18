import bpy
import bmesh
import traceback

from bpy.props import IntProperty
from ..core.animation_ctrl_setup import toggle_mesh_mask_mesh_for_active_bone, setup_controllers
from ..core.mesh import AnimUv, _flip_uv

def _bf2_setup_started(context):
    context.scene['bf2_is_setup'] = True
    bpy.types.VIEW3D_MT_editor_menus.append(menu_func_view3d)


def _bf2_is_setup(context):
    return 'bf2_is_setup' in context.scene and context.scene['bf2_is_setup']


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

    def draw(self, context):
        layout = self.layout

        layout.label(text="Please move all 'meshX.CTRL' bones to desired loaction to best match with the weapon meshes.")
        layout.label(text="You can toggle showing only a specific weapon part that corresponds")
        layout.label(text="to the active bone with 'Mask mesh for active bone' in the top menu.")
        layout.label(text="")
        layout.label(text="When You are done, select 'Finish setup'")

    def execute(self, context):
        try:
            setup_controllers(context, step=1)
            _bf2_setup_started(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def cancel(self, context):
        bpy.ops.bf2_animation.anim_ctrl_setup_begin('INVOKE_DEFAULT')


class IMPORT_OT_bf2_anim_ctrl_setup_end(bpy.types.Operator):
    bl_idname = "bf2_animation.anim_ctrl_setup_end"
    bl_label = "Finish controller setup"

    def execute(self, context):
        try:
            setup_controllers(context, step=2)
            _bf2_setup_finished(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)


def menu_func_view3d(self, context):
    self.layout.operator(IMPORT_OT_bf2_anim_ctrl_setup_end.bl_idname, text="Finish setup")
    self.layout.operator(IMPORT_OT_bf2_anim_ctrl_setup_mask.bl_idname, text="Mask mesh for active bone")


class EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix(bpy.types.Operator):
    bl_idname = "bf2_mesh.select_uv_matrix"
    bl_label = "Select Animated UV Matrix"
    bl_description = "Selects all elements with the common matrix index of the animated UVs"

    uv_matrix_index: IntProperty(
        default=0,
        options={'HIDDEN'},
        min=0,
        max=6
    )

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
    )

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

def menu_func_edit_mesh(self, context):
    self.layout.menu(EDIT_MESH_MT_bf2_submenu.bl_idname, text="BF2")

def register():
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

def unregister():
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
