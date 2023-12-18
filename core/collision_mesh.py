import bpy
import bmesh

from itertools import cycle
from .bf2.bf2_collmesh import BF2CollMesh
from .utils import delete_object_if_exists

def import_collisionmesh(context, mesh_file, geom=0, subgeom=0, lod=0, reload=False, bsp=False):
    bf2_mesh = BF2CollMesh(mesh_file)
    name = bf2_mesh.name
    bf2_lod = bf2_mesh.geoms[geom].subgeoms[subgeom].lods[lod]

    if bsp:
        _import_bsp(context, bf2_lod, bsp_name=f'{name}_BSP', reload=reload)
        return

    if reload: delete_object_if_exists(name)

    verts = [(v.x, v.z, v.y) for v in bf2_lod.verts]
    faces = [(f.v3, f.v2, f.v1) for f in bf2_lod.faces]
    face_materials = [f.material for f in bf2_lod.faces]

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

    cycol = cycle([[0.267004, 0.004874, 0.329415, 1.],
                    [0.282623, 0.140926, 0.457517, 1.],
                    [0.253935, 0.265254, 0.529983, 1.],
                    [0.206756, 0.371758, 0.553117, 1.],
                    [0.163625, 0.471133, 0.558148, 1.],
                    [0.127568, 0.566949, 0.550556, 1.],
                    [0.134692, 0.658636, 0.517649, 1.],
                    [0.266941, 0.748751, 0.440573, 1.],
                    [0.477504, 0.821444, 0.318195, 1.],
                    [0.741388, 0.873449, 0.149561, 1.]])

    for i in set(face_materials):
        mat_name = f'{bf2_mesh.name}_collmesh_material_{i}'
        try:
            material = bpy.data.materials[mat_name]
            bpy.data.materials.remove(material, do_unlink=True)
        except:
            pass
        material = bpy.data.materials.new(mat_name)
        mesh.materials.append(material)
        
        material.use_nodes=True
        principled_BSDF = material.node_tree.nodes.get('Principled BSDF')
        principled_BSDF.inputs[0].default_value = tuple(next(cycol))

    collmesh = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(collmesh)

def _import_bsp(context, bf2_lod, bsp_name, reload=False):
    bsp = bf2_lod.bsp
    verts = [(v.x, v.z, v.y) for v in bf2_lod.verts]

    def _import_bsp_node(node, parent_obj):
        node_idx = bsp._nodes.index(node)
        for i, child in enumerate(node.children):
            p = '|F' if i == 0 else '|B'
            name = bsp_name + '_' + str(node_idx) + p
            if child is None: # leaf
                faces = [(f.v3, f.v2, f.v1) for f in node.faces[i]]

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
    
    context.scene.collection.objects.link(root_obj)