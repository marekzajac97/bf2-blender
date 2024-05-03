import bpy # type: ignore
import bmesh # type: ignore
import os
import enum

from itertools import chain
from mathutils import Vector # type: ignore

from .bf2.bf2_mesh import BF2Mesh, BF2BundledMesh, BF2SkinnedMesh, BF2StaticMesh
from .bf2.bf2_common import Mat4
from .bf2.bf2_mesh.bf2_visiblemesh import Material, MaterialWithTransparency, Vertex, VertexAttribute
from .bf2.bf2_mesh.bf2_types import D3DDECLTYPE, D3DDECLUSAGE
from .bf2.fileutils import FileUtils

from .exceptions import ImportException, ExportException
from .utils import (conv_bf2_to_blender,
                    conv_blender_to_bf2,
                    delete_object_if_exists,
                    check_prefix,
                    DEFAULT_REPORTER)
from .skeleton import (ske_get_bone_rot,
                       ske_weapon_part_ids,
                       find_rig_attached_to_object)
from .mesh_material import (setup_material,
                            get_staticmesh_technique_from_maps, 
                            get_staticmesh_uv_channels,
                            get_tex_type_to_file_mapping,
                            get_material_maps,
                            TEXTURE_MAPS)

_DEBUG = False

SPECULAR_LUT = 'Common\Textures\SpecularLUT_pow36.dds'

class AnimUv(enum.IntEnum):
    NONE = 0
    L_WHEEL_ROTATION = 1
    L_WHEEL_TRANSLATION = 2
    R_WHEEL_ROTATION = 3
    R_WHEEL_TRANSLATION = 4
    R_TRACK_TRANSLATION = 5
    L_TRACK_TRANSLATION = 6

ANIM_UV_ROTATION_MATRICES = (AnimUv.L_WHEEL_ROTATION, AnimUv.R_WHEEL_ROTATION)

_MESH_TYPES = {
    'STATICMESH' : BF2StaticMesh,
    'BUNDLEDMESH' : BF2BundledMesh,
    'SKINNEDMESH' : BF2SkinnedMesh
}

# hardcoded BF2 limit
# if you are a BF2142 modder you could increase this to 50 :)
MAX_GEOM_LIMIT = MAX_BONE_LIMIT = 26

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

def import_mesh(context, mesh_file, **kwargs):
    return _import_mesh(context, mesh_file, **kwargs)

def import_bundledmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, mesh_file, mesh_type='BundledMesh', **kwargs)

def import_skinnedmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, mesh_file, mesh_type='SkinnedMesh', **kwargs)

def import_staticmesh(context, mesh_file, **kwargs):
    return _import_mesh(context, mesh_file, mesh_type='StaticMesh', **kwargs)

def _import_mesh(context, mesh_file, mesh_type='',
                 name='', geom=None, lod=None, **kwargs):
    importer = MeshImporter(context, mesh_file, mesh_type=mesh_type, **kwargs)
    return importer.import_mesh(name=name, geom=geom, lod=lod)

def export_bundledmesh(mesh_obj, mesh_file, **kwargs):
    return _export_mesh(mesh_obj, mesh_file, mesh_type='BundledMesh', **kwargs)

def export_skinnedmesh(mesh_obj, mesh_file, **kwargs):
    return _export_mesh(mesh_obj, mesh_file, mesh_type='SkinnedMesh', **kwargs)

def export_staticmesh(mesh_obj, mesh_file, **kwargs):
    return _export_mesh(mesh_obj, mesh_file, mesh_type='StaticMesh', **kwargs)

def _export_mesh(mesh_obj, mesh_file, mesh_type, **kwargs):
    exporter = MeshExporter(mesh_obj, mesh_file, mesh_type, **kwargs)
    return exporter.export_mesh()

