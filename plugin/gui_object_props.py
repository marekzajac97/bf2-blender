import bpy
from bpy.props import StringProperty

class OBJECT_PT_bf2_object(bpy.types.Panel):
    bl_label = "Battlefield 2"
    bl_idname = "OBJECT_PT_bf2_object"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        active_obj = context.view_layer.objects.active
        return active_obj is not None

    def draw(self, context):
        layout = self.layout
        active_obj = context.view_layer.objects.active
        layout.prop(active_obj, "bf2_object_type")

def register():
    bf2_object_type_prop = StringProperty(
            name="BF2 Object Type",
            description="Type of BF2 Object (e.g. GenericFirearm) this Blender Object represents",
            default = 'SimpleObject'
        )
    bpy.types.Object.bf2_object_type = bf2_object_type_prop
    bpy.utils.register_class(OBJECT_PT_bf2_object)

def unregister():
    bpy.utils.unregister_class(OBJECT_PT_bf2_object)
    del bpy.types.Object.bf2_object_type
