import bpy # type: ignore
import bmesh # type: ignore
import os
from mathutils import Matrix # type: ignore
from math import sqrt
from .exceptions import ImportException


def import_water_plane(context, world_size, water_level, name='WaterPlane'):
    bm = bmesh.new()
    bm.verts.new((0, 0, water_level))
    bm.verts.new((0, world_size, water_level))
    bm.verts.new((world_size, world_size, water_level))
    bm.verts.new((world_size, 0, water_level))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.new(bm.verts[i] for i in ((0, 1, 2, 3)))

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    water_uv_layer = mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        vertex = mesh.vertices[loop.vertex_index]
        water_uv_layer.data[loop.index].uv = (vertex.co[0] / world_size, vertex.co[1] / world_size)

    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)


def import_heightmap(context, fname, y_scale=1.0, water_level=None):
    with open(fname, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()

        world_size = int(sqrt(file_size * 8))
        world_dim = int(world_size / 4)

        if file_size != world_dim * world_dim * 2:
            raise ImportException("not a valid heightmap, file size is incorrect")

        f.seek(0, 0)
        raw_data = f.read()

        bm = bmesh.new()
        for x in range(world_dim):
            for y in range(world_dim):
                idx = 2 * (x + y * world_dim)
                unsigned16bit = raw_data[idx + 1] * 256 + raw_data[idx]
                height = 256 * y_scale * (unsigned16bit / 65535)
                bm.verts.new((x*4, y*4, height))

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        for x in range(world_dim - 1):
            for y in range(world_dim - 1):
                index = y * world_dim + x
                if (y+x) % 2 == 0:
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
        terrain_uv_layer.data[loop.index].uv = (vertex.co[0] / world_size, vertex.co[1] / world_size)

    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)

    if water_level:
        import_water_plane(context, world_size, water_level)

    return obj


def export_heightmap(obj, fname, world_size, y_scale=1.0):        
        matrix_cpy = obj.matrix_world.copy()

        obj.data.transform(obj.matrix_world)
        obj.matrix_world = Matrix.Identity(4)

        try:
            with open(fname, "rb") as f:
                for y in range(0, world_size, 4):
                    for x in range(0, world_size, 4):
                        result, location, normal, index = obj.ray_cast([x, y, 1000], [0, 0, -1])
                        height=0
                        if result:
                            height = min(max(location[2], 0), 256 * y_scale)
                        int16 = round(65535 * height/ (256 * y_scale))
                        int8_2 = int16 >> 8
                        int8_1 = int16 & 255
                        f.write(int.to_bytes(int8_1))
                        f.write(int.to_bytes(int8_2))
        except:
            raise
        finally:
            obj.data.transform(matrix_cpy.inverted())
            obj.matrix_world = matrix_cpy
