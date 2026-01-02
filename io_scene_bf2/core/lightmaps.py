import os.path as path
import math
import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Matrix, Vector, Euler # type: ignore

from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            HeightmapCluster,
                            Object)
from .bf2.bf2_mesh import BF2BundledMesh, BF2StaticMesh, BF2SkinnedMesh, BF2Samples
from .mod_loader import ModLoader
from .mesh import MeshImporter, MeshExporter
from .utils import (DEFAULT_REPORTER,
                    swap_zy, file_name,
                    _convert_pos, _convert_rot,
                    to_matrix, save_img_as_dds,
                    delete_object, find_root,
                    is_pow_two, obj_bounds)
from .heightmap import import_heightmap_from, make_water_plane
from .exceptions import ImportException

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

DEBUG = False

# -------------------
# baking
# -------------------

def _setup_scene_for_baking(context):
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.bake_type = 'DIFFUSE'
    context.scene.render.bake.use_pass_direct = True
    context.scene.render.bake.use_pass_indirect = True
    context.scene.render.bake.use_pass_color = True

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

# -------------------
# baking terrain
# -------------------

def _make_flatten_at_watter_level(water_level):
    if 'FlattenAtWaterLevel' in bpy.data.node_groups:
        node_group = bpy.data.node_groups['FlattenAtWaterLevel']
        bpy.data.node_groups.remove(node_group)

    node_tree = bpy.data.node_groups.new(type='GeometryNodeTree', name="FlattenAtWaterLevel")

    in_sock = node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    in_sock.attribute_domain = 'POINT'
    in_sock.default_input = 'VALUE'
    in_sock.structure_type = 'AUTO'

    out_sock = node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    out_sock.attribute_domain = 'POINT'
    out_sock.default_input = 'VALUE'
    out_sock.structure_type = 'AUTO'

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

def _add_flatten_at_watter_level_mod(terrain, water_level):
    modifier = terrain.modifiers.new(type='NODES', name="FlattenAtWaterLevel")
    modifier.node_group = _make_flatten_at_watter_level(water_level)
    return modifier

def _make_water_depth_material(water_level, water_attenuation=0.05):
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

def _combine_channels():
    view_transform = bpy.context.scene.view_settings.view_transform
    bpy.context.scene.view_settings.view_transform = 'Standard'
    
    # TODO

    bpy.context.scene.view_settings.view_transform = view_transform

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

def _set_watter_attenuation(material, water_attenuation):
    material.node_tree.nodes['WaterAttenuation'].outputs['Value'].default_value = water_attenuation

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
    for obj in context.scene.collection.children['Heightmaps'].objects:
        if obj.name.startswith('Heightmap'):
            return obj

