import bpy
import traceback
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ...core.game_object import import_object, export_object, parse_geom_type
from ...core.mesh import collect_uv_layers

from ... import PLUGIN_NAME

class IMPORT_OT_bf2_object(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_object.import"
    bl_description = 'Battlefield 2 ObjectTemplate'
    bl_label = "Import BF2 ObjectTemplate"
    filter_glob = StringProperty(default="*.con", options={'HIDDEN'})

    import_collmesh: BoolProperty(
        name="Import CollisionMesh",
        description="Load CollisionMesh and merge with the object hierarchy",
        default=False
    )

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
            import_object(context, self.filepath, import_collmesh=self.import_collmesh, texture_path=mod_path)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


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
        try:
            geom_type, _ = parse_geom_type(active_obj)
            if geom_type == 'StaticMesh':
                default = 1 # Detail normal
            elif geom_type == 'BundledMesh':
                default = 0 # Diffuse/Normal
        except Exception as e:
            pass

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
    )

    export_geometry: BoolProperty(
        name="Export Geometry",
        description="Export visible mesh geometry to a file",
        default=True
    )

    export_collmesh: BoolProperty(
        name="Export CollisionMesh",
        description="Export collision mesh geometry to a file",
        default=True
    )

    triangulate: BoolProperty(
        name="Triangulate",
        description="Convert Quads to Triangles",
        default=True
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply object modifiers",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
           export_object(active_obj, self.filepath,
                         geom_export=self.export_geometry,
                         colmesh_export=self.export_collmesh,
                         triangluate=self.triangulate,
                         apply_modifiers=self.apply_modifiers,
                         texture_path=mod_path,
                         tangent_uv_map=self.tangent_uv_map)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


FILE_DESC = "ObjectTemplate (.con)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_object.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(EXPORT_OT_bf2_object)
    bpy.utils.register_class(IMPORT_OT_bf2_object)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_object)
    bpy.utils.unregister_class(EXPORT_OT_bf2_object)
