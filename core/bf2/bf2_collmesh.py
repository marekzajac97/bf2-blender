from typing import Dict, List, Tuple, Optional

from .fileutils import FileUtils
from .bsp_builder import BspBuilder
from .bf2_common import Vec3, calc_bounds, load_n_elems

import os

class BF2CollMeshException(Exception):
    pass

class Face:
    def __init__(self, verts, material):
        self.verts : Tuple[int] = verts
        self.material : int = material

    @classmethod
    def load(cls, f : FileUtils):
        v1 = f.read_word()
        v2 = f.read_word()
        v3 = f.read_word()
        verts = (v1, v2, v3)
        material = f.read_word()
        return cls(verts, material)
    
    def save(self, f : FileUtils):
        f.write_word(self.verts[0])
        f.write_word(self.verts[1])
        f.write_word(self.verts[2])
        f.write_word(self.material)

# https://en.wikipedia.org/wiki/Binary_space_partitioning
class BSP:
    class Node():
        def __init__(self, split_plane_val, split_plane_axis):
            self.split_plane_val : float = split_plane_val
            self.split_plane_axis : int = split_plane_axis
            # axis 0 == parallel to ZY plane and intersecting (val, _, _) point
            # axis 1 == parallel to XZ plane and intersecting (_, val, _) point
            # axis 2 == parallel to XY plane and intersecting (_, _, val) point

            self.parent : Optional[BSP.Node] = None # not set for root
            self.children : List[Optional[BSP.Node]] = [None, None] # front/back set only for a subtree Node
            self.faces : List[List[Face]] = [[], []]  # 2-element front/back set only for leaf Node
            # NOTE: in DICE's implementation if a face straddles the split plane it is added to both 'front' and 'back' sets

            # temporary raw import data
            self._face_refs_idx : List[List[int]] = [[], []]
            self._children_idx : List[int] = [None, None]

        @classmethod
        def load(cls, f : FileUtils):
            split_plane_val = f.read_float()
            _0x04 = f.read_dword()
            split_plane_axis = _0x04 & 0b11

            obj = cls(split_plane_val, split_plane_axis)

            for i in range(2):
                is_leaf = bool((4 << i) & _0x04)

                # face ref counts
                if is_leaf:
                    face_ref_count = _0x04 >> (i * 8 + 16) & 0xFF
                    face_ref_start = f.read_dword()
                    obj._face_refs_idx[i] = list(range(face_ref_start, face_ref_start + face_ref_count))
                    obj._children_idx[i] = None
                else:
                    obj._children_idx[i] = f.read_dword()
            return obj

        def load_children_and_faces(self, nodes, face_ref_to_face):
            for i in range(2):
                child_idx = self._children_idx[i]
                if child_idx is not None:
                    self.children[i] = nodes[child_idx]
                    self.children[i].parent = self
                else:
                    for j in self._face_refs_idx[i]:
                        self.faces[i].append(face_ref_to_face[j])

        def save(self, f : FileUtils, nodes, face_refs):
            f.write_float(self.split_plane_val)
            _0x04 = self.split_plane_axis & 0b11

            face_ref_start = [0, 0]
            for i in range(2):
                if self.children[i] == None:
                    face_ref_count = len(self.faces[i])
                    face_ref_start[i] = len(face_refs)
                    for face in self.faces[i]:
                        face_refs.append(face)

                    _0x04 |= 4 << i
                    _0x04 |= face_ref_count << (i * 8 + 16)
                else:
                    face_ref_start[i] = nodes.index(self.children[i]) 

            f.write_dword(_0x04)
            for i in range(2):
                f.write_dword(face_ref_start[i])

        def _to_string(self, level=0):
            prfx = '   ' * level
            ret = prfx + f' |* split_plane: {self.split_plane_val}|{self.split_plane_axis}\n'
            for i, child in enumerate(self.children):
                p = ' |F' if i == 0 else ' |B'
                if child is None: # leaf
                    faceset = '{'
                    for f in self.faces[i]:
                        if len(faceset) > 1:
                            faceset += ', '
                        faceset += str(f.verts)
                    faceset += '}'
                    ret += prfx + f'{p}  {faceset}\n'
                else:
                    ret += prfx + f'{p}\\\n'
                    ret += child._to_string(level+1)
            return ret
        
        def __str__(self):
            return self._to_string()

    def __init__(self, min, max, root):
        self.min : Vec3 = min
        self.max : Vec3 = max
        self.root : BSP.Node = root

    @classmethod
    def load(cls, f : FileUtils, faces : List[Face]):
        tree_min = Vec3.load(f)
        tree_max = Vec3.load(f)

        obj = cls(tree_min, tree_max, None)

        nodes = load_n_elems(f, BSP.Node, count=f.read_dword())
        face_refs = [f.read_word() for _ in range(f.read_dword())]

        face_ref_to_face : Dict[int, Face] = {}
        for i, face_ref in enumerate(face_refs):
            face_ref_to_face[i] = faces[face_ref]

        for node in nodes:
            node.load_children_and_faces(nodes, face_ref_to_face)

        obj.root = None
        for node in nodes:
            if node.parent is None:
                if obj.root is None:
                    obj.root = node
                else:
                    raise BF2CollMeshException("BSP: found multiple root nodes")
        if obj.root is None:
            raise BF2CollMeshException("BSP: root node not found")
        return obj

    def save(self, f : FileUtils, faces):
        self.min.save(f)
        self.max.save(f)

        def _get_nodes_list(node, node_list):
            node_list.append(node)
            for i in range(2):
                child = node.children[i]
                if child is not None:
                    _get_nodes_list(child, node_list)

        nodes = list()
        _get_nodes_list(self.root, nodes)
        face_refs = list()

        f.write_dword(len(nodes))

        for node in nodes:
            node.save(f, nodes, face_refs)

        f.write_dword(len(face_refs))
        for face in face_refs:
            f.write_word(faces.index(face))


    @staticmethod
    def build(verts, faces):
        builder = BspBuilder(verts, faces)

        def _copy(builder_node, parent=None):
            split_plane = builder_node.split_plane
            node = BSP.Node(split_plane.val, split_plane.axis)
            node.parent = parent
            children = builder_node.get_children()
            faces = builder_node.get_faces()

            for i in range(2):
                if children[i] is not None:
                    node.children[i] = _copy(children[i], node)
                else:
                    node.children[i] = None
                    node.faces[i] = faces[i]
            return node

        root = _copy(builder.root)
        mins = calc_bounds(verts, min)
        maxs = calc_bounds(verts, max)
        return BSP(mins, maxs, root)


