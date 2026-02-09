import bpy # type: ignore
import traceback
import os
from pathlib import Path

from bpy.props import BoolProperty, EnumProperty, StringProperty, IntProperty, FloatProperty, PointerProperty # type: ignore
from bpy_extras.io_utils import ImportHelper # type: ignore

from ..ops_prefs import get_mod_dirs
from ...core.tools.anim_utils import (
    toggle_mesh_mask_mesh_for_active_bone,
    setup_controllers,
    Mode,
    AnimationContext)
from ...core.utils import Reporter, next_power_of_2, prev_power_of_2
from ...core.skeleton import is_bf2_skeleton
from ...core.tools.lightmaping import (load_level,
                               ObjectBaker,
                               TerrainBaker,
                               PostProcessor,
                               get_default_heightmap_patch_count_and_size,
                               LIGHTMAPPING_CONFIG_TEMPLATE)

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

class VIEW3D_OT_bf2_lm_post_process(bpy.types.Operator):
    bl_idname = "bf2.lm_post_process"
    bl_label = "Post process"
    bl_description = "Post process baked lightmaps"

    srcdir: StringProperty (
            name="Source directory",
            subtype="DIR_PATH"
        ) # type: ignore

    outdir: StringProperty (
            name="Output directory",
            subtype="DIR_PATH"
        ) # type: ignore

    dds_compression : EnumProperty(
        name="DDS compression",
        default=1,
        items=[
            ('DXT1', "DXT1", "", 0),
            ('NONE', "NONE", "", 1)
        ]
    ) # type: ignore

    intensity: FloatProperty(
        name="Intensity",
        description="Intensity of the ambient light",
        min=0.0,
        max=1.0,
        default=0.663
    ) # type: ignore

    @classmethod
    def is_running(cls, context):
        for op in context.window.modal_operators:
            if op.bl_idname == 'BF2_OT_lm_post_process':
                return True
        return False

    def update_progress(self, context, status='Post-processing'):
        if not self.processor:
            context.scene.bf2_lm_progress_msg = 'Finished'
            context.scene.bf2_lm_progress_value = 1
            return
        total_items = self.processor.total_items()
        completed_items = self.processor.completed_items()
        if total_items == 0:
            context.scene.bf2_lm_progress_msg = f'Nothing to do'
            context.scene.bf2_lm_progress_value = 1
            return
        context.scene.bf2_lm_progress_msg = f"{status}... {completed_items}/{total_items}"
        context.scene.bf2_lm_progress_value = completed_items / total_items
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type=='ESC' and event.value=='PRESS':
            self.report({"WARNING"}, "Post-processing has been canceled!")
            return {'FINISHED'}
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}

        if not self.processor.process_next(context):
            self.processor = None
        self.update_progress(context)

        if self.processor:
            return {'RUNNING_MODAL'}
        else:
            context.window_manager.event_timer_remove(self.timer)
            self.report({"INFO"}, "Post-processing has finished!")
            return {'FINISHED'}

    def execute(self, context):
        if VIEW3D_OT_bf2_bake.is_running(context):
            self.report({"ERROR"}, f"Bake is running")
        if not os.path.isdir(self.srcdir):
            self.report({"ERROR"}, f"Choosen src path '{self.srcdir}' is NOT a directory!")
            return {'CANCELLED'}
        if not os.path.isdir(self.outdir):
            self.report({"ERROR"}, f"Choosen out path '{self.outdir}' is NOT a directory!")
            return {'CANCELLED'}
        
        self.processor = PostProcessor(context, self.srcdir, self.outdir,
                                       ambient_light_intensity=self.intensity,
                                       dds_fmt=self.dds_compression)

        wm = context.window_manager
        self.timer = wm.event_timer_add(0, window=context.window)
        wm.modal_handler_add(self)
        self.update_progress(context)
        return {'RUNNING_MODAL'}

