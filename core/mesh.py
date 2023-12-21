import bpy
import bmesh
import math
import struct
import os

from mathutils import Vector, Matrix
from .bf2.bf2_mesh import BF2Mesh
from .utils import to_matrix, convert_bf2_pos_rot, delete_object_if_exists
from .skeleton import find_active_skeleton, ske_get_bone_rot, ske_weapon_part_ids

NODE_WIDTH = 400
NODE_HEIGHT = 100

def import_mesh(context, mesh_file, geom=0, lod=0, texture_path='', reload=False):
    bf2_mesh = BF2Mesh(mesh_file)

    mesh_obj = _import_mesh_geometry(bf2_mesh.name, bf2_mesh, geom, lod, texture_path, reload)

    if bf2_mesh.isSkinnedMesh:
        _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, geom, lod)
    elif bf2_mesh.isBundledMesh:
        _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod)

    context.scene.collection.objects.link(mesh_obj)

def _roatate_uv(uv, angle):
    uv = Vector(uv)
    pivot = Vector((0.5, 0.5))
    angle = math.radians(angle)
    uv -= pivot
    uv_len = uv.length
    uv.normalize()
    uv = Vector((uv.x * math.cos(angle) - uv.y * math.sin(angle),
                    uv.x * math.sin(angle) + uv.y * math.cos(angle)))
    uv *= uv_len
    uv += pivot
    return uv

