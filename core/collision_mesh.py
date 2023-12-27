import bpy
import bmesh

from itertools import cycle
from .bf2.bf2_collmesh import BF2CollMesh, BF2CollMeshException, Geom, SubGeom, Lod, Face, Vec3
from .utils import delete_object_if_exists, check_suffix
from .exceptions import ImportException, ExportException

MATERIAL_COLORS = [
    [0.267004, 0.004874, 0.329415, 1.],
    [0.282623, 0.140926, 0.457517, 1.],
    [0.253935, 0.265254, 0.529983, 1.],
    [0.206756, 0.371758, 0.553117, 1.],
    [0.163625, 0.471133, 0.558148, 1.],
    [0.127568, 0.566949, 0.550556, 1.],
    [0.134692, 0.658636, 0.517649, 1.],
    [0.266941, 0.748751, 0.440573, 1.],
    [0.477504, 0.821444, 0.318195, 1.],
    [0.741388, 0.873449, 0.149561, 1.]
]

def import_collisionmesh(context, mesh_file, reload=False):
    try:
        bf2_mesh = BF2CollMesh(mesh_file)
    except BF2CollMeshException as e:
        raise ImportException(str(e)) from e

    name = bf2_mesh.name

    collmesh_name = f'{name}_collmesh' # to avoid object name conflicts when loaded together with geometry
    if reload: delete_object_if_exists(collmesh_name)
    collmesh_obj = bpy.data.objects.new(collmesh_name, None)
    context.scene.collection.objects.link(collmesh_obj)

    cycol = cycle(MATERIAL_COLORS)

    for geom_idx, geom in enumerate(bf2_mesh.geoms):
        geom_name = f'{name}_geom{geom_idx}'
        if reload: delete_object_if_exists(geom_name)
        geom_obj = bpy.data.objects.new(geom_name, None)
        geom_obj.parent = collmesh_obj
        context.scene.collection.objects.link(geom_obj)

        for subgeom_idx, subgeom in enumerate(geom.subgeoms):
            subgeom_name = f'{geom_name}_subgeom{subgeom_idx}'
            if reload: delete_object_if_exists(subgeom_name)
            subgeom_obj = bpy.data.objects.new(subgeom_name, None)
            subgeom_obj.parent = geom_obj
            context.scene.collection.objects.link(subgeom_obj)

            for lod_idx, lod in enumerate(subgeom.lods):
                lod_name = f'{subgeom_name}_lod{lod_idx}'
                if reload: delete_object_if_exists(lod_name)
                materials = _import_collisionmesh_dummy_materials(name, cycol, lod.faces)
                lod_obj = _import_collisionmesh_lod(lod_name, lod.verts, lod.faces, materials, reload=reload)
                lod_obj.parent = subgeom_obj
                context.scene.collection.objects.link(lod_obj)

def _import_collisionmesh_dummy_materials(name, cycol, lod_faces):
    face_materials = set([f.material for f in lod_faces])

    materials = list()
    for i in face_materials:
        mat_name = f'{name}_material_{i}'
        if mat_name in bpy.data.materials:
            materials.append(bpy.data.materials[mat_name])
            continue # already imported
        material = bpy.data.materials.new(mat_name)     
        material.use_nodes = True
        principled_BSDF = material.node_tree.nodes.get('Principled BSDF')
        principled_BSDF.inputs[0].default_value = tuple(next(cycol))
        materials.append(material)
    return materials

