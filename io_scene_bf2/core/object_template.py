import bpy # type: ignore
import os
import math

from getpass import getuser
from mathutils import Matrix, Vector, Euler # type: ignore
from bpy.types import Mesh, Armature # type: ignore

from .bf2.bf2_engine import (BF2Engine, ObjectTemplate,
                             GeometryTemplate, CollisionMeshTemplate)
from .bf2.bf2_collmesh import NATIVE_BSP_EXPORT
from .bf2.bf2_mesh import BF2Samples
from .mesh import MeshImporter, MeshExporter
from .collision_mesh import CollMeshImporter, CollMeshExporter
from .skeleton import find_all_skeletons, find_rig_attached_to_object

from .utils import (delete_object, check_suffix,
                    check_prefix, swap_zy,
                    apply_modifiers as _apply_modifiers,
                    triangulate as _triangulate,
                    DEFAULT_REPORTER)
from .exceptions import ImportException, ExportException

NONVIS_PRFX = 'NONVIS_'
COL_SUFFIX = '_COL'
ANCHOR_PREFIX = 'ANCHOR__'

################################
########## IMPORT ##############
################################

class GeomPartInfo:
    def __init__(self, part_id, obj) -> None:
        self.part_id = part_id
        self.name = _strip_prefix(obj.name)
        self.bf2_object_type = obj.bf2_object_type
        self.location = obj.location.copy()
        self.rotation_quaternion = obj.rotation_quaternion.copy()
        self.matrix_local = obj.matrix_local.copy()
        self.children = []

def import_object_template(context, con_filepath, import_collmesh=True,
                           import_rig_mode='AUTO', geom_to_ske_name=None, reload=False,
                           weld_verts=False, load_backfaces=True, reporter=DEFAULT_REPORTER, **kwargs):
    BF2Engine().shutdown() # clear previous state
    obj_template_manager = BF2Engine().get_manager(ObjectTemplate)
    geom_template_manager = BF2Engine().get_manager(GeometryTemplate)
    col_template_manager = BF2Engine().get_manager(CollisionMeshTemplate)

    BF2Engine().main_console.run_file(con_filepath, ignore_includes=True) # don't parse .tweak
    for object_template in obj_template_manager.templates.values():
        obj_template_manager.add_bundle_childs(object_template)

    root_template = None
    for object_template in obj_template_manager.templates.values():
        if object_template.parent is None:
            if root_template is None:
                root_template = object_template
            else:
                raise ImportException(f"{con_filepath}: found multiple root objects: {root_template.name}, {object_template.name}, which one to import?")
    if root_template is None:
        raise ImportException(f"{con_filepath}: root object not found!")

    if not root_template.geom:
        ImportException(f"The imported object '{root_template.name}' has no geometry set")

    _verify_template(root_template)

    geometry_template_name = root_template.geom.lower()
    if geometry_template_name not in geom_template_manager.templates:
        raise ImportException(f"Geometry '{collmesh_template_name}' is not defined")

    geometry_template = geom_template_manager.templates[geometry_template_name]

    collmesh_template = None
    if root_template.collmesh:
        collmesh_template_name = root_template.collmesh.lower()
        if collmesh_template_name not in col_template_manager.templates:
            raise ImportException(f"Collision mesh '{collmesh_template_name}' is not defined")
        collmesh_template = col_template_manager.templates[collmesh_template_name]

    con_dir = os.path.dirname(con_filepath)
    geometry_type = geometry_template.geometry_type
    geometry_filepath = os.path.join(con_dir, 'Meshes', f'{geometry_template.name}.{geometry_type.lower()}')

    # Skeleton import
    geom_to_ske = _get_geom_to_ske(root_template, geometry_type, import_rig_mode, geom_to_ske_name, reporter)

    importer = MeshImporter(context, geometry_filepath,
                            reload=reload,
                            geom_to_ske=geom_to_ske,
                            reporter=reporter,
                            load_backfaces=load_backfaces,
                            **kwargs)

    root_geometry_obj = importer.import_mesh(name=root_template.name)
    root_geometry_obj.name = f'{geometry_type}_{root_template.name}'

    coll_parts = None
    if collmesh_template and import_collmesh:
        collmesh_filepath = os.path.join(con_dir, 'Meshes', f'{collmesh_template.name}.collisionmesh')

        collmesh_importer = CollMeshImporter(collmesh_filepath, name=root_template.name, reload=reload)
        coll_parts, col_materials = collmesh_importer.import_collmesh()
        # name materials
        for col_material_idx, col_material_name in root_template.col_material_map.items():
            col_materials[col_material_idx].name = col_material_name

    for geom_obj in root_geometry_obj.children:
        for lod_obj in geom_obj.children:
            geom_idx, lod_idx = check_prefix(lod_obj.name, ('G', 'L'))
            if geometry_type != 'BundledMesh':
                geom_parts = {'mesh1': lod_obj} # XXX hack
            else:
                geom_parts = _split_mesh_by_vertex_groups(context, lod_obj)

            new_lod = _apply_obj_template_data_to_lod(context, root_template, geom_parts, coll_parts, geom_idx, lod_idx)
            new_lod.parent = geom_obj
            _fix_unassigned_parts(geom_obj, new_lod)
            _delete_hierarchy_if_has_no_meshes(new_lod)
            _cleanup_unused_materials(new_lod)
            if weld_verts:
                _weld_vers_recursive(new_lod)

    # create anchor
    if root_template.anchor_point:
        anchor_obj = bpy.data.objects.new(ANCHOR_PREFIX + root_template.name, None)
        anchor_obj.parent = root_geometry_obj
        anchor_obj.location = swap_zy(root_template.anchor_point)
        context.scene.collection.objects.link(anchor_obj)

    return root_geometry_obj

