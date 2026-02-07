import bpy # type: ignore
import traceback
import os
import re
from pathlib import Path
from bpy.types import Mesh, Material # type: ignore
from bpy.props import EnumProperty, StringProperty, BoolProperty # type: ignore
from .. import get_mod_dirs

from ..core.utils import Reporter, show_error, file_name
from ..core.material import is_staticmesh_map_allowed, setup_material, get_staticmesh_technique_from_maps
from ..core.mesh import MaterialWithTransparency

MATERIAL_TYPES = [
    ('STATICMESH', 'StaticMesh', "", 0),
    ('BUNDLEDMESH', 'BundledMesh', "", 1),
    ('SKINNEDMESH', 'SkinnedMesh', "", 2)
]

def to_blender_enum(e, visible_name):
    return (e.name, visible_name, "", e.value)

ALPHA_MODES = [
    to_blender_enum(MaterialWithTransparency.AlphaMode.NONE, 'None'),
    to_blender_enum(MaterialWithTransparency.AlphaMode.ALPHA_BLEND, 'Alpha Blend'),
    to_blender_enum(MaterialWithTransparency.AlphaMode.ALPHA_TEST, 'Alpha Test')
]

class SkipMaterialUpdateCallback():
    def __init__(self, material):
        self.material = material

    def __enter__(self):
        self.is_bf2_material = False
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.is_bf2_material = True

PATTERN_ALPHA_TEST = re.compile(re.escape('Alpha_Test'), re.IGNORECASE)
PATTERN_TANGENT = re.compile(re.escape('tangent'), re.IGNORECASE)

def _add_technique(material, pattern):
    if not pattern.search(material.bf2_technique):
        material.bf2_technique += pattern.pattern

def _del_technique(material, pattern):
    material.bf2_technique = pattern.sub('', material.bf2_technique)

class MESH_OT_bf2_apply_material(bpy.types.Operator):
    bl_idname = "bf2.material_apply"
    bl_label = "Apply Material"
    bl_description = "Create Shader Nodes that mimic the BF2 material with the selected material settings"

    @classmethod
    def poll(cls, context):
        material = context.material
        if material and material.is_bf2_material:
            if material.bf2_shader == 'STATICMESH':
                return material.bf2_technique
            else:
                return material.texture_slot_0 # has diffuse
        return False

    def execute(self, context):
        mod_paths = get_mod_dirs(context)
        material = context.material
        try:
            setup_material(material, texture_paths=mod_paths, reporter=Reporter(self.report))
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
        return context.material

    def draw(self, context):
        material = context.material

        if material:
            col = self.layout.column()
            col.prop(material, "is_bf2_material")

            enabled = material.is_bf2_material

            col = self.layout.column()
            col.prop(material, "bf2_shader")
            col.enabled = enabled

            col = self.layout.column()
            col.prop(material, "bf2_technique")
            col.enabled = enabled and material.bf2_shader != 'STATICMESH'

            col = self.layout.column()
            col.prop(material, "is_bf2_vegitation")
            col.enabled = enabled and material.bf2_shader == 'STATICMESH'

            row = self.layout.row(align=True)
            row.label(text="Alpha Mode")
            for item in ALPHA_MODES:
                identifier = item[0]
                item_layout = row.row(align=True)  
                item_layout.prop_enum(material, "bf2_alpha_mode", identifier)

                if identifier == 'ALPHA_BLEND':
                    item_layout.enabled = material.bf2_shader == 'BUNDLEDMESH'
            row.enabled = enabled

            if material.bf2_shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
                col = self.layout.column()
                col.prop(material, "texture_slot_0", text="Diffuse")
                col.prop(material, "texture_slot_1", text="Normal")
                if material.bf2_shader == 'BUNDLEDMESH':
                    col.prop(material, "texture_slot_2", text="Wreck")
                col.enabled = enabled
            else:
                is_vegitation = material.is_bf2_vegitation

                col = self.layout.column()
                col.prop(material, "texture_slot_0", text="Base")
                col.enabled = enabled

                col = self.layout.column()
                col.prop(material, "texture_slot_1", text="Detail")
                col.enabled = enabled and is_staticmesh_map_allowed(material, "Detail")

                col = self.layout.column()
                col.prop(material, "texture_slot_2", text="Dirt")
                col.enabled = enabled and not is_vegitation and is_staticmesh_map_allowed(material, "Dirt")

                col = self.layout.column()
                col.prop(material, "texture_slot_3", text="Crack")
                col.enabled = enabled and not is_vegitation and is_staticmesh_map_allowed(material, "Crack")

                col = self.layout.column()
                col.prop(material, "texture_slot_4", text="Detail Normal")
                col.enabled = enabled and is_staticmesh_map_allowed(material, "NDetail")

                col = self.layout.column()
                col.prop(material, "texture_slot_5", text="Crack Normal")
                col.enabled = enabled and not is_vegitation and is_staticmesh_map_allowed(material, "NCrack")

            mod_paths = get_mod_dirs(context)
            if not mod_paths:
                col = self.layout.column()
                col.label(text='WARNING: Mod Path is not defined in add-on preferences, textures will not load', icon='ERROR')

            col = self.layout.column()
            col.operator(MESH_OT_bf2_apply_material.bl_idname, text="Apply Material")