def _import_collisionmesh_lod(name, lod_verts, lod_faces, materials, reload=False):
    # swap order
    verts = [(v.x, v.z, v.y) for v in lod_verts]
    faces = [(f.verts[2], f.verts[1], f.verts[0]) for f in lod_faces]
    face_materials = [f.material for f in lod_faces]

    bm = bmesh.new()
    for vert in verts:
        bm.verts.new(vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    for face, mat in zip(faces, face_materials):
        face_verts = [bm.verts[i] for i in face]
        bm_face = bm.faces.new(face_verts)
        bm_face.material_index = mat

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    for i in set(face_materials):
        mesh.materials.append(materials[i])

    return bpy.data.objects.new(name, mesh)


def export_collisonmesh(context, mesh_file):
    collmesh_obj = context.view_layer.objects.active
    if collmesh_obj is None:
        raise ExportException("No object selected!")
    
    collmesh = BF2CollMesh(name=collmesh_obj.name)

    if not collmesh_obj.children:
        raise ExportException(f"collisionmesh '{collmesh_obj.name}' has no children (geoms)!")

    geoms = dict()
    for geom_obj in collmesh_obj.children:
        geom_idx = check_suffix(geom_obj.name, 'geom')
        if geom_idx in geoms:
            raise ExportException(f"collisionmesh '{collmesh_obj.name}' has duplicated geom{geom_idx}")
        geoms[geom_idx] = geom_obj
    for _, geom_obj in sorted(geoms.items()):
        geom = Geom()
        collmesh.geoms.append(geom)

        if not geom_obj.children:
            raise ExportException(f"geom '{geom_obj.name}' has no children (subgeoms)!")

        subgeoms = dict()
        for subgeom_obj in geom_obj.children:
            subgeom_idx = check_suffix(subgeom_obj.name, 'subgeom')
            if subgeom_idx in subgeoms:
                raise ExportException(f"geom '{geom_obj.name}' has duplicated subgeom{subgeom_idx}")
            subgeoms[subgeom_idx] = subgeom_obj
        for _, subgeom_obj in sorted(subgeoms.items()):
            subgeom = SubGeom()
            geom.subgeoms.append(subgeom)

            # it is possible for a subgeom to have no lods
            # although it is probably a result of the broken-ass DICE's max exporter
            # which creates them even when a geom has no _novis tree
            # TODO: check whether creating them affects anything
            lods = dict()
            for lod_obj in subgeom_obj.children:
                lod_idx = check_suffix(lod_obj.name, 'lod')
                if lod_idx in lods:
                    raise ExportException(f"lod '{lod_obj.name}' has duplicated lod{lod_idx}")
                lods[lod_idx] = lod_obj
            for lod_idx, lod_obj in sorted(lods.items()):
                lod = Lod()
                subgeom.lods.append(lod)
                mesh = lod_obj.data
                if mesh is None:
                    raise ExportException(f"lod '{lod_obj.name}' has no mesh data!")

                if lod_idx < 0 or lod_idx > 3:
                    raise ExportException(f"Invalid lod index '{lod_idx}, must be in 0-3")

                lod.coll_type = lod_idx
                for v in mesh.vertices:
                    vert = Vec3(v.co[0], v.co[2], v.co[1])
                    lod.verts.append(vert)
                    lod.vert_materials.append(0)
                for p in mesh.polygons:
                    vert_indexes = (p.vertices[2], p.vertices[1], p.vertices[0])
                    face = Face(vert_indexes, p.material_index)
                    lod.faces.append(face)
                    for v in vert_indexes:
                        lod.vert_materials[v] = p.material_index

    collmesh.export(mesh_file)

# debug stuff
def _import_bsp(context, bf2_lod, bsp_name, reload=False):
    bsp = bf2_lod.bsp
    verts = [(v.x, v.z, v.y) for v in bf2_lod.verts]

    def _import_bsp_node(node, parent_obj):
        node_idx = bsp._nodes.index(node)
        for i, child in enumerate(node.children):
            p = '|F' if i == 0 else '|B'
            name = bsp_name + '_' + str(node_idx) + p
            if child is None: # leaf
                faces = [(f.verts[2], f.verts[1], f.verts[0]) for f in node.faces[i]]

                bm = bmesh.new()
                for vert in verts:
                    bm.verts.new(vert)

                bm.verts.ensure_lookup_table()
                bm.verts.index_update()

                for face in faces:
                    face_verts = [bm.verts[i] for i in face]
                    bm_face = bm.faces.new(face_verts)
                    # bm_face.material_index = 0

                if reload: delete_object_if_exists(name)

                mesh = bpy.data.meshes.new(name)
                bm.to_mesh(mesh)

                obj = bpy.data.objects.new(name, mesh)
                obj.parent = parent_obj
            else:
                obj = bpy.data.objects.new(name, None)
                obj.parent = parent_obj
                _import_bsp_node(child, obj)

    if reload: delete_object_if_exists(bsp_name)

    root_obj = bpy.data.objects.new(bsp_name, None)
    _import_bsp_node(bsp.root, root_obj)

    # link
    def _link_recursive(self, obj):
        context.scene.collection.objects.link(obj)
        if obj.parent:
            self._link_recursive(obj)
    
    _link_recursive(root_obj)
