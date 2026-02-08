import bpy # type: ignore
import bmesh # type: ignore
import os
import enum

from itertools import chain
from mathutils import Vector # type: ignore

from .bf2.bf2_mesh import BF2MeshException, BF2Mesh, BF2BundledMesh, BF2SkinnedMesh, BF2StaticMesh
from .bf2.bf2_common import Mat4
from .bf2.bf2_mesh.bf2_visiblemesh import Material, MaterialWithTransparency, Vertex
from .bf2.fileutils import FileUtils

from .exceptions import ImportException, ExportException
from .utils import (conv_bf2_to_blender,
                    conv_blender_to_bf2,
                    delete_object,
                    delete_object_if_exists,
                    check_prefix,
                    swap_zy,
                    flip_uv,
                    invert_face,
                    are_backfaces,
                    apply_modifiers,
                    triangulate,
                    compare_val,
                    file_name,
                    DEFAULT_REPORTER)
from .skeleton import (ske_get_bone_rot,
                       ske_weapon_part_ids,
                       find_rig_attached_to_object)
from .material import (setup_material,
                            get_staticmesh_technique_from_maps, 
                            get_staticmesh_uv_channels,
                            get_tex_type_to_file_mapping,
                            get_material_maps,
                            texture_suffix_is_valid,
                            get_texture_suffix,
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
                 texture_paths=[], geom_to_ske=None, merge_materials=True,
                 load_backfaces=True, loader=None, silent=False, reporter=DEFAULT_REPORTER):
        self.context = context
        self.is_vegitation = 'vegitation' in mesh_file.lower() # yeah this is legit how BF2 detects it lmao

        if loader:
            self._loader = loader
        elif mesh_type: 
            self._loader = lambda: _MESH_TYPES[mesh_type.upper()](mesh_file)
        else:
            self._loader = lambda: BF2Mesh.load(mesh_file)

        self.bf2_mesh = None
        self.reload = reload
        self.texture_paths = texture_paths
        self.geom_to_ske = geom_to_ske
        self.reporter = reporter
        self.mesh_materials = []
        self.merge_materials = merge_materials
        self.load_backfaces = load_backfaces
        self.silent = silent

    def import_mesh(self, name='', geom=None, lod=None):
        try:
            self.bf2_mesh = self._loader()
        except BF2MeshException as e:
            raise ImportException(str(e)) from e

        self.mesh_name = name or self.bf2_mesh.name
        self._cleanup_old_materials()
        if geom is None and lod is None:
            if self.reload: delete_object_if_exists(self.mesh_name)
            root_obj = bpy.data.objects.new(self.mesh_name, None)
            self.context.scene.collection.objects.link(root_obj)
            for geom_idx, _ in enumerate(self.bf2_mesh.geoms):
                geom_name = self.build_mesh_prefix(geom_idx) + self.mesh_name
                if self.reload: delete_object_if_exists(geom_name)
                geom_obj = bpy.data.objects.new(geom_name, None)
                geom_obj.parent = root_obj
                self.context.scene.collection.objects.link(geom_obj)
                for lod_idx, _ in enumerate(self.bf2_mesh.geoms[geom_idx].lods):
                    lod_obj = self._import_mesh_lod(self.build_mesh_prefix(geom_idx, lod_idx) + self.mesh_name,
                                                    self.bf2_mesh.geoms[geom_idx].lods[lod_idx])
                    lod_obj.parent = geom_obj
            return root_obj
        else:
            return self._import_mesh_lod(self.mesh_name, self.bf2_mesh.geoms[geom].lods[lod])

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
        
        has_normals = bf2_mesh.has_normal()
        has_anim_uv = (isinstance(bf2_mesh, BF2BundledMesh) and
                       bf2_mesh.has_uv(1) and bf2_mesh.has_blend_indices())

        uv_count = 5 if isinstance(bf2_mesh, BF2StaticMesh) else 1
        uvs = dict()
        for uv_chan in range(uv_count):
            if not bf2_mesh.has_uv(uv_chan):
                continue
            uvs[uv_chan] = list()

        vertex_normals = list()
        vertex_animuv_rot_center = list()
        vertex_animuv_matrix_index = list()

        mesh_materials = list()

        bm = bmesh.new()
        vertex_offset = 0

        fucked_up_faces = 0
        double_sided_faces = set()

        for bf2_mat in bf2_lod.materials:
            uv_ratio = None

            # create vertices
            for vert in bf2_mat.vertices:
                bm.verts.new(swap_zy(vert.position))

                # Normals
                if has_normals:
                    vertex_normals.append(swap_zy(vert.normal))
                    # XXX: Blender does NOT support custom tangents import

                # UVs
                uv_matrix_idx = vert.blendindices[3]
                for uv_chan, vertex_uv in uvs.items():
                    uv = getattr(vert, f'texcoord{uv_chan}')
                    if has_anim_uv and uv_matrix_idx in ANIM_UV_ROTATION_MATRICES:
                        if uv_ratio is None:
                            try:
                                uv_ratio = _get_anim_uv_ratio(bf2_mat.maps[0], self.texture_paths)
                            except Exception:
                                uv_ratio = (1.0, 1.0)
                                self.reporter.warning(f"Could not read texture size: {bf2_mat.maps[0]}")
                        # FIX UVs for animated parts
                        # UV1 is actual UV, UV0 is just center of UV rotation / shift
                        # and needs to be corected by texture size ratio as well
                        vert_animuv_center = vert.texcoord1
                        uv = (uv[0] + vert_animuv_center[0] * uv_ratio[0],
                            uv[1] + vert_animuv_center[1] * uv_ratio[1])
                    uv = flip_uv(uv)
                    vertex_uv.append(uv)

                # Animated UVs data
                if has_anim_uv:
                    if uv_matrix_idx in ANIM_UV_ROTATION_MATRICES:
                        vertex_animuv_rot_center.append(Vector(vert.texcoord0))
                    else:
                        vertex_animuv_rot_center.append(Vector((0, 0)))
                    vertex_animuv_matrix_index.append(uv_matrix_idx)

            bm.verts.ensure_lookup_table()
            bm.verts.index_update()

            # create materials
            mat_idx = self._get_unique_material_index(bf2_mat)
            mat_name = f'{self.mesh_name}_material_{mat_idx}'
            if mat_name in bpy.data.materials.keys():
                material = bpy.data.materials[mat_name]
            else:
                material = bpy.data.materials.new(mat_name)
                try:
                    material.bf2_shader = bf2_mat.fxfile[:-3].upper()
                except TypeError:
                    raise ImportError(f"Unsupported shader '{bf2_mat.fxfile}'")

                if _MESH_TYPES[material.bf2_shader] != type(bf2_mesh):
                    self.reporter.warning(f"'{name}': Material shader '{bf2_mat.fxfile}' doesn't match the mesh type")

                is_basendetail = False
                material.bf2_technique = bf2_mat.technique
                if material.bf2_shader == 'STATICMESH':
                    if 'parallaxdetail' in material.bf2_technique:
                        if not self.silent:
                            self.reporter.warning(f"'{name}': Technique 'parallaxdetail' is not supported and will be ignored")
                        material.bf2_technique = material.bf2_technique.replace('parallaxdetail', '')
                    elif material.bf2_technique.lower() in ('basendetail', 'basenbase'):
                        # XXX: BF2 shaders seem to also support 'BaseNBase' (base with normal maps), I've never seen it used anywhere
                        # 'BaseNDetail' is used on some meshes though and internally it gets changed to 'BaseNBase' by the game
                        # but since it is rarely used there is no point in supporting it for now
                        if not self.silent:
                            self.reporter.warning(f"'{name}': Technique '{material.bf2_technique}' is not supported and will be replaced with 'BaseDetailNDetail' with a dummy base texture")
                        material.bf2_technique = 'BaseDetailNDetail'
                        bf2_mat.maps.insert(0, 'dummy_for_basendetail.dds') # won't import but we don't care
                        is_basendetail = True

                texture_map_types = TEXTURE_MAPS[material.bf2_shader]
                texture_maps = get_tex_type_to_file_mapping(material, bf2_mat.maps)
                for map_type, map_file in texture_maps.items():
                    if os.path.isabs(map_file):
                        if not self.silent:
                            self.reporter.warning(f"Invalid material texture map path: '{map_file}' is an absolute path, ignoring and converting to relative path...")
                        map_file = map_file.lstrip('/').lstrip('\\')
                    type_index = texture_map_types.index(map_type)
                    setattr(material, f'texture_slot_{type_index}', map_file)

                if isinstance(bf2_mat, MaterialWithTransparency): # BundledMesh, StaticMesh
                    material.bf2_alpha_mode = bf2_mat.alpha_mode.name
                elif 'alpha_test' in material.bf2_technique.lower(): # SkinnedMesh
                    material.bf2_alpha_mode = 'ALPHA_TEST'
                else:
                    material.bf2_alpha_mode = 'NONE'

                if isinstance(bf2_mesh, BF2StaticMesh):
                    material.is_bf2_vegitation = self.is_vegitation

                material.is_bf2_material = True # MUST be set last!
                setup_material(material, uvs=uvs.keys(), texture_paths=self.texture_paths, reporter=self.reporter)

                # BaseNDetail workaround
                if is_basendetail:
                    base = material.node_tree.nodes.get('Base')
                    material.node_tree.nodes.remove(base)

            try:
                material_index = mesh_materials.index(material)
            except ValueError:
                material_index = len(mesh_materials)
                mesh_materials.append(material)

            # create faces
            for face in bf2_mat.faces:
                face_verts = [bm.verts[v + vertex_offset] for v in invert_face(face)]
                try:
                    bm_face = bm.faces.new(face_verts)
                    bm_face.material_index = material_index
                except ValueError:
                    # duplicate face.. or vert, lets find out
                    if not self.load_backfaces:
                        fucked_up_faces += 1
                        continue
                    if len(set(face_verts)) != 3: # duplicate vert
                        fucked_up_faces += 1
                        continue

                    bm.faces.index_update()
                    bm_face_verts = [vert.index for vert in face_verts]
                    for other_bm_face in bm.faces:
                        if are_backfaces(bm_face_verts, [vert.index for vert in other_bm_face.verts]):
                            if material_index != other_bm_face.material_index: # XXX: could they differ ??
                                raise ImportException("Attempted to create a backface with different material index, aborting")
                            double_sided_faces.add(other_bm_face.index)
                            break
                    else:
                        # must be a duplicate face
                        fucked_up_faces += 1

            vertex_offset += len(bf2_mat.vertices)

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()

        if fucked_up_faces and not self.silent:
            self.reporter.warning(f"'{name}': Skipped {fucked_up_faces} invalid faces")

        # mark faces with backfaces
        if double_sided_faces:
            animuv_matrix_index = mesh.attributes.new('backface', 'BOOLEAN', 'FACE')
            animuv_matrix_index.data.foreach_set('value', [poly.index in double_sided_faces for poly in mesh.polygons])

        # apply materials
        for material in mesh_materials:
            mesh.materials.append(material)

        # apply normals
        if has_normals:
            if isinstance(bf2_mesh, BF2SkinnedMesh):
                # Note to self: by default 'sharp_face' is true so smooth shading (interpolated normals) is disabled
                # but if mesh uses custom normals the normals get interpolated anyways...
                # either way smooth shading MUST be enabled before calculating custom split normals
                # otherwise on defomration normals will be broken af
                mesh.attributes['sharp_face'].data.foreach_set('value', [False] * len(mesh.polygons))
                mesh.normals_split_custom_set_from_vertices(vertex_normals)
            else:
                # use per vertex normals in object space for non-deformable objects, docs says they are faster...
                # https://docs.blender.org/manual/en/dev/modeling/meshes/structure.html#free-normals
                custom_normal = mesh.attributes.new('custom_normal', 'FLOAT_VECTOR', 'POINT')
                custom_normal.data.foreach_set('vector', [n for vn in vertex_normals for n in vn])

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

        mesh_obj = bpy.data.objects.new(name, mesh)
        self.context.scene.collection.objects.link(mesh_obj)

        if isinstance(bf2_mesh, BF2SkinnedMesh):
            # add custom modifier which saves tangent & normal vectors to attributes
            # need those from before mesh deformation to fix shading with OS normal maps later
            modifier = mesh_obj.modifiers.new(type='NODES', name="SaveTangentSpace")
            modifier.node_group = _make_rest_tangent_space_node()
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
        return skeleton

    def _cleanup_old_materials(self):
        self.mesh_materials = []
        for material in list(bpy.data.materials):
            if material.name.startswith(f'{self.mesh_name}_material_'):
                bpy.data.materials.remove(material, do_unlink=True)

    def _get_unique_material_index(self, other_bf2_mat):
        material_index = lod_index = geom_index = -1
        bone_count = 0

        if self.merge_materials:
            if isinstance(self.bf2_mesh, BF2SkinnedMesh):
                for geom_idx, geom in enumerate(self.bf2_mesh.geoms):
                    if material_index != -1:
                        break
                    for lod_idx, lod in enumerate(geom.lods):
                        try:
                            material_index = lod.materials.index(other_bf2_mat)
                            rig = lod.rigs[material_index]
                            bone_count = len(rig.bones)
                            geom_index = geom_idx
                            lod_index = lod_idx
                            break
                        except ValueError:
                            pass   

            for mat_idx, mat_data in enumerate(self.mesh_materials):
                bf2_mat = mat_data['bf2_mat']
                if type(bf2_mat) != type(other_bf2_mat):
                    continue
                if bf2_mat.fxfile.lower() != other_bf2_mat.fxfile.lower():
                    continue
                if bf2_mat.technique.lower() != other_bf2_mat.technique.lower():
                    continue
                if len(bf2_mat.maps) != len(other_bf2_mat.maps):
                    continue
                textures_eq = True
                for texture_map, other_texture_map in zip(bf2_mat.maps, other_bf2_mat.maps):
                    if texture_map.lower() != other_texture_map.lower():
                        textures_eq = False
                        break
                if not textures_eq:
                    continue
                if (isinstance(bf2_mat, MaterialWithTransparency) and
                    bf2_mat.alpha_mode != other_bf2_mat.alpha_mode):
                    continue

                material_bone_count = mat_data['geom_to_bone_count'].setdefault(geom_index, 0)
                if material_bone_count + bone_count > MAX_BONE_LIMIT:
                    self.reporter.info(f"Geom{geom_index} Lod{lod_index}: material {material_index} won't be merged, bone limit has been reached")
                    break
                mat_data['geom_to_bone_count'][geom_index] += bone_count
                return mat_idx

        mat_idx = len(self.mesh_materials)
        geom_to_bone_count = dict()
        geom_to_bone_count[geom_index] = bone_count
        mat_data = {'bf2_mat': other_bf2_mat, 'geom_to_bone_count': geom_to_bone_count}
        self.mesh_materials.append(mat_data)
        return mat_idx


