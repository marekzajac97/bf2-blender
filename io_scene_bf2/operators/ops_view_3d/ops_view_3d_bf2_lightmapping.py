import bpy # type: ignore
import traceback
import os
from pathlib import Path

from bpy.props import BoolProperty, EnumProperty, StringProperty, IntProperty, FloatProperty, PointerProperty # type: ignore
from bpy_extras.io_utils import ImportHelper # type: ignore

from ..utils import RegisterFactory
from ..ops_prefs import get_mod_dirs
from ...core.utils import Reporter, set_power_of_two_int, get_power_of_two_int
from ...core.tools.lightmapping.scene import load_level, LIGHTMAPPING_CONFIG_TEMPLATE
from ...core.tools.lightmapping.baking import (
                               ObjectParallelBaker,
                               ObjectBaker,
                               TerrainBaker,
                               PostProcessor,
                               get_default_heightmap_patch_count_and_size,
                               check_gpu)
from ...core.tools.lightmapping.packing import pack_lightmaps

def objects_subdir(directory, mkdir=True):
    sdir = os.path.join(directory, 'objects')
    if mkdir:
        os.makedirs(sdir, exist_ok=True)
    return sdir

class VIEW3D_OT_bf2_lm_post_process(bpy.types.Operator):
    bl_idname = "bf2.lm_post_process"
    bl_label = "Post process"
    bl_description = "Run only the post-processing pass on the baked lightmaps"

    @classmethod
    def is_running(cls, context):
        for op in context.window.modal_operators:
            if op is None:
                continue
            if op.bl_idname == 'BF2_OT_lm_post_process':
                return True
        return False

    def update_progress(self, context, status='Post-processing'):
        context.area.tag_redraw()
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

    def cancel_timer(self, context):
        context.window_manager.event_timer_remove(self.timer)

    def setup_timer(self, context):
        self.timer = context.window_manager.event_timer_add(0, window=context.window)

    def modal(self, context, event):
        if event.type=='ESC' and event.value=='PRESS':
            self.report({"WARNING"}, "Post-processing has been canceled!")
            self.cancel_timer(context)
            return {'FINISHED'}
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}
        
        self.cancel_timer(context)

        if not self.processor.process_next(context):
            self.processor = None
        self.update_progress(context)

        if self.processor:
            self.setup_timer(context)
            return {'RUNNING_MODAL'}
        else:
            context.window_manager.event_timer_remove(self.timer)
            self.report({"INFO"}, "Post-processing has finished!")
            return {'FINISHED'}

    def execute(self, context):
        if VIEW3D_OT_bf2_bake.is_running(context):
            self.report({"ERROR"}, f"Bake is running")
        srcdir = context.scene.bf2_lm_outdir
        outdir = context.scene.bf2_lm_post_process_outdir or context.scene.bf2_lm_outdir
        if not os.path.isdir(srcdir):
            self.report({"ERROR"}, f"Chosen src path '{srcdir}' is NOT a directory!")
            return {'CANCELLED'}
        if not os.path.isdir(outdir):
            self.report({"ERROR"}, f"Chosen out path '{outdir}' is NOT a directory!")
            return {'CANCELLED'}

        self.processor = PostProcessor([srcdir, objects_subdir(srcdir, mkdir=False)], outdir,
                                       ambient_light_intensity=context.scene.bf2_lm_ambient_light_level,
                                       dds_fmt=context.scene.bf2_lm_dds_compression)

        self.update_progress(context)
        self.setup_timer(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class VIEW3D_OT_bf2_lm_pack_lightmaps(bpy.types.Operator):
    bl_idname = "bf2.lm_pack_lightmaps"
    bl_label = "Pack Lightmaps"
    bl_description = "Pack individual lightmap DDS files into texture atlases and generate LightmapAtlas.tai"

    def execute(self, context):
        if context.scene.bf2_lm_post_process_outdir:
            indir = objects_subdir(context.scene.bf2_lm_post_process_outdir, mkdir=False)
        else:
            self.report({"INFO"}, f"Post-process output directory is undefined, using bake output directory as input")
            indir = objects_subdir(context.scene.bf2_lm_outdir, mkdir=False)

        outdir = context.scene.bf2_lm_pack_outdir or context.scene.bf2_lm_outdir
        if not os.path.isdir(indir):
            self.report({"ERROR"}, f"Input directory '{indir}' is NOT a directory!")
            return {'CANCELLED'}
        if not os.path.isdir(outdir):
            self.report({"ERROR"}, f"Output directory '{outdir}' is NOT a directory!")
            return {'CANCELLED'}

        atlas_size = context.scene.bf2_lm_pack_atlas_size
        pack_lightmaps(indir, outdir,
                       context.scene.bf2_lm_level_path,
                       context.scene.bf2_lm_dds_compression,
                       (atlas_size, atlas_size))
        self.report({"INFO"}, "Lightmap packing finished")
        return {'FINISHED'}

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

    lm_skip_lod0_only: BoolProperty(
        name="Simplify hierarchies",
        description="Import only LOD0 for non-lightmapable map objects (Overgrowth, BundledMeshes etc.) to reduce the overall object count in the scene and improve import speed",
        default=True
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'load_static_objects')
        layout.prop(self, 'load_overgrowth')
        col = layout.column()
        col.prop(self, 'max_lod_to_load')
        col.prop(self, 'lm_skip_lod0_only')
        col.enabled = self.load_static_objects or self.load_overgrowth
        layout.prop(self, 'load_heightmap')
        col = layout.column()
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

        level_path = None # relative path!
        mod_dirs = get_mod_dirs(context)
        test_path = Path(self.filepath)
        for mod_path in mod_dirs:
            try:
                level_path = test_path.relative_to(mod_path).as_posix().lower()
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
                       max_lod_to_load=self.max_lod_to_load,
                       lm_skip_lod0_only=self.lm_skip_lod0_only,
                       mod_dirs=mod_dirs,
                       config=config,
                       reporter=Reporter(self.report))

            if terrain_cfg := get_default_heightmap_patch_count_and_size(context):
                context.scene.bf2_lm_patch_count = terrain_cfg[0]
                context.scene.bf2_lm_patch_size = terrain_cfg[1]

            context.scene.bf2_lm_level_path = level_path

        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return super().invoke(context, event)


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

    non_blocking: BoolProperty(
        name="Non-Blocking",
        description="Bake asynchronously without freezing the UI",
        default=False,
        options={'HIDDEN'}
    ) # type: ignore

    @classmethod
    def is_running(cls, context):
        for op in context.window.modal_operators:
            if op is None:
                continue
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
        context.area.tag_redraw()
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

    def cancel_timer(self, context):
        context.window_manager.event_timer_remove(self.timer)

    def setup_timer(self, context):
        self.timer = context.window_manager.event_timer_add(0, window=self._window)

    def _bake_next(self, context):
        while True:
            baker = self.active_baker()
            if not baker:
                return False # done
            if not baker.prepare_next(context):
                self.bakers.remove(baker)
                continue
            try:
                bpy.ops.object.bake('INVOKE_DEFAULT', **baker.get_bake_params())
                return True
            except Exception:
                self.report({"ERROR"}, traceback.format_exc())
                return False

    def _complete_bake(self, canceled):
        context = bpy.context
        self.setup_timer(context) # trigger next modal() call

        baker = self.active_baker()
        if not baker:
            self.report({"ERROR"}, "No active baker")
            self._baking_abort = True
            return

        try:
            baker.complete_bake(context, canceled)
        except Exception:
            self.report({"ERROR"}, traceback.format_exc())
            self._baking_abort = True
            return

        if canceled:
            self._unregister_handlers()
            self._baking_cancel = True

    def _on_bake_complete_handler(self, *args):
        self._complete_bake(False)

    def _on_bake_cancel_handler(self, *args):
        self._complete_bake(True)

    def _register_handlers(self):
        bpy.app.handlers.object_bake_complete.append(self._on_bake_complete_handler)
        bpy.app.handlers.object_bake_cancel.append(self._on_bake_cancel_handler)

    def _unregister_handlers(self):
        try:
            bpy.app.handlers.object_bake_complete.remove(self._on_bake_complete_handler)
        except ValueError:
            pass
        try:
            bpy.app.handlers.object_bake_cancel.remove(self._on_bake_cancel_handler)
        except ValueError:
            pass

    def _on_bake_canceled(self, context):
        baker = self.active_baker()
        if baker:
            self.update_progress(context, status='Canceled')
            baker.cleanup(context)
        self.report({"WARNING"}, "Baking has been canceled!")

    def modal(self, context, event):
        if event.type=='ESC' and event.value=='PRESS':
            if self.non_blocking:
                return {'PASS_THROUGH'}
            self._baking_cancel = True
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}

        self.cancel_timer(context)
        if self._baking_cancel:
            self._on_bake_canceled(context)
            return {'FINISHED'}

        if self.non_blocking:
            stop = False
            if self._baking_abort:
                stop = True
            elif not self._bake_next(context):
                self.report({"INFO"}, "Baking has finished!")
                stop = True

            self.update_progress(context)

            if stop:
                self._unregister_handlers()
                return {'FINISHED'}
            else:
                return {'RUNNING_MODAL'}
        else:
            baker = self.active_baker()
            if not baker.bake_next(context):
                self.bakers.remove(baker)
            self.update_progress(context)

            baker = self.active_baker()
            if baker:
                self.setup_timer(context)
                return {'RUNNING_MODAL'}
            else:
                self.report({"INFO"}, "Baking has finished!")
                return {'FINISHED'}

    def execute(self, context):
        if self.is_running(context):
            return {'CANCELLED'}
        if VIEW3D_OT_bf2_lm_post_process.is_running(context):
            self.report({"ERROR"}, f"Post-processor is running")
            return {'CANCELLED'}
        if not os.path.isdir(context.scene.bf2_lm_outdir):
            self.report({"ERROR"}, f"Chosen out path '{context.scene.bf2_lm_outdir}' is NOT a directory!")
            return {'CANCELLED'}

        obj_kwargs = dict(
            dds_fmt=context.scene.bf2_lm_dds_compression,
            only_selected=context.scene.bf2_lm_bake_objects_mode == 'ONLY_SELECTED',
            normal_maps=context.scene.bf2_lm_normal_maps,
            skip_existing=context.scene.bf2_lm_resume,
            max_lod=context.scene.bf2_lm_max_lod,
            reporter=Reporter(self.report)
        )

        self.bakers = list()
        if context.scene.bf2_lm_bake_objects:
            if context.scene.bf2_lm_batch_mode:
                obj_kwargs['atlas_size'] = (context.scene.bf2_lm_atlas_dim, context.scene.bf2_lm_atlas_dim)
                obj_baker_cls = ObjectParallelBaker
            else:
                obj_baker_cls = ObjectBaker

            baker = obj_baker_cls(context, objects_subdir(context.scene.bf2_lm_outdir), **obj_kwargs)
            self.bakers.append(baker)
            if context.scene.bf2_lm_post_process:
                baker.post_process_enable(context.scene.bf2_lm_ambient_light_level,
                                          objects_subdir(context.scene.bf2_lm_post_process_outdir))
        if context.scene.bf2_lm_bake_terrain:
            baker = TerrainBaker(context, context.scene.bf2_lm_outdir,
                                 dds_fmt=context.scene.bf2_lm_dds_compression,
                                 patch_count=context.scene.bf2_lm_patch_count,
                                 patch_size=context.scene.bf2_lm_patch_size,
                                 skip_existing=context.scene.bf2_lm_resume,
                                 water_attenuation=context.scene.bf2_lm_water_attenuation,
                                 reporter=Reporter(self.report))
            self.bakers.append(baker)
            if context.scene.bf2_lm_post_process:
                baker.post_process_enable(context.scene.bf2_lm_ambient_light_level,
                                          context.scene.bf2_lm_post_process_outdir)

        if not self.bakers:
            self.report({"INFO"}, f"Nothing to bake")
            return {'CANCELLED'}

        self._baking_abort = False
        self._baking_cancel = False
        self._window = context.window

        self.update_progress(context)
        self.setup_timer(context)
        context.window_manager.modal_handler_add(self)

        if self.non_blocking:
            self._register_handlers()

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.non_blocking = True
        return self.execute(context)

