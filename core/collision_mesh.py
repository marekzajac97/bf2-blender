import bpy
import bmesh

from itertools import cycle
from .bf2.bf2_collmesh import BF2CollMesh, BF2CollMeshException, GeomPart, Geom, Col, Face, Vec3
from .utils import delete_object_if_exists, delete_material_if_exists, delete_mesh_if_exists, check_prefix
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

def _build_col_prefix(geompart=None, geom=None, col=None):
    if geompart is not None and geom is not None and col is not None:
        return f'N{geompart}G{geom}C{col}__'
    elif geompart is not None and geom is not None:
        return f'N{geompart}G{geom}__'
    elif geompart is not None:
        return f'N{geompart}__'
    else:
        return ''

def import_collisionmesh(context, mesh_file, name='', make_objects=True, reload=False):
    """Import all meshes from collisionmesh file as Blender's Mesh objects"""
    try:
        bf2_mesh = BF2CollMesh(mesh_file)
    except BF2CollMeshException as e:
        raise ImportException(str(e)) from e

    name = name or bf2_mesh.name

    materials = _import_collisionmesh_dummy_materials(name, bf2_mesh)
    geom_parts = list()
    for geompart_idx, geompart in enumerate(bf2_mesh.geom_parts):
        geoms = list()
        geom_parts.append(geoms)
        for geom_idx, geom in  enumerate(geompart.geoms):
            cols = dict()
            geoms.append(cols)
            for col_idx, bf2_col in enumerate(geom.cols):
                prfx = _build_col_prefix(geompart_idx, geom_idx, col_idx)
                col_name = prfx + name
                if reload: delete_mesh_if_exists(col_name)
                cols[bf2_col.col_type] = _import_collisionmesh_col(col_name, bf2_col, materials)

    if make_objects:
        _make_objects(context, name, geom_parts, reload)

    return geom_parts, materials

def _make_objects(context, name, geom_parts, reload):
    """Create Blender object hierarchy for imported meshes"""
    collmesh_name = f'{name}_collmesh' # to avoid object name conflicts when loaded together with geometry

    if reload: delete_object_if_exists(collmesh_name)
    root_obj = bpy.data.objects.new(collmesh_name, None)
    context.scene.collection.objects.link(root_obj)

    for geompart_idx, geompart in enumerate(geom_parts):
        geompart_name = _build_col_prefix(geompart_idx) + name
        if reload: delete_object_if_exists(geompart_name)
        geompart_obj = bpy.data.objects.new(geompart_name, None)
        geompart_obj.parent = root_obj
        context.scene.collection.objects.link(geompart_obj)

        for geom_idx, geom in enumerate(geompart):
            geom_name = _build_col_prefix(geompart_idx, geom_idx) + name
            if reload: delete_object_if_exists(geom_name)
            geom_obj = bpy.data.objects.new(geom_name, None)
            geom_obj.parent = geompart_obj
            context.scene.collection.objects.link(geom_obj)

            for col_idx, col_mesh in geom.items():
                col_name = _build_col_prefix(geompart_idx, geom_idx, col_idx) + name
                if reload: delete_object_if_exists(col_name)
                col_obj = bpy.data.objects.new(col_name, col_mesh)
                col_obj.parent = geom_obj
                context.scene.collection.objects.link(col_obj)

    return root_obj

def _import_collisionmesh_dummy_materials(name, bf2_mesh):
    material_indexes = set()
    for geompart in bf2_mesh.geom_parts:
        for geom in geompart.geoms:
            for col in geom.cols:
                material_indexes.update(set([f.material for f in col.faces]))

    cycol = cycle(MATERIAL_COLORS)

    materials = dict()
    for i in material_indexes:
        mat_name = f'{name}_collmesh_material_{i}'
        delete_material_if_exists(mat_name)
        material = bpy.data.materials.new(mat_name)     
        material.use_nodes = True
        principled_BSDF = material.node_tree.nodes.get('Principled BSDF')
        principled_BSDF.inputs[0].default_value = tuple(next(cycol))
        materials[i] = material

    return materials

def _import_collisionmesh_col(name, bf2_col, materials):
    # swap order
    verts = [(v.x, v.z, v.y) for v in bf2_col.verts]
    faces = [(f.verts[2], f.verts[1], f.verts[0]) for f in bf2_col.faces]
    face_materials = [f.material for f in bf2_col.faces]

    # map bf2 material index to blender material index
    material_indexes = list(set(face_materials))
    bf2_mat_idx_to_blend_mat_idx = dict()
    for blender_idx, bf2_index in enumerate(material_indexes):
        bf2_mat_idx_to_blend_mat_idx[bf2_index] = blender_idx

    bm = bmesh.new()
    for vert in verts:
        bm.verts.new(vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    for face, bf2_mat_idx in zip(faces, face_materials):
        face_verts = [bm.verts[i] for i in face]

        try:
            bm_face = bm.faces.new(face_verts)
        except ValueError:
            pass # XXX sometimes mesh hsa duplicated faces or face duplicated verts...

        bm_face.material_index = bf2_mat_idx_to_blend_mat_idx[bf2_mat_idx]

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)

    # add materials to mesh
    for bf2_index in material_indexes:
        bf2_mat_idx_to_blend_mat_idx[bf2_index] = len(mesh.materials)
        mesh.materials.append(materials[bf2_index])

    return mesh

