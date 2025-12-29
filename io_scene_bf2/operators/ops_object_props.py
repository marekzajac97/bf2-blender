import bpy # type: ignore
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntVectorProperty # type: ignore
from ..core.bf2.bf2_engine import BF2_OBJECT_TEMPLATE_TYPES
from ..core.utils import next_power_of_2, prev_power_of_2, find_root
from ..core.object_template import parse_geom_type_safe

BF2_OBJECTS_ENUM = [(n, n, "", i) for i, n in enumerate(BF2_OBJECT_TEMPLATE_TYPES)]

LIGHTMAP_MAX_SIZE = 4096
LIGHTMAP_MIN_SIZE = 8

def on_bf2_obj_type_enum_update(self, context):
    self.bf2_object_type = self.bf2_object_type_enum

def on_bf2_obj_type_manual_mode_update(self, context):
    if not self.bf2_object_type_manual_mode:
        self.bf2_object_type = self.bf2_object_type_enum

def set_lm_size(self, value):
    prev_val = tuple(self.bf2_lightmap_size)
    val = list(value)
    for i in range(2):
        link = False
        if val[i] != prev_val[i]:
            link = self.bf2_link_lightmap_size
        if val[i] > prev_val[i]:
            val[i] = next_power_of_2(val[i])
        else:
            val[i] = prev_power_of_2(val[i])
        val[i] = max(LIGHTMAP_MIN_SIZE, val[i])
        val[i] = min(LIGHTMAP_MAX_SIZE, val[i])
        if link:
            val[0] = val[1] = val[i]
    self['bf2_lightmap_size'] = val

def get_lm_size(self):
    return self.get('bf2_lightmap_size', [0, 0]) 

class OBJECT_PT_bf2_object(bpy.types.Panel):
    bl_label = "Battlefield 2"
    bl_idname = "OBJECT_PT_bf2_object"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object
        # root = find_root(context.object)
        # return parse_geom_type_safe(root)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="BF2 ObjectTemplate Type:")

        # TODO: disable if not staticmesh geom child
        if context.object.bf2_object_type_manual_mode:
            row.prop(context.object, "bf2_object_type", text="")
            ico = 'UNLOCKED'
        else:
            row.prop(context.object, "bf2_object_type_enum", text="")
            ico = 'LOCKED'
        row.prop(context.object, "bf2_object_type_manual_mode", text="", icon_only=True, icon=ico)

        # TODO: disable if not staticmesh lod
        row = layout.row()
        row.prop(context.object, "bf2_lightmap_size", text="Lightmap Size")
        col = row.column()
        col.prop(context.object, "bf2_link_lightmap_size", text="", icon='LINKED')

def register():
    bpy.types.Object.bf2_object_type = StringProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents, the value is relevant only for the Geom's children",
            default = 'SimpleObject'
        ) # type: ignore

    bpy.types.Object.bf2_object_type_enum = EnumProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents, the value is relevant only for the Geom's children",
            default=BF2_OBJECT_TEMPLATE_TYPES.index('SimpleObject'),
            items=BF2_OBJECTS_ENUM,
            update=on_bf2_obj_type_enum_update
        ) # type: ignore

    bpy.types.Object.bf2_object_type_manual_mode = BoolProperty(
            name="Lock selection",
            description="Type-in the ObjectTemplate type manually or choose from a list of valid types",
            default=True,
            update=on_bf2_obj_type_manual_mode_update
        ) # type: ignore

    bpy.types.Object.bf2_link_lightmap_size = BoolProperty(
        name="Link Lightmap Size",
        description="Change both X and Y size uniformly",
        default=True
    ) # type: ignore

    bpy.types.Object.bf2_lightmap_size = IntVectorProperty(
        name="Lightmap size",
        description="Lightmap bitmap dimensions for baking & samples generation, the value is relevant only for StaticMesh Lod objects (Geom's immediate child)",
        default=(0, 0),
        size=2,
        set=set_lm_size,
        get=get_lm_size
    ) # type: ignore

    bpy.utils.register_class(OBJECT_PT_bf2_object)

def unregister():
    bpy.utils.unregister_class(OBJECT_PT_bf2_object)
    del bpy.types.Object.bf2_lightmap_size
    del bpy.types.Object.bf2_link_lightmap_size
    del bpy.types.Object.bf2_object_type_manual_mode
    del bpy.types.Object.bf2_object_type_enum
    del bpy.types.Object.bf2_object_type