class VIEW3D_PT_bf2_lightmapping_Panel(bpy.types.Panel):
    bl_category = "BF2"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Lightmapping"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        scene = context.scene

        row = layout.row()
        row.prop(scene, "bf2_lm_config_file", text="Config")
        row.operator(VIEW3D_OT_bf2_new_lm_config.bl_idname, text='', icon='ADD')

        layout.operator(VIEW3D_OT_bf2_load_level.bl_idname, icon='IMPORT')

        main = layout.column()
        header, body = main.panel("BF2_PT_bake_settings", default_closed=True)
        header.label(text="Bake Settings")
        if body:
            body.prop(scene, "bf2_lm_outdir")
            body.prop(scene, "bf2_lm_dds_compression")
            body.separator(factor=1.0, type='LINE')

            body.prop(scene, "bf2_lm_bake_objects", text='Bake Objects')
            col = body.column()
            col.prop(scene, "bf2_lm_bake_objects_mode", text=" ")
            col.prop(scene, "bf2_lm_normal_maps")
            col.prop(scene, "bf2_lm_batch_mode")
            row = col.row()
            row.prop(scene, "bf2_lm_atlas_dim")
            row.active = scene.bf2_lm_batch_mode
            col.prop(scene, "bf2_lm_max_lod")
            col.active = scene.bf2_lm_bake_objects
            body.separator(factor=1.0, type='LINE')

            body.prop(scene, "bf2_lm_bake_terrain", text='Bake Terrain')
            col = body.column()
            col.prop(scene, "bf2_lm_patch_count")
            col.prop(scene, "bf2_lm_patch_size")
            col.prop(scene, "bf2_lm_water_attenuation")
            col.active = scene.bf2_lm_bake_terrain
            body.separator(factor=1.0, type='LINE')
            body.prop(scene, "bf2_lm_post_process")
            col = body.column()
            col.prop(scene, "bf2_lm_post_process_outdir")
            col.prop(scene, "bf2_lm_ambient_light_level")
            col.active = scene.bf2_lm_post_process

            body.separator(factor=1.0, type='LINE')
            body.prop(scene, "bf2_lm_resume")

            row = main.row()
            row.operator(VIEW3D_OT_bf2_bake.bl_idname, icon='RENDER_STILL')
            row.enabled = scene.bf2_lm_bake_objects or scene.bf2_lm_bake_terrain

            if scene.bf2_lm_post_process:
                if not scene.bf2_lm_post_process_outdir:
                    col = body.column()
                    row = col.row()
                    row.label(text="Post-process output directory not set,", icon='ERROR')
                    row = col.row()
                    row.label(text="raw bake results will get overwritten!", icon='BLANK1')

            for warn in check_gpu(context):
                row = body.row()
                row.label(text=warn, icon='ERROR')

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

            row = main.row()
            row.operator(VIEW3D_OT_bf2_lm_post_process.bl_idname, icon='OUTPUT')

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
            row.enabled = scene.bf2_lm_post_process

        header, body = main.panel("BF2_PT_pack_lightmaps", default_closed=True)
        header.label(text="Lightmap packing")
        if body:
            body.prop(scene, "bf2_lm_pack_outdir")
            body.prop(scene, "bf2_lm_pack_atlas_size")
            row = main.row()
            row.operator(VIEW3D_OT_bf2_lm_pack_lightmaps.bl_idname, icon='PACKAGE')
            row.enabled = scene.bf2_lm_outdir != ''

