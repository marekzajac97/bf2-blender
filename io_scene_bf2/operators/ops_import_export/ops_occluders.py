import bpy # type: ignore
from bpy.props import StringProperty # type: ignore
from bpy_extras.io_utils import poll_file_object_drop # type: ignore

from .ops_common import ImporterBase, ExporterBase
from ...core.occluders import import_occluders, export_occluders

class IMPORT_OT_bf2_occluders(bpy.types.Operator, ImporterBase):
    bl_idname= "bf2.occ_import"
    bl_description = 'Battlefield 2 occluder planes file'
    bl_label = "Import occluder planes"

    filter_glob: StringProperty(default="*.occ", options={'HIDDEN'}) # type: ignore

    def _execute(self, context):
        context.view_layer.objects.active = \
            import_occluders(context, self.filepath)

class EXPORT_OT_bf2_occluders(bpy.types.Operator, ExporterBase):
    bl_idname = "bf2.occ_export"
    bl_description = 'Battlefield 2 occluder planes file'
    bl_label = "Export occluder planes"

    filename_ext = ".occ"
    filter_glob: StringProperty(default="*.occ", options={'HIDDEN'}) # type: ignore

    @classmethod
    def poll(cls, context):
        active_obj = context.view_layer.objects.active
        return active_obj and isinstance(active_obj.data, bpy.types.Mesh)

    def _execute(self, context):
        export_occluders(context.view_layer.objects.active, self.filepath)

    def invoke(self, context, _event):
        self.filepath = context.view_layer.objects.active.name + self.filename_ext
        return super().invoke(context, _event)


class IMPORT_EXPORT_FH_occ(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_occ"
    bl_label = "BF2 Occlusion Mesh"
    bl_import_operator = IMPORT_OT_bf2_occluders.bl_idname
    bl_export_operator = EXPORT_OT_bf2_occluders.bl_idname
    bl_file_extensions = ".occ"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


FILE_DESC = "Occlusion Mesh (.occ)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_occluders.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_occluders.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_EXPORT_FH_occ)
    bpy.utils.register_class(IMPORT_OT_bf2_occluders)
    bpy.utils.register_class(EXPORT_OT_bf2_occluders)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_occ)
    bpy.utils.unregister_class(EXPORT_OT_bf2_occluders)
    bpy.utils.unregister_class(IMPORT_OT_bf2_occluders)
