import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Euler # type: ignore
from bpy.types import Object # type: ignore
from bpy.props import (StringProperty, EnumProperty, BoolProperty, # type: ignore
                       IntProperty, IntVectorProperty, CollectionProperty,
                       PointerProperty, FloatProperty, FloatVectorProperty)
from ..core.bf2.bf2_engine import BF2_OBJECT_TEMPLATE_TYPES
from ..core.utils import next_power_of_2, prev_power_of_2, find_root, show_error
from ..core.object_template import parse_geom_type_safe
from .utils import RegisterFactory

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

# --------------------------------------------------------------------

class BF2_OT_bf2_fence_add_item(bpy.types.Operator):
    bl_idname = "bf2.fence_add_item"
    bl_label = "Add custom segment"

    element_index: IntProperty() # type: ignore

    def execute(self, context):
        bm = bmesh.new()
        try:
            mesh = bpy.context.object.data
            bpy.ops.object.mode_set(mode='EDIT')
            bm.from_mesh(mesh)
            bpy.ops.object.mode_set(mode='OBJECT')
            bm.verts.new()
            bm.to_mesh(mesh)
            item = context.object.bf2_fence_custom_segments.add()
            item.vertex_index = self.element_index
        except Exception:
            raise
        finally:
            bm.free()
        return {'FINISHED'}

class BF2_OT_bf2_fence_remove_item(bpy.types.Operator):
    bl_idname = "bf2.fence_remove_item"
    bl_label = "Remove custom segment"

    element_index: IntProperty() # type: ignore

    def execute(self, context):
        bm = bmesh.new()
        try:
            mesh = bpy.context.object.data
            bpy.ops.object.mode_set(mode='EDIT')
            bm.from_mesh(mesh)
            bpy.ops.object.mode_set(mode='OBJECT')
            bm.verts.ensure_lookup_table()
            bm.verts.remove(bm.verts[self.element_index])
            bm.to_mesh(mesh)
            context.object.bf2_fence_custom_segments.remove(self.element_index)
        except Exception:
            raise
        finally:
            bm.free()
        return {'FINISHED'}

class BF2_OT_bf2_fence_duplicate_item(bpy.types.Operator):
    bl_idname = "bf2.fence_duplicate_item"
    bl_label = "Duplicate custom segment"

    source_index: IntProperty() # type: ignore

    element_index: IntProperty() # type: ignore

    def execute(self, context):
        bpy.ops.bf2.fence_add_item(element_index=self.element_index)
        dst = context.object.bf2_fence_custom_segments[self.element_index]
        src = context.object.bf2_fence_custom_segments[self.source_index]
        dst.instance_ref = src.instance_ref
        dst.instance_size = src.instance_size
        dst.instance_pos = src.instance_pos + 1
        dst.instance_translation = src.instance_translation
        dst.instance_rotation = src.instance_rotation
        return {'FINISHED'}

def on_curve_update(self, context):
    modifier = context.object.modifiers["GenerateFence"]
    input_id = modifier.node_group.interface.items_tree["Curve"].identifier
    if isinstance(self.bf2_fence_curve.data, bpy.types.Curve):
        modifier[input_id] = self.bf2_fence_curve
    else:
        show_error(context, "Object is not a Curve")
        self.bf2_fence_curve = None

def on_collection_update(self, context):
    modifier = context.object.modifiers["GenerateFence"]
    input_id = modifier.node_group.interface.items_tree["Elements"].identifier
    modifier[input_id] = self.bf2_fence_collection

def on_attr_update(self, context, attr):
    context.object.data.attributes[attr].data[self.vertex_index].value = getattr(self, attr)

def on_translation_update(self, context):
    context.object.data.attributes['instance_translation'].data[self.vertex_index].vector = self.instance_translation

def on_rotation_update(self, context):
    rot = Euler(self.instance_rotation, 'XYZ')
    context.object.data.attributes['instance_rotation'].data[self.vertex_index].value = rot.to_quaternion()

def on_is_repeating_update(self, context):
    context.object.data.attributes['instance_pos'].data[self.vertex_index].value = -1 if self.is_repeating else self.instance_pos