class VIEW3D_OT_bf2_new_lm_config(bpy.types.Operator):
    bl_idname = "bf2.new_lm_config"
    bl_label = "Add lightmapping config"
    bl_description = "Add new Text data block and fills it with a lightmapping config template"

    def execute(self, context):
        text = bpy.data.texts.new('lightmap_config')
        text.name += '.py'
        text.from_string(LIGHTMAPPING_CONFIG_TEMPLATE)
        text.current_line_index = 0
        text.current_character = 0
        context.scene.bf2_lm_config_file = text

        if 'Scripting' in bpy.data.workspaces:
            if 'Scripting' in bpy.data.screens:
                screen = bpy.data.screens['Scripting']
                for area in screen.areas:
                    if area.type == 'TEXT_EDITOR':
                        with context.temp_override(area=area, screen=screen):
                            context.space_data.text = text
            context.window.workspace = bpy.data.workspaces['Scripting']

        return {'FINISHED'}

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
        name="Load Heightmap",
        description="Import primary heightmap and water plane defined in Heightdata.con",
        default=True
    ) # type: ignore

    water_light_attenuation: FloatProperty(
        name="Water light attenuation",
        description="Used for setting up the water depth material. Higher values make the water more opaque",
        default=0.3,
        min=0.0
    ) # type: ignore

    load_lights: BoolProperty(
        name="Load Lights",
        description="Import sun from Sky.con and point lights from the config file",
        default=True
    ) # type: ignore

    max_lod_to_load: IntProperty(
        name="Max LOD",
        description="Skips loading LODs with higher index, use this if you don't want lower detail LODs to receive any lightmaps",
        default=6,
        min=0,
        max=6
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'load_static_objects')
        layout.prop(self, 'load_overgrowth')
        col = layout.column()
        col.prop(self, 'max_lod_to_load')
        col.enabled = self.load_static_objects or self.load_overgrowth
        layout.prop(self, 'load_heightmap')
        col = layout.column()
        col.prop(self, 'water_light_attenuation')
        col.enabled = self.load_heightmap
        layout.prop(self, 'load_lights')

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Mod path must be defined in addon preferences")
        return get_mod_dirs(context)

    def execute(self, context):
        if not os.path.isdir(self.filepath):
            self.report({"ERROR"}, f"Choosen path '{self.filepath}' is NOT a directory!")
            return {'CANCELLED'}

        filepath = self.filepath.rstrip('/').rstrip('\\')

        mod_dirs = get_mod_dirs(context)
        for mod_path in mod_dirs:
            try:
                Path(self.filepath).relative_to(mod_path).as_posix().lower()
                break
            except ValueError:
                mod_path = ''

        if not mod_path:
            self.report({"ERROR"}, f'Given path: "{self.filepath}" is not relative to any of the MOD paths defined in add-on preferences')
            return {'CANCELLED'}

        try:
            if context.scene.bf2_lm_config_file:
                config = context.scene.bf2_lm_config_file.as_module()
            else:
                config = None

            load_level(context, filepath,
                       load_static_objects=self.load_static_objects,
                       load_overgrowth=self.load_overgrowth,
                       load_heightmap=self.load_heightmap,
                       load_lights=self.load_lights,
                       water_attenuation=self.water_light_attenuation,
                       max_lod_to_load=self.max_lod_to_load,
                       texture_paths=mod_dirs,
                       config=config,
                       reporter=Reporter(self.report))

            if terrain_cfg := get_default_heightmap_patch_count_and_size(context):
                context.scene.bf2_lm_patch_count = terrain_cfg[0]
                context.scene.bf2_lm_patch_size = terrain_cfg[1]

        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return super().invoke(context, event)

TERRAIN_MAX_SIZE = 4096
TERRAIN_MIN_SIZE = 16

def set_patch_size(self, val):
    prev_val = self.bf2_lm_patch_size
    if val > prev_val:
        val = next_power_of_2(val)
    else:
        val = prev_power_of_2(val)
    val = max(TERRAIN_MIN_SIZE, val)
    val = min(TERRAIN_MAX_SIZE, val)
    self['bf2_lm_patch_size'] = val

def get_patch_size(self):
    def_val = self.bl_rna.properties['bf2_lm_patch_size'].default
    return self.get('bf2_lm_patch_size', def_val) 

def set_patch_count(self, val):
    prev_val = self.bf2_lm_patch_count
    if val > prev_val:
        val = prev_val * 4
    else:
        val = int(prev_val / 4)
    val = max(4, val)
    val = min(64, val)
    self['bf2_lm_patch_count'] = val

