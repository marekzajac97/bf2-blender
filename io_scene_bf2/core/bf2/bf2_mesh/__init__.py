from .bf2_visiblemesh import BF2MeshException
from .bf2_bundledmesh import BF2BundledMesh
from .bf2_skinnedmesh import BF2SkinnedMesh
from .bf2_staticmesh import BF2StaticMesh
from .bf2_samples import BF2Samples
import os

class BF2Mesh:

    @staticmethod
    def load(file : str, use_fm=False):
        ext = os.path.splitext(file)[1].lower()
        if ext == BF2SkinnedMesh._FILE_EXT:
            return BF2SkinnedMesh(file)
        elif ext == BF2StaticMesh._FILE_EXT:
            return BF2StaticMesh(file)
        elif ext == BF2BundledMesh._FILE_EXT:
            return BF2BundledMesh(file)
        else:
            raise ValueError(f"unknown mesh type {ext}")
