import os
import os.path as path
import math
import re
import bpy # type: ignore
from abc import ABC, abstractmethod
from array import array

from .... import rectpack
from ...mesh import MeshExporter
from ...utils import (DEFAULT_REPORTER,
                    save_img_as_dds, find_root,
                    is_pow_two, obj_bounds,
                    strip_geom_lod_prefix as strip_prefix)
from .common import plug_socket_to, unplug_socket_from, gen_lm_key

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

    def bake_next(self, context):
        if not self.prepare_next(context):
            return False
        bpy.ops.object.bake(**self.get_bake_params())
        self.complete_bake(context, False)
        return True

    def save_bake(self, image, name=''):
        if not name:
            name = image.name
        save_img_as_dds(image, path.join(self.output_dir, f'{name}.dds'), self.dds_fmt)

    def bake_all(self, context):
        while self.bake_next(context):
            pass

    def cleanup(self, context):
        pass

def _setup_scene_for_baking(context):
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.bake_type = 'DIFFUSE'
    context.scene.render.image_settings.file_format = 'TARGA'
    context.scene.render.bake.use_pass_direct = True
    context.scene.render.bake.use_pass_indirect = True
    context.scene.render.bake.use_pass_color = False

def check_gpu(context):
    if not context.scene.cycles.denoising_use_gpu:
        yield "'Use GPU' is disabled in 'Denoiser' settings"
    if context.scene.cycles.device != 'GPU':
        yield f"Device is configured to '{context.scene.cycles.device}' instead of the 'GPU' in render settings"
    else:
        cycles = context.preferences.addons.get('cycles')
        if cycles and hasattr(cycles.preferences, 'compute_device_type') and cycles.preferences.compute_device_type == 'NONE':
            yield f"Cycles compute device type is set to 'NONE' in system preferences"

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

def _make_add_ambient_light(ambient_light_level):
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
    def __init__(self, context, src_dir, out_dir='', ambient_light_intensity=0.5, dds_fmt='NONE'):
        if 'Render Result' in bpy.data.images:
            render_result = bpy.data.images['Render Result']
            bpy.data.images.remove(render_result)

        if not out_dir:
            out_dir = src_dir

        self.dds_fmt = dds_fmt
        self.add_ambient_light = _make_add_ambient_light(ambient_light_intensity)
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
            context.scene.render.image_settings.file_format = 'TARGA'
            bpy.ops.render.render()

            # save output
            render_result = bpy.data.images['Render Result']
            save_img_as_dds(render_result, path.join(self.out_dir, path.basename(filepath)), self.dds_fmt)

            # cleanup
            self.add_ambient_light.nodes['SrcImage'].image = None
            bpy.data.images.remove(image)
            bpy.data.images.remove(render_result)
        
        return True

    def process_all(self, context):
        while self.process_next(context):
            pass