def get_patch_count(self):
    def_val = self.bl_rna.properties['bf2_lm_patch_count'].default
    return self.get('bf2_lm_patch_count', def_val) 

class VIEW3D_OT_bf2_bake(bpy.types.Operator):
    bl_idname = "bf2.lightmap_bake"
    bl_label = "Bake"
    bl_description = "Bake lighting to texture"

    outdir: StringProperty (
            name="Output directory",
            subtype="DIR_PATH"
        ) # type: ignore

    dds_compression : EnumProperty(
        name="DDS compression",
        default=1,
        items=[
            ('DXT1', "DXT1", "", 0),
            ('NONE', "NONE", "", 1)
        ]
    ) # type: ignore

    bake_objects_mode : EnumProperty(
        name="Objects",
        default=0,
        items=[
            ('ALL', "All", "Bake will run for every object in the StaticObjects collection", 0),
            ('ONLY_SELECTED', "Only Selected", "Bake will run only for the selected objects", 1)
        ]
    ) # type: ignore

    normal_maps: BoolProperty(
        name="Normal Maps",
        description="When disabled, bakes lightmaps without normal maps on materials. Usually results in less noisy lightmaps",
        default=False
    ) # type: ignore

    bake_objects: BoolProperty(
        name="Objects",
        description="Bake lightmaps for static objects",
        default=True
    ) # type: ignore

    bake_terrain: BoolProperty(
        name="Terrain",
        description="Bake lightmaps for terrain",
        default=True
    ) # type: ignore

    patch_count: IntProperty(
        name="Patch count",
        description="Number of terrain patches, must be a power of four",
        default=64,
        min=4,
        max=64
    ) # type: ignore

    patch_size: IntProperty(
        name="Patch size",
        description="Texture size of a single terrain patch",
        default=1024
    ) # type: ignore

    resume: BoolProperty(
        name="Resume",
        description="Resume previously canceled bake by skipping Objects which has been lightmapped already",
        default=False
    ) # type: ignore

    @classmethod
    def is_running(cls, context):
        for op in context.window.modal_operators:
            if op.bl_idname == 'BF2_OT_lightmap_bake':
                return True
        return False

    def active_baker(self):
        if not self.bakers:
            return None
        else:
            return self.bakers[0]

    def update_progress(self, context, status='Baking'):
        baker = self.active_baker()
        if not baker:
            context.scene.bf2_lm_progress_msg = 'Finished'
            context.scene.bf2_lm_progress_value = 1
            return
        total_items = baker.total_items()
        completed_items = baker.completed_items()
        if total_items == 0:
            context.scene.bf2_lm_progress_msg = f'Nothing to do'
            context.scene.bf2_lm_progress_value = 1
            return
        context.scene.bf2_lm_progress_msg = f"{status} {baker.type()}... {completed_items}/{total_items}"
        context.scene.bf2_lm_progress_value = completed_items / total_items
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type=='ESC' and event.value=='PRESS':
            baker = self.active_baker()
            if baker:
                self.update_progress(context, status='Canceled')
                baker.cleanup(context)
            self.report({"WARNING"}, "Baking has been canceled!")
            return {'FINISHED'}
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}

        baker = self.active_baker()
        if not baker.bake_next(context):
            self.bakers.remove(baker)
        self.update_progress(context)

        baker = self.active_baker()
        if baker:
            return {'RUNNING_MODAL'}
        else:
            context.window_manager.event_timer_remove(self.timer)
            self.report({"INFO"}, "Baking has finished!")
            return {'FINISHED'}

    def execute(self, context):
        if self.is_running(context):
            return {'CANCELLED'}
        if VIEW3D_OT_bf2_lm_post_process.is_running(context):
            self.report({"ERROR"}, f"Post-processor is running")
            return {'CANCELLED'}
        if not os.path.isdir(self.outdir):
            self.report({"ERROR"}, f"Choosen out path '{self.outdir}' is NOT a directory!")
            return {'CANCELLED'}

        self.bakers = list()
        if self.bake_objects:
            baker = ObjectBaker(context, self.outdir,
                                dds_fmt=self.dds_compression,
                                only_selected=self.bake_objects_mode == 'ONLY_SELECTED',
                                normal_maps=self.normal_maps,
                                skip_existing=self.resume,
                                reporter=Reporter(self.report))
            self.bakers.append(baker)
        if self.bake_terrain:
            baker = TerrainBaker(context, self.outdir,
                                 dds_fmt=self.dds_compression,
                                 patch_count=self.patch_count,
                                 patch_size=self.patch_size,
                                 skip_existing=self.resume,
                                 reporter=Reporter(self.report))
            self.bakers.append(baker)

        # need this to generate dummy events for modal opeartor if user does nothing
        wm = context.window_manager
        self.timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)

        self.update_progress(context)
        return {'RUNNING_MODAL'}