def parse_geom_type(mesh_obj):
    name_split = mesh_obj.name.split('_')
    gt = name_split[0].lower()
    obj_name = '_'.join(name_split[1:])
    if len(name_split) == 1 or gt not in GeometryTemplate.TYPES:
        raise ExportException(f"Root object '{mesh_obj.name}' object must be prefixed with a valid geometry type! e.g. 'StaticMesh_'")
    geometry_type = GeometryTemplate.TYPES[gt]
    return geometry_type, obj_name

def parse_geom_type_safe(mesh_obj):
    try:
        return parse_geom_type(mesh_obj)
    except Exception:
        return None

def _delete_hierarchy_if_has_no_meshes(obj, parent_bones=None):
    if parent_bones is None: parent_bones = set()

    parent_bones.update(obj.vertex_groups.keys())
    if not _object_hierarchy_has_any_meshes(obj, parent_bones):
        delete_object(obj, recursive=True)
    else:
        for child_obj in obj.children:
            _delete_hierarchy_if_has_no_meshes(child_obj, parent_bones)

def _fix_unassigned_parts(geom_obj, lod_obj):
    # parts unassigned to any object template (e.g. GenericFirearm) 
    # will be parented to geom, so just add numeric suffix
    # and reparent them to LOD
    i = 1
    for child in geom_obj.children:
        if child.name.startswith(lod_obj.name) and child.name != lod_obj.name:
            child.parent = lod_obj
            n = lod_obj.name + f'_{i}'
            child.name = n
            child.data.name = n
            child.bf2_object_type = ''
            i += 1

def _apply_obj_template_data_to_lod(context, root_template, geom_parts, coll_parts, geom, lod):
    prfx = MeshImporter.build_mesh_prefix(geom, lod)
    add_col = coll_parts and lod == 0 # Add colistion only for LOD 0

    skinned_objects = dict()

    def _fix_geom_parts(obj_template, geom_parent=None, position=(0, 0, 0), rotation=(0, 0, 0)):
        geom_part_id = obj_template.geom_part
        vertex_group_name = f'mesh{geom_part_id + 1}'
        part_name = f'{prfx}{obj_template.name}'
        part_position = Vector(swap_zy(position))
        part_rotation = _yaw_pitch_roll_to_matrix(rotation).to_euler('XYZ')

        if vertex_group_name in geom_parts:
            geometry_part_obj = geom_parts[vertex_group_name]

            if vertex_group_name in geometry_part_obj.vertex_groups.keys():
                # this geom part shares some faces with another geom part
                # so this is a possibly a bone of another part
                geometry_part_vg = geometry_part_obj.vertex_groups[vertex_group_name]

                if not _has_obj_in_hierarchy_up(geom_parent, search_obj=geometry_part_obj):
                    # this is root object that has been weighted to bones (other vertex_groups)
                    geometry_part_obj.name = part_name
                    geometry_part_obj.data.name = part_name
                    # delete the group
                    geometry_part_obj.vertex_groups.remove(geometry_part_vg)
                else:
                    # this is a bone, create new dummy for it, it will not hold visible mesh data
                    # the root object will instead (to keep faces intact!)
                    # need this dummy for two things: holding object type and collmesh
                    if geometry_part_obj.name not in skinned_objects:
                        skinned_objects[geometry_part_obj.name] = (geometry_part_obj, list())
                    _, bones = skinned_objects[geometry_part_obj.name]

                    # but first transform verts of the root object
                    transform = part_rotation.to_matrix()
                    transform.resize_4x4()
                    transform.translation = part_position

                    # it might happen that direct parent (geom_parent) does not have mesh with this vertex group
                    # in this case we need to apply transforms of all parents to be relative to geometry_part_obj
                    parents_to_root = list()
                    _get_parent_list(geom_parent, geometry_part_obj, parents_to_root)
                    for parent in parents_to_root:
                        # for whatever reason using parent.matrix_local does not work correctly sometimes
                        parent_transform = parent.rotation_euler.copy().to_matrix()
                        parent_transform.resize_4x4()
                        parent_transform.translation = parent.location
                        transform @= parent_transform

                    _transform_verts(geometry_part_obj, vertex_group_name, transform)

                    # next override geometry_part_obj with a dummy
                    dummy_mesh = bpy.data.meshes.new(part_name)
                    geometry_part_obj = bpy.data.objects.new(part_name, dummy_mesh)
                    context.scene.collection.objects.link(geometry_part_obj)

                    # add to set of bones
                    bones.append((geometry_part_obj, transform))

                    geometry_part_vg.name = part_name 
            else:
                # normal case, all vertices for all faces have the same part id
                geometry_part_obj.name = part_name
                geometry_part_obj.data.name = part_name
        else:
            # might happen that some lod does not have geometry for some parts
            # but this part's children do, so we gotta create a dummy parent for them
            dummy_mesh = bpy.data.meshes.new(part_name)
            geometry_part_obj = bpy.data.objects.new(part_name, dummy_mesh)
            context.scene.collection.objects.link(geometry_part_obj)

        geometry_part_obj.rotation_euler = part_rotation
        geometry_part_obj.location = part_position
        geometry_part_obj.parent = geom_parent
        geometry_part_obj.bf2_object_type = obj_template.type # custom property
        try:
            geometry_part_obj.bf2_object_type_enum = obj_template.type
            geometry_part_obj.bf2_object_type_manual_mode = False
        except TypeError:
            geometry_part_obj.bf2_object_type_manual_mode = True

        if obj_template.has_collision_physics and add_col:
            col_part_id = obj_template.col_part
            col_dummy = bpy.data.objects.new(f'{NONVIS_PRFX}{prfx}{obj_template.name}', None)
            context.scene.collection.objects.link(col_dummy)
            col_dummy.parent = geometry_part_obj
            for col_id, col_mesh in coll_parts[col_part_id][geom].items():
                col_name = f'{part_name}{COL_SUFFIX}{col_id}'
                collmesh_obj = bpy.data.objects.new(col_name, col_mesh)
                col_mesh.name = col_name
                collmesh_obj.parent = col_dummy
                context.scene.collection.objects.link(collmesh_obj)

        for child in obj_template.children:
            _fix_geom_parts(child.template, geometry_part_obj, child.position, child.rotation)

        return geometry_part_obj

    return _fix_geom_parts(root_template)

