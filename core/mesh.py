import bpy
import bmesh
import os

from itertools import chain
from mathutils import Vector, Matrix

from .bf2.bf2_mesh import BF2Mesh, BF2BundledMesh, BF2SkinnedMesh, BF2StaticMesh
from .bf2.bf2_common import Vec3, Mat4
from .bf2.bf2_mesh.bf2_visiblemesh import Material, MaterialWithTransparency, Vertex, VertexAttribute
from .bf2.bf2_mesh.bf2_types import D3DDECLTYPE, D3DDECLUSAGE

from .exceptions import ImportException, ExportException
from .utils import to_matrix, convert_bf2_pos_rot, delete_object_if_exists, check_prefix
from .skeleton import find_active_skeleton, ske_get_bone_rot, ske_weapon_part_ids
from .mesh_material import (setup_material,
                            get_staticmesh_technique_from_maps, 
                            get_staticmesh_uv_channels,
                            get_tex_type_to_file_mapping,
                            get_material_maps,
                            TEXTURE_MAPS)

SPECULAR_LUT = 'Common\Textures\SpecularLUT_pow36.dds'

def import_mesh(context, mesh_file, **kwargs):
    return _import_mesh(context, BF2Mesh.load(mesh_file), **kwargs)

def import_bundledmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, BF2BundledMesh(mesh_file), **kwargs)

def import_skinnedmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, BF2SkinnedMesh(mesh_file), **kwargs)

def import_staticmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, BF2StaticMesh(mesh_file), **kwargs)

def _build_mesh_prefix(geom=None, lod=None):
    if geom is not None and lod is not None:
        return f'G{geom}L{lod}__'
    elif geom is not None:
        return f'G{geom}__'
    else:
        return ''

def _import_mesh(context, bf2_mesh, name='', geom=None, lod=None, reload=False, remove_doubles=False, **kwargs):
    name = name or bf2_mesh.name
    if geom is None and lod is None:
        if reload: delete_object_if_exists(name)
        root_obj = bpy.data.objects.new(name, None)
        context.scene.collection.objects.link(root_obj)
        for geom_idx, _ in enumerate(bf2_mesh.geoms):
            geom_name = _build_mesh_prefix(geom_idx) + name
            if reload: delete_object_if_exists(geom_name)
            geom_obj = bpy.data.objects.new(geom_name, None)
            geom_obj.parent = root_obj
            context.scene.collection.objects.link(geom_obj)
            for lod_idx, _ in enumerate(bf2_mesh.geoms[geom_idx].lods):
                bf2_lod = bf2_mesh.geoms[geom_idx].lods[lod_idx]
                lod_name = _build_mesh_prefix(geom_idx, lod_idx) + name
                lod_obj = _import_mesh_lod(context, lod_name, bf2_mesh,
                                           bf2_lod, reload, **kwargs)
                if remove_doubles: _remove_double_verts(context, lod_obj)
                lod_obj.parent = geom_obj
        return root_obj
    else:
        bf2_lod = bf2_mesh.geoms[geom].lods[lod]
        lod_obj = _import_mesh_lod(context, name, bf2_mesh, bf2_lod, reload, **kwargs)
        if remove_doubles: _remove_double_verts(context, lod_obj)
        return lod_obj

def collect_uv_layers(mesh_obj, geom=0, lod=0):
    uv_layers = dict()
    if mesh_obj is None:
        return uv_layers

    for geom_obj in mesh_obj.children:
        if geom_obj.name.startswith(f'G{geom}'):
            for lod_obj in geom_obj.children:
                if lod_obj.name.startswith(f'G{geom}L{lod}'):
                    if lod_obj.data:
                        for uv_chan in range(5):
                            if f'UV{uv_chan}' in lod_obj.data.uv_layers:
                                uv_layers[uv_chan] = f'UV{uv_chan}'
    return uv_layers

def export_bundledmesh(mesh_obj, mesh_file, **kwargs):
    return _export_mesh(mesh_obj, mesh_file, BF2BundledMesh, **kwargs)

# def export_skinnedmesh(mesh_obj, mesh_file, **kwargs):
#     return _export_mesh(mesh_obj, mesh_file, BF2SkinnedMesh, **kwargs)

def export_staticmesh(mesh_obj, mesh_file, **kwargs):
    return _export_mesh(mesh_obj, mesh_file, BF2StaticMesh, **kwargs)

