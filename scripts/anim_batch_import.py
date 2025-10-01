# Change any settings you'd like here

SKELETON_NAME = '3p_setup'
IMPORT_DIR = 'Objects/Soldiers/Common/Animations/3P/'
ANIM_LIST = [
    '3p_crouchStill',
    '3p_stand',
    '3p_runForward',
]

SETUP_CONTROLLERS = True

# change hierarchy after controllers setup (optional) for example:
# BONE_HIERARCHY = {
#     'mesh1': ['mesh2', 'mesh4', 'mesh5', 'mesh6']
#     'mesh4': 'mesh3'
# }

BONE_HIERARCHY = {} 

# --------------------------------------------------------

import bpy
from os import path
from bl_ext.user_default.io_scene_bf2 import (
    get_mod_dir,
    import_animation,
    setup_anim_controllers,
    reparent_bones
)

MOD_PATH = get_mod_dir(bpy.context)
ske = bpy.data.objects[SKELETON_NAME]
if ske.animation_data is None:
    ske.animation_data_create()

for anim in ANIM_LIST:
    action = bpy.data.actions.new(anim)
    ske.animation_data.action = action
    import_animation(bpy.context, ske, path.join(MOD_PATH, IMPORT_DIR, anim + '.baf'))
    action.use_fake_user = True
    if hasattr(action, 'use_frame_range'):
        action.use_frame_range = True

if SETUP_CONTROLLERS:
    setup_anim_controllers(bpy.context, ske)

for parent, children in BONE_HIERARCHY.items():
    reparent_bones(bpy.context, ske, [f'{cb}.CTRL' for cb in children], f'{parent}.CTRL')
