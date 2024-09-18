import bpy # type: ignore
import bmesh # type: ignore

from .bf2.bf2_occluder_planes import BF2OccluderPlanes, BF2OccluderPlanesException, Group
from .bf2.bf2_common import Vec3
from .exceptions import ImportException, ExportException
from .utils import delete_object_if_exists

def import_occluders(context, mesh_file, name='', reload=False):
    try:
        bf2_occ = BF2OccluderPlanes(mesh_file)
    except BF2OccluderPlanesException as e:
        raise ImportException(str(e)) from e
    name = name or bf2_occ.name
    if reload: delete_object_if_exists(name)

    mesh = bpy.data.meshes.new(name)
    mesh_obj = bpy.data.objects.new(name, mesh)
    bm = bmesh.new()

    vertex_offset = 0
    for occ_group in bf2_occ.groups:
        # swap order
        verts = [(v.x, v.z, v.y) for v in occ_group.verts]
        for vert in verts:
            bm.verts.new(vert)

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        for face in occ_group.planes:
            face_verts = [bm.verts[v + vertex_offset] for v in face]
            bm.faces.new(face_verts)
        vertex_offset += len(verts)

    bm.to_mesh(mesh)

    # make vertex groups
    vertex_offset = 0
    for i, occ_group in enumerate(bf2_occ.groups):
        vertex_range = list(range(vertex_offset, vertex_offset + len(occ_group.verts)))
        vg = mesh_obj.vertex_groups.new(name=f'OCC_GROUP_{i}')
        vg.add(vertex_range, 1.0, "REPLACE")
        vertex_offset += len(occ_group.verts)

    context.scene.collection.objects.link(mesh_obj)
    return mesh_obj

def export_occluders(obj, mesh_file):
    occ = BF2OccluderPlanes(name=obj.name)

    mesh = obj.data
    verts = list()

    for v in mesh.vertices:
        vert = Vec3(v.co[0], v.co[2], v.co[1])
        verts.append(vert)

    vg_idx_to_polygons = dict()
    for poly in mesh.polygons:
        if poly.loop_total != 4:
            raise ExportException(f"{obj.name}: Occluder planes must be quads!")

        if obj.vertex_groups:
            face_vert_groups = list()
            for v_idx in poly.vertices:
                v = mesh.vertices[v_idx]
                s = set([g.group for g in v.groups])
                face_vert_groups.append(s)

            u = set.intersection(*face_vert_groups)
            if len(u) != 1:
                raise ExportException(f"{obj.name}: All vertices of the occluder plane must belong to the same vertex group!")
            vg_idx = tuple(u)[0]
        else:
            vg_idx = 0

        vg_polygons = vg_idx_to_polygons.setdefault(vg_idx, list())
        vg_polygons.append(poly)

    for vg_idx, polygons in vg_idx_to_polygons.items():
        occ_group = Group()
        occ.groups.append(occ_group)

        vert_mapping = dict()
        vert_index = 0
        for poly in polygons:
            indices = list()
            for v_idx in poly.vertices:
                if v_idx not in vert_mapping:  
                    vert_mapping[v_idx] = vert_index
                    vert_index += 1
                indices.append(vert_mapping[v_idx])
            occ_group.planes.append(tuple(indices))

        for v_idx, _ in sorted(vert_mapping.items(), key=lambda item: item[1]):
            v = mesh.vertices[v_idx]
            vert = Vec3(v.co[0], v.co[2], v.co[1])
            occ_group.verts.append(vert)

    occ.export(mesh_file)
