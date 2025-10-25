import bpy # type: ignore
import traceback
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, IntVectorProperty, FloatProperty, CollectionProperty # type: ignore
from bpy_extras.io_utils import poll_file_object_drop # type: ignore

from .ops_common import ImporterBase, ExporterBase
from ...core.object_template import (import_object_template, export_object_template,
                                     parse_geom_type, NATIVE_BSP_EXPORT)
from ...core.mesh import collect_uv_layers
from ...core.skeleton import find_all_skeletons
from ...core.utils import Reporter, find_root, next_power_of_2, prev_power_of_2

from ... import get_mod_dir

class SkeletonsToLinkCollection(bpy.types.PropertyGroup):

    def get_skeletons(self, context):
        items = []
        for i, rig in enumerate(find_all_skeletons()):
            items.append((rig.name, rig.name, "", i))
        return items

    geom_idx: IntProperty(
        name="Geom Index",
        description="Index of Geometry from the mesh being imported",
        default=0,
        min=0,
        max=99
    ) # type: ignore

    skeleton : EnumProperty(
        name="Skeleton",
        description="Name of armature object to apply geom data to",
        items=get_skeletons
    ) # type: ignore

class IMPORT_OT_bf2_object(bpy.types.Operator, ImporterBase):
    bl_idname = "bf2.con_import"
    bl_description = 'Battlefield 2 ObjectTemplate'
    bl_label = "Import ObjectTemplate"
    filter_glob: StringProperty(default="*.con", options={'HIDDEN'}) # type: ignore

    import_collmesh: BoolProperty(
        name="Import CollisionMesh",
        description="Load CollisionMesh and merge with the object hierarchy",
        default=True
    ) # type: ignore

    import_rig_mode : EnumProperty(
        name="Import Rigs",
        description="Load skin weights and bone transforms from SkinnedMeshes and apply them to mesh and armature",
        default=0,
        items=[
            ('AUTO', "Auto", "Guess which Geom should be assigned to which skeleton (armature) based on imported ObjectTemplate type", 0),
            ('MANUAL', "Manual", "Manually define the mapping of each geom to a skeleton (armature)", 1),
            ('OFF', "Off", "Skip rig import", 2),
        ]
    ) # type: ignore

    merge_materials: BoolProperty(
        name="Merge Materials",
        description="Merge repeating BF2 materials into one Blender material (NOTE: might be force disabled on SkinnedMeshes when bone limit per material is reached)",
        default=True
    ) # type: ignore

    weld_verts: BoolProperty(
        name="Weld Vertices",
        description="Welds vertices based on their proximity. Export process splits some of the vertices as their per-face attribute values (normals, tangents, UVs etc) differ",
        default=False
    ) # type: ignore

    load_backfaces: BoolProperty(
        name="Backfaces",
        description="Adds 'backface' attribute to double-sided faces. Disabling this will ignore any duplicated faces",
        default=True
    ) # type: ignore

    skeletons_to_link : CollectionProperty(type=SkeletonsToLinkCollection) # type: ignore

    instance=None

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "import_collmesh")
        row = layout.row()
        row.label(text="Import Rigs:")
        row.prop(self, "import_rig_mode", text='')

        col = layout.column()
        if self.import_rig_mode == 'MANUAL':
            for prop in self.skeletons_to_link:
                row = col.row()
                row.prop(prop, "geom_idx", text='Geom:')
                row.prop(prop, "skeleton", text='')

            col = layout.column()
            row = col.row()
            row.operator(IMPORT_OT_bf2_object_skeleton_add.bl_idname, text='', icon='ADD')
            row.operator(IMPORT_OT_bf2_object_skeleton_remove.bl_idname, text='', icon='REMOVE')

        col = layout.column()
        col.prop(self, "merge_materials")

        col = layout.column()
        col.prop(self, "weld_verts")

        col = layout.column()
        col.prop(self, "load_backfaces")

    def _execute(self, context):
        mod_path = get_mod_dir(context)

        geom_to_ske = None
        if self.import_rig_mode == 'MANUAL':
            geom_to_ske = dict()
            for prop in self.skeletons_to_link:
                geom_to_ske[prop.geom_idx] = prop.skeleton

        context.view_layer.objects.active = \
            import_object_template(context, self.filepath,
                import_collmesh=self.import_collmesh,
                import_rig_mode=self.import_rig_mode,
                geom_to_ske_name=geom_to_ske,
                texture_path=mod_path,
                merge_materials=self.merge_materials,
                weld_verts=self.weld_verts,
                load_backfaces=self.load_backfaces,
                reporter=Reporter(self.report))

    def invoke(self, context, _event):
        IMPORT_OT_bf2_object.instance=self
        return super().invoke(context, _event)

