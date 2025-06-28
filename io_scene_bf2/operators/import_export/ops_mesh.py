import bpy # type: ignore
import traceback
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper, poll_file_object_drop # type: ignore

from ...core.exceptions import ImportException, ExportException # type: ignore
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

from ... import get_mod_dir

class IMPORT_OT_bf2_mesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_mesh.import"
    bl_description = 'Import Battlefield 2 Mesh file'
    bl_label = "Import mesh"
    filter_glob: StringProperty(default="*.bundledmesh;*.skinnedmesh;*.staticmesh", options={'HIDDEN'}) # type: ignore
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

    load_backfaces: BoolProperty(
        name="Backfaces",
        description="Adds 'backface' attribute to double-sided faces. Disabling this will ignore any duplicated faces",
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

        col = layout.column()
        col.prop(self, "merge_materials")

        col = layout.column()
        col.prop(self, "load_backfaces")

    def invoke(self, context, _event):
        try:
            # suggest to load only single LOD whe skeleton got imported previoulsy
            self.rig = find_active_skeleton(context)
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
        mod_path = get_mod_dir(context)
        try:
            kwargs = {}
            if self.only_selected_lod:
                kwargs['geom'] = self.geom
                kwargs['lod'] = self.lod

            if self.rig:
                kwargs['geom_to_ske'] = {-1: self.rig}

            self.__class__.IMPORT_FUNC(context, self.filepath,
                                       texture_path=mod_path,
                                       merge_materials=self.merge_materials,
                                       load_backfaces=self.load_backfaces,
                                       reporter=Reporter(self.report),
                                       **kwargs)
        except ImportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        return {'FINISHED'}


class IMPORT_OT_bf2_staticmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_staticmesh"
    bl_description = 'Import Battlefield 2 static mesh file'
    bl_label = "Import StaticMesh"
    filter_glob: StringProperty(default="*.staticmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_staticmesh
    FILE_DESC = "StaticMesh (.staticmesh)"


class IMPORT_OT_bf2_skinnedmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_skinnedmesh"
    bl_description = 'Import Battlefield 2 skinned mesh file'
    bl_label = "Import SkinnedMesh"
    filter_glob: StringProperty(default="*.skinnedmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_skinnedmesh
    FILE_DESC = "SkinnedMesh (.skinnedmesh)"


class IMPORT_OT_bf2_bundledmesh(IMPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.import_bundledmesh"
    bl_description = 'Import Battlefield 2 bundled mesh file'
    bl_label = "Import BundledMesh"
    filter_glob: StringProperty(default="*.bundledmesh", options={'HIDDEN'}) # type: ignore
    IMPORT_FUNC = import_bundledmesh
    FILE_DESC = "BundledMesh (.bundledmesh)"


class EXPORT_OT_bf2_mesh(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_mesh.export_mesh"
    bl_label = "Export Mesh"
    EXPORT_FUNC = None
    FILE_DESC = None

    def get_uv_layers(self, context):
        items = []
        root = find_root(context.view_layer.objects.active)
        object_uv_layers = collect_uv_layers(root)
        default = None

        idname = self.bl_rna.identifier
        if idname == 'BF2_MESH_OT_export_staticmesh':
            default = 1 # Detail normal
        elif idname == 'BF2_MESH_OT_export_bundledmesh' or idname == 'BF2_MESH_OT_export_skinnedmesh':
            default = 0 # Diffuse/Normal

        # XXX: it is not possible to define a default for dynamic enums
        # the only way is to reorder items in such a way that the default one
        # is the first one in the list, not ideal but works
        start = 0
        if default in object_uv_layers:
            uv_layer = object_uv_layers.pop(default)
            items.append((uv_layer, uv_layer, "", 0))
            start = 1

        for i, uv_layer in enumerate(object_uv_layers.values(), start=start):
            items.append((uv_layer, uv_layer, "", i))

        return items

    tangent_uv_map : EnumProperty(
        name="Tangent UV",
        description="UV Layer that you've used to bake the normal map, needed for tangent space generation",
        items=get_uv_layers
    ) # type: ignore

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

    def execute(self, context):
        mod_path = get_mod_dir(context)
        try:
           self.__class__.EXPORT_FUNC(self.root, self.filepath,
                                      texture_path=mod_path,
                                      tangent_uv_map=self.tangent_uv_map,
                                      save_backfaces=self.save_backfaces,
                                      apply_modifiers=self.apply_modifiers,
                                      reporter=Reporter(self.report))
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


class EXPORT_OT_bf2_staticmesh(EXPORT_OT_bf2_mesh):
    bl_idname = "bf2_mesh.export_staticmesh"
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


class EXPORT_OT_bf2_bundledmesh(EXPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.export_bundledmesh"
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


class EXPORT_OT_bf2_skinnedmesh(EXPORT_OT_bf2_mesh):
    bl_idname= "bf2_mesh.export_skinnedmesh"
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
