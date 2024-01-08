import bpy
import os
from getpass import getuser

from .bf2.bf2_engine.components import (BF2Engine, ObjectTemplate,
                                        GeometryTemplate, CollisionMeshTemplate)
from .mesh import (import_mesh, export_bundledmesh, export_staticmesh,
                   _build_mesh_prefix, _collect_geoms_lods, _get_vertex_group_to_part_id_mapping)
from .collision_mesh import import_collisionmesh, export_collisionmesh

from .utils import delete_object, check_suffix
from .exceptions import ImportException, ExportException

NONVIS_PRFX = 'NONVIS_'
COL_SUFFIX = '__COL'
TMP_PREFIX = 'TMP__'

def import_object(context, con_filepath, import_collmesh=False, reload=False, **kwargs):
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
                raise ImportException(f"{con_filepath}: found multiple root objects: {root_template}, {object_template}, which one to import?")
    if root_template is None:
        raise ImportException(f"{con_filepath}: root object not found!")

    if not root_template.geom:
        ImportException(f"The imported object '{root_template.name}' has no geometry set")
    
    geometry_template = geom_template_manager.templates[root_template.geom.lower()]

    collmesh_template = None
    if root_template.collmesh:
        collmesh_template = col_template_manager.templates[root_template.collmesh.lower()]

    con_dir = os.path.dirname(con_filepath)
    geometry_type = geometry_template.geometry_type
    geometry_filepath = os.path.join(con_dir, 'Meshes', f'{geometry_template.name}.{geometry_type.lower()}')

    root_geometry_obj = import_mesh(context, geometry_filepath, name=root_template.name, reload=reload, **kwargs)
    root_geometry_obj.name = f'{geometry_type}_{root_template.name}'

    if geometry_type == 'SkinnedMesh': # XXX
        return

    coll_parts = None
    if collmesh_template and import_collmesh:
        collmesh_filepath = os.path.join(con_dir, 'Meshes', f'{collmesh_template.name}.collisionmesh')
        coll_parts, col_materials = import_collisionmesh(context, collmesh_filepath, name=root_template.name, make_objects=False, reload=reload)
        # name materials
        for col_material_idx, col_material_name in root_template.col_material_map.items():
            col_materials[col_material_idx].name = col_material_name

    for geom_idx, geom_obj in enumerate(root_geometry_obj.children):
        for lod_idx, lod_obj in enumerate(geom_obj.children):
            if geometry_type == 'StaticMesh':
                geom_parts = {'mesh1': lod_obj} # XXX hack, no need to split staticmehes
            else:
                geom_parts = _split_mesh_by_vertex_groups(context, lod_obj)
            new_lod = _apply_mesh_data_to_lod(context, root_template, geom_parts, coll_parts, geom_idx, lod_idx)
            new_lod.parent = geom_obj
            _fix_unassigned_parts(geom_obj, new_lod)
            _delete_hierarchy_if_has_no_meshes(new_lod)
            _cleanup_unused_materials(new_lod)

def parse_geom_type(mesh_obj):
    name_split = mesh_obj.name.split('_')
    gt = name_split[0].lower()
    obj_name = '_'.join(name_split[1:])
    if len(name_split) == 1 or gt not in GeometryTemplate.TYPES:
        raise ExportException(f"Root object '{mesh_obj.name}' object must be prefixed with a valid geometry type! e.g. 'StaticMesh_'")
    geometry_type = GeometryTemplate.TYPES[gt]
    return geometry_type, obj_name

