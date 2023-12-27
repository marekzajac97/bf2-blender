import bpy
import bmesh
import math
import struct
import os

from mathutils import Vector, Matrix

from .bf2.bf2_mesh import BF2Mesh, BF2BundledMesh, BF2SkinnedMesh, BF2StaticMesh
from .bf2.bf2_common import Vec3, Mat4
from .bf2.bf2_mesh.bf2_staticmesh import StaticMeshGeom, StaticMeshLod, StaticMeshMaterial
from .bf2.bf2_mesh.bf2_visiblemesh import Vertex, VertexAttribute
from .bf2.bf2_mesh.bf2_types import D3DDECLTYPE, D3DDECLUSAGE

from .exceptions import ImportException, ExportException
from .utils import to_matrix, convert_bf2_pos_rot, delete_object_if_exists, check_suffix
from .skeleton import find_active_skeleton, ske_get_bone_rot, ske_weapon_part_ids

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
    'BaseDetailDirtCrack',
    'BaseDetailDirtCrackNCrack',
    'BaseDetailDirtCrackNDetail',
    'BaseDetailDirtCrackNDetailNCrack'
]

STATICMESH_TEXUTRE_MAP_TYPES = {'Base', 'Detail', 'Dirt', 'Crack', 'NDetail', 'NCrack'}

def import_mesh(context, mesh_file, geom=None, lod=None, texture_path='', reload=False):
    bf2_mesh = BF2Mesh.load(mesh_file)
    if geom is None and lod is None:
        if reload: delete_object_if_exists(bf2_mesh.name)
        root_obj = bpy.data.objects.new(bf2_mesh.name, None)
        context.scene.collection.objects.link(root_obj)
        for geom_idx, _ in enumerate(bf2_mesh.geoms):
            geom_name = f'{bf2_mesh.name}_geom{geom_idx}'
            if reload: delete_object_if_exists(geom_name)
            geom_obj = bpy.data.objects.new(geom_name, None)
            geom_obj.parent = root_obj
            context.scene.collection.objects.link(geom_obj)
            for lod_idx, _ in enumerate(bf2_mesh.geoms[geom_idx].lods):
                lod_name = f'{geom_name}_lod{lod_idx}'
                if reload: delete_object_if_exists(lod_name)
                lod_obj = _import_mesh(context, lod_name, bf2_mesh, geom_idx, lod_idx, texture_path, reload=reload)
                lod_obj.parent = geom_obj
                context.scene.collection.objects.link(lod_obj)
    else:
        obj = _import_mesh(context, bf2_mesh.name, bf2_mesh, geom, lod, texture_path, reload=reload)
        context.scene.collection.objects.link(obj)

def _import_mesh(context, name, bf2_mesh, geom, lod, texture_path='', reload=False):
    mesh_obj = _import_mesh_geometry(name, bf2_mesh, geom, lod, texture_path, reload)

    if isinstance(bf2_mesh, BF2SkinnedMesh):
        _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, geom, lod)
    elif isinstance(bf2_mesh, BF2BundledMesh):
        _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod)

    return mesh_obj

