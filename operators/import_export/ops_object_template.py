import bpy # type: ignore
import traceback
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty, CollectionProperty # type: ignore
from bpy_extras.io_utils import ExportHelper, ImportHelper # type: ignore

from ...core.object_template import import_object, export_object, parse_geom_type, NATIVE_BSP_EXPORT
from ...core.mesh import collect_uv_layers
from ...core.skeleton import find_all_skeletons
from ...core.exceptions import ImportException, ExportException
from ...core.utils import Reporter

from ... import PLUGIN_NAME

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

class IMPORT_OT_bf2_object(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_object.import"
    bl_description = 'Battlefield 2 ObjectTemplate'
    bl_label = "Import BF2 ObjectTemplate"
    filter_glob = StringProperty(default="*.con", options={'HIDDEN'})

    import_collmesh: BoolProperty(
        name="Import CollisionMesh",
        description="Load CollisionMesh and merge with the object hierarchy",
        default=False
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

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory

        geom_to_ske = None
        if self.import_rig_mode == 'MANUAL':
            geom_to_ske = dict()
            for prop in self.skeletons_to_link:
                geom_to_ske[prop.geom_idx] = prop.skeleton

        try:
            import_object(context, self.filepath,
                          import_collmesh=self.import_collmesh,
                          import_rig=(self.import_rig_mode, geom_to_ske),
                          texture_path=mod_path,
                          reporter=Reporter(self.report))
        except ImportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, _event):
        IMPORT_OT_bf2_object.instance=self
        return super().invoke(context, _event)

class IMPORT_OT_bf2_object_skeleton_add(bpy.types.Operator):
    bl_idname = "bf2_object.skeleton_add"
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
    bl_idname = "bf2_object.skeleton_remove"
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

class EXPORT_OT_bf2_object(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_object.export"
    bl_label = "Export BF2 ObjectTemplate"
    filename_ext = ".con"
    filter_glob = StringProperty(default="*.con", options={'HIDDEN'})
    FILE_DESC = "ObjectTemplate (.con)"

    def get_uv_layers(self, context):
        items = []
        active_obj = context.view_layer.objects.active
        object_uv_layers = collect_uv_layers(active_obj)
        default = None

        geom_type, _ = parse_geom_type(active_obj)
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

    tangent_uv_map : EnumProperty(
        name="Tangent UV",
        description="UV Layer that you've used to bake the normal map, needed for tangent space generation",
        items=get_uv_layers
    ) # type: ignore

    gen_lightmap_uv: BoolProperty(
        name="Generate lightmap UVs",
        description="Generate StaticMesh Lightmap UVs for each Lod (UV4) if not present",
        default=True
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

    triangulate: BoolProperty(
        name="Triangulate",
        description="Convert Polygons to Triangles",
        default=True
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

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "tangent_uv_map")

        row = layout.row()
        row.prop(self, "gen_lightmap_uv")
        row.enabled = self.geom_type == 'StaticMesh'

        layout.prop(self, "export_geometry")
        layout.prop(self, "export_collmesh")
        if not NATIVE_BSP_EXPORT and self.export_collmesh:
            layout.label(text='WARNING: Native BSP export module could not be loaded', icon='ERROR')
            layout.label(text='CollisionMesh export may take forever for complex meshes')
        layout.prop(self, "triangulate")
        layout.prop(self, "apply_modifiers")
        layout.prop(self, "normal_weld_threshold")
        layout.prop(self, "tangent_weld_threshold")

    @classmethod
    def poll(cls, context):
        try:
            active_obj = context.view_layer.objects.active
            return active_obj is not None and parse_geom_type(active_obj)
        except Exception as e:
            cls.poll_message_set(str(e))
            return False

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
           export_object(active_obj, self.filepath,
                         geom_export=self.export_geometry,
                         colmesh_export=self.export_collmesh,
                         triangluate=self.triangulate,
                         apply_modifiers=self.apply_modifiers,
                         gen_lightmap_uv=self.gen_lightmap_uv,
                         texture_path=mod_path,
                         tangent_uv_map=self.tangent_uv_map,
                         normal_weld_thres=self.normal_weld_threshold,
                         tangent_weld_thres=self.tangent_weld_threshold,
                         reporter=Reporter(self.report))
        except ExportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}

    def invoke(self, context, _event):
        active_obj = context.view_layer.objects.active
        geom_type, obj_name = parse_geom_type(active_obj)
        self.filepath = obj_name + self.filename_ext
        self.geom_type = geom_type
        return super().invoke(context, _event)


FILE_DESC = "ObjectTemplate (.con)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(SkeletonsToLinkCollection)
    bpy.utils.register_class(EXPORT_OT_bf2_object)
    bpy.utils.register_class(IMPORT_OT_bf2_object)
    bpy.utils.register_class(IMPORT_OT_bf2_object_skeleton_add)
    bpy.utils.register_class(IMPORT_OT_bf2_object_skeleton_remove)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_object_skeleton_remove)
    bpy.utils.unregister_class(IMPORT_OT_bf2_object_skeleton_add)
    bpy.utils.unregister_class(IMPORT_OT_bf2_object)
    bpy.utils.unregister_class(EXPORT_OT_bf2_object)
    bpy.utils.unregister_class(SkeletonsToLinkCollection)