def export_object(mesh_obj, con_file, geom_export=True, colmesh_export=True,
                  apply_modifiers=False, triangluate=False, **kwargs):
    geometry_type, obj_name = parse_geom_type(mesh_obj)

    if tuple(mesh_obj.location) != (0, 0, 0) or tuple(mesh_obj.rotation_euler) != (0, 0, 0):
        raise ExportException(f"The root of the exported object '{mesh_obj.name}' must be placed in the scene origin, with no rotation")

    mesh_geoms = _collect_geoms_lods(mesh_obj)
    main_lod, obj_to_geom_part_id = _find_main_lod_and_geom_parts(mesh_geoms)

    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            _verify_lods_consistency(main_lod, lod_obj)

    collmesh_parts, obj_to_col_part_id = _find_collmeshes(mesh_geoms)

    root_obj_template = _create_object_template(main_lod, obj_to_geom_part_id, obj_to_col_part_id)
    root_obj_template.save_in_separate_file = True
    root_obj_template.creator_name = getuser()
    root_obj_template.geom = GeometryTemplate(geometry_type, obj_name)
    if root_obj_template.has_collision_physics:
        root_obj_template.collmesh = CollisionMeshTemplate(obj_name)

    con_dir = os.path.dirname(con_file)
    if geom_export or colmesh_export:
        os.makedirs(os.path.join(con_dir, 'Meshes'), exist_ok=True)

    geometry_filepath = os.path.join(con_dir, 'Meshes', f'{root_obj_template.geom.name}.{geometry_type.lower()}')

    export_func = None
    if geometry_type == 'BundledMesh':
        export_func = export_bundledmesh
    elif geometry_type == 'StaticMesh':
        export_func = export_staticmesh
    else:
        raise ExportException(f'{geometry_type} export not supported')

    # create temporary meshes for export, that we can modify e.g trigangulate
    print(f"duplicating LODs...")
    temp_mesh_geoms = _duplicate_lods(mesh_geoms)
    try:
        if geometry_type == 'BundledMesh':
            print(f"joining LODs...")
            _join_lods(temp_mesh_geoms, obj_to_geom_part_id)

        if apply_modifiers:
            _apply_modifiers(temp_mesh_geoms)

        if triangluate:
            _triangulate(temp_mesh_geoms)

        if geom_export:
            print(f"Exporting geometry to '{geometry_filepath}'")
            export_func(mesh_obj, geometry_filepath, mesh_geoms=temp_mesh_geoms, **kwargs)
    except Exception:
        raise
    finally:
        _delete_lods(temp_mesh_geoms)

    if root_obj_template.collmesh:
        collmesh_filepath = os.path.join(con_dir, 'Meshes', f'{root_obj_template.collmesh.name}.collisionmesh')
        if colmesh_export:
            print(f"Exporting collision to '{geometry_filepath}'")
            _, material_to_index = export_collisionmesh(mesh_obj, collmesh_filepath, geom_parts=collmesh_parts)
        for mat, mat_idx in sorted(material_to_index.items(), key=lambda item: item[1]):
            root_obj_template.col_material_map[mat_idx] = mat

    print(f"Writing con file to '{con_file}'")
    _dump_con_file(root_obj_template, con_file)


def _find_main_lod_and_geom_parts(mesh_geoms):
    main_lod = None
    main_obj_to_part_id = None
    parts_num = 0
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            geom_parts = list()
            obj_to_part_id = dict()
            _collect_geometry_parts(lod_obj, geom_parts, obj_to_part_id)
            lod_parts_num = len(geom_parts)
            if lod_parts_num > parts_num:
                parts_num = lod_parts_num
                main_lod = lod_obj
                main_obj_to_part_id = obj_to_part_id

    return main_lod, main_obj_to_part_id

def _collect_geometry_parts(obj, geom_parts, obj_to_part_id):
    part_id = len(geom_parts)
    object_name = _strip_prefix(obj.name)
    obj_to_part_id[object_name] = part_id
    geom_parts.append(obj)
    # process childs
    for _, child_obj in sorted([(child.name, child) for child in obj.children]):
        if not _is_colmesh_dummy(child_obj):
            _collect_geometry_parts(child_obj, geom_parts, obj_to_part_id)
    return geom_parts

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
            object_name = _strip_prefix(child_obj.name)
            obj_to_part_id[object_name] = part_id

            # map collision part to collision meshes
            cols = dict()
            collmesh_parts.append(cols)
            for col_obj in child_obj.children:
                col_idx = check_suffix(col_obj.name, COL_SUFFIX)
                cols[col_idx] = col_obj

    # process childs
    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _collect_collmesh_parts(child_obj, collmesh_parts, obj_to_part_id)
    return collmesh_parts

def _is_colmesh_dummy(obj):
    return obj.name.lower().startswith(NONVIS_PRFX.lower())

def _verify_lods_consistency(main_lod_obj, lod_obj):
    main_lod_name = _strip_prefix(main_lod_obj.name)
    lod_name = _strip_prefix(lod_obj.name)

    if any([c.isspace() for c in lod_obj.name]):
            raise ExportException(f"'{child_obj.name}' name contain spaces!")

    if lod_obj.data is None and len(lod_obj.children) == 0: # leaf with no meshes
        raise ExportException(f"Object '{child_obj.name}' has no mesh data")

    def _inconsistency(item, val, exp_val):
        raise ExportException(f"{lod_obj.name}: Inconsistent {item} for different LODs, got '{val}' but expected '{exp_val}'")

    if lod_name != main_lod_name:
        _inconsistency('object names', lod_obj.name, main_lod_obj.name)
    if lod_obj.bf2_object_type != main_lod_obj.bf2_object_type:
        _inconsistency('BF2 Object Types', lod_obj.bf2_object_type, main_lod_obj.bf2_object_type)
    if main_lod_obj.location != lod_obj.location:
        _inconsistency('object locations', lod_obj.location, main_lod_obj.location)
    if main_lod_obj.rotation_quaternion != lod_obj.rotation_quaternion:
        _inconsistency('object rotations', lod_obj.rotation_quaternion, main_lod_obj.rotation_quaternion)

    main_lod_children = dict()
    for child_obj in main_lod_obj.children:
        main_lod_children[_strip_prefix(child_obj.name)] = child_obj

    for child_obj in lod_obj.children:
        child_name = _strip_prefix(child_obj.name)
        if _is_colmesh_dummy(child_obj):
            continue
        if child_name not in main_lod_children:
            raise ExportException(f"Unexpected object '{child_obj.name}' found, hierarchy does not match with other LOD(s)")

        prev_lod_child = main_lod_children[child_name]
        _verify_lods_consistency(prev_lod_child, child_obj)