class MeshImporter:

    def __init__(self, context, mesh_file, mesh_type='', reload=False,
                 texture_path='', geom_to_ske=None, reporter=DEFAULT_REPORTER):
        self.context = context
        if mesh_type:
            self.bf2_mesh = _MESH_TYPES[mesh_type.upper()](mesh_file)
        else:
            self.bf2_mesh = BF2Mesh.load(mesh_file)
        self.reload = reload
        self.texture_path = texture_path
        self.geom_to_ske = geom_to_ske
        self.reporter = reporter

    def import_mesh(self, name='', geom=None, lod=None):
        name = name or self.bf2_mesh.name
        if geom is None and lod is None:
            if self.reload: delete_object_if_exists(name)
            root_obj = bpy.data.objects.new(name, None)
            self.context.scene.collection.objects.link(root_obj)
            for geom_idx, _ in enumerate(self.bf2_mesh.geoms):
                geom_name = self.build_mesh_prefix(geom_idx) + name
                if self.reload: delete_object_if_exists(geom_name)
                geom_obj = bpy.data.objects.new(geom_name, None)
                geom_obj.parent = root_obj
                self.context.scene.collection.objects.link(geom_obj)
                for lod_idx, _ in enumerate(self.bf2_mesh.geoms[geom_idx].lods):
                    lod_obj = self._import_mesh_lod(self.build_mesh_prefix(geom_idx, lod_idx) + name,
                                                    self.bf2_mesh.geoms[geom_idx].lods[lod_idx])
                    lod_obj.parent = geom_obj
            return root_obj
        else:
            return self._import_mesh_lod(name, self.bf2_mesh.geoms[geom].lods[lod])

    @staticmethod
    def build_mesh_prefix(geom=None, lod=None):
        if geom is not None and lod is not None:
            return f'G{geom}L{lod}__'
        elif geom is not None:
            return f'G{geom}__'
        else:
            return ''

    def _import_mesh_lod(self, name, bf2_lod):
        bf2_mesh = self.bf2_mesh

        if self.reload:
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
        vertex_animuv_rot_center = list()
        vertex_animuv_matrix_index = list()

        for mat in bf2_lod.materials:

            if has_anim_uv and mat.maps:
                try:
                    u_ratio, v_ratio = _get_anim_uv_ratio(mat.maps[0], self.texture_path)
                except Exception:
                    u_ratio = v_ratio = 1.0
                    self.reporter.warning(f"Could not read texture file size: {mat.maps[0]}")

            for vert in mat.vertices:
                # Normals
                if has_normals:
                    vertex_normals.append(_swap_zy(vert.normal))
                    # XXX: Blender does NOT support custom tangents import

                # UVs
                uv_matrix_idx = vert.blendindices[3]
                for uv_chan, vertex_uv in uvs.items():
                    uv = getattr(vert, f'texcoord{uv_chan}')
                    if has_anim_uv and uv_matrix_idx in ANIM_UV_ROTATION_MATRICES:
                        # FIX UVs for animated parts
                        # UV1 is actual UV, UV0 is just center of UV rotation / shift
                        # and needs to be corected by texture size ratio as well
                        vert_animuv_center = vert.texcoord1
                        uv = (uv[0] + vert_animuv_center[0] * u_ratio,
                            uv[1] + vert_animuv_center[1] * v_ratio)
                    uv = _flip_uv(uv)
                    vertex_uv.append(uv)

                # # Animated UVs data
                if has_anim_uv:
                    if uv_matrix_idx in ANIM_UV_ROTATION_MATRICES:
                        vertex_animuv_rot_center.append(Vector(vert.texcoord0))
                    else:
                        vertex_animuv_rot_center.append(Vector((0, 0)))
                    vertex_animuv_matrix_index.append(uv_matrix_idx)

        # apply normals
        if has_normals:
            mesh.normals_split_custom_set_from_vertices(vertex_normals)

        # apply Animated UVs data
        if has_anim_uv:
            animuv_matrix_index = mesh.attributes.new('animuv_matrix_index', 'INT', 'POINT')
            animuv_matrix_index.data.foreach_set('value', vertex_animuv_matrix_index)

            animuv_rot_center = mesh.color_attributes.new('animuv_rot_center', type='FLOAT2', domain='POINT')
            animuv_rot_center.data.foreach_set('vector', list(chain(*vertex_animuv_rot_center)))

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
            try:
                SHADER_MAPPING = {'STATICMESH' : 0, 'BUNDLEDMESH' : 1, 'SKINNEDMESH' : 2}
                material['bf2_shader'] = SHADER_MAPPING[bf2_mat.fxfile[:-3].upper()]
            except KeyError:
                raise ImportError(f"Bad shader '{bf2_mat.fxfile}'")

            material['bf2_technique'] = bf2_mat.technique
            if material.bf2_shader == 'STATICMESH' and 'parallaxdetail' in material.bf2_technique:
                self.reporter.warning(f"Ignoring technique 'parallaxdetail', (not supported)")
                material['bf2_technique'] = material['bf2_technique'].replace('parallaxdetail', '')

            texture_map_types = TEXTURE_MAPS[material.bf2_shader]
            texture_maps = get_tex_type_to_file_mapping(material, bf2_mat.maps)
            for map_type, map_file in texture_maps.items():
                type_index = texture_map_types.index(map_type)
                material[f"texture_slot_{type_index}"] = map_file

            if isinstance(bf2_mat, MaterialWithTransparency):
                material['bf2_alpha_mode'] = bf2_mat.alpha_mode
            else:
                material['bf2_alpha_mode'] = MaterialWithTransparency.AlphaMode.NONE

            setup_material(material, uvs=uvs.keys(), texture_path=self.texture_path, reporter=self.reporter)

        mesh_obj = bpy.data.objects.new(name, mesh)
        self.context.scene.collection.objects.link(mesh_obj)

        if isinstance(bf2_mesh, BF2SkinnedMesh):
            self._import_rig_skinned_mesh(mesh_obj, bf2_lod)
        elif isinstance(bf2_mesh, BF2BundledMesh):
            self._import_parts_bundled_mesh(mesh_obj, bf2_lod)

        return mesh_obj

    def _import_parts_bundled_mesh(self, mesh_obj, bf2_lod):
        if not self.bf2_mesh.has_blend_indices():
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

        rig = self._find_skeleton(bf2_lod)
        if not rig:
            return # ignore if skeleton not loaded

        # add armature modifier to the object
        modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
        modifier.object = rig

    def _import_rig_skinned_mesh(self, mesh_obj, bf2_lod):
        rig = self._find_skeleton(bf2_lod)
        if not rig:
            return # ignore if skeleton not loaded
        
        if not self.bf2_mesh.has_blend_indices():
            return

        if not self.bf2_mesh.has_blend_weight():
            return

        ske_bones = rig['bf2_bones']
        armature = rig.data

        self.context.view_layer.objects.active = rig
        
        # we're gona change the 'rest' transforms of the bones
        bpy.ops.object.mode_set(mode='EDIT')

        id_to_bone = dict()
        for i, ske_bone in enumerate(ske_bones):
            id_to_bone[i] = armature.edit_bones[ske_bone]

        rigs_bones = list()
        for bf2_rig in bf2_lod.rigs:
            rig_bones = list()
            for bf2_bone in bf2_rig.bones:
                m = conv_bf2_to_blender(bf2_bone.matrix)
                bone_obj = id_to_bone[bf2_bone.id]
                bone_obj.matrix = m @ ske_get_bone_rot(bone_obj)
                rig_bones.append(bone_obj.name)
            rigs_bones.append(rig_bones)

        # get weigths from bf2 mesh
        vert_weigths = list()
        for rig_bones, mat in zip(rigs_bones, bf2_lod.materials):
            for vert in mat.vertices:
                bone_ids = vert.blendindices
                bone_weight = vert.blendweight[0]

                weights = []
                if rig_bones: # can be an empty list (e.g dropkit)
                    _bone = rig_bones[bone_ids[0]]
                    weights.append((_bone, bone_weight))
                    if bone_weight < 1.0: # max two bones per vert
                        _bone = rig_bones[bone_ids[1]]
                        weights.append((_bone, 1.0 - bone_weight))
                vert_weigths.append(weights)

        # create vertex group for each bone
        mesh_bones = ske_weapon_part_ids(rig)
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

        # add armature modifier to the object
        modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
        modifier.object = rig

    def _find_skeleton(self, bf2_lod):
        if self.geom_to_ske is None:
            return None
        default_skeleton = self.geom_to_ske.get(-1)
        for geom_idx, geom in enumerate(self.bf2_mesh.geoms):
            if bf2_lod in geom.lods:
                skeleton = self.geom_to_ske.get(geom_idx, default_skeleton)
                break
        if skeleton is None:
            self.reporter.warning(f"No skeleton (amrature) found for Geom {geom_idx}")
        return skeleton