def _transform_verts(geometry_part_obj, vertex_group, transform):
    bpy.ops.object.mode_set(mode='OBJECT')
    vg_idx = -1
    for v_group in geometry_part_obj.vertex_groups:
        if v_group.name == vertex_group:
            vg_idx = v_group.index
            break

    mesh = geometry_part_obj.data
    # save normals to re-apply them later on
    # changing vert coords fucks them all up...
    loop_normals = list()
    for loop in mesh.loops:
        loop_normals.append(tuple(loop.normal))

    for vert in mesh.vertices:
        for vg in vert.groups:
            if vg.group == vg_idx:
                vert.co = transform @ vert.co
                break

    mesh.normals_split_custom_set(loop_normals)

def _has_obj_in_hierarchy_up(obj, search_obj):
    if obj is None:
        return False
    if obj.name == search_obj.name:
        return obj
    return _has_obj_in_hierarchy_up(obj.parent, search_obj)

def _get_parent_list(obj, stop_at, parent_list):
    if obj is None:
        return parent_list
    if obj.name == stop_at.name:
        return parent_list
    parent_list.append(obj)
    return _get_parent_list(obj.parent, stop_at, parent_list)

def _delete_material(mesh, mat_to_del):
    for mat_idx, mat in enumerate(mesh.materials):
        if mat.name == mat_to_del.name:
            mesh.materials.pop(index=mat_idx)
            return

def _cleanup_unused_materials(obj):
    if obj.data and isinstance(obj.data, Mesh):
        mesh = obj.data
        used_material_indexes = set()
        for poly in mesh.polygons:
            used_material_indexes.add(poly.material_index)
        unused_materials = list()
        for mat_idx, mat in enumerate(mesh.materials):
            if mat_idx not in used_material_indexes:
                unused_materials.append(mat)
        for mat in unused_materials:
            _delete_material(mesh, mat)

    for child_obj in obj.children:
        _cleanup_unused_materials(child_obj)

def _find_unsplittable_groups(mesh_obj):
    unsplittable_groups = set()

    for poly in mesh_obj.data.polygons:
        poly_groups = set()
        for vertex_index in poly.vertices:
            vertex = mesh_obj.data.vertices[vertex_index]
            vert_group = vertex.groups[0].group
            poly_groups.add(vert_group)
            if len(poly_groups) != 1:
                unsplittable_groups.update(poly_groups)
    return unsplittable_groups

