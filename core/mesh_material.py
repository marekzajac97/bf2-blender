import bpy
import os
from collections import OrderedDict

from .utils import DEFAULT_REPORTER
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
BUNDLEDMESH_TEXTURE_MAP_TYPES = ['Diffuse', 'Normal', 'Shadow']
SKINNEDMESH_TEXTURE_MAP_TYPES = ['Diffuse', 'Normal']

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
    bf2_axes_swap.links.new(swap_yz_decompose.outputs[0], swap_yz_compose.inputs[0])
    bf2_axes_swap.links.new(swap_yz_decompose.outputs[2], swap_yz_compose.inputs[1])
    bf2_axes_swap.links.new(swap_yz_decompose.outputs[1], swap_yz_compose.inputs[2])

    bf2_axes_swap.links.new(group_inputs.outputs['in'], swap_yz_decompose.inputs[0])
    bf2_axes_swap.links.new(swap_yz_compose.outputs[0], group_outputs.inputs['out'])

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

    multi_rgb.links.new(node_separate_color.outputs[0], node_multiply_rg.inputs[0])
    multi_rgb.links.new(node_separate_color.outputs[1], node_multiply_rg.inputs[1])
    multi_rgb.links.new(node_separate_color.outputs[2], node_multiply_rgb.inputs[0])
    multi_rgb.links.new(node_multiply_rg.outputs[0], node_multiply_rgb.inputs[1])

    multi_rgb.links.new(group_inputs.outputs['color'], node_separate_color.inputs[0])
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

TEXTURE_MAPS = {
    'STATICMESH': STATICMESH_TEXUTRE_MAP_TYPES,
    'BUNDLEDMESH': BUNDLEDMESH_TEXTURE_MAP_TYPES,
    'SKINNEDMESH': SKINNEDMESH_TEXTURE_MAP_TYPES
}

def get_material_maps(material):
    texture_maps = OrderedDict()
    for i, map_type in enumerate(TEXTURE_MAPS[material.bf2_shader]):
        map_filepath = getattr(material, f"texture_slot_{i}")
        if map_filepath:
            map_filepath = bpy.path.abspath(map_filepath)
            texture_maps[map_type] = map_filepath
    return texture_maps

def get_tex_type_to_file_mapping(shader, techinique, texture_files, texture_path='', reporter=DEFAULT_REPORTER):
    texture_files = list(filter(lambda x: 'SpecularLUT_pow36' not in x, texture_files))

    map_name_to_file = dict()
    if shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        map_name_to_file['Diffuse'] = texture_files[0]
        if len(texture_files) > 1:
            map_name_to_file['Normal'] = texture_files[1]
        if len(texture_files) > 2:
            map_name_to_file['Shadow'] = texture_files[2]
    elif shader == 'STATICMESH':
        if techinique not in STATICMESH_TECHNIQUES:
            raise ImportException(f'Unsupported staticmesh technique "{techinique}"')
        maps = _split_str_from_word_set(techinique, set(STATICMESH_TEXUTRE_MAP_TYPES))
        if len(texture_files) != len(maps):
            raise ImportException(f'Material technique ({techinique}) doesn\'t match number of texture maps ({len(texture_files)})')
        for map_name, tex_node in zip(maps, texture_files):
            map_name_to_file[map_name] = tex_node

    # convert to absolute paths:
    if texture_path:
        for map_type, texture_map_file in map_name_to_file.items():
            if not os.path.isabs(texture_map_file):
                # not an absolute path but we have base path
                map_name_to_file[map_type] = os.path.join(texture_path, texture_map_file)
    else:
        reporter.warning("Mod path is not defined in add-on preferences, textures won't load")

    return map_name_to_file

