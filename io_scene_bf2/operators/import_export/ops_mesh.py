import bpy # type: ignore
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import poll_file_object_drop # type: ignore

from .ops_common import ImporterBase, ExporterBase
from ...core.mesh import (import_mesh,
                          import_bundledmesh,
                          import_skinnedmesh,
                          import_staticmesh,
                          export_staticmesh,
                          export_bundledmesh,
                          export_skinnedmesh,
                          collect_uv_layers)
from ...core.skeleton import find_active_skeleton
from ...core.utils import find_root, Reporter

from ... import get_mod_dirs

class MeshImportBase(ImporterBase):

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

    load_backfaces: BoolProperty(
        name="Backfaces",
        description="Adds 'backface' attribute to double-sided faces. Disabling this will ignore any duplicated faces",
        default=True
    ) # type: ignore

    def draw(self, context):
        layout = self.layout

        header, body = layout.panel("BF2_PT_export_geometry", default_closed=False)
        header.prop(self, "only_selected_lod")

        if body:
            body.enabled = self.only_selected_lod
            body.prop(self, "geom")
            body.prop(self, "lod")

        col = layout.column()
        col.prop(self, "merge_materials")

        col = layout.column()
        col.prop(self, "load_backfaces")

    def invoke(self, context, _event):
        # suggest to load only single LOD when a skeleton got imported previoulsy
        rig = find_active_skeleton(context)
        if rig:
            self.only_selected_lod = True
            if rig.name in ('1p_setup', '3p_setup'):
                self.lod = 0
                self.geom = 1 if rig.name.lower() == '3p_setup' else 0
            else:
                self.lod = self.geom = 0
        return super().invoke(context, _event)

    def _execute(self, context):
        mod_paths = get_mod_dirs(context)
        kwargs = {}
        if self.only_selected_lod:
            kwargs['geom'] = self.geom
            kwargs['lod'] = self.lod

        rig = find_active_skeleton(context)
        if rig:
            kwargs['geom_to_ske'] = {-1: rig}

        context.view_layer.objects.active = \
            self.__class__.IMPORT_FUNC(context, self.filepath,
                                       texture_paths=mod_paths,
                                       merge_materials=self.merge_materials,
                                       load_backfaces=self.load_backfaces,
                                       reporter=Reporter(self.report),
                                       **kwargs)

