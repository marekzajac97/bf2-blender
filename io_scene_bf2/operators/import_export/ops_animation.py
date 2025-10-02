import bpy # type: ignore
import os
import traceback
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import ExportHelper, ImportHelper, poll_file_object_drop

from ...core.exceptions import ImportException, ExportException # type: ignore
from ...core.animation import import_animation, export_animation, get_bones_for_export, save_bones_for_export
from ...core.skeleton import find_active_skeleton

def _cannot_batch(what):
    for addon in bpy.context.preferences.addons:
        if addon.module.split('.')[-1] == 'action_to_scene_range':
            break
    else:
        return "Batch export is only supported with 'Action to Scene Range' add-on, get it from extensions.blender.org"
    if bpy.app.version[0] >= 4 and bpy.app.version[0] >= 4:
        return ''
    else:
        return "Batch export is only supported with Blender 4.4 or above"

# -------------------------- Import --------------------------

class AnimationImportBase:
    filename_ext = ".baf"
    filter_glob: StringProperty(default="*.baf", options={'HIDDEN'}) # type: ignore

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

    def _import(self, context, file):
        import_animation(context, self.rig, file, insert_at_frame=self.insert_at_frame)

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No active skeleton found")
        if find_active_skeleton(context) is None:
            return False
        return cls._poll(context)

    def invoke(self, context, _event):
        self.rig = find_active_skeleton(context)
        if self.rig.animation_data is None:
            self.rig.animation_data_create()
        return self._invoke(context, _event)

    def execute(self, context):
        try:
            self._execute(context)
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


class IMPORT_OT_bf2_animation(bpy.types.Operator, AnimationImportBase, ImportHelper):
    bl_description = "Import Battlefield 2 animation file into active Action"
    bl_label = "Import animation"
    bl_idname= "bf2_animation.import"

    @classmethod
    def _poll(cls, context):
        return True

    def _invoke(self, context, _event):
        return ImportHelper.invoke(self, context, _event)

    def _execute(self, context):
        self._import(context, self.filepath)


class IMPORT_OT_bf2_animation_batch(bpy.types.Operator, AnimationImportBase):
    bl_description = "Import Battlefield 2 animation files into separate Actions"
    bl_label = "Import animations"
    bl_idname= "bf2_animation.import_batch"

    filepath: StringProperty(subtype='FILE_PATH') # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement) # type: ignore

    @classmethod
    def _poll(cls, context):
        msg = _cannot_batch('import')
        cls.poll_message_set(msg)
        return not msg

    def _invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _execute(self, context):
        dirpath = os.path.dirname(self.filepath)
        for file in self.files:
            filepath = os.path.join(dirpath, file.name)
            action = bpy.data.actions.new(os.path.splitext(file.name)[0])
            self.rig.animation_data.action = action
            self._import(context, filepath)
            action.use_fake_user = True
            if hasattr(action, 'use_frame_range'):
                action.use_frame_range = True
        if self.setup_ctrls:
            context.view_layer.objects.active = self.rig
            bpy.ops.bf2_animation.anim_ctrl_setup_begin('INVOKE_DEFAULT')


# -------------------------- Export --------------------------


class BoneExportCollection(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="") # type: ignore
    included: BoolProperty(name="", default=True) # type: ignore

