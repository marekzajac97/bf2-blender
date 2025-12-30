import os.path as path
import math
import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Matrix, Vector, Euler # type: ignore

from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            FileManagerFileNotFound,
                            ObjectTemplate,
                            GeometryTemplate,
                            HeightmapCluster,
                            Object)
from .bf2.bf2_mesh import BF2BundledMesh, BF2StaticMesh, BF2SkinnedMesh, BF2Samples
from .mod_loader import ModLoader
from .mesh import MeshImporter, MeshExporter
from .utils import DEFAULT_REPORTER, swap_zy, file_name, _convert_pos, _convert_rot, to_matrix, save_img_as_dds, delete_object, find_root
from .heightmap import import_heightmap_from, make_water_plane
from .exceptions import ImportException

MESH_TYPES = {
    'StaticMesh': BF2StaticMesh,
    'BundledMesh': BF2BundledMesh,
    'SkinnedMesh': BF2SkinnedMesh
}

DEBUG = False

def _unplug_socket_from_bsdf(socket_name):
    for mesh in bpy.data.meshes:
        for material in mesh.materials:
            if not material.is_bf2_material:
                continue
            node_tree = material.node_tree
            for node_link in node_tree.links:
                node = node_link.to_node
                if node.type == 'BSDF_PRINCIPLED' and node_link.to_socket.name == socket_name:
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

def _strip_prefix(s):
    for char_idx, _ in enumerate(s):
        if s[char_idx:].startswith('__'):
            return s[char_idx+2:]
    raise s

def _gen_lm_key(obj, lod=0):
    # TODO: warn if objects are too close to each other and generate same key
    geom_template_name = _strip_prefix(_strip_suffix(obj.name)).lower()
    x, y, z = [str(int(i)) for i in obj.matrix_world.translation]
    return '='.join([geom_template_name, f'{lod:02d}', x, z, y])

def _setup_object_for_baking(lod_idx, obj): # TODO: LM size per object
    lm_name = _gen_lm_key(obj, lod=lod_idx)
    lm_size = tuple(obj.bf2_lightmap_size)

    if lm_size == (0, 0):
        return None

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
            if node.type == 'TEX_IMAGE' and node.name == 'LIGHTMAP_BAKE_TXT':
                texture_node = node
                break
        else:
            texture_node = node_tree.nodes.new(type='ShaderNodeTexImage')
            texture_node.name = 'LIGHTMAP_BAKE_TXT'
            texture_node.location = (400, 500)

        texture_node.select = True
        texture_node.image = bake_image

        # make UV node
        # TODO: verify has UV4
        uv_node = None
        for node in node_tree.nodes:
            if node.type == 'UVMAP' and node.name == 'LIGHTMAP_BAKE_UV':
                uv_node = node
                break
        else:
            uv_node = node_tree.nodes.new('ShaderNodeUVMap')
            uv_node.name = 'LIGHTMAP_BAKE_UV'
            uv_node.location = (400, 300)

        uv_node.uv_map = 'UV4'
        uv_node.select = True

        # link
        node_tree.links.new(uv_node.outputs['UV'], texture_node.inputs['Vector'])
        node_tree.nodes.active = texture_node

    if setup_ok:
        return bake_image
    else:
        bpy.data.images.remove(bake_image)

def _select_lod_for_bake(geom, lod):
    for lod_idx, lod_obj in enumerate(geom):
        if lod_idx == lod:
            lod_obj.hide_set(False)
            lod_obj.select_set(True)
            lod_obj.hide_render = False
        else:
            lod_obj.hide_set(True)
            lod_obj.select_set(False)
            lod_obj.hide_render = True