class FenceSegmentsCollection(bpy.types.PropertyGroup):
    vertex_index: IntProperty () # type: ignore

    instance_ref: IntProperty (
            name="Collection Index",
            description="Index of the object in the segments collection",
            min=0,
            update=lambda self, context: on_attr_update(self, context, 'instance_ref'),
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

    instance_pos: IntProperty (
            name="Position",
            description="Index determining the position of this segment on the curve",
            min=-1,
            soft_min=0,
            update=lambda self, context: on_attr_update(self, context, 'instance_pos'),
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

    instance_offset: FloatProperty (
            name="Offset",
            description="Offset of the segment on the curve",
            update=lambda self, context: on_attr_update(self, context, 'instance_offset'),
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

    is_repeating: BoolProperty(
            name="Is Repeating",
            description="Repeat this segment on the entire curve",
            default=False,
            update=on_is_repeating_update,
            options=set()  # Remove ANIMATABLE default option.
    ) # type: ignore

    instance_size: FloatProperty (
            name="Size",
            description="Space taken by this segment one the curve, The maximum value of this parameter is taken for all of the repeating segments if there's more than one",
            min=0,
            update=lambda self, context: on_attr_update(self, context, 'instance_size'),
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

    instance_translation: FloatVectorProperty(
            name="Translation",
            description="This segment's translation relative to the its location on the curve",
            default=(0.0, 0.0, 0.0),
            update=on_translation_update,
            subtype='TRANSLATION',
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

    instance_rotation: FloatVectorProperty(
            name="Rotation",
            description="This segment's rotation in Euler (XYZ)",
            default=(0.0, 0.0, 0.0),
            update=on_rotation_update,
            subtype='EULER',
            options=set()  # Remove ANIMATABLE default option.
        ) # type: ignore

class OBJECT_PT_bf2_fence(bpy.types.Panel):
    bl_label = "BF2 Fence Object"
    bl_idname = "OBJECT_PT_bf2_fence"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return (isinstance(context.object.data, bpy.types.Mesh) and
                'GenerateFence' in context.object.modifiers)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        row = col.row()
        row.prop(context.object, 'bf2_fence_curve')
        row = col.row()
        row.prop(context.object, 'bf2_fence_collection')

        total_items = len(context.object.bf2_fence_custom_segments)
        for i, prop in enumerate(context.object.bf2_fence_custom_segments):
            col = layout.column()
            col.use_property_split = True
            header, body = layout.panel(f"BF2_PT_custom_fence_segment_{i}", default_closed=False)
            header.label(text=f'Segment #{i}')
            op = header.operator(BF2_OT_bf2_fence_remove_item.bl_idname, text='', icon='REMOVE')
            op.element_index = i
            op = header.operator(BF2_OT_bf2_fence_duplicate_item.bl_idname, text='', icon='DUPLICATE')
            op.source_index = i
            op.element_index = total_items
            if body:
                body.use_property_split = True
                body.prop(prop, 'instance_ref')
                body.prop(prop, 'is_repeating')
                if not prop.is_repeating:
                    body.prop(prop, 'instance_pos')
                body.prop(prop, 'instance_size')
                body.prop(prop, 'instance_offset')
                body.prop(prop, 'instance_translation')
                body.prop(prop, 'instance_rotation')

        row = layout.row()
        op = row.operator(BF2_OT_bf2_fence_add_item.bl_idname, icon='ADD')
        op.element_index = total_items

# --------------------------------------------------------------------

def init(rc : RegisterFactory):
    rc.reg_prop(Object, 'bf2_object_type',
        StringProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents, the value is relevant only for the Geom's children",
            default = 'SimpleObject'
        ) # type: ignore
    )

    rc.reg_prop(Object, 'bf2_object_type_enum',
        EnumProperty(
            name="BF2 ObjectTemplate Type",
            description="Type of BF2 ObjectTemplate this Blender Object represents, the value is relevant only for the Geom's children",
            default=BF2_OBJECT_TEMPLATE_TYPES.index('SimpleObject'),
            items=BF2_OBJECTS_ENUM,
            update=on_bf2_obj_type_enum_update
        ) # type: ignore
    )

    rc.reg_prop(Object, 'bf2_object_type_manual_mode',
        BoolProperty(
            name="Lock selection",
            description="Type-in the ObjectTemplate type manually or choose from a list of valid types",
            default=True,
            update=on_bf2_obj_type_manual_mode_update
        ) # type: ignore
    )

    # --------------------------------------------------------------------

    rc.reg_prop(Object, 'bf2_link_lightmap_size',
        BoolProperty(
            name="Link Lightmap Size",
            description="Change both X and Y size uniformly",
            default=True
        ) # type: ignore
    )

    rc.reg_prop(Object, 'bf2_lightmap_size',
        IntVectorProperty(
            name="Lightmap size",
            description="Lightmap bitmap dimensions for baking & samples generation, the value is relevant only for StaticMesh Lod objects (Geom's immediate child)",
            default=(0, 0),
            size=2,
            set=set_lm_size,
            get=get_lm_size
        ) # type: ignore
    )

    rc.reg_class(OBJECT_PT_bf2_object)

    # --------------------------------------------------------------------

    rc.reg_prop(Object, 'bf2_fence_collection',
        PointerProperty(
            name="Segments",
            description = "Collection with all the segments used for generating the fence",
            type=bpy.types.Collection,
            update=on_collection_update
        ) # type: ignore
    )

    rc.reg_prop(Object, 'bf2_fence_curve',
        PointerProperty(
            name="Curve",
            description = "Curve on which to generate the fence",
            type=bpy.types.Object,
            update=on_curve_update
        ) # type: ignore
    )

    rc.reg_class(FenceSegmentsCollection)
    rc.reg_prop(Object, 'bf2_fence_custom_segments',
        CollectionProperty(type=FenceSegmentsCollection) # type: ignore
    )

    rc.reg_class(BF2_OT_bf2_fence_duplicate_item)
    rc.reg_class(BF2_OT_bf2_fence_remove_item)
    rc.reg_class(BF2_OT_bf2_fence_add_item)
    rc.reg_class(OBJECT_PT_bf2_fence)

register, unregister = RegisterFactory.create(init)