class Lod:

    class CollType:
        PROJECTILE = 0
        VEHICLE = 1
        SOLDIER = 2
        AI = 3

    def __init__(self):
        self.coll_type : Lod.CollType = None

        self.faces : List[Face] = []
        self.verts : List[Vec3] = []
        self.vert_materials : List[int] = []

        # vertex bounds
        self.min = Vec3()
        self.max = Vec3()

        self.bsp : Optional[BSP] = None
        self.debug_mesh : Optional[List[int]] = None

    @classmethod
    def load(cls, f : FileUtils, version):
        obj = cls()
        obj.coll_type = f.read_dword()

        obj.faces = load_n_elems(f, Face, count=f.read_dword())

        vertnum = f.read_dword()
        obj.verts = load_n_elems(f, Vec3, count=vertnum)
        obj.vert_materials = [f.read_word() for _ in range(vertnum)]

        obj.min = Vec3.load(f)
        obj.max = Vec3.load(f)

        bsp_present = int(chr(f.read_byte())) # 0x30 or 0x31 (which is ASCII '0' or '1'... why DICE)

        if bsp_present:
            obj.bsp = BSP.load(f, obj.faces)

        # array of face indexes, can be -1 if unset, loaded only for ver >= 10, what exactly is this I don't know
        # used for buildDebugMeshes, we could probably skip this and export as ver 9 and BF2 will generate it
        if version[0] == 0 and version[1] >= 10:
            obj.debug_mesh = [f.read_dword(signed=True) for _ in range(f.read_dword())]
        return obj

    def save(self, f : FileUtils, update_bounds=True):
        f.write_dword(self.coll_type)
        f.write_dword(len(self.faces))
        for face in self.faces:
            face.save(f)
        f.write_dword(len(self.verts))
        for vert in self.verts:
            vert.save(f)

        if len(vert_mat) != len(self.verts):
            raise BF2CollMeshException("vertex materials don't match vertex count")

        for vert_mat in self.vert_materials:
            f.write_word(vert_mat)

        if update_bounds:
            calc_bounds(self.verts, min).save(f)
            calc_bounds(self.verts, max).save(f)
        else:
            self.min.save(f)
            self.max.save(f)

        f.write_byte(0x31)
        if self.bsp is None:
            self.bsp = BSP.build(self.verts, self.faces)
  
        self.bsp.save(f, self.faces)


class SubGeom:
    def __init__(self):
        self.lods : List[Lod] = []

    @classmethod
    def load(cls, f : FileUtils, version):
        obj = cls()
        obj.lods = load_n_elems(f, Lod, count=f.read_dword(), version=version)
        return obj
    
    def save(self, f : FileUtils):
        f.write_dword(len(self.lods))
        for lod in self.lods:
            lod.save(f)

class Geom:
    def __init__(self):
        self.subgeoms : List[SubGeom] = []

    @classmethod
    def load(cls, f : FileUtils, version):
        obj = cls()
        obj.subgeoms = load_n_elems(f, SubGeom, count=f.read_dword(), version=version)
        return obj

    def save(self, f : FileUtils):
        f.write_dword(len(self.subgeoms))
        for subgeom in self.subgeoms:
            subgeom.save(f)


class BF2CollMesh:
    def __init__(self, file='', name=''):
        self.geoms : List[Geom] = []

        if name:
            self.name = name
        elif file:
            self.name = os.path.splitext(os.path.basename(file))[0]
        else:
            raise BF2CollMeshException("file or name required")
    
        if not file:
            return

        with open(file, "rb") as file:
            f = FileUtils(file)
            v1 = f.read_dword()
            v2 = f.read_dword()
            version = (v1, v2)

            if version[0] != 0 and version[1] < 9 or version[1] > 10:
                raise BF2CollMeshException(f"Unsupported .collisionmesh version {version}")

            self.geoms = load_n_elems(f, Geom, count=f.read_dword(), version=version)

            if os.fstat(file.fileno()).st_size != file.tell():
                raise BF2CollMeshException("Corrupted .collisionmesh file? Reading finished and file pointer != filesize")

    def export(self, export_path):
        with open(export_path, "wb") as file:
            f = FileUtils(file)
            f.write_dword(0)
            f.write_dword(9)
            f.write_dword(len(self.geoms))
            for geoms in self.geoms:
                geoms.save(f)