def _import_mesh_geometry(name, bf2_mesh, geom, lod, texture_path, reload):

    if reload:
        delete_object_if_exists(name)

    bf2_lod = bf2_mesh.geoms[geom].lods[lod]

    verts = list()
    faces = list()

    for mat in bf2_lod.materials:
        f_offset = len(verts)
        index_arr = bf2_mesh.index[mat.istart:mat.istart + mat.inum]
        _faces = list()
        for i in range(0, len(index_arr), 3):
            v1 = index_arr[i + 0] + f_offset
            v2 = index_arr[i + 1] + f_offset
            v3 = index_arr[i + 2] + f_offset
            _faces.append((v3, v2, v1))
        faces.append(_faces)

        for i in range(mat.vstart, mat.vstart + mat.vnum):
            vi = i * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            x = bf2_mesh.vertices[vi + 0]
            y = bf2_mesh.vertices[vi + 1]
            z = bf2_mesh.vertices[vi + 2]
            verts.append((x, z, y))

    bm = bmesh.new()
    for vert in verts:
        bm.verts.new(vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    for material_index, _faces in enumerate(faces):
        for face  in _faces:
            face_verts = [bm.verts[i] for i in face]
            try:
                bm_face = bm.faces.new(face_verts)
                bm_face.material_index = material_index
            except ValueError:
                pass
                # XXX: some meshes (e.g. vBF2 usrif_remington11-87)
                # produce "face already exists" error
                # even though vert indexes are unique
                # I don't know wtf is going on, so lets just ignore it

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    # load vertex normals
    normal_off = bf2_mesh.get_normal_offset()
    vertex_normals = list()

    for i, mat in enumerate(bf2_lod.materials):
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            x = bf2_mesh.vertices[vi + normal_off + 0]
            y = bf2_mesh.vertices[vi + normal_off + 1]
            z = bf2_mesh.vertices[vi + normal_off + 2]
            vertex_normals.append((x, z, y))

    # apply normals
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.normals_split_custom_set_from_vertices(vertex_normals)
    mesh.use_auto_smooth = True

    bm.normal_update()
    bm.free()

    # load UVs
    uvs = dict()
    for uv_chan in range(5):
        uv_off = bf2_mesh.get_uv_offset(uv_chan)
        if uv_off is None:
            continue
        uvs[uv_chan] = list()
        for i, mat in enumerate(bf2_lod.materials):
            for j in range(mat.vstart, mat.vstart + mat.vnum):
                vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
                u = bf2_mesh.vertices[vi + uv_off + 0]
                v = bf2_mesh.vertices[vi + uv_off + 1]
                uvs[uv_chan].append((v, u)) # this is no mistake

    # apply UVs
    for uv_chan, vert_uv in uvs.items():
        uvlayer = mesh.uv_layers.new(name=f'UV{uv_chan}')
        for l in mesh.loops:
            uv = _roatate_uv(vert_uv[l.vertex_index], -90.0) # the only way it can display properly
            uvlayer.data[l.index].uv = uv

        mesh.calc_tangents()

    # create materials
    for i, bf2_mat in enumerate(bf2_lod.materials):
        mat_name = f'{bf2_mesh.name}_material_{i}'
        try:
            material = bpy.data.materials[mat_name]
            bpy.data.materials.remove(material, do_unlink=True)
        except:
            pass
        material = bpy.data.materials.new(mat_name)
        mesh.materials.append(material)

        material.use_nodes = True
        node_tree = material.node_tree

        # create UV nodes
        uv_map_nodes = dict()
        for uv_chan in uvs.keys():
            uv = node_tree.nodes.new('ShaderNodeUVMap')
            uv.uv_map = f'UV{uv_chan}'
            uv.location = (-2 * NODE_WIDTH, -uv_chan * NODE_HEIGHT)
            uv.hide = True
            uv_map_nodes[uv_chan] = uv

        # load textures
        textute_map_nodes = list()
        for map_index, texture_map in enumerate(bf2_mat.maps):
            tex_node = node_tree.nodes.new('ShaderNodeTexImage')
            textute_map_nodes.append(tex_node)
            texture_file = texture_map.decode('ascii')
            if texture_path:
                # t = os.path.basename(texture_file)
                # if t in bpy.data.images:
                #     bpy.data.images.remove(bpy.data.images[t])
                try:
                    tex_node.image = bpy.data.images.load(os.path.join(texture_path, texture_file), check_existing=True)
                    tex_node.image.alpha_mode = 'NONE'
                except OSError:
                    pass

            tex_node.location = (-1 * NODE_WIDTH, -map_index * NODE_HEIGHT)
            tex_node.hide = True

        # TODO check technique name
        if bf2_mesh.isStaticMesh:
            _setup_static_mesh_shader(node_tree, textute_map_nodes, uv_map_nodes)
        elif bf2_mesh.isBundledMesh:
            _setup_mesh_shader(node_tree, textute_map_nodes, uv_map_nodes, has_specular=True)
        elif bf2_mesh.isSkinnedMesh:
            _setup_mesh_shader(node_tree, textute_map_nodes, uv_map_nodes, has_specular=False)

    obj = bpy.data.objects.new(name, mesh)
    return obj

def _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod):
    
    if not find_active_skeleton(context):
        return # ignore if skeleton not loaded
        
    rig, skeleton = find_active_skeleton(context)

    bf2_lod = bf2_mesh.geoms[geom].lods[lod]
    
    off = bf2_mesh.get_wight_offset()
    
    # find which part vertex bbelongs to
    vert_part_id = list()
    for mat in bf2_lod.materials:
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            _data_float = bf2_mesh.vertices[vi + off]
            _data = tuple([b for b in struct.pack('f', _data_float)])
            part_id = _data[0]
            vert_part_id.append(part_id)
    
    # create vertex groups and assing verticies to them
    for vertex in mesh_obj.data.vertices:
        part_id = vert_part_id[vertex.index]
        group_name = f'mesh{part_id + 1}'
        if group_name not in mesh_obj.vertex_groups.keys():
            mesh_obj.vertex_groups.new(name=group_name)
        mesh_obj.vertex_groups[group_name].add([vertex.index], 1.0, "REPLACE")

    # parent mesh oject to armature
    mesh_obj.parent = rig
    
    # add armature modifier to the object
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = rig

