from typing import List
from .bf2_visiblemesh import BF2VisibleMesh, MaterialWithTransparency, Lod, Geom
from ..fileutils import FileUtils
from ..bf2_common import Mat4, Vec3, load_n_elems


class StaticMeshMaterial(MaterialWithTransparency):

    @classmethod
    def load(cls, f : FileUtils, version, **kwargs):
        obj : StaticMeshMaterial = super(StaticMeshMaterial, cls).load(f, version=version, **kwargs)
        if version == 11:
            obj._min = Vec3.load(f)
            obj._max = Vec3.load(f)
        return obj

    def save(self, f : FileUtils):
        super().save(f)
        # precalculated already when Lod.save_parts_rigs is called
        self._min.save(f)
        self._max.save(f)


class StaticMeshLod(Lod):
    _MATERIAL_TYPE = StaticMeshMaterial

    def __init__(self) -> None:
        # matrix only present StaticMeshes, dunno what is it used for yet (base pivot/rotation?)
        self.parts : List[Mat4] = []
        super().__init__()

    def load_parts_rigs(self, f : FileUtils, version):
        super().load_parts_rigs(f, version=version)
        self.parts = load_n_elems(f, Mat4, count=f.read_dword())

    def save_parts_rigs(self, f : FileUtils):
        super().save_parts_rigs(f)
        f.write_dword(len(self.parts))
        for part in self.parts:
            part.save(f)


class StaticMeshGeom(Geom):
    _LOD_TYPE = StaticMeshLod


class BF2StaticMesh(BF2VisibleMesh):
    _VERSION = 11
    _GEOM_TYPE = StaticMeshGeom
    _FILE_EXT = '.staticmesh'
