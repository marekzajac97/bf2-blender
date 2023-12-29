import bpy
import traceback
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core.collision_mesh import import_collisionmesh, export_collisionmesh

class IMPORT_OT_bf2_collisionmesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_collisionmesh.import"
    bl_description = 'Battlefield 2 collision mesh file'
    bl_label = "Import Collision Mesh"
    filter_glob = StringProperty(default="*.collisionmesh", options={'HIDDEN'})

    def execute(self, context):
        try:
            import_collisionmesh(context, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

class EXPORT_OT_bf2_collisionmesh(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_collisionmesh.export"
    bl_label = "Export Collision Mesh"

    filename_ext = ".collisionmesh"
    filter_glob = StringProperty(default="*.collisionmesh", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        try:
           export_collisionmesh(active_obj, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


FILE_DESC = "CollisionMesh (.collisionmesh)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_collisionmesh.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_collisionmesh.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_collisionmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_collisionmesh)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_bf2_collisionmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_collisionmesh)