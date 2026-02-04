import bpy # type: ignore
import bmesh # type: ignore

from os import path
from itertools import cycle
from .bf2.bf2_collmesh import BF2CollMesh, BF2CollMeshException, GeomPart, Geom, Col, Face, Vec3
from .utils import (delete_object,
                    delete_object_if_exists,
                    delete_material_if_exists,
                    delete_mesh_if_exists,
                    check_prefix,
                    invert_face,
                    are_backfaces,
                    apply_modifiers as _apply_modifiers,
                    triangulate as _triangulate,
                    DEFAULT_REPORTER)
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

def import_collisionmesh(context, mesh_file, **kwargs):
    importer = CollMeshImporter(mesh_file, **kwargs)
    importer.import_collmesh()
    return importer.make_objects(context) 

class CollMeshImporter:
    def __init__(self, mesh_file, name='',
                 reload=False,
                 load_backfaces=True,
                 reporter=DEFAULT_REPORTER):
        self.mesh_file = mesh_file
        self.name = name
        self.reload = reload
        self.load_backfaces = load_backfaces
        self.bf2_mesh = None
        self.materials = None
        self.geom_parts = None
        self.reporter = reporter

    def import_collmesh(self):
        try:
            self.bf2_mesh = BF2CollMesh(self.mesh_file)
        except BF2CollMeshException as e:
            raise ImportException(str(e)) from e

        self.name = self.name or self.bf2_mesh.name
        self.materials = self._import_materials()

        self.geom_parts = list()
        for geompart_idx, geompart in enumerate(self.bf2_mesh.geom_parts):
            geoms = list()
            self.geom_parts.append(geoms)
            for geom_idx, geom in  enumerate(geompart.geoms):
                cols = dict()
                geoms.append(cols)
                for col_idx, bf2_col in enumerate(geom.cols):
                    prfx = _build_col_prefix(geompart_idx, geom_idx, col_idx)
                    col_name = prfx + self.name
                    if self.reload: delete_mesh_if_exists(col_name)
                    cols[bf2_col.col_type] = self._import_col(col_name, bf2_col)

        return self.geom_parts, self.materials

    def make_objects(self, context):
        """Create Blender object hierarchy for imported meshes"""

        if self.reload: delete_object_if_exists(self.name)
        root_obj = bpy.data.objects.new(self.name, None)
        context.scene.collection.objects.link(root_obj)

        for geompart_idx, geompart in enumerate(self.geom_parts):
            geompart_name = _build_col_prefix(geompart_idx) + self.name
            if self.reload: delete_object_if_exists(geompart_name)
            geompart_obj = bpy.data.objects.new(geompart_name, None)
            geompart_obj.parent = root_obj
            context.scene.collection.objects.link(geompart_obj)

            for geom_idx, geom in enumerate(geompart):
                geom_name = _build_col_prefix(geompart_idx, geom_idx) + self.name
                if self.reload: delete_object_if_exists(geom_name)
                geom_obj = bpy.data.objects.new(geom_name, None)
                geom_obj.parent = geompart_obj
                context.scene.collection.objects.link(geom_obj)

                for col_idx, col_mesh in geom.items():
                    col_name = _build_col_prefix(geompart_idx, geom_idx, col_idx) + self.name
                    if self.reload: delete_object_if_exists(col_name)
                    col_obj = bpy.data.objects.new(col_name, col_mesh)
                    col_obj.parent = geom_obj
                    context.scene.collection.objects.link(col_obj)

        return root_obj

    def _import_materials(self):
        material_indexes = set()
        for geompart in self.bf2_mesh.geom_parts:
            for geom in geompart.geoms:
                for col in geom.cols:
                    material_indexes.update(set([f.material for f in col.faces]))

        cycol = cycle(MATERIAL_COLORS)

        materials = dict()
        for i in material_indexes:
            # proper material names are in .con so it will be corrected by the ObjectTemplate importer
            mat_name = f'{self.name}_collmesh_material_{i}'
            delete_material_if_exists(mat_name)
            material = bpy.data.materials.new(mat_name)     
            material.use_nodes = True
            principled_BSDF = material.node_tree.nodes.get('Principled BSDF')
            principled_BSDF.inputs[0].default_value = tuple(next(cycol))
            materials[i] = material

        return materials

    def _import_col(self, name, bf2_col):
        # swap order
        verts = [(v.x, v.z, v.y) for v in bf2_col.verts]
        faces = [face.verts for face in bf2_col.faces]
        face_materials = [face.material for face in bf2_col.faces]

        # map bf2 material index to blender material index
        material_indexes = list(set(face_materials))
        bf2_mat_idx_to_blend_mat_idx = dict()
        for blender_idx, bf2_index in enumerate(list(material_indexes)):
            bf2_mat_idx_to_blend_mat_idx[bf2_index] = blender_idx

        bm = bmesh.new()
        for vert in verts:
            bm.verts.new(vert)

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        fucked_up_faces = 0
        double_sided_faces = set()
        for face, bf2_mat_idx in zip(faces, face_materials):
            face_verts = [bm.verts[i] for i in face]
            material_index = bf2_mat_idx_to_blend_mat_idx[bf2_mat_idx]

            try:
                bm_face = bm.faces.new(face_verts)
                bm_face.material_index = material_index
            except ValueError:
                # duplicate face.. or vert, lets find out
                if not self.load_backfaces:
                    fucked_up_faces += 1
                    continue
                if len(set(face_verts)) != 3: # duplicate verts
                    fucked_up_faces += 1
                    continue

                bm.faces.index_update()
                bm_face_verts = [vert.index for vert in face_verts]
                for other_bm_face in bm.faces:
                    if are_backfaces(bm_face_verts, [vert.index for vert in other_bm_face.verts]):
                        if material_index != other_bm_face.material_index: # XXX: could they differ ??
                            raise ImportException("Attempted to create a backface with different material index, aborting")
                        double_sided_faces.add(other_bm_face.index)
                        break
                else:
                    # must be a duplicate face
                    fucked_up_faces += 1

        if fucked_up_faces:
            self.reporter.warning(f"'{name}': Skipped {fucked_up_faces} invalid faces")

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)

        # mark faces with backfaces
        if double_sided_faces:
            animuv_matrix_index = mesh.attributes.new('backface', 'BOOLEAN', 'FACE')
            animuv_matrix_index.data.foreach_set('value', [poly.index in double_sided_faces for poly in mesh.polygons])

        # add materials to mesh
        for bf2_index in material_indexes:
            bf2_mat_idx_to_blend_mat_idx[bf2_index] = len(mesh.materials)
            mesh.materials.append(self.materials[bf2_index])

        return mesh

