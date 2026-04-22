import bpy # type: ignore

from bpy.props import PointerProperty # type: ignore
from .utils import RegisterFactory
from ..core.tools.anim_utils import update_nla_setup, nla_tweak_enable, nla_tweak_disable

def _get_active_nla_track(context):
    if not context.object:
        return
    anim_data = context.object.animation_data
    if not anim_data:
        return
    return anim_data.nla_tracks.active

class DOPESHEET_OT_bf2_weapon_anim_tweak_enable(bpy.types.Operator):
    bl_idname = "bf2.weapon_anim_tweak_enable"
    bl_label = "Tweak Action"
    bl_description = "A shortcut for enabling tweaking mode in NLA editor.\n\nBecause of the NLA stack, the action can't be edited normally. Also you will not be able to change action whilst in editing mode"
    TRACK_NAME = '3P_WEAPON'

    def execute(self, context):
        if self.is_active(context):
            nla_tweak_disable(context)
        else:
            nla_tweak_enable(context, context.active_action, track_name=self.TRACK_NAME)
        return {'FINISHED'}

    @classmethod
    def is_active(cls, context):
        if not context.scene.is_nla_tweakmode:
            return False
        track = _get_active_nla_track(context)
        if not track or cls.TRACK_NAME != track.name:
            return False
        return True

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.active_action and
                context.active_action.bf2_soldier_action and
                context.object.animation_data and
                cls.TRACK_NAME in context.object.animation_data.nla_tracks)

class DOPESHEET_PT_bf2_action(bpy.types.Panel):
    bl_region_type = 'UI'
    bl_label = "Battlefield 2"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_category = "Action"

    @classmethod
    def poll(cls, context):
        return bool(context.active_action)

    def draw(self, context):
        action = context.active_action
        self.layout.use_property_split = True
        self.layout.prop(action, "bf2_soldier_action")
        self.layout.operator(DOPESHEET_OT_bf2_weapon_anim_tweak_enable.bl_idname,
                             emboss=True, depress=DOPESHEET_OT_bf2_weapon_anim_tweak_enable.is_active(context))

def _on_soldier_action_update(action, context):
    if context.scene.is_nla_tweakmode:
        return
    update_nla_setup(context, action)

def _on_action_change():
    if bpy.context.scene.is_nla_tweakmode:
        return
    update_nla_setup(bpy.context)

_msgbus_owner = object()

def _register_message_bus() -> None:
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.AnimData, "action"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_action_change,
        options={"PERSISTENT"},
    )

@bpy.app.handlers.persistent
def _on_blendfile_load_post(none, other_none) -> None:
    _register_message_bus()

def _unregister_message_bus() -> None:
    bpy.msgbus.clear_by_owner(_msgbus_owner)

def init(rc : RegisterFactory):
    rc.reg_prop(bpy.types.Action, 'bf2_soldier_action',
        PointerProperty(
            type=bpy.types.Action,
            name="Soldier action",
            description="Soldier animation to link with this animation (3P only)\n\nThis will set up a special NLA stack that combines both actions and also update it each time the action is changed",
            update=_on_soldier_action_update
        ) # type: ignore
    )

    rc.reg_class(DOPESHEET_PT_bf2_action)
    rc.reg_fun(
        on_register=_register_message_bus,
        on_unregister=_unregister_message_bus
    )

    rc.add_menu(bpy.app.handlers.load_post, _on_blendfile_load_post)
    rc.reg_class(DOPESHEET_OT_bf2_weapon_anim_tweak_enable)

register, unregister = RegisterFactory.create(init)