# ---------------------------------------------------

def init(rc : RegisterFactory):
    rc.reg_class(VIEW3D_OT_bf2_lm_post_process)
    rc.reg_class(VIEW3D_OT_bf2_lm_pack_lightmaps)
    rc.reg_class(VIEW3D_OT_bf2_new_lm_config)
    rc.reg_class(VIEW3D_OT_bf2_load_level)
    rc.reg_class(VIEW3D_OT_bf2_bake)

    from bpy.types import Scene # type: ignore

    rc.reg_prop(Scene, 'bf2_lm_bake_objects',
        BoolProperty(
            name="Bake Objects",
            description="Bake lightmaps for static objects",
            default=True,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_bake_terrain',
        BoolProperty(
            name="Bake Terrain",
            description="Bake lightmaps for terrain",
            default=True,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_bake_objects_mode',
        EnumProperty(
            name="Objects",
            default=0,
            items=[
                ('ALL', "All", "Bake will run for every object in the StaticObjects collection", 0),
                ('ONLY_SELECTED', "Only Selected", "Bake will run only for the selected objects", 1)
            ],
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_dds_compression',
        EnumProperty(
            name="DDS compression",
            default=1,
            items=[
                ('DXT1', "DXT1", "", 0),
                ('NONE', "NONE", "", 1)
            ],
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_outdir',
        StringProperty (
            name="Output directory",
            subtype="DIR_PATH"
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_post_process_outdir',
        StringProperty (
            name="Output directory",
            description="Output directory for lightmap post-processing. If not set, bake results will be overwritten",
            subtype="DIR_PATH"
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_patch_count',
        IntProperty(
            name="Patch count",
            description="Number of terrain patches, must be a power of four",
            default=64,
            get=get_patch_count,
            set=set_patch_count,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_patch_size',
        IntProperty(
            name="Patch size",
            description="Texture size of a single terrain patch",
            default=1024,
            min=16,
            max=4096,
            get=get_power_of_two_int('bf2_lm_patch_size'),
            set=set_power_of_two_int('bf2_lm_patch_size'),
            subtype='PIXEL',
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_config_file',
        PointerProperty(
            type=bpy.types.Text,
            name="Lightmapping configuration file",
            description="Pointer to text file containing optional actions to perform when loading the level, e.g. what objects to skip, where to place point lights etc"
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_progress_value',
        FloatProperty()
    )

    rc.reg_prop(Scene, 'bf2_lm_progress_msg',
        StringProperty()
    )

    rc.reg_prop(Scene, 'bf2_lm_ambient_light_level',
        FloatProperty(
            name="Ambient light intensity",
            min=0.0,
            max=1.0,
            default=0.663,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_normal_maps',
        BoolProperty(
            name="Use Normal Maps",
            description="Bakes lightmaps with normal map details/shadows. Disabling this usually results in less noisy lightmaps",
            default=False,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_max_lod',
        IntProperty(
            name="Max LOD",
            description="Skips baking lightmaps for lower detail LODs",
            default=6,
            min=0,
            max=6,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_water_attenuation',
        FloatProperty(
            name="Water attenuation",
            description="Water light attenuation coefficient. Higher values make the water more opaque with increasing depth",
            default=0.15,
            min=0.0,
            max=1.0,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_resume',
        BoolProperty(
            name="Resume",
            description="Resume previously canceled bake by skipping lightmaps which have already been created",
            default=False,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_post_process',
        BoolProperty(
            name="Post-process",
            description="Run post-processing pass after each bake",
            default=False,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_atlas_dim',
        IntProperty(
            name="Atlas size",
            description="Atlas dimensions (width and height) to use for baking a single batch. A bigger atlas will use more GPU memory but can fit more objects in a single batch.",
            default=2192,
            min=512,
            max=8192,
            subtype='PIXEL',
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_batch_mode',
        BoolProperty(
            name="Use Atlas",
            description="Bake objects in batches on a texture atlas. This should better utilize GPU when baking a lot of small objects thus cutting down the rendering time (use only if you have a capable hardware)\n\n"
                        "NOTE: The margin (from the Bake settings) will be used to prevent bleeding from one object to another, keep this in mind when choosing the atlas size",
            default=False,
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_pack_outdir',
        StringProperty (
            name="Pack output directory",
            description="Output directory for packed atlases. If not set, the bake output directory will be used",
            subtype="DIR_PATH"
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_pack_atlas_size',
        IntProperty(
            name="Atlas size",
            description="Width and height of each output atlas",
            default=2048,
            min=512,
            max=4096,
            get=get_power_of_two_int('bf2_lm_pack_atlas_size'),
            set=set_power_of_two_int('bf2_lm_pack_atlas_size'),
            subtype='PIXEL',
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore
    )

    rc.reg_prop(Scene, 'bf2_lm_level_path',
        StringProperty ()
    )

    rc.reg_class(VIEW3D_PT_bf2_lightmapping_Panel)

register, unregister = RegisterFactory.create(init)