class VIEW3D_PT_bf2_lightmapping_Panel(View3DPanel_BF2, bpy.types.Panel):
    bl_label = "Lightmapping"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        scene = context.scene

        row = layout.row()
        row.prop(scene, "bf2_lm_config_file", text="Config")
        row.operator(VIEW3D_OT_bf2_new_lm_config.bl_idname, text='', icon='ADD')

        layout.operator(VIEW3D_OT_bf2_load_level.bl_idname, icon='IMPORT')

        main = layout.column(heading="Bake")
        header, body = main.panel("BF2_PT_bake_settings", default_closed=True)
        header.label(text="Bake Settings")
        if body:
            body.prop(scene, "bf2_lm_outdir")
            body.prop(scene, "bf2_lm_dds_compression")
            body.separator(factor=1.0, type='LINE')
            body.prop(scene, "bf2_lm_bake_objects")
            col = body.column()
            col.prop(scene, "bf2_lm_bake_objects_mode", text=" ")
            col.prop(scene, "bf2_lm_normal_maps")
            col.enabled = scene.bf2_lm_bake_objects
            body.separator(factor=1.0, type='LINE')
            body.prop(scene, "bf2_lm_bake_terrain")
            col = body.column()
            col.prop(scene, "bf2_lm_patch_count")
            col.prop(scene, "bf2_lm_patch_size")
            col.enabled = scene.bf2_lm_bake_terrain
            body.separator(factor=1.0, type='LINE')
            body.prop(scene, "bf2_lm_resume")
            props = main.operator(VIEW3D_OT_bf2_bake.bl_idname, icon='RENDER_STILL')
            props.outdir = scene.bf2_lm_outdir
            props.dds_compression = scene.bf2_lm_dds_compression
            props.bake_objects = scene.bf2_lm_bake_objects
            props.bake_objects_mode = scene.bf2_lm_bake_objects_mode
            props.bake_terrain = scene.bf2_lm_bake_terrain
            props.patch_count = scene.bf2_lm_patch_count
            props.patch_size = scene.bf2_lm_patch_size
            props.normal_maps = scene.bf2_lm_normal_maps
            props.resume = scene.bf2_lm_resume

            if VIEW3D_OT_bf2_bake.is_running(context):
                row = layout.row()
                row.progress(
                    factor=context.scene.bf2_lm_progress_value,
                    type="BAR",
                    text=context.scene.bf2_lm_progress_msg 
                )
                row.scale_x = 2
                row = layout.row()
                row.label(text='Press ESC to cancel', icon='CANCEL')

        header, body = layout.panel("BF2_PT_post_process", default_closed=True)
        header.label(text="Post-process")
        if body:
            body.prop(scene, "bf2_lm_post_process_outdir", text='Output directory')
            body.prop(scene, "bf2_lm_ambient_light_level")
            props = body.operator(VIEW3D_OT_bf2_lm_post_process.bl_idname, icon='OUTPUT')
            props.srcdir = scene.bf2_lm_outdir
            props.outdir = scene.bf2_lm_post_process_outdir
            props.dds_compression = scene.bf2_lm_dds_compression
            props.intensity = scene.bf2_lm_ambient_light_level

            if VIEW3D_OT_bf2_lm_post_process.is_running(context):
                row = layout.row()
                row.progress(
                    factor=context.scene.bf2_lm_progress_value,
                    type="BAR",
                    text=context.scene.bf2_lm_progress_msg 
                )
                row.scale_x = 2
                row = layout.row()
                row.label(text='Press ESC to cancel', icon='CANCEL')