TMP_PREFIX = 'TMP__'

class MeshExporter:

    def __init__(self, mesh_obj, mesh_file, mesh_type,
                 mesh_geoms=None, gen_lightmap_uv=True,
                 texture_paths=[],
                 normal_weld_thres=0.999,
                 tangent_weld_thres=0.999,
                 save_backfaces=True,
                 apply_modifiers=False,
                 triangulate=False,
                 reporter=DEFAULT_REPORTER):
        self.mesh_obj = mesh_obj
        self.mesh_file = mesh_file
        self.mesh_geoms = mesh_geoms
        self.bf2_mesh = _MESH_TYPES[mesh_type.upper()](name=mesh_obj.name)
        self.gen_lightmap_uv = gen_lightmap_uv
        self.texture_paths = texture_paths
        self.normal_weld_thres = normal_weld_thres
        self.tangent_weld_thres = tangent_weld_thres
        self.reporter = reporter
        self.has_animated_uvs = None # checked later
        self.save_backfaces = save_backfaces
        self.apply_modifiers = apply_modifiers
        self.triangulate = triangulate

    def export_mesh(self):
        if self.mesh_geoms:
            return self._export_mesh()
        else:
            try:
                self.mesh_geoms = self.collect_geoms_lods(self.mesh_obj)
                self.mesh_geoms = self._make_temp_geoms_lods(self.mesh_geoms)
                return self._export_mesh()
            except Exception:
                raise
            finally:
                self._revert_temp_geom_lods()

    def _export_mesh(self):
        self.has_animated_uvs = self._has_anim_uv()
        self._setup_vertex_attributes()
        for geom_obj in self.mesh_geoms:
            bf2_geom = self.bf2_mesh.new_geom()
            for lod_obj in geom_obj:
                bf2_lod = bf2_geom.new_lod()
                self._export_mesh_lod(bf2_lod, lod_obj)
        try:
            self.bf2_mesh.export(self.mesh_file)
        except BF2MeshException as e:
            raise ExportException(str(e)) from e
        return self.bf2_mesh

    def _setup_vertex_attributes(self):
        self.bf2_mesh.add_vert_attr('FLOAT3', 'POSITION')
        self.bf2_mesh.add_vert_attr('FLOAT3', 'NORMAL')
        if isinstance(self.bf2_mesh, BF2SkinnedMesh):
            self.bf2_mesh.add_vert_attr('FLOAT1', 'BLENDWEIGHT')

        self.bf2_mesh.add_vert_attr('D3DCOLOR', 'BLENDINDICES')
        self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD0')
        if self.has_animated_uvs:
            self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD1')

        elif isinstance(self.bf2_mesh, BF2StaticMesh):
            # XXX: do we need all those texcoords for vertex if none of the materials use dirt, crack etc??
            self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD1')
            self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD2')
            self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD3')
            if self.gen_lightmap_uv or self._has_lightmap_uv():
                self.bf2_mesh.add_vert_attr('FLOAT2', 'TEXCOORD4')
        self.bf2_mesh.add_vert_attr('FLOAT3', 'TANGENT')

    def _any_material_has_anim_uv(self, lod_obj):
        for material in lod_obj.data.materials:
            if material.is_bf2_material and 'animateduv' in material.bf2_technique.lower():
                return True
        return False

    def _has_anim_uv(self):
        if not isinstance(self.bf2_mesh, BF2BundledMesh):
            return False
        for geom_obj in self.mesh_geoms:
            for lod_obj in geom_obj:
                if self._any_material_has_anim_uv(lod_obj):
                    return True
        return False

    def _has_lightmap_uv(self):
        for geom_obj in self.mesh_geoms:
            for lod_obj in geom_obj:
                if 'UV4' in lod_obj.data.uv_layers:
                    return True
        return False

    @staticmethod
    def _make_temp_object(obj, prefix=TMP_PREFIX):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action='DESELECT')
        hide = obj.hide_get()
        obj.hide_set(False)
        obj.select_set(True)
        name = obj.name
        obj.name = prefix + name # rename original
        bpy.ops.object.duplicate() # duplicate
        new_obj = bpy.context.view_layer.objects.active
        new_obj.name = name # set copy name to original object
        obj.hide_set(hide)
        return new_obj

    @staticmethod
    def _revert_temp_object(obj, prefix=TMP_PREFIX):
        name = obj.name
        org_obj = bpy.data.objects[prefix + obj.name]
        delete_object(obj, recursive=False)
        org_obj.name = name

    def _revert_temp_geom_lods(self):
        for geom_obj in self.mesh_geoms:
            for lod_obj in geom_obj:
                self._revert_temp_object(lod_obj)

    def _make_temp_geoms_lods(self, mesh_geoms):
        new_mesh_geoms = list()
        for geom_obj in mesh_geoms:
            new_geom_obj = list()
            new_mesh_geoms.append(new_geom_obj)
            for lod_obj in geom_obj:
                new_lod_obj = self._make_temp_object(lod_obj)
                new_geom_obj.append(new_lod_obj)
        return new_mesh_geoms

    @staticmethod
    def _check_obj_transform(obj):
        if not compare_val(obj.scale, (1, 1, 1)):
            raise ExportException(f"'{obj.name}' has non-uniform scale: {tuple(obj.scale)}")
        if not compare_val(obj.location, (0, 0, 0)):
            raise ExportException(f"'{obj.name}' has non-zero location: {tuple(obj.location)})")
        if not compare_val(obj.rotation_quaternion, (1, 0, 0, 0)):
            raise ExportException(f"'{obj.name}' has non-zero rotation (quat): {tuple(obj.rotation_quaternion)}")

    @staticmethod
    def collect_geoms_lods(root_obj, skip_checks=False):
        if not root_obj.children:
            raise ExportException(f"root object '{root_obj.name}' has no children (geoms)!")
        if not skip_checks and not compare_val(root_obj.scale, (1, 1, 1)):
            raise ExportException(f"'{root_obj.name}' has non-uniform scale: {tuple(root_obj.scale)}")
        geoms = list()

        mesh_geoms = dict()
        for geom_obj in root_obj.children:
            geom_idx = check_prefix(geom_obj.name, ('G', ))
            if geom_idx in mesh_geoms:
                raise ExportException(f"root object '{root_obj.name}' has duplicated G{geom_idx}")
            if not skip_checks:
                MeshExporter._check_obj_transform(geom_obj)

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
                if not skip_checks:
                    MeshExporter._check_obj_transform(lod_obj)
                mesh_lods[lod_idx] = lod_obj
            for _, lod_obj in sorted(mesh_lods.items()):
                if lod_obj.data is None:
                    raise ExportException(f"lod '{lod_obj.name}' has no mesh data!")
                lods.append(lod_obj)

        return geoms

    def _export_mesh_lod(self, bf2_lod, lod_obj):
        # must get rig before modifiers are applied
        rig = find_rig_attached_to_object(lod_obj)

        if self.apply_modifiers:
            apply_modifiers(lod_obj)
        if self.triangulate:
            triangulate(lod_obj)

        mesh = lod_obj.data
        mesh_type = type(self.bf2_mesh)

        uv_count = 5 if mesh_type == BF2StaticMesh else 1

        animuv_matrix_index = mesh.attributes.get('animuv_matrix_index')
        animuv_rot_center = mesh.attributes.get('animuv_rot_center')
        if mesh_type != BF2BundledMesh: # just in case someone does this...
            animuv_matrix_index = None
            animuv_rot_center = None
        elif (animuv_matrix_index or animuv_rot_center) and not self._any_material_has_anim_uv(lod_obj):
            self.reporter.warning(f"{lod_obj.name}: has animated UV attributes but there's no material with 'AnimatedUV' technique defined")

        backface_attr = mesh.attributes.get('backface') if self.save_backfaces else None

        # generate tangent space
        if mesh_type == BF2StaticMesh and 'UV1' in mesh.uv_layers:
            tangent_uv_map = 'UV1'
        elif 'UV0' in mesh.uv_layers:
            tangent_uv_map = 'UV0'
        else:
            raise ExportException(f"'{mesh.name}': no valid UVs found to generate the tangent space!\n Make sure your UV maps are called correctly (UV0, UV1 etc..)")

        mesh.calc_tangents(uvmap=tangent_uv_map)

        # lightmap UV, if not present, generate it
        if mesh_type == BF2StaticMesh and 'UV4' not in mesh.uv_layers and self.gen_lightmap_uv:
            lightmap_uv_layer = mesh.uv_layers.new(name='UV4')
            lightmap_uv_layer.active = True
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
                self.reporter.warning(f"{lod_obj.name}: BF2 only supports a maximum of "
                                      f"{MAX_GEOM_LIMIT} geometry parts but got {bf2_lod.parts_num}")

        elif mesh_type == BF2SkinnedMesh:
            bone_to_matrix = dict()
            bone_to_id = dict()
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
            # check texture suffixes as well, wrong suffix can cause shading bugs especially for normal maps
            for txt_map_type, txt_map_file in texture_maps.items():
                filepath = txt_map_file.replace('\\', '/').lower()
                texture_maps[txt_map_type] = filepath

                if not texture_suffix_is_valid(filepath, txt_map_type):
                    self.reporter.warning(f"{txt_map_type} texture map '{filepath}' does not have valid suffix, expected '{get_texture_suffix(txt_map_type)}'")

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
                if mesh_type == BF2SkinnedMesh:
                    if blend_material.bf2_alpha_mode == 'ALPHA_TEST' and 'alpha_test' not in blend_material.bf2_technique.lower():
                        self.reporter.warning(f"{blend_material.name}: Material has Alpha Mode set to Alpha Test but 'Alpha_Test' hasn't been included in its technique")
                    if 'Normal' in texture_maps and file_name(texture_maps['Normal']).endswith('_b') and 'tangent' not in blend_material.bf2_technique.lower():
                        self.reporter.warning(f"{blend_material.name}: Material has tangent space normal map but 'tangent' hasn't been included in its technique")

                bf2_mat.technique = blend_material.bf2_technique
                if 'Diffuse' not in texture_maps:
                    raise ExportException(f"{blend_material.name}: Material is missing 'Diffuse' Texture map, check material settings!")
                bf2_mat.maps.append(texture_maps['Diffuse'])
                if 'Normal' in texture_maps:
                    bf2_mat.maps.append(texture_maps['Normal'])
                bf2_mat.maps.append(SPECULAR_LUT)
                if mesh_type == BF2BundledMesh and 'Wreck' in texture_maps:
                    bf2_mat.maps.append(texture_maps['Wreck'])
                # check required UVs are present
                if 0 not in uv_layers:
                    self.reporter.warning(f"{lod_obj.name}: Missing required UV layer 'UV0', make sure it exists and the name is correct")

            # animated UVs (lazy resolve)
            uv_ratio = None

            # rigs
            if mesh_type == BF2SkinnedMesh:
                bone_list = list() # bone names used for this material
                bf2_rig = bf2_lod.new_rig()

            # map each loop to vert index in vertex array
            loop_to_vert_idx = [-1] * len(mesh.loops)

            # merge stats
            merged_loops_count = 0
            total_loops_count = 0

            # create material's vertices
            this_material_vert_loops = filter(lambda x: x[0] in blend_vert_set, vert_loops.items())
            for vert_idx, loops in this_material_vert_loops: 
    
                unique_loops = dict() # loop_idx -> vertex
                merged_loops = dict() # loop_idx -> unique loop idx

                blend_vertex = mesh.vertices[vert_idx]
                for loop in loops:
                    vert = Vertex()

                    vert.position = swap_zy(blend_vertex.co)
                    vert.normal = swap_zy(loop.normal)
                    vert.tangent = swap_zy(loop.tangent)

                    # blendindices
                    blendindices = [0, 0, 0, 0]
                    # - (BundledMesh) first one is geom part index, second one unused
                    # - (SkinnedMesh) first and second one are bone indices
                    # - (StaticMesh)  both first and second one are unused
                    if mesh_type == BF2BundledMesh:
                        if len(blend_vertex.groups) > 1:
                            raise ExportException(f"{lod_obj.name}: Found vertex assigned to more than one vertex group! BF2 BundledMesh only supports one bone per vertex")
                        elif len(blend_vertex.groups) > 0:
                            vert_group = blend_vertex.groups[0].group
                            blendindices[0] = vertex_group_to_part_id[vert_group]
                    elif mesh_type == BF2SkinnedMesh:
                        if len(blend_vertex.groups) > 2:
                            raise ExportException(f"{lod_obj.name}: Found vertex assigned to more than two vertex groups (bones)!, BF2 SkinnedMesh only supports two bones per vertex")
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
                            uv = flip_uv(uvlayer.data[loop.index].uv)
                        else:
                            uv = (0, 0)
                        setattr(vert, f'texcoord{uv_chan}', uv)

                    # animated UVs
                    if self.has_animated_uvs:
                        vert.texcoord1 = (0, 0)
                        if animuv_rot_center and blendindices[3] in ANIM_UV_ROTATION_MATRICES:
                            if uv_ratio is None:
                                try:
                                    uv_ratio = _get_anim_uv_ratio(texture_maps['Diffuse'], self.texture_paths)
                                except (ValueError, FileNotFoundError) as e:
                                    raise ExportException(f"{lod_obj.name} (mat: {blend_material.name}): Cannot determine texture size ratio due to error: {e}")

                            # take the original UV and substract rotation center
                            # scale by texture size ratio, move to TEXCOORD1
                            # keeping only the center of rotation in TEXCOORD0
                            uv = vert.texcoord0
                            vert_animuv_center = animuv_rot_center.data[vert_idx].vector
                            vert.texcoord1 = ((uv[0] - vert_animuv_center[0]) / uv_ratio[0],
                                            (uv[1] - vert_animuv_center[1]) / uv_ratio[1])
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
                face_verts = invert_face(loop_to_vert_idx[face.loop_start:face.loop_start + face.loop_total])
                bf2_mat.faces.append(face_verts)
                if backface_attr and backface_attr.data[face.index].value:
                    bf2_mat.faces.append(invert_face(face_verts))

            # print stats
            if _DEBUG:
                stats = f'{lod_obj.name}_material{bf2_lod.materials.index(bf2_mat)}:'
                stats += f'\n\tmerged loops: {merged_loops_count}/{total_loops_count}'
                stats += f'\n\tvertices: {len(bf2_mat.vertices)}'
                stats += f'\n\tduplicated vertices: {len(bf2_mat.vertices) - len(blend_vert_set)}'
                stats += f'\n\tfaces: {len(bf2_mat.faces)}'
                print(stats)

            if mesh_type == BF2SkinnedMesh:
                if not bone_list:
                    self.reporter.info(f"{lod_obj.name}: Material '{blend_material.name}' has no weights assigned")
                if len(bone_list) > MAX_BONE_LIMIT:
                    self.reporter.warning(f"{lod_obj.name}: BF2 only supports a maximum of {MAX_BONE_LIMIT} bones per material,"
                                          f" but material '{blend_material.name}' has got {len(bone_list)} bones (vertex groups) assigned!")
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
            this_uv = getattr(this, uv_attr)
            other_uv = getattr(other, uv_attr)
            if any([abs(this_uv[i] - other_uv[i]) > 0.0001 for i in (0, 1)]):
                return False
        return True

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

