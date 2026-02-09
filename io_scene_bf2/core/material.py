import bpy # type: ignore
import os
from collections import OrderedDict

from .utils import DEFAULT_REPORTER, file_name
from .exceptions import ImportException

NODE_WIDTH = 300
NODE_HEIGHT = 100

STATICMESH_TECHNIQUES = [
    'Base',
    'BaseDetail',
    'BaseDetailNDetail',
    'BaseDetailCrack',
    'BaseDetailCrackNCrack',
    'BaseDetailCrackNDetail',
    'BaseDetailCrackNDetailNCrack',
    'BaseDetailDirt',
    'BaseDetailDirtNDetail',
    'BaseDetailDirtCrack',
    'BaseDetailDirtCrackNCrack',
    'BaseDetailDirtCrackNDetail',
    'BaseDetailDirtCrackNDetailNCrack'
]

STATICMESH_TEXUTRE_MAP_TYPES = ['Base', 'Detail', 'Dirt', 'Crack', 'NDetail', 'NCrack']
BUNDLEDMESH_TEXTURE_MAP_TYPES = ['Color', 'Normal', 'Wreck']
SKINNEDMESH_TEXTURE_MAP_TYPES = ['Color', 'Normal']

TEXTURE_MAPS = {
    'STATICMESH': STATICMESH_TEXUTRE_MAP_TYPES,
    'BUNDLEDMESH': BUNDLEDMESH_TEXTURE_MAP_TYPES,
    'SKINNEDMESH': SKINNEDMESH_TEXTURE_MAP_TYPES
}

TEXTURE_TYPE_TO_SUFFIXES = {
    # BundledMesh/SkinnedMesh
    'Color': ('_c',),
    'Normal': ('_b', '_b_os'),
    'Wreck': ('_w',),
    # StaticMesh
    'Base': ('_c',),
    'Detail': ('_de','_c'),
    'Dirt': ('_di','_w'),
    'Crack': ('_cr',),
    'NDetail': ('_deb','_b'),
    'NCrack': ('_crb',)
}

def get_texture_suffix(texture_type):
    return TEXTURE_TYPE_TO_SUFFIXES[texture_type][0]

def texture_suffix_is_valid(texture_path, texture_type):
    map_filename = file_name(texture_path)
    suffixes = TEXTURE_TYPE_TO_SUFFIXES[texture_type]
    return any([map_filename.endswith(sfx) for sfx in suffixes])

def _create_bf2_axes_swap():
    if 'BF2AxesSwap' in bpy.data.node_groups:
        return bpy.data.node_groups['BF2AxesSwap']
    bf2_axes_swap = bpy.data.node_groups.new('BF2AxesSwap', 'ShaderNodeTree')

    group_inputs = bf2_axes_swap.nodes.new('NodeGroupInput')
    bf2_axes_swap.interface.new_socket(name="in", in_out='INPUT', socket_type='NodeSocketVector')
    group_outputs = bf2_axes_swap.nodes.new('NodeGroupOutput')
    bf2_axes_swap.interface.new_socket(name="out", in_out='OUTPUT', socket_type='NodeSocketVector')

    # swap Y/Z axes
    swap_yz_decompose = bf2_axes_swap.nodes.new('ShaderNodeSeparateXYZ')
    swap_yz_compose = bf2_axes_swap.nodes.new('ShaderNodeCombineXYZ')
    bf2_axes_swap.links.new(swap_yz_decompose.outputs['X'], swap_yz_compose.inputs['X'])
    bf2_axes_swap.links.new(swap_yz_decompose.outputs['Z'], swap_yz_compose.inputs['Y'])
    bf2_axes_swap.links.new(swap_yz_decompose.outputs['Y'], swap_yz_compose.inputs['Z'])

    bf2_axes_swap.links.new(group_inputs.outputs['in'], swap_yz_decompose.inputs['Vector'])
    bf2_axes_swap.links.new(swap_yz_compose.outputs['Vector'], group_outputs.inputs['out'])

    return bf2_axes_swap

