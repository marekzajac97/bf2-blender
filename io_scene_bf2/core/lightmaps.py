import os
import os.path as path
import math
import re
import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Matrix, Vector # type: ignore
from abc import ABC, abstractmethod

from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            HeightmapCluster,
                            Object)
from .bf2.bf2_mesh import BF2BundledMesh, BF2StaticMesh, BF2SkinnedMesh, BF2Samples
from .mod_loader import ModLoader
from .mesh_material import setup_material, get_material_maps, STATICMESH_TEXUTRE_MAP_TYPES
from .mesh import MeshImporter, MeshExporter
from .utils import (DEFAULT_REPORTER,
                    swap_zy, file_name,
                    _convert_pos, _convert_rot,
                    to_matrix, save_img_as_dds,
                    delete_object, find_root,
                    is_pow_two, obj_bounds)
from .heightmap import import_heightmap_from
from .exceptions import ImportException
from fnmatch import fnmatch

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

def module_from_file(py_file):
    import importlib.util
    spec = importlib.util.spec_from_file_location("lm_config", py_file)
    lm_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lm_config)
    return lm_config

# -------------------
# baking common
# -------------------

class BakerBase(ABC):
    def __init__(self, output_dir, dds_fmt='NONE'):
        self.output_dir =output_dir
        self.dds_fmt = dds_fmt

    @abstractmethod
    def type(self):
        ...

    @abstractmethod
    def total_items(self):
        ...

    @abstractmethod
    def completed_items(self):
        ...

    @abstractmethod
    def bake_next(self, context):
        ...

    def save_bake(self, image, name=''):
        if not name:
            name = image.name
        save_img_as_dds(image, path.join(self.output_dir, f'{name}.dds'), self.dds_fmt)

    def bake_all(self):
        while self.bake_next():
            pass

    def cleanup(self, context):
        pass

def _setup_scene_for_baking(context):
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.bake_type = 'DIFFUSE'
    context.scene.render.bake.use_pass_direct = True
    context.scene.render.bake.use_pass_indirect = True
    context.scene.render.bake.use_pass_color = False

def _setup_material_for_baking(material, bake_image=None, uv='UV4'):
    node_tree = material.node_tree
    # unselect all
    for node in node_tree.nodes:
        node.select = False

    # make texture image node
    texture_node = None
    for node in node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.name == 'LIGHTMAP_BAKE_TXT':
            texture_node = node
            break
    else:
        texture_node = node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.name = 'LIGHTMAP_BAKE_TXT'
        texture_node.location = (400, 500)

    texture_node.select = True
    texture_node.image = bake_image

    # make UV node
    uv_node = None
    for node in node_tree.nodes:
        if node.type == 'UVMAP' and node.name == 'LIGHTMAP_BAKE_UV':
            uv_node = node
            break
    else:
        uv_node = node_tree.nodes.new('ShaderNodeUVMap')
        uv_node.name = 'LIGHTMAP_BAKE_UV'
        uv_node.location = (400, 300)

    uv_node.uv_map = uv
    uv_node.select = True

    # link
    node_tree.links.new(uv_node.outputs['UV'], texture_node.inputs['Vector'])
    node_tree.nodes.active = texture_node
    return texture_node

def _make_add_ambinet_light(ambient_light_level):
    if 'AddAmbientLight' in bpy.data.node_groups:
        node_group = bpy.data.node_groups['AddAmbientLight']
        bpy.data.node_groups.remove(node_group)

    node_tree = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "AddAmbientLight")

    image = node_tree.nodes.new("CompositorNodeImage")
    image.name = "SrcImage"

    node_tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    separate_color = node_tree.nodes.new("CompositorNodeSeparateColor")
    combine_color = node_tree.nodes.new("CompositorNodeCombineColor")

    srgb_val = math.pow((ambient_light_level + 0.055) / 1.055, 2.4)
    map_range = node_tree.nodes.new('ShaderNodeMapRange')
    map_range.inputs['To Min'].default_value = srgb_val

    node_tree.links.new(
        image.outputs['Image'],
        separate_color.inputs['Image']
    )
    node_tree.links.new(
        separate_color.outputs['Green'],
        combine_color.inputs['Green']
    )
    node_tree.links.new(
        separate_color.outputs['Red'],
        combine_color.inputs['Red']
    )
    node_tree.links.new(
        separate_color.outputs['Blue'],
        map_range.inputs['Value']
    )
    node_tree.links.new(
        map_range.outputs['Result'],
        combine_color.inputs['Blue']
    )
    node_tree.links.new(
        combine_color.outputs['Image'],
        group_output.inputs['Image']
    )

    return node_tree

class PostProcessor:
    def __init__(self, context, src_dir, out_dir, intensity, dds_fmt='NONE'):
        if 'Render Result' in bpy.data.images:
            render_result = bpy.data.images['Render Result']
            bpy.data.images.remove(render_result)

        self.dds_fmt = dds_fmt
        self.add_ambient_light = _make_add_ambinet_light(intensity)
        context.scene.compositing_node_group = self.add_ambient_light
        self.out_dir = out_dir
        self.textures = list()
        for file in os.listdir(src_dir):
            filepath = path.join(src_dir, file)
            if not path.isfile(filepath):
                continue
            if not file.endswith(".dds"):
                continue
            self.textures.append(filepath)
        self.total_count = len(self.textures)

    def total_items(self):
        return self.total_count

    def completed_items(self):
        return self.total_count - len(self.textures)

    def process_next(self, context):
        if not self.textures:
            return False

        filepath = self.textures.pop(0)

        with PreserveColorSpaceSettings(context):
            context.scene.view_settings.view_transform = 'Standard'

            image = bpy.data.images.load(filepath, check_existing=False)
            image.alpha_mode = 'NONE'

            self.add_ambient_light.nodes['SrcImage'].image = image
            context.scene.render.resolution_x = image.size[0]
            context.scene.render.resolution_y = image.size[1]
            bpy.ops.render.render()

            # save output
            render_result = bpy.data.images['Render Result']
            save_img_as_dds(render_result, path.join(self.out_dir, path.basename(filepath)), self.dds_fmt)

            # cleanup
            self.add_ambient_light.nodes['SrcImage'].image = None
            bpy.data.images.remove(image)
            bpy.data.images.remove(render_result)
        
        return True

def get_all_lightmap_files(dir):
    files = set()
    for file in os.listdir(dir):
        if not file.endswith(".dds"):
            continue
        files.add(file[:-4])
    return files

