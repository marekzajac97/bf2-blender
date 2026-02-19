import bpy # type: ignore
from mathutils import Vector # type: ignore
import bmesh # type: ignore
import tempfile
import os
import math
from ... import rectpack

from ..object_template import collect_anchor_geoms_lods, parse_geom_type
from ..utils import next_power_of_2, obj_bounds

class PlaneConfig:
    def __init__(self, plane_axes, camera_rot, dir, flip_uv):
        self.plane_axes = plane_axes
        self.camera_rot = camera_rot
        self.dir = dir
        self.flip_uv = flip_uv

PLANE_CONFIGS = {
    'FRONT':  PlaneConfig(('x', 'z'), (90,   0, 180), True,  flip_uv=True),
    'BACK':   PlaneConfig(('x', 'z'), (90,   0,   0), False, flip_uv=False),
    'RIGHT':  PlaneConfig(('y', 'z'), (90,   0,  90), True,  flip_uv=False),
    'LEFT':   PlaneConfig(('y', 'z'), (90,   0, -90), False, flip_uv=True),
    'TOP':    PlaneConfig(('x', 'y'), ( 0,   0,   0), True,  flip_uv=False),
    'BOTTOM': PlaneConfig(('x', 'y'), ( 0, 180,   0), False, flip_uv=True)
}

def paste_img(dst_img, src_img, x, y):
    src_width, src_height = src_img.size

    # its RGBA buffer so every pixel contains 4 values
    row_offset = lambda img, i: img.size[0] * img.size[1]*4 - (i + 1) * img.size[0]*4

    # copy
    for i in range(src_height):
        dst_off = row_offset(dst_img, i + y) + x*4
        src_off = row_offset(src_img, i)
        dst_img.pixels[dst_off:dst_off+src_width*4] = src_img.pixels[src_off:src_off+src_width*4]
    dst_img.update()

def combine_planes(name, planes, textures):
    plane_dims = [(t.size[0], t.size[1]) for t in textures]

    # pack textures
    packer = rectpack.newPacker(rotation=False)
    required_area = 0
    for i, (x, y) in enumerate(plane_dims):
        packer.add_rect(x, y, i)
        required_area += x * y

    # find minimum possible dimenesions
    width = 0
    height = 0
    while True:
        width = next_power_of_2(width+1)
        if width * height >= required_area:
            break
        height = next_power_of_2(height+1)
        if height * height >= required_area:
            break

    packer.add_bin(width, height)
    packer.pack()

    if len(packer[0]) != len(planes):
        raise RuntimeError("Packing error")

    combined_image = bpy.data.images.new(name='CombinedTexture', width=width, height=height, alpha=True)
    combined_image.pixels[:] = (0,0,0,0) * width * height # clear image

    # make combined mesh object
    bm = bmesh.new()
    for plane_idx, plane in enumerate(planes):
        for vert in plane.data.vertices:
            bm.verts.new(Vector(vert.co) + plane.location)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    for plane_idx, plane in enumerate(planes):
        for poly in plane.data.polygons:
            bm.faces.new(bm.verts[v+(plane_idx*4)] for v in poly.vertices)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    obj = bpy.data.objects.new(name, mesh)

    combined_uv = obj.data.uv_layers.new(name='UV0')
    combined_uv.active = True
    obj.data.uv_layers.active = combined_uv

    for rect in packer[0]:
        # combine textures
        image = textures[rect.rid]
        paste_img(combined_image, image, rect.x, rect.y)

        # combine uvs
        plane = planes[rect.rid]
        old_uv = plane.data.uv_layers['UVMap']
        for loop in mesh.loops:
            plane_idx = int(loop.vertex_index / 4)
            if plane_idx != rect.rid:
                continue
            uv = None
            for l in plane.data.loops:
                if l.vertex_index == loop.vertex_index % 4:
                    uv = old_uv.data[l.index].uv
                    break
            plane_width, plane_height = plane_dims[plane_idx]
            scale_u = plane_width / width
            scale_v = plane_height / height
            offset_u = rect.x / width
            offset_v =  1 - rect.y / height - scale_v
            u, v = uv
            u = u * scale_u + offset_u
            v = v * scale_v + offset_v
            combined_uv.data[loop.index].uv = (u, v)

    # cleanup old
    for image in textures:
        bpy.data.images.remove(image, do_unlink=True)

    for plane in planes:
        bpy.data.meshes.remove(plane.data, do_unlink=True)

    return obj, combined_image

