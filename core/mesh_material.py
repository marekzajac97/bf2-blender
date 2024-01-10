import bpy
import os

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
    bf2_axes_swap.inputs.new('NodeSocketVector', 'in')
    group_outputs = bf2_axes_swap.nodes.new('NodeGroupOutput')
    bf2_axes_swap.outputs.new('NodeSocketVector', 'out')

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
    multi_rgb.inputs.new('NodeSocketColor', 'color')
    group_outputs = multi_rgb.nodes.new('NodeGroupOutput')
    multi_rgb.outputs.new('NodeSocketFloat', 'value')

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

def _setup_transparency(node_tree, src_alpha_out, one_minus_src_alpha=False):
    principled_BSDF = node_tree.nodes.get('Principled BSDF')

    transparent_BSDF = node_tree.nodes.new('ShaderNodeBsdfTransparent')
    mix_shader = node_tree.nodes.new('ShaderNodeMixShader')

    if one_minus_src_alpha:
        one_minus = node_tree.nodes.new('ShaderNodeMath')
        one_minus.operation = 'SUBTRACT'
        one_minus.inputs[0].default_value = 1
        node_tree.links.new(src_alpha_out, one_minus.inputs[1])
        alpha_output = one_minus.outputs[0]
    else:
        alpha_output = src_alpha_out

    node_tree.links.new(principled_BSDF.outputs[0], mix_shader.inputs[2])
    node_tree.links.new(transparent_BSDF.outputs[0], mix_shader.inputs[1])

    node_tree.links.new(alpha_output, mix_shader.inputs[0])
    return mix_shader.outputs[0]

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

def get_staticmesh_uv_channels(technique):
    maps = _split_str_from_word_set(technique, STATICMESH_TEXUTRE_MAP_TYPES)
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

DEFAULT_TECHNIQUE = {
    'STATICMESH': 'BaseDetailDirtCrackNDetailNCrack',
    'BUNDLEDMESH': 'ColormapGloss',
    'SKINNEDMESH': '' # TODO
}

def _default_uvs(shader, technique):
    if shader == 'STATICMESH':
        return get_staticmesh_uv_channels(technique)
    elif shader in ('BUNDLEDMESH', 'SKINNEDMESH'):
        return {0} # TODO: BundledMesh can have 2 UVs (animated UV for the tracks I think)
    else:
        raise ValueError()

# empty texture sets
def _default_texture_maps(shader, technique):
    if shader == 'STATICMESH':
        maps = _split_str_from_word_set(technique, STATICMESH_TEXUTRE_MAP_TYPES)
        return [''] * len(maps)
    elif shader == 'BUNDLEDMESH':
        return [''] * len(BUNDLEDMESH_TEXTURE_MAP_TYPES)
    elif  shader == 'SKINNEDMESH':
        return [''] * len(SKINNEDMESH_TEXTURE_MAP_TYPES)
    else:
        raise ValueError()