def _create_multiply_rgb_shader_node():
    if 'MultiplyRGB' in bpy.data.node_groups:
        return bpy.data.node_groups['MultiplyRGB']
    multi_rgb = bpy.data.node_groups.new('MultiplyRGB', 'ShaderNodeTree')

    group_inputs = multi_rgb.nodes.new('NodeGroupInput')
    multi_rgb.interface.new_socket(name="color", in_out='INPUT', socket_type='NodeSocketColor')
    group_outputs = multi_rgb.nodes.new('NodeGroupOutput')
    multi_rgb.interface.new_socket(name="value", in_out='OUTPUT', socket_type='NodeSocketFloat')

    node_separate_color = multi_rgb.nodes.new('ShaderNodeSeparateColor')
    node_multiply_rg = multi_rgb.nodes.new('ShaderNodeMath')
    node_multiply_rg.operation = 'MULTIPLY'
    node_multiply_rgb = multi_rgb.nodes.new('ShaderNodeMath')
    node_multiply_rgb.operation = 'MULTIPLY'

    multi_rgb.links.new(node_separate_color.outputs['Red'], node_multiply_rg.inputs[0])
    multi_rgb.links.new(node_separate_color.outputs['Green'], node_multiply_rg.inputs[1])
    multi_rgb.links.new(node_separate_color.outputs['Blue'], node_multiply_rgb.inputs[0])
    multi_rgb.links.new(node_multiply_rg.outputs[0], node_multiply_rgb.inputs[1])

    multi_rgb.links.new(group_inputs.outputs['color'], node_separate_color.inputs['Color'])
    multi_rgb.links.new(node_multiply_rgb.outputs[0], group_outputs.inputs['value'])
    return multi_rgb

def _create_os_to_b_converter():
    name = 'ConvToTangentSpace'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    node_tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')

    node_tree.interface.new_socket(name="Color", in_out='OUTPUT', socket_type='NodeSocketColor')
    node_tree.interface.new_socket(name="Color", in_out='INPUT', socket_type='NodeSocketColor')

    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.location = (994.2379150390625, 181.35035705566406)

    group_input = node_tree.nodes.new("NodeGroupInput")
    group_input.location = (-923.6591796875, 228.047607421875)

    # we gotta swap Z/Y axes for it to look correct
    normal_map = node_tree.nodes.new("ShaderNodeNormalMap")
    normal_map.space = 'OBJECT'
    normal_map.location = (-690.7890625, 277.37982177734375)

    axes_swap = node_tree.nodes.new('ShaderNodeGroup')
    axes_swap.node_tree = _create_bf2_axes_swap()
    axes_swap.location = (-432.96795654296875, 270.1278076171875)
    axes_swap.hide = True

    cross_product = node_tree.nodes.new("ShaderNodeVectorMath")
    cross_product.hide = True
    cross_product.operation = 'CROSS_PRODUCT'
    cross_product.location = (-348.1199645996094, -160.49468994140625)

    x_val = node_tree.nodes.new("ShaderNodeVectorMath")
    x_val.hide = True
    x_val.operation = 'DOT_PRODUCT'
    x_val.location = (-26.9112548828125, 147.0039520263672)

    y_val = node_tree.nodes.new("ShaderNodeVectorMath")
    y_val.hide = True
    y_val.operation = 'DOT_PRODUCT'
    y_val.location = (-29.3994140625, 50.9498291015625)

    z_val = node_tree.nodes.new("ShaderNodeVectorMath")
    z_val.hide = True
    z_val.operation = 'DOT_PRODUCT'
    z_val.location = (-24.8734130859375, -46.870635986328125)

    combine_xyz = node_tree.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.hide = True
    combine_xyz.location = (183.85723876953125, 56.20903778076172)

    to_rgb_scale = node_tree.nodes.new("ShaderNodeVectorMath")
    to_rgb_scale.hide = True
    to_rgb_scale.operation = 'SCALE'
    to_rgb_scale.inputs['Scale'].default_value = 0.5
    to_rgb_scale.location = (383.8500061035156, 56.60145568847656)

    to_rgb_add = node_tree.nodes.new("ShaderNodeVectorMath")
    to_rgb_add.hide = True
    to_rgb_add.operation = 'ADD'
    to_rgb_add.inputs[1].default_value = (0.5, 0.5, 0.5)
    to_rgb_add.location = (578.1530151367188, 57.50624084472656)

    rest_tangent = node_tree.nodes.new("ShaderNodeAttribute")
    rest_tangent.attribute_name = "rest_tangent"
    rest_tangent.attribute_type = 'GEOMETRY'
    rest_tangent.location = (-709.5729370117188, -186.66122436523438)

    rest_normal = node_tree.nodes.new("ShaderNodeAttribute")
    rest_normal.attribute_name = "rest_normal"
    rest_normal.attribute_type = 'GEOMETRY'
    rest_normal.location = (-715.3265991210938, 11.88730525970459)

    node_tree.links.new(group_input.outputs['Color'], normal_map.inputs['Color'])
    node_tree.links.new(normal_map.outputs['Normal'], axes_swap.inputs[0])

    node_tree.links.new(axes_swap.outputs[0], x_val.inputs[0])
    node_tree.links.new(rest_tangent.outputs['Vector'], x_val.inputs[1])

    node_tree.links.new(rest_normal.outputs['Vector'], cross_product.inputs[0])
    node_tree.links.new(rest_tangent.outputs['Vector'], cross_product.inputs[1])
    node_tree.links.new(cross_product.outputs['Vector'], y_val.inputs[1])
    node_tree.links.new(axes_swap.outputs[0], y_val.inputs[0])

    node_tree.links.new(axes_swap.outputs[0], z_val.inputs[0])
    node_tree.links.new(rest_normal.outputs['Vector'], z_val.inputs[1] )

    node_tree.links.new(x_val.outputs['Value'], combine_xyz.inputs['X'])
    node_tree.links.new(y_val.outputs['Value'], combine_xyz.inputs['Y'])
    node_tree.links.new(z_val.outputs['Value'], combine_xyz.inputs['Z'])
    node_tree.links.new(combine_xyz.outputs['Vector'], to_rgb_scale.inputs['Vector'])
    node_tree.links.new(to_rgb_scale.outputs[0], to_rgb_add.inputs[0])
    node_tree.links.new(to_rgb_add.outputs['Vector'], group_output.inputs['Color'])

    return node_tree