LIGHTMAPPING_CONFIG_TEMPLATE = \
"""
# THIS IS A LIGHTMAPING CONFIG TEMPLATE
# PROVIDED VALUES ARE JUST EXAMPLES
# REMOVE LEADING `#` FOR THEM TO MAKE THEM TAKE ANY EFFECT

# Used to assign lightmap sizes to the object
# based on the total surface area of the mesh in meters squared
# NOTE1: values are only used when `.samples` file does not exist for the mesh
# NOTE2: values for LOD0, size for consequtive lods will be halved
LIGHTMAP_SIZE_TO_SURFACE_AREA_THRESHOLDS = [
    # {'size': 8, 'min_area': 0},
    # {'size': 16, 'min_area': 4},
    # {'size': 32, 'min_area': 8},
    # {'size': 64, 'min_area': 16},
    # {'size': 128, 'min_area': 32},
    # {'size': 256, 'min_area': 256},
    # {'size': 512, 'min_area': 1024},
    # {'size': 1024, 'min_area': 2056}
]

# Skips loading meshes for GeometryTemplates
# whose .con locations match the pattern
SKIP_OBJECT_TEMPLATE_PATHS = [
    # 'common/lightsources/dp_lights',
    # 'common/lightsources/l_lights',
    # 'common/lightsources/nf_lights'
]

# Skips loading meshes for GeometryTemplates
# whose names match the pattern
SKIP_OBJECT_TEMPLATES = [
    # 'glow*'
]

# Disables backface culling on materials for
# GeometryTemplates whose names match the pattern
FORCE_TWO_SIDED = [
    # 'command_underground'
]

# Replaces textures paths on materials:
#   'from' - the source texture pattern, NOTE: it's only Color/Detail/Crack/Dirt textures, not normal maps
#   'to' - the target texture path
#   'alpha_mode' - optional, the value must be either:
#      'ALPHA_TEST' - texture's alpha channel will be used as transparency. Material will not receive or cast any shadows.
#      'RAY_MASK' - texture's alpha channel will be used as a ray visibility mask instead. Material will receive shadows but will not cast them.
TEXTURE_REPLACE = [
    # {'from': 'objects/staticobjects/common_statics/textures/common_trench_de*.dds',
    #  'to': 'objects/staticobjects/common_statics/textures/common_trench_lightmapping_c.dds',
    #  'alpha_mode': 'ALPHA_TEST'},
    # {'from': 'objects/water/textures/watertemp.dds',
    #  'to': 'objects/staticobjects/common/textures/transparent_c.dds',
    #  'alpha_mode': 'RAY_MASK'}
]

# Defines where to place point lights:
#   'at' - pattern that matches the name of the ObjectTemplate, where the light should be placed, this value is mandatory
#   'offset' - offset relative to the ObjectTemplate pivot, defaults to (0, 0, 0)
#   'intensity' - sets 'intensity' value on the created Blender light, defaults to 100
#   'radius' - sets 'radius' value on the created Blender light, defaults to 0
#   'color' - defaults to 'red', use 'blue' if you want the point lights to appear on the terrain
LIGHT_SOURCES = [
    # {'at': 'houselight_small*', 'intensity': 400.0},
    # {'at': 'fh_groundlight_big', 'intensity': 400.0, 'color': 'blue'},
    # {'at': 'bunkerlight', 'intensity': 200.0, 'radius': 0.01, 'offset': (-0.0035, 0.002, 0.597)},
]
"""

class PreserveColorSpaceSettings():
    def __init__(self, context):
        self.context = context

    def __enter__(self):
        self.view_transform = self.context.scene.view_settings.view_transform
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.context.scene.view_settings.view_transform = self.view_transform

# -------------------
# baking terrain
# -------------------

def _make_flatten_at_watter_level(water_level):
    if 'FlattenAtWaterLevel' in bpy.data.node_groups:
        node_group = bpy.data.node_groups['FlattenAtWaterLevel']
        bpy.data.node_groups.remove(node_group)

    node_tree = bpy.data.node_groups.new(type='GeometryNodeTree', name="FlattenAtWaterLevel")

    in_sock = node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    out_sock = node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')

    group_input = node_tree.nodes.new("NodeGroupInput")
    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.is_active_output = True

    get_position = node_tree.nodes.new("GeometryNodeInputPosition")

    clamp = node_tree.nodes.new("ShaderNodeClamp")
    clamp.inputs['Min'].default_value = water_level
    clamp.inputs['Max'].default_value = 10000.0

    set_position = node_tree.nodes.new("GeometryNodeSetPosition")
    combine_xyz = node_tree.nodes.new("ShaderNodeCombineXYZ")
    separate_xyz = node_tree.nodes.new("ShaderNodeSeparateXYZ")

    node_tree.links.new(group_input.outputs['Geometry'], set_position.inputs['Geometry'])
    node_tree.links.new(set_position.outputs['Geometry'], group_output.inputs['Geometry'])
    node_tree.links.new(get_position.outputs['Position'], separate_xyz.inputs['Vector'])
    node_tree.links.new(separate_xyz.outputs['Z'], clamp.inputs['Value'])
    node_tree.links.new(clamp.outputs['Result'], combine_xyz.inputs['Z'])
    node_tree.links.new(separate_xyz.outputs['Y'], combine_xyz.inputs['Y'])
    node_tree.links.new(separate_xyz.outputs['X'], combine_xyz.inputs['X'])
    node_tree.links.new(combine_xyz.outputs['Vector'], set_position.inputs['Position'])
    return node_tree