def bake_object_lightmaps(context, output_dir, dds_fmt='NONE', lods=None, only_selected=True):
    _setup_scene_for_baking(context)
    objects = list()
    if only_selected:
        for obj in context.selected_objects:
            root_obj = find_root(obj)
            if root_obj not in objects:
                objects.append(root_obj)
    else:
        for obj in context.scene.collection.children['StaticObjects'].objects:
            if obj.parent is None and obj.data is None:
                objects.append(root_obj)

    for obj in context.selected_objects:
        obj.select_set(False)

    total_cnt = len(objects)
    for i, root_obj in enumerate(objects, start=1):
        print(f"Baking object {root_obj.name} {i}/{total_cnt}")
        geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
        for geom_idx, geom in enumerate(geoms):
            if geom_idx != 0: # TODO: Geom1 support
                continue
            for lod_idx, lod_obj in enumerate(geom):
                if lods is not None and lod_idx not in lods:
                    continue
                if image := _setup_object_for_baking(lod_idx, lod_obj):
                    _select_lod_for_bake(geom, lod_idx)
                    context.view_layer.update()
                    bpy.ops.object.bake(type='DIFFUSE', uv_layer='UV4')
                    save_img_as_dds(image, path.join(output_dir, image.name + '.dds'), dds_fmt)
                    bpy.data.images.remove(image)

            _select_lod_for_bake(geom, 0)
            context.view_layer.update()

def _make_collection(context, name):
    if name in bpy.data.collections:
        c = bpy.data.collections[name]
        return c
    else:
        c = bpy.data.collections.new(name)
        context.scene.collection.children.link(c)
        return c

DEFAULT_LM_SIZE_TO_SURFACE_AREA_THRESHOLDS = [
    (8, 0),
    (16, 4),
    (32, 8),
    (64, 16),
    (128, 32),
    (256, 256),
    (512, 1024),
    (1024, 2056)
]

def _calc_mesh_area(lod_obj):
    bm = bmesh.new()
    bm.from_mesh(lod_obj.data)
    area = sum(f.calc_area() for f in bm.faces)
    bm.free()
    return area

def _clone_object(collection, src_root):
    geoms = MeshExporter.collect_geoms_lods(src_root, skip_checks=True)
    root = bpy.data.objects.new(src_root.name, None)
    root.hide_render = True
    collection.objects.link(root)
    root.hide_set(True)
    for geom_idx, geom in enumerate(geoms):
        geom_obj = bpy.data.objects.new(f'G{geom_idx}__' + src_root.name, None)
        geom_obj.parent = root
        geom_obj.hide_render = True
        collection.objects.link(geom_obj)
        geom_obj.hide_set(True)
        for lod_idx, src_lod_obj in enumerate(geom):
            lod_obj = bpy.data.objects.new(f'G{geom_idx}L{lod_idx}__' + src_root.name, src_lod_obj.data)
            lod_obj.parent = geom_obj
            lod_obj.bf2_lightmap_size = src_lod_obj.bf2_lightmap_size
            collection.objects.link(lod_obj)
            if lod_idx != 0:
                lod_obj.hide_render = True
                lod_obj.hide_set(True)
    return root

