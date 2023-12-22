import bpy
import traceback
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper

from ..core.mesh import import_mesh
from ..core.skeleton import find_active_skeleton, ske_is_3p

from .. import PLUGIN_NAME

class IMPORT_OT_bf2_mesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_mesh.import"
    bl_description = 'Battlefield 2 mesh file'
    bl_label = "Import mesh"
    filter_glob = StringProperty(default="*.bundledmesh;*.skinnedmesh;*.staticmesh", options={'HIDDEN'})

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

    only_selected_lod: BoolProperty(
        name="Only selected LOD",
        description="When unchecked, lods whole mesh hierarchy, ignoring above options",
        default=False
    )

    def invoke(self, context, _event):
        try:
            # suggest to load only single LOD whe skeleton got imported previoulsy
            ske_data = find_active_skeleton(context)
            if ske_data:
                self.only_selected_lod = True
                _, skeleton = ske_data
                self.lod = 0
                self.geom = 1 if ske_is_3p(skeleton) else 0
        except Exception as e:
            print(e)
        return super().invoke(context, _event)

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
            if self.only_selected_lod:
                import_mesh(context, self.filepath, geom=self.geom, lod=self.lod, texture_path=mod_path)
            else:
                import_mesh(context, self.filepath, texture_path=mod_path)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

FILE_DESC = "Mesh (.bundledmesh, .skinnedmesh, .staticmesh)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_mesh.bl_idname, text=FILE_DESC)

def draw_export(layout):
    pass

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_mesh)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)