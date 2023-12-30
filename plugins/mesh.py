import bpy
import traceback
from bpy.types import Mesh
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ..core.mesh import (import_mesh,
                         import_bundledmesh,
                         import_skinnedmesh,
                         import_staticmesh,
                         export_staticmesh,
                         add_staticmesh_material,
                         get_uv_layers)
from ..core.skeleton import find_active_skeleton, ske_is_3p

from .. import PLUGIN_NAME

class IMPORT_OT_bf2_mesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_mesh.import"
    bl_description = 'Import Battlefield 2 Mesh file'
    bl_label = "Import mesh"
    filter_glob = StringProperty(default="*.bundledmesh;*.skinnedmesh;*.staticmesh", options={'HIDDEN'})
    IMPORT_FUNC = import_mesh
    FILE_DESC = "Mesh (.bundledmesh, .skinnedmesh, .staticmesh)"

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
        description="When unchecked, loads whole mesh hierarchy, ignoring above options",
        default=False
    )

    remove_doubles: BoolProperty(
        name="Merge double verts",
        description="Try to remove vertices that were duplicated during export to preserve split per-vertex normals",
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
                kwargs = {'geom': self.geom, 'lod': self.lod}
            else:
                kwargs = {}

            self.__class__.IMPORT_FUNC(context, self.filepath, remove_doubles=self.remove_doubles,
                                       texture_path=mod_path, **kwargs)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class IMPORT_OT_bf2_staticmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_staticmesh"
    bl_description = 'Import Battlefield 2 static mesh file'
    bl_label = "Import StaticMesh"
    filter_glob = StringProperty(default="*.staticmesh", options={'HIDDEN'})
    IMPORT_FUNC = import_staticmesh
    FILE_DESC = "StaticMesh (.staticmesh)"


class IMPORT_OT_bf2_skinnedmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_skinnedmesh"
    bl_description = 'Import Battlefield 2 skinned mesh file'
    bl_label = "Import SkinnedMesh"
    filter_glob = StringProperty(default="*.skinnedmesh", options={'HIDDEN'})
    IMPORT_FUNC = import_skinnedmesh
    FILE_DESC = "SkinnedMesh (.skinnedmesh)"


class IMPORT_OT_bf2_bundledmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_bundledmesh"
    bl_description = 'Import Battlefield 2 bundled mesh file'
    bl_label = "Import BundledMesh"
    filter_glob = StringProperty(default="*.bundledmesh", options={'HIDDEN'})
    IMPORT_FUNC = import_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"


def add_uvs(self, context):
    items = []
    active_obj = context.view_layer.objects.active
    for uv_channel, uv_layer in get_uv_layers(active_obj).items():
        items.append((uv_layer, uv_layer, "", uv_channel))
    return items

class EXPORT_OT_bf2_staticmesh(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_mesh.export_staticmesh"
    bl_label = "Export Static Mesh"
    filename_ext = ".staticmesh"
    filter_glob = StringProperty(default="*.staticmesh", options={'HIDDEN'})
    FILE_DESC = "StaticMesh (.staticmesh)"

    tangent_uv_map : EnumProperty(
        name="Tangent UV",
        description="UV Layer that you've used to bake the normal map, needed for tangent space generation",
        default=1,
        items=add_uvs
    )

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
           export_staticmesh(active_obj, self.filepath, mod_path, self.tangent_uv_map)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

###########################
######### Materials #######
###########################

MATERIAL_TYPES = [
    ('STATICMESH', 'StaticMesh', "", 0),
]
   
ALPHA_MODES = [
    ('NONE', 'None', "", 0),
    ('ALPHA_TEST', 'Alpha Test', "", 1)
    # ('ALPHA_BLEND', 'Alpha Blend', "", 2) # Not supported yet
]

class MESH_OT_bf2_add_material(bpy.types.Operator):
    bl_idname = "bf2_mesh.add_material_staticmesh"
    bl_label = "Add Static Mesh material"

    meaterial_type : EnumProperty(
        name="Material type",
        description="Sets up material nodes to mimic specific BF2 shader",
        default=0,
        items=MATERIAL_TYPES
    )

    alpha_mode : EnumProperty(
        name="Alpha mode",
        description="Creates additional transparency BSDF and links it with proper alpha channel",
        default=0,
        items=ALPHA_MODES
    )

    @classmethod
    def poll(cls, context):
        active_obj = context.view_layer.objects.active
        return active_obj is not None and isinstance(active_obj.data, Mesh)

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        try:
           if self.meaterial_type == 'STATICMESH':
                add_staticmesh_material(active_obj.data, self.alpha_mode)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

class MESH_PT_bf2_materials(bpy.types.Panel):
    bl_label = "BF2 Material Tools"
    bl_idname = "MESH_PT_bf2_materials"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        active_obj = context.view_layer.objects.active
        return active_obj is not None and isinstance(active_obj.data, Mesh)

    def draw(self, context):
        row = self.layout.row()
        row.operator(MESH_OT_bf2_add_material.bl_idname, text="Add Material")

def draw_import(layout):
    # layout.operator(IMPORT_OT_bf2_mesh.bl_idname, text=IMPORT_OT_bf2_mesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_staticmesh.bl_idname, text=IMPORT_OT_bf2_staticmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_skinnedmesh.bl_idname, text=IMPORT_OT_bf2_skinnedmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_bundledmesh.bl_idname, text=IMPORT_OT_bf2_bundledmesh.FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_staticmesh.bl_idname, text=EXPORT_OT_bf2_staticmesh.FILE_DESC)

def register():
    # bpy.utils.register_class(IMPORT_OT_bf2_mesh)
    bpy.utils.register_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(MESH_OT_bf2_add_material)
    bpy.utils.register_class(MESH_PT_bf2_materials)

def unregister():
    bpy.utils.unregister_class(MESH_OT_bf2_add_material)
    bpy.utils.unregister_class(MESH_PT_bf2_materials)
    bpy.utils.unregister_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_staticmesh)
    
    # bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)