def load_level(context, mod_dir, level_name, use_cache=True,
               load_unpacked=True, load_objects=True,
               load_og=True, load_heightmap='PRIMARY', load_lights=True,
               no_normalmaps=False, lm_size_thresholds=None,
               reporter=DEFAULT_REPORTER):

    if lm_size_thresholds is None:
        lm_size_thresholds = DEFAULT_LM_SIZE_TO_SURFACE_AREA_THRESHOLDS

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

    if DEBUG:
        print(f"Loading statics")

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

    static_objects = _make_collection(context, "StaticObjects")
    static_objects_skip = _make_collection(context, "StaticObjects_SkipLightmaps")

    for idx, (template_name, geom_temp) in enumerate(templates.items()):
        if DEBUG:
            print(f"Importing {geom_temp.name} | {idx}/{len(templates)}")

        data = file_manager.readFile(geom_temp.location, as_stream=True)
        mesh_type = MESH_TYPES.get(geom_temp.geometry_type)
        if not mesh_type:
            reporter.warning(f"skipping '{template_name}' as it is not supported mesh type {geom_temp.geometry_type}")
            continue
        try:
            bf2_mesh = mesh_type.load_from(template_name, data)
        except Exception as e:
            reporter.warning(f"Failed to load mesh '{geom_temp.location}', the file might be corrupted: {e}")
            del template_to_instances[template_name]
            continue
    
        # determine samples size
        meshes_dir = path.dirname(geom_temp.location)
        lm_sizes = dict()
        for lod_idx, _ in enumerate(bf2_mesh.geoms[0].lods): # TODO: Geom1 support
            if lod_idx == 0:
                fname = path.join(meshes_dir, geom_temp.name + '.samples')
            else:
                fname = path.join(meshes_dir, geom_temp.name + f'.samp_{lod_idx:02d}')
            
            lm_size = None
            if load_unpacked:
                if path.isfile(fname):
                    with open(fname, "rb") as f:
                        lm_size = BF2Samples.read_map_size_from(f)
            else:
                raise NotImplementedError() # TODO
            lm_sizes[lod_idx] = lm_size

        obj_transforms = template_to_instances[template_name]

        # TODO: texture load from FileManager if not load_unpacked!
        importer = MeshImporter(context, geom_temp.location, loader=lambda: bf2_mesh, texture_path=mod_dir, reporter=reporter)
        try:
            root_obj = importer.import_mesh()
        except ImportException as e:
            reporter.warning(f"Failed to import mesh '{geom_temp.location}': {e}")
            continue

        geoms = MeshExporter.collect_geoms_lods(root_obj, skip_checks=True)
        lod0_lm_size = None
        MIN_LM_SIZE = 8
        for lod_idx, lod_obj in enumerate(geoms[0]): # TODO: Geom1 support
            lm_size = lm_sizes[lod_idx]
            if lm_size is None:
                # if lm_size is None:
                #     reporter.warning(f"Cannot determine LM size for mesh '{geom.location}' Lod{lod_idx} from samples file, it may not exist")
                if lod0_lm_size is not None:
                    # halve the LOD0 size
                    lm_size = [max(int(i / (2**lod_idx)), MIN_LM_SIZE) for i in lod0_lm_size]
                else:
                    # guess using surface area of the mesh
                    mesh_area = _calc_mesh_area(lod_obj)
                    for lms, min_area in reversed(lm_size_thresholds):
                        if mesh_area >= min_area:
                            lm_size = (lms, lms)
                            break
            if lm_size is None:
                lm_size = (MIN_LM_SIZE, MIN_LM_SIZE)
            if lod_idx == 0:
                lod0_lm_size = lm_size
            lod_obj.bf2_lightmap_size = lm_size

        # TODO: Geom1 support
        if 'StaticMesh' == geom_temp.geometry_type:
            for geom_obj in geoms[1:]:
                delete_object(geom_obj)

        for matrix_world in obj_transforms:
            if geom_temp.dont_generate_lightmaps or 'StaticMesh' != geom_temp.geometry_type:
                obj = _clone_object(static_objects_skip, root_obj)
            else:
                obj = _clone_object(static_objects, root_obj)
            obj.matrix_world = matrix_world

        # delete source instance
        delete_object(root_obj, remove_data=False)

    if no_normalmaps:
        _unplug_socket_from_bsdf('Normal')

    heightmaps = _make_collection(context, "Heightmaps")

    if DEBUG:
        print(f"Loading heightmap")

    if load_heightmap:
        main_console.run_file(f'{level_dir}/Heightdata.con')
        hm_cluster = BF2Engine().get_manager(HeightmapCluster).active_obj
        if hm_cluster:
            water_plane = make_water_plane(context, hm_cluster.heightmap_size, hm_cluster.water_level)
            primary_hightmap = None
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
                if heightmap.cluster_offset == (0, 0):
                    primary_hightmap = obj

            # load minimap as diffuse texture on primary heightmap and waterplane

            for obj in (water_plane, primary_hightmap):
                if not obj:
                    continue
                minimap_path = path.join(level_dir, 'Hud', 'Minimap', 'ingameMap.dds')
                if path.isfile(minimap_path):
                    material = bpy.data.materials.new('Minimap')     
                    material.use_nodes = True
                    obj.data.materials.append(material)

                    tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
                    try:
                        tex_node.image = bpy.data.images.load(minimap_path, check_existing=True)
                        tex_node.image.alpha_mode = 'NONE'
                    except RuntimeError:
                        pass # ignore if can't be loaded

                    bsdf = material.node_tree.nodes['Principled BSDF']
                    bsdf.inputs['Roughness'].default_value = 1
                    bsdf.inputs['Specular IOR Level'].default_value = 0
                    bsdf.inputs['IOR'].default_value = 1.1
                    material.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

    if DEBUG:
        print(f"Loading lights")

    lights = _make_collection(context, "Lights")
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