def _setup_vertex_attributes(bf2_mesh):
    mesh_type = type(bf2_mesh)
    vert_attrs = bf2_mesh.vertex_attributes
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.POSITION))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.NORMAL))
    if mesh_type == BF2SkinnedMesh:
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT1, D3DDECLUSAGE.BLENDWEIGHT))

    vert_attrs.append(VertexAttribute(D3DDECLTYPE.D3DCOLOR, D3DDECLUSAGE.BLENDINDICES))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD0))

    if mesh_type == BF2StaticMesh:
        # XXX: do we need all those texcoords for vertex if none of the materials use dirt, crack etc??
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD1))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD2))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD3))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD4))
    vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.TANGENT))

def _collect_geoms_lods(mesh_obj):
    if not mesh_obj.children:
        raise ExportException(f"mesh object '{mesh_obj.name}' has no children (geoms)!")
    geoms = list()

    mesh_geoms = dict()
    for geom_obj in mesh_obj.children:
        geom_idx = check_prefix(geom_obj.name, ('G', ))
        if geom_idx in mesh_geoms:
            raise ExportException(f"mesh object '{mesh_obj.name}' has duplicated G{geom_idx}")
        mesh_geoms[geom_idx] = geom_obj
    for _, geom_obj in sorted(mesh_geoms.items()):
        lods = list()
        geoms.append(lods)

        if not geom_obj.children:
            raise ExportException(f"geom '{geom_obj.name}' has no children (lods)!")

        mesh_lods = dict()
        for lod_obj in geom_obj.children:
            _, lod_idx = check_prefix(lod_obj.name, ('G', 'L'))
            if lod_idx in mesh_lods:
                raise ExportException(f"geom '{geom_obj.name}' has duplicated L{lod_idx}")
            mesh_lods[lod_idx] = lod_obj
        for _, lod_obj in sorted(mesh_lods.items()):
            if lod_obj.data is None:
                raise ExportException(f"lod '{lod_obj.name}' has no mesh data!")
            lods.append(lod_obj)

    return geoms


def _export_mesh(mesh_obj, mesh_file, mesh_type, mesh_geoms=None, **kwargs):
    bf2_mesh = mesh_type(name=mesh_obj.name)
    _setup_vertex_attributes(bf2_mesh)

    if mesh_geoms is None:
        mesh_geoms = _collect_geoms_lods(mesh_obj)

    for geom_obj in mesh_geoms:
        geom = mesh_type._GEOM_TYPE()
        bf2_mesh.geoms.append(geom)
        for lod_obj in geom_obj:
            lod = mesh_type._GEOM_TYPE._LOD_TYPE()
            geom.lods.append(lod)
            _export_mesh_lod(mesh_type, lod, lod_obj, **kwargs)

    bf2_mesh.export(mesh_file)
    return bf2_mesh

def _get_vertex_group_to_part_id_mapping(obj):
    vertex_group_to_part_id = dict()
    for vg in obj.vertex_groups:
        part_id = None
        if vg.name.startswith('mesh'):
            try:
                part_id = int(vg.name[len('mesh'):]) - 1
            except ValueError:
                pass

        if part_id is None or part_id < 0:
            raise ExportException(f"Invalid vertex group '{vg.name}', expected 'mesh<index>' where index is a positive integer")

        vertex_group_to_part_id[vg.index] = part_id
    return vertex_group_to_part_id

