import os
import os.path as path
import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Matrix, Vector # type: ignore

from typing import Dict, List

from ...bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            HeightmapCluster,
                            Object)
from ...bf2.bf2_mesh import BF2BundledMesh, BF2StaticMesh, BF2SkinnedMesh, BF2Samples
from ...mod_loader import ModLoader
from ...utils import set_gn_modifier_input
from ...material import (setup_material,
                        get_material_maps,
                        get_staticmesh_uv_channel_mapping,
                        STATICMESH_TEXUTRE_MAP_TYPES)
from ...mesh import MeshImporter, MeshExporter
from ...utils import (DEFAULT_REPORTER,
                    swap_zy, file_name,
                    _convert_pos, _convert_rot,
                    to_matrix, delete_object,
                    yaw_pitch_roll_to_matrix,
                    remove_double_verts)
from ...heightmap import import_heightmap_from
from ...exceptions import ImportException
from fnmatch import fnmatch
from .common import plug_socket_to, unplug_socket_from, gen_lm_key


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

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

def _make_flatten_at_water_level():
    if 'FlattenAtWaterLevel' in bpy.data.node_groups:
        node_group = bpy.data.node_groups['FlattenAtWaterLevel']
        bpy.data.node_groups.remove(node_group)

    node_tree = bpy.data.node_groups.new(type='GeometryNodeTree', name="FlattenAtWaterLevel")

    node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name="Water Level", in_out='INPUT', socket_type='NodeSocketFloat')

    group_input = node_tree.nodes.new("NodeGroupInput")
    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.is_active_output = True

    get_position = node_tree.nodes.new("GeometryNodeInputPosition")

    clamp = node_tree.nodes.new("ShaderNodeClamp")
    clamp.inputs['Min'].default_value = 0.0
    clamp.inputs['Max'].default_value = 10000.0

    set_position = node_tree.nodes.new("GeometryNodeSetPosition")
    combine_xyz = node_tree.nodes.new("ShaderNodeCombineXYZ")
    separate_xyz = node_tree.nodes.new("ShaderNodeSeparateXYZ")

    node_tree.links.new(group_input.outputs['Water Level'], clamp.inputs['Min'])
    node_tree.links.new(group_input.outputs['Geometry'], set_position.inputs['Geometry'])
    node_tree.links.new(set_position.outputs['Geometry'], group_output.inputs['Geometry'])
    node_tree.links.new(get_position.outputs['Position'], separate_xyz.inputs['Vector'])
    node_tree.links.new(separate_xyz.outputs['Z'], clamp.inputs['Value'])
    node_tree.links.new(clamp.outputs['Result'], combine_xyz.inputs['Z'])
    node_tree.links.new(separate_xyz.outputs['Y'], combine_xyz.inputs['Y'])
    node_tree.links.new(separate_xyz.outputs['X'], combine_xyz.inputs['X'])
    node_tree.links.new(combine_xyz.outputs['Vector'], set_position.inputs['Position'])
    return node_tree

def _make_water_depth_material():
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
    watter_lvl_node = node_tree.nodes.new("ShaderNodeAttribute")
    watter_lvl_node.name = "WaterLevel"
    watter_lvl_node.label = "WaterLevel"
    watter_lvl_node.attribute_type = 'OBJECT'
    watter_lvl_node.attribute_name = 'water_level'
    watter_lvl_node.location = (2 * NODE_SPACING, -100)

    math_substract = node_tree.nodes.new("ShaderNodeMath")
    math_substract.operation = 'SUBTRACT'
    math_substract.location = (2 * NODE_SPACING, 100)

    node_tree.links.new(watter_lvl_node.outputs['Factor'], math_substract.inputs[1])
    node_tree.links.new(separate_xyz.outputs['Z'], math_substract.inputs[0])

    # multiply by water attenuation coefficient
    watter_att_node = node_tree.nodes.new("ShaderNodeAttribute")
    watter_att_node.name = "WaterAttenuation"
    watter_att_node.label = "WaterAttenuation"
    watter_att_node.attribute_type = 'OBJECT'
    watter_att_node.attribute_name = 'water_attenuation'
    watter_att_node.location = (1 * NODE_SPACING, -100)

    math_multiply = node_tree.nodes.new("ShaderNodeMath")
    math_multiply.operation = 'MULTIPLY'
    math_multiply.location = (2 * NODE_SPACING, 0)
    node_tree.links.new(watter_att_node.outputs['Factor'], math_multiply.inputs[1])
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

