import bpy
import traceback
from bpy.props import StringProperty, IntProperty
from bpy_extras.io_utils import ImportHelper

from ..core.mesh import import_mesh
from .. import PLUGIN_NAME

class IMPORT_OT_bf2_mesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_mesh.import"
    bl_description = 'Battlefield 2 mesh file'
    bl_label = "Import mesh"
    filter_glob = StringProperty(default="*.bundledmesh;*.skinnedmesh", options={'HIDDEN'})

    geom: IntProperty(
        name="Geom",
        description="Geometry to load",
        default=0,
        min=0
    )

    lod: IntProperty(
        name="Lod",
        description="Level of detail to load",
        default=0,
        min=0
    )

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
            import_mesh(context, self.filepath, geom=self.geom, lod=self.lod, texture_path=mod_path)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_mesh)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)