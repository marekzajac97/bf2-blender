
from typing import List
from .bf2_visiblemesh import BF2VisibleMesh, MaterialWithTransparency, Lod, Geom
from ..fileutils import FileUtils
from ..bf2_common import Mat4, Vec3, load_n_elems

class StaticMeshMaterial(MaterialWithTransparency):
    def __init__(self) -> None:
        # bounding box
        self.mmin : Vec3 = None
        self.mmax : Vec3 = None
        super().__init__()

    @classmethod
    def load(cls, f : FileUtils, version, **kwargs):
        obj : StaticMeshMaterial = super(StaticMeshMaterial, cls).load(f, version=version, **kwargs)
        if version == 11:
            obj.mmin = Vec3.load(f)
            obj.mmax = Vec3.load(f)
        return obj

class StaticMeshLod(Lod):
    _MATERIAL_TYPE = StaticMeshMaterial

    def __init__(self) -> None:
        # matrix only present StaticMeshes, dunno what is it used for yet (bas pivot/rotation?)
        self.parts_num = None
        self.parts_mat : List[Mat4] = []
        super().__init__()

    def load_parts_rigs(self, f : FileUtils, version):
        super().load_parts_rigs(f, version=version)
        self.parts_num = f.read_dword()
        self.parts = load_n_elems(f, Mat4, count=self.parts_num)

class StaticMeshGeom(Geom):
    _LOD_TYPE = StaticMeshLod

class BF2StaticMesh(BF2VisibleMesh):
    _GEOM_TYPE = StaticMeshGeom
    _FILE_EXT = '.staticmesh'
