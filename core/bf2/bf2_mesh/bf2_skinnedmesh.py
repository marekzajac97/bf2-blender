
from typing import List
from .bf2_visiblemesh import Material, Lod, Geom, BF2VisibleMesh
from ..fileutils import FileUtils
from ..bf2_common import Mat4, load_n_elems

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
    
    def save(self, f : FileUtils):
        f.write_dword(self.id)
        self.matrix.save(f)

class Rig:
    def __init__(self):
        self.bones : List[Bone] = []

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.bones = load_n_elems(f, Bone, count=f.read_dword())
        return obj

    def save(self, f : FileUtils):
        f.write_dword(len(self.bones))
        for bone in self.bones:
            bone.save(f)

    def new_bone(self):
        self.bones.append(Bone())
        return self.bones[-1]

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

    def save_parts_rigs(self, f : FileUtils):
        super().save_parts_rigs(f)
        f.write_dword(len(self.rigs))
        for rig in self.rigs:
            rig.save(f)

    def new_rig(self):
        self.rigs.append(Rig())
        return self.rigs[-1]


class SkinnedMeshGeom(Geom):
    _LOD_TYPE = SkinnedMeshLod


class BF2SkinnedMesh(BF2VisibleMesh):
    _VERSION = 11
    _GEOM_TYPE = SkinnedMeshGeom
    _FILE_EXT = '.skinnedmesh'
