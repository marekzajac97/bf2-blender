import bpy # type: ignore

from bpy.props import PointerProperty # type: ignore
from .utils import RegisterFactory

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

def _on_action_change() -> None:
    obj = bpy.context.object
    if not obj or not obj.animation_data:
        return
    action = obj.animation_data.action
    if not action:
        return

    # cleanup
    soldier_track = obj.animation_data.nla_tracks.get('3P_SOLDIER')
    weapon_track = obj.animation_data.nla_tracks.get('3P_WEAPON')
    if soldier_track:
        obj.animation_data.nla_tracks.remove(soldier_track)
    if weapon_track:
        obj.animation_data.nla_tracks.remove(weapon_track)
    obj.animation_data.action_influence = 1

    soldier_action = action.bf2_soldier_action
    if not soldier_action:
        return

    obj.animation_data.action_influence = 0
    weapon_track = obj.animation_data.nla_tracks.new()
    soldier_track = obj.animation_data.nla_tracks.new() # IMPORTANT: soldier must be on top
    weapon_track.name = '3P_WEAPON'
    soldier_track.name = '3P_SOLDIER'
    weapon_track.strips.new(action.name, int(action.frame_start), action)
    strip = soldier_track.strips.new(soldier_action.name, int(action.frame_start), soldier_action)

    action_len = action.frame_end - action.frame_start
    soldier_len = soldier_action.frame_end - soldier_action.frame_start
    if int(action_len) == 0 or int(soldier_len) == 0:
        return
    else:
        strip.repeat = action_len / soldier_len

_msgbus_owner = object()

def _register_message_bus() -> None:
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.AnimData, "action"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_action_change,
        options={"PERSISTENT"},
    )

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.Action, "bf2_soldier_action"),
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
            description="Soldier animation to apply as a secondary NLA layer when viewing/editing this action (3P only)"
        ) # type: ignore
    )

    rc.reg_class(DOPESHEET_PT_bf2_action)
    rc.reg_fun(
        on_register=_register_message_bus,
        on_unregister=_unregister_message_bus
    )

    rc.add_menu(bpy.app.handlers.load_post, _on_blendfile_load_post)

register, unregister = RegisterFactory.create(init)