def _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, geom, lod):
    
    if not find_active_skeleton(context):
        return # ignore if skeleton not loaded
        
    rig, skeleton = find_active_skeleton(context)
    armature = rig.data
    
    context.view_layer.objects.active = rig
    
    # we're gona change the 'rest' transforms of the bones
    bpy.ops.object.mode_set(mode='EDIT')
    
    bf2_lod = bf2_mesh.geoms[geom].lods[lod]
    
    id_to_bone = dict()
    for i, node in enumerate(skeleton.node_list()):
        id_to_bone[i] = armature.edit_bones[node.name]
    
    rigs_bones = list()
    for bf2_rig in bf2_lod.rigs:
        rig_bones = list()
        for bf2_bone in bf2_rig.bones:    
            m = Matrix(bf2_bone.matrix)
            m.transpose()
            m.invert()
            pos, rot, _ = m.decompose()
            convert_bf2_pos_rot(pos, rot)
            bone_obj = id_to_bone[bf2_bone.id]
            bone_obj.matrix = to_matrix(pos, rot) @ ske_get_bone_rot(bone_obj)
            rig_bones.append(bone_obj.name)
        rigs_bones.append(rig_bones)
    
    # get weigths from bf2 mesh
    vert_weigths = list()
    for i, mat in enumerate(bf2_lod.materials):
        rig_bones = rigs_bones[i]
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            WIEGHTS_OFFSET = 6
            w = bf2_mesh.vertices[vi + WIEGHTS_OFFSET + 0]
            _bones_float = bf2_mesh.vertices[vi + WIEGHTS_OFFSET + 1]
            _bone_ids = tuple([b for b in struct.pack('f', _bones_float)])
            weights = [] # max two bones per vert
            
            _bone = rig_bones[_bone_ids[0]]
            weights.append((_bone, w))
            if w < 1.0:
                _bone = rig_bones[_bone_ids[1]]
                weights.append((_bone, 1.0 - w))
            vert_weigths.append(weights)

    # create vertex group for each bone
    mesh_bones = ske_weapon_part_ids(skeleton)
    for i, bone_obj in id_to_bone.items():
        if i in mesh_bones:
            continue
        mesh_obj.vertex_groups.new(name=bone_obj.name)
    
    # assign verticies to vertex groups and apply weights
    for vertex in mesh_obj.data.vertices:
        v_weights = vert_weigths[vertex.index]
        for v_bone, v_bone_weight in v_weights: 
            mesh_obj.vertex_groups[v_bone].add([vertex.index], v_bone_weight, "REPLACE")
    
    bpy.ops.object.mode_set(mode='OBJECT')

    # parent mesh oject to armature
    mesh_obj.parent = rig
    
    # add armature modifier to the object
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = rig


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

    multi_rgb.links.new(group_inputs.outputs['color'], node_separate_color.inputs[0])

    multi_rgb.links.new(node_separate_color.outputs[0], node_multiply_rg.inputs[0])
    multi_rgb.links.new(node_separate_color.outputs[1], node_multiply_rg.inputs[1])
    multi_rgb.links.new(node_separate_color.outputs[2], node_multiply_rgb.inputs[0])
    multi_rgb.links.new(node_multiply_rg.outputs[0], node_multiply_rgb.inputs[1])

    multi_rgb.links.new(node_multiply_rgb.outputs[0], group_outputs.inputs['value'])

    return multi_rgb