def _add_ao_node(material):
    node_tree = material.node_tree
    bsdf_node = None
    output_node = None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf_node = node
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        if bsdf_node and output_node:
            break

    mix = node_tree.nodes.new('ShaderNodeMixShader')
    ao = node_tree.nodes.new('ShaderNodeAmbientOcclusion')

    node_tree.links.new(bsdf_node.outputs[0], mix.inputs[2])
    node_tree.links.new(ao.outputs[1], mix.inputs[0])
    node_tree.links.new(mix.outputs[0], output_node.inputs[0])

def _add_texture_node(material, texture_file, uv_index, texture_paths, reporter):
    node_tree = material.node_tree
    uv_node = None
    for node in node_tree.nodes:
        if node.type == 'UVMAP' and node.uv_map == f'UV{uv_index}':
            uv_node = node

    for texture_path in texture_paths:
        abs_path = os.path.join(texture_path, texture_file)
        if os.path.isfile(abs_path):
            break
    else:
        if texture_paths:
            reporter.warning(f"Texture file '{texture_file}' not found in any of the texture paths")
        abs_path = ''
    tex_node = node_tree.nodes.new('ShaderNodeTexImage')
    if abs_path:
        tex_node.image = bpy.data.images.load(abs_path, check_existing=True)
        tex_node.image.alpha_mode = 'STRAIGHT'

    node_tree.links.new(uv_node.outputs['UV'], tex_node.inputs['Vector'])
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

# -------------------
# scene setup
# -------------------

def _module_from_file(py_file):
    import importlib.util
    spec = importlib.util.spec_from_file_location("lm_config", py_file)
    lm_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lm_config)
    return lm_config

def _get_templates(template, matrix, templates=None):
    if templates is None:
        templates = list()
    templates.append((template, matrix))
    template.add_bundle_childs()
    for child in template.children:
        if child.template is not None:
            child_matrix = yaw_pitch_roll_to_matrix(child.rotation)
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
        matrix_world = yaw_pitch_roll_to_matrix(bf2_object.rot)
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

