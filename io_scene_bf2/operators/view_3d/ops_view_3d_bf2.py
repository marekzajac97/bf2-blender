import bpy # type: ignore
import traceback

from ...core.anim_utils import (
    toggle_mesh_mask_mesh_for_active_bone,
    setup_controllers,
    Mode,
    AnimationContext)

from ...core.skeleton import is_bf2_skeleton

class View3DPanel_BF2:
    bl_category = "BF2"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

# --------------- animation ----------------------

def _bf2_setup_started(context, rig):
    context.scene['bf2_is_setup'] = rig.name

def _bf2_is_setup(context):
    return context.scene.get('bf2_is_setup')

def _bf2_setup_finished(context):
    if 'bf2_is_setup' in context.scene:
        del context.scene['bf2_is_setup']

class VIEW3D_OT_bf2_anim_ctrl_setup_mask(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_mask"
    bl_label = "Mask mesh for bone"
    bl_description = "Toggle mask for weapon part that corresponds to the active bone"

    def execute(self, context):
        rig = bpy.data.objects[_bf2_is_setup(context)]
        try:
            toggle_mesh_mask_mesh_for_active_bone(context, rig)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context) and context.active_bone

class VIEW3D_OT_bf2_anim_ctrl_setup_begin(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_begin"
    bl_label = "Setup controllers"
    bl_description = "Setup animation controller bones and basic IK constraints"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Please move each 'meshX.CTRL' bone to the desired loaction,")
        layout.label(text="it will be used as pivot for the corresponding weapon part.")
        layout.label(text="When You are done, click 'Finish setup' in the Sidebar, BF2 tab (toggled with `N`)")
        layout.label(text="")
        layout.label(text="You can toggle showing only a specific weapon part that corresponds")
        layout.label(text="to the active bone with 'Mask mesh for bone'.")


    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No skeleton selected")
        rig = context.view_layer.objects.active
        return rig and is_bf2_skeleton(rig)

    def execute(self, context):
        rig = context.view_layer.objects.active
        try:
            setup_controllers(context, rig, step=Mode.MAKE_CTRLS_ONLY)
            _bf2_setup_started(context, rig)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def cancel(self, context):
        bpy.ops.bf2.anim_setup_begin('INVOKE_DEFAULT')


class VIEW3D_OT_bf2_anim_ctrl_setup_end(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_end"
    bl_label = "Finish setup"
    bl_description = "Finish animation controller setup"

    def execute(self, context):
        rig = bpy.data.objects[_bf2_is_setup(context)]
        try:
            with AnimationContext(context.scene, rig):
                setup_controllers(context, rig, step=Mode.APPLY_ANIMATION_ONLY)
            _bf2_setup_finished(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)

class VIEW3D_PT_bf2_anim_Panel(View3DPanel_BF2, bpy.types.Panel):
    bl_label = "Animation"

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)

    def draw(self, context):
        self.layout.operator(VIEW3D_OT_bf2_anim_ctrl_setup_end.bl_idname)
        self.layout.operator(VIEW3D_OT_bf2_anim_ctrl_setup_mask.bl_idname)

# --------------- lightmapping ----------------------

# TODO


# ---------------------------------------------------

def register():
    # animation
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)

def unregister():
    # animation
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
