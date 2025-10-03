import bpy # type: ignore
import os
import traceback
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import ExportHelper, ImportHelper, poll_file_object_drop

from ...core.exceptions import ImportException, ExportException # type: ignore
from ...core.animation import import_animation, export_animation, get_bones_for_export, save_bones_for_export
from ...core.skeleton import find_active_skeleton
from ...core.anim_utils import SUPPORTS_ACTION_SLOTS, AnimationContext

# -------------------------- Import --------------------------

class IMPORT_OT_bf2_animation(bpy.types.Operator, ImportHelper):
    bl_description = "Battlefield 2 animation"
    bl_label = "Import animation"
    bl_idname= "bf2_animation.import"
    filename_ext = ".baf"

    filter_glob: StringProperty(default="*.baf", options={'HIDDEN'}) # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN'}) # type: ignore

    append_action: BoolProperty(
        name="To active Action",
        description="Import animations into the currently active Action (in a sequence), otherwise import each animation file into its own Action",
        default=True
    ) # type: ignore

    setup_ctrls: BoolProperty(
        name="Setup Controllers",
        description="Create basic animation helper bones and setup IKs, (NOTE: IKs may break or alter the animation in some way)",
        default=False
    ) # type: ignore

    insert_at_frame: IntProperty(
        name="Insert at frame",
        description="Frame index to import the keyframes",
        default=0
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No active skeleton found")
        return find_active_skeleton(context) is not None

    def invoke(self, context, _event):
        self.rig = find_active_skeleton(context)
        if self.rig.animation_data is None:
            self.rig.animation_data_create()
        return super().invoke(context, _event)

    def execute(self, context):
        try:
            dirpath = os.path.dirname(self.filepath)
            frame = self.insert_at_frame
            for file in self.files:
                filepath = os.path.join(dirpath, file.name)
                if self.append_action:
                    import_animation(context, self.rig, filepath, insert_at_frame=frame)
                    frame += context.scene.frame_end - frame + 1
                    # TODO: add a marker
                else:
                    action = bpy.data.actions.new(os.path.splitext(file.name)[0])
                    self.rig.animation_data.action = action
                    import_animation(context, self.rig, filepath, insert_at_frame=self.insert_at_frame)
                    action.use_fake_user = True # prevent Actions from getting deleted
                    action.use_frame_range = True
            if self.append_action:
                context.scene.frame_start = self.insert_at_frame
            if self.setup_ctrls:
                context.view_layer.objects.active = self.rig
                bpy.ops.bf2_animation.anim_ctrl_setup_begin('INVOKE_DEFAULT')
        except ImportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        return {'FINISHED'}  


def multi_action_update(self, context):
    if self.multi_action:
        context.space_data.params.filename = ''

# -------------------------- Export --------------------------

class SelectableItemCollection(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="") # type: ignore
    included: BoolProperty(name="", default=True) # type: ignore

class EXPORT_OT_bf2_animation(bpy.types.Operator, ExportHelper):
    bl_description = "Battlefield 2 animation file"
    bl_label = "Export Animation"
    bl_idname = "bf2_animation.export"
    bl_options = {'PRESET'}

    filename_ext = ".baf"
    filter_glob: StringProperty(default="*.baf", options={'HIDDEN'}) # type: ignore

    multi_action: BoolProperty(
        name="Actions to export:",
        description="[requires Blender 4.4] Export multiple Actions into separate animation files (using Action frame range), otherwise export only the currently active Action (using Scene frame range)",
        default=False,
        update=multi_action_update
    ) # type: ignore

    space : EnumProperty(
        name="Space",
        description="Space in which bone transformations are evaluated",
        default=0,
        items=[
            ('OBJECT', "Object", "Export bones relative to the Armature object", 0),
            ('WORLD', "World", "Export bones relative to the World origin", 1),
        ]
    ) # type: ignore

    actions_for_export: CollectionProperty(type=SelectableItemCollection) # type: ignore

    bones_for_export: CollectionProperty(type=SelectableItemCollection) # type: ignore

    def _export(self, context, file, fstart=None, fend=None):
        export_animation(context, self.rig, file,
                         bones_to_export=self._selected_bones,
                         world_space=self.space == 'WORLD',
                         fstart=fstart, fend=fend)

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No active skeleton found")
        return find_active_skeleton(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'space', text="Space:")
        header, body = layout.panel("BF2_PT_actions_for_export", default_closed=True)
        header.prop(self, 'multi_action')
        header.enabled = SUPPORTS_ACTION_SLOTS
        if body:
            for prop in self.actions_for_export:
                body.enabled = header.enabled and self.multi_action
                body.prop(prop, "included", text=prop["name"])
        header, body = layout.panel("BF2_PT_bones_for_export", default_closed=False)
        header.label(text="Bones to export:")
        if body:
            for prop in self.bones_for_export:
                body.prop(prop, "included", text=prop["name"])

    def invoke(self, context, _event):
        self.rig = find_active_skeleton(context)
        if self.rig.animation_data is None:
            self.rig.animation_data_create()

        if not SUPPORTS_ACTION_SLOTS:
            self.multi_action = False
        else:
            for action in bpy.data.actions:
                for slot in action.slots:
                    if slot.identifier != 'OB' + self.rig.name:
                        continue
                    item = self.actions_for_export.add()
                    item.name = action.name
                    item.included = True

        if self.multi_action:
            self.filepath = ''

        try:
            bones = get_bones_for_export(self.rig)
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
        self._selected_bones = [i.name for i in self.bones_for_export if i.included]
        save_bones_for_export(self.rig, {i.name: i.included for i in self.bones_for_export})
        try:
            if not self.multi_action:
                self._export(context, self.filepath)
            else:
                with AnimationContext(context.scene, self.rig):
                    if not os.path.isdir(self.filepath):
                        raise ExportException("For batch export select a directory, not a file!")
                    selected_actions = [i.name for i in self.actions_for_export if i.included]
                    for action_name in selected_actions:
                        action = bpy.data.actions[action_name]
                        self.rig.animation_data.action = action
                        self.rig.animation_data.action_slot = action.slots['OB' + self.rig.name]
                        frame_start, frame_end = action.frame_range
                        fpath = os.path.join(self.filepath, action.name + '.baf')
                        self._export(context, fpath, fstart=int(frame_start), fend=int(frame_end))
        except ExportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}


class IMPORT_EXPORT_FH_baf(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_baf"
    bl_label = "BF2 Animation"
    bl_import_operator = IMPORT_OT_bf2_animation.bl_idname
    bl_export_operator = EXPORT_OT_bf2_animation.bl_idname
    bl_file_extensions = ".baf"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


FILE_DESC = "Animation (.baf)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)

def register():
    dump_presets()
    bpy.utils.register_class(SelectableItemCollection)
    bpy.utils.register_class(IMPORT_OT_bf2_animation)
    bpy.utils.register_class(EXPORT_OT_bf2_animation)
    bpy.utils.register_class(IMPORT_EXPORT_FH_baf)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_baf)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation)
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation)
    bpy.utils.unregister_class(SelectableItemCollection)

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
