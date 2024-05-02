import bpy # type: ignore
import traceback
from bpy.props import StringProperty # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

from ...core.skeleton import import_skeleton, export_skeleton

class IMPORT_OT_bf2_skeleton(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_skeleton.import"
    bl_description = 'Battlefield 2 skeleton file'
    bl_label = "Import skeleton"
    filter_glob = StringProperty(default="*.ske", options={'HIDDEN'})

    def execute(self, context):
        try:
           import_skeleton(context, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

class EXPORT_OT_bf2_skeleton(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_skeleton.export"
    bl_label = "Export Collision Mesh"

    filename_ext = ".ske"
    filter_glob = StringProperty(default="*.ske", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        active_obj = context.view_layer.objects.active
        return active_obj is not None and isinstance(active_obj.data, bpy.types.Armature)

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        try:
           export_skeleton(active_obj, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}

    def invoke(self, context, _event):
        self.filepath = context.view_layer.objects.active.name + self.filename_ext
        return super().invoke(context, _event)

FILE_DESC = "Skeleton (.ske)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_skeleton.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_skeleton.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_skeleton)
    bpy.utils.register_class(EXPORT_OT_bf2_skeleton)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_bf2_skeleton)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skeleton)
