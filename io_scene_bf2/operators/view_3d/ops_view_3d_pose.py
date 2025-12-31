import bpy # type: ignore

from .ops_view_3d_bf2 import VIEW3D_OT_bf2_anim_ctrl_setup_begin

from ...core.utils import Reporter
from ...core.anim_utils import reparent_bones

class POSE_OT_bf2_change_parent(bpy.types.Operator):
    bl_idname = "bf2.pose_change_parent"
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
        reparent_bones(context, rig, bones, parent_bone, reporter=Reporter(self.report))
        return {'FINISHED'}

class POSE_OT_bf2_clear_parent(bpy.types.Operator):
    bl_idname = "bf2.pose_clear_parent"
    bl_label = "Clear Parent"
    bl_description = "Clears parent of all selected bones while also adjusting all position/rotation keyframes"

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No bones selected")
        return context.selected_pose_bones_from_active_object

    def execute(self, context):
        rig = context.view_layer.objects.active
        bones = list(map(lambda b: b.name, context.selected_pose_bones_from_active_object))
        reparent_bones(context, rig, bones, None, reporter=Reporter(self.report))
        return {'FINISHED'}

class POSE_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "POSE_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(POSE_OT_bf2_change_parent.bl_idname)
        self.layout.operator(POSE_OT_bf2_clear_parent.bl_idname)
        self.layout.operator(VIEW3D_OT_bf2_anim_ctrl_setup_begin.bl_idname)

def menu_func_pose(self, context):
    self.layout.menu(POSE_MT_bf2_submenu.bl_idname, text="BF2")

def register():
    bpy.utils.register_class(POSE_OT_bf2_change_parent)
    bpy.utils.register_class(POSE_OT_bf2_clear_parent)
    bpy.utils.register_class(POSE_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_pose.append(menu_func_pose)


def unregister():
    bpy.types.VIEW3D_MT_pose.remove(menu_func_pose)
    bpy.utils.unregister_class(POSE_MT_bf2_submenu)
    bpy.utils.unregister_class(POSE_OT_bf2_clear_parent)
    bpy.utils.unregister_class(POSE_OT_bf2_change_parent)
