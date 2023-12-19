import bpy
import traceback
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core.collision_mesh import import_collisionmesh, export_collisonmesh

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

    def execute(self, context):
        try:
           export_collisonmesh(context, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


def register():
    bpy.utils.register_class(IMPORT_OT_bf2_collisionmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_collisionmesh)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_bf2_collisionmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_collisionmesh)