def _export_mesh_lod(mesh_type, bf2_lod, lod_obj, texture_path='', tangent_uv_map=''):
    mesh = lod_obj.data
    has_custom_normals = mesh.has_custom_normals

    uv_count = 5 if mesh_type == BF2StaticMesh else 1

    # temporarly create custom split normals from vertex normals if not present
    # need them for tangent calculation, otherwise doesn't work for god knows what reason
    if not has_custom_normals:
        vertex_normals = [vert.normal for vert in mesh.vertices]
        mesh.normals_split_custom_set_from_vertices(vertex_normals)

    # XXX: I have no idea what map is this supposed to be calculated on
    # I assume it must match with tangents which were used to generate the normal map
    # but we don't know this! so its probably needed to be added as an export setting?
    if not tangent_uv_map:
        raise ExportException("No UV selected for tangent space generation!")
    mesh.calc_tangents(uvmap=tangent_uv_map)

    # map uv channel to uv layer object
    uv_layers = dict()
    for uv_chan in range(uv_count):
        if f'UV{uv_chan}' in mesh.uv_layers:
            uv_layers[uv_chan] = mesh.uv_layers[f'UV{uv_chan}']

    # lightmap UV, if not present, generate it
    if mesh_type == BF2StaticMesh and 4 not in uv_layers.keys():
        light_uv_layer = mesh.uv_layers.new(name='UV4')
        light_uv_layer.active = True
        bpy.ops.object.select_all(action='DESELECT')
        lod_obj.select_set(True)
        bpy.context.view_layer.objects.active = lod_obj
        bpy.ops.uv.lightmap_pack(PREF_CONTEXT='ALL_FACES', PREF_PACK_IN_ONE=True, PREF_NEW_UVLAYER=False,
                                    PREF_APPLY_IMAGE=False, PREF_IMG_PX_SIZE=128, PREF_BOX_DIV=12, PREF_MARGIN_DIV=0.2)

    # BundledMesh specific
    vertex_group_to_part_id = _get_vertex_group_to_part_id_mapping(lod_obj)

    if mesh_type == BF2StaticMesh:
        bf2_lod.parts = [Mat4()] # TODO parts
    elif mesh_type == BF2BundledMesh:
        # XXX: some geometry parts migh have no verts assigned at all
        # so write all groups defined, might do a warning or something in the future
        bf2_lod.parts_num = len(vertex_group_to_part_id)
    elif mesh_type == BF2SkinnedMesh:
        raise NotImplementedError("rigs!!") # TODO

    # map materials to verts and faces
    mat_idx_to_verts_faces = dict()
    for poly in mesh.polygons:
        if poly.loop_total > 3:
            raise ExportException("Exporter does not support polygons with more than 3 vertices! It must be triangulated")
        if poly.material_index not in mat_idx_to_verts_faces:
            mat_idx_to_verts_faces[poly.material_index] = (set(), list())
        vert_set, face_list = mat_idx_to_verts_faces[poly.material_index]
        for v in poly.vertices:
            vert_set.add(v)
        face_list.append(poly)
    
    # map each vert to a list of loops that use this vert
    vert_loops = dict()
    for loop in mesh.loops:
        vert_idx = loop.vertex_index
        if vert_idx not in vert_loops:
            loops = list()
            vert_loops[vert_idx] = loops
        else:
            loops = vert_loops[vert_idx]
        loops.append(loop)

    # create bf2 materials
    for blend_mat_idx, (blend_vert_set, blend_faces) in sorted(mat_idx_to_verts_faces.items()):
        blend_material = mesh.materials[blend_mat_idx]

        # validate material has correct settings
        if not blend_material.is_bf2_material:
            raise ExportException(f"Material '{blend_material.name}' is not toggled as BF2 material, check material settngs!")  
        
        SHADER_TYPE_TO_MESH = {
            'STATICMESH' : BF2StaticMesh,
            'BUNDLEDMESH' : BF2BundledMesh,
            'SKINNEDMESH' : BF2SkinnedMesh
        }

        if SHADER_TYPE_TO_MESH[blend_material.bf2_shader] != mesh_type:
            raise ExportException(f"Trying to export '{mesh_type.__name__}' but material '{blend_material.name}'"
                                  f" shader type is set to '{blend_material.bf2_shader}', check material settings!")

        bf2_mat : Material = mesh_type._GEOM_TYPE._LOD_TYPE._MATERIAL_TYPE()
        bf2_lod.materials.append(bf2_mat)

        # map each loop to vert index in vertex array
        loop_to_vert_idx = [-1] * len(mesh.loops)

        # merge stats
        merged_loops_count = 0
        total_loops_count = 0

        # create material's vertices
        for vert_idx, loops in vert_loops.items():
            if vert_idx not in blend_vert_set: # filter only vertices for this material
                continue
 
            unique_loops = dict() # loop_idx -> vertex
            merged_loops = dict() # loop_idx -> unique loop idx

            blend_vertex = mesh.vertices[vert_idx]
            for loop in loops:
                vert = Vertex()
                vert.position = _swap_zy(blend_vertex.co)
                vert.normal = _swap_zy(loop.normal)
                vert.tangent = _swap_zy(loop.tangent)

                # (BundledMesh) first elem of blendindices is geom part index
                part_idx = 0
                if len(blend_vertex.groups) > 1:
                    raise ExportException(f"Vertex assigned to more than one vertex group!")
                elif len(blend_vertex.groups) > 0:
                    vert_group = blend_vertex.groups[0].group
                    part_idx = vertex_group_to_part_id[vert_group]

                # third element of blendindices is bitangent sign 0 or 1
                # bitangent was caluculated based on UV and because we flip it vertically
                # (see below) the sign of the bitangent gotta be inverted as well
                bitangent_sign = 0 if loop.bitangent_sign > 0 else 1
                vert.blendindices = (part_idx, 0, bitangent_sign, 0)

                for uv_chan, uvlayer in uv_layers.items():
                    uv = _flip_uv(uvlayer.data[loop.index].uv)
                    setattr(vert, f'texcoord{uv_chan}', uv)

                # check if loop can be merged, if so, add reference to the same loop
                total_loops_count += 1
                for other_loop_idx, other_vert in unique_loops.items():
                    if _can_merge_vert(other_vert, vert, uv_count):
                        merged_loops_count += 1
                        merged_loops[loop.index] = other_loop_idx
                        break
                else:
                    unique_loops[loop.index] = vert

            # add unique verts to vertex buffer
            for loop_idx, vert in unique_loops.items():
                loop_to_vert_idx[loop_idx] = len(bf2_mat.vertices)
                bf2_mat.vertices.append(vert)
            # map the loops to other unique verts
            for loop_idx, unique_loop_idx in merged_loops.items():
                loop_to_vert_idx[loop_idx] = loop_to_vert_idx[unique_loop_idx]

        # create material's faces
        for face in blend_faces:
            face_verts = _invert_face(loop_to_vert_idx[face.loop_start:face.loop_start + face.loop_total])
            bf2_mat.faces.append(face_verts)

        # print stats
        stats = f'{lod_obj.name}_material{bf2_lod.materials.index(bf2_mat)}:'
        stats += f'\n\tmerged loops: {merged_loops_count}/{total_loops_count}'
        stats += f'\n\tvertices: {len(bf2_mat.vertices)}'
        stats += f'\n\tduplicated vertices: {len(bf2_mat.vertices) - len(blend_vert_set)}'
        stats += f'\n\tfaces: {len(bf2_mat.faces)}'
        print(stats)

        ALPHA_MAPPING = {
            'ALPHA_BLEND': MaterialWithTransparency.AlphaMode.ALPHA_BLEND,
            'ALPHA_TEST': MaterialWithTransparency.AlphaMode.ALPHA_TEST,
            'NONE': MaterialWithTransparency.AlphaMode.NONE,
        }

        if isinstance(bf2_mat, MaterialWithTransparency):
            bf2_mat.alpha_mode = ALPHA_MAPPING[blend_material.bf2_alpha_mode]
        
        SHADER_MAPPING = {
            'STATICMESH' : 'StaticMesh.fx',
            'BUNDLEDMESH' : 'BundledMesh.fx',
            'SKINNEDMESH' : 'SkinnedMesh.fx'
        }

        bf2_mat.fxfile = SHADER_MAPPING[blend_material.bf2_shader]

        texture_maps = get_material_maps(blend_material)

        # convert pahts to relative and linux format (game will not find them otherwise)
        for txt_map_type, txt_map_file in texture_maps.items():
            if texture_path: # make relative
                txt_map_file = os.path.relpath(txt_map_file, start=texture_path)
            else:
                pass # TODO: add warning
            texture_maps[txt_map_type] = txt_map_file.replace('\\', '/').lower()

        if mesh_type == BF2StaticMesh:
            bf2_mat.technique = get_staticmesh_technique_from_maps(blend_material)

            if not bf2_mat.technique:
                raise ExportException(f"Could not find a matching shader technique for texture maps: {texture_maps.keys()} "
                                      f" defined for material {blend_material.name}:")

            for texture_map in texture_maps.values():
                bf2_mat.maps.append(texture_map)
            bf2_mat.maps.append(SPECULAR_LUT)

            # check required UVs are present
            for uv_chan in get_staticmesh_uv_channels(texture_maps.keys()):
                if uv_chan not in uv_layers:
                    # TODO: replace with warning
                    raise ExportException(f"{lod_obj.name}: Missing required UV layer 'UV{uv_chan}', make sure it exists and the name is correct")

        elif mesh_type == BF2BundledMesh:
            if not blend_material.bf2_technique:
                raise ExportException(f"{blend_material.name}: Material is missing technique, check material settings!")

            bf2_mat.technique = blend_material.bf2_technique
            if 'Diffuse' not in texture_maps:
                raise ExportException(f"{blend_material.name}: Material is missing 'Diffuse' Texture map, check material settings!")
            bf2_mat.maps.append(texture_maps['Diffuse'])
            if 'Normal' in texture_maps:
                bf2_mat.maps.append(texture_maps['Normal'])
            bf2_mat.maps.append(SPECULAR_LUT)
            if 'Shadow' in texture_maps: # TODO: 3ds max exports shadow as last texture which seems weird, maybe because it is optional? check if the order matters
                bf2_mat.maps.append(texture_maps['Shadow'])

            # check required UVs are present
            if 0 not in uv_layers:
                # TODO: replace with warning
                raise ExportException(f"{lod_obj.name}: Missing required UV layer 'UV0', make sure it exists and the name is correct")

        elif mesh_type == BF2SkinnedMesh:
            raise NotImplementedError() # TODO

    if not has_custom_normals:
        mesh.free_normals_split() # remove custom split normals if we added them
        mesh.free_tangents()

