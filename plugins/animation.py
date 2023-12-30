import bpy
import traceback
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core.animation import import_animation, export_animation, get_bones_for_export
from ..core.skeleton import find_active_skeleton

# -------------------------- Import --------------------------

class IMPORT_OT_bf2_animation(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_animation.import"
    bl_description = 'Battlefield 2 animation file'
    bl_label = "Import animation"
    filter_glob = StringProperty(default="*.baf", options={'HIDDEN'})

    setup_ctrls: BoolProperty(
        name="Setup Controllers",
        description="Create basic animation helper bones and setup IKs, (NOTE: enabling this may slightly alter the elbow orientation)",
        default=False
    )

    @classmethod
    def poll(cls, context):
        return find_active_skeleton(context) is not None

    def execute(self, context):
        try:
           import_animation(context, self.filepath)
           if self.setup_ctrls:
               bpy.ops.bf2_animation.anim_ctrl_setup_begin('INVOKE_DEFAULT')
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

# -------------------------- Export --------------------------

class BoneExportCollection(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="")
    included: BoolProperty(name="", default=True)


class EXPORT_OT_bf2_animation(bpy.types.Operator, ExportHelper):
    bl_idname = "bf2_animation.export"
    bl_label = "Export Animation"

    filename_ext = ".baf"

    filter_glob: StringProperty(
        default="*.baf",
        options={'HIDDEN'},
        maxlen=1024
    )

    bones_for_export: CollectionProperty(type=BoneExportCollection)

    @classmethod
    def poll(cls, context):
        return find_active_skeleton(context) is not None

    def draw(self, context):
        layout = self.layout

        layout.label(text="Bones to export:")
        for prop in self.bones_for_export:
            layout.prop(prop, "included", text=prop["name"])

    def invoke(self, context, _event):

        try:
            bones = get_bones_for_export(context)
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
           export_animation(context, self.filepath, bones_to_export=bones_to_export)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}


FILE_DESC = "Animation (.baf)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def register():
    bpy.utils.register_class(BoneExportCollection)
    bpy.utils.register_class(IMPORT_OT_bf2_animation)
    bpy.utils.register_class(EXPORT_OT_bf2_animation)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation)
    bpy.utils.unregister_class(BoneExportCollection)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation)