def _split_mesh_by_vertex_groups(context, mesh_obj):
    splitted_parts = dict()
    not_splitted_parts = set()

    unsplittable_groups = _find_unsplittable_groups(mesh_obj)
    context.view_layer.objects.active = mesh_obj
    for v_group in mesh_obj.vertex_groups:
        if v_group.index in unsplittable_groups:
            not_splitted_parts.add(v_group.name)
            continue

        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.vertex_group_set_active(group=v_group.name)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.vertex_group_select()
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')

        for o in context.selected_objects:
            if o.name == mesh_obj.name:
                continue
            new_name = f'{mesh_obj.name}_{v_group.name}'
            o.name = new_name
            o.data.name = new_name
            o.vertex_groups.clear()
            splitted_parts[v_group.name] = o
            break

    # delete object if no unasigned verts left after splitting
    if mesh_obj.data is None or len(mesh_obj.data.vertices) == 0:
        delete_object(mesh_obj)
        return splitted_parts

    # assing one remaining object to unsplittable groups
    for v_group_name in not_splitted_parts:
        splitted_parts[v_group_name] = mesh_obj
    
    # remove groups from the object that were split (don't have verts)
    vgs_assigned = list()
    for vg in mesh_obj.vertex_groups:
        if vg.name not in not_splitted_parts:
            vgs_assigned.append(vg)
    for vg in vgs_assigned:
        mesh_obj.vertex_groups.remove(vg)

    # rename the object (this avoids duplicating object names later)
    mesh_obj.name = mesh_obj.name + "_UNSPLITABLE"
    mesh_obj.data.name = mesh_obj.name + "_UNSPLITABLE"

    return splitted_parts

def _object_hierarchy_has_any_meshes(obj, parent_bones):
    if obj.data and isinstance(obj.data, Mesh) and len(obj.data.vertices):
        return True
    if obj.name in parent_bones:
        # empty object but refers to parent vertex group, keep this
        return True
    if obj.data and isinstance(obj.data, Armature):
        return True # skin, keep this

    for child_obj in obj.children:
        return _object_hierarchy_has_any_meshes(child_obj, parent_bones)
    return False

def _weld_vers_recursive(obj):
    if obj.data and isinstance(obj.data, Mesh):
        _weld_verts(obj)
    else:
        for child_obj in obj.children:
            _weld_vers_recursive(child_obj)