def _can_merge_vert(this, other, uv_count, normal_weld_thres=0.9999, tangent_weld_thres=0.9999):
    """compare vertex data from two loops"""
    # EPSILON = 0.0001
    # if not all([abs(this.normal[i] - other.normal[i]) < EPSILON for i in range(3)]):
    #     return False
    # if not all([abs(this.tangent[i] - other.tangent[i]) < EPSILON for i in range(3)]):
    #     return False
    if Vector(this.tangent).dot(Vector(other.tangent)) < tangent_weld_thres:
        return False
    if Vector(this.normal).dot(Vector(other.normal)) < normal_weld_thres:
        return False
    if this.blendindices[2] != other.blendindices[2]: # bitangent sign
        return False
    for uv_chan in range(uv_count):
        uv_attr = f'texcoord{uv_chan}'
        if getattr(this, uv_attr) != getattr(other, uv_attr):
            return False
    return True

def _import_mesh_lod(context, name, bf2_mesh, bf2_lod, reload=False, texture_path=''):

    if reload:
        delete_object_if_exists(name)

    verts = list()
    faces = list()

    for mat in bf2_lod.materials:
        f_offset = len(verts)
        mat_faces = list()
        for face in mat.faces:
            face_verts = _invert_face([v + f_offset for v in face])
            mat_faces.append(face_verts)
        faces.append(mat_faces)

        for vert in mat.vertices:
            verts.append(_swap_zy(vert.position))

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
    bm.free()

    has_anim_uv = isinstance(bf2_mesh, BF2BundledMesh) and bf2_mesh.has_uv(1) and bf2_mesh.has_blend_indices()
    has_normals = bf2_mesh.has_normal()

    uv_count = 5 if isinstance(bf2_mesh, BF2StaticMesh) else 1
    uvs = dict()
    for uv_chan in range(uv_count):
        if not bf2_mesh.has_uv(uv_chan):
            continue
        uvs[uv_chan] = list()

    vertex_normals = list()
    # vertex_animuv_rot_center = list()
    # vertex_animuv_matrix_index = list()

    for mat in bf2_lod.materials:
        for vert in mat.vertices:
            # Normals
            if has_normals:
                vertex_normals.append(_swap_zy(vert.normal))
                # XXX: Blender does NOT support custom tangents import

            # UVs
            uv_matrix_idx = vert.blendindices[3]
            for uv_chan, vertex_uv in uvs.items():
                uv = getattr(vert, f'texcoord{uv_chan}')
                # if has_anim_uv and uv_matrix_idx != 0:
                #     # FIX UVs for animated parts
                #     # UV1 is actual UV, UV0 is just center of UV rotation / shift
                #     anim_uv_center = vert.texcoord1
                #     uv = (uv[0] + anim_uv_center[0] * 0.5, # XXX: no idea why but I have to do this, probably needs to account for texture ratio?
                #           uv[1] + anim_uv_center[1])
                uv = _flip_uv(uv)
                vertex_uv.append(uv)

            # # Animated UVs data
            # if has_anim_uv:
            #     if uv_matrix_idx != 0:
            #         vertex_animuv_rot_center.append(Vector(vert.texcoord0))
            #     else:
            #         vertex_animuv_rot_center.append(Vector((0, 0)))
            #     vertex_animuv_matrix_index.append(uv_matrix_idx)

    # apply normals
    if has_normals:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.normals_split_custom_set_from_vertices(vertex_normals)
        mesh.use_auto_smooth = True

    # apply Animated UVs data
    # if has_anim_uv:
    #     animuv_matrix_index = mesh.attributes.new('animuv_matrix_index', 'INT8', 'POINT')
    #     animuv_matrix_index.data.foreach_set('value', vertex_animuv_matrix_index)

    #     animuv_rot_center = mesh.color_attributes.new('animuv_rot_center', type='FLOAT2', domain='POINT')
    #     animuv_rot_center.data.foreach_set('vector', list(chain(*vertex_animuv_rot_center)))

    # apply UVs
    for uv_chan, vertex_uv in uvs.items():
        uvlayer = mesh.uv_layers.new(name=f'UV{uv_chan}')
        for l in mesh.loops:
            uvlayer.data[l.index].uv = vertex_uv[l.vertex_index]

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

        material.is_bf2_material = True
        if bf2_mat.fxfile.endswith('.fx'):
            material.bf2_shader = bf2_mat.fxfile[:-3].upper()
        else:
            raise ImportError(f"Bad shader '{bf2_mat.fxfile}'")

        material.bf2_technique = bf2_mat.technique

        texture_map_types = TEXTURE_MAPS[material.bf2_shader]
        texture_maps = get_tex_type_to_file_mapping(material.bf2_shader, material.bf2_technique,
                                                    bf2_mat.maps, texture_path=texture_path)
        for map_type, map_file in texture_maps.items():
            type_index = texture_map_types.index(map_type)
            setattr(material, f"texture_slot_{type_index}", map_file)

        material.bf2_alpha_mode = 'NONE'
        if isinstance(bf2_mat, MaterialWithTransparency):
            if bf2_mat.alpha_mode == MaterialWithTransparency.AlphaMode.ALPHA_BLEND:
                material.bf2_alpha_mode = 'ALPHA_BLEND'
            elif bf2_mat.alpha_mode == MaterialWithTransparency.AlphaMode.ALPHA_TEST:
                material.bf2_alpha_mode = 'ALPHA_TEST'

        setup_material(material, uvs=uvs.keys())

    mesh_obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(mesh_obj)

    if isinstance(bf2_mesh, BF2SkinnedMesh):
        _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, bf2_lod)
    elif isinstance(bf2_mesh, BF2BundledMesh):
        _import_parts_bundled_mesh(context, mesh_obj, bf2_mesh, bf2_lod)

    return mesh_obj

