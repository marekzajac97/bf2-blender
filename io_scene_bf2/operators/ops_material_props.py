import bpy # type: ignore
import traceback
import os
import re
from pathlib import Path
from bpy.types import Mesh, Material # type: ignore
from bpy.props import EnumProperty, StringProperty, BoolProperty # type: ignore
from .ops_prefs import get_mod_dirs
from .utils import RegisterFactory

from ..core.utils import Reporter, show_error, file_name
from ..core.material import is_staticmesh_map_allowed, setup_material, get_staticmesh_technique_from_maps
from ..core.mesh import MaterialWithTransparency

AlphaMode = MaterialWithTransparency.AlphaMode

def to_blender_enum(e, visible_name):
    return (e.name, visible_name, "", e.value)

class SkipMaterialUpdateCallback():
    def __init__(self, material):
        self.material = material

    def __enter__(self):
        self.material.is_bf2_material = False
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.material.is_bf2_material = True

class MESH_OT_bf2_apply_material(bpy.types.Operator):
    bl_idname = "bf2.material_apply"
    bl_label = "Apply Material"
    bl_description = "Creates shader nodes that imitate BF2 material using selected material settings"

    @classmethod
    def poll(cls, context):
        material = context.material
        if material and material.is_bf2_material:
            if material.bf2_shader == 'STATICMESH':
                cls.poll_message_set("msut set at least the 'Base' texture map")
                return material.bf2_technique
            else:
                cls.poll_message_set("must set at least the 'Color' texture map")
                return material.texture_slot_0 # has color
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
        layout = self.layout
        layout.use_property_split = True
        material = context.material

        if material:
            col = layout.column()
            col.prop(material, "is_bf2_material")

            main = layout.column()
            main.enabled = material.is_bf2_material

            main.prop(material, "bf2_shader")

            if material.bf2_shader == 'STATICMESH':
                main.prop(material, "is_bf2_vegitation")

            if material.bf2_shader != 'STATICMESH':
                row = main.row(heading="Technique")
                row.prop(material, "bf2_technique_typein_mode", text="")
                subrow = row.row()
                subrow.enabled = material.bf2_technique_typein_mode
                subrow.prop(material, "bf2_technique", text="")
            else:
                row = main.row()
                row.enabled = False
                row.prop(material, "bf2_technique")   

            main.separator(factor=1.0, type='SPACE')

            if material.bf2_shader == 'BUNDLEDMESH':
                col = main.column(align=True)
                col.enabled = not material.bf2_technique_typein_mode
                row = col.row(align=True)
                row.prop(material, "bf2_use_colormapgloss", toggle=True)
                row = col.row(align=True)
                row.prop(material, "bf2_use_envmap", toggle=True)
                row.prop(material, "bf2_use_animateduv", toggle=True)
                row = col.row(align=True)
                row.prop(material, "bf2_use_cockpit", toggle=True)
                row.prop(material, "bf2_use_nohemilight", toggle=True)

            main.separator(factor=1.0, type='SPACE')

            if material.bf2_shader == 'BUNDLEDMESH':
                main.prop(material, "bf2_alpha_mode", expand=True)
            else:
                main.prop(material, "bf2_alpha_mode_restricted", expand=True)

            main.separator(factor=1.0, type='SPACE')

            if material.bf2_shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
                main.prop(material, "texture_slot_0", text="Color")

                col = main.column()
                col.prop(material, "texture_slot_1", text="Normal")
                col.enabled = bool(material.texture_slot_0)
                if material.bf2_shader == 'BUNDLEDMESH':
                    col = main.column()
                    col.prop(material, "texture_slot_2", text="Wreck")
                    col.enabled = bool(material.texture_slot_0)
            else:
                is_vegitation = material.is_bf2_vegitation

                main.prop(material, "texture_slot_0", text="Base")

                col = main.column()
                col.prop(material, "texture_slot_1", text="Detail")
                col.enabled = is_staticmesh_map_allowed(material, "Detail")

                col = main.column()
                col.prop(material, "texture_slot_2", text="Dirt")
                col.enabled = not is_vegitation and is_staticmesh_map_allowed(material, "Dirt")

                col = main.column()
                col.prop(material, "texture_slot_3", text="Crack")
                col.enabled = not is_vegitation and is_staticmesh_map_allowed(material, "Crack")

                col = main.column()
                col.prop(material, "texture_slot_4", text="Detail Normal")
                col.enabled = is_staticmesh_map_allowed(material, "NDetail")

                col = main.column()
                col.prop(material, "texture_slot_5", text="Crack Normal")
                col.enabled = not is_vegitation and is_staticmesh_map_allowed(material, "NCrack")

            mod_paths = get_mod_dirs(context)
            if not mod_paths:
                col = layout.column()
                col.label(text='WARNING: Mod Path is not defined in add-on preferences, textures will not load', icon='ERROR')

            col = layout.column()
            col.operator(MESH_OT_bf2_apply_material.bl_idname, text="Apply Material")

def _update_techinique(material):
    if not material.is_bf2_material:
        return

    if material.bf2_shader == 'STATICMESH':
        material.bf2_technique = get_staticmesh_technique_from_maps(material)
        return

    if material.bf2_shader == 'SKINNEDMESH':
        if material.texture_slot_1:
            if file_name(material.texture_slot_1).endswith('_b'):
                material.bf2_use_tangent = True
            else:
                material.bf2_use_tangent = False

    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        if material.bf2_alpha_mode == 'ALPHA_TEST':
            material.bf2_use_alpha_test = True # only needed for colormapgloss but won't hurt if not present
        else:
            material.bf2_use_alpha_test = False