def _create_object_template(obj, obj_to_geom_part_id, obj_to_col_part_id, is_vehicle=None) -> ObjectTemplate:
    if obj.bf2_object_type == '': # special case, geom part which has no object template (see GenericFirearm)
        return None

    obj_name = _strip_prefix(obj.name)
    obj_template = ObjectTemplate(obj.bf2_object_type, obj_name)

    if is_vehicle is None: # root object
        # TODO: no idea how to properly detect whether the exported object
        # should or should not have mobile physics
        is_vehicle = obj_template.type.lower() == 'PlayerControlObject'.lower()

    obj_template.has_mobile_physics = is_vehicle

    if obj_name in obj_to_col_part_id:
        obj_template.physics_type = ObjectTemplate._PhysicsType.MESH
        obj_template.has_collision_physics = True
        obj_template.col_part = obj_to_col_part_id[obj_name]

    if obj_name in obj_to_geom_part_id:
        obj_template.geom_part = obj_to_geom_part_id[obj_name]

    for _, child_obj in sorted([(child.name, child) for child in obj.children]):
        if _is_colmesh_dummy(child_obj): # skip collmeshes
            continue
        child_template = _create_object_template(child_obj, obj_to_geom_part_id, obj_to_col_part_id, is_vehicle)
        if child_template is None:
            continue
        child_object = ObjectTemplate.ChildObject(child_template.name)
        child_object.template = child_template
        child_object.position = _swap_zy(child_obj.location)
        child_object.rotation = _swap_zy(child_obj.rotation_euler)
        obj_template.children.append(child_object)

    return obj_template

def _strip_prefix(s):
    for char_idx, _ in enumerate(s):
        if s[char_idx:].startswith('__'):
            return s[char_idx+2:]
    return ExportException(f"'{s}' has no GxLx__ prefix!")

def _object_hierarchy_has_any_meshes(obj):
    if obj.data:
        return True
    for child_obj in obj.children:
        if child_obj.data:
            return True
        return _object_hierarchy_has_any_meshes(child_obj)
    return False

def _delete_hierarchy_if_has_no_meshes(obj):
    if not _object_hierarchy_has_any_meshes(obj):
        delete_object(obj, recursive=True)
    else:
        for child_obj in obj.children:
            _delete_hierarchy_if_has_no_meshes(child_obj)

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

def _apply_mesh_data_to_lod(context, root_template, geom_parts, coll_parts, geom, lod):
    prfx = _build_mesh_prefix(geom, lod)
    add_col = coll_parts and lod == 0 # Add colistion only for LOD 0

    def _fix_geom_parts(obj_template, geom_parent=None, position=(0, 0, 0), rotation=(0, 0, 0)):
        geom_part_id = obj_template.geom_part
        vertex_group_name = f'mesh{geom_part_id + 1}'
        part_name = f'{prfx}{obj_template.name}'
        part_rotation = _swap_zy(rotation)
        part_position = _swap_zy(position)

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
                else:
                    # this is a bone, create new dummy for it, it will not hold visible mesh data
                    # the root object will instead (to keep faces intact!)
                    # need this dummy for two things: holding object type and collmesh

                    # but first transform verts of the root object
                    _transform_verts(geometry_part_obj, vertex_group_name, part_position, part_rotation)
                    # it might happen that direct parent (geom_parent) does not have mesh with this vertex group
                    # in this case we need to apply transforms of all parents to be relative to geometry_part_obj
                    parents_to_root = list()
                    _get_parent_list(geom_parent, geometry_part_obj, parents_to_root)
                    for parent in parents_to_root:
                        _transform_verts(geometry_part_obj, vertex_group_name, parent.location, parent.rotation_euler)

                    # next override geometry_part_obj with a dummy
                    geometry_part_obj = bpy.data.objects.new(part_name, None)
                    context.scene.collection.objects.link(geometry_part_obj)

                geometry_part_vg.name = part_name 
            else:
                # normal case, all vertices for all faces have the same part id
                geometry_part_obj.name = part_name
                geometry_part_obj.data.name = part_name
        else:
            # might happen that some lod does not have geometry for some parts
            # but this part's children do, so we gotta create a dummy parent for them
            geometry_part_obj = bpy.data.objects.new(part_name, None)
            context.scene.collection.objects.link(geometry_part_obj)

        geometry_part_obj.rotation_euler = part_rotation
        geometry_part_obj.location = part_position
        geometry_part_obj.parent = geom_parent
        geometry_part_obj.bf2_object_type = obj_template.type # custom property

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