def bake_terrain_lightmaps(context, output_dir, dds_fmt='NONE', patch_count=None, patch_size=None,
                           water_attenuation=0.05, reporter=DEFAULT_REPORTER):
    terrain = find_heightmap(context)

    if not terrain:
        raise RuntimeError(f'Heightmap object not found')

    if patch_count is None or patch_size is None:
        hm_size = get_heightmap_size(terrain)
        if hm_size is None:
            raise RuntimeError(f'Cannot determine heightmap size')
        if hm_size not in DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES:
            raise RuntimeError(f'Cannot determine default values for patch_count and patch_size')
        patch_count, patch_size = DEFAULT_HM_SIZE_TO_PATCH_COUNT_AND_RES[hm_size]

    grid_size = math.isqrt(patch_count)
    if grid_size * grid_size != patch_count:
        raise RuntimeError(f'patch_count must be a power of 4')

    mesh = terrain.data
    vert_count = math.isqrt(len(mesh.vertices))
    if vert_count * vert_count != len(mesh.vertices) or not is_pow_two(vert_count - 1):
        raise RuntimeError(f'heightmap vert count is invalid')
    
    default_terrain_mat = bpy.data.materials['DefaultTerrain']
    water_depth_mat = bpy.data.materials['WaterDepth']
    _set_watter_attenuation(water_depth_mat, water_attenuation)
    flatten_water_mod = terrain.modifiers['FlattenAtWaterLevel']

    mesh.materials.clear()
    mesh.materials.append(default_terrain_mat)

    # we gon simply scale the UV up so the 0-1 range fits one whole patch
    # then shift the UV when rendering the grid
    uv_layer = mesh.uv_layers.new(name='LightmapBakeUV')

    for loop in mesh.loops:
        loop_uv = uv_layer.data[loop.index]
        u, v = loop_uv.uv
        loop_uv.uv = (grid_size * u, 1 - grid_size * v)

    texture_node_light = _setup_material_for_baking(default_terrain_mat, uv=uv_layer.name)
    texture_node_water_depth = _setup_material_for_baking(water_depth_mat, uv=uv_layer.name)

    _setup_scene_for_baking(context)

    for obj in context.selected_objects:
        obj.select_set(False)

    terrain.select_set(True)
    terrain.hide_set(False)
    terrain.hide_render = False
    context.view_layer.update()

    col = 0
    row = 0
    while col < grid_size:
        while row < grid_size:
            name = f'tx{col:02d}x{row:02d}'
            reporter.info(f"Baking terrain patch {name} {1 + row + grid_size * col}/{patch_count}")
            bake_image_light = bpy.data.images.new(name=f'TerrainLightmapBakeImageLight', width=patch_size, height=patch_size)
            bake_image_water_depth = bpy.data.images.new(name=f'TerrainLightmapBakeImageWaterDepth', width=patch_size, height=patch_size)

            for water_pass in [False, True]:
                if water_pass:
                    name += '_waterdepth'

                bake_image = None
                if water_pass:
                    flatten_water_mod.show_render = False
                    mesh.materials[0] = water_depth_mat
                    bake_image = texture_node_water_depth.image = bake_image_water_depth
                else:
                    flatten_water_mod.show_render = True
                    mesh.materials[0] = default_terrain_mat
                    bake_image = texture_node_light.image = bake_image_light

                context.scene.render.bake.use_pass_direct = not water_pass
                context.scene.render.bake.use_pass_indirect = not water_pass
                context.scene.render.bake.use_pass_color = water_pass

                bpy.ops.object.bake(type='DIFFUSE', uv_layer=uv_layer.name)
                save_img_as_dds(bake_image, path.join(output_dir, f'{name}.dds'), dds_fmt)

            # TODO: combine water_pass in compositor and save

            bpy.data.images.remove(bake_image_light)
            bpy.data.images.remove(bake_image_water_depth)

            row += 1
            for loop in mesh.loops:
                uv_layer.data[loop.index].uv[1] += 1
        row = 0
        col += 1
        for loop in mesh.loops:
            loop_uv = uv_layer.data[loop.index]
            u, v = loop_uv.uv
            loop_uv.uv = (u - 1, v - grid_size)
        break

    mesh.materials[0] = default_terrain_mat
    mesh.uv_layers.remove(uv_layer)

# -------------------
# baking objects
# -------------------

def _strip_suffix(s):
    if '.' not in s:
        return s
    head, tail = s.rsplit('.', 1)
    if tail.isnumeric():
        return head
    return s

def _strip_prefix(s):
    for char_idx, _ in enumerate(s):
        if s[char_idx:].startswith('__'):
            return s[char_idx+2:]
    return s

def _gen_lm_key(obj, lod=0):
    geom_template_name = _strip_prefix(_strip_suffix(obj.name)).lower()
    x, y, z = [str(int(i)) for i in obj.matrix_world.translation]
    return '='.join([geom_template_name, f'{lod:02d}', x, z, y])

def _setup_object_for_baking(lod_idx, obj, reporter):
    lm_name = _gen_lm_key(obj, lod=lod_idx)
    lm_size = tuple(obj.bf2_lightmap_size)

    if lm_size == (0, 0):
        reporter.warning(f"skipping '{obj.name}' because lightmap size is not set")
        return None
    if 'UV4' not in obj.data.uv_layers:
        reporter.warning(f"skipping '{obj.name}' because lightmap UV layer (UV4) is missing")
        return None

    # create bake image
    if lm_name in bpy.data.images:
        bake_image = bpy.data.images[lm_name]
        bpy.data.images.remove(bake_image)

    bake_image = bpy.data.images.new(name=lm_name, width=lm_size[0], height=lm_size[1])

    # add bake lightmap texture for each material
    for material in obj.data.materials:
        _setup_material_for_baking(material, bake_image)

    return bake_image