def _make_water_depth_material(water_level, water_attenuation):
    if 'WaterDepth' in bpy.data.materials:
        water_depth = bpy.data.materials['WaterDepth']
        bpy.data.materials.remove(water_depth)

    NODE_SPACING = 200

    material = bpy.data.materials.new(name='WaterDepth')
    material.use_nodes = True
    node_tree = material.node_tree
    node_tree.nodes.clear()

    geometry = node_tree.nodes.new("ShaderNodeNewGeometry")
    geometry.location = (0, 0)
    separate_xyz = node_tree.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz.location = (1 * NODE_SPACING, 0)
    node_tree.links.new(geometry.outputs['Position'], separate_xyz.inputs['Vector'])

    # substract water level value from Z
    math_substract = node_tree.nodes.new("ShaderNodeMath")
    math_substract.operation = 'SUBTRACT'
    math_substract.inputs[1].default_value = water_level
    math_substract.location = (2 * NODE_SPACING, 100)
    node_tree.links.new(separate_xyz.outputs['Z'], math_substract.inputs[0])

    # multiply by water attenuation coefficient
    watter_att_node = node_tree.nodes.new("ShaderNodeValue")
    watter_att_node.name = "WaterAttenuation"
    watter_att_node.label = "WaterAttenuation"
    watter_att_node.outputs['Value'].default_value = water_attenuation
    watter_att_node.location = (1 * NODE_SPACING, -100)

    math_multiply = node_tree.nodes.new("ShaderNodeMath")
    math_multiply.operation = 'MULTIPLY'
    math_multiply.location = (2 * NODE_SPACING, 0)
    node_tree.links.new(watter_att_node.outputs['Value'], math_multiply.inputs[1])
    node_tree.links.new(math_substract.outputs['Value'], math_multiply.inputs[0])

    # calc exponent
    math_exp = node_tree.nodes.new("ShaderNodeMath")
    math_exp.operation = 'EXPONENT'
    math_exp.location = (3 * NODE_SPACING, 0)
    node_tree.links.new(math_multiply.outputs['Value'], math_exp.inputs['Value'])

    # re-map range 0-1 to 1-0
    math_substract = node_tree.nodes.new("ShaderNodeMath")
    math_substract.operation = 'SUBTRACT'
    math_substract.inputs[0].default_value = 1.0
    math_substract.location = (4 * NODE_SPACING, 0)
    node_tree.links.new(math_exp.outputs['Value'], math_substract.inputs[1])

    # map to red channel
    combine_color = node_tree.nodes.new("ShaderNodeCombineColor")
    combine_color.mode = 'RGB'
    combine_color.inputs['Green'].default_value = 0.0
    combine_color.inputs['Blue'].default_value = 0.0
    combine_color.location = (5 * NODE_SPACING, 0)
    node_tree.links.new(math_substract.outputs['Value'], combine_color.inputs['Red'])

    # output as diffuse color
    diffuse_bsdf = node_tree.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse_bsdf.location = (6 * NODE_SPACING, 0)

    node_tree.links.new(combine_color.outputs['Color'], diffuse_bsdf.inputs['Color'])

    material_output = node_tree.nodes.new("ShaderNodeOutputMaterial")
    material_output.location = (7 * NODE_SPACING, 0)
    node_tree.links.new(diffuse_bsdf.outputs['BSDF'], material_output.inputs['Surface'])
    return material

def _make_combine_channels():
    if 'CombineLightAndWaterDepth' in bpy.data.node_groups:
        node_group = bpy.data.node_groups['CombineLightAndWaterDepth']
        bpy.data.node_groups.remove(node_group)

    node_tree = bpy.data.node_groups.new(type = 'CompositorNodeTree', name = "CombineLightAndWaterDepth")

    image_light = node_tree.nodes.new("CompositorNodeImage")
    image_light.name = "LightMap"

    image_water = node_tree.nodes.new("CompositorNodeImage")
    image_water.name = "WaterDepthMap"

    node_tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    separate_color_light = node_tree.nodes.new("CompositorNodeSeparateColor")
    separate_color_water = node_tree.nodes.new("CompositorNodeSeparateColor")
    combine_color = node_tree.nodes.new("CompositorNodeCombineColor")

    node_tree.links.new(
        image_water.outputs['Image'],
        separate_color_water.inputs['Image']
    )
    node_tree.links.new(
        image_light.outputs['Image'],
        separate_color_light.inputs['Image']
    )
    node_tree.links.new(
        separate_color_water.outputs['Red'],
        combine_color.inputs['Red']
    )
    node_tree.links.new(
        separate_color_light.outputs['Green'],
        combine_color.inputs['Green']
    )
    node_tree.links.new(
        separate_color_light.outputs['Blue'],
        combine_color.inputs['Blue']
    )
    node_tree.links.new(
        combine_color.outputs['Image'],
        group_output.inputs['Image']
    )

    return node_tree

def _make_default_terrain_material(minimap_path):
    if 'DefaultTerrain' in bpy.data.materials:
        terrain = bpy.data.materials['DefaultTerrain']
        bpy.data.materials.remove(terrain)

    material = bpy.data.materials.new('DefaultTerrain')     
    material.use_nodes = True
    
    tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    try:
        tex_node.image = bpy.data.images.load(minimap_path, check_existing=True)
        tex_node.image.alpha_mode = 'NONE'
    except RuntimeError:
        pass # ignore if can't be loaded

    bsdf = material.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 1
    bsdf.inputs['Specular IOR Level'].default_value = 0
    bsdf.inputs['IOR'].default_value = 1.1
    material.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    return material

DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES = {
    512: (16, 1024),
    1024: (16, 2048),
    2048: (64, 2048),
    4096: (64, 4096)
}

def get_default_heightmap_patch_count_and_size(context, terrain=None):
    if not terrain:
        terrain = find_heightmap(context)
    if not terrain:
        return
    hm_size = get_heightmap_size(terrain)
    if hm_size is None:
        return
    if hm_size not in DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES:
        return
    return DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES[hm_size]

def get_heightmap_size(heightmap):
    bounds = obj_bounds(heightmap)
    x_s = int(bounds['x'].distance)
    y_s = int(bounds['y'].distance)
    if x_s != y_s or not is_pow_two(x_s):
        return None
    return x_s

def find_heightmap(context):
    if 'Heightmaps' not in context.scene.collection.children:
        return None
    for obj in context.scene.collection.children['Heightmaps'].objects:
        if obj.name.startswith('Heightmap'):
            return obj

def _offset_uvs(uv_layer, u, v):
    tmp = len(uv_layer.data) * 2 * [None]
    uv_layer.data.foreach_get('uv', tmp)
    def do_offset(i, value):
        if i % 2 == 0:
            return value + u
        else:
            return value + v
    tmp = [do_offset(i, value) for i, value in enumerate(tmp)]
    uv_layer.data.foreach_set('uv', tmp)

