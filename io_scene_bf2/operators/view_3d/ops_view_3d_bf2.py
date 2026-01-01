import bpy # type: ignore
import traceback
import os
from pathlib import Path

from bpy.props import BoolProperty, EnumProperty, CollectionProperty # type: ignore
from bpy_extras.io_utils import ImportHelper # type: ignore

from ... import get_mod_dir
from ...core.anim_utils import (
    toggle_mesh_mask_mesh_for_active_bone,
    setup_controllers,
    Mode,
    AnimationContext)
from ...core.utils import Reporter
from ...core.skeleton import is_bf2_skeleton
from ...core.lightmaps import load_level

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

class VIEW3D_PT_bf2_animation_Panel(View3DPanel_BF2, bpy.types.Panel):
    bl_label = "Animation"

    @classmethod
    def poll(cls, context):
        return _bf2_is_setup(context)

    def draw(self, context):
        self.layout.operator(VIEW3D_OT_bf2_anim_ctrl_setup_end.bl_idname)
        self.layout.operator(VIEW3D_OT_bf2_anim_ctrl_setup_mask.bl_idname)

# --------------- lightmapping ----------------------

class VIEW3D_OT_bf2_load_level(bpy.types.Operator, ImportHelper):
    bl_idname = "bf2.load_level"
    bl_label = "Load level"
    bl_description = "Import BF2 level (static objects, heightmap and lights), make sure your level files are unpacked"

    load_static_objects: BoolProperty(
        name="Load Static Objects",
        description="Import meshes of objects defined in StaticObjects.con",
        default=True
    ) # type: ignore

    load_overgrowth: BoolProperty(
        name="Load Overgrowth",
        description="Import meshes of objects defined in OvergrowthCollision.con",
        default=True
    ) # type: ignore

    load_heightmap: BoolProperty(
        name="Load Overgrowth",
        description="Import primary heightmap and water plane defined in Heightdata.con",
        default=True
    ) # type: ignore

    load_lights: BoolProperty(
        name="Load Overgrowth",
        description="Import sun direction from Sky.con and set proper light colors",
        default=True
    ) # type: ignore

    # TODO: area thresholds

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Mod path must be defined in addon preferences")
        return get_mod_dir(context)

    def execute(self, context):
        if not os.path.isdir(self.filepath):
            self.report({"ERROR"}, f"Choosen path '{self.filepath}' is NOT a directory!")
            return {'CANCELLED'}

        mod_path = get_mod_dir(context)
        try:
            Path(self.filepath).relative_to(mod_path).as_posix().lower()
        except ValueError:
            self.report({"ERROR"}, f'Given path: "{self.filepath}" is not relative to MOD path defined in add-on preferences ("{mod_path}")')
            return {'CANCELLED'}

        level_name = os.path.basename(self.filepath.rstrip('/').rstrip('\\'))
        print(self.filepath, level_name)

        try:
            load_level(context,
                       mod_dir=get_mod_dir(context),
                       level_name=level_name,
                       load_static_objects=self.load_static_objects,
                       load_overgrowth=self.load_overgrowth,
                       load_heightmap=self.load_heightmap,
                       load_lights=self.load_lights,
                       reporter=Reporter(self.report)
                       )
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return super().invoke(context, event)

class VIEW3D_PT_bf2_lightmapping_Panel(View3DPanel_BF2, bpy.types.Panel):
    bl_label = "Lightmapping"

    def draw(self, context):
        self.layout.operator(VIEW3D_OT_bf2_load_level.bl_idname)

# ---------------------------------------------------

def register():
    # animation
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.register_class(VIEW3D_PT_bf2_animation_Panel)

    # lightmapping
    bpy.utils.register_class(VIEW3D_OT_bf2_load_level)
    bpy.utils.register_class(VIEW3D_PT_bf2_lightmapping_Panel)

def unregister():
    # lightmapping
    bpy.utils.unregister_class(VIEW3D_PT_bf2_lightmapping_Panel)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_load_level)

    # animation
    bpy.utils.unregister_class(VIEW3D_PT_bf2_animation_Panel)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