def _update_techinique_default_value(material):
    if not material.is_bf2_material:
        return

    if material.bf2_shader == 'STATICMESH':
        material.bf2_technique = get_staticmesh_technique_from_maps(material)
    elif material.bf2_shader == 'BUNDLEDMESH':
        if material.bf2_alpha_mode != 'ALPHA_TEST':
            _del_technique(material, PATTERN_ALPHA_TEST)
    elif material.bf2_shader == 'SKINNEDMESH':
        if material.texture_slot_1 and file_name(material.texture_slot_1).endswith('_b'):
            _add_technique(material, PATTERN_TANGENT)
        if material.bf2_alpha_mode == 'ALPHA_TEST':
            _add_technique(material, PATTERN_ALPHA_TEST)
        else:
            _del_technique(material, PATTERN_ALPHA_TEST)

def on_shader_update(self, context):
    if not self.is_bf2_material:
        return

    with SkipMaterialUpdateCallback(self):
        self.bf2_technique = ''
        if self.bf2_shader != 'STATICMESH':
            self.is_bf2_vegitation = False
    _update_techinique_default_value(self)

def on_alpha_mode_update(self, context):
    _update_techinique_default_value(self)

def on_texture_map_update(self, context, index):
    if not self.is_bf2_material:
        return

    mod_paths = get_mod_dirs(context)
    prop_name = f'texture_slot_{index}'
    prop_val = getattr(self, prop_name)

    if prop_val.startswith('//'): # path relative to current blend file
        prop_val = bpy.path.abspath(prop_val)

    if os.path.isabs(prop_val):
        prop_val = os.path.normpath(prop_val)
        if not mod_paths:
            show_error(context,
                       title='MOD path not set!',
                       text='To set texture paths, MOD path must be defined in add-on\'s preferences! Read the manual')
            prop_val = ''
        else:
            for mod_path in mod_paths:
                try:
                    prop_val = Path(prop_val).relative_to(mod_path).as_posix().lower()
                    break
                except ValueError:
                    prop_val = ''
            if not prop_val:
                show_error(context,
                        title='Invalid texture path!',
                        text=f'Given path: "{prop_val}" is not relative to any of the MOD paths defined in add-on preferences')
                prop_val = ''
    else:
        pass # relative path probably typed manually, dunno what could check here  

    with SkipMaterialUpdateCallback(self):
        setattr(self, prop_name, prop_val)

    if self.bf2_shader in ('STATICMESH', 'SKINNEDMESH'):
        _update_techinique_default_value(self)

def on_is_vegitation_update(self, context):
    if not self.is_bf2_material:
        return

    if self.bf2_shader != 'STATICMESH':
        return
    if not self.is_bf2_vegitation:
        return
    
    # clear Dirt, Crack, NCrack
    with SkipMaterialUpdateCallback(self):
        self.texture_slot_2 = ''
        self.texture_slot_3 = ''
        self.texture_slot_5 = ''
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
        description="Enable this to mark the material to export as BF2 material",
        default=False
    )

    Material.is_bf2_vegitation = BoolProperty(
        name="Is Vegitation",
        description="Enable this if StaticMesh shall use vegitation shaders (it does not affect export)",
        default=False,
        update=on_is_vegitation_update
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
    del Material.is_bf2_vegitation
    del Material.is_bf2_material
