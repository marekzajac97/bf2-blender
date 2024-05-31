import bpy # type: ignore
import traceback
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

from ...core.mesh import (import_mesh,
                          import_bundledmesh,
                          import_skinnedmesh,
                          import_staticmesh,
                          export_staticmesh,
                          export_bundledmesh,
                          export_skinnedmesh,
                          collect_uv_layers)
from ...core.skeleton import find_active_skeleton

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
    ) # type: ignore

    lod: IntProperty(
        name="Lod",
        description="Level of detail to load",
        default=0,
        min=0
    ) # type: ignore

    only_selected_lod: BoolProperty(
        name="Only selected LOD",
        description="When unchecked, loads whole mesh hierarchy, ignoring above options",
        default=False
    ) # type: ignore

    merge_materials: BoolProperty(
        name="Merge Materials",
        description="Merge repeating BF2 materials into one Blender material (NOTE: might be force disabled on SkinnedMeshes when bone limit per material is reached)",
        default=True
    ) # type: ignore

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "only_selected_lod")
        col = layout.column()
        col.prop(self, "geom")
        col.enabled = self.only_selected_lod

        col = layout.column()
        col.prop(self, "lod")
        col.enabled = self.only_selected_lod

    def invoke(self, context, _event):
        try:
            # suggest to load only single LOD whe skeleton got imported previoulsy
            self.rig = find_active_skeleton()
            if self.rig:
                self.only_selected_lod = True
                if self.rig.name in ('1p_setup', '3p_setup'):
                    self.lod = 0
                    self.geom = 1 if self.rig.name.lower() == '3p_setup' else 0
                else:
                    self.lod = self.geom = 0
        except Exception as e:
            print(e)
        return super().invoke(context, _event)

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
            kwargs = {}
            if self.only_selected_lod:
                kwargs['geom'] = self.geom
                kwargs['lod'] = self.lod

            if self.rig:
                kwargs['geom_to_ske'] = {-1: self.rig}

            self.__class__.IMPORT_FUNC(context, self.filepath,
                                       texture_path=mod_path,
                                       merge_materials=self.merge_materials
                                       **kwargs)
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
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        try:
           self.__class__.EXPORT_FUNC(active_obj, self.filepath,
                                      texture_path=mod_path,
                                      tangent_uv_map=self.tangent_uv_map)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}

    def invoke(self, context, _event):
        self.filepath = context.view_layer.objects.active.name + self.filename_ext
        return super().invoke(context, _event)

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
    filename_ext = ".bundledmesh"
    filter_glob = StringProperty(default="*.bundledmesh", options={'HIDDEN'})
    EXPORT_FUNC = export_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"

class EXPORT_OT_bf2_skinnedmesh(EXPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.export_skinnedmesh"
    bl_label = "Export SkinnedMesh"
    filename_ext = ".skinnedmesh"
    filter_glob = StringProperty(default="*.skinnedmesh", options={'HIDDEN'})
    EXPORT_FUNC = export_skinnedmesh
    FILE_DESC = "SkinnedMesh (.skinnedmesh)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_staticmesh.bl_idname, text=IMPORT_OT_bf2_staticmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_skinnedmesh.bl_idname, text=IMPORT_OT_bf2_skinnedmesh.FILE_DESC)
    layout.operator(IMPORT_OT_bf2_bundledmesh.bl_idname, text=IMPORT_OT_bf2_bundledmesh.FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_staticmesh.bl_idname, text=EXPORT_OT_bf2_staticmesh.FILE_DESC)
    layout.operator(EXPORT_OT_bf2_bundledmesh.bl_idname, text=EXPORT_OT_bf2_bundledmesh.FILE_DESC)
    layout.operator(EXPORT_OT_bf2_skinnedmesh.bl_idname, text=EXPORT_OT_bf2_skinnedmesh.FILE_DESC)

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_mesh)
    bpy.utils.register_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.register_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_bundledmesh)
    bpy.utils.register_class(EXPORT_OT_bf2_skinnedmesh)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)
