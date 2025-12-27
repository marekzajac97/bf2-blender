import bpy # type: ignore
import bmesh # type: ignore
import os
from mathutils import Matrix # type: ignore
from math import sqrt
from .exceptions import ImportException


def import_water_plane(context, heixels, water_level, name='WaterPlane'):
    bm = bmesh.new()
    bm.verts.new((0, 0, water_level))
    bm.verts.new((0, heixels, water_level))
    bm.verts.new((heixels, heixels, water_level))
    bm.verts.new((heixels, 0, water_level))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.new(bm.verts[i] for i in ((0, 1, 2, 3)))

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    water_uv_layer = mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        vertex = mesh.vertices[loop.vertex_index]
        water_uv_layer.data[loop.index].uv = (vertex.co[0] / heixels, vertex.co[1] / heixels)

    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)


def import_heightmap(context, fname, bit_res=16, scale=(1, 1, 1), water_level=None):
    with open(fname, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()

        bytes_per_heixel = int(bit_res / 8)
        world_dim = int(sqrt(file_size / bytes_per_heixel))

        if file_size != world_dim * world_dim * bytes_per_heixel:
            raise ImportException("not a valid heightmap, file size is incorrect")

        f.seek(0, 0)
        raw_data = f.read()

        # center it
        offset_x = (world_dim - 1) * scale[0] / 2
        offset_y = (world_dim - 1) * scale[1] / 2

        bm = bmesh.new()
        for x in range(world_dim):
            for y in range(world_dim):
                idx = bytes_per_heixel * (x + y * world_dim)
                unsigned = int.from_bytes(raw_data[idx:idx+bytes_per_heixel], byteorder='little')
                height = unsigned * scale[2]
                bm.verts.new((x * scale[0] - offset_x, y * scale[1] - offset_y, height))

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        for x in range(world_dim - 1):
            for y in range(world_dim - 1):
                index = y * world_dim + x
                if (y + x) % bytes_per_heixel == 0:
                    bm.faces.new(bm.verts[i] for i in (index + 1, index, index + world_dim +1 ))
                    bm.faces.new(bm.verts[i] for i in (index + world_dim + 1, index, index + world_dim))
                else:
                    bm.faces.new(bm.verts[i] for i in (index + 1, index , index + world_dim))
                    bm.faces.new(bm.verts[i] for i in (index + world_dim + 1, index + 1, index + world_dim))

    name = os.path.splitext(os.path.basename(fname))[0]
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    terrain_uv_layer = mesh.uv_layers.new(name='UVMap')

    for loop in mesh.loops:
        vertex = mesh.vertices[loop.vertex_index]
        terrain_uv_layer.data[loop.index].uv = (vertex.co[0], vertex.co[1])

    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)

    if water_level:
        import_water_plane(context, world_dim, water_level)

    return obj

# TODO
# def export_heightmap(obj, fname, world_size, y_scale=1.0):        
#         matrix_cpy = obj.matrix_world.copy()

#         obj.data.transform(obj.matrix_world)
#         obj.matrix_world = Matrix.Identity(4)

#         try:
#             with open(fname, "rb") as f:
#                 for y in range(0, world_size, 4):
#                     for x in range(0, world_size, 4):
#                         result, location, normal, index = obj.ray_cast([x, y, 1000], [0, 0, -1])
#                         height=0
#                         if result:
#                             height = min(max(location[2], 0), 256 * y_scale)
#                         int16 = round(65535 * height/ (256 * y_scale))
#                         int8_2 = int16 >> 8
#                         int8_1 = int16 & 255
#                         f.write(int.to_bytes(int8_1))
#                         f.write(int.to_bytes(int8_2))
#         except:
#             raise
#         finally:
#             obj.data.transform(matrix_cpy.inverted())
#             obj.matrix_world = matrix_cpy
