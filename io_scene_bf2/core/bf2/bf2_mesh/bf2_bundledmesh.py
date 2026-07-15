from .bf2_visiblemesh import BF2VisibleMesh, MaterialWithTransparency, Lod, Geom
from ..fileutils import FileUtils


class BundledMeshMaterial(MaterialWithTransparency):
    pass


class BundledMeshLod(Lod):
    _MATERIAL_TYPE = BundledMeshMaterial

    def __init__(self) -> None:
        self.parts_num = None
        super().__init__()

    def load_other_data(self, f : FileUtils):
        self.parts_num = f.read_dword()

    def save_other_data(self, f : FileUtils):
        f.write_dword(self.parts_num)

class BundledMeshGeom(Geom):
    _LOD_TYPE = BundledMeshLod


class BF2BundledMesh(BF2VisibleMesh):
    _VERSION = 10
    _GEOM_TYPE = BundledMeshGeom
    _FILE_EXT = '.bundledmesh'