def _weld_verts(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')

def _yaw_pitch_roll_to_matrix(rotation):
    rotation = tuple(map(lambda x: -math.radians(x), rotation))
    yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
    pitch = Matrix.Rotation(rotation[1], 4, 'X')
    roll  = Matrix.Rotation(rotation[2], 4, 'Y')
    return (yaw @ pitch @ roll)

def _get_geom_to_ske(root_template, geometry_type, import_rig_mode, geom_to_ske_name=None, reporter=DEFAULT_REPORTER):
    if import_rig_mode == 'OFF':
        return None
    else:
        geom_to_ske = dict()
        rigs = dict()
        for s in find_all_skeletons():
            rigs[s.name] = s

        def put_rig_safe(geom_idx, ske_name):
            rig = rigs.get(ske_name)
            if rig is None:
                reporter.warning(f"Armature '{ske_name}' not found for ObjectTemplate type '{root_template.type}'")
            geom_to_ske[geom_idx] = rig

        if import_rig_mode == 'AUTO':
            if geometry_type == 'SkinnedMesh':
                if root_template.type.lower() == 'soldier':
                    put_rig_safe(0, '1p_setup')
                    put_rig_safe(1, '3p_setup')
                elif 'kits' in root_template.name.lower(): # actually hardcoded in engine
                    put_rig_safe(-1, '3p_setup')
                elif root_template.type.lower() == 'animatedbundle':
                    if rigs:
                        geom_to_ske[-1] = list(rigs.values())[0]
                    else:
                        reporter.warning(f"Armature '{ske_name}' not found for ObjectTemplate type 'AnimatedBundle'")
                        geom_to_ske = None
            elif geometry_type == 'BundledMesh':
                if root_template.type.lower() == 'genericfirearm':
                    put_rig_safe(0, '1p_setup')
                    put_rig_safe(1, '3p_setup')
                else:
                    geom_to_ske = None
        elif import_rig_mode == 'MANUAL':
            if geom_to_ske_name is None:
                raise ImportException(f'geom_to_ske_name missing for MANUAL mode')
            for geom_idx, ske_name in geom_to_ske_name.items():
                geom_to_ske[geom_idx] = rigs[ske_name]
        else:
            raise ImportException(f'Unhandled import_rig_mode {import_rig_mode}')
        return geom_to_ske

def _verify_template(root_obj_template):
    part_id_to_obj_template = dict()
    def _check_geom_part_unique(obj_template):
        if obj_template.geom_part in part_id_to_obj_template:
            raise ImportException(f"'{obj_template.name}' has the same ObjectTemplate.geometryPart index as '{part_id_to_obj_template[obj_template.geom_part].name}'")
        part_id_to_obj_template[obj_template.geom_part] = obj_template
        for child in obj_template.children:
            _check_geom_part_unique(child.template)
    _check_geom_part_unique(root_obj_template)


################################
########## EXPORT ##############
################################

TMP_PREFIX = 'TMP__' # prefix for temporary object copy

def export_object_template(mesh_obj, con_file, geom_export=True, colmesh_export=True,
                           apply_modifiers=False, samples_size=None, sample_padding=6,
                           use_edge_margin=True, save_backfaces=True, reporter=DEFAULT_REPORTER, **kwargs):
    geometry_type, obj_name = parse_geom_type(mesh_obj)

    # find anchor
    anchor_obj = None
    for child in mesh_obj.children:
        if child.name.startswith(ANCHOR_PREFIX):
            anchor_obj = child
            break

    # temporarily remove parent to not be taken as geom
    if anchor_obj:
        anchor_obj.parent = None

    try:
        mesh_geoms = MeshExporter.collect_geoms_lods(mesh_obj)
    except Exception:
        raise
    finally:
        if anchor_obj:
            anchor_obj.parent = mesh_obj

    obj_to_geom_part = _find_geom_parts(mesh_geoms)

    for obj_name, geom_part in obj_to_geom_part.items():
        if geom_part.part_id == 0:
            root_geom_part = geom_part
            break

    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            _verify_lods_consistency(root_geom_part, lod_obj)

    collmesh_parts, obj_to_col_part_id = _find_collmeshes(mesh_geoms)

    root_obj_template = _create_object_template(root_geom_part, obj_to_geom_part, obj_to_col_part_id)
    if root_obj_template is None:
        raise ExportException(f"root object '{root_geom_part.name}' is missing ObjectTemplate type, check object properties!")
    root_obj_template.save_in_separate_file = True
    root_obj_template.creator_name = getuser()
    root_obj_template.geom = GeometryTemplate(geometry_type, obj_name)
    if root_obj_template.has_collision_physics:
        root_obj_template.collmesh = CollisionMeshTemplate(obj_name)

    con_dir = os.path.dirname(con_file)
    if geom_export or colmesh_export:
        os.makedirs(os.path.join(con_dir, 'Meshes'), exist_ok=True)

    geometry_filepath = os.path.join(con_dir, 'Meshes', f'{root_obj_template.geom.name}.{geometry_type.lower()}')

    # create temporary meshes for export, that we can modify e.g trigangulate
    print(f"duplicating LODs...")
    temp_mesh_geoms = _duplicate_lods(mesh_geoms)
    try:
        if geometry_type == 'BundledMesh':
            print(f"joining LODs...")
            _join_lods(temp_mesh_geoms, obj_to_geom_part)

            root_obj_template.geom.nr_of_animated_uv_matrix = _get_nr_of_animted_uvs(temp_mesh_geoms)

        for geom_obj in temp_mesh_geoms:
            for lod_obj in geom_obj:
                if apply_modifiers:
                    rig = find_rig_attached_to_object(lod_obj)
                    _apply_modifiers(lod_obj)
                    if rig:
                        modifier = lod_obj.modifiers.new(type='ARMATURE', name="Armature")
                        modifier.object = rig
                _triangulate(lod_obj)

        if geom_export:
            print(f"Exporting geometry to '{geometry_filepath}'")
            bf2_mesh = MeshExporter(mesh_obj, geometry_filepath,
                                    mesh_geoms=temp_mesh_geoms,
                                    mesh_type=geometry_type,
                                    reporter=reporter,
                                    save_backfaces=save_backfaces,
                                    **kwargs).export_mesh()

            if samples_size is not None and geometry_type == 'StaticMesh':
                if len(bf2_mesh.geoms) != 1:
                    reporter.error("Cannot generate samples for meshes with more than one Geom")
                elif not bf2_mesh.has_uv(4):
                    reporter.error(f"Cannot generate samples, missing ligtmap UV Layer (UV4)")
                else:
                    for lod_idx, bf2_lod in enumerate(bf2_mesh.geoms[0].lods):
                        MIN_SAMPLE_SIZE = 8
                        if lod_idx == 0:
                            sample_size = samples_size
                            samples_filename = obj_name + '.samples'
                        else:
                            sample_size = [max(int(i / (2**lod_idx)), MIN_SAMPLE_SIZE) for i in samples_size]
                            samples_filename = obj_name + f'.samp_{lod_idx:02d}'

                        samples = BF2Samples(bf2_lod, size=sample_size, sample_padding=sample_padding,
                                             use_edge_margin=use_edge_margin, uv_chan=4)

                        samples_filepath = os.path.join(os.path.dirname(geometry_filepath), samples_filename)
                        print(f"Exporting samples to '{samples_filepath}'")
                        samples.export(samples_filepath)

    except Exception:
        raise
    finally:
        _delete_lods(temp_mesh_geoms)

    if root_obj_template.collmesh and colmesh_export:
        collmesh_filepath = os.path.join(con_dir, 'Meshes', f'{root_obj_template.collmesh.name}.collisionmesh')

        print(f"duplicating COLs...")
        temp_collmesh_parts = _duplicate_cols(collmesh_parts)

        for geoms in temp_collmesh_parts:
            for cols in geoms:
                for _, col_obj in cols.items():
                    if apply_modifiers:
                        _apply_modifiers(col_obj)
                    _triangulate(col_obj)
        try:
            print(f"Exporting collision to '{collmesh_filepath}'")
            collmesh_exporter = CollMeshExporter(mesh_obj, collmesh_filepath, geom_parts=temp_collmesh_parts)
            collmesh_exporter.export_collmesh()
            material_to_index = collmesh_exporter.material_to_index
        except Exception:
            raise
        finally:
            _delete_cols(temp_collmesh_parts)

        for mat, mat_idx in sorted(material_to_index.items(), key=lambda item: item[1]):
            if ' ' in mat:
                # XXX: add quoting when dumping con to allow this
                raise ExportException(f"CollisionMesh material: '{mat}' must not contain whitespaces!")
            root_obj_template.col_material_map[mat_idx] = mat

    if anchor_obj:
        root_obj_template.anchor_point = swap_zy(anchor_obj.location)

    print(f"Writing con file to '{con_file}'")
    _dump_con_file(root_obj_template, con_file)


def _find_geom_parts(mesh_geoms):
    obj_to_part = dict()
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            _collect_geometry_parts(lod_obj, obj_to_part)
    return obj_to_part

def _collect_geometry_parts(obj, obj_to_part):
    object_name = _strip_prefix(obj.name)
    geom_part = obj_to_part.get(object_name)
    if geom_part is None:
        part_id = len(obj_to_part)
        geom_part = GeomPartInfo(part_id, obj)
        obj_to_part[object_name] = geom_part        

    for _, child_obj in sorted([(_strip_prefix(child.name), child) for child in obj.children]):
        if not _is_colmesh_dummy(child_obj):
            child_geom_part = _collect_geometry_parts(child_obj, obj_to_part)
            if child_geom_part not in geom_part.children:
                geom_part.children.append(child_geom_part)
    return geom_part

def _find_collmeshes(mesh_geoms):
    collmesh_parts_per_geom = list()
    obj_to_part_id = dict()

    for geom_obj in mesh_geoms:
        parts = list()
        lod0 = geom_obj[0] # only lod0 might have collmesh
        _collect_collmesh_parts(lod0, parts, obj_to_part_id)
        collmesh_parts_per_geom.append(parts)

    collmesh_parts = list() # part id -> geoms -> colmeshes
    for col_part_idx in sorted(obj_to_part_id.values()):
        col_geoms = list()
        for geom_col_parts in collmesh_parts_per_geom:
            if len(geom_col_parts) > col_part_idx:
                col_geoms.append(geom_col_parts[col_part_idx])
            else:
                col_geoms.append(dict()) # no cols for this geom
        collmesh_parts.append(col_geoms)

    # for node_idx, node in enumerate(collmesh_parts):
    #     print(f"node-{node_idx}")
    #     for geom_idx, geom in enumerate(node):
    #         print(f"   geom-{geom_idx}")
    #         for col_idx, col in geom.items():
    #             print(f"      col-{col_idx}", col)

    return collmesh_parts, obj_to_part_id

def _collect_collmesh_parts(obj, collmesh_parts, obj_to_part_id):
    # find and add collmeshes first
    for child_obj in obj.children:
        if _is_colmesh_dummy(child_obj):
            # map object template name to collistion part
            part_id = len(collmesh_parts)
            object_name = _strip_prefix(obj.name)
            obj_to_part_id[object_name] = part_id
            # map collision part to collision meshes
            cols = dict()
            collmesh_parts.append(cols)
            for col_obj in child_obj.children:
                col_idx = check_suffix(col_obj.name, COL_SUFFIX)
                cols[col_idx] = col_obj
            break

    # process childs
    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _collect_collmesh_parts(child_obj, collmesh_parts, obj_to_part_id)
    return collmesh_parts

def _is_colmesh_dummy(obj):
    return obj.name.lower().startswith(NONVIS_PRFX.lower())

def _verify_lods_consistency(root_geom_part, lod_obj):
    lod_name = _strip_prefix(lod_obj.name)

    if any([c.isspace() for c in lod_obj.name]):
        raise ExportException(f"'{lod_obj.name}' name contain spaces!")

    if tuple(lod_obj.scale) != (1, 1, 1):
        raise ExportException(f"'{lod_obj.name}' has non uniform scale: {lod_obj.scale}")

    if lod_obj.data is None:
        raise ExportException(f"'{lod_obj.name}' has no mesh data! If you don't want it to contain any, simply make it a mesh object and delete all vertices")

    def _inconsistency(item, val, exp_val):
        raise ExportException(f"{lod_obj.name}: Inconsistent {item} for different Geoms/LODs, got '{val}' but other Geom/LOD has '{exp_val}'")

    if lod_name != root_geom_part.name:
        _inconsistency('object names', lod_obj.name, root_geom_part.name)
    if lod_obj.bf2_object_type != root_geom_part.bf2_object_type:
        _inconsistency('BF2 Object Types', lod_obj.bf2_object_type, root_geom_part.bf2_object_type)
    if (root_geom_part.location - lod_obj.location).length > 0.0001:
        _inconsistency('object locations', lod_obj.location, root_geom_part.location)
    if root_geom_part.rotation_quaternion.rotation_difference(lod_obj.rotation_quaternion).angle > 0.0001:
        _inconsistency('object rotations', lod_obj.rotation_quaternion, root_geom_part.rotation_quaternion)

    root_geom_children = dict()
    for child_geom_part in root_geom_part.children:
        root_geom_children[child_geom_part.name] = child_geom_part

    for child_obj in lod_obj.children:
        child_name = _strip_prefix(child_obj.name)
        if _is_colmesh_dummy(child_obj):
            continue
        if child_name not in root_geom_children:
            raise ExportException(f"Unexpected object '{child_obj.name}' found, hierarchy does not match with other LOD(s)")

        geom_part_child = root_geom_children[child_name]
        _verify_lods_consistency(geom_part_child, child_obj)

def _create_object_template(root_geom_part, obj_to_geom_part, obj_to_col_part_id, is_vehicle=None) -> ObjectTemplate:
    if root_geom_part.bf2_object_type == '': # special case, geom part which has no object template (see GenericFirearm)
        return None

    obj_name = root_geom_part.name
    obj_template = ObjectTemplate(root_geom_part.bf2_object_type, obj_name)

    if is_vehicle is None: # root object
        # TODO: no idea how to properly detect whether the exported object
        # should or should not have mobile physics
        is_vehicle = obj_template.type.lower() == 'PlayerControlObject'.lower()

    obj_template.has_mobile_physics = is_vehicle

    if obj_name in obj_to_col_part_id:
        obj_template.physics_type = ObjectTemplate._PhysicsType.MESH
        obj_template.has_collision_physics = True
        obj_template.col_part = obj_to_col_part_id[obj_name]

    if obj_name in obj_to_geom_part:
        obj_template.geom_part = obj_to_geom_part[obj_name].part_id

    for _, child_obj in sorted([(child.name, child) for child in root_geom_part.children]):
        if _is_colmesh_dummy(child_obj): # skip collmeshes
            continue
        child_template = _create_object_template(child_obj, obj_to_geom_part, obj_to_col_part_id, is_vehicle)
        if child_template is None:
            continue
        child_object = ObjectTemplate.ChildObject(child_template.name)
        child_object.template = child_template
        child_object.position = swap_zy(child_obj.location)
        child_object.rotation = _matrix_to_yaw_pitch_roll(child_obj.matrix_local)
        obj_template.children.append(child_object)

    return obj_template

def _strip_prefix(s):
    for char_idx, _ in enumerate(s):
        if s[char_idx:].startswith('__'):
            return s[char_idx+2:]
    raise ExportException(f"'{s}' has no GxLx__ prefix!")

def _strip_tmp_prefix(name):
    if name.startswith(TMP_PREFIX):
        return name[len(TMP_PREFIX):]
    return name

def _find_child(obj, child_name):
    org_obj_name = _strip_tmp_prefix(obj.name)
    if org_obj_name == child_name:
        return obj
    for child in obj.children:
        c = _find_child(child, child_name)
        if c: return c  
    return None

def _create_mesh_vertex_group(obj, obj_to_vertex_group):
    org_obj_name = _strip_tmp_prefix(obj.name)
    obj_name = _strip_prefix(org_obj_name)
    group_name = obj_to_vertex_group[obj_name]

    # reset object location
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)

    child_groups = set()
    for group in obj.vertex_groups:
        if group_name == group.name:
            raise ExportException(f"{org_obj_name}: '{group_name}' vertex group should not exist")
        # check if vertex group links to a child object
        child_obj = _find_child(obj, group.name)
        if not child_obj:
            raise ExportException(f"{org_obj_name}: has got a vertex group called '{group.name}', but such child object does not exist")

        parents_to_root = list()
        _get_parent_list(child_obj, obj, parents_to_root)

        transform = Matrix.Identity(4)
        for parent in parents_to_root:
            parent_transform = Euler(parent.rotation_euler, parent.rotation_mode).to_matrix()
            parent_transform.resize_4x4()
            parent_transform.translation = parent.location
            transform @= parent_transform
        transform.invert()

        _transform_verts(obj, group.name, transform)

        child_groups.add(group.index)
        child_name = _strip_prefix(group.name)
        child_group_name = obj_to_vertex_group[child_name]
        # rename this group to child group
        # after joining objects both groups will be merged into one
        # this is exactly what we want
        group.name = child_group_name

    # add main group
    obj.vertex_groups.new(name=group_name)
    for vertex in obj.data.vertices:
        if len(vertex.groups) > 1:
            raise ExportException(f"{org_obj_name} has vertex assigned to multiple vertex groups"
                                    f", this is not allowed! found groups: {vertex.groups.keys()}")
        if len(vertex.groups) and vertex.groups[0].group in child_groups:
            continue # this vert will  be "transfered" to child geom part
        obj.vertex_groups[group_name].add([vertex.index], 1.0, "REPLACE")

    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _create_mesh_vertex_group(child_obj, obj_to_vertex_group)