def get_all_lightmap_files(dir, pattern):
    files = set()
    for file in os.listdir(dir):
        if not file.endswith(".dds"):
            continue
        if not re.match(pattern, file):
            continue
        files.add(file[:-4])
    return files

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
                 water_attenuation=0.15, reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self._reporter = reporter

        self._terrain = find_heightmap(context)
        if not self._terrain:
            raise RuntimeError(f'Heightmap object not found')

        if patch_count is None or patch_size is None:
            hm_size = get_heightmap_size(self._terrain)
            if hm_size is None:
                raise RuntimeError(f'Cannot determine heightmap size')
            if hm_size not in DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES:
                raise RuntimeError(f'Cannot determine default values for patch_count and patch_size')
            patch_count, patch_size = DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES[hm_size]

        grid_size = math.isqrt(patch_count)
        if grid_size * grid_size != patch_count:
            raise RuntimeError(f'patch_count must be a power of 4')

        self.patches_to_bake = list()
        if skip_existing:
            existing_patches = get_all_lightmap_files(output_dir, r'tx\d{2}x\d{2}')
            for col in range(grid_size):
                for row in range(grid_size):
                    name = f'tx{col:02d}x{row:02d}'
                    print(f"{name} exists, skipping")
                    if name not in existing_patches:
                        self.patches_to_bake.append((col, row))
        else:
            for col in range(grid_size):
                for row in range(grid_size):
                    self.patches_to_bake.append((col, row))
        self._patch_index = 0
        self._patch_size = patch_size
        self._patch_count = patch_count

        mesh = self._terrain.data
        vert_count = math.isqrt(len(mesh.vertices))
        if vert_count * vert_count != len(mesh.vertices) or not is_pow_two(vert_count - 1):
            raise RuntimeError(f'heightmap vert count is invalid')

        self._default_terrain_mat = bpy.data.materials['DefaultTerrain']
        self._water_depth_mat = bpy.data.materials['WaterDepth']
        self._flatten_water_mod = self._terrain.modifiers['FlattenAtWaterLevel']
        self._terrain['water_attenuation'] = water_attenuation # referenced by the shader

        self._combine_channels = _make_combine_channels()
        context.scene.compositing_node_group = self._combine_channels

        mesh.materials.clear()
        mesh.materials.append(self._default_terrain_mat)

        # we gon simply scale the UV up so the 0-1 range fits one whole patch
        # then shift the UV when rendering the grid
        mesh.uv_layers.active = mesh.uv_layers['UVMap']
        self.uv_layer = mesh.uv_layers.new(name='LightmapBakeUV')

        tmp = len(self.uv_layer.data) * 2 * [None]
        self.uv_layer.data.foreach_get('uv', tmp)

        def do_scale_and_offset(i, value):
            if i % 2 == 0:
                return grid_size * value
            else:
                return 1 - grid_size * value
        self.uv_layer.data.foreach_set('uv', [do_scale_and_offset(i, value) for i, value in enumerate(tmp)])

        self._texture_node_light = _setup_material_for_baking(self._default_terrain_mat, uv=self.uv_layer.name)
        self._texture_node_water_depth = _setup_material_for_baking(self._water_depth_mat, uv=self.uv_layer.name)
        self._is_water_pass = False

        _setup_scene_for_baking(context)

        # cleanup possible lefover render result
        if 'Render Result' in bpy.data.images:
            render_result = bpy.data.images['Render Result']
            bpy.data.images.remove(render_result)


    def _skipped_patches(self):
        return self._patch_count - len(self.patches_to_bake)

    def type(self):
        return 'Terrain'

    def total_items(self):
        return self._patch_count

    def completed_items(self):
        return self._patch_index  + self._skipped_patches()

    def cleanup(self, context):
        mesh = self._terrain.data
        context.scene.compositing_node_group = None
        mesh.materials[0] = self._default_terrain_mat
        mesh.uv_layers.remove(self.uv_layer)
        if self._texture_node_light.image:
            bpy.data.images.remove(self._texture_node_light.image)
        if self._texture_node_water_depth.image:
            bpy.data.images.remove(self._texture_node_water_depth.image)

    def _setup_next_patch(self, context):
        if self._patch_index >= len(self.patches_to_bake):
            return False

        if self._is_water_pass:
            return True # skip, was set up already before light pass

        for obj in context.selected_objects:
            obj.select_set(False)

        context.view_layer.objects.active = self._terrain
        self._terrain.hide_set(False)
        self._terrain.select_set(True)
        self._terrain.hide_render = False

        print(f"Baking terrain patch {self.completed_items() + 1}/{self.total_items()}")

        col, row = self.patches_to_bake[self._patch_index]
        if self._patch_index == 0:
            prev_col = 0
            prev_row = 0
        else:
            prev_col, prev_row = self.patches_to_bake[self._patch_index - 1]

        u_offset = col - prev_col
        v_offset = row - prev_row

        _offset_uvs(self.uv_layer, -u_offset, v_offset)
        return True

    def _combine_passes(self, context):
        light_map = self._texture_node_light.image
        water_depth_map = self._texture_node_water_depth.image
        assert light_map and water_depth_map

        with PreserveColorSpaceSettings(context):
            context.scene.view_settings.view_transform = 'Standard'
            self._combine_channels.nodes['LightMap'].image = light_map
            self._combine_channels.nodes['WaterDepthMap'].image = water_depth_map
            context.scene.render.resolution_x = self._patch_size
            context.scene.render.resolution_y = self._patch_size
            bpy.ops.render.render()

            render_result = bpy.data.images['Render Result']

            col, row = self.patches_to_bake[self._patch_index]
            self.save_bake(render_result, f'tx{col:02d}x{row:02d}')

            # cleanup
            self._combine_channels.nodes['LightMap'].image = None
            self._combine_channels.nodes['WaterDepthMap'].image = None
            self._texture_node_light.image = None
            self._texture_node_water_depth.image = None
            bpy.data.images.remove(light_map)
            bpy.data.images.remove(water_depth_map)
            bpy.data.images.remove(render_result)

    def get_bake_params(self):
        return {'type': 'DIFFUSE', 'uv_layer': self.uv_layer.name}

    def prepare_next(self, context):
        mesh = self._terrain.data

        if not self._setup_next_patch(context):
            self.cleanup(context)
            return False

        if not self._is_water_pass:
            self._texture_node_light.image = bpy.data.images.new(
                name='TerrainLightmapBakeImageLight',
                width=self._patch_size, height=self._patch_size)

            self._flatten_water_mod.show_render = True
            mesh.materials[0] = self._default_terrain_mat

            context.scene.render.bake.use_pass_direct = True
            context.scene.render.bake.use_pass_indirect = True
            context.scene.render.bake.use_pass_color = False
        else:
            self._texture_node_water_depth.image = bpy.data.images.new(
                name='TerrainLightmapBakeImageWaterDepth',
                width=self._patch_size, height=self._patch_size)

            self._flatten_water_mod.show_render = False
            mesh.materials[0] = self._water_depth_mat

            context.scene.render.bake.use_pass_direct = False
            context.scene.render.bake.use_pass_indirect = False
            context.scene.render.bake.use_pass_color = True

        return True

    def complete_bake(self, context, canceled):
        if canceled:
            return

        if self._is_water_pass:
            self._combine_passes(context)
            self._patch_index += 1
            self._is_water_pass = False
        else:
            self._is_water_pass = True

