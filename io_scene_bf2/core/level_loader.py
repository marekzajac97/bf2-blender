import os.path as path
import math
import bpy # type: ignore
from mathutils import Matrix, Vector # type: ignore

from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            HeightmapCluster,
                            Object)
from .bf2.bf2_mesh import BF2BundledMesh, BF2StaticMesh, BF2SkinnedMesh
from .mod_loader import ModLoader
from .mesh import MeshImporter
from .utils import DEFAULT_REPORTER, swap_zy, file_name, _convert_pos, _convert_rot, to_matrix
from .heightmap import import_heightmap_from, make_water_plane
from .exceptions import ImportException

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

def _yaw_pitch_roll_to_matrix(rotation):
    rotation = tuple(map(lambda x: -math.radians(x), rotation))
    yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
    pitch = Matrix.Rotation(rotation[1], 4, 'X')
    roll  = Matrix.Rotation(rotation[2], 4, 'Y')
    return (yaw @ pitch @ roll)

def _get_geom(template):
    if not template.geom:
        return None
    geom_manager = BF2Engine().get_manager(GeometryTemplate)
    return geom_manager.templates[template.geom.lower()]

def _get_templates(template, matrix, templates=None):
    if templates is None:
        templates = list()
    templates.append((template, matrix))
    template.add_bundle_childs()
    for child in template.children:
        if child.template is not None:
            child_matrix = _yaw_pitch_roll_to_matrix(child.rotation)
            child_matrix.translation = swap_zy(child.position)
            _get_templates(child.template, matrix @ child_matrix, templates)
    return templates

def _get_obj_matrix(bf2_object):
    if bf2_object.transform:
        # OG
        matrix_world = Matrix(bf2_object.transform)
        matrix_world.transpose()
        pos, rot, _ = matrix_world.decompose()
        _convert_pos(pos)
        _convert_rot(rot)
        return to_matrix(pos, rot)
    else:
        # statics
        matrix_world = _yaw_pitch_roll_to_matrix(bf2_object.rot)
        matrix_world.translation = swap_zy(bf2_object.absolute_pos)
        return matrix_world

def load_level(context, mod_dir, level_name, use_cache=True,
               load_unpacked=True, load_objects=True,
               obj_geom=0, obj_lod=0, load_og=True,
               load_heightmap='PRIMARY',
               reporter=DEFAULT_REPORTER):

    if not load_unpacked:
        mod_loader = ModLoader(mod_dir, use_cache)
        mod_loader.reload_all()
    else:
        BF2Engine().shutdown()

    file_manager = BF2Engine().file_manager
    main_console = BF2Engine().main_console
    file_manager.root_dir = mod_dir

    def report_cb(con_file, line_no, line, what):
        if line.lower().startswith('object.create'):
            reporter.warning(f'{con_file}:{line_no}:{line}: {what}')

    main_console.report_cb = report_cb

    level_dir = f'levels/{level_name}'
    if load_unpacked:
        level_dir = path.join(mod_dir, level_dir)
    client_zip_path = path.join(level_dir, 'client.zip')
    server_zip_path = path.join(level_dir, 'server.zip')

    # mount level archives
    if not load_unpacked:
        file_manager.mountArchive(client_zip_path, level_dir)
        file_manager.mountArchive(server_zip_path, level_dir)

    # load statics & OG
    if load_objects or load_og:
        # load mapside object templates if exist
        if not load_unpacked:
            try:
                main_console.run_file(f'{level_dir}/serverarchives.con')
                mod_loader.load_objects(levels_only=True)
            except FileManagerFileNotFound:
                pass

        if load_objects:
            args = ['BF2Editor'] if load_unpacked else []
            main_console.run_file(f'{level_dir}/StaticObjects.con', args=args)

        if load_og:
            main_console.run_file(f'{level_dir}/Overgrowth/OvergrowthCollision.con')

    templates : Dict[str, ObjectTemplate] = dict()
    template_to_instances : Dict[str, List[Matrix]] = dict()

    obj_manager = BF2Engine().get_manager(Object)
    for obj in obj_manager.objects:
        template = obj.template
        # TODO: keep obj relations
        for temp, matrix_world, in _get_templates(template, _get_obj_matrix(obj)):
            geom = _get_geom(temp)
            if not geom:
                continue
            obj_transforms = template_to_instances.setdefault(temp.name.lower(), list())
            obj_transforms.append(matrix_world)
            templates[temp.name.lower()] = temp

    # load meshes
    if not load_unpacked:
        main_console.run_file('clientarchives.con')
        try:
            main_console.run_file(f'{level_dir}/clientarchives.con')
        except FileManagerFileNotFound:
            pass

    template_to_mesh = dict()
    for template_name, template in templates.items():
        # TODO obj templates can share geom templates
        geom = _get_geom(template)
        data = file_manager.readFile(geom.location, as_stream=True)
        mesh_type = MESH_TYPES.get(geom.geometry_type)
        if not mesh_type:
            reporter.warning(f"skipping {template_name} as it is not supported mesh type {geom.geometry_type}")
            continue
        try:
            template_to_mesh[template_name] = mesh_type.load_from(template_name, data)
        except Exception as e:
            reporter.warning(f"Failed to load mesh '{geom.location}', the file might be corrupted: {e}")
            del template_to_instances[template_name]

    for template_name, obj_transforms in template_to_instances.items():
        template = templates[template_name]
        geom = _get_geom(template)
        bf2_mesh = template_to_mesh[template_name]
        # TODO: texture load from FileManager if not load_unpacked!
        importer = MeshImporter(context, geom.location, loader=lambda: bf2_mesh, texture_path=mod_dir, reporter=reporter)
        try:
            obj = importer.import_mesh(geom=obj_geom, lod=obj_lod)
        except ImportException as e:
            reporter.warning(f"Failed to import mesh '{geom.location}': {e}")
            continue
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        for matrix_world in obj_transforms:
            obj = bpy.data.objects.new(mesh.name, mesh)
            obj.matrix_world = matrix_world
            context.scene.collection.objects.link(obj)

    if load_heightmap:
        main_console.run_file(f'{level_dir}/Heightdata.con')
        hm_cluster = BF2Engine().get_manager(HeightmapCluster).active_obj
        if hm_cluster:
            make_water_plane(context, hm_cluster.heightmap_size, hm_cluster.water_level)
            for heightmap in hm_cluster.heightmaps:
                if load_heightmap == 'PRIMARY':
                    if heightmap.cluster_offset != (0, 0):
                        continue
                elif load_heightmap != 'ALL':
                    continue
                location = hm_cluster.heightmap_size * Vector(heightmap.cluster_offset)
                data = file_manager.readFile(heightmap.raw_file, as_stream=True)
                obj = import_heightmap_from(context, data, name=file_name(heightmap.raw_file),
                                            bit_res=heightmap.bit_res, scale=swap_zy(heightmap.scale))
                obj.location.x = location.x
                obj.location.y = location.y