def export_collisionmesh(root_obj, mesh_file, **kwargs):
    exporter = CollMeshExporter(root_obj, mesh_file, **kwargs)
    return exporter.export_collmesh()

TMP_PREFIX = "TMP__"

class CollMeshExporter:
    def __init__(self, root_obj, mesh_file,
                 geom_parts=None,
                 save_backfaces=True,
                 apply_modifiers=False,
                 triangulate=False,
                 reporter=DEFAULT_REPORTER):
        self.root_obj = root_obj
        self.mesh_file = mesh_file
        self.geom_parts = geom_parts
        self.save_backfaces = save_backfaces
        self.apply_modifiers = apply_modifiers
        self.triangulate = triangulate
        self.reporter = reporter

    @staticmethod
    def _make_temp_object(obj, prefix=TMP_PREFIX):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action='DESELECT')
        hide = obj.hide_get()
        obj.hide_set(False)
        obj.select_set(True)
        name = obj.name
        obj.name = prefix + name # rename original
        bpy.ops.object.duplicate() # duplicate
        new_obj = bpy.context.view_layer.objects.active
        new_obj.name = name # set copy name to original object
        obj.hide_set(hide)
        return new_obj

    @staticmethod
    def _revert_temp_object(obj, prefix=TMP_PREFIX):
        name = obj.name
        org_obj = bpy.data.objects[prefix + obj.name]
        delete_object(obj, recursive=False)
        org_obj.name = name

    def _revert_temp_geom_lods(self):
        for geoms in self.geom_parts:
            for cols in geoms:
                for col_obj in cols.values():
                    self._revert_temp_object(col_obj)

    def _make_temp_nodes_geoms_lods(self):
        new_geom_parts = list()
        for geoms in self.geom_parts:
            new_geoms = list()
            new_geom_parts.append(new_geoms)
            for cols in geoms:
                new_cols = dict()
                new_geoms.append(new_cols)
                for col_idx, col_obj in cols.items():
                    new_cols[col_idx] = self._make_temp_object(col_obj)
        return new_geom_parts

    @staticmethod
    def _collect_nodes_geoms_lods(collmesh_obj):
        if not collmesh_obj.children:
            raise ExportException(f"collisionMesh '{collmesh_obj.name}' has no children (nodes)!")

        geom_parts = list()

        mesh_geomparts = dict()
        for geompart_obj in collmesh_obj.children:
            geompart_idx = check_prefix(geompart_obj.name, ('N',))
            if geompart_idx in mesh_geomparts:
                raise ExportException(f"collisionMesh '{collmesh_obj.name}' has duplicated N{geompart_idx}")
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
                    if col_obj.data is None:
                        raise ExportException(f"col '{col_obj.name}' has no mesh data!")
                    mesh_cols[col_idx] = col_obj
                for col_idx, col_obj in sorted(mesh_cols.items()):
                    cols[col_idx] = col_obj
        return geom_parts

    def export_collmesh(self):
        if self.geom_parts:
            return self._export_collmesh()
        else:
            self.geom_parts = self._collect_nodes_geoms_lods(self.root_obj)
            self.geom_parts = self._make_temp_nodes_geoms_lods()
            try:
                return self._export_collmesh()
            except Exception:
                raise
            finally:
                self._revert_temp_geom_lods()

    def _collect_materials(self):
        # important to preserve material order as they appear in cols
        # for compatibility with 3ds max!
        material_to_index = dict()
        for geompart in self.geom_parts:
            for geom in geompart:
                for _, col_obj in sorted(geom.items()):
                    mesh = col_obj.data
                    for p in mesh.polygons:
                        mat_name = mesh.materials[p.material_index].name
                        if mat_name in material_to_index:
                            continue
                        material_to_index[mat_name] = len(material_to_index)
        return material_to_index

    def _export_collmesh(self):
        bf2_collmesh = BF2CollMesh(name=self.root_obj.name)
        self.material_to_index = self._collect_materials()

        for geoms in self.geom_parts:
            geompart = GeomPart()
            bf2_collmesh.geom_parts.append(geompart)
            for cols in geoms:
                geom = Geom()
                geompart.geoms.append(geom)
                for col_idx, col_obj in cols.items():
                    col = self._export_col(col_idx, col_obj)
                    geom.cols.append(col)

        try:
            bf2_collmesh.export(self.mesh_file)
        except BF2CollMeshException as e:
            raise ExportException(str(e)) from e

        return bf2_collmesh

    def _export_col(self, col_idx, mesh_obj):
        col = Col()
        mesh = mesh_obj.data

        if self.apply_modifiers:
            _apply_modifiers(mesh_obj)
        if self.triangulate:
            _triangulate(mesh_obj)

        backface_attr = mesh.attributes.get('backface') if self.save_backfaces else None

        if col_idx < 0 or col_idx > 3:
            raise ExportException(f"'{mesh_obj.name}' Invalid col index '{col_idx}, must be in 0-3")

        col.col_type = col_idx
        for v in mesh.vertices:
            vert = Vec3(v.co[0], v.co[2], v.co[1])
            col.verts.append(vert)
            col.vert_materials.append(0)
        for p in mesh.polygons:
            if p.loop_total > 3:
                raise ExportException(f"{mesh_obj.name}: Exporter does not support polygons with more than 3 vertices! It must be triangulated")
            vert_indexes = tuple(p.vertices)
            mat_name = mesh.materials[p.material_index].name
            material_index = self.material_to_index[mat_name]
            face = Face(vert_indexes, material_index)
            col.faces.append(face)
            if backface_attr and backface_attr.data[p.index].value:
                backface = Face(invert_face(vert_indexes), material_index)
                col.faces.append(backface)
            for v in vert_indexes:
                col.vert_materials[v] = material_index
        return col

# debug stuff

def import_bsp(context, mesh_file, part=0, geom=0, col=0, reload=False):
    bf2_mesh = BF2CollMesh(mesh_file)
    _import_bsp(context, bf2_mesh.geom_parts[part].geoms[geom].cols[col], bf2_mesh.name, reload)

def _import_bsp(context, bf2_col, bsp_name, reload=False):
    bsp = bf2_col.bsp
    verts = [(v.x, v.z, v.y) for v in bf2_col.verts]

    def _import_bsp_node(node, parent_obj):
        for i, child in enumerate(node.children):
            p = '|F' if i == 0 else '|B'
            name = bsp_name + '_' + p
            if child is None: # leaf
                faces = [f.verts for f in node.faces[i]]

                bm = bmesh.new()
                for vert in verts:
                    bm.verts.new(vert)

                bm.verts.ensure_lookup_table()
                bm.verts.index_update()

                for face in faces:
                    face_verts = [bm.verts[i] for i in face]
                    bm.faces.new(face_verts)

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
    def _link_recursive(obj):
        context.scene.collection.objects.link(obj)
        for child in obj.children:
            _link_recursive(child)

    _link_recursive(root_obj)