def _split_str_from_word_set(s : str, word_set : set):
    words = list()
    while s:
        for word in word_set:
            if s.startswith(word):
                words.append(word)
                s = s[len(word):]
                break
        else:
            return None # contains word not in wordset
    return words

def get_staticmesh_uv_channels(maps):
    uv_channels = set()
    has_dirt = 'Dirt' in maps
    for texture_map in maps:
        if texture_map == 'Base':
            uv_chan = 0
        elif texture_map == 'Detail':
            uv_chan = 1
        elif texture_map == 'Dirt':
            uv_chan = 2
        elif texture_map == 'Crack':
            uv_chan = 3 if has_dirt else 2
        elif texture_map == 'NDetail':
            uv_chan = 1
        elif texture_map == 'NCrack':
            uv_chan = 3 if has_dirt else 2
        uv_channels.add(uv_chan)
    return uv_channels

def get_staticmesh_technique_from_maps(material):
    map_type_to_file = get_material_maps(material)
    technique = ''.join(map_type_to_file.keys())
    if technique in STATICMESH_TECHNIQUES:
        return technique
    return '' # invalid

def is_staticmesh_map_allowed(material, mapname):
    technique = ''
    for i, map_type in enumerate(TEXTURE_MAPS[material.bf2_shader]):
        if map_type == mapname:
            technique += map_type
            continue
        map_filepath = getattr(material, f"texture_slot_{i}")
        if map_filepath:
            technique += map_type
    return technique in STATICMESH_TECHNIQUES

def get_material_maps(material):
    texture_maps = OrderedDict()
    for i, map_type in enumerate(TEXTURE_MAPS[material.bf2_shader]):
        map_filepath = getattr(material, f"texture_slot_{i}")
        if map_filepath:
            texture_maps[map_type] = map_filepath
    return texture_maps

def get_tex_type_to_file_mapping(material, texture_files):
    texture_files = list(filter(lambda x: 'SpecularLUT_pow36' not in x, texture_files))

    map_name_to_file = dict()
    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        map_name_to_file['Color'] = texture_files[0]
        if len(texture_files) > 1:
            if material.bf2_shader == 'SKINNEDMESH':
                map_name_to_file['Normal'] = texture_files[1]
            elif texture_suffix_is_valid(texture_files[1], 'Normal'): # guess which is which by suffix
                map_name_to_file['Normal'] = texture_files[1]
            else:
                map_name_to_file['Wreck'] = texture_files[1]
        if len(texture_files) > 2:
            map_name_to_file['Wreck'] = texture_files[2]
    elif material.bf2_shader == 'STATICMESH':
        bf2_technique = None
        for sm_technique in STATICMESH_TECHNIQUES:
            if material.bf2_technique.lower() == sm_technique.lower():
                bf2_technique = sm_technique
                break
        if not bf2_technique:
            raise ImportException(f'Unsupported staticmesh technique "{material.bf2_technique}"')
        maps = _split_str_from_word_set(bf2_technique, set(STATICMESH_TEXUTRE_MAP_TYPES))
        if len(texture_files) != len(maps):
            raise ImportException(f'Material technique ({material.bf2_technique}) doesn\'t match number of texture maps ({len(texture_files)})')
        for map_name, tex_node in zip(maps, texture_files):
            map_name_to_file[map_name] = tex_node
    return map_name_to_file

def _socket(sockets, name, _type):
    for s in sockets:
        if s.name == name and s.type == _type:
            return s

def _sockets(sockets, name):
    s_list = list()
    for s in sockets:
        if s.name == name:
            s_list.append(s)
    return s_list

def _set_alpha_straigt(texture_node): # need this to render properly with Cycles
    if texture_node.image:
        texture_node.image.alpha_mode = 'STRAIGHT'