def _map_objects_to_vertex_groups(obj, obj_to_geom_part, obj_to_vertex_group):
    org_obj_name = _strip_tmp_prefix(obj.name)
    obj_name = _strip_prefix(org_obj_name)
    part_id = obj_to_geom_part[obj_name].part_id
    group_name = f'mesh{part_id + 1}'
    obj_to_vertex_group[obj_name] = group_name

    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _map_objects_to_vertex_groups(child_obj, obj_to_geom_part, obj_to_vertex_group)

def _select_all_geometry_parts(obj):
    obj.select_set(True)
    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _select_all_geometry_parts(child_obj)

def _join_lod_hierarchy_into_single_mesh(lod_obj, obj_to_geom_part):
    # first, assign one vertex group for each mesh which corresponds to geom part id
    obj_to_vertex_group = dict()
    _map_objects_to_vertex_groups(lod_obj, obj_to_geom_part, obj_to_vertex_group)
    _create_mesh_vertex_group(lod_obj, obj_to_vertex_group)

    # select all geom parts with meshes
    bpy.context.view_layer.objects.active = lod_obj
    bpy.ops.object.select_all(action='DESELECT')
    _select_all_geometry_parts(lod_obj)
    bpy.ops.object.join()

def _join_lods(mesh_geoms, obj_to_geom_part):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            _join_lod_hierarchy_into_single_mesh(lod_obj, obj_to_geom_part)