def _setup_static_mesh_shader(node_tree, texture_nodes, uv_map_nodes):
    principled_BSDF = node_tree.nodes.get('Principled BSDF')
    shader_base_color = principled_BSDF.inputs[0]
    shader_specular = principled_BSDF.inputs[7]
    shader_roughness = principled_BSDF.inputs[9]
    shader_normal = principled_BSDF.inputs[22]

    shader_roughness.default_value = 1
    shader_specular.default_value = 0

    # link UVs
    for map_index, tex_node in enumerate(texture_nodes):
        uv_chan = None
        if map_index == 0: # color
            uv_chan = 0
        elif map_index == 1: # detail
            uv_chan = 1
        elif map_index == 2: # dirt
            uv_chan = 2
        elif map_index == 3: # crack
            uv_chan = 3
        elif map_index == 4: # ndetail
            uv_chan = 1
        elif map_index == 5: # ncrack
            uv_chan = 3

        if uv_chan is not None and uv_chan in uv_map_nodes:
            node_tree.links.new(uv_map_nodes[uv_chan].outputs[0], tex_node.inputs[0])

    base = texture_nodes[0]
    detail = texture_nodes[1]
    dirt = texture_nodes[2]
    crack = texture_nodes[3]
    ndetail = texture_nodes[4]
    ncrack = texture_nodes[5]

    # ---- diffuse ----
    multiply_detail = node_tree.nodes.new('ShaderNodeMixRGB')
    multiply_detail.inputs[0].default_value = 1
    multiply_detail.blend_type = 'MULTIPLY'
    multiply_detail.location = (0 * NODE_WIDTH, 0 * NODE_HEIGHT)
    multiply_detail.hide = True

    mix_crack = node_tree.nodes.new('ShaderNodeMixRGB')
    mix_crack.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
    mix_crack.hide = True

    multiply_dirt = node_tree.nodes.new('ShaderNodeMixRGB')
    multiply_dirt.inputs[0].default_value = 1
    multiply_dirt.blend_type = 'MULTIPLY'
    multiply_dirt.location = (2 * NODE_WIDTH, 0 * NODE_HEIGHT)
    multiply_dirt.hide = True

    # multiply detail and base color
    node_tree.links.new(base.outputs[0], multiply_detail.inputs[1])
    node_tree.links.new(detail.outputs[0], multiply_detail.inputs[2])

    # mix detail & crack color based on crack alpha
    node_tree.links.new(crack.outputs[1], mix_crack.inputs[0])
    node_tree.links.new(multiply_detail.outputs[0], mix_crack.inputs[1])
    node_tree.links.new(crack.outputs[0], mix_crack.inputs[2])

    # multiply above with dirt
    node_tree.links.new(mix_crack.outputs[0], multiply_dirt.inputs[1])
    node_tree.links.new(dirt.outputs[0], multiply_dirt.inputs[2])

    node_tree.links.new(multiply_dirt.outputs[0], shader_base_color)

    # ---- specular ----

    dirt_rgb_mult = node_tree.nodes.new('ShaderNodeGroup')
    dirt_rgb_mult.node_tree = _create_multiply_rgb_shader_node()
    dirt_rgb_mult.location = (0 * NODE_WIDTH, 1 * NODE_HEIGHT)
    dirt_rgb_mult.hide = True

    specular = node_tree.nodes.new('ShaderNodeMath')
    specular.operation = 'MULTIPLY'
    specular.location = (0 * NODE_WIDTH, 1 * NODE_HEIGHT)
    specular.hide = True

    node_tree.links.new(dirt.outputs[0], dirt_rgb_mult.inputs[0])

    node_tree.links.new(dirt_rgb_mult.outputs[0], specular.inputs[1])
    node_tree.links.new(detail.outputs[0], specular.inputs[0])

    node_tree.links.new(specular.outputs[0], shader_specular)

    # ---- normal  ----

    map_range_ndetail = node_tree.nodes.new('ShaderNodeMapRange')
    map_range_ndetail.data_type = 'FLOAT_VECTOR'
    map_range_ndetail.inputs[9].default_value = (-1, -1, -1)
    map_range_ndetail.location = (0 * NODE_WIDTH, 3 * NODE_HEIGHT)
    map_range_ndetail.hide = True

    map_range_ncrack = node_tree.nodes.new('ShaderNodeMapRange')
    map_range_ncrack.data_type = 'FLOAT_VECTOR'
    map_range_ncrack.inputs[9].default_value = (-1, -1, -1)
    map_range_ncrack.location = (0 * NODE_WIDTH, 4 * NODE_HEIGHT)
    map_range_ncrack.hide = True

    mix_normal = node_tree.nodes.new('ShaderNodeMix')
    mix_normal.data_type = 'VECTOR'
    mix_normal.location = (1 * NODE_WIDTH, 3 * NODE_HEIGHT)
    mix_normal.hide = True

    normalize = node_tree.nodes.new('ShaderNodeVectorMath')
    normalize.operation = 'NORMALIZE'
    normalize.location = (2 * NODE_WIDTH, 3 * NODE_HEIGHT)
    normalize.hide = True

    node_tree.links.new(ndetail.outputs[0], map_range_ndetail.inputs[6])
    node_tree.links.new(ncrack.outputs[0], map_range_ncrack.inputs[6])

    node_tree.links.new(crack.outputs[1], mix_normal.inputs[0])
    node_tree.links.new(map_range_ndetail.outputs[1], mix_normal.inputs[4])
    node_tree.links.new(map_range_ncrack.outputs[1], mix_normal.inputs[5])

    node_tree.links.new(mix_normal.outputs[1], normalize.inputs[0])

    node_tree.links.new(normalize.outputs[0], shader_normal)

    principled_BSDF.location = (3 * NODE_WIDTH, 0 * NODE_HEIGHT)


def _setup_mesh_shader(node_tree, texture_nodes, uv_map_nodes, has_specular=True):
    principled_BSDF = node_tree.nodes.get('Principled BSDF')
    shader_base_color = principled_BSDF.inputs[0]
    shader_specular = principled_BSDF.inputs[7]
    shader_roughness = principled_BSDF.inputs[9]
    shader_normal = principled_BSDF.inputs[22]

    shader_roughness.default_value = 1
    shader_specular.default_value = 0

    # link UVs
    for map_index, tex_node in enumerate(texture_nodes):
        uv_chan = None
        if map_index == 0: # diffuse
            uv_chan = 0
        elif map_index == 1: # normal
            uv_chan = 0

        if uv_chan is not None and uv_chan in uv_map_nodes:
            node_tree.links.new(uv_map_nodes[uv_chan].outputs[0], tex_node.inputs[0])
    
    diffuse = texture_nodes[0]
    normal = texture_nodes[1]

    node_tree.links.new(diffuse.outputs[0], shader_base_color)
    if has_specular:
        node_tree.links.new(diffuse.outputs[1], shader_specular)
    node_tree.links.new(normal.outputs[0], shader_normal)