def setup_material(material, uvs=None):
    material.use_nodes = True
    node_tree = material.node_tree
    node_tree.nodes.clear()
    material_output = node_tree.nodes.new('ShaderNodeOutputMaterial')
    material_output.name = material_output.label = 'Material Output'
    principled_BSDF = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled_BSDF.name = principled_BSDF.label = 'Principled BSDF'
    node_tree.links.new(principled_BSDF.outputs[0], material_output.inputs[0])

    texture_maps = get_material_maps(material)

    if uvs is None:
        if material.bf2_shader == 'STATICMESH':
            uvs = get_staticmesh_uv_channels(texture_maps.keys())
        elif material.bf2_shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
            uvs = {0}

    # alpha mode
    has_alpha = False
    if material.bf2_alpha_mode == 'ALPHA_BLEND':
        has_alpha = True
        material.blend_method = 'BLEND'
    elif material.bf2_alpha_mode == 'ALPHA_TEST':
        has_alpha = True
        material.blend_method = 'CLIP'
    elif material.bf2_alpha_mode == 'NONE':
        material.blend_method = 'OPAQUE'
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
        tex_node = node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.label = tex_node.name = texture_map_type
        tex_node.location = (-1 * NODE_WIDTH, -map_index * NODE_HEIGHT)
        tex_node.hide = True
        texture_nodes[texture_map_type] = tex_node

        try:
            tex_node.image = bpy.data.images.load(texture_map_file, check_existing=True)
            tex_node.image.alpha_mode = 'NONE'
        except RuntimeError:
            pass # ignore if file not found

    shader_base_color = principled_BSDF.inputs[0]
    shader_specular = principled_BSDF.inputs[12]
    shader_roughness = principled_BSDF.inputs[2]
    shader_normal = principled_BSDF.inputs[5]
    shader_alpha = principled_BSDF.inputs[4]
    shader_ior = principled_BSDF.inputs[3]

    shader_roughness.default_value = 1
    shader_specular.default_value = 0
    shader_ior.default_value = 1.1
    ROUGHNESS_BASE = 0.25

    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH'):
        UV_CHANNEL = 0

        # TODO SETUP it properly based on techinique

        has_envmap = 'envmap' in material.bf2_technique.lower()

        diffuse = texture_nodes['Diffuse']
        normal = texture_nodes.get('Normal')
        shadow = texture_nodes.get('Shadow')

        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], diffuse.inputs[0])
        if normal:
            node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], normal.inputs[0])
        if shadow:
            node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], shadow.inputs[0])

        if normal and normal.image:
            normal.image.colorspace_settings.name = 'Non-Color'

        # diffuse
        if shadow:
            # multiply diffuse and shadow
            multiply_diffuse = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_diffuse.inputs[0].default_value = 1
            multiply_diffuse.blend_type = 'MULTIPLY'
            multiply_diffuse.location = (1 * NODE_WIDTH, -3 * NODE_HEIGHT)
            multiply_diffuse.hide = True

            node_tree.links.new(shadow.outputs[0], multiply_diffuse.inputs[1])
            node_tree.links.new(diffuse.outputs[0], multiply_diffuse.inputs[2])
            shadow_out = multiply_diffuse.outputs[0]
        else:
            shadow_out = diffuse.outputs[0]

        node_tree.links.new(shadow_out, shader_base_color)

        # specular/roughness

        specular_txt = None
        if material.bf2_shader == 'SKINNEDMESH':
            specular_txt = normal
        elif has_alpha:
            specular_txt = normal
        else:
            specular_txt = diffuse

        if specular_txt:
            if shadow:
                # multiply diffuse and shadow
                multiply_diffuse = node_tree.nodes.new('ShaderNodeMixRGB')
                multiply_diffuse.inputs[0].default_value = 1
                multiply_diffuse.blend_type = 'MULTIPLY'
                multiply_diffuse.location = (1 * NODE_WIDTH, -2 * NODE_HEIGHT)
                multiply_diffuse.hide = True

                node_tree.links.new(shadow.outputs[0], multiply_diffuse.inputs[1])
                node_tree.links.new(specular_txt.outputs[1], multiply_diffuse.inputs[2])
                shadow_spec_out = multiply_diffuse.outputs[0]
            else:
                shadow_spec_out = specular_txt.outputs[1]

            node_tree.links.new(shadow_spec_out, shader_specular)

            # remap range to reduce roughness, to appear more like in BF2
            # (purely based on tiral & error, I don't know how this works in BF2 shaders)
            reduce_roughness = node_tree.nodes.new('ShaderNodeMapRange')
            reduce_roughness.inputs[3].default_value = ROUGHNESS_BASE
            node_tree.links.new(shadow_spec_out, reduce_roughness.inputs[0])

            node_tree.links.new(reduce_roughness.outputs[0], shader_roughness)

        # normal
        if normal:
            normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
            normal_node.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
            normal_node.hide = True
            node_tree.links.new(normal.outputs[0], normal_node.inputs[1])

            if material.bf2_shader == 'SKINNEDMESH':
                normal_node.space = 'OBJECT'
                # since this is object space normal we gotta swap Z/Y axes for it to look correct
                axes_swap = node_tree.nodes.new('ShaderNodeGroup')
                axes_swap.node_tree = _create_bf2_axes_swap()
                axes_swap.location = (2 * NODE_WIDTH, -1 * NODE_HEIGHT)
                axes_swap.hide = True
        
                node_tree.links.new(normal_node.outputs[0], axes_swap.inputs[0])
                normal_out = axes_swap.outputs[0]
            else:
                normal_node.uv_map = uv_map_nodes[UV_CHANNEL].uv_map
                normal_out = normal_node.outputs[0]

            node_tree.links.new(normal_out, shader_normal)

        # transparency
        if has_alpha:
            node_tree.links.new(diffuse.outputs[1], shader_alpha)

        # envmap reflections
        if has_envmap:
            glossy_BSDF = node_tree.nodes.new('ShaderNodeBsdfGlossy')
            glossy_BSDF.inputs[1].default_value = 0.1 # roughness
            mix_envmap = node_tree.nodes.new('ShaderNodeMixShader')

            node_tree.links.new(principled_BSDF.outputs[0], mix_envmap.inputs[2])
            node_tree.links.new(glossy_BSDF.outputs[0], mix_envmap.inputs[1])
            mix_envmap_out = mix_envmap.outputs[0]
        else:
            mix_envmap_out = principled_BSDF.outputs[0]

        node_tree.links.new(mix_envmap_out, material_output.inputs[0])

        principled_BSDF.location = (3 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)

    elif material.bf2_shader == 'STATICMESH':

        def _link_uv_chan(uv_chan, tex_node):
            node_tree.links.new(uv_map_nodes[uv_chan].outputs[0], tex_node.inputs[0])

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
            # multiply detail and base color
            multiply_detail = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_detail.inputs[0].default_value = 1
            multiply_detail.blend_type = 'MULTIPLY'
            multiply_detail.location = (0 * NODE_WIDTH, 0 * NODE_HEIGHT)
            multiply_detail.hide = True

            node_tree.links.new(base.outputs[0], multiply_detail.inputs[1])
            node_tree.links.new(detail.outputs[0], multiply_detail.inputs[2])
            detail_out = multiply_detail.outputs[0]
        else:
            detail_out = base.outputs[0]

        if crack:
            # mix detail & crack color based on crack alpha
            mix_crack = node_tree.nodes.new('ShaderNodeMixRGB')
            mix_crack.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
            mix_crack.hide = True

            node_tree.links.new(crack.outputs[1], mix_crack.inputs[0])
            node_tree.links.new(detail_out, mix_crack.inputs[1])
            node_tree.links.new(crack.outputs[0], mix_crack.inputs[2])
            crack_out = mix_crack.outputs[0]
        else:
            crack_out =  detail_out

        if dirt:
            # multiply dirt and diffuse
            multiply_dirt = node_tree.nodes.new('ShaderNodeMixRGB')
            multiply_dirt.inputs[0].default_value = 1
            multiply_dirt.blend_type = 'MULTIPLY'
            multiply_dirt.location = (2 * NODE_WIDTH, 0 * NODE_HEIGHT)
            multiply_dirt.hide = True

            node_tree.links.new(crack_out, multiply_dirt.inputs[1])
            node_tree.links.new(dirt.outputs[0], multiply_dirt.inputs[2])
            dirt_out = multiply_dirt.outputs[0]
        else:
            dirt_out = crack_out

        # finally link to shader
        node_tree.links.new(dirt_out, shader_base_color)

        # ---- specular ----
        # TODO: this is wrong for vegitation
        if dirt and detail:
            # dirt.r * dirt.g * dirt.b
            dirt_rgb_mult = node_tree.nodes.new('ShaderNodeGroup')
            dirt_rgb_mult.node_tree = _create_multiply_rgb_shader_node()
            dirt_rgb_mult.location = (0 * NODE_WIDTH, -1 * NODE_HEIGHT)
            dirt_rgb_mult.hide = True

            node_tree.links.new(dirt.outputs[0], dirt_rgb_mult.inputs[0])

            # multiply that with detailmap alpha
            mult_detaila = node_tree.nodes.new('ShaderNodeMath')
            mult_detaila.operation = 'MULTIPLY'
            mult_detaila.location = (0 * NODE_WIDTH, -1 * NODE_HEIGHT)
            mult_detaila.hide = True

            node_tree.links.new(dirt_rgb_mult.outputs[0], mult_detaila.inputs[1])
            node_tree.links.new(detail.outputs[1], mult_detaila.inputs[0])
            dirt_spec_out = mult_detaila.outputs[0]
        elif detail:
            dirt_spec_out = detail.outputs[1]
        else:
            dirt_spec_out = None

        if has_alpha and ndetail:
            # mult with detaimap normal alpha
            mult_ndetaila = node_tree.nodes.new('ShaderNodeMath')
            mult_ndetaila.operation = 'MULTIPLY'
            mult_ndetaila.location = (1 * NODE_WIDTH, -1 * NODE_HEIGHT)
            mult_ndetaila.hide = True

            node_tree.links.new(dirt_spec_out, mult_ndetaila.inputs[1])
            node_tree.links.new(ndetail.outputs[1], mult_ndetaila.inputs[0])
            has_alpha_out = mult_ndetaila.outputs[0]
        elif detail:
            has_alpha_out = dirt_spec_out
        else:
            has_alpha_out = None

        if has_alpha_out:
            node_tree.links.new(has_alpha_out, shader_specular)

            reduce_roughness = node_tree.nodes.new('ShaderNodeMapRange')
            reduce_roughness.inputs[3].default_value = ROUGHNESS_BASE
            node_tree.links.new(has_alpha_out, reduce_roughness.inputs[0])
            node_tree.links.new(reduce_roughness.outputs[0], shader_roughness)

        # ---- normal  ----

        normal_out = None

        def _create_normal_map_node(nmap, uv_chan):
            # convert to normal
            normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
            normal_node.uv_map = uv_map_nodes[uv_chan].uv_map
            normal_node.location = (1 * NODE_WIDTH, -1 - uv_chan * NODE_HEIGHT)
            normal_node.hide = True
            node_tree.links.new(nmap.outputs[0], normal_node.inputs[1])
            return normal_node.outputs[0]

        ndetail_out = ndetail and _create_normal_map_node(ndetail, 1)
        ncrack_out = ncrack and _create_normal_map_node(ncrack, 3 if dirt else 2)

        if ndetail_out and ncrack_out:
            # mix ndetail & ncrack based on crack alpha
            mix_normal = node_tree.nodes.new('ShaderNodeMix')
            mix_normal.data_type = 'VECTOR'
            mix_normal.location = (3 * NODE_WIDTH, -3 * NODE_HEIGHT)
            mix_normal.hide = True

            node_tree.links.new(crack.outputs[1], mix_normal.inputs[0])
            node_tree.links.new(ndetail_out, mix_normal.inputs[4])
            node_tree.links.new(ncrack_out, mix_normal.inputs[5])
            normal_out = mix_normal.outputs[1]
        elif ndetail_out:
            normal_out = ndetail_out

        if normal_out:
            node_tree.links.new(normal_out, shader_normal)

        # ---- transparency ------
        if has_alpha:
            # TODO alpha blend for statics, is this even used ?
            if detail:
                alpha_output = detail.outputs[1]
            else:
                alpha_output = base.outputs[1]

            node_tree.links.new(alpha_output, shader_alpha)

        principled_BSDF.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (5 * NODE_WIDTH, 0 * NODE_HEIGHT)