def _select_lod_for_bake(geom, lod):
    for lod_idx, lod_obj in enumerate(geom):
        if lod_idx == lod:
            lod_obj.hide_set(False)
            lod_obj.select_set(True)
            lod_obj.hide_render = False
        else:
            lod_obj.hide_set(True)
            lod_obj.select_set(False)
            lod_obj.hide_render = True

def bake_object_lightmaps(context, output_dir, dds_fmt='NONE', lods=None, only_selected=True, reporter=DEFAULT_REPORTER):
    _setup_scene_for_baking(context)
    objects = list()
    if only_selected:
        for obj in context.selected_objects:
            root_obj = find_root(obj)
            if root_obj not in objects:
                objects.append(root_obj)
    else:
        for obj in context.scene.collection.children['StaticObjects'].objects:
            if obj.parent is None and obj.data is None:
                objects.append(root_obj)

    for obj in context.selected_objects:
        obj.select_set(False)

    total_cnt = len(objects)
    for i, root_obj in enumerate(objects, start=1):
        reporter.info(f"Baking object {root_obj.name} {i}/{total_cnt}")
        geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
        for geom_idx, geom in enumerate(geoms):
            if geom_idx != 0: # TODO: Geom1 support
                continue
            for lod_idx, lod_obj in enumerate(geom):
                if lods is not None and lod_idx not in lods:
                    continue
                if image := _setup_object_for_baking(lod_idx, lod_obj, reporter=reporter):
                    _select_lod_for_bake(geom, lod_idx)
                    context.view_layer.update()
                    bpy.ops.object.bake(type='DIFFUSE', uv_layer='UV4')
                    save_img_as_dds(image, path.join(output_dir, image.name + '.dds'), dds_fmt)
                    bpy.data.images.remove(image)

            _select_lod_for_bake(geom, 0)
            context.view_layer.update()

# -------------------
# material tweaks
# -------------------

def _unplug_socket_from_bsdf(socket_name):
    for mesh in bpy.data.meshes:
        for material in mesh.materials:
            if not material.is_bf2_material:
                continue
            node_tree = material.node_tree
            for node_link in node_tree.links:
                node = node_link.to_node
                if node.type == 'BSDF_PRINCIPLED' and node_link.to_socket.name == socket_name:
                    node_tree.links.remove(node_link)
                    break

def tweak_materials(no_normalmap=True):
    if no_normalmap:
        _unplug_socket_from_bsdf('Normal')

    # TODO: add ambient occlusion as an option

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
    (8, 0),
    (16, 4),
    (32, 8),
    (64, 16),
    (128, 32),
    (256, 256),
    (512, 1024),
    (1024, 2056)
]

def _calc_mesh_area(lod_obj):
    bm = bmesh.new()
    bm.from_mesh(lod_obj.data)
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    return area

def _clone_object(collection, src_root):
    geoms = MeshExporter.collect_geoms_lods(src_root, skip_checks=True)
    root = bpy.data.objects.new(src_root.name, None)
    root.hide_render = True
    collection.objects.link(root)
    root.hide_set(True)
    for geom_idx, geom in enumerate(geoms):
        geom_obj = bpy.data.objects.new(f'G{geom_idx}__' + src_root.name, None)
        geom_obj.parent = root
        geom_obj.hide_render = True
        collection.objects.link(geom_obj)
        geom_obj.hide_set(True)
        for lod_idx, src_lod_obj in enumerate(geom):
            lod_obj = bpy.data.objects.new(f'G{geom_idx}L{lod_idx}__' + src_root.name, src_lod_obj.data)
            lod_obj.parent = geom_obj
            lod_obj.bf2_lightmap_size = src_lod_obj.bf2_lightmap_size
            collection.objects.link(lod_obj)
            if lod_idx != 0:
                lod_obj.hide_render = True
                lod_obj.hide_set(True)
    return root