class IMPORT_OT_bf2_object_skeleton_add(bpy.types.Operator):
    bl_idname = "bf2.con_skeleton_add"
    bl_label = "Add armature mapping"

    def execute(self, context):
        last_item = None
        if len(self.skeletons_to_link):
            last_item = self.skeletons_to_link[-1]
        item = self.skeletons_to_link.add()

        if last_item is None:
            item.geom_idx = 0
        else:
            item.geom_idx = last_item.geom_idx + 1
            item.skeleton = last_item.skeleton
        context.window.cursor_warp(self.mouse_x, self.mouse_y - 22)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.skeletons_to_link = IMPORT_OT_bf2_object.instance.skeletons_to_link
        return self.execute(context)


class IMPORT_OT_bf2_object_skeleton_remove(bpy.types.Operator):
    bl_idname = "bf2.con_skeleton_remove"
    bl_label = "Remove armature mapping"

    def execute(self, context):
        last_item_idx = len(list(self.skeletons_to_link)) - 1
        self.skeletons_to_link.remove(last_item_idx)
        context.window.cursor_warp(self.mouse_x, self.mouse_y + 22)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.skeletons_to_link = IMPORT_OT_bf2_object.instance.skeletons_to_link
        return self.execute(context)


SAMPLES_MAX_SIZE = 4096
SAMPLES_MIN_SIZE = 8

