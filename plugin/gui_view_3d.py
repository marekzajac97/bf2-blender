import bpy
import traceback

from ..core.animation_ctrl_setup import toggle_mesh_mask_mesh_for_active_bone, setup_controllers

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


def register():
    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_begin)
    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.register_class(IMPORT_OT_bf2_anim_ctrl_setup_mask)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.unregister_class(IMPORT_OT_bf2_anim_ctrl_setup_begin)
