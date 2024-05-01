import bpy
import os
import traceback
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ...core.animation import import_animation, export_animation, get_bones_for_export
from ...core.skeleton import find_active_skeleton

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
        return find_active_skeleton() is not None

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
    bl_options = {'PRESET'}

    filename_ext = ".baf"

    filter_glob: StringProperty(
        default="*.baf",
        options={'HIDDEN'},
        maxlen=1024
    )

    bones_for_export: CollectionProperty(type=BoneExportCollection)

    @classmethod
    def poll(cls, context):
        return find_active_skeleton() is not None

    def draw(self, context):
        layout = self.layout

        layout.label(text="Bones to export:")
        for prop in self.bones_for_export:
            layout.prop(prop, "included", text=prop["name"])

    def invoke(self, context, _event):

        try:
            bones = get_bones_for_export()
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
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}

FILE_DESC = "Animation (.baf)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def register():
    dump_presets()
    bpy.utils.register_class(BoneExportCollection)
    bpy.utils.register_class(IMPORT_OT_bf2_animation)
    bpy.utils.register_class(EXPORT_OT_bf2_animation)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation)
    bpy.utils.unregister_class(BoneExportCollection)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation)

def dump_presets(force=False):
    op_presets = os.path.join("presets", "operator", EXPORT_OT_bf2_animation.bl_idname)
    preset_dir = bpy.utils.user_resource('SCRIPTS', path=op_presets, create=True)
    for preset_name, bone_list in ANIM_EXPORT_DEFAULT_PRESETS:
        preset_file = os.path.join(preset_dir, f'{preset_name}.py')
        try:
            if os.path.isfile(preset_file) and not force:
                return
            with open(preset_file, 'w') as f:
                f.write("import bpy\n")
                f.write("op = bpy.context.active_operator\n\n")
                f.write("BONE_LIST = {}\n".format(bone_list))
                f.write("for item in op.bones_for_export:\n")
                f.write("    if item.name in BONE_LIST:\n")
                f.write("        item.included = True\n")
                f.write("    else:\n")
                f.write("        item.included = False\n")
        except OSError as e:
            print(e)

ANIM_EXPORT_DEFAULT_PRESETS = [
        ('1P', ['Camerabone', 'torus',
                'L_collar', 'L_arm', 'L_elbowMiddleJoint', 'L_lowerarm', 'L_ullna', 'L_wrist',
                'L_thumb_1', 'L_thumb_2', 'L_thumb_3', 'L_thumb_END',
                'L_point_1', 'L_point_2', 'L_point_3', 'L_point_END',
                'L_ring_1', 'L_ring_2', 'L_ring_3', 'L_ring_END',
                'L_index_1', 'L_index_2', 'L_index_3', 'L_index_END',
                'L_pink_1', 'L_pink_2', 'L_pink_3', 'L_pink_END',
                'R_collar', 'R_arm', 'R_elbowJoint', 'R_lowerarm', 'R_ullna', 'R_wrist',
                'R_thumb_1', 'R_thumb_2', 'R_thumb_3', 'R_thumb_END',
                'R_point_1', 'R_point_2', 'R_point_3', 'R_point_END',
                'R_ring_1', 'R_ring_2', 'R_ring_3', 'R_ring_END',
                'R_index_1', 'R_index_2', 'R_index_3', 'R_index_END',
                'R_pink_1', 'R_pink_2', 'R_pink_3', 'R_pink_END']),

        ('3P', ['root', 'spine2', 'spine3', 'torso',
                'left_collar', 'left_shoulder', 'left_elbow', 'left_low_arm', 'joint19', 'left_wrist1', 'L_wrist',
                'left_ring1', 'left_ring2', 'left_ring3', 'left_index1', 'left_index2', 'left_index3',
                'left_thumb1', 'left_thumb2', 'left_thumb3', 'right_collar', 'right_shoulder', 'right_elbow',
                'right_low_arm', 'right_ullna', 'R_wrist', 'right_ring1', 'right_ring2', 'right_ring3', 'right_index1',
                'right_index2', 'right_index3', 'right_thumb1', 'right_thumb2', 'right_thumb3', 'joint20', 'neck',
                'head', 'chin', 'chin_END', 'left_lower_lip', 'right_lower_lip', 'left_eye', 'right_eye',
                'right_upper_lip', 'left_upper_lip', 'left_eyebrow', 'right_eyebrow', 'left_mouht',
                'right_mouth', 'right_eyelid', 'left_eyelid', 'left_cheek', 'right_cheek',
                'left_upperleg', 'left_knee', 'left_lowerleg', 'left_foot',
                'left_ball', 'right_upperleg', 'right_knee', 'right_lowerleg',
                'right_foot', 'right_ball', 'mesh16', 'mesh14', 'mesh15',
                'mesh10', 'mesh9', 'mesh11', 'mesh12', 'mesh13']),

        ('3P_WEAPON', ['root', 'spine2', 'spine3', 'torso',
                       'left_collar', 'left_shoulder', 'left_elbow', 'left_low_arm', 'joint19', 'left_wrist1', 'L_wrist',
                       'left_ring1', 'left_ring2', 'left_ring3', 'left_index1', 'left_index2', 'left_index3',
                       'left_thumb1', 'left_thumb2', 'left_thumb3', 'right_collar', 'right_shoulder', 'right_elbow',
                       'right_low_arm', 'right_ullna', 'R_wrist', 'right_ring1', 'right_ring2', 'right_ring3', 'right_index1',
                       'right_index2', 'right_index3', 'right_thumb1', 'right_thumb2', 'right_thumb3', 'joint20', 'neck',
                       'head', 'chin', 'chin_END', 'left_lower_lip', 'right_lower_lip', 'left_eye', 'right_eye',
                       'right_upper_lip', 'left_upper_lip', 'left_eyebrow', 'right_eyebrow', 'left_mouht',
                       'right_mouth', 'right_eyelid', 'left_eyelid', 'left_cheek', 'right_cheek',
                       'mesh16', 'mesh14', 'mesh15',]),

        ('3P_SOLDIER', ['root', 'left_upperleg', 'left_knee', 'left_lowerleg', 'left_foot',
                        'left_ball', 'right_upperleg', 'right_knee', 'right_lowerleg',
                        'right_foot', 'right_ball', 'mesh10', 'mesh9', 'mesh11', 'mesh12', 'mesh13'])
    ]
