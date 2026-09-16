import bpy # type: ignore

from bpy.props import PointerProperty, StringProperty # type: ignore
from .utils import RegisterFactory
from ..core.tools.anim_utils import update_nla_setup

def _get_bf2_bone_id(armature, bone_name):
    if not armature or not bone_name:
        return -1
    bf2_bones = list(armature.get('bf2_bones') or [])
    if bone_name not in bf2_bones:
        return -1
    return bf2_bones.index(bone_name)

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
        col = self.layout.column()
        col.enabled = bool(action.bf2_soldier_action)
        armature = context.object if context.object and context.object.type == 'ARMATURE' else None
        if armature:
            col.prop_search(action, "bf2_ignore_mother_orientation", armature.data, "bones")
        else:
            col.prop(action, "bf2_ignore_mother_orientation")
        # bone_id = _get_bf2_bone_id(armature, action.bf2_ignore_mother_orientation)
        # col.label(text=f"Ignore mother orientation value: {bone_id}")

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

    rc.reg_prop(bpy.types.Action, 'bf2_ignore_mother_orientation',
        StringProperty(
            name="Cutoff bone",
            description="This bone including its children will be driven by the current (weapon) action, while every parent will be driven by the soldier action. Leave unset to let the weapon action drive every bone it animates.\n\nThis is the equivalent of the `animationManager.ignoreMotherOrientation` from the BF2's AnimationSystem",
            update=_on_soldier_action_update
        ) # type: ignore
    )

    rc.reg_class(DOPESHEET_PT_bf2_action)
    rc.reg_fun(
        on_register=_register_message_bus,
        on_unregister=_unregister_message_bus
    )

    rc.add_menu(bpy.app.handlers.load_post, _on_blendfile_load_post)

register, unregister = RegisterFactory.create(init)