def _collect_collisionmesh_nodes_geoms_lods(collmesh_obj):
    if not collmesh_obj.children:
        raise ExportException(f"collisionmesh '{collmesh_obj.name}' has no children (nodes)!")

    geom_parts = list()

    mesh_geomparts = dict()
    for geompart_obj in collmesh_obj.children:
        geompart_idx = check_prefix(geompart_obj.name, ('N',))
        if geompart_idx in mesh_geomparts:
            raise ExportException(f"collisionmesh '{collmesh_obj.name}' has duplicated N{geompart_idx}")
        mesh_geomparts[geompart_idx] = geompart_obj
    for _, geompart_obj in sorted(mesh_geomparts.items()):
        geoms = list()
        geom_parts.append(geoms)

        if not geompart_obj.children:
            raise ExportException(f"node '{geompart_obj.name}' has no children (geoms)!")

        mesh_geoms = dict()
        for geom_obj in geompart_obj.children:
            _, geom_idx = check_prefix(geom_obj.name, ('N', 'G'))
            if geom_idx in mesh_geoms:
                raise ExportException(f"geom '{geom_obj.name}' has duplicated G{geom_idx}")
            mesh_geoms[geom_idx] = geom_obj
        for _, geom_obj in sorted(mesh_geoms.items()):
            cols = dict()
            geoms.append(cols)

            mesh_cols = dict()
            for col_obj in geom_obj.children:
                _, _, col_idx = check_prefix(col_obj.name, ('N', 'G', 'C'))
                if col_idx in mesh_cols:
                    raise ExportException(f"col '{col_obj.name}' has duplicated C{col_idx}")
                mesh_cols[col_idx] = col_obj
            for col_idx, col_obj in sorted(mesh_cols.items()):
                cols[col_idx] = col_obj
    return geom_parts

def _collect_collisionmesh_dummy_materials(geom_parts):
    materials = set()
    for geompart in geom_parts:
        for geom in geompart:
            for col_obj in geom.values():
                mesh = col_obj.data
                for p in mesh.polygons:
                    mat_name = mesh.materials[p.material_index].name
                    materials.add(mat_name)
    material_to_index = dict()
    for i, mat in enumerate(materials):
        material_to_index[mat] = i
    return material_to_index

def export_collisionmesh(root_obj, mesh_file, geom_parts=None):
    collmesh = BF2CollMesh(name=root_obj.name)

    if geom_parts is None:
        geom_parts = _collect_collisionmesh_nodes_geoms_lods(root_obj)

    material_to_index = _collect_collisionmesh_dummy_materials(geom_parts)

    for geoms in geom_parts:
        geompart = GeomPart()
        collmesh.geom_parts.append(geompart)
        for cols in geoms:
            geom = Geom()
            geompart.geoms.append(geom)
            for col_idx, col_obj in cols.items():
                col = _export_collistionmesh_col(col_idx, col_obj, material_to_index)
                geom.cols.append(col)

    collmesh.export(mesh_file)

    return collmesh, material_to_index

def _export_collistionmesh_col(col_idx, mesh_obj, material_to_index):
    col = Col()
    mesh = mesh_obj.data
    if mesh is None:
        raise ExportException(f"col '{mesh_obj.name}' has no mesh data!")

    if col_idx < 0 or col_idx > 3:
        raise ExportException(f"'{mesh_obj.name}' Invalid col index '{col_idx}, must be in 0-3")

    col.col_type = col_idx
    for v in mesh.vertices:
        vert = Vec3(v.co[0], v.co[2], v.co[1])
        col.verts.append(vert)
        col.vert_materials.append(0)
    for p in mesh.polygons:
        vert_indexes = (p.vertices[2], p.vertices[1], p.vertices[0])
        mat_name = mesh.materials[p.material_index].name
        material_index = material_to_index[mat_name]
        face = Face(vert_indexes, material_index)
        col.faces.append(face)
        for v in vert_indexes:
            col.vert_materials[v] = material_index
    return col

# debug stuff
def _import_bsp(context, bf2_col, bsp_name, reload=False):
    bsp = bf2_col.bsp
    verts = [(v.x, v.z, v.y) for v in bf2_col.verts]

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