def export_staticmesh(context, mesh_file, texture_path=''):
    mesh_obj = context.view_layer.objects.active
    if mesh_obj is None:
        raise ExportException("No object selected!")
    
    bf2_mesh = BF2StaticMesh(name=mesh_obj.name)

    class _VertexData:
        def __init__(self):
            self.position = (0, 0, 0)
            self.normal = (0, 0, 0)
            self.tangent = (0, 0, 0)
            self.texcoords = [(0, 0) for _ in range(5)]

    vert_attrs = bf2_mesh.vertex_attributes
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.POSITION))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.NORMAL))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.D3DCOLOR, D3DDECLUSAGE.BLENDINDICES))

    # TODO do we need all those texcoords for vertex if none of the materials use dirt, crack etc??
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD0))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD1))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD2))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD3))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD4))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.TANGENT))

    if not mesh_obj.children:
        raise ExportException(f"mesh object '{mesh_obj.name}' has no children (geoms)!")

    geoms = dict()
    for geom_obj in mesh_obj.children:
        geom_idx = check_suffix(geom_obj.name, 'geom')
        if geom_idx in geoms:
            raise ExportException(f"mesh object '{mesh_obj.name}' has duplicated geom{geom_idx}")
        geoms[geom_idx] = geom_obj
    for _, geom_obj in sorted(geoms.items()):
        geom = StaticMeshGeom()
        bf2_mesh.geoms.append(geom)

        if not geom_obj.children:
            raise ExportException(f"geom '{geom_obj.name}' has no children (lods)!")

        lods = dict()
        for lod_obj in geom_obj.children:
            lod_idx = check_suffix(lod_obj.name, 'lod')
            if lod_idx in lods:
                raise ExportException(f"geom '{geom_obj.name}' has duplicated lod{lod_idx}")
            lods[lod_idx] = lod_obj
        for lod_idx, lod_obj in sorted(lods.items()):
            lod = StaticMeshLod()
            geom.lods.append(lod)
            mesh = lod_obj.data
            if mesh is None:
                raise ExportException(f"lod '{lod_obj.name}' has no mesh data!")

            mesh.calc_tangents()

            # map uv channel to uv layer object
            uv_layers = dict()
            for uv_chan in range(5):
                if f'UV{uv_chan}' in mesh.uv_layers:
                    uv_layers[uv_chan] = mesh.uv_layers[f'UV{uv_chan}']

            # map materials to verts and faces
            mat_idx_to_verts_faces = dict()
            for poly in mesh.polygons:
                # XXX: make sure is it always a triangle??
                v1, v2, v3 = poly.vertices
                if poly.material_index not in mat_idx_to_verts_faces:
                    mat_idx_to_verts_faces[poly.material_index] = (set(), list())

                vert_set = mat_idx_to_verts_faces[poly.material_index][0]
                face_list = mat_idx_to_verts_faces[poly.material_index][1]
    
                vert_set.add(v1)
                vert_set.add(v2)
                vert_set.add(v3)
                face_list.append(tuple(poly.vertices))

            # create bf2 materials
            for blend_mat_idx, (blend_vert_set, blend_faces) in sorted(mat_idx_to_verts_faces.items()):
                blend_material = mesh.materials[blend_mat_idx]
                blend_verts = [mesh.vertices[v] for v in blend_vert_set]

                bf2_mat = StaticMeshMaterial()
                lod.materials.append(bf2_mat)

                # create vertex data for each vertex
                blend_vert_idx_to_vert_data = dict()
                for loop in mesh.loops:
                    blend_vert = mesh.vertices[loop.vertex_index]
                    if loop.vertex_index not in blend_vert_idx_to_vert_data:
                        vert_data = _VertexData()
                        blend_vert_idx_to_vert_data[loop.vertex_index] = vert_data
                        vert_data.position = tuple(blend_vert.co)
                        # TODO: will this break if mesh has no split normals?
                        # idea for future me, if mesh has no custom split normals temporarly create them from vertex normals
                        # to calculate tangents
                        vert_data.normal = tuple(loop.normal)
                        vert_data.tangent = tuple(loop.tangent)
                        for uv_chan, uvlayer in uv_layers.items():
                            vert_data.texcoords[uv_chan] = tuple(uvlayer.data[loop.index].uv)
                    else:
                        # XXX: probably it will be needed to duplicate the vertex if it is present in more than one loop
                        # for now lets just make sure loop data it is the same
                        vert_data = blend_vert_idx_to_vert_data[loop.vertex_index]
                        if not _is_same(vert_data.normal, tuple(loop.normal)):
                            raise ExportException(f"Only one normal per vertex is supported, merge split normals before exporting!")
                        # TODO: why the fuck tangents are different when normals and uvs are?
                        # if not _is_same(vert_data.tangent, tuple(loop.tangent)):
                        #     raise ExportException(f"tangent missmatch {vert_data.tangent} != {tuple(loop.tangent)}")
                        for uv_chan, uvlayer in uv_layers.items():
                            loop_uv = tuple(uvlayer.data[loop.index].uv)
                            if vert_data.texcoords[uv_chan] != loop_uv:
                                raise ExportException(f"Multiple different UV{uv_chan} coords for single vertex in different mesh loops")

                # create vertices
                for blend_vert in blend_verts:
                    vert_data = blend_vert_idx_to_vert_data[blend_vert.index]
                    vert = Vertex()
                    vert.position = _swap_zy(vert_data.position)
                    vert.normal = _swap_zy(vert_data.normal)
                    vert.blendindices = (0, 0, 0, 0) # TODO blendindices! THE FUCK IS THIS USED FOR
                    vert.tangent = _swap_zy(vert_data.tangent)
                    for uv_chan, uv in enumerate(vert_data.texcoords):
                        _uv = _roatate_uv(uv, 90.0)
                        setattr(vert, f'texcoord{uv_chan}', (_uv[1], _uv[0]))

                    bf2_mat.vertices.append(vert)

                # create faces
                for f in blend_faces:
                    v1 ,v2, v3 = [blend_verts.index(mesh.vertices[v_idx]) for v_idx in f]
                    vert_indexes = (v3, v2, v1)
                    bf2_mat.faces.append(vert_indexes)

                bf2_mat.alpha_mode = StaticMeshMaterial.AlphaMode.NONE # TODO alpha mode
                bf2_mat.fxfile = 'StaticMesh.fx'

                # collect texture maps from nodes
                texture_maps = dict()
                for node in blend_material.node_tree.nodes:
                    if node.bl_idname != 'ShaderNodeTexImage':
                        continue
                    if node.image is None:
                        continue
                    if node.name not in STATICMESH_TEXUTRE_MAP_TYPES:
                        continue
                    texture_maps[node.name] = node.image.filepath

                # find matching technique, which only conatins maps from collected set
                for technique in STATICMESH_TECHNIQUES:
                    maps = _split_str_from_word_set(technique, texture_maps.keys())
                    if maps is not None and len(maps) == len(texture_maps.keys()):
                        bf2_mat.technique = technique
                        break
                else:
                    raise ExportException(f"Could not find a matching shader technique for the detected texture map set: {texture_maps.keys()},"
                                          "make sure that all of your Image Texture nodes are named correctly and have texture files loaded")

                # add maps in proper order, based on technique
                ordered_maps = _split_str_from_word_set(technique, texture_maps.keys())
                for texture_map in ordered_maps:
                    txt_map_file = texture_maps[texture_map]
                    if texture_path: # make relative
                        txt_map_file = os.path.relpath(txt_map_file, start=texture_path)     
                    bf2_mat.maps.append(txt_map_file.replace('\\', '/').lower())

                # TODO
                bf2_mat.maps.append('Common\Textures\SpecularLUT_pow36.dds')

                # collect required UV channel indexes
                uv_channels = set()
                has_dirt = 'Dirt' in texture_maps.keys()
                for texture_map in texture_maps.keys():
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

                # TODO lightmap UV, needs to be generated??
                uv_channels.add(4)

                # check UVs are present
                for uv_chan in uv_channels:
                    if uv_chan not in uv_layers.keys():
                        raise ExportException(f"Missing required UV layer 'UV{uv_chan}', make sure it exists and the name is correct")

            lod.parts = [Mat4()] # TODO parts

    bf2_mesh.export(mesh_file)

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
        mat_faces = list()
        for face in mat.faces:
            v1, v2, v3 = face
            # shift indexes
            v1 += f_offset
            v2 += f_offset
            v3 += f_offset
            mat_faces.append((v3, v2, v1))
        faces.append(mat_faces)

        for vert in mat.vertices:
            x, y, z = tuple(vert.position)
            verts.append((x, z, y))

    bm = bmesh.new()
    for vert in verts:
        bm.verts.new(vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    for material_index, mat_faces in enumerate(faces):
        for face in mat_faces:
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
    if bf2_mesh.has_normal():
        vertex_normals = list()

        for mat in bf2_lod.materials:
            for vert in mat.vertices:
                x = vert.normal[0]
                y = vert.normal[1]
                z = vert.normal[2]
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
        if not bf2_mesh.has_uv(uv_chan):
            continue
        vert_uv = list()
        uvs[uv_chan] = vert_uv
        for mat in bf2_lod.materials:
            for vert in mat.vertices:
                uv_attr = getattr(vert, f'texcoord{uv_chan}')
                u = uv_attr[0]
                v = uv_attr[1]
                uv = _roatate_uv((v, u), -90.0) # the only way it can display properly
                vert_uv.append(uv)

    # apply UVs
    for uv_chan, vert_uv in uvs.items():
        uvlayer = mesh.uv_layers.new(name=f'UV{uv_chan}')
        for l in mesh.loops:
            uvlayer.data[l.index].uv = vert_uv[l.vertex_index]

        mesh.calc_tangents()

    # create materials
    for i, bf2_mat in enumerate(bf2_lod.materials):
        mat_name = f'{name}_material_{i}'
        try:
            material = bpy.data.materials[mat_name]
            bpy.data.materials.remove(material, do_unlink=True)
        except:
            pass
        material = bpy.data.materials.new(mat_name)
        mesh.materials.append(material)

        # alpha mode
        if bf2_mat.SUPPORTS_TRANSPARENCY:
            has_alpha = bf2_mat.alpha_mode > 0
        else:
            has_alpha = False

        if has_alpha:
            material.blend_method = 'BLEND'

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
            if texture_path:
                # t = os.path.basename(texture_file)
                # if t in bpy.data.images:
                #     bpy.data.images.remove(bpy.data.images[t])
                try:
                    tex_node.image = bpy.data.images.load(os.path.join(texture_path, texture_map), check_existing=True)
                    tex_node.image.alpha_mode = 'NONE'
                except RuntimeError:
                    pass

            tex_node.location = (-1 * NODE_WIDTH, -map_index * NODE_HEIGHT)
            tex_node.hide = True

        _setup_mesh_shader(node_tree, textute_map_nodes, uv_map_nodes,
                           bf2_mat.fxfile, bf2_mat.technique, has_alpha=has_alpha)

    obj = bpy.data.objects.new(name, mesh)
    return obj

def _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod):
    
    if not find_active_skeleton(context):
        return # ignore if skeleton not loaded
    
    if not bf2_mesh.has_blend_indices():
        return

    rig, skeleton = find_active_skeleton(context)

    bf2_lod = bf2_mesh.geoms[geom].lods[lod]

    # find which part vertex belongs to
    vert_part_id = list()
    for mat in bf2_lod.materials:
        for vert in mat.vertices:
            part_id = vert.blendindices[0]
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
    
    if not bf2_mesh.has_blend_indices():
        return

    if not bf2_mesh.has_blend_weight():
        return

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
            m = Matrix(bf2_bone.matrix.m)
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
    for rig_bones, mat in zip(rigs_bones, bf2_lod.materials):
        for vert in mat.vertices:
            bone_ids = vert.blendindices
            bone_weight = vert.blendweight[0]

            weights = []
            _bone = rig_bones[bone_ids[0]]
            weights.append((_bone, bone_weight))
            if bone_weight < 1.0: # max two bones per vert
                _bone = rig_bones[bone_ids[1]]
                weights.append((_bone, 1.0 - bone_weight))
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