class EXPORT_OT_bf2_object(bpy.types.Operator, ExporterBase):
    bl_idname = "bf2.con_export"
    bl_label = "Export ObjectTemplate"
    filename_ext = ".con"
    filter_glob: StringProperty(default="*.con", options={'HIDDEN'}) # type: ignore
    FILE_DESC = "ObjectTemplate (.con)"

    def get_uv_layers(self, context):
        items = []
        root = find_root(context.view_layer.objects.active)
        object_uv_layers = collect_uv_layers(root)
        default = None

        geom_type, _ = parse_geom_type(root)
        if geom_type == 'StaticMesh':
            default = 1 # Detail normal
        elif geom_type == 'BundledMesh' or geom_type == 'SkinnedMesh':
            default = 0 # Diffuse/Normal

        # XXX: it is not possible to define a default for dynamic enums
        # the only way is to reorder items in such a way that the default one
        # is the first one in the list, not ideal but works
        start = 0
        if default in object_uv_layers:
            uv_layer = object_uv_layers.pop(default)
            items.append((uv_layer, uv_layer, "", 0))
            start = 1

        for i, uv_layer in enumerate(object_uv_layers.values(), start=start):
            items.append((uv_layer, uv_layer, "", i))

        return items

    def set_sample_size(self, value):
        prev_val = tuple(self.samples_size)
        val = list(value)
        for i in range(2):
            link = False
            if val[i] != prev_val[i]:
                link = self.link_samples_size
            if val[i] > prev_val[i]:
                val[i] = next_power_of_2(val[i])
            else:
                val[i] = prev_power_of_2(val[i])
            val[i] = max(SAMPLES_MIN_SIZE, val[i])
            val[i] = min(SAMPLES_MAX_SIZE, val[i])
            if link:
                val[0] = val[1] = val[i]
        self['samples_size'] = val

    def get_sample_size(self):
        def_val = tuple(self.bl_rna.properties['samples_size'].default_array)
        return self.get('samples_size', def_val) 

    tangent_uv_map : EnumProperty(
        name="Tangent space UV",
        description="UV Layer to be used for tangent space calculation, should be the same that you've used to bake the normal map",
        items=get_uv_layers
    ) # type: ignore

    gen_lightmap_uv: BoolProperty(
        name="Generate lightmap UVs",
        description="Generate Lightmap UVs for each Lod (UV4) if not present (for StaticMeshes only)",
        default=True
    ) # type: ignore

    export_samples: BoolProperty(
        name="Export Samples",
        description="Export lightmap samples (for StaticMeshes only)",
        default=True
    ) # type: ignore

    link_samples_size: BoolProperty(
        name="Link Sample Size",
        description="Change both X and Y size uniformly",
        default=True
    ) # type: ignore

    samples_size: IntVectorProperty(
        name="Samples size",
        description="X and Y samples dimentions for Lod0, for consecutive Lods the size is halved",
        default=(256, 256),
        size=2,
        set=set_sample_size,
        get=get_sample_size
    ) # type: ignore

    use_edge_margin: BoolProperty(
        name="Use edge margin",
        description="whether to clamp samples to trinagle edge or not",
        default=True
    ) # type: ignore

    sample_padding: IntProperty(
        name="Sample padding",
        description="Sample padding",
        default=6,
        min=0,
        max=64
    ) # type: ignore

    export_geometry: BoolProperty(
        name="Export Geometry",
        description="Export visible mesh geometry to a file",
        default=True
    ) # type: ignore

    export_collmesh: BoolProperty(
        name="Export CollisionMesh",
        description="Export collision mesh geometry to a file",
        default=NATIVE_BSP_EXPORT
    ) # type: ignore

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply object modifiers",
        default=True
    ) # type: ignore

    normal_weld_threshold : FloatProperty(
        name="Normal Weld Threshold",
        description="Per-face vertex normals will get welded together when a dot product between them is above the threshold."
                    " In other words, lowering the threshold reduces the number of unique vertices getting exported, but might affect shading accuracy",
        default=0.999,
        min=0.9,
        max=1.0
    ) # type: ignore

    tangent_weld_threshold : FloatProperty(
        name="Tangent Weld Threshold",
        description="Per-face vertex tangents will get welded together when a dot product between them is above the threshold."
                    " In other words, lowering the threshold reduces the number of unique vertices getting exported, but might affect shading accuracy",
        default=0.999,
        min=0.9,
        max=1.0
    ) # type: ignore

    save_backfaces: BoolProperty(
        name="Backfaces",
        description="Exports faces with 'backface' attribute as double-sided",
        default=True
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        is_sm = self.geom_type == 'StaticMesh'

        header, body = layout.panel("BF2_PT_export_geometry", default_closed=False)
        header.prop(self, "export_geometry")
        if body:
            body.enabled = self.export_geometry
            row = body.row()
            row.label(text="Tangent UV map:")
            row.prop(self, "tangent_uv_map", text='')

            if not self.tangent_uv_map:
                body.label(text='ERROR: No valid UV map found!', icon='ERROR')

            row = body.row()
            row.prop(self, "gen_lightmap_uv")
            row.enabled = is_sm
            body.prop(self, "save_backfaces") 
            body.prop(self, "normal_weld_threshold")
            body.prop(self, "tangent_weld_threshold")

        header, body = layout.panel("BF2_PT_export_samples", default_closed=True)
        header.prop(self, "export_samples")
        header.enabled = is_sm and self.export_geometry
        if body:
            body.enabled = header.enabled and self.export_samples
            row = body.row()
            row.prop(self, "samples_size", text="Size")
            col = row.column()
            col.prop(self, "link_samples_size", text="")
            body.prop(self, "use_edge_margin")
            body.prop(self, "sample_padding")

        layout.prop(self, "export_collmesh")
        if not NATIVE_BSP_EXPORT and self.export_collmesh:
            layout.label(text='WARNING: Native BSP export module could not be loaded!', icon='ERROR')
            layout.label(text='The add-on might be incompatible with this Blender version or platform')
            layout.label(text='CollisionMesh export may take a while to complete for complex meshes')
        layout.prop(self, "apply_modifiers")

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No object active")
        try:
            active_obj = context.view_layer.objects.active
            if not active_obj:
                return
            root = find_root(active_obj)
            return parse_geom_type(root)
        except Exception as e:
            cls.poll_message_set(str(e))
            return False

    def _execute(self, context):
        mod_path = get_mod_dir(context)
        root = find_root(context.view_layer.objects.active)
        samples_size = self.samples_size if self.export_samples else None

        export_object_template(root, self.filepath,
            geom_export=self.export_geometry,
            colmesh_export=self.export_collmesh,
            apply_modifiers=self.apply_modifiers,
            gen_lightmap_uv=self.gen_lightmap_uv,
            texture_path=mod_path,
            tangent_uv_map=self.tangent_uv_map,
            normal_weld_thres=self.normal_weld_threshold,
            tangent_weld_thres=self.tangent_weld_threshold,
            samples_size=samples_size,
            use_edge_margin=self.use_edge_margin,
            sample_padding=self.sample_padding,
            save_backfaces=self.save_backfaces,
            reporter=Reporter(self.report))

    def invoke(self, context, _event):
        root = find_root(context.view_layer.objects.active)
        geom_type, obj_name = parse_geom_type(root)
        self.geom_type = geom_type # for draw()
        self.filepath = obj_name + self.filename_ext
        op = context.window_manager.operator_properties_last(EXPORT_OT_bf2_object.bl_idname)
        self.samples_size = op.samples_size
        return super().invoke(context, _event)


class IMPORT_EXPORT_FH_con(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_con"
    bl_label = "BF2 ObjectTemplate"
    bl_import_operator = IMPORT_OT_bf2_object.bl_idname
    bl_export_operator = EXPORT_OT_bf2_object.bl_idname
    bl_file_extensions = ".con"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


FILE_DESC = "ObjectTemplate (.con)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(SkeletonsToLinkCollection)
    bpy.utils.register_class(IMPORT_EXPORT_FH_con)
    bpy.utils.register_class(EXPORT_OT_bf2_object)
    bpy.utils.register_class(IMPORT_OT_bf2_object)
    bpy.utils.register_class(IMPORT_OT_bf2_object_skeleton_add)
    bpy.utils.register_class(IMPORT_OT_bf2_object_skeleton_remove)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_object_skeleton_remove)
    bpy.utils.unregister_class(IMPORT_OT_bf2_object_skeleton_add)
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_con)
    bpy.utils.unregister_class(IMPORT_OT_bf2_object)
    bpy.utils.unregister_class(EXPORT_OT_bf2_object)
    bpy.utils.unregister_class(SkeletonsToLinkCollection)