class AnimationExportBase:
    filename_ext = ".baf"

    filter_glob: StringProperty(
        default="*.baf",
        options={'HIDDEN'},
        maxlen=1024
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

    bones_for_export: CollectionProperty(type=BoneExportCollection) # type: ignore

    def _export(self, context, file, fstart=None, fend=None):
        export_animation(context, self.rig, file,
                         bones_to_export=self._selected_bones,
                         world_space=self.space == 'WORLD',
                         fstart=fstart, fend=fend)

    def _draw_bone_list(self, context):
        layout = self.layout
        header, body = layout.panel("BF2_PT_bones_for_export", default_closed=False)
        header.label(text="Bones to export:")
        if body:
            for prop in self.bones_for_export:
                layout.prop(prop, "included", text=prop["name"])

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No active skeleton found")
        if find_active_skeleton(context) is None:
            return False
        return cls._poll(context)

    def invoke(self, context, _event):
        self.rig = find_active_skeleton(context)
        if self.rig.animation_data is None:
            self.rig.animation_data_create()
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

        return self._invoke(context, _event)

    def execute(self, context):
        self._selected_bones = [i.name for i in self.bones_for_export if i.included]
        save_bones_for_export(self.rig, {i.name: i.included for i in self.bones_for_export})
        try:
           self._execute(context)
        except ExportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        self.report({"INFO"}, 'Export complete')
        return {'FINISHED'}


class EXPORT_OT_bf2_animation(bpy.types.Operator, AnimationExportBase, ExportHelper):
    bl_description = "Export active Action to a Battlefield 2 animation file"
    bl_label = "Export Animation"
    bl_idname = "bf2_animation.export"
    bl_options = {'PRESET'}

    @classmethod
    def _poll(cls, context):
        return True

    def draw(self, context):
        self.layout.prop(self, 'space', text="Space:")
        self._draw_bone_list(context)

    def _invoke(self, context, _event):
        return ExportHelper.invoke(self, context, _event)

    def _execute(self, context):
        self._export(context, self.filepath)


class EXPORT_OT_bf2_animation_batch(bpy.types.Operator, AnimationExportBase):
    bl_description = "Export Actions to a Battlefield 2 animation files"
    bl_label = "Export Animations"
    bl_idname = "bf2_animation.export_batch"
    # TODO: preset

    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    actions_for_export: CollectionProperty(type=BoneExportCollection) # type: ignore

    @classmethod
    def _poll(cls, context):
        msg = _cannot_batch('export')
        cls.poll_message_set(msg)
        return not msg

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'space', text="Space:")
        header, body = layout.panel("BF2_PT_actions_for_export", default_closed=False)
        header.label(text="Actions to export:")
        if body:
            for prop in self.actions_for_export:
                layout.prop(prop, "included", text=prop["name"])
        self._draw_bone_list(context)

    def _invoke(self, context, _event):
        for action in bpy.data.actions:
            for slot in action.slots:
                if slot.identifier == 'OB' + self.rig.name:
                    item = self.actions_for_export.add()
                    item.name = action.name
                    item.included = True
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _execute(self, context):
        if os.path.isfile(self.filepath):
            raise ExportException("For batch export select a directory, not a file!")
        selected_actions = [i.name for i in self.actions_for_export if i.included]
        for action_name in selected_actions:
            action = bpy.data.actions[action_name]
            self.rig.animation_data.action = action
            self.rig.animation_data.action_slot = action.slots['OB' + self.rig.name]
            frame_start = bpy.context.scene.frame_start
            frame_end = bpy.context.scene.frame_end
            if hasattr(action, 'frame_start'):
                frame_start = int(action.frame_start)
            if hasattr(action, 'frame_end'):
                frame_end = int(action.frame_end)
            fpath = os.path.join(self.filepath, action.name + '.baf')
            self._export(context, fpath, fstart=frame_start, fend=frame_end)


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
    layout.operator(IMPORT_OT_bf2_animation_batch.bl_idname, text=FILE_DESC + " [BATCH]")

def draw_export(layout):
    layout.operator(EXPORT_OT_bf2_animation.bl_idname, text=FILE_DESC)
    layout.operator(EXPORT_OT_bf2_animation_batch.bl_idname, text=FILE_DESC + " [BATCH]")

def register():
    dump_presets()
    bpy.utils.register_class(BoneExportCollection)
    bpy.utils.register_class(IMPORT_OT_bf2_animation)
    bpy.utils.register_class(IMPORT_OT_bf2_animation_batch)
    bpy.utils.register_class(EXPORT_OT_bf2_animation)
    bpy.utils.register_class(EXPORT_OT_bf2_animation_batch)
    bpy.utils.register_class(IMPORT_EXPORT_FH_baf)

def unregister():
    bpy.utils.unregister_class(IMPORT_EXPORT_FH_baf)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation_batch)
    bpy.utils.unregister_class(EXPORT_OT_bf2_animation)
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation_batch)
    bpy.utils.unregister_class(IMPORT_OT_bf2_animation)
    bpy.utils.unregister_class(BoneExportCollection)

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
