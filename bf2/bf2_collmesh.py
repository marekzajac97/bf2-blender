from typing import List
from .fileutils import FileUtils

import os

class BF2CollMeshException(Exception):
    pass

def load_n_elems(f : FileUtils, struct_type, count, version=None):
    elems = [struct_type() for _ in range(count)]
    for elem in elems:
        kwargs = {}
        if version is not None:
            kwargs = {'version': version}
        elem.load(f, **kwargs)
    return elems


class CollFace():
    def __init__(self):
        self.v1 = None
        self.v2 = None
        self.v3 = None
        self.material = None

    def load(self, f : FileUtils):
        self.v1 = f.read_word()
        self.v2 = f.read_word()
        self.v3 = f.read_word()
        self.material = f.read_word()


class Vec3():
    def __init__(self):
        self.x = None
        self.y = None
        self.z = None

    def load(self, f : FileUtils):
        self.x = f.read_float()
        self.y = f.read_float()
        self.z = f.read_float()


# https://en.wikipedia.org/wiki/Binary_space_partitioning
class BSP():
    class Node():
        def __init__(self):
            self.split_plane_val = None
            self.split_plane_axis = None # 0,1,2
            # 0 = split plane on ZY which crosses (val, _, _) point
            # 1 = split plane on XZ which crosses (_, val, _) point
            # 2 = split plane on XY which crosses (_, _, val) point

            self.parent = None # BSP.Node, None if root
            self.children = [None, None] # front/back BSP.Node (if Node is a subtree Node)
            self.face_refs = [[], []] # front/back lists of face_ref indexes
            self.faces = [[], []] # front/back lists of CollFace (if Node is a leaf Node)
            # NOTE: in DICE's implementation if a face straddles the split plane it is added to both 'front' and 'back' sets

            self._face_refs_idx = [[], []]
            self._children_idx = [None, None]

        def load(self, f : FileUtils):
            self.split_plane_val = f.read_float()
            _0x04 = f.read_dword()
            self.split_plane_axis = _0x04 & 0b11

            for i in range(2):
                is_leaf = bool((4 << i) & _0x04)

                # face ref counts
                if is_leaf:
                    face_ref_count = _0x04 >> (i * 8 + 16) & 0xFF
                    face_ref_start = f.read_dword()
                    self._face_refs_idx[i] = list(range(face_ref_start, face_ref_start + face_ref_count))
                    self._children_idx[i] = None
                else:
                    self._children_idx[i] = f.read_dword()
 
        def resolve_children(self, nodes):
            for i in range(2):
                child_idx = self._children_idx[i]
                if child_idx is not None:
                    self.children[i] = nodes[child_idx]
                    self.children[i].parent = self

        def resolve_face_refs(self, face_refs):
            for i in range(2):
                for j in self._face_refs_idx[i]:
                    self.face_refs[i].append(face_refs[j])
        
        def resolve_faces(self, faces):
            for i in range(2):
                for j in self.face_refs[i]:
                    self.faces[i].append(faces[j])
        
        def _to_string(self, level=0):
            prfx = '   ' * level
            ret = prfx + f' |* split_plane: {self.split_plane_val:.2f}|{self.split_plane_axis}\n'
            for i, child in enumerate(self.children):
                p = ' |F' if i == 0 else ' |B'
                
                if child is None: # leaf
                    faceset = '{'
                    for f in self.faces[i]:
                        if len(faceset) > 1:
                            faceset += ', '
                        faceset += f'({f.v1}, {f.v2}, {f.v3})'
                    faceset += '}'
                    ret += prfx + f'{p}  {faceset}\n'
                else:
                    ret += prfx + f'{p}\\\n'
                    ret += child._to_string(level+1)
            return ret
        
        def __str__(self):
            return self._to_string()

    def __init__(self):
        # tree bounds, used for checking rayRadiusIntersectsAABB
        self.min : Vec3 = Vec3()
        self.max : Vec3 = Vec3()

        self.root : BSP.Node = None

        self._nodes : List[BSP.Node] = []
        self._face_refs : List[int] = []
    
    def load(self, f : FileUtils):
        self.min.load(f)
        self.max.load(f)

        self._nodes = load_n_elems(f, BSP.Node, count=f.read_dword())
        self._face_refs = [f.read_word() for _ in range(f.read_dword())]

        for node in self._nodes:
            node.resolve_children(self._nodes)
            node.resolve_face_refs(self._face_refs)
        
        self._find_root()

    def resolve_faces(self, faces):
        for node in self._nodes:
            node.resolve_faces(faces)

    def _find_root(self):
        self.root = None
        for node in self._nodes:
            if node.parent is None:
                if self.root is None:
                    self.root = node
                else:
                    raise BF2CollMeshException("BSP: found multiple root nodes")
        if self.root is None:
            raise BF2CollMeshException("BSP: root node not found")


class CollLod():

    class CollType:
        PROJECTILE = 0
        VEHICLE = 1
        SOLDIER = 2
        AI = 3

    def __init__(self):
        self.coll_type : CollLod.CollType = None

        self.faces = []
        self.verts = []
        self.vert_materials = []

        # vertex bounds
        self.min = Vec3()
        self.max = Vec3()

        self.bsp = None
        self.debug_mesh = None

    def load(self, f : FileUtils, version):
        self.coll_type = f.read_dword()

        self.faces = load_n_elems(f, CollFace, count=f.read_dword())

        vertnum = f.read_dword()
        self.verts = load_n_elems(f, Vec3, count=vertnum)
        self.vert_materials = [f.read_word() for _ in range(vertnum)]

        self.min.load(f)
        self.max.load(f)

        bsp_present = int(chr(f.read_byte())) # 0x30 or 0x31 (which is ASCII '0' or '1'... why DICE)

        if bsp_present:
            self.bsp = BSP()
            self.bsp.load(f)
            self.bsp.resolve_faces(self.faces)

        # array of face indexes, can be -1 if unset, loaded only for ver >= 10, what exactly is this I don't know
        # used for buildDebugMeshes, we could probably skip this and export as ver 9 and BF2 will generate it
        if version[0] == 0 and version[1] >= 10:
            self.debug_mesh = [f.read_dword(signed=True) for _ in range(f.read_dword())]


class CollSubGeom():
    def __init__(self):
        self.lods = []

    def load(self, f : FileUtils, version):
        self.lods = load_n_elems(f, CollLod, count=f.read_dword(), version=version)


class CollGeom():
    def __init__(self):
        self.subgeoms = []

    def load(self, f : FileUtils, version):
        self.subgeoms = load_n_elems(f, CollSubGeom, count=f.read_dword(), version=version)


class BF2CollMesh:
    def __init__(self, file='', name=''):
        self.version = None
        self.geoms = []

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
            self.load(f)
            if os.fstat(file.fileno()).st_size != file.tell():
                raise BF2CollMeshException("Corrupted .collisionmesh file? Reading finished and file pointer != filesize")

    def load(self, f : FileUtils):
        v1 = f.read_dword()
        v2 = f.read_dword()
        self.version = (v1, v2)

        if self.version[0] != 0 and self.version[1] < 9 or self.version[1] > 10:
            raise BF2CollMeshException(f"Unsupported .collisionmesh version {self.version}")

        self.geoms = load_n_elems(f, CollGeom, count=f.read_dword(), version=self.version)
