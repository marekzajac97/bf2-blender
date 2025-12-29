import os.path as path
import math
import bpy # type: ignore
from mathutils import Matrix, Vector, Euler # type: ignore

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
from .utils import DEFAULT_REPORTER, swap_zy, file_name, _convert_pos, _convert_rot, to_matrix, save_img_as_dds
from .heightmap import import_heightmap_from, make_water_plane
from .exceptions import ImportException

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

def _remove_diffuse_color_from_all_materials():
    for mesh in bpy.data.meshes:
        for material in mesh.materials:
            if not material.is_bf2_material:
                continue
            node_tree = material.node_tree
            for node_link in node_tree.links:
                if 'Base Color' in node_link.to_node.inputs:
                    node_tree.links.remove(node_link)
                    break

def _yaw_pitch_roll_to_matrix(rotation):
    rotation = tuple(map(lambda x: -math.radians(x), rotation))
    yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
    pitch = Matrix.Rotation(rotation[1], 4, 'X')
    roll  = Matrix.Rotation(rotation[2], 4, 'Y')
    return (yaw @ pitch @ roll)

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

def _setup_scene_for_baking(context):
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.bake_type = 'DIFFUSE'
    context.scene.render.bake.use_pass_direct = True
    context.scene.render.bake.use_pass_indirect = True
    context.scene.render.bake.use_pass_color = False

def _strip_suffix(s):
    if '.' not in s:
        return s
    head, tail = s.rsplit('.', 1)
    if tail.isnumeric():
        return head
    return s

def _gen_lm_key(obj, lod=0):
    # TODO: warn if objects are too close to each other and generate same key
    geom_template_name = _strip_suffix(obj.name).lower()
    x, y, z = [str(int(i)) for i in obj.location]
    return '='.join([geom_template_name, f'{lod:02d}', x, z, y])

def _setup_object_for_baking(obj, lm_size=(512, 512)): # TODO: LM size per object
    lm_name = _gen_lm_key(obj)

    # create bake image
    if lm_name in bpy.data.images:
        bake_image = bpy.data.images[lm_name]
        bpy.data.images.remove(bake_image)

    bake_image = bpy.data.images.new(name=lm_name, width=lm_size[0], height=lm_size[1])

    setup_ok = False
    # add bake lightmap texture for each material
    for material in obj.data.materials:
        if not material.is_bf2_material:
            continue
        setup_ok = True

        node_tree = material.node_tree
        # unselect all
        for node in node_tree.nodes:
            node.select = False

        # make texture image node
        texture_node = None
        for node in node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.name == lm_name + '_TXT':
                texture_node = node
                break
        else:
            texture_node = node_tree.nodes.new(type='ShaderNodeTexImage')
            texture_node.name = lm_name + '_TXT'
            texture_node.location = (500, 500)

        texture_node.select = True
        texture_node.image = bake_image

        # make UV node
        # TODO: verify has UV4
        uv_node = None
        for node in node_tree.nodes:
            if node.type == 'UV_MAP' and node.name == lm_name + '_UV':
                texture_node = node
                break
        else:
            uv_node = node_tree.nodes.new('ShaderNodeUVMap')
            uv_node.name = lm_name + '_UV'
            texture_node.location = (400, 500)

        uv_node.uv_map = 'UV4'
        uv_node.select = True

        # link
        node_tree.links.new(uv_node.outputs['UV'], texture_node.inputs['Vector'])
        node_tree.nodes.active = texture_node

    if setup_ok:
        return bake_image
    else:
        bpy.data.images.remove(bake_image)

def bake_object_lightmaps(context, output_dir, dds_fmt='DXT1', only_selected=True):
    _setup_scene_for_baking(context)
    if only_selected:
        objects = context.selected_objects
    else:
        objects = context.scene.collection.children['StaticObjects'].objects
    total_cnt = len(objects)
    for i, obj in enumerate(objects, start=1):
        print(f"Baking object {obj.name} {i}/{total_cnt}")
        if image := _setup_object_for_baking(obj):
            bpy.ops.object.bake(type='DIFFUSE', uv_layer='UV4')
            save_img_as_dds(image, path.join(output_dir, image.name + '.dds'), dds_fmt)
            bpy.data.images.remove(image)


