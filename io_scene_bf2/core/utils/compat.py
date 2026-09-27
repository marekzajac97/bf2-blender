"""Blender API compatibility module"""

import bpy

def set_gn_modifier_input(modifier, identifier, value):
    if hasattr(modifier, 'properties'):
        # Blender 5.2
        getattr(modifier.properties.inputs, identifier).value = value
    else:
        modifier[identifier] = value

SUPPORTS_ACTION_SLOTS = hasattr(bpy.types, "ActionSlot") # Blender 4.4

SUPPORTS_GEOMETRY_NODE_UV_TANGENT = hasattr(bpy.types,'GeometryNodeUVTangent') # Blender 5.0

def iter_action_fcurves(action, slot=None):
    if action is None:
        return
    if not SUPPORTS_ACTION_SLOTS: # < Blender 4.4, use legacy API
        yield from action.fcurves
        return
    # TODO: update to support layers in the future
    slots = action.slots if slot is None else [slot]
    for slot in slots:
        for layer in action.layers:
            for strip in layer.strips:
                channelbag = strip.channelbag(slot)
                if channelbag is None:
                    continue
                yield from channelbag.fcurves

def eevee_id():
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    if 'BLENDER_EEVEE_NEXT' in ids:
        return 'BLENDER_EEVEE_NEXT'
    else:
        return 'BLENDER_EEVEE' # Blender 5.0

def pose_bone_hide(pose_bone, value=True):
    if hasattr(pose_bone, 'hide'):
        pose_bone.hide = value # Blender 5.0 onwards
    else:
        pose_bone.bone.hide = value # Blender 4.5 and earlier
