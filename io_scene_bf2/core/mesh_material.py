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
BUNDLEDMESH_TEXTURE_MAP_TYPES = ['Diffuse', 'Normal', 'Wreck']
SKINNEDMESH_TEXTURE_MAP_TYPES = ['Diffuse', 'Normal']

TEXTURE_MAPS = {
    'STATICMESH': STATICMESH_TEXUTRE_MAP_TYPES,
    'BUNDLEDMESH': BUNDLEDMESH_TEXTURE_MAP_TYPES,
    'SKINNEDMESH': SKINNEDMESH_TEXTURE_MAP_TYPES
}

TEXTURE_TYPE_TO_SUFFIXES = {
    # BundledMesh/SkinnedMesh
    'Diffuse': ('_c',),
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
        map_name_to_file['Diffuse'] = texture_files[0]
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
        geometry = node_tree.nodes.new("ShaderNodeNewGeometry")
        geometry.location = (0 * NODE_WIDTH, 3 * NODE_HEIGHT)
        geometry.hide = True
        light_path = node_tree.nodes.new("ShaderNodeLightPath")
        light_path.location = (0 * NODE_WIDTH, 4 * NODE_HEIGHT)
        light_path.hide = True
        # use comapre as exclusive or gate
        compare = node_tree.nodes.new("ShaderNodeMath")
        compare.operation = 'COMPARE'
        compare.location = (1 * NODE_WIDTH, 3 * NODE_HEIGHT)
        compare.hide = True
        node_tree.links.new(geometry.outputs['Backfacing'], compare.inputs[1])
        node_tree.links.new(light_path.outputs['Is Shadow Ray'], compare.inputs[0])
        backface_cull_alpha = compare.outputs['Value']
    else:
        backface_cull_alpha = None

    # alpha mode
    has_alpha = False
    if is_trunk:
        material.blend_method = 'OPAQUE'
    elif is_leaf:
        has_alpha = True
        material.blend_method = 'CLIP'
    else:
        if material.bf2_alpha_mode == 'NONE':
            material.blend_method = 'OPAQUE'
        elif material.bf2_alpha_mode == 'ALPHA_TEST':
            has_alpha = True
            material.blend_method = 'CLIP'
        elif material.bf2_alpha_mode == 'ALPHA_BLEND':
            has_alpha = True
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
    shader_specular = principled_BSDF.inputs['Specular IOR Level']
    shader_roughness = principled_BSDF.inputs['Roughness']
    shader_normal = principled_BSDF.inputs['Normal']
    shader_alpha = principled_BSDF.inputs['Alpha']
    shader_ior = principled_BSDF.inputs['IOR']

    shader_roughness.default_value = 1
    shader_specular.default_value = 0
    shader_ior.default_value = 1.1
    ROUGHNESS_BASE = 0.25

    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        UV_CHANNEL = 0

        technique = material.bf2_technique.lower()
        has_envmap = 'envmap' in technique and material.bf2_shader == 'BUNDLEDMESH'
        has_alphatest = 'alpha_test' in technique and material.bf2_shader == 'SKINNEDMESH'

        diffuse = texture_nodes['Diffuse']
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
        if material.bf2_shader == 'SKINNEDMESH':
            specular_txt = normal
        elif has_alpha: # BM with alpha
            specular_txt = normal
        else:
            specular_txt = diffuse

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
                shadow_spec_out = multiply_diffuse.outputs['Color']
            else:
                shadow_spec_out = specular_txt.outputs['Alpha']

            node_tree.links.new(shadow_spec_out, shader_specular)

            # remap range to reduce roughness, to appear more like in BF2
            # (purely based on tiral & error, I don't know how this works in BF2 shaders)
            reduce_roughness = node_tree.nodes.new('ShaderNodeMapRange')
            reduce_roughness.inputs['To Min'].default_value = ROUGHNESS_BASE
            reduce_roughness.location = (3 * NODE_WIDTH, NODE_HEIGHT)
            reduce_roughness.hide = True
            node_tree.links.new(shadow_spec_out, reduce_roughness.inputs['Value'])
            node_tree.links.new(reduce_roughness.outputs['Result'], shader_roughness)

        # normal
        if normal:
            normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
            normal_node.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
            normal_node.hide = True
            node_tree.links.new(normal.outputs['Color'], normal_node.inputs['Color'])

            if material.bf2_shader == 'SKINNEDMESH':
                normal_node.space = 'OBJECT'
                # since this is object space normal we gotta swap Z/Y axes for it to look correct
                axes_swap = node_tree.nodes.new('ShaderNodeGroup')
                axes_swap.node_tree = _create_bf2_axes_swap()
                axes_swap.location = (2 * NODE_WIDTH, -1 * NODE_HEIGHT)
                axes_swap.hide = True
        
                node_tree.links.new(normal_node.outputs['Normal'], axes_swap.inputs['in'])
                normal_out = axes_swap.outputs['out']
            else:
                normal_node.uv_map = uv_map_nodes[UV_CHANNEL].uv_map
                normal_out = normal_node.outputs['Normal']

            node_tree.links.new(normal_out, shader_normal)

        # transparency
        alpha_out = None
        if has_alpha or has_alphatest:
            _set_alpha_straigt(diffuse)
            alpha_out = diffuse.outputs['Alpha']
            if backface_cull:
                mult_backface = node_tree.nodes.new('ShaderNodeMath')
                mult_backface.operation = 'MULTIPLY'
                mult_backface.location = (2 * NODE_WIDTH, 3 * NODE_HEIGHT)
                mult_backface.hide = True
                node_tree.links.new(diffuse.outputs['Alpha'], mult_backface.inputs[1])
                node_tree.links.new(backface_cull_alpha, mult_backface.inputs[0])
                alpha_out = mult_backface.outputs['Value']
        elif backface_cull:
            alpha_out = backface_cull_alpha

        if alpha_out:
            node_tree.links.new(alpha_out, shader_alpha)

        # envmap reflections
        if has_envmap:
            glossy_BSDF = node_tree.nodes.new('ShaderNodeBsdfGlossy')
            glossy_BSDF.inputs['Roughness'].default_value = 0.1
            mix_envmap = node_tree.nodes.new('ShaderNodeMixShader')

            mix_envmap_shaders = _sockets(mix_envmap.inputs, 'Shader')
            node_tree.links.new(principled_BSDF.outputs['BSDF'], mix_envmap_shaders[1])
            node_tree.links.new(glossy_BSDF.outputs['BSDF'], mix_envmap_shaders[0])
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

            if has_alpha and ndetail:
                # mult with detaimap normal alpha
                mult_ndetaila = node_tree.nodes.new('ShaderNodeMath')
                mult_ndetaila.operation = 'MULTIPLY'
                mult_ndetaila.location = (1 * NODE_WIDTH, -1 * NODE_HEIGHT)
                mult_ndetaila.hide = True

                mult_ndetaila_values = _sockets(mult_ndetaila.inputs, 'Value')
                node_tree.links.new(dirt_spec_out, mult_ndetaila_values[1])
                node_tree.links.new(ndetail.outputs['Alpha'], mult_ndetaila_values[0])
                has_alpha_out = mult_ndetaila.outputs['Value']
            elif detail:
                has_alpha_out = dirt_spec_out
            else:
                has_alpha_out = None

            if has_alpha_out:
                node_tree.links.new(has_alpha_out, shader_specular)

                reduce_roughness = node_tree.nodes.new('ShaderNodeMapRange')
                reduce_roughness.inputs['To Min'].default_value = ROUGHNESS_BASE
                reduce_roughness.location = (3 * NODE_WIDTH, NODE_HEIGHT)
                reduce_roughness.hide = True
                node_tree.links.new(has_alpha_out, reduce_roughness.inputs['Value'])
                node_tree.links.new(reduce_roughness.outputs["Result"], shader_roughness)

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
        if has_alpha:
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