def _import_parts_bundled_mesh(context, mesh_obj, bf2_mesh, bf2_lod):

    if not bf2_mesh.has_blend_indices():
        return

    # find which part vertex belongs to
    vert_part_id = list()
    for mat in bf2_lod.materials:
        for vert in mat.vertices:
            part_id = vert.blendindices[0]
            vert_part_id.append(part_id)

    # create vertex groups and assing verticies to them
    for vertex in mesh_obj.data.vertices:
        part_id = vert_part_id[vertex.index]
        # have to be called same as bones
        group_name = f'mesh{part_id + 1}'
        if group_name not in mesh_obj.vertex_groups.keys():
            mesh_obj.vertex_groups.new(name=group_name)
        mesh_obj.vertex_groups[group_name].add([vertex.index], 1.0, "REPLACE")

    ske_data = find_active_skeleton(context)
    if not ske_data:
        return # ignore if skeleton not loaded
    rig, _ = ske_data
    # parent mesh oject to armature
    mesh_obj.parent = rig
    # add armature modifier to the object
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = rig

def _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, bf2_lod):
    
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

# BF2 <-> Blender convertions

def _swap_zy(vec):
    return (vec[0], vec[2], vec[1])

def _invert_face(verts):
    return (verts[2], verts[1], verts[0])

def _flip_uv(uv):
    u, v = uv
    return (u, 1 - v)

# utils

def _remove_double_verts(context, obj):
    context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT') 
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001, use_sharp_edge_from_normals=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
