import os
import os.path as path
import math
import tempfile
import bpy # type: ignore
from abc import ABC, abstractmethod
import numpy as np

from .... import rectpack
from ...mesh import MeshExporter
from ...utils import (DEFAULT_REPORTER,
                    convert_to_dds, file_name,
                    save_img_as_dds, find_root,
                    is_pow_two, obj_bounds,
                    strip_geom_lod_prefix as strip_prefix)
from .common import plug_socket_to, unplug_socket_from, gen_lm_key

# -------------------
# baking common
# -------------------

class BakerBase(ABC):
    def __init__(self, output_dir, dds_fmt='NONE'):
        self._output_dir = output_dir
        self._dds_fmt = dds_fmt
        self._pp_ambient_light_level = 0
        self._pp_out_dir = None

    @abstractmethod
    def type(self):
        ...

    @abstractmethod
    def total_items(self):
        ...

    @abstractmethod
    def completed_items(self):
        ...

    def post_process_enable(self, ambient_light_level, out_dir=''):
        self._pp_ambient_light_level = ambient_light_level
        self._pp_out_dir = out_dir

    def _post_process(self, image):
        channels = image.channels
        w, h = image.size
        pixels = np.array(image.pixels[:]).reshape((h, w, channels))
        pixels[:, :, 2] = pixels[:, :, 2] * (1 - self._pp_ambient_light_level) + self._pp_ambient_light_level
        image.pixels = pixels.ravel().tolist()
        image.update()

    def _post_process_and_save(self, context, image, name=''):
        if not name:
            name = image.name

        img_name = f'{name}.dds'
        if self._pp_out_dir is None:
            # post processing disabled
            save_img_as_dds(image, os.path.join(self._output_dir, img_name), self._dds_fmt)
            return

        if(not self._pp_out_dir or os.path.normpath(self._pp_out_dir) == os.path.normpath(self._output_dir)):
            # override with post processed result
            self._post_process(image)
            save_img_as_dds(image, os.path.join(self._output_dir, img_name), self._dds_fmt)
        else:
            # keep both variants
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_file = os.path.join(tmp_dir, f'{name}.tga')
                image.file_format = 'TARGA'
                image.filepath_raw = tmp_file
                image.alpha_mode = 'STRAIGHT'
                image.save(filepath=tmp_file)
                convert_to_dds(tmp_file, self._output_dir, self._dds_fmt)
                self._post_process(image)
                image.save(filepath=tmp_file)
                convert_to_dds(tmp_file, self._pp_out_dir, self._dds_fmt)

    def bake_next(self, context):
        if not self.prepare_next(context):
            return False
        bpy.ops.object.bake(**self.get_bake_params())
        self.complete_bake(context, False)
        return True

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

class PostProcessor:
    def __init__(self, context, src_dir, out_dir='', ambient_light_intensity=0.5, dds_fmt='NONE'):
        if not out_dir:
            out_dir = src_dir

        self._dds_fmt = dds_fmt
        self._blue_color_boost = ambient_light_intensity
        self._out_dir = out_dir
        self._textures = list()
        for file in os.listdir(src_dir):
            filepath = path.join(src_dir, file)
            if not path.isfile(filepath):
                continue
            if not file.endswith(".dds"):
                continue
            self._textures.append(filepath)
        self._total_count = len(self._textures)

    def total_items(self):
        return self._total_count

    def completed_items(self):
        return self._total_count - len(self._textures)

    def process_next(self, context):
        if not self._textures:
            return False

        filepath = self._textures.pop(0)

        image = bpy.data.images.load(filepath, check_existing=False)
        image.alpha_mode = 'NONE'

        w, h = image.size
        channels = image.channels
        pixels = np.array(image.pixels[:]).reshape((h, w, channels))
        pixels[:, :, 2] = pixels[:, :, 2] * (1 - self._blue_color_boost) + self._blue_color_boost
        image.pixels = pixels.ravel().tolist()
        image.update()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = os.path.join(tmp_dir, file_name(filepath) + '.tga')
            context.scene.view_settings.view_transform = 'Standard'
            context.scene.render.resolution_x = image.size[0]
            context.scene.render.resolution_y = image.size[1]
            context.scene.render.image_settings.color_mode = 'RGB'
            context.scene.render.image_settings.file_format = 'TARGA'
            image.save_render(tmp_file, scene=context.scene)
            convert_to_dds(tmp_file, self._out_dir, self._dds_fmt)

        bpy.data.images.remove(image)
        return True

    def process_all(self, context):
        while self.process_next(context):
            pass

def _get_all_lightmap_files(dir, pattern):
    files = set()
    for file in os.listdir(dir):
        if not file.endswith(".dds"):
            continue
        if not re.match(pattern, file):
            continue
        files.add(file[:-4])
    return files

def get_object_lightmaps(dir):
    return _get_all_lightmap_files(dir, r'.*=\d{2}=-?\d+=-?\d+=-?\d+')