def project_to_plane(obj, plane_name, texture_size):
    # make temp scene
    hide_render = obj.hide_render
    camera = None
    mesh = None
    scene = bpy.data.scenes.new("TempScene")
    scene.world = bpy.data.worlds.new("TempWorld")
    scene.collection.objects.link(obj)
    obj.hide_render = False
    try:
        bounds = obj_bounds(obj)

        cfg = PLANE_CONFIGS[plane_name]
        plane_axes = cfg.plane_axes
        camera_rot = cfg.camera_rot
        dir = cfg.dir
        flip_uv = cfg.flip_uv

        u_bound = bounds[plane_axes[0]]
        v_bound = bounds[plane_axes[1]]
        u_offset = u_bound.distance / 2 + u_bound.min
        v_offset = v_bound.distance / 2 + v_bound.min

        texture_width, texture_height = texture_size
        aspect_ratio = texture_width / texture_height

        if u_bound.distance > v_bound.distance:
            ortho_scale = plane_width = u_bound.distance
            plane_height = plane_width * (1/aspect_ratio)
        else:
            ortho_scale = plane_height = v_bound.distance
            plane_width = plane_height * aspect_ratio

        # Make plane
        bm = bmesh.new()

        plane_axes_idx = ['xyz'.index(a) for a in plane_axes]

        bottom_left = [0, 0, 0]
        bottom_left[plane_axes_idx[0]] = -plane_width / 2
        bottom_left[plane_axes_idx[1]] = -plane_height / 2

        top_left = [0, 0, 0]
        top_left[plane_axes_idx[0]] = -plane_width / 2
        top_left[plane_axes_idx[1]] = plane_height / 2

        top_right = [0, 0, 0]
        top_right[plane_axes_idx[0]] = plane_width / 2
        top_right[plane_axes_idx[1]] = plane_height / 2

        bottom_right = [0, 0, 0]
        bottom_right[plane_axes_idx[0]] = plane_width / 2
        bottom_right[plane_axes_idx[1]] = -plane_height / 2

        bm.verts.new(bottom_left)
        bm.verts.new(top_left)
        bm.verts.new(top_right)
        bm.verts.new(bottom_right)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.new(bm.verts[i] for i in ((0, 1, 2, 3)))

        mesh = bpy.data.meshes.new(plane_name)
        bm.to_mesh(mesh)

        uv_layer = mesh.uv_layers.new(name='UVMap')
        for loop in mesh.loops:
            vertex = mesh.vertices[loop.vertex_index]
            u = vertex.co[plane_axes_idx[0]] / plane_width + 0.5
            v = vertex.co[plane_axes_idx[1]] / plane_height + 0.5
            if flip_uv:
                uv = (1 - u, v)
            else:
                uv = (u, v)
            uv_layer.data[loop.index].uv = uv

        plane_obj = bpy.data.objects.new(plane_name, mesh)
        scene.collection.objects.link(plane_obj)
        plane_obj.matrix_world = obj.matrix_world
        plane_obj.location[plane_axes_idx[0]] += u_offset
        plane_obj.location[plane_axes_idx[1]] += v_offset
        plane_obj.hide_render = True

        # create camera

        camera_name = 'Camera_' + plane_name
        camera = bpy.data.cameras.new(name=camera_name)
        camera_obj = bpy.data.objects.new(camera_name, camera)
        scene.collection.objects.link(camera_obj)
        scene.camera = camera_obj

        camera.type = 'ORTHO'
        camera.ortho_scale = ortho_scale

        depth_axis = [a for a in 'xyz' if a not in plane_axes][0]
        depth_bound = bounds[depth_axis]
        depth_offset = depth_bound.max if dir else depth_bound.min

        camera_obj.matrix_world = obj.matrix_world
        camera_obj.location[plane_axes_idx[0]] += u_offset
        camera_obj.location[plane_axes_idx[1]] += v_offset
        camera_obj.location['xyz'.index(depth_axis)] += depth_offset

        for axis, rot in enumerate(camera_rot):
            camera_obj.rotation_euler[axis] = math.radians(rot)

        # ambient light
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs['Color'].default_value = (1, 1, 1, 1)

        # render settings
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except:
            scene.render.engine = 'BLENDER_EEVEE' # Blender 5.0

        scene.render.resolution_x = texture_width
        scene.render.resolution_y = texture_height
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.film_transparent = True

        # render
        layer = scene.view_layers[0].name
        bpy.ops.render.render(layer=layer, scene=scene.name)

        # save and reload image, Render Result can't be used directly as img texture...
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "tmp.png")
            bpy.data.images["Render Result"].save_render(file_path, scene=scene)
            image = bpy.data.images.load(file_path)
            image.name = plane_name
            image.pack() # pack into .blend file

    except Exception:
        raise
    finally:
        # cleanup
        obj.hide_render = hide_render
        if camera:
            bpy.data.cameras.remove(camera, do_unlink=True)
        bpy.data.worlds.remove(scene.world)
        bpy.data.scenes.remove(scene)

    return plane_obj, image

def generate_og_lod(root, projections):
    _, obj_name = parse_geom_type(root)
    _, mesh_geoms = collect_anchor_geoms_lods(root)
    obj = mesh_geoms[0][0]

    planes = list()
    textures = list()
    for side, size_x, size_y in projections:
        plane, texture = project_to_plane(obj, side, (size_x, size_y))
        planes.append(plane)
        textures.append(texture)

    obj, texture = combine_planes(obj_name + '_lod', planes, textures)
    return obj, texture
