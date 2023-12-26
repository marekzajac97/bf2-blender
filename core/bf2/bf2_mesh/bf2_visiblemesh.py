import os
import enum
import struct
from typing import List, Optional, Tuple

from .bf2_types import D3DDECLTYPE, D3DDECLUSAGE, D3DPRIMITIVETYPE, USED, UNUSED
from ..fileutils import FileUtils
from ..bf2_common import Vec3, load_n_elems

class BF2MeshException(Exception):
    pass

class Vertex:
    def __init__(self):
        pass # Attributes added dynamically based on D3DDECLUSAGE with value based on D3DDECLTYPE


class Material:

    SUPPORTS_TRANSPARENCY = False

    def __init__(self):
        self.fxfile : str = None
        self.technique : str = None

        # textures
        self.maps : List[str] = []

        self.vertices : List[Vertex] = []
        self.faces : List[Tuple[int]] = []

        # geom data
        self._vstart : int = None # vertex_buffer offset
        self._istart : int = None # index_buffer offset
        self._inum : int = None # number of indices
        self._vnum : int = None # number of vertices

        # unknowns
        self._u4 : int = None
        self._u5 : int = None

    @classmethod
    def load(cls, f : FileUtils, **kwargs):
        obj = cls()
        obj.fxfile = f.read_string()
        obj.technique = f.read_string()

        obj.maps = [f.read_string() for _ in range(f.read_dword())]

        obj._vstart = f.read_dword()
        obj._istart = f.read_dword()
        obj._inum = f.read_dword()
        obj._vnum = f.read_dword()

        obj._u4 = f.read_dword() # XXX: only used for Staticmesh
        obj._u5 = f.read_dword()
        return obj

    def load_vertices_faces(self, vertex_decl_size, vertex_attributes, vertex_buffer, index_buffer):
        self.vertices = list()
        for i in range(self._vstart, self._vstart + self._vnum):
            vertex = Vertex()
            self.vertices.append(vertex)
            for vertex_attr in vertex_attributes:
                if vertex_attr.flag == UNUSED:
                    continue
                fmt = vertex_attr.decl_type.get_struct_fmt()
                size = struct.calcsize(fmt)
                vstart = i * vertex_decl_size + vertex_attr.offset
                data_packed = vertex_buffer[vstart:vstart+size]
                vertex_attr_value = struct.unpack(fmt, data_packed)
                setattr(vertex, vertex_attr.decl_usage.name.lower(), vertex_attr_value)

        self.faces = list()
        for i in range(self._istart, self._istart + self._inum, 3):
            v1 = index_buffer[i + 0]
            v2 = index_buffer[i + 1]
            v3 = index_buffer[i + 2]
            self.faces.append((v1, v2, v3))


class MaterialWithTransparency(Material):

    SUPPORTS_TRANSPARENCY = True

    class AlphaMode(enum.IntEnum):
        NONE = 0
        ALPHA_BLEND = 1
        ALPHA_TEST = 2

    def __init__(self) -> None:
        self.alpha_mode : Material.AlphaMode = None
        # extra sets of pre-sorted indieces, only used for materials with alpha blend
        self.presorted_faces : Optional[List[List[int]]] = None
        super().__init__()

    @classmethod
    def load(cls, f : FileUtils, version, alpha_blend_indexnum):
        alpha_mode = cls.AlphaMode(f.read_dword())
        obj : MaterialWithTransparency = super(MaterialWithTransparency, cls).load(f, version=version)
        obj.alpha_mode = alpha_mode

        if alpha_mode == cls.AlphaMode.ALPHA_BLEND:
            obj.presorted_faces = list()
            # TODO
        return obj

    def supports_transparency():
        return True


class Lod:
    _MATERIAL_TYPE = Material

    def __init__(self):
        # boundaries
        self.min = None
        self.max = None

        self.materials : List[Material] = []
    
    @classmethod
    def load(cls, f : FileUtils):
        return cls()

    def load_parts_rigs(self, f : FileUtils, version):
        self.min = Vec3.load(f)
        self.max = Vec3.load(f)
        if version <= 6: # some old meshes, version 4, 6
            Vec3.load(f)

    def load_materials(self, f : FileUtils, **kwargs):
        self.materials = load_n_elems(f, self._MATERIAL_TYPE, count=f.read_dword(), **kwargs)