def _load_heightmap(context, level_dir):
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

    # water_plane = make_water_plane(context, hm_cluster.heightmap_size, hm_cluster.water_level)
    # context.scene.collection.objects.unlink(water_plane)
    # heightmaps.objects.link(water_plane)

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

    material = _make_water_depth_material(hm_cluster.water_level) 
    material.use_fake_user = True # will be used later

    _add_flatten_at_watter_level_mod(terrain, hm_cluster.water_level)

def load_level(context, mod_dir, level_name, use_cache=True,
               load_unpacked=True, load_static_objects=True,
               load_overgrowth=True, load_heightmap=True, load_lights=True,
               lm_size_thresholds=None,
               reporter=DEFAULT_REPORTER):

    if lm_size_thresholds is None:
        lm_size_thresholds = DEFAULT_LM_SIZE_TO_SURFACE_AREA_THRESHOLDS

    if not load_unpacked:
        mod_loader = ModLoader(mod_dir, use_cache)
        mod_loader.reload_all()
    else:
        BF2Engine().shutdown()

    file_manager = BF2Engine().file_manager
    main_console = BF2Engine().main_console
    file_manager.root_dir = mod_dir

    def report_cb(con_file, line_no, line, what):
        if line.lower().startswith('object.create'):
            reporter.warning(f'{con_file}:{line_no}:{line}: {what}')

    main_console.report_cb = report_cb

    level_dir = path.join('levels', level_name)
    if load_unpacked:
        level_dir = path.join(mod_dir, level_dir)
    client_zip_path = path.join(level_dir, 'client.zip')
    server_zip_path = path.join(level_dir, 'server.zip')

    # mount level archives
    if not load_unpacked:
        file_manager.mountArchive(client_zip_path, level_dir)
        file_manager.mountArchive(server_zip_path, level_dir)

    if DEBUG:
        print(f"Loading statics")

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
            args = ['BF2Editor'] if load_unpacked else []
            main_console.run_file(path.join(level_dir, 'StaticObjects.con'), args=args)

        if load_overgrowth:
            main_console.run_file(path.join(level_dir, 'Overgrowth', 'OvergrowthCollision.con'))

    templates : Dict[str, GeometryTemplate] = dict()
    template_to_instances : Dict[str, List[Matrix]] = dict()

    obj_manager = BF2Engine().get_manager(Object)
    geom_manager = BF2Engine().get_manager(GeometryTemplate)

    for obj in obj_manager.objects:
        template = obj.template
        for temp, matrix_world, in _get_templates(template, _get_obj_matrix(obj)):
            if not temp.geom:
                continue

            geom = geom_manager.templates[temp.geom.lower()]
            obj_transforms = template_to_instances.setdefault(geom.name.lower(), list())
            obj_transforms.append(matrix_world)
            templates[geom.name.lower()] = geom

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

    for idx, (template_name, geom_temp) in enumerate(templates.items()):
        if DEBUG:
            print(f"Importing {geom_temp.name} | {idx}/{len(templates)}")

        data = file_manager.readFile(geom_temp.location, as_stream=True)
        mesh_type = MESH_TYPES.get(geom_temp.geometry_type)
        if not mesh_type:
            reporter.warning(f"skipping '{template_name}' as it is not supported mesh type {geom_temp.geometry_type}")
            continue
        try:
            bf2_mesh = mesh_type.load_from(template_name, data)
        except Exception as e:
            reporter.warning(f"Failed to load mesh '{geom_temp.location}', the file might be corrupted: {e}")
            del template_to_instances[template_name]
            continue

        # TODO: texture load from FileManager if not load_unpacked!
        importer = MeshImporter(context, geom_temp.location, loader=lambda: bf2_mesh, texture_path=mod_dir, reporter=reporter)
        try:
            root_obj = importer.import_mesh()
        except ImportException as e:
            reporter.warning(f"Failed to import mesh '{geom_temp.location}': {e}")
            continue

        # determine samples size
        meshes_dir = path.dirname(geom_temp.location)
        lm_sizes = dict()
        for lod_idx, _ in enumerate(bf2_mesh.geoms[0].lods): # TODO: Geom1 support
            if lod_idx == 0:
                fname = path.join(meshes_dir, geom_temp.name + '.samples')
            else:
                fname = path.join(meshes_dir, geom_temp.name + f'.samp_{lod_idx:02d}')
            
            lm_size = None
            if load_unpacked:
                if path.isfile(fname):
                    with open(fname, "rb") as f:
                        lm_size = BF2Samples.read_map_size_from(f)
            else:
                raise NotImplementedError() # TODO
            lm_sizes[lod_idx] = lm_size

        obj_transforms = template_to_instances[template_name]

        geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
        lod0_lm_size = None
        MIN_LM_SIZE = 8
        for lod_idx, lod_obj in enumerate(geoms[0]): # TODO: Geom1 support
            lm_size = lm_sizes[lod_idx]
            if lm_size is None:
                # if lm_size is None:
                #     reporter.warning(f"Cannot determine LM size for mesh '{geom.location}' Lod{lod_idx} from samples file, it may not exist")
                if lod0_lm_size is not None:
                    # halve the LOD0 size
                    lm_size = [max(int(i / (2**lod_idx)), MIN_LM_SIZE) for i in lod0_lm_size]
                else:
                    # guess using surface area of the mesh
                    mesh_area = _calc_mesh_area(lod_obj)
                    for lms, min_area in reversed(lm_size_thresholds):
                        if mesh_area >= min_area:
                            lm_size = (lms, lms)
                            break
            if lm_size is None:
                lm_size = (MIN_LM_SIZE, MIN_LM_SIZE)
            if lod_idx == 0:
                lod0_lm_size = lm_size
            lod_obj.bf2_lightmap_size = lm_size

        # TODO: Geom1 support
        if 'StaticMesh' == geom_temp.geometry_type:
            for geom_obj in geoms[1:]:
                delete_object(geom_obj)

        for matrix_world in obj_transforms:
            if geom_temp.dont_generate_lightmaps or 'StaticMesh' != geom_temp.geometry_type:
                obj = _clone_object(static_objects_skip, root_obj)
            else:
                obj = _clone_object(static_objects, root_obj)
            obj.matrix_world = matrix_world

            # check LM key collisions
            lm_key = _gen_lm_key(obj, lod_idx)
            if lm_key in lm_keys:
                reporter.warning(f"GeometryTemplate '{geom_temp.name}' at position {matrix_world.translation} "
                                 "is too close to another object of the same type which will result in them having the same lightmap filenames!")
            lm_keys.add(lm_key)

        # delete source instance
        delete_object(root_obj, remove_data=False)

    if DEBUG:
        print(f"Loading heightmap")

    if load_heightmap:
        _load_heightmap(context, level_dir)

    if DEBUG:
        print(f"Loading lights")

    lights = _make_collection(context, "Lights")
    if load_lights:
        # sun (green channel)
        main_console.run_file(path.join(level_dir, 'Sky.con'))
        sun_dir = Vector(BF2Engine().light_manager.sun_dir)
        _convert_pos(sun_dir)
        light = bpy.data.lights.new(name='Sun', type='SUN')
        obj = bpy.data.objects.new(light.name, light)
        lights.objects.link(obj)
        sun_dir.z = -sun_dir.z # points down
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = sun_dir.rotation_difference(Vector((0, 0, 1)))

        sin_alpha = abs(sun_dir.z)
        light.energy = 3 + 2.0 * sin_alpha # TODO strength
        light.color = (0, 1, 0)

        # ambient light / soft shadows (blue channel)
        if "SkyLight" in bpy.data.worlds:
            world = bpy.data.worlds["SkyLight"]
            bpy.data.worlds.remove(world)
        context.scene.world = bpy.data.worlds.new("SkyLight")
        background = context.scene.world.node_tree.nodes["Background"]
        background.inputs['Color'].default_value = (0, 0, 1, 1)
        background.inputs['Strength'].default_value = 0.7 # TODO strength

        # TODO: point lights (red channel)