# ---------------------------------------------------

def register():
    # animation
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.register_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.register_class(VIEW3D_PT_bf2_animation_Panel)

    # lightmapping
    bpy.utils.register_class(VIEW3D_OT_bf2_lm_post_process)
    bpy.utils.register_class(VIEW3D_OT_bf2_new_lm_config)
    bpy.utils.register_class(VIEW3D_OT_bf2_load_level)
    bpy.utils.register_class(VIEW3D_OT_bf2_bake)

    bpy.types.Scene.bf2_lm_bake_objects = BoolProperty(
        name="Objects",
        description="Bake lightmaps for static objects",
        default=True,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_bake_terrain = BoolProperty(
        name="Terrain",
        description="Bake lightmaps for terrain",
        default=True,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_bake_objects_mode = EnumProperty(
        name="Objects",
        default=0,
        items=[
            ('ALL', "All", "Bake will run for every object in the StaticObjects collection", 0),
            ('ONLY_SELECTED', "Only Selected", "Bake will run only for the selected objects", 1)
        ],
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_dds_compression = EnumProperty(
        name="DDS compression",
        default=1,
        items=[
            ('DXT1', "DXT1", "", 0),
            ('NONE', "NONE", "", 1)
        ],
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_outdir = StringProperty (
            name="Output directory",
            subtype="DIR_PATH"
        ) # type: ignore

    bpy.types.Scene.bf2_lm_post_process_outdir = StringProperty (
            name="Output directory for lightmap post-processing",
            subtype="DIR_PATH"
        ) # type: ignore

    bpy.types.Scene.bf2_lm_patch_count = IntProperty(
        name="Patch count",
        description="Number of terrain patches, must be a power of four",
        default=64,
        get=get_patch_count,
        set=set_patch_count,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_patch_size = IntProperty(
        name="Patch size",
        description="Texture size of a single terrain patch",
        default=1024,
        get=get_patch_size,
        set=set_patch_size,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_config_file = PointerProperty(
        type=bpy.types.Text,
        name="Lightmapping configuration file",
        description="Pointer to text file containing optional actions to perform when loading the level, e.g. what objects to skip, where to place point lights etc"
    ) # type: ignore

    bpy.types.Scene.bf2_lm_progress_value = FloatProperty()
    bpy.types.Scene.bf2_lm_progress_msg = StringProperty()

    bpy.types.Scene.bf2_lm_ambient_light_level = FloatProperty(
        name="Ambient light intensity",
        min=0.0,
        max=1.0,
        default=0.663,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_normal_maps = BoolProperty(
        name="Normal Maps",
        description="When disabled, bakes lightmaps without normal maps on materials. Usually results in less noisy lightmaps",
        default=False,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.types.Scene.bf2_lm_resume = BoolProperty(
        name="Resume",
        description="Resume previously canceled bake by skipping Objects which has been lightmapped already",
        default=False,
        options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    bpy.utils.register_class(VIEW3D_PT_bf2_lightmapping_Panel)

def unregister():
    # lightmapping
    bpy.utils.unregister_class(VIEW3D_PT_bf2_lightmapping_Panel)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_bake)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_load_level)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_new_lm_config)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_lm_post_process)

    del bpy.types.Scene.bf2_lm_resume
    del bpy.types.Scene.bf2_lm_normal_maps
    del bpy.types.Scene.bf2_lm_ambient_light_level
    del bpy.types.Scene.bf2_lm_progress_value
    del bpy.types.Scene.bf2_lm_progress_msg
    del bpy.types.Scene.bf2_lm_config_file
    del bpy.types.Scene.bf2_lm_patch_count
    del bpy.types.Scene.bf2_lm_patch_size
    del bpy.types.Scene.bf2_lm_post_process_outdir
    del bpy.types.Scene.bf2_lm_outdir
    del bpy.types.Scene.bf2_lm_dds_compression
    del bpy.types.Scene.bf2_lm_bake_objects_mode
    del bpy.types.Scene.bf2_lm_bake_terrain
    del bpy.types.Scene.bf2_lm_bake_objects

    # animation
    bpy.utils.unregister_class(VIEW3D_PT_bf2_animation_Panel)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    bpy.utils.unregister_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
