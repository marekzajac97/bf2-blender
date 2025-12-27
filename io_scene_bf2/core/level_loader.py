import os.path as path
import math
import bpy # type: ignore
from mathutils import Matrix # type: ignore

from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            Object)
from .bf2.bf2_mesh import BF2StaticMesh
from .mod_loader import ModLoader
from .mesh import MeshImporter
from .utils import DEFAULT_REPORTER, delete_object, conv_bf2_to_blender, to_matrix
from .bf2.bf2_common import Vec3, Quat

def _get_geom(template):
    if not template.geom:
        return None
    geom_manager = BF2Engine().get_manager(GeometryTemplate)
    geom = geom_manager.templates[template.geom.lower()]
    if geom.geometry_type != 'StaticMesh':
        return None # TODO: bundledmeshes which are sometimes added to bundles as winndows
    return geom

def _get_templates(template, templates=None):
    if templates is None:
        templates = list()
    templates.append(template)
    template.add_bundle_childs()
    for child in template.children:
        _get_templates(child.template, templates)
    return templates

def load_level(context, mod_dir, level_name, use_cache=True, reporter=DEFAULT_REPORTER):
    mod_loader = ModLoader(mod_dir, use_cache)
    mod_loader.reload_all()

    file_manager = BF2Engine().file_manager
    main_console = BF2Engine().main_console

    level_dir = f'levels/{level_name}'
    client_zip_path = path.join(level_dir, 'client.zip')
    server_zip_path = path.join(level_dir, 'server.zip')

    # mount level archives
    file_manager.mountArchive(client_zip_path, level_dir)
    file_manager.mountArchive(server_zip_path, level_dir)

    # load mapside object templates if exist
    try:
        main_console.run_file(f'{level_dir}/serverarchives.con')
        mod_loader.load_objects(levels_only=True)
    except FileManagerFileNotFound:
        pass

    # load objects
    main_console.run_file(f'{level_dir}/StaticObjects.con')
    templates : Dict[str, List[ObjectTemplate]] = dict()
    template_to_objects = dict()

    obj_manager = BF2Engine().get_manager(Object)
    skipped_templates = dict()
    for obj in obj_manager.objects:
        template = obj.template
        for temp in _get_templates(template):
            geom = _get_geom(temp)
            if not geom:
                skipped_templates[temp.name.lower()] = temp
                continue

            objects = template_to_objects.setdefault(template.name.lower(), list())
            objects.append(obj)
            templates[temp.name.lower()] = temp

    # load meshes
    main_console.run_file('clientarchives.con')
    try:
        main_console.run_file(f'{level_dir}/clientarchives.con')
    except FileManagerFileNotFound:
        pass

    template_to_mesh = dict()
    for template_name, template in templates.items():
        # TODO obj templates can share geom templates
        geom = _get_geom(template)
        try:
            data = BF2Engine().file_manager.readFile(geom.location, as_stream=True)
            template_to_mesh[template_name] = BF2StaticMesh.load_from(template_name, data)
        except Exception as e:
            reporter.warning(f"Failed to load StaticMesh '{geom.location}', the file might be corrupted: {e}")
            del template_to_objects[template_name]

    for template_name, bf2_objects in template_to_objects.items():
        geom = _get_geom(template)
        bf2_mesh = template_to_mesh[template_name]
        importer = MeshImporter(context, geom.location, loader=lambda: bf2_mesh, texture_path=mod_dir, setup_materials=False, reporter=reporter)
        obj = importer.import_mesh(geom=0, lod=0)
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        for bf2_object in bf2_objects:
            rotation = tuple(map(lambda x: -math.radians(x), bf2_object.rot))
            yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
            pitch = Matrix.Rotation(rotation[1], 4, 'X')
            roll  = Matrix.Rotation(rotation[2], 4, 'Y')
            matrix_world = yaw @ pitch @ roll
            matrix_world.translation = conv_bf2_to_blender(Vec3(*bf2_object.absolute_pos))
            obj = bpy.data.objects.new(mesh.name, mesh)
            obj.matrix_world = matrix_world
            context.scene.collection.objects.link(obj)