class Geom:
    _LOD_TYPE = Lod

    def __init__(self):
        self.lods : List[Lod] = []

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.lods = load_n_elems(f, cls._LOD_TYPE, count=f.read_dword())
        return obj


class VertexAttribute:
    def __init__(self):
        self.flag = None # USED\UNUSED
        self.offset = None # byte offset from vertex_buffer start
        self.decl_type : D3DDECLTYPE = None
        self.decl_usage : D3DDECLUSAGE = None

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.flag = f.read_word()
        obj.offset = f.read_word()
        obj.decl_type = D3DDECLTYPE(f.read_word())
        obj.decl_usage = D3DDECLUSAGE(f.read_word())
        return obj


class MeshHeader:
    def __init__(self):
        self.u1 = None
        self.version = None
        # those below seem to be reserved for future use
        # BF2 just reads them and doesn't save the values anywhere
        self.u3 = None
        self.u4 = None
        self.u5 = None
        self.u6 = None # seems to be version flag for bfp4f

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.u1 = f.read_dword()
        obj.version = f.read_dword()
        obj.u3 = f.read_dword()
        obj.u4 = f.read_dword()
        obj.u5 = f.read_dword()
        obj.u6 = f.read_byte()
        return obj


class BF2VisibleMesh():
    _GEOM_TYPE = Geom
    _FILE_EXT = ''

    def __init__(self, file='', name=''):

        self.head : MeshHeader = None
        self.geoms : List[Geom] = []

        self.vertex_attributes : List[VertexAttribute] = []
        self.primitive_type : D3DPRIMITIVETYPE = None  # seems to be always D3DPT_TRIANGLELIST but DICE's code also handles D3DPT_TRIANGLESTRIP
        self.vertex_decl_size : int = None # byte size of Vertex declaration
        self.vertex_buffer : bytes = b''
        self.index_buffer : List[int] = []

        if name:
            self.name = name
        elif file:
            self.name = os.path.splitext(os.path.basename(file))[0]
        else:
            raise BF2MeshException("file or name required")

        if not file:
            return

        with open(file, mode='rb') as fo:
            f = FileUtils(fo)
            self.load(f)

            if os.fstat(fo.fileno()).st_size != fo.tell():
                raise BF2MeshException(f"Corrupted {self._FILE_EXT} file? Reading finished and file pointer != filesize")


    def load(self, f : FileUtils):
        self.head = MeshHeader.load(f)

        self.geoms = load_n_elems(f, self._GEOM_TYPE, count=f.read_dword())
        self.vertex_attributes = load_n_elems(f, VertexAttribute, count=f.read_dword())
        self.primitive_type = f.read_dword()

        if self.primitive_type != D3DPRIMITIVETYPE.TRIANGLELIST:
            raise BF2MeshException(f"Unsupported primitive type: {D3DPRIMITIVETYPE(self.primitive_type).name}")

        self.vertex_decl_size = f.read_dword()

        self.vertex_buffer = f.read_raw(self.vertex_decl_size * f.read_dword())
        self.index_buffer = f.read_word(count=f.read_dword())

        alpha_blend_indexnum = None
        if issubclass(self._GEOM_TYPE._LOD_TYPE._MATERIAL_TYPE, MaterialWithTransparency):
            alpha_blend_indexnum = f.read_dword()

        for geom in self.geoms:
            for lod in geom.lods:
                lod.load_parts_rigs(f, version=self.head.version)

        for geom in self.geoms:
            for lod in geom.lods:
                lod.load_materials(f, version=self.head.version, alpha_blend_indexnum=alpha_blend_indexnum)
                for mat in lod.materials:
                    mat.load_vertices_faces(self.vertex_decl_size, self.vertex_attributes, self.vertex_buffer, self.index_buffer)

    def _has_vert_attr(self, decl_usage):
        for vert_attr in self.vertex_attributes:
            if vert_attr.decl_usage == decl_usage:
                return True
        return False

    def has_normal(self):
        return self._has_vert_attr(D3DDECLUSAGE.NORMAL)

    def has_uv(self, uv_channel):
        attr = D3DDECLUSAGE(uv_channel << 8 | 5)
        return self._has_vert_attr(attr)
    
    def has_blend_indices(self):
        return self._has_vert_attr(D3DDECLUSAGE.BLENDINDICES)

    def has_blend_weight(self):
        return self._has_vert_attr(D3DDECLUSAGE.BLENDWEIGHT)