def on_shader_update(self, context):
    if not self.is_bf2_material:
        return

    with SkipMaterialUpdateCallback(self):
        self.bf2_technique = ''
        if self.bf2_shader != 'STATICMESH':
            self.is_bf2_vegitation = False

        if self.bf2_shader != 'BUNDLEDMESH' and self.bf2_alpha_mode == 'ALPHA_BLEND':
            self.bf2_alpha_mode = 'NONE'

    _update_techinique(self)

def on_alpha_mode_update(self, context):
    _update_techinique(self)

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
        _update_techinique(self)

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
    _update_techinique(self)

def _create_technique_prop(name, description=''):
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    def setter(self, value):
        if value:
            if not pattern.search(self.bf2_technique):
                self.bf2_technique += name
        else:
            self.bf2_technique = pattern.sub('', self.bf2_technique)

    def getter(self):
        return pattern.search(self.bf2_technique) is not None

    return BoolProperty(
        name=name,
        description=description,
        get=getter,
        set=setter,
        options=set()
    )

def init(rc : RegisterFactory):
    rc.reg_prop(Material, 'is_bf2_material',
        BoolProperty(
            name="Is BF2 Material",
            description="Enable this to mark the material for export as BF2 material",
            default=False,
            options=set()
        )
    )

    rc.reg_prop(Material, 'is_bf2_vegitation',
        BoolProperty(
            name="Is Vegitation",
            description="Whether to use special vegitation leaf/trunk shaders. (it does not affect export)",
            default=False,
            update=on_is_vegitation_update,
            options=set()
        )
    )

    rc.reg_prop(Material, 'bf2_alpha_mode',
        EnumProperty(
            name="Alpha Mode",
            description="Sets what BF2 transparency render states to use",
            default=0,
            items=[
                to_blender_enum(AlphaMode.NONE, 'None'),
                to_blender_enum(AlphaMode.ALPHA_BLEND, 'Alpha Blend'),
                to_blender_enum(AlphaMode.ALPHA_TEST, 'Alpha Test')
            ],
            update=on_alpha_mode_update,
            options=set()
        )
    )

    def set_alpha_mode_restricted(self, int_val):
        self.bf2_alpha_mode = AlphaMode(int_val).name

    def get_alpha_mode_restricted(self):
        return AlphaMode[self.bf2_alpha_mode].value

    rc.reg_prop(Material, 'bf2_alpha_mode_restricted',
        EnumProperty(
            name="Alpha Mode",
            description="Sets what BF2 transparency render states to use",
            items=[
                to_blender_enum(AlphaMode.NONE, 'None'),
                to_blender_enum(AlphaMode.ALPHA_TEST, 'Alpha Test')
            ],
            get=get_alpha_mode_restricted,
            set=set_alpha_mode_restricted,
            options=set()
        ) # type: ignore
    )

    rc.reg_prop(Material, 'bf2_technique',
        StringProperty(
            name="Technique",
            description="BF2 Shader Technique to export",
            default=''
        )
    )

    rc.reg_prop(Material, 'bf2_technique_typein_mode',
        BoolProperty(
            name="Manual Type-in",
            description="Specify the technique manually",
            default=False,
            options=set()
        )
    )

    rc.reg_prop(Material, 'bf2_shader',
        EnumProperty(
            name="Shader",
            description="BF2 Shader to export",
            default=0,
            items=[
                ('STATICMESH', 'StaticMesh', "", 0),
                ('BUNDLEDMESH', 'BundledMesh', "", 1),
                ('SKINNEDMESH', 'SkinnedMesh', "", 2)
            ],
            update=on_shader_update,
            options=set()
        )
    )

    for index in range(6):
        rc.reg_prop(Material, f'texture_slot_{index}',
            StringProperty(
                name=f"Texture{index} Path",
                description=f"Filepath used for texture slot {index}",
                maxlen=1024,
                subtype='FILE_PATH',
                update=lambda self, context: on_texture_map_update(self, context, index)
            )                
        )

    rc.reg_prop(Material, 'bf2_use_colormapgloss',
        _create_technique_prop(
            name='ColormapGloss',
            description="If enabled, The alpha channel of the `Color` map will be used as the gloss map instead of the opacity map. "
                        "If disabled, the gloss map is taken from the `Normal` map's alpha channel if provided."
        )
    )

    rc.reg_prop(Material, 'bf2_use_alpha_test',
        _create_technique_prop(
            name='Alpha_Test',
            description="By itself, enabling it will have no effect. When combined with `ColormapGloss` it makes parts of the surface where the `Color` map is black (RGB == 0,0,0) fully transparent."
        )
    )

    rc.reg_prop(Material, 'bf2_use_envmap',
        _create_technique_prop(
            name='EnvMap',
            description="Enables environment map based reflections (scaled using gloss map)"
        )
    )

    rc.reg_prop(Material, 'bf2_use_animateduv',
        _create_technique_prop( # TODO: add alt 'animated'
            name='AnimatedUV',
            description="Enables transformation of texture coordinates"
        )
    )

    rc.reg_prop(Material, 'bf2_use_cockpit',
        _create_technique_prop(
            name='Cockpit',
            description="Enables static lighting"
        )
    )

    rc.reg_prop(Material, 'bf2_use_nohemilight',
        _create_technique_prop(
            name='NoHemiLight',
            description="Disables hemimap"
        )
    )

    rc.reg_prop(Material, 'bf2_use_tangent',
        _create_technique_prop(
            name='tangent'
        )
    )

    rc.reg_class(MESH_OT_bf2_apply_material)
    rc.reg_class(MESH_PT_bf2_materials)

register, unregister = RegisterFactory.create(init)