def _calc_mesh_area(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    return area

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

    # setup waterdepth material, will be used later
    terrain['water_attenuation'] = 0.15
    terrain['water_level'] = hm_cluster.water_level
    material = _make_water_depth_material() 
    material.use_fake_user = True

    modifier = terrain.modifiers.new(type='NODES', name="FlattenAtWaterLevel")
    modifier.node_group = _make_flatten_at_water_level()
    input_id = modifier.node_group.interface.items_tree["Water Level"].identifier
    set_gn_modifier_input(modifier, input_id, hm_cluster.water_level)

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

    def instantiate(self, collection, name, lod0_only=False):
        if lod0_only:
            lod_data = self.geoms[0].lods[0]
            lod_obj = bpy.data.objects.new(name, lod_data.mesh)
            collection.objects.link(lod_obj)
            return lod_obj

        root = bpy.data.objects.new(name, None)
        root.hide_render = True
        root.hide_viewport = True
        collection.objects.link(root)
        for geom_idx, geom in enumerate(self.geoms):
            geom_obj = bpy.data.objects.new(f'G{geom_idx}__' + name, None)
            geom_obj.parent = root
            geom_obj.hide_render = True
            geom_obj.hide_viewport = True
            collection.objects.link(geom_obj)
            for lod_idx, lod_data in enumerate(geom.lods):
                lod_obj = bpy.data.objects.new(f'G{geom_idx}L{lod_idx}__' + name, lod_data.mesh)
                lod_obj.parent = geom_obj
                lod_obj.bf2_lightmap_size = lod_data.lm_size
                if lod_idx != 0:
                    lod_obj.hide_render = True
                    lod_obj.hide_viewport = True
                collection.objects.link(lod_obj)
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
            child_matrix = yaw_pitch_roll_to_matrix(child.rotation)
            child_matrix.translation = swap_zy(child.position)
            _get_template_configs(child.template, matrix @ child_matrix, config, templates, reporter)

def _do_material_tweaks(config, geom_temp_name, geom, texture_paths, ray_vis_mask, reporter):
    materials_done = set()
    for lod_obj in geom:
        mesh = lod_obj.data
        for material in mesh.materials:
            if material.name in materials_done:
                continue

            materials_done.add(material.name)

            modified = False
            backface_cull = True
            if _match_config_pattern(geom_temp_name, config, 'FORCE_TWO_SIDED'):
                backface_cull = False
                modified = True

            alpha_mode = None
            ray_masks_to_add = dict()
            mat_maps = get_material_maps(material)
            map_to_uv = get_staticmesh_uv_channel_mapping(mat_maps)
            for map_name, path in mat_maps.items():
                if map_name not in ('Base', 'Detail', 'Dirt', 'Crack'):
                    continue

                replace_cfg = _match_config_pattern(path, config, 'TEXTURE_REPLACE', lambda p: p['from'])
                if not replace_cfg:
                    continue

                if alpha_mode and replace_cfg.get('alpha_mode', alpha_mode) != alpha_mode:
                    raise RuntimeError(f"Bad config, texture replace results in conflicting `alpha_mode`s on '{mesh.name}'")

                alpha_mode = replace_cfg.get('alpha_mode', None)
                if alpha_mode == 'RAY_MASK':
                    ray_masks_to_add[map_name] = replace_cfg['to']
                    continue # added below

                material.is_bf2_material = False # temporarily disable so update() doesn't trigger
                index = STATICMESH_TEXUTRE_MAP_TYPES.index(map_name)
                setattr(material, f"texture_slot_{index}", replace_cfg['to'])
                if alpha_mode == 'ALPHA_TEST':
                    material.bf2_alpha_mode = 'ALPHA_TEST'
                material.is_bf2_material = True

                # reporter.info(f"Replaced texture '{path}' for '{mesh.name}' as requested")
                modified = True

            if modified:
                setup_material(material, texture_paths=texture_paths, reporter=reporter, backface_cull=backface_cull) # re-apply

            for map_name, ray_mask in ray_masks_to_add.items():
                tex_node = _add_texture_node(material, ray_mask, map_to_uv[map_name], texture_paths, reporter)
                node_tree = material.node_tree
                ray_vis_mask_node = node_tree.nodes.new('ShaderNodeGroup')
                ray_vis_mask_node.node_tree = ray_vis_mask
                alpha_socket = unplug_socket_from(material, 'Alpha')
                node_tree.links.new(alpha_socket, ray_vis_mask_node.inputs['Alpha'])
                plug_socket_to(material, 'Alpha', ray_vis_mask_node.outputs['Alpha'])
                node_tree.links.new(tex_node.outputs['Alpha'], ray_vis_mask_node.inputs['Mask'])
                # reporter.info(f"Added ray mask '{path}' for '{mesh.name}' as requested")

            # _add_ao_node(material)

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
               mod_dirs=[], max_lod_to_load=None, lm_skip_lod0_only=True,
               config=None, config_file='', reporter=DEFAULT_REPORTER):

    level_dir = level_dir.rstrip('/').rstrip('\\')
    mod_dir = path.normpath(path.join(level_dir, '..', '..'))

    if config_file and path.isfile(config_file):
        config = _module_from_file(config_file)

    lm_size_thresholds = _get_lm_size_thresholds(config, reporter)
    ray_vis_mask = _make_ray_visibility_mask()

    if load_unpacked:
        BF2Engine().shutdown()

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
    else:
        # add to to other mod dirs if needed
        if not any([mod_dir.lower() == t.rstrip('/').rstrip('\\').lower() for t in mod_dirs]):
            mod_dirs.append(mod_dir)

        mod_dirs.append(level_dir) # for objects inside levels dir
        BF2Engine().file_manager.root_dirs = mod_dirs

    # load statics & OG
    if load_static_objects or load_overgrowth:
        # load mapside object templates if exist
        if not load_unpacked:
            try:
                main_console.run_file(path.join(level_dir, 'serverarchives.con'))
                mod_loader = ModLoader(mod_dir, use_cache) # load just the main mod (ignore mod_dirs)
                mod_loader.reload_all()
            except FileManagerFileNotFound:
                pass
        else:
            # load each mod_dir configured
            for md in mod_dirs:
                print(f'Loading objects from "{md}"')
                _run_all_con_files(os.path.join(md, 'objects'))
            _run_all_con_files(os.path.join(level_dir, 'objects'))

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

            importer = MeshImporter(context, geom_temp.location, loader=lambda: bf2_mesh,
                                    texture_paths=mod_dirs, reporter=reporter, silent=True)
            try:
                mesh_obj = importer.import_mesh()
            except ImportException as e:
                reporter.error(f"Failed to import mesh '{geom_temp.location}': {e}")
                continue

            remove_double_verts(mesh_obj, recursive=True)

            # determine samples size
            meshes_dir = path.dirname(geom_temp.location)
            geoms = MeshExporter.collect_geoms_lods(mesh_obj, skip_checks=True)
            lod0_lm_size = None
            MIN_LM_SIZE = 8
            geom_info = GeometryTemplateConfig.Geom() # TODO: Geom1 support
            mesh_info.geoms.append(geom_info)

            skip_lightmaps = (geom_temp.dont_generate_lightmaps or
                'StaticMesh' != geom_temp.geometry_type or
                not bf2_mesh.has_uv(4)) # overgrowth doesn't have lightmap UV

            for lod_idx, lod_obj in enumerate(geoms[0]): # TODO: Geom1 support
                lm_size = None

                if not skip_lightmaps:
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
                else:
                    lm_size = (0, 0)

                lod_info = GeometryTemplateConfig.Lod(lod_obj.data, lm_size)
                geom_info.lods.append(lod_info)

            # do material tweaks
            if 'StaticMesh' == geom_temp.geometry_type:
                _do_material_tweaks(config, geom_temp.name, geoms[0], mod_dirs, ray_vis_mask, reporter) # TODO: Geom1 support

            # delete source objects, keep mesh instances
            delete_object(mesh_obj, remove_data=False)

        # instantiate meshes
        for matrix_world in temp_cfg.instances:
            collection = static_objects_skip if skip_lightmaps else static_objects

            # optimization to minimize the number of objects: if we don't need to lightmap the object just import LOD0
            # objects.new() becomes very slow as object count increases
            lod0_only = skip_lightmaps and lm_skip_lod0_only

            # XXX: objects are be named by ObjectTemplate and meshes are named by GeometryTemplate which is not always the same!
            obj = mesh_info.instantiate(collection, temp_cfg.template.name, lod0_only=lod0_only)
            obj.matrix_world = matrix_world

            # check LM key collisions
            if not skip_lightmaps:
                lm_key = gen_lm_key(geom_temp.name, obj.matrix_world.translation, lod_idx)
                if lm_key in lm_keys:
                    reporter.warning(f"Object '{obj.name}' is too close to another which will result in both having the same lightmap filenames!")
                lm_keys.add(lm_key)

    if load_heightmap:
        _load_heightmap(context, level_dir)

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