class MeshExporter:

    def __init__(self, mesh_obj, mesh_file, mesh_type,
                 mesh_geoms=None, gen_lightmap_uv=True,
                 texture_path='', tangent_uv_map='',
                 normal_weld_thres=0.999,
                 tangent_weld_thres=0.999,
                 reporter=DEFAULT_REPORTER):
        self.mesh_obj = mesh_obj
        self.mesh_file = mesh_file
        self.mesh_geoms = mesh_geoms
        if self.mesh_geoms is None:
            self.mesh_geoms = self.collect_geoms_lods(self.mesh_obj)
        self.bf2_mesh = _MESH_TYPES[mesh_type.upper()](name=mesh_obj.name)
        self.gen_lightmap_uv = gen_lightmap_uv
        self.texture_path = texture_path
        self.tangent_uv_map = tangent_uv_map
        self.normal_weld_thres = normal_weld_thres
        self.tangent_weld_thres = tangent_weld_thres
        self.reporter = reporter
        self.has_animated_uvs = self._has_anim_uv()

    def export_mesh(self):
        self._setup_vertex_attributes()
        for geom_obj in self.mesh_geoms:
            bf2_geom = self.bf2_mesh.new_geom()
            for lod_obj in geom_obj:
                bf2_lod = bf2_geom.new_lod()
                self._export_mesh_lod(bf2_lod, lod_obj)

        self.bf2_mesh.export(self.mesh_file)
        return self.bf2_mesh  

    def _setup_vertex_attributes(self):
        vert_attrs = self.bf2_mesh.vertex_attributes
        mesh_type = type(self.bf2_mesh)
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.POSITION))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.NORMAL))
        if mesh_type == BF2SkinnedMesh:
            vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT1, D3DDECLUSAGE.BLENDWEIGHT))

        vert_attrs.append(VertexAttribute(D3DDECLTYPE.D3DCOLOR, D3DDECLUSAGE.BLENDINDICES))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD0))
        if self.has_animated_uvs:
            vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD1))

        elif mesh_type == BF2StaticMesh:
            # XXX: do we need all those texcoords for vertex if none of the materials use dirt, crack etc??
            vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD1))
            vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD2))
            vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD3))
            if self.gen_lightmap_uv or self._has_lightmap_uv():
                vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT2, D3DDECLUSAGE.TEXCOORD4))
        vert_attrs.append(VertexAttribute(D3DDECLTYPE.FLOAT3, D3DDECLUSAGE.TANGENT))

    def _has_anim_uv(self):
        if not isinstance(self.bf2_mesh, BF2BundledMesh):
            return False
        for geom_obj in self.mesh_geoms:
            for lod_obj in geom_obj:
                for material in lod_obj.data.materials:
                    if material.is_bf2_material and 'animateduv' in material.bf2_technique.lower():
                        return True
        return False

    def _has_lightmap_uv(self):
        for geom_obj in self.mesh_geoms:
            for lod_obj in geom_obj:
                if 'UV4' in lod_obj.data.uv_layers:
                    return True
        return False

    @staticmethod
    def collect_geoms_lods(mesh_obj):
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

    def _export_mesh_lod(self, bf2_lod, lod_obj):
        mesh = lod_obj.data
        mesh_type = type(self.bf2_mesh)

        uv_count = 5 if mesh_type == BF2StaticMesh else 1

        animuv_matrix_index = mesh.attributes.get('animuv_matrix_index')
        animuv_rot_center = mesh.attributes.get('animuv_rot_center')
        if mesh_type != BF2BundledMesh: # just in case someone does this...
            animuv_matrix_index = None
            animuv_rot_center = None

        # XXX: I have no idea what map is this supposed to be calculated on
        # I assume it must match with tangents which were used to generate the normal map
        # but we don't know this! so its probably needed to be added as an export setting?
        if not self.tangent_uv_map:
            raise ExportException("No UV selected for tangent space generation!")
        mesh.calc_tangents(uvmap=self.tangent_uv_map)

        # lightmap UV, if not present, generate it
        if mesh_type == BF2StaticMesh and 'UV4' not in mesh.uv_layers and self.gen_lightmap_uv:
            light_uv_layer = mesh.uv_layers.new(name='UV4')
            light_uv_layer.active = True
            bpy.ops.object.select_all(action='DESELECT')
            lod_obj.select_set(True)
            bpy.context.view_layer.objects.active = lod_obj
            bpy.ops.uv.lightmap_pack(PREF_CONTEXT='ALL_FACES', PREF_PACK_IN_ONE=True,
                                     PREF_NEW_UVLAYER=False, PREF_BOX_DIV=12, PREF_MARGIN_DIV=0.2)

        # map uv channel to uv layer object
        uv_layers = dict()
        for uv_chan in range(uv_count):
            if f'UV{uv_chan}' in mesh.uv_layers:
                uv_layers[uv_chan] = mesh.uv_layers[f'UV{uv_chan}']

        # number of parts/bones
        if mesh_type == BF2StaticMesh:
            bf2_lod.parts = [Mat4()] # XXX: unused in BF2
        elif mesh_type == BF2BundledMesh:
            vertex_group_to_part_id = dict()
            for vg in lod_obj.vertex_groups:
                part_id = None
                if vg.name.startswith('mesh'):
                    try:
                        part_id = int(vg.name[len('mesh'):]) - 1
                    except ValueError:
                        pass
                if part_id is None or part_id < 0:
                    raise ExportException(f"Invalid vertex group '{vg.name}', expected 'mesh<index>' where index is a positive integer")
                vertex_group_to_part_id[vg.index] = part_id

            # NOTE: some geometry parts migh have no verts assigned at all
            # that's why we gonna write all groups defined
            bf2_lod.parts_num = len(vertex_group_to_part_id)
            if bf2_lod.parts_num > MAX_GEOM_LIMIT:
                raise ExportException(f"{lod_obj.name}: BF2 only supports a maximum of "
                                      f"{MAX_GEOM_LIMIT} geometry parts but got {bf2_lod.parts_num}")
        elif mesh_type == BF2SkinnedMesh:
            bone_to_matrix = dict()
            bone_to_id = dict()
            rig = find_rig_attached_to_object(lod_obj)
            if rig is None:
                raise ExportException(f"{lod_obj.name}: does not have 'Armature' modifier or 'Object' in the modifier settings does not point to a BF2 skeleton")
            ske_bones = rig['bf2_bones']

            for bone_id, ske_bone in enumerate(ske_bones):
                bone_obj = rig.data.bones[ske_bone]
                m = bone_obj.matrix_local.copy() @ ske_get_bone_rot(bone_obj).inverted()
                bone_to_matrix[bone_obj.name] = conv_blender_to_bf2(m)
                bone_to_id[bone_obj.name] = bone_id

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

            if _MESH_TYPES[blend_material.bf2_shader] != mesh_type:
                raise ExportException(f"Trying to export '{mesh_type.__name__}' but material '{blend_material.name}'"
                                    f" shader type is set to '{blend_material.bf2_shader}', check material settings!")

            # create matrerial
            bf2_mat : Material = bf2_lod.new_material()

            # alpha mode
            if isinstance(bf2_mat, MaterialWithTransparency):
                bf2_mat.alpha_mode = MaterialWithTransparency.AlphaMode[blend_material.bf2_alpha_mode]
            
            # fx shader
            SHADER_MAPPING = {
                'STATICMESH' : 'StaticMesh.fx',
                'BUNDLEDMESH' : 'BundledMesh.fx',
                'SKINNEDMESH' : 'SkinnedMesh.fx'
            }

            bf2_mat.fxfile = SHADER_MAPPING[blend_material.bf2_shader]

            # texture paths
            texture_maps = get_material_maps(blend_material)

            # paths should already be relative but convert to linux format just in case (game will not find them otherwise)
            for txt_map_type, txt_map_file in texture_maps.items():
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
                        self.reporter.warning(f"{lod_obj.name}: Missing required UV layer 'UV{uv_chan}', make sure it exists and the name is correct")

            elif mesh_type == BF2BundledMesh or mesh_type == BF2SkinnedMesh:
                # XXX: many SkinnedMeshes have just empty technique (idk why) and just work
                if mesh_type == BF2BundledMesh and not blend_material.bf2_technique:
                    self.reporter.warning(f"{blend_material.name}: Material is missing technique, check material settings!")

                bf2_mat.technique = blend_material.bf2_technique
                if 'Diffuse' not in texture_maps:
                    raise ExportException(f"{blend_material.name}: Material is missing 'Diffuse' Texture map, check material settings!")
                bf2_mat.maps.append(texture_maps['Diffuse'])
                if 'Normal' in texture_maps:
                    bf2_mat.maps.append(texture_maps['Normal'])
                bf2_mat.maps.append(SPECULAR_LUT)
                if mesh_type == BF2BundledMesh and 'Shadow' in texture_maps:
                    bf2_mat.maps.append(texture_maps['Shadow'])
                # check required UVs are present
                if 0 not in uv_layers:
                    self.reporter.warning(f"{lod_obj.name}: Missing required UV layer 'UV0', make sure it exists and the name is correct")

            # rigs
            if mesh_type == BF2SkinnedMesh:
                bone_list = list() # bone names used for this material
                bf2_rig = bf2_lod.new_rig()

            # animated UV ratio (BundledMesh)
            if animuv_rot_center:
                try:
                    u_ratio, v_ratio = _get_anim_uv_ratio(texture_maps['Diffuse'], self.texture_path)
                except (ValueError, FileNotFoundError) as e:
                    raise ExportException(str(e)) from e

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
                    
                    # blendindices
                    blendindices = [0, 0, 0, 0]
                    # - (BundledMesh) first one is geom part index, second one unused
                    # - (SkinnedMesh) first and second one are bone indices
                    # - (StaticMesh)  both first and second one are unused
                    if mesh_type == BF2BundledMesh:
                        if len(blend_vertex.groups) > 1:
                            raise ExportException(f"{lod_obj.name}: Found vertex assigned to more than one vertex group!")
                        elif len(blend_vertex.groups) > 0:
                            vert_group = blend_vertex.groups[0].group
                            blendindices[0] = vertex_group_to_part_id[vert_group]
                    elif mesh_type == BF2SkinnedMesh:
                        if len(blend_vertex.groups) > 2:
                            raise ExportException(f"{lod_obj.name}: Found vertex assigned to more than two vertex groups (bones)!, BF2 only supports two bones per vertex")
                        elif len(blend_vertex.groups) == 0:
                            if bone_list:
                                # it's not possible for a material to have some verts weighted and some not
                                raise ExportException(f"{lod_obj.name}: Not all vertices have been assigned to a vertex group (bone)!")
                            else:
                                # but it's possible for it to have no weights (e.g. dropkit)
                                vert.blendweight = (0,)
                        else:
                            _bone_weights = list()
                            for _bone_idx, _bone in enumerate(blend_vertex.groups):
                                _bone_name = lod_obj.vertex_groups[_bone.group].name
                                _bone_weights.append(_bone.weight)
                                try:
                                    blendindices[_bone_idx] = bone_list.index(_bone_name)
                                except ValueError:
                                    blendindices[_bone_idx] = len(bone_list)
                                    bone_list.append(_bone_name)
                                    if len(bone_list) > MAX_BONE_LIMIT:
                                        raise ExportException(f"{lod_obj.name} (mat: {blend_material.name}): BF2 only supports a maximum of {MAX_BONE_LIMIT} bones per material")
                                    bf2_bone = bf2_rig.new_bone()
                                    if _bone_name not in bone_to_id:
                                        raise ExportException(f"{lod_obj.name} (mat: {blend_material.name}): bone '{_bone_name}' is not present in BF2 skeleton")
                                    bf2_bone.id = bone_to_id[_bone_name]
                                    bf2_bone.matrix = bone_to_matrix[_bone_name]

                            if abs(sum(_bone_weights) - 1.0) > 0.001:
                                raise ExportException(f"{lod_obj.name}: Found vertex with weights that are not normalized, all weights must add up to 1!")
                            vert.blendweight = (_bone_weights[0],)

                    # third element of blendindices is bitangent sign 0 or 1
                    # bitangent was caluculated based on UV and because we flip it vertically
                    # (see below) the sign of the bitangent gotta be inverted as well
                    blendindices[2] = 0 if loop.bitangent_sign > 0 else 1

                    # (BundledMesh) fourth elem of blendindices is matrix index of the animated UV
                    # (SkinnedMesh/StaticMesh) unused
                    if animuv_matrix_index:
                        blendindices[3] = AnimUv(animuv_matrix_index.data[vert_idx].value)

                    vert.blendindices = tuple(blendindices)

                    # UVs
                    for uv_chan in range(uv_count):
                        uvlayer = uv_layers.get(uv_chan)
                        if uvlayer:
                            uv = _flip_uv(uvlayer.data[loop.index].uv)
                        else:
                            uv = (0, 0)
                        setattr(vert, f'texcoord{uv_chan}', uv)

                    # animated UVs
                    if self.has_animated_uvs:
                        vert.texcoord1 = (0, 0)
                        if animuv_rot_center and blendindices[3] in ANIM_UV_ROTATION_MATRICES:
                            # take the original UV and substract rotation center
                            # scale by texture size ratio, move to TEXCOORD1
                            # keeping only the center of rotation in TEXCOORD0
                            uv = vert.texcoord0
                            vert_animuv_center = animuv_rot_center.data[vert_idx].vector
                            vert.texcoord1 = ((uv[0] - vert_animuv_center[0]) / u_ratio,
                                            (uv[1] - vert_animuv_center[1]) / v_ratio)
                            vert.texcoord0 = vert_animuv_center

                    # check if loop can be merged, if so, add reference to the same loop
                    total_loops_count += 1
                    for other_loop_idx, other_vert in unique_loops.items():
                        if self._can_merge_vert(other_vert, vert, uv_count):
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
            if _DEBUG:
                stats = f'{lod_obj.name}_material{bf2_lod.materials.index(bf2_mat)}:'
                stats += f'\n\tmerged loops: {merged_loops_count}/{total_loops_count}'
                stats += f'\n\tvertices: {len(bf2_mat.vertices)}'
                stats += f'\n\tduplicated vertices: {len(bf2_mat.vertices) - len(blend_vert_set)}'
                stats += f'\n\tfaces: {len(bf2_mat.faces)}'
                print(stats)

            if mesh_type == BF2SkinnedMesh and not bone_list:
                self.reporter.warning(f"{lod_obj.name}: (mat: {blend_material.name}): has no weights assigned")

        mesh.free_tangents()

    def _can_merge_vert(self, this, other, uv_count):
        """compare vertex data from two loops"""
        if Vector(this.tangent).dot(Vector(other.tangent)) < self.tangent_weld_thres:
            return False
        if Vector(this.normal).dot(Vector(other.normal)) < self.normal_weld_thres:
            return False
        if this.blendindices[2] != other.blendindices[2]: # bitangent sign
            return False
        for uv_chan in range(uv_count):
            uv_attr = f'texcoord{uv_chan}'
            if getattr(this, uv_attr) != getattr(other, uv_attr):
                return False
        return True

# BF2 <-> Blender convertions

def _swap_zy(vec):
    return (vec[0], vec[2], vec[1])

def _invert_face(verts):
    return (verts[2], verts[1], verts[0])

def _flip_uv(uv):
    u, v = uv
    return (u, 1 - v)

# utils

def _get_texture_size(texture_file):
    with open(texture_file, "rb") as file:
        f = FileUtils(file)
        magic = f.read_dword()
        if magic != 0x20534444:
            raise ValueError(f"{texture_file} not a DDS file!")
        size = f.read_dword()
        flags = f.read_dword()
        height = f.read_dword()
        width = f.read_dword()
        return height, width

def _get_anim_uv_ratio(texture_map_file, texture_path):
    u_ratio = 1.0
    v_ratio = 1.0
    if texture_path:
        texture_map_file = os.path.join(texture_path, texture_map_file)
    texture_size = _get_texture_size(texture_map_file)
    tex_height, tex_width = texture_size
    if tex_width > tex_height:
        u_ratio = tex_height / tex_width
    elif tex_height > tex_width:
        v_ratio = tex_width / tex_height
    return u_ratio, v_ratio
