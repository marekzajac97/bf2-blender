import bpy
import traceback
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ...core.mesh import (import_mesh,
                          import_bundledmesh,
                          import_skinnedmesh,
                          import_staticmesh,
                          export_staticmesh,
                          export_bundledmesh,
                          collect_uv_layers)
from ...core.skeleton import find_active_skeleton, ske_is_3p

from ... import PLUGIN_NAME

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

            self.__class__.IMPORT_FUNC(context, self.filepath,
                                       remove_doubles=self.remove_doubles,
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


class EXPORT_OT_bf2_mesh(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_mesh.export_mesh"
    bl_label = "Export Mesh"
    EXPORT_FUNC = None
    FILE_DESC = None

    def get_uv_layers(self, context):
        items = []
        active_obj = context.view_layer.objects.active
        for uv_channel, uv_layer in collect_uv_layers(active_obj).items():
            items.append((uv_layer, uv_layer, "", uv_channel))
        return items

    tangent_uv_map : EnumProperty(
        name="Tangent UV",
        description="UV Layer that you've used to bake the normal map, needed for tangent space generation",
        default=1,
        items=get_uv_layers
    )

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
           self.EXPORT_FUNC(active_obj, self.filepath,
                            texture_path=mod_path,
                            tangent_uv_map=self.tangent_uv_map)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class EXPORT_OT_bf2_staticmesh(EXPORT_OT_bf2_mesh):
    bl_idname = "bf2_mesh.export_staticmesh"
    bl_label = "Export Static Mesh"
    filename_ext = ".staticmesh"
    filter_glob = StringProperty(default="*.staticmesh", options={'HIDDEN'})
    EXPORT_FUNC = export_staticmesh
    FILE_DESC = "StaticMesh (.staticmesh)"

class EXPORT_OT_bf2_bundledmesh(EXPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.export_bundledmesh"
    bl_label = "Export BundledMesh"
    filename_ext = ".staticmesh"
    filter_glob = StringProperty(default="*.bundledmesh", options={'HIDDEN'})
    EXPORT_FUNC = export_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_staticmesh.bl_idname, text=IMPORT_OT_bf2_staticmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_skinnedmesh.bl_idname, text=IMPORT_OT_bf2_skinnedmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_bundledmesh.bl_idname, text=IMPORT_OT_bf2_bundledmesh.FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_staticmesh.bl_idname, text=EXPORT_OT_bf2_staticmesh.FILE_DESC)
    layout.operator(EXPORT_OT_bf2_bundledmesh.bl_idname, text=EXPORT_OT_bf2_bundledmesh.FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_mesh)
    bpy.utils.register_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_bundledmesh)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)
