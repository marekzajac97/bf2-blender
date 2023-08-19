import bpy
import traceback
from bpy.props import StringProperty, IntProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .scene_manipulator import SceneManipulator

# -------------------------- Import --------------------------

class IMPORT_OT_bf2_skeleton(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_import.skeleton"
    bl_description = 'Battlefield 2 skeleton file'
    bl_label = "Import skeleton"
    filter_glob = StringProperty(default="*.ske", options={'HIDDEN'})

    def invoke(self, context, _event):
        self.sm = SceneManipulator(context.scene)
        return super().invoke(context, _event)

    def execute(self, context):
        try:
           self.sm.import_skeleton(self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class IMPORT_OT_bf2_animation(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_import.animation"
    bl_description = 'Battlefield 2 animation file'
    bl_label = "Import animation"
    filter_glob = StringProperty(default="*.baf", options={'HIDDEN'})

    setup_ctrls: BoolProperty(
        name="Setup Controllers",
        description="Create basic animation helper bones and setup IKs, (NOTE: enabling this may slightly alter the elbow orientation)",
        default=False
    )

    def invoke(self, context, _event):
        self.sm = SceneManipulator(context.scene)
        return super().invoke(context, _event)
    
    def execute(self, context):
        try:
           self.sm.import_animation(self.filepath)
           if self.setup_ctrls:
               self.sm.setup_controllers()
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class IMPORT_OT_bf2_mesh(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_import.mesh"
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

    def invoke(self, context, _event):
        self.sm = SceneManipulator(context.scene)
        return super().invoke(context, _event)

    def execute(self, context):
        mod_path = context.preferences.addons[__package__].preferences.mod_directory
        try:
            self.sm.import_mesh(self.filepath, geom=self.geom, lod=self.lod, mod_path=mod_path)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class IMPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "bf2_import.submenu"
    bl_label = "Battlefield 2"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        self.layout.operator(IMPORT_OT_bf2_skeleton.bl_idname, text="Skeleton (.ske)")
        self.layout.operator(IMPORT_OT_bf2_animation.bl_idname, text="Animation (.baf)")
        self.layout.operator(IMPORT_OT_bf2_mesh.bl_idname, text="Mesh (.bundledmesh, .skinnedmesh)")


def menu_func_import(self, context):
    self.layout.menu(IMPORT_MT_bf2_submenu.bl_idname, text="BF2")

# -------------------------- Export --------------------------


class BoneExportCollection(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="")
    included: BoolProperty(name="", default=True)


class EXPORT_OT_bf2_animation(bpy.types.Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "bf2_export.animation"
    bl_label = "Export Animation"

    filename_ext = ".baf"

    filter_glob: StringProperty(
        default="*.baf",
        options={'HIDDEN'},
        maxlen=1024
    )

    bones_for_export: CollectionProperty(type=BoneExportCollection)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Bones to export:")
        for prop in self.bones_for_export:
            layout.prop(prop, "included", text=prop["name"])

    def invoke(self, context, _event):
        self.sm = SceneManipulator(context.scene)

        try:
            bones = self.sm.get_bones_for_export()
        except Exception as e:
            print(e)
            bones = dict()

        self.bones_for_export.clear()
        for bone_name, inc in bones.items():
            item = self.bones_for_export.add()
            item.name = bone_name
            item.included = inc

        return super().invoke(context, _event)

    def execute(self, context):

        bones_to_export = list()
        for item in self.bones_for_export:
            if item.included:
                bones_to_export.append(item.name)

        try:
           self.sm.export_animation(self.filepath, bones_to_export=bones_to_export)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


class EXPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "bf2_export.submenu"
    bl_label = "Battlefield 2"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        self.layout.operator(EXPORT_OT_bf2_animation.bl_idname, text="Animation (.baf)")


def menu_func_export(self, context):
    self.layout.menu(EXPORT_MT_bf2_submenu.bl_idname, text="BF2")

# ----------------------------------------------------------

class BF2AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mod_directory: StringProperty (
            name="BF2 mod directory",
            subtype="DIR_PATH"
        )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'mod_directory', expand=True)

# ----------------------------------------------------------

def register():
    bpy.utils.register_class(BF2AddonPreferences)
    bpy.utils.register_class(BoneExportCollection)

    bpy.utils.register_class(IMPORT_OT_bf2_skeleton)
    bpy.utils.register_class(IMPORT_OT_bf2_mesh)
    bpy.utils.register_class(IMPORT_OT_bf2_animation)
    bpy.utils.register_class(IMPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    bpy.utils.register_class(EXPORT_OT_bf2_animation)
    bpy.utils.register_class(EXPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_MT_bf2_submenu)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_MT_bf2_submenu)
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation)
    bpy.utils.unregister_class(IMPORT_OT_bf2_mesh)
    bpy.utils.unregister_class(IMPORT_OT_bf2_skeleton)

    bpy.utils.unregister_class(BoneExportCollection)
    bpy.utils.unregister_class(BF2AddonPreferences)