def _transform_verts(geometry_part_obj, vertex_group, part_position, part_rotation):
    bpy.context.view_layer.objects.active = geometry_part_obj
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.object.vertex_group_set_active(group=vertex_group)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.vertex_group_select()
    bpy.ops.transform.rotate(value=part_rotation[0], orient_axis='X')
    bpy.ops.transform.rotate(value=part_rotation[1], orient_axis='Y')
    bpy.ops.transform.rotate(value=part_rotation[2], orient_axis='Z')
    bpy.ops.transform.translate(value=part_position)
    bpy.ops.object.mode_set(mode='OBJECT')

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
    if obj.data:
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

    return splitted_parts

def _create_mesh_vertex_group(obj, obj_to_geom_part_id, empty_groups):
    org_obj_name = obj.name[len(TMP_PREFIX):]
    obj_name = _strip_prefix(org_obj_name)
    part_id = obj_to_geom_part_id[obj_name]
    group_name = f'mesh{part_id + 1}'
    if obj.data:
        if group_name in obj.vertex_groups.keys():
            raise ExportException(f"{org_obj_name}: '{group_name}' vertex group should not exist")
        obj.vertex_groups.new(name=group_name)
        for vertex in obj.data.vertices:
            obj.vertex_groups[group_name].add([vertex.index], 1.0, "REPLACE")
    else:
        # might happen that geometry part has no mesh, it's valid!
        # have to add this empty vertex group after merging
        # can't do that if object has no mesh!
        empty_groups.add(group_name)

    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _create_mesh_vertex_group(child_obj, obj_to_geom_part_id, empty_groups)

def _select_all_geometry_parts_and_reset_positions(obj):
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.select_set(True)

    for child_obj in obj.children:
        if not _is_colmesh_dummy(child_obj):
            _select_all_geometry_parts_and_reset_positions(child_obj)

def _join_lod_hierarchy_into_single_mesh(lod_obj, obj_to_geom_part_id):
    # first, assign one vertex group for each mesh which corresponds to geom part id
    empty_groups = set()
    _create_mesh_vertex_group(lod_obj, obj_to_geom_part_id, empty_groups)

    # select all geom parts with meshes
    bpy.context.view_layer.objects.active = lod_obj
    bpy.ops.object.select_all(action='DESELECT')
    _select_all_geometry_parts_and_reset_positions(lod_obj)
    bpy.ops.object.join()

    for group_name in empty_groups:
        lod_obj.vertex_groups.new(name=group_name)

def _join_lods(mesh_geoms, obj_to_geom_part_id):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            _join_lod_hierarchy_into_single_mesh(lod_obj, obj_to_geom_part_id)

def _duplicate_object(obj, recursive=True):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.duplicate()
    new_obj = bpy.context.view_layer.objects.active
    new_obj.name = TMP_PREFIX + obj.name

    if recursive:
        for child_obj in obj.children:
            if _is_colmesh_dummy(child_obj):
                continue
            new_child = _duplicate_object(child_obj, recursive=recursive)
            new_child.parent = new_obj
    return new_obj

def _duplicate_lods(mesh_geoms):
    new_mesh_geoms = list()
    for geom_obj in mesh_geoms:
        new_geom_obj = list()
        new_mesh_geoms.append(new_geom_obj)
        for lod_obj in geom_obj:
            new_lod_obj = _duplicate_object(lod_obj)
            new_geom_obj.append(new_lod_obj)
    return new_mesh_geoms

def _delete_lods(mesh_geoms):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            delete_object(lod_obj, recursive=True)

def _apply_modifiers(mesh_geoms):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            bpy.ops.object.select_all(action='DESELECT')
            lod_obj.select_set(True)
            bpy.context.view_layer.objects.active = lod_obj
            bpy.ops.object.convert()

def _triangulate(mesh_geoms):
    for geom_obj in mesh_geoms:
        for lod_obj in geom_obj:
            bpy.ops.object.select_all(action='DESELECT')
            lod_obj.select_set(True)
            bpy.context.view_layer.objects.active = lod_obj
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.object.mode_set(mode='OBJECT')

def _dump_con_file(root_obj_template, con_file):
    with open(con_file, 'w') as f:
        root_obj_template.geom.make_script(f)
        if root_obj_template.collmesh:
            root_obj_template.collmesh.make_script(f)
        f.write('\n')
        root_obj_template.make_script(f)
        f.write(f'include {root_obj_template.name}.tweak')
        f.write('\n')

def _swap_zy(vec):
    return (vec[0], vec[2], vec[1])