class TerrainBaker(BakerBase):
    def __init__(self, context, output_dir, dds_fmt='NONE',
                 patch_count=None, patch_size=None, skip_existing=False,
                 reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self.patch_count = patch_count
        self.patch_size = patch_size
        self.reporter = reporter
        self.terrain = find_heightmap(context)
        self.existing_patches = set()
        if skip_existing:
            existing = get_all_lightmap_files(output_dir)
            self.existing_patches = [e for e in existing if re.match(r'tx\d{2}x\d{2}', e)]
            # TODO: detect which terrain patches to skip entirely and do UV offset at one go based on skipped row/col

        if not self.terrain:
            raise RuntimeError(f'Heightmap object not found')

        if patch_count is None or patch_size is None:
            hm_size = get_heightmap_size(self.terrain)
            if hm_size is None:
                raise RuntimeError(f'Cannot determine heightmap size')
            if hm_size not in DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES:
                raise RuntimeError(f'Cannot determine default values for patch_count and patch_size')
            patch_count, patch_size = DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES[hm_size]

        self.grid_size = math.isqrt(patch_count)
        if self.grid_size * self.grid_size != patch_count:
            raise RuntimeError(f'patch_count must be a power of 4')

        mesh = self.terrain.data
        vert_count = math.isqrt(len(mesh.vertices))
        if vert_count * vert_count != len(mesh.vertices) or not is_pow_two(vert_count - 1):
            raise RuntimeError(f'heightmap vert count is invalid')
        
        self.default_terrain_mat = bpy.data.materials['DefaultTerrain']
        self.water_depth_mat = bpy.data.materials['WaterDepth']
        self.flatten_water_mod = self.terrain.modifiers['FlattenAtWaterLevel']

        self.combine_channels = _make_combine_channels()
        context.scene.compositing_node_group = self.combine_channels

        mesh.materials.clear()
        mesh.materials.append(self.default_terrain_mat)

        # we gon simply scale the UV up so the 0-1 range fits one whole patch
        # then shift the UV when rendering the grid
        mesh.uv_layers.active = mesh.uv_layers['UVMap']
        self.uv_layer = mesh.uv_layers.new(name='LightmapBakeUV')

        tmp = len(self.uv_layer.data) * 2 * [None]
        self.uv_layer.data.foreach_get('uv', tmp)

        def do_scale_and_offset(i, value):
            if i % 2 == 0:
                return self.grid_size * value
            else:
                return 1 - self.grid_size * value
        self.uv_layer.data.foreach_set('uv', [do_scale_and_offset(i, value) for i, value in enumerate(tmp)])

        self.texture_node_light = _setup_material_for_baking(self.default_terrain_mat, uv=self.uv_layer.name)
        self.texture_node_water_depth = _setup_material_for_baking(self.water_depth_mat, uv=self.uv_layer.name)

        _setup_scene_for_baking(context)
        if 'Render Result' in bpy.data.images:
            render_result = bpy.data.images['Render Result']
            bpy.data.images.remove(render_result)

        self.col = 0
        self.row = 0

    def type(self):
        return 'Terrain'

    def total_items(self):
        return self.patch_count

    def completed_items(self):
        return self.row + self.grid_size * self.col
    
    def cleanup(self, context):
        mesh = self.terrain.data
        context.scene.compositing_node_group = None
        mesh.materials[0] = self.default_terrain_mat
        mesh.uv_layers.remove(self.uv_layer)

    def bake_next(self, context):
        mesh = self.terrain.data

        for obj in context.selected_objects:
            obj.select_set(False)

        self.terrain.hide_set(False)
        self.terrain.select_set(True)
        self.terrain.hide_render = False

        if self.row >= self.grid_size:
            # next column
            self.row = 0
            self.col += 1
            _offset_uvs(self.uv_layer, -1, -self.grid_size)

        if self.col >= self.grid_size:
            # cleanup & return
            self.cleanup(context)
            return False

        name = f'tx{self.col:02d}x{self.row:02d}'
        if name in self.existing_patches:
            print(f"Skipped terrain patch {self.completed_items() + 1}/{self.patch_count}")
        else:
            print(f"Baking terrain patch {self.completed_items() + 1}/{self.patch_count}")

            light_map = bpy.data.images.new(name=f'TerrainLightmapBakeImageLight', width=self.patch_size, height=self.patch_size)
            water_depth_map = bpy.data.images.new(name=f'TerrainLightmapBakeImageWaterDepth', width=self.patch_size, height=self.patch_size)

            for water_pass in [False, True]:
                if water_pass:
                    self.flatten_water_mod.show_render = False
                    mesh.materials[0] = self.water_depth_mat
                    self.texture_node_water_depth.image = water_depth_map
                else:
                    self.flatten_water_mod.show_render = True
                    mesh.materials[0] = self.default_terrain_mat
                    self.texture_node_light.image = light_map

                context.scene.render.bake.use_pass_direct = not water_pass
                context.scene.render.bake.use_pass_indirect = not water_pass
                context.scene.render.bake.use_pass_color = water_pass
                bpy.ops.object.bake(type='DIFFUSE', uv_layer=self.uv_layer.name)

            # combine both passes in compositor
            with PreserveColorSpaceSettings(context):
                context.scene.view_settings.view_transform = 'Standard'
                self.combine_channels.nodes['LightMap'].image = light_map
                self.combine_channels.nodes['WaterDepthMap'].image = water_depth_map
                context.scene.render.resolution_x = self.patch_size
                context.scene.render.resolution_y = self.patch_size
                bpy.ops.render.render()

                # save output
                render_result = bpy.data.images['Render Result']
                self.save_bake(render_result, name)

                # cleanup
                self.combine_channels.nodes['LightMap'].image = None
                self.combine_channels.nodes['WaterDepthMap'].image = None
                bpy.data.images.remove(light_map)
                bpy.data.images.remove(water_depth_map)
                bpy.data.images.remove(render_result)

        self.row += 1
        _offset_uvs(self.uv_layer, 0, 1)
        return True

# -------------------
# baking objects
# -------------------

def _add_texture_node(material, texture_file, texture_paths, reporter):
    for texture_path in texture_paths:
        abs_path = os.path.join(texture_path, texture_file)
        if os.path.isfile(abs_path):
            break
    else:
        if texture_paths:
            reporter.warning(f"Texture file '{texture_file}' not found in any of the texture paths")
        abs_path = ''
    tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    if abs_path:
        tex_node.image = bpy.data.images.load(abs_path, check_existing=True)
        tex_node.image.alpha_mode = 'STRAIGHT'
    return tex_node

def _make_ray_visibility_mask():
    if 'RayVisibilityMask' in bpy.data.node_groups:
        node_tree = bpy.data.node_groups['RayVisibilityMask']
        bpy.data.node_groups.remove(node_tree)

    node_tree = bpy.data.node_groups.new('RayVisibilityMask', 'ShaderNodeTree')

    group_inputs = node_tree.nodes.new('NodeGroupInput')
    node_tree.interface.new_socket(name="Mask", in_out='INPUT', socket_type='NodeSocketFloat')
    node_tree.interface.new_socket(name="Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    group_outputs = node_tree.nodes.new('NodeGroupOutput')
    node_tree.interface.new_socket(name="Alpha", in_out='OUTPUT', socket_type='NodeSocketFloat')

    light_path = node_tree.nodes.new("ShaderNodeLightPath")
    light_path.hide = True

    # combines world (diffuse) light with other ligth sources
    add_light = node_tree.nodes.new('ShaderNodeMath')
    add_light.operation = 'ADD'
    add_light.use_clamp = True

    invert_shadow_ray = node_tree.nodes.new('ShaderNodeMapRange')
    invert_shadow_ray.inputs['From Min'].default_value = 1.0
    invert_shadow_ray.inputs['From Max'].default_value = 0.0

    bypass = node_tree.nodes.new('ShaderNodeMath')
    bypass.operation = 'MULTIPLY'
    bypass.inputs[1].default_value = 0.0

    invert_bypass = node_tree.nodes.new('ShaderNodeMapRange')
    invert_bypass.inputs['From Min'].default_value = 1.0
    invert_bypass.inputs['From Max'].default_value = 0.0

    mult_alpha = node_tree.nodes.new('ShaderNodeMath')
    mult_alpha.operation = 'MULTIPLY'

    mix = node_tree.nodes.new("ShaderNodeMix")

    node_tree.links.new(light_path.outputs['Is Shadow Ray'], add_light.inputs[0])
    node_tree.links.new(light_path.outputs['Is Diffuse Ray'], add_light.inputs[1])

    node_tree.links.new(group_inputs.outputs['Mask'], mix.inputs['Factor'])

    node_tree.links.new(add_light.outputs['Value'], invert_shadow_ray.inputs['Value'])
    node_tree.links.new(invert_shadow_ray.outputs['Result'], mix.inputs['A'])

    node_tree.links.new(add_light.outputs['Value'], bypass.inputs[0])
    node_tree.links.new(bypass.outputs['Value'], invert_bypass.inputs['Value'])
    node_tree.links.new(invert_bypass.outputs['Result'], mult_alpha.inputs[0])
    node_tree.links.new(group_inputs.outputs['Alpha'], mult_alpha.inputs[1])
    node_tree.links.new(mult_alpha.outputs['Value'], mix.inputs['B'])

    node_tree.links.new(mix.outputs['Result'], group_outputs.inputs['Alpha'])

    return node_tree

def _unplug_socket_from_bsdf(material, socket_name):
    if not material.is_bf2_material:
        return None
    node_tree = material.node_tree
    for node_link in node_tree.links:
        node = node_link.to_node
        if node.type == 'BSDF_PRINCIPLED' and node_link.to_socket.name == socket_name:
            from_socket = node_link.from_socket
            node_tree.links.remove(node_link)
            return from_socket

def _plug_socket_to_bsdf(material, socket_name, from_socket):
    if not material.is_bf2_material:
        return
    node_tree = material.node_tree
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node_socket = node.inputs[socket_name]
            material.node_tree.links.new(from_socket, node_socket)

def _strip_prefix(s):
    for char_idx, _ in enumerate(s):
        if s[char_idx:].startswith('__'):
            return s[char_idx+2:]
    return s

def _gen_lm_key(geom_template_name, position, lod):
    x, y, z = [str(int(i)) for i in position]
    return '='.join([geom_template_name.lower(), f'{lod:02d}', x, z, y])

class ObjectBaker(BakerBase):
    def __init__(self, context, output_dir, dds_fmt='NONE', lod_mask=None,
                 only_selected=True, normal_maps=True, skip_existing=False,
                 reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self.lod_mask = lod_mask
        self.reporter = reporter
        self.normal_maps = normal_maps
        self.objects = list()

        self.existing_lods = set()
        if skip_existing:
            self.existing_lods = get_all_lightmap_files(output_dir)
            # TODO: filter terrain

        if only_selected:
            for obj in context.selected_objects:
                root_obj = find_root(obj)
                if root_obj not in self.objects:
                    self.objects.append(root_obj)
        elif 'StaticObjects' in context.scene.collection.children:
            for obj in context.scene.collection.children['StaticObjects'].objects:
                if obj.parent is None and obj.data is None:
                    self.objects.append(obj)

        self.total_count = len(self.objects)
        _setup_scene_for_baking(context)

    def _select_lod_for_bake(self, geom, lod):
        for lod_idx, lod_obj in enumerate(geom):
            if lod_idx == lod:
                lod_obj.hide_set(False)
                lod_obj.select_set(True)
                lod_obj.hide_render = False
            else:
                lod_obj.hide_set(True)
                lod_obj.select_set(False)
                lod_obj.hide_render = True

    def type(self):
        return 'Objects'

    def total_items(self):
        return self.total_count

    def completed_items(self):
        return self.total_count - len(self.objects)

    def bake_next(self, context):
        if not self.objects:
            return False

        for obj in context.selected_objects:
            obj.select_set(False)

        root_obj = self.objects.pop(0)

        print(f"Baking object {root_obj.name} {self.completed_items()}/{self.total_count}")
        try:
            geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
        except Exception as e:
            self.reporter.warning(f"Skipping bake for '{root_obj.name}': {e}")
            return True

        geom = geoms[0] # TODO: Geom1 support
        for lod_idx in range(len(geom)-1, -1, -1): # enum lods in reversed order
            lod_obj = geom[lod_idx]

            if self.lod_mask is not None and lod_idx not in self.lod_mask:
                continue
            mesh = lod_obj.data
            geom_temp_name = _strip_prefix(mesh.name)
            lm_name = _gen_lm_key(geom_temp_name, root_obj.matrix_world.translation, lod_idx)
            if lm_name in self.existing_lods:
                continue

            lm_size = tuple(lod_obj.bf2_lightmap_size)
            if lm_size == (0, 0):
                self.reporter.warning(f"skipping '{lod_obj.name}' because lightmap size is not set")
                continue

            if 'UV4' not in lod_obj.data.uv_layers:
                self.reporter.warning(f"skipping '{lod_obj.name}' because lightmap UV layer (UV4) is missing")
                continue

            # create bake image
            bake_image = bpy.data.images.get(lm_name)
            if bake_image:
                bpy.data.images.remove(bake_image)

            bake_image = bpy.data.images.new(name=lm_name, width=lm_size[0], height=lm_size[1])

            # add bake lightmap texture for each material
            normal_socket = None
            for material in lod_obj.data.materials:
                _setup_material_for_baking(material, bake_image)
                if not self.normal_maps:
                    normal_socket = _unplug_socket_from_bsdf(material, 'Normal')

            self._select_lod_for_bake(geom, lod_idx)
            bpy.ops.object.bake(type='DIFFUSE', uv_layer='UV4')
            self.save_bake(bake_image)
            bpy.data.images.remove(bake_image)

            if normal_socket:
                for material in lod_obj.data.materials:
                    _plug_socket_to_bsdf(material, 'Normal', normal_socket)
        return True

# -------------------
# scene setup
# -------------------

def _yaw_pitch_roll_to_matrix(rotation):
    rotation = tuple(map(lambda x: -math.radians(x), rotation))
    yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
    pitch = Matrix.Rotation(rotation[1], 4, 'X')
    roll  = Matrix.Rotation(rotation[2], 4, 'Y')
    return (yaw @ pitch @ roll)

def _get_templates(template, matrix, templates=None):
    if templates is None:
        templates = list()
    templates.append((template, matrix))
    template.add_bundle_childs()
    for child in template.children:
        if child.template is not None:
            child_matrix = _yaw_pitch_roll_to_matrix(child.rotation)
            child_matrix.translation = swap_zy(child.position)
            _get_templates(child.template, matrix @ child_matrix, templates)
    return templates

def _get_obj_matrix(bf2_object):
    if bf2_object.transform:
        # OG
        matrix_world = Matrix(bf2_object.transform)
        matrix_world.transpose()
        pos, rot, _ = matrix_world.decompose()
        _convert_pos(pos)
        _convert_rot(rot)
        return to_matrix(pos, rot)
    else:
        # statics
        matrix_world = _yaw_pitch_roll_to_matrix(bf2_object.rot)
        matrix_world.translation = swap_zy(bf2_object.absolute_pos)
        return matrix_world

def _make_collection(context, name):
    if name in bpy.data.collections:
        c = bpy.data.collections[name]
        return c
    else:
        c = bpy.data.collections.new(name)
        context.scene.collection.children.link(c)
        return c

DEFAULT_LM_SIZE_TO_SURFACE_AREA_THRESHOLDS = [
    {'size': 8, 'min_area': 0},
    {'size': 16, 'min_area': 4},
    {'size': 32, 'min_area': 8},
    {'size': 64, 'min_area': 16},
    {'size': 128, 'min_area': 32},
    {'size': 256, 'min_area': 256},
    {'size': 512, 'min_area': 1024},
    {'size': 1024, 'min_area': 2056}
]

def _calc_mesh_area(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    return area

def _load_heightmap(context, level_dir, water_attenuation):
    file_manager = BF2Engine().file_manager
    main_console = BF2Engine().main_console

    main_console.run_file(path.join(level_dir, 'Heightdata.con'))
    hm_cluster = BF2Engine().get_manager(HeightmapCluster).active_obj
    if not hm_cluster:
        return
    for heightmap in hm_cluster.heightmaps:
        if heightmap.cluster_offset == (0, 0): # load primary only
            break
    else:
        return
    
    heightmaps = _make_collection(context, "Heightmaps")

    location = hm_cluster.heightmap_size * Vector(heightmap.cluster_offset)
    data = file_manager.readFile(heightmap.raw_file, as_stream=True)
    terrain = import_heightmap_from(context, data, name=file_name(heightmap.raw_file),
                                    bit_res=heightmap.bit_res, scale=swap_zy(heightmap.scale))
    context.scene.collection.objects.unlink(terrain)
    heightmaps.objects.link(terrain)
    terrain.location.x = location.x
    terrain.location.y = location.y

    # enable smooth shading for the terrain
    context.view_layer.objects.active = terrain
    terrain.select_set(True)
    bpy.ops.object.shade_smooth()
    terrain.select_set(False)

    # load minimap as diffuse texture on primary heightmap and waterplane
    minimap_path = path.join(level_dir, 'Hud', 'Minimap', 'ingameMap.dds')
    material = _make_default_terrain_material(minimap_path)
    terrain.data.materials.append(material)

    material = _make_water_depth_material(hm_cluster.water_level, water_attenuation) 
    material.use_fake_user = True # will be used later

    modifier = terrain.modifiers.new(type='NODES', name="FlattenAtWaterLevel")
    modifier.node_group = _make_flatten_at_watter_level(hm_cluster.water_level)

def _match_config_pattern(value, config, prop, get_pattern=None):
    for prop_val in getattr(config, prop, []):
        if not prop_val:
            continue
        if get_pattern:
            pattern = get_pattern(prop_val)
        else:
            pattern = prop_val
        if fnmatch(value, pattern):
            return prop_val
    return None

class ObjectTemplateConfig:
    def __init__(self, template, geom, point_light_cfg=None):
        self.template : ObjectTemplate = template
        self.geom : GeometryTemplate = geom
        self.instances : List[Matrix] = list()
        self.point_light_cfg : Dict = point_light_cfg

class GeometryTemplateConfig:
    class Lod:
        def __init__(self, mesh, lm_size):
            self.mesh = mesh
            self.lm_size = lm_size

    class Geom:
        def __init__(self):
            self.lods = list()

    def __init__(self):
        self.geoms = list()

    def instantiate(self, collection, name):
        root = bpy.data.objects.new(name, None)
        root.hide_render = True
        collection.objects.link(root)
        root.hide_set(True)
        for geom_idx, geom in enumerate(self.geoms):
            geom_obj = bpy.data.objects.new(f'G{geom_idx}__' + name, None)
            geom_obj.parent = root
            geom_obj.hide_render = True
            collection.objects.link(geom_obj)
            geom_obj.hide_set(True)
            for lod_idx, lod_data in enumerate(geom.lods):
                lod_obj = bpy.data.objects.new(f'G{geom_idx}L{lod_idx}__' + name, lod_data.mesh)
                lod_obj.parent = geom_obj
                lod_obj.bf2_lightmap_size = lod_data.lm_size
                collection.objects.link(lod_obj)
                if lod_idx != 0:
                    lod_obj.hide_render = True
                    lod_obj.hide_set(True)
        return root

def _get_template_configs(template, matrix, config, templates : Dict[str, ObjectTemplateConfig], reporter):
    temp_cfg = templates.get(template.name.lower())
    if temp_cfg is None:
        template.add_bundle_childs() # resolve children
        geom_name = template.geom

        if (geom_name and
            _match_config_pattern(template.name, config, 'SKIP_OBJECT_TEMPLATES') or
            _match_config_pattern(template.location, config, 'SKIP_OBJECT_TEMPLATE_PATHS')):
            geom_name = None

        if geom_name:
            geom_manager = BF2Engine().get_manager(GeometryTemplate)
            geom = geom_manager.templates.get(geom_name.lower())
            if not geom:
                reporter.error(f"GeometryTemplate definition for '{geom_name}' not found")
        else:
            geom = None

        point_light_cfg = _match_config_pattern(template.name, config, 'LIGHT_SOURCES', lambda p: p['at'])
        temp_cfg = ObjectTemplateConfig(template, geom, point_light_cfg)
        templates[template.name.lower()] = temp_cfg

    temp_cfg.instances.append(matrix)

    # check children
    for child in template.children:
        if child.template is not None:
            child_matrix = _yaw_pitch_roll_to_matrix(child.rotation)
            child_matrix.translation = swap_zy(child.position)
            _get_template_configs(child.template, matrix @ child_matrix, config, templates, reporter)

def _do_material_tweaks(config, geom_temp_name, mesh, texture_paths, ray_vis_mask, reporter):
    for material in mesh.materials:
        modified = False
        backface_cull = True
        if _match_config_pattern(geom_temp_name, config, 'FORCE_TWO_SIDED'):
            backface_cull = False
            modified = True

        alpha_mode = None
        ray_mask = None
        for name, path in get_material_maps(material).items():
            if name not in ('Base', 'Detail', 'Dirt', 'Crack'):
                continue

            replace_cfg = _match_config_pattern(path, config, 'TEXTURE_REPLACE', lambda p: p['from'])
            if not replace_cfg:
                continue

            if alpha_mode and replace_cfg.get('alpha_mode', alpha_mode) != alpha_mode:
                raise RuntimeError(f"Bad config, texture replace results in conflicting `alpha_mode`s on '{mesh.name}'")

            alpha_mode = replace_cfg.get('alpha_mode', None)
            if alpha_mode == 'RAY_MASK':
                ray_mask = replace_cfg['to']
                continue

            material.is_bf2_material = False # temporarily disable so update() doesn't trigger
            index = STATICMESH_TEXUTRE_MAP_TYPES.index(name)
            setattr(material, f"texture_slot_{index}", replace_cfg['to'])
            if alpha_mode == 'ALPHA_TEST':
                material.bf2_alpha_mode = 'ALPHA_TEST'
            material.is_bf2_material = True

            reporter.info(f"Replaced texture '{path}' for '{mesh.name}' as requested")
            modified = True

        if modified:
            setup_material(material, texture_paths=texture_paths, reporter=reporter, backface_cull=backface_cull) # re-apply

        if ray_mask:
            tex_node = _add_texture_node(material, ray_mask, texture_paths, reporter)
            node_tree = material.node_tree
            ray_vis_mask_node = node_tree.nodes.new('ShaderNodeGroup')
            ray_vis_mask_node.node_tree = ray_vis_mask
            alpha_socket = _unplug_socket_from_bsdf(material, 'Alpha')
            node_tree.links.new(alpha_socket, ray_vis_mask_node.inputs['Alpha'])
            _plug_socket_to_bsdf(material, 'Alpha', ray_vis_mask_node.outputs['Alpha'])
            node_tree.links.new(tex_node.outputs['Alpha'], ray_vis_mask_node.inputs['Mask'])
            reporter.info(f"Added ray mask '{path}' for '{mesh.name}' as requested")

def _get_lm_size_thresholds(config, reporter):
    lm_size_thresholds = list()
    for t in getattr(config, 'LIGHTMAP_SIZE_TO_SURFACE_AREA_THRESHOLDS', DEFAULT_LM_SIZE_TO_SURFACE_AREA_THRESHOLDS):
        lm_size_thresholds.append((t['size'], t['min_area']))
    lm_size_thresholds.sort(key=lambda x: x[0])
    if lm_size_thresholds:
        _, prev_thresh = lm_size_thresholds[0]
        if prev_thresh != 0:
            reporter.error(f"LIGHTMAP_SIZE_TO_SURFACE_AREA_THRESHOLDS: Surface area thresholds must be starting from zero")
            return None
        for _, thresh in lm_size_thresholds[1:]:
            if thresh <= prev_thresh:
                reporter.error(f"LIGHTMAP_SIZE_TO_SURFACE_AREA_THRESHOLDS: Lightmap sizes and threshold must be sorted in ascending order")
                return None
            prev_thresh = thresh
    return lm_size_thresholds

def _run_all_con_files(root_dir):
    if not path.isdir(root_dir):
        return
    main_console = BF2Engine().main_console
    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith('.con'):
                main_console.run_file(os.path.join(root, filename))

def load_level(context, level_dir, use_cache=True,
               load_unpacked=True, load_static_objects=True,
               load_overgrowth=True, load_heightmap=True, load_lights=True,
               water_attenuation=0.1, texture_paths=[], max_lod_to_load=None,
               config=None, config_file='', reporter=DEFAULT_REPORTER):

    level_dir = level_dir.rstrip('/').rstrip('\\')
    mod_dir = path.normpath(path.join(level_dir, '..', '..'))

    if config_file and path.isfile(config_file):
        config = module_from_file(config_file)

    lm_size_thresholds = _get_lm_size_thresholds(config, reporter)
    ray_vis_mask = _make_ray_visibility_mask()

    if not load_unpacked:
        mod_loader = ModLoader(mod_dir, use_cache)
        mod_loader.reload_all()
    else:
        BF2Engine().shutdown()
        if not any([mod_dir.lower() == t.rstrip('/').rstrip('\\').lower() for t in texture_paths]):
            texture_paths.append(mod_dir)
        texture_paths.append(level_dir) # for objects inside levels dir
        BF2Engine().file_manager.root_dirs = texture_paths
        _run_all_con_files(os.path.join(mod_dir, 'objects'))
        _run_all_con_files(os.path.join(level_dir, 'objects'))

    file_manager = BF2Engine().file_manager
    main_console = BF2Engine().main_console

    def report_cb(con_file, line_no, line, what):
        if line.lower().startswith('object.create'):
            reporter.warning(f'{con_file}:{line_no}:{line}: {what}')

    main_console.report_cb = report_cb

    # mount level archives
    if not load_unpacked:
        file_manager.mountArchive(path.join(level_dir, 'client.zip'), level_dir)
        file_manager.mountArchive(path.join(level_dir, 'server.zip'), level_dir)

    # load statics & OG
    if load_static_objects or load_overgrowth:
        # load mapside object templates if exist
        if not load_unpacked:
            try:
                main_console.run_file(path.join(level_dir, 'serverarchives.con'))
                mod_loader.load_objects(levels_only=True)
            except FileManagerFileNotFound:
                pass

        if load_static_objects:
            main_console.run_file(path.join(level_dir, 'StaticObjects.con'))

        if load_overgrowth:
            main_console.run_file(path.join(level_dir, 'Overgrowth', 'OvergrowthCollision.con'))

    # collect template configs recursively
    templates : Dict[str, ObjectTemplateConfig] = dict()
    for obj in BF2Engine().get_manager(Object).objects:
        _get_template_configs(obj.template, _get_obj_matrix(obj), config, templates, reporter)

    # load meshes
    if not load_unpacked:
        main_console.run_file('clientarchives.con')
        try:
            main_console.run_file(path.join(level_dir, 'clientarchives.con'))
        except FileManagerFileNotFound:
            pass

    static_objects = _make_collection(context, "StaticObjects")
    static_objects_skip = _make_collection(context, "StaticObjects_SkipLightmaps")
    lm_keys = set()
    geom_template_to_mesh : Dict[str, GeometryTemplateConfig] = dict() # differen ObjectTemplates may use same GeometryTemplate

    for template_name, temp_cfg in templates.items():
        geom_temp = temp_cfg.geom
        if not geom_temp:
            continue # skip, just for point lights

        mesh_info = geom_template_to_mesh.get(geom_temp.name.lower())
        if not mesh_info:
            mesh_info = GeometryTemplateConfig()
            geom_template_to_mesh[geom_temp.name.lower()] = mesh_info

            data = file_manager.readFile(geom_temp.location, as_stream=True)
            mesh_type = MESH_TYPES.get(geom_temp.geometry_type)
            if not mesh_type:
                reporter.warning(f"skipping '{template_name}' as it is not supported mesh type {geom_temp.geometry_type}")
                continue
            try:
                bf2_mesh = mesh_type.load_from(geom_temp.name.lower(), data)
            except Exception as e:
                reporter.error(f"Failed to load mesh '{geom_temp.location}', the file might be corrupted: {e}")
                continue

            del bf2_mesh.geoms[1:] # TODO: Geom1 support
            if max_lod_to_load is not None:
                bf2_mesh.geoms[0].lods = bf2_mesh.geoms[0].lods[0:max_lod_to_load+1]

            if not load_unpacked:
                raise NotImplementedError() # TODO: texture load from FileManager

            importer = MeshImporter(context, geom_temp.location, loader=lambda: bf2_mesh, texture_paths=texture_paths, reporter=reporter, silent=True)
            try:
                mesh_obj = importer.import_mesh()
            except ImportException as e:
                reporter.error(f"Failed to import mesh '{geom_temp.location}': {e}")
                continue

            # determine samples size
            meshes_dir = path.dirname(geom_temp.location)
            geoms = MeshExporter.collect_geoms_lods(mesh_obj, skip_checks=True)
            lod0_lm_size = None
            MIN_LM_SIZE = 8
            geom_info = GeometryTemplateConfig.Geom() # TODO: Geom1 support
            mesh_info.geoms.append(geom_info)
            for lod_idx, lod_obj in enumerate(geoms[0]): # TODO: Geom1 support
                lm_size = None

                if lod_idx == 0:
                    fname = path.join(meshes_dir, geom_temp.name + '.samples')
                else:
                    fname = path.join(meshes_dir, geom_temp.name + f'.samp_{lod_idx:02d}')

                if load_unpacked:
                    if path.isfile(fname):
                        with open(fname, "rb") as f:
                            lm_size = BF2Samples.read_map_size_from(f)
                else:
                    raise NotImplementedError() # TODO

                if lm_size is None:
                    if lod0_lm_size is not None:
                        # halve the LOD0 size
                        lm_size = [max(int(i / (2**lod_idx)), MIN_LM_SIZE) for i in lod0_lm_size]
                    else:
                        # guess using surface area of the mesh
                        mesh_area = _calc_mesh_area(lod_obj.data)
                        if not lm_size_thresholds:
                            reporter.warning(f"Cannot determine LM size for mesh '{geom_temp.name}', .samples file not found and LIGHTMAP_SIZE_TO_SURFACE_AREA_THRESHOLDS is empty")
                            lm_size = (0, 0)
                        else: 
                            for lms, min_area in reversed(lm_size_thresholds):
                                if mesh_area >= min_area:
                                    lm_size = (lms, lms)
                                    break
                if lm_size is None:
                    lm_size = (MIN_LM_SIZE, MIN_LM_SIZE)
                if lod_idx == 0:
                    lod0_lm_size = lm_size

                lod_info = GeometryTemplateConfig.Lod(lod_obj.data, lm_size)
                geom_info.lods.append(lod_info)

            # do material tweaks
            if 'StaticMesh' == geom_temp.geometry_type:
                for lod_idx, lod_obj in enumerate(geoms[0]): # TODO: Geom1 support
                    _do_material_tweaks(config, geom_temp.name, lod_obj.data, texture_paths, ray_vis_mask, reporter)

            # delete source objects, keep mesh instances
            delete_object(mesh_obj, remove_data=False)

        # instantiate meshes
        skip_lightmaps = geom_temp.dont_generate_lightmaps or 'StaticMesh' != geom_temp.geometry_type
        for matrix_world in temp_cfg.instances:
            # XXX: objects will be named by ObjectTemplate
            # and meshes will be named by GeometryTemplate
            # which is not always the same!
            collection = static_objects_skip if skip_lightmaps else static_objects
            obj = mesh_info.instantiate(collection, temp_cfg.template.name)
            obj.matrix_world = matrix_world

            # check LM key collisions
            if not skip_lightmaps:
                lm_key = _gen_lm_key(geom_temp.name, obj.matrix_world.translation, lod_idx)
                if lm_key in lm_keys:
                    reporter.warning(f"Object '{obj.name}' is too close to another which will result in both having the same lightmap filenames!")
                lm_keys.add(lm_key)

    if load_heightmap:
        _load_heightmap(context, level_dir, water_attenuation)

    if load_lights:
        lights = _make_collection(context, "Lights")

        # sun (green channel)
        main_console.run_file(path.join(level_dir, 'Sky.con'))
        sun_dir = Vector(BF2Engine().light_manager.sun_dir)
        _convert_pos(sun_dir)
        sun_light = bpy.data.lights.new(name='Sun', type='SUN')
        obj = bpy.data.objects.new(sun_light.name, sun_light)
        lights.objects.link(obj)
        sun_dir.z = -sun_dir.z # points down
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = sun_dir.rotation_difference(Vector((0, 0, 1)))

        sin_alpha = abs(sun_dir.z)
        sun_light.energy = (1 + 0.5 * sin_alpha) * 4 # TODO strength
        sun_light.color = (0, 1, 0)

        # skylight / soft shadows (blue channel)
        if "SkyLight" in bpy.data.worlds:
            world = bpy.data.worlds["SkyLight"]
            bpy.data.worlds.remove(world)
        context.scene.world = bpy.data.worlds.new("SkyLight")
        background = context.scene.world.node_tree.nodes["Background"]
        background.inputs['Color'].default_value = (0, 0, 1, 1)
        background.inputs['Strength'].default_value = 1.4 # TODO strength

        COLOR_MAP = {'red': (1, 0, 0), 'green': (0, 1, 0), 'blue': (0, 0, 1)}

        # point lights (red channel)
        for temp_cfg in templates.values():
            if not temp_cfg.point_light_cfg:
                continue

            point_light = bpy.data.lights.new(name=temp_cfg.template.name, type='POINT')
            point_light.energy = temp_cfg.point_light_cfg.get('intensity', 100.0)
            point_light.shadow_soft_size = temp_cfg.point_light_cfg.get('radius', 0.0)
            point_light.color = COLOR_MAP[temp_cfg.point_light_cfg.get('color', 'red')]

            offset = Vector(temp_cfg.point_light_cfg.get('offset', (0, 0, 0)))
            for matrix_world in temp_cfg.instances:
                om = Matrix.Identity(4)
                om.translation = offset
                obj = bpy.data.objects.new(point_light.name, point_light)
                lights.objects.link(obj)
                obj.matrix_world = matrix_world @ om