# -------------------
# baking objects
# -------------------

class StripNormalMaps:
    def __init__(self):
        self.materials = list()
        self.normal_sockets = list()

    def apply(self, materials):
        self.materials = materials
        for material in self.materials:
            self.normal_sockets.append(unplug_socket_from(material, 'Normal'))

    def revert(self):
        for normal_socket, material in zip(self.normal_sockets, self.materials):
            if normal_socket:
                plug_socket_to(material, 'Normal', normal_socket)

class ObjectBaker(BakerBase):
    def __init__(self, context, output_dir, dds_fmt='NONE',
                 only_selected=False, normal_maps=False, skip_existing=False,
                 max_lod=99, reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self._reporter = reporter
        self._strip_normal_maps = None if normal_maps else StripNormalMaps()
        self._max_lod = max_lod
        self._objects = list()

        self._existing_lods = set()
        if skip_existing:
            self._existing_lods = get_all_lightmap_files(output_dir, r'.*=\d{2}=-?\d+=-?\d+=-?\d+')

        if only_selected:
            for obj in context.selected_objects:
                root_obj = find_root(obj)
                if root_obj not in self._objects:
                    self._objects.append(root_obj)
        elif 'StaticObjects' in context.scene.collection.children:
            for obj in context.scene.collection.children['StaticObjects'].objects:
                if obj.parent is None and obj.data is None:
                    self._objects.append(obj)

        self._objects.sort(key=lambda o: o.name)
        self._total_count = len(self._objects)

        self._lod_idx = -1
        self._geom = None
        self._bake_image = None
        self._snm = None

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
        return self._total_count

    def completed_items(self):
        return self._total_count - len(self._objects)

    def cleanup(self, context):
        if not self._geom:
            return
        self._select_lod_for_bake(self._geom, 0)

    def get_bake_params(self):
        return {'type': 'DIFFUSE', 'uv_layer': 'UV4'}

    def prepare_next(self, context):
        for obj in context.selected_objects:
            obj.select_set(False)

        if self._lod_idx < 0:
            # switch to new object
            if not self._objects:
                self.cleanup(context)
                return False

            root_obj = self._objects[0]
            try:
                geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
            except Exception as e:
                self._reporter.warning(f"Skipping bake for '{root_obj.name}': {e}")
                return self.prepare_next(context)

            self._geom = geoms[0] # TODO: Geom1
            self._lod_idx = len(self._geom) - 1

            print(f"Baking object {root_obj.name} {self.completed_items()}/{self._total_count}")
        else:
            root_obj = self._objects[0]

        while self._lod_idx >= 0:
            if self._lod_idx > self._max_lod:
                self._lod_idx -= 1
                continue

            lod_obj = self._geom[self._lod_idx]
            mesh = lod_obj.data
            geom_temp_name = strip_prefix(mesh.name)
            lm_name = gen_lm_key(geom_temp_name, root_obj.matrix_world.translation, self._lod_idx)

            if lm_name in self._existing_lods:
                self._lod_idx -= 1
                continue

            lm_size = tuple(lod_obj.bf2_lightmap_size)
            if lm_size == (0, 0):
                self._reporter.warning(f"skipping '{lod_obj.name}' because lightmap size is not set")
                self._lod_idx -= 1
                continue

            if 'UV4' not in lod_obj.data.uv_layers:
                self._reporter.warning(f"skipping '{lod_obj.name}' because lightmap UV layer (UV4) is missing")
                self._lod_idx -= 1
                continue

            bake_image = bpy.data.images.get(lm_name)
            if bake_image:
                bpy.data.images.remove(bake_image)
            self._bake_image = bpy.data.images.new(name=lm_name, width=lm_size[0], height=lm_size[1])

            for material in lod_obj.data.materials:
                _setup_material_for_baking(material, self._bake_image)

            if self._strip_normal_maps:
                self._strip_normal_maps.apply(lod_obj.data.materials)

            self._select_lod_for_bake(self._geom, self._lod_idx)
            context.view_layer.objects.active = lod_obj
            return True

        return self.prepare_next(context)

    def complete_bake(self, context, canceled):
        if self._strip_normal_maps:
            self._strip_normal_maps.revert()
            self._strip_normal_maps = None

        if not canceled:
            self.save_bake(self._bake_image)

        bpy.data.images.remove(self._bake_image)
        self._bake_image = None

        self._lod_idx -= 1
        if self._lod_idx < 0:
            self._objects.pop(0)
            self._geom = None


class ObjectParallelBaker(BakerBase):
    """
    Object baker that bakes multiple objects at once into an atlas to better utilize GPU
    """
    def __init__(self, context, output_dir, dds_fmt='NONE',
                 only_selected=False, normal_maps=False, atlas_size=(2048, 2048),
                 max_lod=99, skip_existing=None, reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self._reporter = reporter
        self._strip_normal_maps = None if normal_maps else StripNormalMaps()
        self._max_lod = max_lod
        self._atlas_size = atlas_size

        existing_lods = set()
        if skip_existing:
            existing_lods = get_all_lightmap_files(output_dir, r'.*=\d{2}=-?\d+=-?\d+=-?\d+')

        objects = list()
        if only_selected:
            for obj in context.selected_objects:
                root_obj = find_root(obj)
                if root_obj not in objects:
                    objects.append(root_obj)
        elif 'StaticObjects' in context.scene.collection.children:
            for obj in context.scene.collection.children['StaticObjects'].objects:
                if obj.parent is None and obj.data is None:
                    objects.append(obj)

        objects.sort(key=lambda o: o.name)

        # filter LODs
        self._lod_to_geom = dict()
        self._lod_to_objects = dict()
        self._lod_to_lm_key = dict()
        for root_obj in objects:
            try:
                geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
            except Exception as e:
                self._reporter.warning(f"Skipping bake for '{root_obj.name}': {e}")
                continue

            geom = geoms[0] # TODO: Geom1 support
            for lod_idx, lod_obj in enumerate(geom):
                if lod_idx > self._max_lod:
                    continue

                mesh = lod_obj.data
                geom_temp_name = strip_prefix(mesh.name)
                lm_name = gen_lm_key(geom_temp_name, root_obj.matrix_world.translation, lod_idx)
                if lm_name in existing_lods:
                    continue

                lm_size = tuple(lod_obj.bf2_lightmap_size)
                if lm_size == (0, 0):
                    self._reporter.warning(f"skipping '{lod_obj.name}' because lightmap size is not set")
                    continue

                if 'UV4' not in lod_obj.data.uv_layers:
                    self._reporter.warning(f"skipping '{lod_obj.name}' because lightmap UV layer (UV4) is missing")
                    continue

                self._lod_to_objects.setdefault(lod_idx, list()).append(lod_obj)
                self._lod_to_geom[lod_obj.name] = geom
                self._lod_to_lm_key[lod_obj.name] = lm_name

        # generate atlases
        # LODs of a single object cannot be on the same atlas
        # and to get best quality atlases will get split per LOD
        self._atlases = list()
        for lod_idx, objects in self._lod_to_objects.items():
            packer = rectpack.newPacker(rotation=False)

            for obj in objects:
                width, height = obj.bf2_lightmap_size
                packer.add_rect(width, height, obj)

            for _ in range(0, 99):
                packer.add_bin(*self._atlas_size)

            packer.pack()

            for bin in packer:
                self._atlases.append(bin)

        self._total_count = len(self._atlases)

        self._bake_image = None
        self._temp_obj = None
        self._snm = None

        _setup_scene_for_baking(context)

    def _select_lod_for_bake(self, lod_obj, lod):
        geom = self._lod_to_geom[lod_obj.name]
        for lod_idx, lod_obj in enumerate(geom):
            if lod_idx == lod:
                lod_obj.hide_set(False)
                lod_obj.select_set(True)
                lod_obj.hide_render = False
            else:
                lod_obj.hide_set(True)
                lod_obj.select_set(False)
                lod_obj.hide_render = True

    def _apply_uv_offset_and_scale(self, mesh, scale_u, scale_v, offset_u, offset_v):
            # get applied scale/offset
            bf2_lm_uv_scale = mesh.get('bf2_lm_uv_scale', (1.0, 1.0))
            bf2_lm_uv_offset = mesh.get('bf2_lm_uv_offset', (0.0, 0.0))

            # calc relative scale/offset
            scale_u /= bf2_lm_uv_scale[0]
            scale_v /= bf2_lm_uv_scale[1]
            offset_u -= bf2_lm_uv_offset[0]
            offset_v -= bf2_lm_uv_offset[1]

            uv_layer = mesh.uv_layers['UV4']
            uv_buf = len(uv_layer.data) * 2 * [None]
            uv_layer.data.foreach_get('uv', uv_buf)
            def do_scale_and_offset(i, value):
                if i % 2 == 0:
                    return (value % 1.0) * scale_u + offset_u
                else:
                    return (value % 1.0) * scale_v + offset_v
            uv_layer.data.foreach_set('uv', [do_scale_and_offset(i, value) for i, value in enumerate(uv_buf)])

            # mark as modified
            mesh['bf2_lm_uv_scale'] = (scale_u, scale_v)
            mesh['bf2_lm_uv_offset'] = (offset_u, offset_v)

    def type(self):
        return 'Objects'

    def total_items(self):
        return self._total_count

    def completed_items(self):
        return self._total_count - len(self._atlases)

    def get_bake_params(self):
        return {'type': 'DIFFUSE', 'uv_layer': 'UV4'}

    def prepare_next(self, context):
        if not self._atlases:
            return False

        atlas_index = self.completed_items()
        atlas_name = f'LightmapAtlas{atlas_index}'
        atlas = self._atlases[0]

        print(f"Preparing atlas {atlas_name} {self.completed_items() + 1}/{self.total_items()}")

        bpy.ops.object.select_all(action='DESELECT')

        for rect in atlas:
            obj = rect.rid.copy()
            context.scene.collection.objects.link(obj)
            obj.hide_set(False)
            obj.select_set(True)
            obj.hide_render = False
            obj.data = obj.data.copy()

            mesh = obj.data
            scale_u = rect.width / self._atlas_size[0]
            scale_v = rect.height / self._atlas_size[1]
            offset_u = rect.x / self._atlas_size[0]
            offset_v = rect.y / self._atlas_size[1]
            self._apply_uv_offset_and_scale(mesh, scale_u, scale_v, offset_u, offset_v)

        temp_mesh = bpy.data.meshes.new(atlas_name)
        self._temp_obj = bpy.data.objects.new(atlas_name, temp_mesh)
        context.scene.collection.objects.link(self._temp_obj)
        bpy.context.view_layer.objects.active = self._temp_obj
        self._temp_obj.select_set(True)
        bpy.ops.object.join()
        temp_mesh.uv_layers.active = temp_mesh.uv_layers['UV4']
        if temp_mesh.materials[0] is None:
            temp_mesh.materials.pop(index=0)

        for rect in atlas:
            self._select_lod_for_bake(rect.rid, -1)

        bake_image = bpy.data.images.get(atlas_name)
        if bake_image:
            bpy.data.images.remove(bake_image)
        self._bake_image = bpy.data.images.new(
            name=atlas_name, width=self._atlas_size[0], height=self._atlas_size[1])

        for material in temp_mesh.materials:
            _setup_material_for_baking(material, self._bake_image)

        if self._strip_normal_maps:
            self._strip_normal_maps.apply(temp_mesh.materials)

        return True

    def complete_bake(self, context, canceled):
        if self._strip_normal_maps:
            self._strip_normal_maps.revert()
            self._strip_normal_maps = None

        bpy.data.meshes.remove(self._temp_obj.data, do_unlink=True)
        self._temp_obj = None

        atlas_index = self.completed_items()
        atlas_name = f'LightmapAtlas{atlas_index}'
        atlas = self._atlases.pop(0)

        # revert objects to lod 0
        for rect in atlas:
            self._select_lod_for_bake(rect.rid, 0)

        if not canceled:
            print(f"Splitting atlas {atlas_name} {self.completed_items()}/{self.total_items()}")

            src_img = self._bake_image
            atlas_width, atlas_height = src_img.size
            num_channels = src_img.channels
            src_pixels = array('f', src_img.pixels[:])

            for rect in atlas:
                lm_name = self._lod_to_lm_key[rect.rid.name]
                tile_img = bpy.data.images.new(
                    name=lm_name, width=rect.width, height=rect.height)
                w, h = tile_img.size
                tile_pixels = array('f')
                for row in range(h):
                    src_row_start = ((rect.y + row) * atlas_width + rect.x) * num_channels
                    src_row_end = src_row_start + (w * num_channels)
                    tile_pixels.extend(src_pixels[src_row_start:src_row_end])
                tile_img.pixels = tile_pixels.tolist()

                self.save_bake(tile_img)
                bpy.data.images.remove(tile_img)

        bpy.data.images.remove(self._bake_image)
        self._bake_image = None