def _duplicate_object(obj, recursive=True, prefix=TMP_PREFIX):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    hide = obj.hide_get()
    obj.hide_set(False)
    obj.select_set(True)
    bpy.ops.object.duplicate()
    new_obj = bpy.context.view_layer.objects.active
    new_obj.name = prefix + obj.name
    obj.hide_set(hide)

    if recursive:
        for child_obj in obj.children:
            if _is_colmesh_dummy(child_obj):
                continue
            new_child = _duplicate_object(child_obj, recursive=recursive)
            new_child.parent = new_obj
    return new_obj

def _duplicate_cols(geom_parts):
    new_geom_parts = list()
    for geoms in geom_parts:
        new_geom_obj = list()
        new_geom_parts.append(new_geom_obj)
        for cols in geoms:
            new_cols = dict()
            new_geom_obj.append(new_cols)
            for col_idx, col_obj in cols.items():
                new_cols[col_idx] = _duplicate_object(col_obj, recursive=False)
    return new_geom_parts

def _duplicate_lods(mesh_geoms):
    new_mesh_geoms = list()
    for geom_obj in mesh_geoms:
        new_geom_obj = list()
        new_mesh_geoms.append(new_geom_obj)
        for lod_obj in geom_obj:
            new_lod_obj = _duplicate_object(lod_obj)
            new_geom_obj.append(new_lod_obj)
    return new_mesh_geoms