def _get_anim_uv_ratio(texture_map_file, texture_paths):
    u_ratio = 1.0
    v_ratio = 1.0
    for texture_path in texture_paths:
        texture_map_file = os.path.join(texture_path, texture_map_file)
        if os.path.isfile(texture_map_file):
            texture_size = _get_texture_size(texture_map_file)
            tex_height, tex_width = texture_size
            if tex_width > tex_height:
                u_ratio = tex_height / tex_width
            elif tex_height > tex_width:
                v_ratio = tex_width / tex_height
            break
    return u_ratio, v_ratio

def _make_rest_tangent_space_node(uv_map='UV0'):
    name = 'RestPoseTangentSpace_' + 'UV0'

    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    node_tree = bpy.data.node_groups.new(type='GeometryNodeTree', name=name)
    node_tree.is_modifier = True

    node_tree.description = "Preserves tangent space for shading, must be placed BEFORE 'Armature' modifier"
    node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')

    group_input = node_tree.nodes.new("NodeGroupInput")
    group_output = node_tree.nodes.new("NodeGroupOutput")

    uv_tangent = node_tree.nodes.new("GeometryNodeUVTangent")
    uv_tangent.name = "UV Tangent"

    uv_attr = node_tree.nodes.new("GeometryNodeInputNamedAttribute")
    uv_attr.data_type = 'FLOAT_VECTOR'
    uv_attr.inputs['Name'].default_value = uv_map

    store_tangent = node_tree.nodes.new("GeometryNodeStoreNamedAttribute")
    store_tangent.data_type = 'FLOAT_VECTOR'
    store_tangent.domain = 'POINT'
    store_tangent.inputs[2].default_value = "rest_tangent"

    normal = node_tree.nodes.new("GeometryNodeInputNormal")

    store_normal = node_tree.nodes.new("GeometryNodeStoreNamedAttribute")
    store_normal.data_type = 'FLOAT_VECTOR'
    store_normal.domain = 'POINT'
    store_normal.inputs[2].default_value = "rest_normal"

    node_tree.links.new(
        uv_attr.outputs['Attribute'],
        uv_tangent.inputs['UV']
    )
    node_tree.links.new(
        store_tangent.outputs['Geometry'],
        group_output.inputs['Geometry']
    )
    node_tree.links.new(
        uv_tangent.outputs['Tangent'],
        store_tangent.inputs['Value']
    )
    node_tree.links.new(
        group_input.outputs['Geometry'],
        store_normal.inputs['Geometry']
    )
    node_tree.links.new(
        store_normal.outputs['Geometry'],
        store_tangent.inputs['Geometry']
    )
    node_tree.links.new(
        normal.outputs['Normal'],
        store_normal.inputs['Value']
    )

    return node_tree