def setup_material(material, texture_maps=None, uvs=None, texture_path=''):
    material.use_nodes = True
    node_tree = material.node_tree
    node_tree.nodes.clear()
    material_output = node_tree.nodes.new('ShaderNodeOutputMaterial')
    material_output.name = material_output.label = 'Material Output'
    principled_BSDF = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled_BSDF.name = principled_BSDF.label = 'Principled BSDF'
    node_tree.links.new(principled_BSDF.outputs[0], material_output.inputs[0])

    if material.bf2_technique == '':
        material.bf2_technique = DEFAULT_TECHNIQUE[material.bf2_shader]

    if texture_maps is None:
        texture_maps = _default_texture_maps(material.bf2_shader, material.bf2_technique)

    if uvs is None:
        uvs = _default_uvs(material.bf2_shader, material.bf2_technique)

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
    texture_nodes = list()
    for map_index, texture_map in enumerate(texture_maps):

        if texture_map and 'SpecularLUT_pow36' in texture_map:
            continue

        tex_node = node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.location = (-1 * NODE_WIDTH, -map_index * NODE_HEIGHT)
        tex_node.hide = True
        texture_nodes.append(tex_node)

        if not texture_map or not texture_path:
            continue

        # t = os.path.basename(texture_file)
        # if t in bpy.data.images:
        #     bpy.data.images.remove(bpy.data.images[t])
        try:
            tex_node.image = bpy.data.images.load(os.path.join(texture_path, texture_map), check_existing=True)
            tex_node.image.alpha_mode = 'NONE'
        except RuntimeError:
            pass

    shader_base_color = principled_BSDF.inputs[0]
    shader_specular = principled_BSDF.inputs[7]
    shader_roughness = principled_BSDF.inputs[9]
    shader_normal = principled_BSDF.inputs[22]

    shader_roughness.default_value = 1
    shader_specular.default_value = 0

    if material.bf2_shader in ('SKINNEDMESH', 'BUNDLEDMESH') :
        UV_CHANNEL = 0

        # TODO SETUP it properly based on techinique ('ColormapGloss', 'EnvColormapGloss', 'Alpha_TestColormapGloss', 'Alpha', 'Alpha_Test')

        diffuse = texture_nodes[0]
        normal = texture_nodes[1]
        shadow = None
        if len(texture_nodes) > 2:
            shadow = texture_nodes[2]

        diffuse.label = diffuse.name = 'Diffuse'
        normal.label = normal.name = 'Normal'
        if shadow: shadow.label = shadow.name = 'Shadow'

        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], diffuse.inputs[0])
        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], normal.inputs[0])
        if shadow:
            node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], shadow.inputs[0])

        if normal.image:
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

        # specular
        has_specular = material.bf2_shader != 'SKINNEDMESH' and not has_alpha
        if has_specular:

            if shadow:
                # multiply diffuse and shadow
                multiply_diffuse = node_tree.nodes.new('ShaderNodeMixRGB')
                multiply_diffuse.inputs[0].default_value = 1
                multiply_diffuse.blend_type = 'MULTIPLY'
                multiply_diffuse.location = (1 * NODE_WIDTH, -2 * NODE_HEIGHT)
                multiply_diffuse.hide = True

                node_tree.links.new(shadow.outputs[0], multiply_diffuse.inputs[1])
                node_tree.links.new(diffuse.outputs[1], multiply_diffuse.inputs[2])
                shadow_spec_out = multiply_diffuse.outputs[0]
            else:
                shadow_spec_out = diffuse.outputs[1]

            node_tree.links.new(shadow_spec_out, shader_specular)

        # normal
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
            mix_shader_out = _setup_transparency(node_tree, diffuse.outputs[1])
            node_tree.links.new(mix_shader_out, material_output.inputs[0])

        principled_BSDF.location = (3 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)

    elif material.bf2_shader == 'STATICMESH':

        if material.bf2_technique not in STATICMESH_TECHNIQUES:
            raise RuntimeError(f'Unsupported staticmesh technique "{material.bf2_technique}"')

        maps = _split_str_from_word_set(material.bf2_technique, set(STATICMESH_TEXUTRE_MAP_TYPES))

        if len(texture_nodes) != len(maps):
            raise RuntimeError(f'Material technique ({material.bf2_technique}) doesn\'t match number of texture maps ({len(texture_nodes)})')

        base = None
        detail = None
        dirt = None
        crack = None
        ndetail = None
        ncrack = None

        for map_name, tex_node in zip(maps, texture_nodes):
            if map_name == 'Base':
                base = tex_node
                uv_chan = 0
            elif map_name == 'Detail':
                detail = tex_node
                uv_chan = 1
            elif map_name == 'Dirt':
                dirt = tex_node
                uv_chan = 2
            elif map_name == 'Crack':
                crack = tex_node
                uv_chan = 3 if dirt else 2
            elif map_name == 'NDetail':
                ndetail = tex_node
                uv_chan = 1
            elif map_name == 'NCrack':
                ncrack = tex_node
                uv_chan = 3 if dirt else 2

            # link UVs with texture nodes
            if uv_chan in uv_map_nodes:
                node_tree.links.new(uv_map_nodes[uv_chan].outputs[0], tex_node.inputs[0])
        
        # change normal maps color space
        if ndetail and ndetail.image:
            ndetail.image.colorspace_settings.name = 'Non-Color'
        if ncrack and ncrack.image:
            ncrack.image.colorspace_settings.name = 'Non-Color'

        if base: base.label = base.name = 'Base'
        if detail: detail.label = detail.name = 'Detail'
        if dirt: dirt.label = dirt.name = 'Dirt'
        if crack: crack.label = crack.name = 'Crack'
        if ndetail: ndetail.label = ndetail.name = 'NDetail'
        if ncrack: ncrack.label = ncrack.name = 'NCrack'

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
                src_alpha_out = detail.outputs[1]
                one_minus_src_alpha = True
            else:
                src_alpha_out = base.outputs[1]
                one_minus_src_alpha = False

            mix_shader_out = _setup_transparency(node_tree, src_alpha_out, one_minus_src_alpha=one_minus_src_alpha)
            node_tree.links.new(mix_shader_out, material_output.inputs[0])

        principled_BSDF.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (5 * NODE_WIDTH, 0 * NODE_HEIGHT)

def get_ordered_staticmesh_maps(texture_maps):
    # find matching technique, which only conatins maps from collected set
    for technique in STATICMESH_TECHNIQUES:
        maps = _split_str_from_word_set(technique, texture_maps.keys())
        if maps is not None and len(maps) == len(texture_maps.keys()):
            return maps
    return None
