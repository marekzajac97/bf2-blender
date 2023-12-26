

from .bf2_visiblemesh import BF2VisibleMesh, MaterialWithTransparency, Lod, Geom
from ..fileutils import FileUtils

class BundledMeshMaterial(MaterialWithTransparency):
    pass

class BundledMeshLod(Lod):
    _MATERIAL_TYPE = BundledMeshMaterial

    def __init__(self) -> None:
        # BundledMesh geometry parts objects for animated springs\rotbundles\weapons
        self.parts_num = None
        super().__init__()

    def load_parts_rigs(self, f : FileUtils, version):
        super().load_parts_rigs(f, version=version)
        self.parts_num = f.read_dword()

class BundledMeshGeom(Geom):
    _LOD_TYPE = BundledMeshLod

class BF2BundledMesh(BF2VisibleMesh):
    _GEOM_TYPE = BundledMeshGeom
    _FILE_EXT = '.bundledmesh'