def get_terrain_lightmaps(dir):
    return _get_all_lightmap_files(dir, r'tx\d{2}x\d{2}')

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
            existing_patches = get_terrain_lightmaps(output_dir)
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
        self._terrain.select_set(True)
        self._terrain.hide_render = False
        self._terrain.hide_viewport = False

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

        light_pixels = np.array(light_map.pixels[:])
        water_pixels = np.array(water_depth_map.pixels[:])
        light_pixels[0::4] = water_pixels[0::4]
        light_map.pixels = light_pixels.tolist()

        col, row = self.patches_to_bake[self._patch_index]
        self._post_process_and_save(context, light_map, f'tx{col:02d}x{row:02d}')

        self._texture_node_light.image = None
        self._texture_node_water_depth.image = None
        bpy.data.images.remove(light_map)
        bpy.data.images.remove(water_depth_map)

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
        self.materials = list(materials)
        for material in self.materials:
            self.normal_sockets.append(unplug_socket_from(material, 'Normal'))

    def revert(self):
        for normal_socket, material in zip(self.normal_sockets, self.materials):
            if normal_socket:
                plug_socket_to(material, 'Normal', normal_socket)
        self.materials.clear()
        self.normal_sockets.clear()

def _select_lod_for_bake(geom, lod):
    for lod_idx, lod_obj in enumerate(geom):
        if lod_idx == lod:
            lod_obj.hide_render = False
            lod_obj.hide_viewport = False
            lod_obj.select_set(True)
        else:
            lod_obj.select_set(False)
            lod_obj.hide_render = True
            lod_obj.hide_viewport = True

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
            self._existing_lods = get_object_lightmaps(output_dir)

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

    def type(self):
        return 'Objects'

    def total_items(self):
        return self._total_count

    def completed_items(self):
        return self._total_count - len(self._objects)

    def cleanup(self, context):
        if not self._geom:
            return
        _select_lod_for_bake(self._geom, 0)

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

            _select_lod_for_bake(self._geom, self._lod_idx)
            context.view_layer.objects.active = lod_obj
            return True

        return self.prepare_next(context)

    def complete_bake(self, context, canceled):
        if self._strip_normal_maps:
            self._strip_normal_maps.revert()

        if not canceled:
            self._post_process_and_save(context, self._bake_image)

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
                 max_lod=99, use_margin=True, skip_existing=None, reporter=DEFAULT_REPORTER):
        super().__init__(output_dir, dds_fmt)
        self._reporter = reporter
        self._strip_normal_maps = None if normal_maps else StripNormalMaps()
        self._max_lod = max_lod
        self._atlas_size = atlas_size
        self._margin = context.scene.render.bake.margin if use_margin else 0

        if self._margin % 2 != 0:
            raise ValueError(f"bake margin ({self._margin}) cannot be odd")

        existing_lods = set()
        if skip_existing:
            existing_lods = get_object_lightmaps(output_dir)

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
                width += self._margin
                height += self._margin

                if width > self._atlas_size[0] or height > self._atlas_size[1]:
                    w, h = obj.bf2_lightmap_size
                    raise ValueError(f"lightmap size for '{obj.name}' ({w}x{h} plus margin of {self._margin}) doesn't fit on the specified atlas size ({self._atlas_size[0]}x{self._atlas_size[1]})")

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
            scale_u = (rect.width - self._margin) / self._atlas_size[0]
            scale_v = (rect.height - self._margin) / self._atlas_size[1]
            offset_u = (rect.x + int(self._margin / 2)) / self._atlas_size[0]
            offset_v = (rect.y + int(self._margin / 2)) / self._atlas_size[1]
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
            geom = self._lod_to_geom[rect.rid.name]
            _select_lod_for_bake(geom, -1)

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

        bpy.data.meshes.remove(self._temp_obj.data, do_unlink=True)
        self._temp_obj = None

        atlas_index = self.completed_items()
        atlas_name = f'LightmapAtlas{atlas_index}'
        atlas = self._atlases.pop(0)

        # revert objects to lod 0
        for rect in atlas:
            geom = self._lod_to_geom[rect.rid.name]
            _select_lod_for_bake(geom, 0)

        if not canceled:
            print(f"Splitting atlas {atlas_name} {self.completed_items()}/{self.total_items()}")

            src_img = self._bake_image
            atlas_width, atlas_height = src_img.size
            num_channels = src_img.channels
            src_pixels = np.array(src_img.pixels[:]).reshape((atlas_height, atlas_width, num_channels))

            for rect in atlas:
                lm_name = self._lod_to_lm_key[rect.rid.name]
                w = rect.width - self._margin
                h = rect.height - self._margin
                y = rect.y + int(self._margin / 2)
                x = rect.x + int(self._margin / 2)
                tile_img = bpy.data.images.new(
                    name=lm_name, width=w, height=h)
                tile = src_pixels[y:y+h, x:x+w, :]
                tile_img.pixels = tile.ravel().tolist()

                self._post_process_and_save(context, tile_img)
                bpy.data.images.remove(tile_img)

        bpy.data.images.remove(self._bake_image)
        self._bake_image = None
