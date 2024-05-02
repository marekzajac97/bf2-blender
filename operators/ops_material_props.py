import bpy # type: ignore
import traceback
import os
from pathlib import Path
from bpy.types import Mesh, Material # type: ignore
from bpy.props import EnumProperty, StringProperty, BoolProperty # type: ignore
from .. import PLUGIN_NAME

from ..core.utils import Reporter
from ..core.mesh_material import setup_material, get_staticmesh_technique_from_maps

MATERIAL_TYPES = [
    ('STATICMESH', 'StaticMesh', "", 0),
    ('BUNDLEDMESH', 'BundledMesh', "", 1),
    ('SKINNEDMESH', 'SkinnedMesh', "", 2)
]

# XXX: must correspond with MaterialWithTransparency.AlphaMode enum
ALPHA_MODES = [
    ('NONE', 'None', "", 0),
    ('ALPHA_BLEND', 'Alpha Blend', "", 1),
    ('ALPHA_TEST', 'Alpha Test', "", 2),
]

def _get_active_material(context):
    active_obj = context.view_layer.objects.active
    if active_obj is not None and isinstance(active_obj.data, Mesh):
        materials = active_obj.data.materials
        material_idx = context.object.active_material_index
        if material_idx < len(materials):
            return materials[material_idx]
    return None

class MESH_OT_bf2_apply_material(bpy.types.Operator):
    bl_idname = "bf2_material.add"
    bl_label = "Apply Material"
    bl_description = "Create Shader Nodes that mimic the BF2 material with the selected material settings"

    @classmethod
    def poll(cls, context):
        material = _get_active_material(context)
        if material and material.is_bf2_material:
            if material.bf2_shader == 'STATICMESH':
                return material.bf2_technique
            else:
                return material.texture_slot_0 # has diffuse
        return False

    def execute(self, context):
        mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
        material = _get_active_material(context)
        try:
            setup_material(material, texture_path=mod_path, reporter=Reporter(self.report))
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
            if material.bf2_shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
                col.prop(material, "texture_slot_0", text="Diffuse")
                col.prop(material, "texture_slot_1", text="Normal")
                if material.bf2_shader == 'BUNDLEDMESH':
                    col.prop(material, "texture_slot_2", text="Shadow")
            else:
                col.prop(material, "texture_slot_0", text="Base")
                col.prop(material, "texture_slot_1", text="Detail")
                col.prop(material, "texture_slot_2", text="Dirt")
                col.prop(material, "texture_slot_3", text="Crack")
                col.prop(material, "texture_slot_4", text="Detail Normal")
                col.prop(material, "texture_slot_5", text="Crack Normal")

            col = self.layout.column()
            col.operator(MESH_OT_bf2_apply_material.bl_idname, text="Apply Material")

def _update_techinique_default_value(material):
    if not material.is_bf2_material:
        material['bf2_technique'] = ''

    if material.bf2_shader == 'STATICMESH':
        material['bf2_technique'] = get_staticmesh_technique_from_maps(material)
    elif material.bf2_shader == 'BUNDLEDMESH':
        if material.bf2_alpha_mode == 'ALPHA_BLEND':
            material['bf2_technique'] = 'Alpha'
        elif material.bf2_alpha_mode == 'ALPHA_TEST':
            material['bf2_technique'] = 'Alpha_Test'
        else:
            material['bf2_technique'] = 'ColormapGloss'
    elif material.bf2_shader == 'SKINNEDMESH':
        material['bf2_technique'] = 'Humanskin'

def on_shader_update(self, context):
    _update_techinique_default_value(self)

def on_alpha_mode_update(self, context):
    _update_techinique_default_value(self)

def on_texture_map_update(self, context, index):
    mod_path = context.preferences.addons[PLUGIN_NAME].preferences.mod_directory
    prop = f'texture_slot_{index}'

    if self[prop].startswith('//'): # path relative to current blend file
        self[prop] = bpy.path.abspath(self[prop])

    if os.path.isabs(self[prop]):
        self[prop] = os.path.normpath(self[prop])
        if mod_path:
            try:
                self[prop] = Path(self[prop]).relative_to(mod_path).as_posix().lower()
            except ValueError as e:
                self[prop] = f'ERROR: Texture path is not relative to MOD path defined in add-on preferences: "{mod_path}"'
        else:
            # TODO don't know how to trigger a warning here
            self[prop] = 'ERROR: MOD path not defined in add-on preferences!'
    else:
        pass # relative path probably typed manually, dunno what could check here  

    if self.bf2_shader == 'STATICMESH':
        _update_techinique_default_value(self)

def _create_texture_slot(index):
    return StringProperty(
        name=f"Texture{index} Path",
        description="Filepath used for texture slot {index}",
        maxlen=1024,
        subtype='FILE_PATH',
        update=lambda self, context: on_texture_map_update(self, context, index)
    )

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

    Material.texture_slot_0 = _create_texture_slot(0)
    Material.texture_slot_1 = _create_texture_slot(1)
    Material.texture_slot_2 = _create_texture_slot(2)
    Material.texture_slot_3 = _create_texture_slot(3)
    Material.texture_slot_4 = _create_texture_slot(4)
    Material.texture_slot_5 = _create_texture_slot(5)

    bpy.utils.register_class(MESH_OT_bf2_apply_material)
    bpy.utils.register_class(MESH_PT_bf2_materials)

def unregister():
    bpy.utils.unregister_class(MESH_PT_bf2_materials)
    bpy.utils.unregister_class(MESH_OT_bf2_apply_material)
    del Material.texture_slot_5
    del Material.texture_slot_4
    del Material.texture_slot_3
    del Material.texture_slot_2
    del Material.texture_slot_1
    del Material.texture_slot_0
    del Material.bf2_shader
    del Material.bf2_technique
    del Material.bf2_alpha_mode
    del Material.is_bf2_material