class IMPORT_OT_bf2_mesh(bpy.types.Operator, MeshImportBase):
    bl_idname= "bf2.mesh_import"
    bl_description = 'Import Battlefield 2 Mesh file'
    bl_label = "Import mesh"
    filter_glob: StringProperty(default="*.bundledmesh;*.skinnedmesh;*.staticmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_mesh
    FILE_DESC = "Mesh (.bundledmesh, .skinnedmesh, .staticmesh)"


class IMPORT_OT_bf2_staticmesh(bpy.types.Operator, MeshImportBase):
    bl_idname= "bf2.staticmesh_import"
    bl_description = 'Import Battlefield 2 static mesh file'
    bl_label = "Import StaticMesh"
    filter_glob: StringProperty(default="*.staticmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_staticmesh
    FILE_DESC = "StaticMesh (.staticmesh)"


class IMPORT_OT_bf2_skinnedmesh(bpy.types.Operator, MeshImportBase):
    bl_idname= "bf2.skinnedmesh_import"
    bl_description = 'Import Battlefield 2 skinned mesh file'
    bl_label = "Import SkinnedMesh"
    filter_glob: StringProperty(default="*.skinnedmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_skinnedmesh
    FILE_DESC = "SkinnedMesh (.skinnedmesh)"


class IMPORT_OT_bf2_bundledmesh(bpy.types.Operator, MeshImportBase):
    bl_idname= "bf2.bundledmesh_import"
    bl_description = 'Import Battlefield 2 bundled mesh file'
    bl_label = "Import BundledMesh"
    filter_glob: StringProperty(default="*.bundledmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"


class MeshExportBase(ExporterBase):
    bl_idname = "bf2.mesh_export"
    bl_label = "Export Mesh"
    EXPORT_FUNC = None
    FILE_DESC = None

    save_backfaces: BoolProperty(
        name="Backfaces",
        description="Exports faces with 'backface' attribute as double-sided",
        default=True
    ) # type: ignore

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply object modifiers",
        default=True
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No object active")
        return context.view_layer.objects.active is not None

    def _execute(self, context):
        mod_paths = get_mod_dirs(context)
        root = find_root(context.view_layer.objects.active)
        self.__class__.EXPORT_FUNC(root, self.filepath,
                                   texture_paths=mod_paths,
                                   save_backfaces=self.save_backfaces,
                                   apply_modifiers=self.apply_modifiers,
                                   triangulate=True,
                                   reporter=Reporter(self.report))

    def invoke(self, context, _event):
        root = find_root(context.view_layer.objects.active)
        self.filepath = root.name + self.filename_ext
        return super().invoke(context, _event)


class EXPORT_OT_bf2_staticmesh(bpy.types.Operator, MeshExportBase):
    bl_idname = "bf2.staticmesh_export"
    bl_label = "Export Static Mesh"
    filename_ext = ".staticmesh"
    filter_glob: StringProperty(default="*.staticmesh", options={'HIDDEN'}) # type: ignore
    EXPORT_FUNC = export_staticmesh
    FILE_DESC = "StaticMesh (.staticmesh)"


class IMPORT_EXPORT_FH_staticmesh(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_staticmesh"
    bl_label = "BF2 StaticMesh"
    bl_import_operator = IMPORT_OT_bf2_staticmesh.bl_idname
    bl_export_operator = EXPORT_OT_bf2_staticmesh.bl_idname
    bl_file_extensions = ".staticmesh"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


class EXPORT_OT_bf2_bundledmesh(bpy.types.Operator, MeshExportBase):
    bl_idname= "bf2.bundledmesh_export"
    bl_label = "Export BundledMesh"
    filename_ext = ".bundledmesh"
    filter_glob: StringProperty(default="*.bundledmesh", options={'HIDDEN'}) # type: ignore
    EXPORT_FUNC = export_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"


class IMPORT_EXPORT_FH_bundledmesh(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_bundledmesh"
    bl_label = "BF2 BundledMesh"
    bl_import_operator = IMPORT_OT_bf2_bundledmesh.bl_idname
    bl_export_operator = EXPORT_OT_bf2_bundledmesh.bl_idname
    bl_file_extensions = ".bundledmesh"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


class EXPORT_OT_bf2_skinnedmesh(bpy.types.Operator, MeshExportBase):
    bl_idname= "bf2.skinnedmesh_export"
    bl_label = "Export SkinnedMesh"
    filename_ext = ".skinnedmesh"
    filter_glob: StringProperty(default="*.skinnedmesh", options={'HIDDEN'}) # type: ignore
    EXPORT_FUNC = export_skinnedmesh
    FILE_DESC = "SkinnedMesh (.skinnedmesh)"


class IMPORT_EXPORT_FH_skinnedmesh(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_skinnedmesh"
    bl_label = "BF2 SkinnedMesh"
    bl_import_operator = IMPORT_OT_bf2_skinnedmesh.bl_idname
    bl_export_operator = EXPORT_OT_bf2_skinnedmesh.bl_idname
    bl_file_extensions = ".skinnedmesh"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


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

    bpy.utils.register_class(IMPORT_EXPORT_FH_staticmesh)
    bpy.utils.register_class(IMPORT_EXPORT_FH_bundledmesh)
    bpy.utils.register_class(IMPORT_EXPORT_FH_skinnedmesh)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_skinnedmesh)
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_bundledmesh)
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_staticmesh)

    bpy.utils.unregister_class(EXPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(EXPORT_OT_bf2_staticmesh)
    
    bpy.utils.unregister_class(IMPORT_OT_bf2_bundledmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skinnedmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_staticmesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)
