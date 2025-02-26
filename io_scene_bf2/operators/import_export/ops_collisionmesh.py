import bpy # type: ignore
import traceback
from bpy.props import StringProperty # type: ignore
from bpy_extras.io_utils import ExportHelper, ImportHelper, poll_file_object_drop # type: ignore

from ...core.exceptions import ImportException, ExportException # type: ignore
from ...core.collision_mesh import import_collisionmesh, export_collisionmesh
from ...core.utils import find_root

class IMPORT_OT_bf2_collisionmesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_collisionmesh.import"
    bl_description = 'Battlefield 2 collision mesh file'
    bl_label = "Import Collision Mesh"
    filter_glob: StringProperty(default="*.collisionmesh", options={'HIDDEN'}) # type: ignore

    def execute(self, context):
        try:
            import_collisionmesh(context, self.filepath)
        except ImportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        return {'FINISHED'}

class EXPORT_OT_bf2_collisionmesh(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_collisionmesh.export"
    bl_label = "Export Collision Mesh"

    filename_ext = ".collisionmesh"
    filter_glob: StringProperty(default="*.collisionmesh", options={'HIDDEN'}) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No object active")
        return context.view_layer.objects.active is not None

    def execute(self, context):
        try:
           export_collisionmesh(self.root, self.filepath)
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
        self.root = find_root(active_obj)
        self.filepath = self.root.name + self.filename_ext
        result = super().invoke(context, _event)
        context.view_layer.objects.active = active_obj # restore
        return result


class IMPORT_EXPORT_FH_collisionmesh(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_collisionmesh"
    bl_label = "BF2 CollisionMesh"
    bl_import_operator = IMPORT_OT_bf2_collisionmesh.bl_idname
    bl_export_operator = EXPORT_OT_bf2_collisionmesh.bl_idname
    bl_file_extensions = ".collisionmesh"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


FILE_DESC = "CollisionMesh (.collisionmesh)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_collisionmesh.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_collisionmesh.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_collisionmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_collisionmesh)
    bpy.utils.register_class(IMPORT_EXPORT_FH_collisionmesh)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_collisionmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_collisionmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_collisionmesh)