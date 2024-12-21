import bpy # type: ignore
from bpy.props import StringProperty, EnumProperty, BoolProperty # type: ignore
from ..core.bf2.bf2_engine import BF2_OBJECT_TEMPLATE_TYPES

BF2_OBJECTS_ENUM = [(n, n, "", i) for i, n in enumerate(BF2_OBJECT_TEMPLATE_TYPES)]

def on_bf2_obj_type_update(self, context):
    self['bf2_object_type'] = self.bf2_object_type_enum

def on_bf2_obj_type_manual_mode_update(self, context):
    if not self.bf2_object_type_manual_mode:
        self['bf2_object_type'] = self.bf2_object_type_enum

class OBJECT_PT_bf2_object(bpy.types.Panel):
    bl_label = "Battlefield 2"
    bl_idname = "OBJECT_PT_bf2_object"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="BF2 ObjectTemplate Type:")
        
        if context.object.bf2_object_type_manual_mode:
            row.prop(context.object, "bf2_object_type", text="")
            ico = 'UNLOCKED'
        else:
            row.prop(context.object, "bf2_object_type_enum", text="")
            ico = 'LOCKED'
        row.prop(context.object, "bf2_object_type_manual_mode", text="", icon_only=True, icon=ico)

def register():
    bpy.types.Object.bf2_object_type = StringProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents",
            default = 'SimpleObject'
        ) # type: ignore

    bpy.types.Object.bf2_object_type_enum = EnumProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents",
            default=BF2_OBJECT_TEMPLATE_TYPES.index('SimpleObject'),
            items=BF2_OBJECTS_ENUM,
            update=on_bf2_obj_type_update
        ) # type: ignore

    bpy.types.Object.bf2_object_type_manual_mode = BoolProperty(
            name="Lock selection",
            description="Type-in the ObjectTemplate type manually or choose from a list of valid types",
            default=True,
            update=on_bf2_obj_type_manual_mode_update
        ) # type: ignore

    bpy.utils.register_class(OBJECT_PT_bf2_object)

def unregister():
    bpy.utils.unregister_class(OBJECT_PT_bf2_object)
    del bpy.types.Object.bf2_object_type_manual_mode
    del bpy.types.Object.bf2_object_type_enum
    del bpy.types.Object.bf2_object_type
