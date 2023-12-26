
from typing import List
from .bf2_visiblemesh import Material, Lod, Geom, BF2VisibleMesh
from ..fileutils import FileUtils
from ..bf2_common import Mat4, load_n_elems

class Rig:
    def __init__(self):
        self.bones : List[Bone] = []

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.bones = load_n_elems(f, Bone, count=f.read_dword())
        return obj

class Bone:
    def __init__(self):
        self.id = None
        self.matrix : Mat4

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.id = f.read_dword()
        obj.matrix = Mat4.load(f)
        return obj

class SkinnedMeshMaterial(Material):
    pass

class SkinnedMeshLod(Lod):
    _MATERIAL_TYPE = SkinnedMeshMaterial

    def __init__(self) -> None:
        self.rigs : List[Rig] = []
        super().__init__()

    def load_parts_rigs(self, f : FileUtils, version):
        super().load_parts_rigs(f, version=version)
        self.rigs = load_n_elems(f, Rig, count=f.read_dword())

class SkinnedMeshGeom(Geom):
    _LOD_TYPE = SkinnedMeshLod

class BF2SkinnedMesh(BF2VisibleMesh):
    _GEOM_TYPE = SkinnedMeshGeom
    _FILE_EXT = '.skinnedmesh'