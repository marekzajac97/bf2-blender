import bpy # type: ignore
import traceback
from bpy.props import StringProperty # type: ignore
from bpy_extras.io_utils import poll_file_object_drop # type: ignore

from .ops_common import ImporterBase, ExporterBase
from ...core.skeleton import import_skeleton, export_skeleton


class IMPORT_OT_bf2_skeleton(bpy.types.Operator, ImporterBase):
    bl_idname = "bf2.ske_import"
    bl_description = 'Battlefield 2 Skeleton file'
    bl_label = "Import Skeleton"

    filter_glob: StringProperty(default="*.ske", options={'HIDDEN'}) # type: ignore

    def _execute(self, context):
        context.view_layer.objects.active = \
            import_skeleton(context, self.filepath)


class EXPORT_OT_bf2_skeleton(bpy.types.Operator, ExporterBase):
    bl_idname = "bf2.ske_export"
    bl_description = 'Battlefield 2 Skeleton file'
    bl_label = "Export Skeleton"

    filename_ext = ".ske"
    filter_glob: StringProperty(default="*.ske", options={'HIDDEN'}) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No armature object active")
        active_obj = context.view_layer.objects.active
        return active_obj is not None and isinstance(active_obj.data, bpy.types.Armature)

    def _execute(self, context):
        export_skeleton(context.view_layer.objects.active, self.filepath)

    def invoke(self, context, _event):
        self.filepath = context.view_layer.objects.active.name + self.filename_ext
        return super().invoke(context, _event)


class IMPORT_EXPORT_FH_ske(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_ske"
    bl_label = "BF2 Skeleton"
    bl_import_operator = IMPORT_OT_bf2_skeleton.bl_idname
    bl_export_operator = EXPORT_OT_bf2_skeleton.bl_idname
    bl_file_extensions = ".ske"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


FILE_DESC = "Skeleton (.ske)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_skeleton.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_skeleton.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_EXPORT_FH_ske)
    bpy.utils.register_class(IMPORT_OT_bf2_skeleton)
    bpy.utils.register_class(EXPORT_OT_bf2_skeleton)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_ske)
    bpy.utils.unregister_class(EXPORT_OT_bf2_skeleton)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skeleton)