def setup_material(material, uvs=None, texture_paths=[], backface_cull=True, reporter=DEFAULT_REPORTER):
    material.use_nodes = True

    node_tree = material.node_tree
    node_tree.nodes.clear()
    material_output = node_tree.nodes.new('ShaderNodeOutputMaterial')
    material_output.name = material_output.label = 'Material Output'
    principled_BSDF = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled_BSDF.name = principled_BSDF.label = 'Principled BSDF'
    node_tree.links.new(principled_BSDF.outputs['BSDF'], material_output.inputs['Surface'])

    texture_maps = get_material_maps(material)

    if uvs is None:
        if material.bf2_shader == 'STATICMESH':
            uvs = get_staticmesh_uv_channels(texture_maps.keys())
        elif material.bf2_shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
            uvs = {0}

    # special staticmesh OG shaders
    is_leaf = is_trunk = False
    if material.bf2_shader == 'STATICMESH':
        is_vegitation = material.is_bf2_vegitation
        is_leaf = is_vegitation and len(texture_maps) == 1
        is_trunk = is_vegitation and len(texture_maps) > 1
        backface_cull = not is_vegitation # vegitation is always renders double sided

    material.use_backface_culling_shadow = backface_cull

    if backface_cull:
        attribute_backface = node_tree.nodes.new("ShaderNodeAttribute")
        attribute_backface.name = "Attribute"
        attribute_backface.hide = True
        attribute_backface.attribute_name = "backface"
        attribute_backface.attribute_type = 'GEOMETRY'
        attribute_backface.location = (-3 * NODE_WIDTH, 4 * NODE_HEIGHT)

        # abs(backface - 1)
        backface_subtract_1 = node_tree.nodes.new("ShaderNodeMath")
        backface_subtract_1.hide = True
        backface_subtract_1.operation = 'SUBTRACT'
        backface_subtract_1.inputs[1].default_value = 1.0
        backface_subtract_1.location = (-2 * NODE_WIDTH, 3 * NODE_HEIGHT)

        if 'Factor' in attribute_backface.outputs:
            backface_factor = attribute_backface.outputs['Factor']
        else:
            backface_factor = attribute_backface.outputs['Fac'] # pre Blender 5.0

        node_tree.links.new(backface_factor, backface_subtract_1.inputs[0])

        backface_abs = node_tree.nodes.new("ShaderNodeMath")
        backface_abs.hide = True
        backface_abs.operation = 'ABSOLUTE'
        backface_abs.location = (-1 * NODE_WIDTH, 3 * NODE_HEIGHT)

        node_tree.links.new(backface_subtract_1.outputs['Value'], backface_abs.inputs[0])

        geometry = node_tree.nodes.new("ShaderNodeNewGeometry")
        geometry.location = (-3 * NODE_WIDTH, 3 * NODE_HEIGHT)
        geometry.hide = True

        backface_mult = node_tree.nodes.new("ShaderNodeMath")
        backface_mult.operation = 'MULTIPLY'
        backface_mult.hide = True
        backface_mult.location = (0 * NODE_WIDTH, 3 * NODE_HEIGHT)

        # mult both == if backface set => treat face as double sided regardless of 'Backfacing' value
        node_tree.links.new(backface_abs.outputs['Value'], backface_mult.inputs[0])
        node_tree.links.new(geometry.outputs['Backfacing'], backface_mult.inputs[1])

        # compare == *exclusive or* between 'Backfacing' and 'Is Shadow Ray'
        compare = node_tree.nodes.new("ShaderNodeMath")
        compare.operation = 'COMPARE'
        compare.location = (1 * NODE_WIDTH, 3 * NODE_HEIGHT)
        compare.hide = True

        light_path = node_tree.nodes.new("ShaderNodeLightPath")
        light_path.location = (0 * NODE_WIDTH, 4 * NODE_HEIGHT)
        light_path.hide = True

        node_tree.links.new(backface_mult.outputs['Value'], compare.inputs[1])
        node_tree.links.new(light_path.outputs['Is Shadow Ray'], compare.inputs[0])
        backface_cull_alpha = compare.outputs['Value']
    else:
        backface_cull_alpha = None

    # alpha mode
    has_alphatest = has_alphablend = False
    if is_trunk:
        material.blend_method = 'OPAQUE'
    elif is_leaf:
        has_alphatest = True
        material.blend_method = 'CLIP'
    else:
        if material.bf2_alpha_mode == 'NONE':
            material.blend_method = 'OPAQUE'
        elif material.bf2_alpha_mode == 'ALPHA_TEST':
            has_alphatest = True
            material.blend_method = 'CLIP'
        elif material.bf2_alpha_mode == 'ALPHA_BLEND':
            has_alphablend = True
            material.blend_method = 'BLEND'
        else:
            raise RuntimeError(f"Unknown alpha mode '{material.bf2_alpha_mode}'")

    # create UV map nodes
    uv_map_nodes = dict()
    for uv_chan in uvs:
        uv = node_tree.nodes.new('ShaderNodeUVMap')
        uv.uv_map = f'UV{uv_chan}'
        uv.location = (-2 * NODE_WIDTH, -uv_chan * NODE_HEIGHT)
        uv.hide = True
        uv_map_nodes[uv_chan] = uv

    # load textures
    texture_nodes = dict()
    for map_index, (texture_map_type, texture_map_file) in enumerate(texture_maps.items()):
        if not texture_paths:
            reporter.warning("MOD path is not defined in add-on preferences!")
        for texture_path in texture_paths:
            abs_path = os.path.join(texture_path, texture_map_file)
            if os.path.isfile(abs_path):
                break
        else:
            if texture_paths:
                reporter.warning(f"Texture file '{texture_map_file}' not found in any of the texture paths")
            abs_path = ''
        tex_node = node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.label = tex_node.name = texture_map_type
        tex_node.location = (-1 * NODE_WIDTH, -map_index * NODE_HEIGHT)
        tex_node.hide = True
        texture_nodes[texture_map_type] = tex_node
        if abs_path:
            tex_node.image = bpy.data.images.load(abs_path, check_existing=True)
            tex_node.image.alpha_mode = 'NONE'

    shader_base_color = principled_BSDF.inputs['Base Color']
    shader_ior_level = principled_BSDF.inputs['Specular IOR Level']
    shader_roughness = principled_BSDF.inputs['Roughness']
    shader_normal = principled_BSDF.inputs['Normal']
    shader_alpha = principled_BSDF.inputs['Alpha']
    shader_ior = principled_BSDF.inputs['IOR']

    # these settings seem the most BF2-like
    shader_roughness.default_value = 0.4 # how sharp the reflection is, 0 == perfect mirror
    shader_ior_level.default_value = 0.3 # this just scales the IOR, value above 0.5 increases it while below 0.5 decreases it
    shader_ior.default_value = 1.0 # this is lowest possible value

    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        UV_CHANNEL = 0

        technique = material.bf2_technique.lower()
        has_envmap = 'envmap' in technique and material.bf2_shader == 'BUNDLEDMESH'
        has_colormapgloss = 'colormapgloss' in technique and material.bf2_shader == 'BUNDLEDMESH'
        has_dot3alpha_test = has_alphatest and has_colormapgloss

        diffuse = texture_nodes['Color']
        normal = texture_nodes.get('Normal')
        shadow = texture_nodes.get('Wreck')

        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs['UV'], diffuse.inputs['Vector'])
        if normal:
            node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs['UV'], normal.inputs['Vector'])
        if shadow:
            node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs['UV'], shadow.inputs['Vector'])

        if normal and normal.image:
            normal.image.colorspace_settings.name = 'Non-Color'

        # diffuse
        if shadow:
            # multiply diffuse and shadow
            multiply_diffuse = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_diffuse.inputs['Fac'].default_value = 1
            multiply_diffuse.blend_type = 'MULTIPLY'
            multiply_diffuse.location = (1 * NODE_WIDTH, -3 * NODE_HEIGHT)
            multiply_diffuse.hide = True

            node_tree.links.new(shadow.outputs['Color'], multiply_diffuse.inputs['Color1'])
            node_tree.links.new(diffuse.outputs['Color'], multiply_diffuse.inputs['Color2'])
            shadow_out = multiply_diffuse.outputs['Color']
        else:
            shadow_out = diffuse.outputs['Color']

        node_tree.links.new(shadow_out, shader_base_color)

        # specular/roughness

        specular_txt = None
        if has_colormapgloss:
            specular_txt = diffuse
        else:
            specular_txt = normal

        spec_out = None
        if specular_txt:
            if shadow:
                # multiply diffuse and shadow
                multiply_diffuse = node_tree.nodes.new('ShaderNodeMixRGB')
                multiply_diffuse.inputs['Fac'].default_value = 1
                multiply_diffuse.blend_type = 'MULTIPLY'
                multiply_diffuse.location = (1 * NODE_WIDTH, -2 * NODE_HEIGHT)
                multiply_diffuse.hide = True

                node_tree.links.new(shadow.outputs['Color'], multiply_diffuse.inputs['Color1'])
                node_tree.links.new(specular_txt.outputs['Alpha'], multiply_diffuse.inputs['Color2'])
                spec_out = multiply_diffuse.outputs['Color']
            else:
                spec_out = specular_txt.outputs['Alpha']

            # convert specular map value to fresnel IOR in range 1..2 by adding one
            spec_to_ior = node_tree.nodes.new('ShaderNodeMath')
            spec_to_ior.operation = 'ADD'
            spec_to_ior.location = (2 * NODE_WIDTH, -1 * NODE_HEIGHT)
            spec_to_ior.inputs[1].default_value = 1.0
            spec_to_ior.hide = True

            node_tree.links.new(spec_out, spec_to_ior.inputs[0])
            node_tree.links.new(spec_to_ior.outputs['Value'], shader_ior)

        # normal
        if normal:
            normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
            normal_node.location = (1 * NODE_WIDTH, -1 * NODE_HEIGHT)
            normal_node.hide = True
            normal_node.space = 'TANGENT'
            normal_node.uv_map = uv_map_nodes[UV_CHANNEL].uv_map

            node_tree.links.new(normal.outputs['Color'], normal_node.inputs['Color'])
            normal_out = normal_node.outputs['Normal']

            is_os = normal.image and file_name(normal.image.name).endswith('_b_os')
            if material.bf2_shader == 'SKINNEDMESH' and is_os:
                if hasattr(bpy.types,'GeometryNodeUVTangent'):
                    # dynamically convert object space normals to tangent space normals
                    # fixes bad shading when mesh is deformed
                    os_to_b = node_tree.nodes.new('ShaderNodeGroup')
                    os_to_b.node_tree = _create_os_to_b_converter()
                    os_to_b.location = (0.5 * NODE_WIDTH, -1 * NODE_HEIGHT)
                    os_to_b.hide = True
                    node_tree.links.new(normal.outputs['Color'], os_to_b.inputs['Color'])
                    node_tree.links.new(os_to_b.outputs['Color'], normal_node.inputs['Color'])
                else:
                    # not Blender 5.0, use normal Object Space normal mapping
                    normal_node.space = 'OBJECT'
                    axes_swap = node_tree.nodes.new('ShaderNodeGroup')
                    axes_swap.node_tree = _create_bf2_axes_swap()
                    axes_swap.location = (0.5 * NODE_WIDTH, -1 * NODE_HEIGHT)
                    axes_swap.hide = True
                    node_tree.links.new(normal.outputs['Color'], normal_node.inputs['Color'])
                    node_tree.links.new(normal_out, axes_swap.inputs['in'])
                    normal_out = axes_swap.outputs['out']

            node_tree.links.new(normal_out, shader_normal)

        # transparency
        alpha_out = None
        if has_alphablend or has_alphatest:
            _set_alpha_straigt(diffuse)
            alpha_out = diffuse.outputs['Alpha']

            if has_dot3alpha_test:
                dot_product = node_tree.nodes.new("ShaderNodeVectorMath")
                dot_product.hide = True
                dot_product.operation = 'DOT_PRODUCT'
                dot_product.inputs[1].default_value = (1, 1, 1)
                node_tree.links.new(diffuse.outputs['Color'], dot_product.inputs[0])

                alpha_ref = node_tree.nodes.new('ShaderNodeMath')
                alpha_ref.operation = 'GREATER_THAN'
                alpha_ref.inputs[1].default_value = 0.03
                node_tree.links.new(dot_product.outputs['Value'], alpha_ref.inputs[0])
                alpha_out = alpha_ref.outputs['Value']

            if backface_cull:
                mult_backface = node_tree.nodes.new('ShaderNodeMath')
                mult_backface.operation = 'MULTIPLY'
                mult_backface.location = (2 * NODE_WIDTH, 3 * NODE_HEIGHT)
                mult_backface.hide = True
                node_tree.links.new(alpha_out, mult_backface.inputs[1])
                node_tree.links.new(backface_cull_alpha, mult_backface.inputs[0])
                alpha_out = mult_backface.outputs['Value']

        elif backface_cull:
            alpha_out = backface_cull_alpha

        if alpha_out:
            node_tree.links.new(alpha_out, shader_alpha)

        # envmap reflections
        if has_envmap:
            glossy_BSDF = node_tree.nodes.new('ShaderNodeBsdfGlossy')
            glossy_BSDF.inputs['Roughness'].default_value = 0.05
            mix_envmap = node_tree.nodes.new('ShaderNodeMixShader')

            # scale envmap with gloss
            mix_envmap.inputs['Factor'].default_value = 1.0
            if spec_out:
                node_tree.links.new(spec_out, mix_envmap.inputs['Factor'])

            # add transparency
            if alpha_out:
                transparent_BSDF = node_tree.nodes.new('ShaderNodeBsdfTransparent')
                mix_transparency = node_tree.nodes.new('ShaderNodeMixShader')
                node_tree.links.new(transparent_BSDF.outputs['BSDF'], _sockets(mix_transparency.inputs, 'Shader')[0])
                node_tree.links.new(glossy_BSDF.outputs['BSDF'], _sockets(mix_transparency.inputs, 'Shader')[1])
                node_tree.links.new(alpha_out, mix_transparency.inputs['Factor'])
                glossy_out = mix_transparency.outputs['Shader']
            else:
                glossy_out = glossy_BSDF.outputs['BSDF']

            node_tree.links.new(principled_BSDF.outputs['BSDF'], _sockets(mix_envmap.inputs, 'Shader')[0])
            node_tree.links.new(glossy_out, _sockets(mix_envmap.inputs, 'Shader')[1])

            mix_envmap_out = mix_envmap.outputs['Shader']
        else:
            mix_envmap_out = principled_BSDF.outputs['BSDF']

        node_tree.links.new(mix_envmap_out, material_output.inputs['Surface'])

        principled_BSDF.location = (3 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)

    elif material.bf2_shader == 'STATICMESH':

        def _link_uv_chan(uv_chan, tex_node):
            node_tree.links.new(uv_map_nodes[uv_chan].outputs['UV'], tex_node.inputs['Vector'])

        base = texture_nodes['Base']
        detail = texture_nodes.get('Detail')
        dirt = texture_nodes.get('Dirt')
        crack = texture_nodes.get('Crack')
        ndetail = texture_nodes.get('NDetail')
        ncrack = texture_nodes.get('NCrack')

        # link uv nodes with textures
        _link_uv_chan(0, base)
        if detail:  _link_uv_chan(1, detail)
        if dirt:    _link_uv_chan(2, dirt)
        if crack:   _link_uv_chan(3 if dirt else 2, crack)
        if ndetail: _link_uv_chan(1, ndetail)
        if ncrack:  _link_uv_chan(3 if dirt else 2, ncrack)

        # change normal maps color space
        if ndetail and ndetail.image:
            ndetail.image.colorspace_settings.name = 'Non-Color'
        if ncrack and ncrack.image:
            ncrack.image.colorspace_settings.name = 'Non-Color'

        # ---- diffuse ----
        if detail:
            if is_trunk:
                # multiply detail by 2
                boost_detail = node_tree.nodes.new('ShaderNodeMixRGB')
                boost_detail.inputs['Fac'].default_value = 1
                boost_detail.blend_type = 'MULTIPLY'
                boost_detail.location = (0 * NODE_WIDTH, 0 * NODE_HEIGHT)
                boost_detail.hide = True

                value_2 = node_tree.nodes.new('ShaderNodeValue')
                value_2.outputs['Value'].default_value = 2.0
                boost_detail.location = (0 * NODE_WIDTH, 0 * NODE_HEIGHT)
                boost_detail.hide = True

                node_tree.links.new(value_2.outputs['Value'], boost_detail.inputs['Color1'])
                node_tree.links.new(detail.outputs['Color'], boost_detail.inputs['Color2'])
                detail_color_out = boost_detail.outputs['Color']
            else:
                detail_color_out = detail.outputs['Color']

            # multiply detail and base color
            multiply_detail = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_detail.inputs['Fac'].default_value = 1
            multiply_detail.blend_type = 'MULTIPLY'
            multiply_detail.location = (0 * NODE_WIDTH, 0 * NODE_HEIGHT)
            multiply_detail.hide = True

            node_tree.links.new(base.outputs['Color'], multiply_detail.inputs['Color1'])
            node_tree.links.new(detail_color_out, multiply_detail.inputs['Color2'])
            detail_out = multiply_detail.outputs['Color']
        else:
            detail_out = base.outputs[0]

        if crack:
            _set_alpha_straigt(crack)
            # mix detail & crack color based on crack alpha
            mix_crack = node_tree.nodes.new('ShaderNodeMixRGB')
            mix_crack.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
            mix_crack.hide = True

            node_tree.links.new(crack.outputs['Alpha'], mix_crack.inputs['Fac'])
            node_tree.links.new(detail_out, mix_crack.inputs['Color1'])
            node_tree.links.new(crack.outputs['Color'], mix_crack.inputs['Color2'])
            crack_out = mix_crack.outputs['Color']
        else:
            crack_out = detail_out

        if dirt:
            # multiply dirt and diffuse
            multiply_dirt = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_dirt.inputs['Fac'].default_value = 1
            multiply_dirt.blend_type = 'MULTIPLY'
            multiply_dirt.location = (2 * NODE_WIDTH, 0 * NODE_HEIGHT)
            multiply_dirt.hide = True

            node_tree.links.new(crack_out, multiply_dirt.inputs['Color1'])
            node_tree.links.new(dirt.outputs['Color'], multiply_dirt.inputs['Color2'])
            dirt_out = multiply_dirt.outputs['Color']
        else:
            dirt_out = crack_out

        # finally link to shader
        node_tree.links.new(dirt_out, shader_base_color)

        # ---- specular ----
        if not is_vegitation:
            if dirt and detail:
                # dirt.r * dirt.g * dirt.b
                dirt_rgb_mult = node_tree.nodes.new('ShaderNodeGroup')
                dirt_rgb_mult.node_tree = _create_multiply_rgb_shader_node()
                dirt_rgb_mult.location = (0 * NODE_WIDTH, -1 * NODE_HEIGHT)
                dirt_rgb_mult.hide = True

                node_tree.links.new(dirt.outputs['Color'], dirt_rgb_mult.inputs['color'])

                # multiply that with detailmap alpha
                mult_detaila = node_tree.nodes.new('ShaderNodeMath')
                mult_detaila.operation = 'MULTIPLY'
                mult_detaila.location = (0 * NODE_WIDTH, -1 * NODE_HEIGHT)
                mult_detaila.hide = True

                mult_detaila_values = _sockets(mult_detaila.inputs, 'Value')
                node_tree.links.new(dirt_rgb_mult.outputs['value'], mult_detaila_values[1])
                node_tree.links.new(detail.outputs['Alpha'], mult_detaila_values[0])
                dirt_spec_out = mult_detaila.outputs['Value']
            elif detail:
                dirt_spec_out = detail.outputs['Alpha']
            else:
                dirt_spec_out = None

            if has_alphatest and ndetail:
                # mult with detaimap normal alpha
                mult_ndetaila = node_tree.nodes.new('ShaderNodeMath')
                mult_ndetaila.operation = 'MULTIPLY'
                mult_ndetaila.location = (1 * NODE_WIDTH, -1 * NODE_HEIGHT)
                mult_ndetaila.hide = True

                mult_ndetaila_values = _sockets(mult_ndetaila.inputs, 'Value')
                node_tree.links.new(dirt_spec_out, mult_ndetaila_values[1])
                node_tree.links.new(ndetail.outputs['Alpha'], mult_ndetaila_values[0])
                spec_out = mult_ndetaila.outputs['Value']
            elif detail:
                spec_out = dirt_spec_out
            else:
                spec_out = None

            if spec_out:
                # convert specular map value to fresnel IOR in range 1..2 by adding one
                spec_to_ior = node_tree.nodes.new('ShaderNodeMath')
                spec_to_ior.operation = 'ADD'
                spec_to_ior.location = (3 * NODE_WIDTH, -1 * NODE_HEIGHT)
                spec_to_ior.inputs[1].default_value = 1.0
                spec_to_ior.hide = True

                node_tree.links.new(spec_out, spec_to_ior.inputs[0])
                node_tree.links.new(spec_to_ior.outputs['Value'], shader_ior)

        # ---- normal  ----

        normal_out = None

        def _create_normal_map_node(nmap, uv_chan):
            # convert to normal
            normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
            normal_node.uv_map = uv_map_nodes[uv_chan].uv_map
            normal_node.location = (1 * NODE_WIDTH, -1 - uv_chan * NODE_HEIGHT)
            normal_node.hide = True
            node_tree.links.new(nmap.outputs['Color'], normal_node.inputs['Color'])
            return normal_node.outputs['Normal']

        ndetail_out = ndetail and _create_normal_map_node(ndetail, 1)
        ncrack_out = ncrack and _create_normal_map_node(ncrack, 3 if dirt else 2)

        if ndetail_out and ncrack_out:
            # mix ndetail & ncrack based on crack alpha
            mix_normal = node_tree.nodes.new('ShaderNodeMix')
            mix_normal.data_type = 'VECTOR'
            mix_normal.location = (3 * NODE_WIDTH, -3 * NODE_HEIGHT)
            mix_normal.hide = True

            node_tree.links.new(crack.outputs['Alpha'], mix_normal.inputs['Factor'])
            node_tree.links.new(ndetail_out, _socket(mix_normal.inputs, 'A', 'VECTOR'))
            node_tree.links.new(ncrack_out, _socket(mix_normal.inputs, 'B', 'VECTOR'))
            normal_out = _socket(mix_normal.outputs, 'Result', 'VECTOR')
        elif ndetail_out:
            normal_out = ndetail_out

        if normal_out:
            node_tree.links.new(normal_out, shader_normal)

        # ---- transparency ------
        alpha_out = None
        if has_alphatest:
            if detail:
                _set_alpha_straigt(detail)
                alpha_out = detail.outputs['Alpha']
            else:
                _set_alpha_straigt(base)
                alpha_out = base.outputs['Alpha']

            if backface_cull:
                mult_backface = node_tree.nodes.new('ShaderNodeMath')
                mult_backface.operation = 'MULTIPLY'
                mult_backface.location = (2 * NODE_WIDTH, 3 * NODE_HEIGHT)
                mult_backface.hide = True
                node_tree.links.new(alpha_out, mult_backface.inputs[1])
                node_tree.links.new(backface_cull_alpha, mult_backface.inputs[0])
                alpha_out = mult_backface.outputs['Value']
        elif backface_cull:
            alpha_out = backface_cull_alpha

        if alpha_out:
            node_tree.links.new(alpha_out, shader_alpha)

        principled_BSDF.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (5 * NODE_WIDTH, 0 * NODE_HEIGHT)