def _delete_cols(geom_parts):
    for geoms in geom_parts:
        for cols in geoms:
            for _, col_obj in cols.items():
                delete_object(col_obj, recursive=True)

def _delete_lods(mesh_geoms):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            delete_object(lod_obj, recursive=True)

def _get_nr_of_animted_uvs(mesh_geoms):
    matrix_set = set()
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            if 'animuv_matrix_index' in lod_obj.data.attributes:
                animuv_matrix_index = lod_obj.data.attributes['animuv_matrix_index']
                vert_matrix = len(animuv_matrix_index.data) * [None]
                animuv_matrix_index.data.foreach_get('value', vert_matrix)
                matrix_set.update(set(vert_matrix))
    if matrix_set:
        return max(matrix_set)
    else:
        return 0

def _dump_con_file(root_obj_template, con_file):
    with open(con_file, 'w') as f:
        root_obj_template.geom.make_script(f)
        if root_obj_template.collmesh:
            root_obj_template.collmesh.make_script(f)
        f.write('\n')
        root_obj_template.make_script(f)
        f.write(f'include {root_obj_template.name}.tweak')
        f.write('\n')

def _matrix_to_yaw_pitch_roll(m):
    yaw = math.atan2(m[0][1], m[1][1])
    pitch = math.asin(-m[2][1])
    roll = math.atan2(m[2][0], m[2][2])
    return tuple(map(math.degrees, (yaw, pitch, roll)))
