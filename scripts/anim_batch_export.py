# Change any settings you'd like here

SKELETON_NAME = '3p_setup'
EXPORT_DIR = 'Objects/Soldiers/Common/Animations/3P/'

# --------------------------------------------------------

import bpy
from os import path
from bl_ext.user_default.io_scene_bf2 import (
    get_mod_dir,
    export_animation
)

MOD_PATH = get_mod_dir(bpy.context)
ske = bpy.data.objects[SKELETON_NAME]
if ske.animation_data is None:
    ske.animation_data_create()

for action in bpy.data.actions:
    for slot in action.slots:
        if slot.name_display == ske.name:
            ske.animation_data.action = action
            ske.animation_data.action_slot = slot
            frame_start = bpy.context.scene.frame_start
            frame_end = bpy.context.scene.frame_end
            if hasattr(action, 'frame_start'):
                frame_start = int(action.frame_start)
            if hasattr(action, 'frame_end'):
                frame_end = int(action.frame_end)
            export_animation(bpy.context, ske, path.join(MOD_PATH, EXPORT_DIR, action.name + '.baf'), fstart=frame_start, fend=frame_end)