def _find_lm_bitmap_size(geom_temp):
    pass


def load_level(context, mod_dir, level_name, use_cache=True,
               load_unpacked=True, load_objects=True,
               obj_geom=0, obj_lod=0, load_og=True,
               load_heightmap='PRIMARY', load_lights=True,
               no_diffuse=False,
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

    templates : Dict[str, GeometryTemplate] = dict()
    template_to_instances : Dict[str, List[Matrix]] = dict()

    obj_manager = BF2Engine().get_manager(Object)
    geom_manager = BF2Engine().get_manager(GeometryTemplate)

    for obj in obj_manager.objects:
        template = obj.template
        # TODO: check GeometryTemplate.doNotGenerateLightmaps 1
        for temp, matrix_world, in _get_templates(template, _get_obj_matrix(obj)):
            if not temp.geom:
                continue

            geom = geom_manager.templates[temp.geom.lower()]
            obj_transforms = template_to_instances.setdefault(geom.name.lower(), list())
            obj_transforms.append(matrix_world)
            templates[geom.name.lower()] = geom

    # load meshes
    if not load_unpacked:
        main_console.run_file('clientarchives.con')
        try:
            main_console.run_file(f'{level_dir}/clientarchives.con')
        except FileManagerFileNotFound:
            pass

    template_to_mesh = dict()
    for template_name, geom in templates.items():
        # TODO obj templates can share geom templates
        data = file_manager.readFile(geom.location, as_stream=True)
        mesh_type = MESH_TYPES.get(geom.geometry_type)
        if not mesh_type:
            reporter.warning(f"skipping '{template_name}' as it is not supported mesh type {geom.geometry_type}")
            continue
        try:
            template_to_mesh[template_name] = mesh_type.load_from(template_name, data)
        except Exception as e:
            reporter.warning(f"Failed to load mesh '{geom.location}', the file might be corrupted: {e}")
            del template_to_instances[template_name]

    static_objects = bpy.data.collections.new("StaticObjects")
    context.scene.collection.children.link(static_objects)

    for template_name, obj_transforms in template_to_instances.items():
        geom = templates[template_name]
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
            static_objects.objects.link(obj)

    heightmaps = bpy.data.collections.new("Heightmaps")
    context.scene.collection.children.link(heightmaps)

    if load_heightmap:
        main_console.run_file(f'{level_dir}/Heightdata.con')
        hm_cluster = BF2Engine().get_manager(HeightmapCluster).active_obj
        if hm_cluster:
            water_plane = make_water_plane(context, hm_cluster.heightmap_size, hm_cluster.water_level)
            context.scene.collection.objects.unlink(water_plane)
            heightmaps.objects.link(water_plane)
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
                context.scene.collection.objects.unlink(obj)
                heightmaps.objects.link(obj)
                obj.location.x = location.x
                obj.location.y = location.y

    # easier to debug/previev the lights
    if no_diffuse:
        _remove_diffuse_color_from_all_materials()

    lights = bpy.data.collections.new("Lights")
    context.scene.collection.children.link(lights)

    if load_lights:
        # sun (green channel)
        main_console.run_file(f'{level_dir}/Sky.con')
        sun_dir = Vector(BF2Engine().light_manager.sun_dir)
        _convert_pos(sun_dir)
        light = bpy.data.lights.new(name='Sun', type='SUN')
        obj = bpy.data.objects.new(light.name, light)
        lights.objects.link(obj)
        sun_dir.z = -sun_dir.z # points down
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = sun_dir.rotation_difference(Vector((0, 0, 1)))

        sin_alpha = abs(sun_dir.z)
        light.energy = 2 * (1.0 + 0.5 * sin_alpha) # TODO strength
        light.color = (0, 1, 0)

        # ambient light / soft shadows (blue channel)
        if "SkyLight" in bpy.data.worlds:
            world = bpy.data.worlds["SkyLight"]
            bpy.data.worlds.remove(world)
        context.scene.world = bpy.data.worlds.new("SkyLight")
        background = context.scene.world.node_tree.nodes["Background"]
        background.inputs['Color'].default_value = (0, 0, 1, 1)
        background.inputs['Strength'].default_value = 0.7 # TODO strength

        # TODO: point lights (red channel)