def _setup_mesh_shader(node_tree, texture_nodes, uv_map_nodes, shader, technique, has_alpha=False):
    material_output = node_tree.nodes.get('Material Output')
    principled_BSDF = node_tree.nodes.get('Principled BSDF')
    shader_base_color = principled_BSDF.inputs[0]
    shader_specular = principled_BSDF.inputs[7]
    shader_roughness = principled_BSDF.inputs[9]
    shader_normal = principled_BSDF.inputs[22]

    shader_roughness.default_value = 1
    shader_specular.default_value = 0

    if shader.lower() in ('skinnedmesh.fx', 'bundledmesh.fx') :
        UV_CHANNEL = 0      

        diffuse = texture_nodes[0]
        normal = texture_nodes[1]
        diffuse.name = 'Diffuse'
        normal.name = 'Normal'

        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], diffuse.inputs[0])
        node_tree.links.new(uv_map_nodes[UV_CHANNEL].outputs[0], normal.inputs[0])

        if normal.image:
            normal.image.colorspace_settings.name = 'Non-Color'

        # diffuse
        node_tree.links.new(diffuse.outputs[0], shader_base_color)

        # specular
        has_specular = shader.lower() != 'skinnedmesh.fx' and not has_alpha
        if has_specular:
            node_tree.links.new(diffuse.outputs[1], shader_specular)

        # normal
        normal_node = node_tree.nodes.new('ShaderNodeNormalMap')
        normal_node.location = (1 * NODE_WIDTH, 0 * NODE_HEIGHT)
        normal_node.hide = True
        node_tree.links.new(normal.outputs[0], normal_node.inputs[1])

        if shader.lower() == 'skinnedmesh.fx':
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
            transparent_BSDF = node_tree.nodes.new('ShaderNodeBsdfTransparent')
            mix_shader = node_tree.nodes.new('ShaderNodeMixShader')

            node_tree.links.new(principled_BSDF.outputs[0], mix_shader.inputs[2])
            node_tree.links.new(transparent_BSDF.outputs[0], mix_shader.inputs[1])

            node_tree.links.new(diffuse.outputs[1], mix_shader.inputs[0])
            node_tree.links.new(mix_shader.outputs[0], material_output.inputs[0])

        principled_BSDF.location = (3 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)

    elif shader.lower() == 'staticmesh.fx':

        if technique == '':
            return

        if technique in ('ColormapGloss', 'EnvColormapGloss', 'Alpha', 'Alpha_Test'):
            return # TODO

        if technique not in STATICMESH_TECHNIQUES:
            raise RuntimeError(f'Unsupported techinique "{technique}"')

        maps = _split_str_from_word_set(technique, STATICMESH_TEXUTRE_MAP_TYPES)

        if len(texture_nodes) - 1 != len(maps):
            raise RuntimeError(f'Material techinique ({technique}) doesn\'t match number of texture maps ({len(texture_nodes)})')

        base = None
        detail = None
        dirt = None
        crack = None
        ndetail = None
        ncrack = None

        # TODO specular LUT

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

        if base: base.name = 'Base'
        if detail: detail.name = 'Detail'
        if dirt: dirt.name = 'Dirt'
        if crack: crack.name = 'Crack'
        if ndetail: ndetail.name = 'NDetail'
        if ncrack: ncrack.name = 'NCrack'

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
        if dirt:
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
            dirt_out = mult_detaila.outputs[0]
        else:
            dirt_out = detail.outputs[1]
        
        if has_alpha:
            # mult with detaimap normal alpha
            mult_ndetaila = node_tree.nodes.new('ShaderNodeMath')
            mult_ndetaila.operation = 'MULTIPLY'
            mult_ndetaila.location = (1 * NODE_WIDTH, -1 * NODE_HEIGHT)
            mult_ndetaila.hide = True
            
            node_tree.links.new(dirt_out, mult_ndetaila.inputs[1])
            node_tree.links.new(ndetail.outputs[1], mult_ndetaila.inputs[0])
            has_alpha_out = mult_ndetaila.outputs[0]
        else:
            has_alpha_out = dirt_out

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

        principled_BSDF.location = (4 * NODE_WIDTH, 0 * NODE_HEIGHT)
        material_output.location = (5 * NODE_WIDTH, 0 * NODE_HEIGHT)

def _swap_zy(vec):
    return (vec[0], vec[2], vec[1])

def _is_same(v1, v2):
    EPSILON = 0.0001
    return all([abs(v1[i] - v2[i]) < EPSILON for i in range(2)])
