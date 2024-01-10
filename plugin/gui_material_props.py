import bpy
import traceback
from bpy.types import Mesh, Material
from bpy.props import EnumProperty, StringProperty, BoolProperty

from ..core.mesh_material import setup_material

MATERIAL_TYPES = [
    ('STATICMESH', 'StaticMesh', "", 0),
    ('BUNDLEDMESH', 'BundledMesh', "", 1),
    ('SKINNEDMESH', 'SkinnedMesh', "", 2), # not yet supported
]

ALPHA_MODES = [
    ('NONE', 'None', "", 0),
    ('ALPHA_TEST', 'Alpha Test', "", 1),
    ('ALPHA_BLEND', 'Alpha Blend', "", 2)
]

def _get_active_material(context):
    active_obj = context.view_layer.objects.active
    if active_obj is not None and isinstance(active_obj.data, Mesh):
        materials = active_obj.data.materials
        material_idx = context.object.active_material_index
        if material_idx < len(materials):
            return materials[material_idx]
    return None

class MESH_OT_bf2_add_material(bpy.types.Operator):
    bl_idname = "bf2_material.add"
    bl_label = "Apply Material"
    bl_description = "Create Shader Nodes that mimic the BF2 material with the selected material settings"

    @classmethod
    def poll(cls, context):
        return _get_active_material(context)

    def execute(self, context):
        material = _get_active_material(context)
        try:
            setup_material(material)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

class MESH_PT_bf2_materials(bpy.types.Panel):
    bl_label = "BF2 Material"
    bl_idname = "MESH_PT_bf2_materials"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return _get_active_material(context)

    def draw(self, context):
        material = _get_active_material(context)

        if material:
            col = self.layout.column()
            col.prop(material, "is_bf2_material")

            col = self.layout.column()
            col.prop(material, "bf2_shader")
            col.enabled = material.is_bf2_material

            col = self.layout.column()
            col.prop(material, "bf2_technique")
            col.enabled = material.is_bf2_material and material.bf2_shader != 'STATICMESH'

            row = self.layout.row(align=True)
            row.label(text="Alpha Mode")
            for item in ALPHA_MODES:
                identifier = item[0]
                item_layout = row.row(align=True)  
                item_layout.prop_enum(material, "bf2_alpha_mode", identifier)

                if identifier == 'ALPHA_TEST':
                    item_layout.enabled = material.bf2_shader != 'SKINNEDMESH'
                elif identifier == 'ALPHA_BLEND':
                    item_layout.enabled = material.bf2_shader == 'BUNDLEDMESH'

            row.enabled = material.is_bf2_material

            col = self.layout.column()
            col.operator(MESH_OT_bf2_add_material.bl_idname, text="Apply Material")
            col.enabled = material.is_bf2_material

# TODO: I don't know what is the differe
# TODO: skinnedmesh will need a different default, tangent?

def _update_techinique_default_value(material):
    if not material.is_bf2_material:
        material.bf2_technique = ''

    if material.bf2_shader == 'STATICMESH':
        material.bf2_technique = ''
    elif material.bf2_shader == 'BUNDLEDMESH':
        if material.bf2_alpha_mode == 'ALPHA_BLEND':
            material.bf2_technique = 'Alpha'
        elif material.bf2_alpha_mode == 'ALPHA_TEST':
            material.bf2_technique = 'Alpha_Test'
        else:
            material.bf2_technique = 'ColormapGloss'

def on_shader_update(self, context):
    _update_techinique_default_value(self)

def on_alpha_mode_update(self, context):
    _update_techinique_default_value(self)

def register():
    Material.is_bf2_material = BoolProperty(
        name="Is BF2 Material",
        description="Enable this to auto-generate Shader Nodes",
        default=False
    )

    Material.bf2_alpha_mode = EnumProperty(
        name="Alpha Mode",
        description="BF2 Alpha mode to export, NOTE: switching the value overrides material's Alpha Blending mode",
        default=0,
        items=ALPHA_MODES,
        update=on_alpha_mode_update
    )

    # TODO: figure out what possible techiniques are and make it an enum
    Material.bf2_technique = StringProperty(
            name="Technique",
            description="BF2 Shader Technique to export",
            default=''
    )

    Material.bf2_shader = EnumProperty(
        name="Shader",
        description="BF2 Shader to export",
        default=0,
        items=MATERIAL_TYPES,
        update=on_shader_update
    )

    bpy.utils.register_class(MESH_OT_bf2_add_material)
    bpy.utils.register_class(MESH_PT_bf2_materials)

def unregister():
    bpy.utils.unregister_class(MESH_PT_bf2_materials)
    bpy.utils.unregister_class(MESH_OT_bf2_add_material)
    del Material.bf2_shader
    del Material.bf2_technique
    del Material.bf2_alpha_mode
    del Material.is_bf2_material
