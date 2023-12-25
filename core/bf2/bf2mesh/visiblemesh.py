# The MIT License (MIT)

# Copyright (c) 2019 Nikita Gotsko

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import logging

from .mesh import BF2Mesh
from .bf2types import D3DDECLTYPE, D3DDECLUSAGE, USED, UNUSED
from .io import read_float
from .io import read_float3
from .io import read_long
from .io import read_short
from .io import read_byte
from .io import read_matrix4
from .io import read_string
from .io import write_long
from .io import write_short
from .io import write_float3
from .io import write_byte
from .io import write_float
from .io import write_matrix4
from .io import write_string

class VisibleMesh(BF2Mesh):
    
    # internal container class for populating wtih D3DDECLUSAGE type attributes
    class _vertex(object):
        pass
    
    def __init__(self,
            filename=None,
            isSkinnedMesh=False,
            isBundledMesh=False,
            isStaticMesh=False):
        BF2Mesh.__init__(self, filename=filename,
                    isSkinnedMesh=isSkinnedMesh,
                    isBundledMesh=isBundledMesh,
                    isStaticMesh=isStaticMesh)

        ### MESH DATA ###
        self.head = _bf2head()  # header contains version info and some bfp4f data

        # geom struct, hold materials info etc
        # staticmesh: geom0 = non-destroayble, geom1 = 3p destroyed
        # skinnedmesh: geom0 = 1p, geom1 = 3p
        # bundledmesh: geom0 = 1p, geom1 = 3p, geom2 = 3p wreck
        self.geomnum = 0
        self.geoms = [_bf2geom() for i in range(self.geomnum)]

        # vertex attributes table, holds info how vertex data packed in .vertices array
        self.vertattribnum = 0
        self.vertex_attributes = [_bf2vertattrib() for i in range(self.vertattribnum)]
        self.primitive_type = 0  # D3DPRIMITIVETYPE enum, seems to be always D3DPT_TRIANGLELIST = 4 but DICE's code also handles D3DPT_TRIANGLESTRIP = 5
        self.vertstride = 0  # bytes len for vertex data chunk

        # vertex data
        self.vertnum = 0  # number of vertices
        #self.vertices = tuple([_ for i in range( self.vertnum * self.vertstride / self.primitive_type )])  # geom data, parse using attrib table
        self.vertices = []

        # indices
        # NOTE: indices are unsigned(?) short, therefor maximum indexed vertices per material is 32k
        self.indexnum = 0  # number of indices
        self.index = []  # indices array, values per-material

        self.alpha_blend_indexnum = 0 # number of extra sets of pre-sorted indieces, only used for materials with alpha_blend
        ### MESH DATA ###

        self.__enter__()

    def __enter__(self):
        if self.filename and not self.isLoaded:
            self.__meshfile = open(file=self.filename, mode='rb')
            self.__load()
            self.__meshfile.close()
        return self
    
    def __exit__(self, type, value, tracebacks):
        if self.__meshfile:
            if not self.__meshfile.closed:
                self.__meshfile.close()
    
    def __str__(self):
        retstr = []
        retstr.append(self.filename)
        retstr.append('header:\n%s' % str(self.head))
        
        raise NotImplementedError
        #return '\n'.join(retstr)
    
    @property
    def vertex_size(self):
        return sum([len(D3DDECLTYPE(v_attrib.vartype)) for v_attrib in self.vertex_attributes if v_attrib.flag is USED])
        
    def __load(self):
        self.__read_header()
        self.__read_geomnum()
        self.__read_geom_table()
        self.__read_vertattribnum()
        self.__read_vertattrib_table()
        self.__read_primitive_type()
        self.__read_vertstride()
        self.__read_vertnum()
        self.__read_vertices()
        self.__read_indexnum()
        self.__read_indices()
        self.__read_alpha_blend_indexnum()
        self.__load_lods_nodes_rigs()
        self.__load_lods_materials()
        
        # make sure we did read whole file, not missing any byte!
        if self.__meshfile.tell() == os.stat(self.filename).st_size:
            logging.debug('loaded %d bytes from %s' % (self.__meshfile.tell(), self.filename))
            self.isLoaded = True
        else:
            raise AttributeError('did not parsed all bytes from %s' % self.filename)
    
    def __read_header(self):
        logging.debug('starting reading header at %d' % self.__meshfile.tell())
        self.head.load(self.__meshfile)
        logging.debug('finished reading header at %d' % self.__meshfile.tell())
    
    def __read_geomnum(self):
        self.geomnum = read_long(self.__meshfile)
        logging.debug('geomnum = %d' % self.geomnum)
    
    def __read_geom_table(self):
        logging.debug('starting reading geom table at %d' % self.__meshfile.tell())
        self.geoms = [_bf2geom() for i in range(self.geomnum)]
        for geom in self.geoms:
            geom.load(self.__meshfile)
        logging.debug('finished reading geom table at %d' % self.__meshfile.tell())

    def __read_vertattribnum(self):
        self.vertattribnum = read_long(self.__meshfile)
        logging.debug('vertattribnum = %d' % self.vertattribnum)
    
    def __read_vertattrib_table(self):
        logging.debug('starting reading vertattrib table at %d' % self.__meshfile.tell())
        self.vertex_attributes = [_bf2vertattrib() for i in range(self.vertattribnum)]
        for i in range(self.vertattribnum):
            self.vertex_attributes[i].load(self.__meshfile)
            logging.debug('attrib [{0}] = {1.flag}, {1.offset}, {1.usage}, {1.vartype}'.format(i, self.vertex_attributes[i]))
        logging.debug('finished reading vertattrib table at %d' % self.__meshfile.tell())

    def __read_primitive_type(self):
        self.primitive_type = read_long(self.__meshfile)
        logging.debug('primitive_type = %d' % self.primitive_type)

    def __read_vertstride(self):
        self.vertstride = read_long(self.__meshfile)
        logging.debug('vertstride = %d' % self.vertstride)

    def __read_vertnum(self):
        self.vertnum = read_long(self.__meshfile)
        logging.debug('vertnum = %d' % self.vertnum)

    def __read_vertices(self):
        logging.debug('starting reading vertex block at %d' % self.__meshfile.tell())
        data_num = int(self.vertstride / self.primitive_type * self.vertnum)
        self.vertices = read_float(self.__meshfile, data_num)
        logging.debug('array size = %d' % len(self.vertices))
        logging.debug('finished reading vertex block at %d' % self.__meshfile.tell())
    
    def __read_indexnum(self):
        self.indexnum = read_long(self.__meshfile)
        logging.debug('indexnum = %d', self.indexnum)

    def __read_indices(self):
        logging.debug('starting reading index block at %d' % self.__meshfile.tell())
        self.index = read_short(self.__meshfile, self.indexnum)
        logging.debug('finished reading index block at %d' % self.__meshfile.tell())

    def __read_alpha_blend_indexnum(self):
        if not self.isSkinnedMesh:
            self.alpha_blend_indexnum = read_long(self.__meshfile)
            logging.debug('alpha_blend_indexnum = %d' % self.alpha_blend_indexnum)
    
    def __load_lods_nodes_rigs(self):
        logging.debug('starting reading lods tables at %d' % self.__meshfile.tell())
        for geom_id, geom in enumerate(self.geoms):
            logging.debug('reading geom%d at %d' % (geom_id, self.__meshfile.tell()))
            for lod_id, lod in enumerate(geom.lods):
                logging.debug('reading lod%d at %d' % (lod_id, self.__meshfile.tell()))
                lod.load_nodes_rigs(self.__meshfile, self.head.version, self.isBundledMesh, self.isSkinnedMesh)
        logging.debug('finished reading lods tables at %d' % (self.__meshfile.tell()))

    def __load_lods_materials(self):
        logging.debug('starting reading materials at %d' % (self.__meshfile.tell()))
        for geom_id, geom in enumerate(self.geoms):
            logging.debug('reading geom%d at %d' % (geom_id, self.__meshfile.tell()))
            for lod_id, lod in enumerate(geom.lods):
                logging.debug('reading lod%d at %d' % (lod_id, self.__meshfile.tell()))
                lod.load_materials(self.__meshfile, self.head.version, self.isSkinnedMesh)
        logging.debug('finished reading materials at %d' % (self.__meshfile.tell()))
    
    def export(self, filename=None, update_bounds=True):
        if not filename: filename = self.filename
        logging.debug('saving mesh as %s' % filename)

        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        
        # update lods&materials bounds first
        if update_bounds: self.update_boundaries()

        with open(filename, 'wb') as vmesh:
            self.__export(vmesh)
            self.filename = filename
            
    def __export(self, fo):
        logging.debug('writing header at %d' % fo.tell())
        self.head.export(fo)
        logging.debug('writing geom table at %d' % fo.tell())
        write_long(fo, self.geomnum)
        for geom in self.geoms:
            geom.export(fo)
        logging.debug('writing vertex attributes table at %d' % fo.tell())
        write_long(fo, self.vertattribnum)
        for vertex_attributes_table in self.vertex_attributes:
            vertex_attributes_table.export(fo)
        logging.debug('writing vertices block at %d' % fo.tell())
        write_long(fo, self.primitive_type)
        write_long(fo, self.vertstride)
        write_long(fo, self.vertnum)
        logging.debug('writing vertices array at %d' % fo.tell())
        for value in self.vertices:
            write_float(fo, value)
        logging.debug('writing %d indices at %d' % (self.indexnum, fo.tell()))
        write_long(fo, self.indexnum)
        for value in self.index:
            write_short(fo, value)
        if not self.isSkinnedMesh: write_long(fo, self.alpha_blend_indexnum)
        logging.debug('writing nodes at %d' % fo.tell())
        for geom in self.geoms:
            for lod in geom.lods:
                lod.export_nodes(fo, self.head.version, self.isBundledMesh, self.isSkinnedMesh)
        logging.debug('writing materials at %d' % fo.tell())
        for geom in self.geoms:
            for lod in geom.lods:
                lod.export_materials(fo, self.head.version, self.isSkinnedMesh)
        logging.debug('exported %d bytes' % fo.tell())
    
    def update_boundaries(self):
        logging.debug('updating %s boundaries' % self.filename)

        for geomId, geom in enumerate(self.geoms):
            for lodId, lod in enumerate(geom.lods):
                lod_min = [0.0, 0.0, 0.0]
                lod_max = [0.0, 0.0, 0.0]
                logging.debug('self.geoms[%d].lods[%d].min = %s' % (geomId, lodId, lod_min))
                logging.debug('self.geoms[%d].lods[%d].max = %s' % (geomId, lodId, lod_max))
                for materialId, material in enumerate(lod.materials):
                    if not self.isSkinnedMesh and self.head.version == 11:
                        material_min = [0.0, 0.0, 0.0]
                        material_max = [0.0, 0.0, 0.0]
                        logging.debug('self.geoms[%d].lods[%d].materials[%d].mmin = %s' % (geomId, lodId, materialId, material_min))
                        logging.debug('self.geoms[%d].lods[%d].materials[%d].mmax = %s' % (geomId, lodId, materialId, material_max))
                    for vertId in range(material.vnum):
                        # create vertex
                        _start = (material.vstart + vertId) * self.vertex_size
                        _end = _start + self.vertex_size
                        vertexBuffer = self.vertices[_start:_end]
                        vertex = self._vertex()
                        for attrib in self.vertex_attributes:
                            if attrib.flag is UNUSED: continue
                            _start = int(attrib.offset / self.primitive_type)
                            _end = _start + len(D3DDECLTYPE(attrib.vartype))
                            setattr(vertex, D3DDECLUSAGE(attrib.usage).name, vertexBuffer[_start:_end])
                        # update material and lod bounds
                        if not self.isSkinnedMesh and self.head.version == 11:
                            for id_axis, axis in enumerate(material_min):
                                position = getattr(vertex, 'POSITION')
                                if position[id_axis] < material_min[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].materials[%d].mmin(%d): %s > %s, updating' % (geomId, lodId, materialId, id_axis, material_min[id_axis], position[id_axis]))
                                    material_min[id_axis] = position[id_axis]
                                if position[id_axis] < lod_min[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].min(%d): %s > %s, updating' % (geomId, lodId, id_axis, lod_min[id_axis], position[id_axis]))
                                    lod_min[id_axis] = position[id_axis]
                            for id_axis, axis in enumerate(material_max):
                                if position[id_axis] > material_max[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].materials[%d].mmin(%d): %s > %s, updating' % (geomId, lodId, materialId, id_axis, material_max[id_axis], position[id_axis]))
                                    material_max[id_axis] = position[id_axis]
                                if position[id_axis] > lod_max[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].min(%d): %s > %s, updating' % (geomId, lodId, id_axis, lod_max[id_axis], position[id_axis]))
                                    lod_max[id_axis] = position[id_axis]
                    if not self.isSkinnedMesh and self.head.version == 11:
                        material.mmin = tuple(material_min)
                        material.mmax = tuple(material_max)
                lod.min = tuple(lod_min)
                lod.max = tuple(lod_max)


class _bf2head:
    """
    Holds version info + some unknown bytes

    """
    def __init__(self):
        self.u1 = None
        self.version = None
        # those below seem to be reserved for future use
        # BF2 just reads them and doesn't save the values anywhere
        self.u3 = None
        self.u4 = None
        self.u5 = None
        self.u6 = None # seems to be version flag for bfp4f

    def load(self, fo):
        self.u1 = read_long(fo)
        self.version = read_long(fo)
        self.u3 = read_long(fo)
        self.u4 = read_long(fo)
        self.u5 = read_long(fo)
        self.u6 = read_byte(fo)
        logging.debug('head.u1 = %d' % self.u1)
        logging.debug('head.version = %d' % self.version)
        logging.debug('head.u3 = %d' % self.u3)
        logging.debug('head.u4 = %d' % self.u4)
        logging.debug('head.u5 = %d' % self.u5)
        logging.debug('head.u6 = %d' % self.u6)
    
    def export(self, fo):
        write_long(fo, self.u1)
        write_long(fo, self.version)
        write_long(fo, self.u3)
        write_long(fo, self.u4)
        write_long(fo, self.u5)
        write_byte(fo, self.u6)

    def __eq__(self, other):
        if self.u1 != other.u1: return False
        if self.version != other.version: return False
        if self.u3 != other.u3: return False
        if self.u4 != other.u4: return False
        if self.u5 != other.u5: return False
        if self.u6 != other.u6: return False
        return True
    
    def __str__(self):
        return '\n'.join([
                        'head.u1 = ' + str(self.u1),
                        'head.version = ' + str(self.version),
                        'head.u3 = ' + str(self.u3),
                        'head.u4 = ' + str(self.u4),
                        'head.u5 = ' + str(self.u5),
                        'head.u6 = ' + str(self.u6)])

class _bf2mat:
    def __init__(self):
        self.alphamode = None # transparency enableddisabled
        self.fxfile = None # shader
        self.technique = None # transparency type

        # textures
        self.mapnum = 0
        self.maps = [b'' for i in range(self.mapnum)]

        # geom data
        self.vstart = None # vertex array offset
        self.istart = None # index array offset
        self.inum = None # amount of indices
        self.vnum = None # amount of vertices

        # unknowns
        self.u4 = None
        self.u5 = None

        # material boundaries
        self.mmin = None
        self.mmax = None

    def __eq__(self, other):
        if self.alphamode != other.alphamode:
            logging.debug('\nmaterial.alphamode = %r\nother.alphamode = %r' % (self.alphamode, other.alphamode))
            return False
        if self.fxfile != other.fxfile:
            logging.debug('\nmaterial.fxfile = %s\nother.fxfile = %s' % (self.fxfile, other.fxfile))
            return False
        if self.technique != other.technique:
            logging.debug('\nmaterial.technique = %s\nother.technique = %s' % (self.technique, other.technique))
            return False
        if self.mapnum != other.mapnum:
            logging.debug('\nmaterial.mapnum = %d\nother.mapnum = %d' % (self.mapnum, other.mapnum))
            return False
        if self.maps != other.maps:
            logging.debug('\nmaterial.maps = %s\nother.maps = %s' % (str(self.maps), str(other.maps)))
            return False
        if self.vstart != other.vstart:
            logging.debug('\nmaterial.vstart = %d\nother.vstart = %d' % (self.vstart, other.vstart))
            return False
        if self.istart != other.istart:
            logging.debug('\nmaterial.istart = %d\nother.vstart = %d' % (self.istart, other.istart))
            return False
        if self.inum != other.inum:
            logging.debug('\nmaterial.inum = %d\nother.inum = %d' % (self.inum, other.inum))
            return False
        if self.vnum != other.vnum:
            logging.debug('\nmaterial.vnum = %d\nother.vnum = %d' % (self.vnum, other.vnum))
            return False
        if self.u4 != other.u4:
            logging.debug('\nmaterial.u4 = %d\nother.u4 = %d' % (self.u4, other.u4))
            return False
        if self.u5 != other.u5:
            logging.debug('\nmaterial.u5 = %d\nother.u5 = %d' % (self.u5, other.u5))
            return False
        if self.mmin != other.mmin:
            logging.debug('\nmaterial.mmin = (%d, %d, %d)\nother.mmin = (%d, %d, %d)' % (*self.mmin, *other.mmin))
            return False
        return True

    def load(self, fo, version, isSkinnedMesh):
        if not isSkinnedMesh:
            self.alphamode = read_long(fo)
            logging.debug('alphamode = %d' % self.alphamode)
        self.fxfile = read_string(fo)
        self.technique = read_string(fo)
        logging.debug('fxfile = %s' % self.fxfile)
        logging.debug('technique = %s' % self.technique)

        self.mapnum = read_long(fo)
        self.maps = [read_string(fo) for i in range(self.mapnum)]
        logging.debug('mapnum = %d' % self.mapnum)
        for texturename in self.maps:
            logging.debug('map = %s' % texturename)

        self.vstart = read_long(fo)
        self.istart = read_long(fo)
        self.inum = read_long(fo)
        self.vnum = read_long(fo)
        logging.debug('vstart = %d' % self.vstart)
        logging.debug('istart = %d' % self.istart)
        logging.debug('inum = %d' % self.inum)
        logging.debug('vnum = %d' % self.vnum)

        self.u4 = read_long(fo) # XXX: only read for Staticmesh
        self.u5 = read_long(fo)
        logging.debug('u4 = %d' % self.u4)
        logging.debug('u5 = %d' % self.u5)

        if not isSkinnedMesh and version == 11:
            self.mmin = read_float3(fo) # XXX: only present for Staticmesh
            self.mmax = read_float3(fo)
            logging.debug('mmin = ({})'.format(*self.mmin))
            logging.debug('mmax = ({})'.format(*self.mmax))

    def export(self, fo, version, isSkinnedMesh):
        if not isSkinnedMesh:
            write_long(fo, self.alphamode)

        write_string(fo, self.fxfile)
        write_string(fo, self.technique)

        write_long(fo, self.mapnum)
        for texturename in self.maps:
            write_string(fo, texturename)

        write_long(fo, self.vstart)
        write_long(fo, self.istart)
        write_long(fo, self.inum)
        write_long(fo, self.vnum)

        write_long(fo, self.u4)
        write_long(fo, self.u5)

        if not isSkinnedMesh and version == 11:
            write_float3(fo, *self.mmin)
            write_float3(fo, *self.mmax)

class _bf2geom:
    """
    Geometry structure table, stores info about lods inheritance from geoms, and materials

    """
    def __init__(self):
        self.lodnum = 0
        self.lods = [_bf2lod() for i in range(self.lodnum)]

    def load(self, fo):
        self.lodnum = read_long(fo)
        self.lods = [_bf2lod() for i in range(self.lodnum)]
        logging.debug('geom.lodnum = %d' % self.lodnum)
    
    def export(self, fo):
        write_long(fo, self.lodnum)

    # NOTE: eq should be comparing only if trees structure same, DO NOT compare content
    def __eq__(self, other):
        if self.lodnum != other.lodnum: return False
        if len(self.lods) != len(other.lods): return False
        return True

class _bf2lod:

    def __init__(self):
        # boundaries
        self.min = None
        self.max = None
        self.pivot = None  # some unknown float3 for .version <=6

        # rigs, only for skinned meshes
        self.rignum = 0
        self.rigs = [_bf2rig() for i in range(self.rignum)]

        # nodes for bundled and staticmeshes
        # seems like those a geomPart objects for animated springs\rotbundles
        self.nodenum = 0
        self.nodes = []  # matrix4 * .nodenum

        # materials stores info about vertices&indices offsets + textures&shaders
        self.matnum = 0
        self.materials = [_bf2mat() for i in range(self.matnum)]

        # StdSample object for LMing statics
        self.sample = None
    
    def __eq__(self, other):
        if self.min != other.min:
            logging.debug('\nlod.min = (%g, %g, %g)\nother.min = (%g, %g, %g)' % (*self.min, *other.min))
            return False
        if self.max != other.max:
            logging.debug('\nlod.max = (%g, %g, %g)\nother.max = (%g, %g, %g)' % (*self.max, *other.max))
            return False
        if self.pivot != other.pivot:
            logging.debug('\nlod.pivot = (%g, %g, %g)\nother.pivot = (%g, %g, %g)' % (*self.pivot, *other.pivot))
            return False
        if self.rignum != other.rignum:
            logging.debug('\nlod.rignum = %d\nother.rignum = %d' % (self.rignum, other.rignum))
            return False
        for rigId, rig in enumerate(self.rigs):
            other_rig = other.rigs[rigId]
            if rig != other_rig:
                logging.debug('\nlod.rigs[%d] = %s\nother.rigs[%d] = %s' % (rigId, str(rig), rigId, str(other_rig)))
                return False
        if self.nodenum != other.nodenum:
            logging.debug('\nlod.nodenum = %d\nother.nodenum = %d' % (self.nodenum, other.nodenum))
            return False
        for nodeId, node in enumerate(self.nodes):
            other_node = other.nodes[nodeId]
            if node != other_node:
                logging.debug('\nlod.nodes[%d] = %s\nother.nodes[%d] = %s' % (nodeId, str(node), nodeId, str(other_node)))
                return False
        if self.matnum != other.matnum:
            logging.debug('\nlod.matnum = %d\nother.matnum = %d' % (self.matnum, other.matnum))
            return False
        for materialId, material in enumerate(self.materials):
            other_material = other.materials[materialId]
            if material != other_material:
                logging.debug('\nlod.material[%d] = %s\nother.material[%d] = %s' % (materialId, str(material), materialId, str(other_material)))
                return False
        return True

    # loading nodes data for bundledmeshes
    # loading rigs data for skinnedmeshes
    # loading boundaries for staticmesh
    def load_nodes_rigs(self, fo, version, isBundledMesh, isSkinnedMesh):
        self.min = read_float3(fo)
        self.max = read_float3(fo)
        logging.debug('lod.min = ({})'.format(*self.min))
        logging.debug('lod.max = ({})'.format(*self.max))

        if version <= 6: # some old meshes, version 4, 6
            self.pivot = read_float3(fo)
            logging.debug('lod.pivot = ({})'.format(*self.pivot))

        if isSkinnedMesh:
            self.rignum = read_long(fo)
            logging.debug('lod.rignum = %d' % (self.rignum))
            if self.rignum > 0:
                self.rigs = [_bf2rig() for i in range(self.rignum)]
                for rig in self.rigs:
                    rig.load(fo)
        else:
            self.nodenum = read_long(fo)
            logging.debug('lod.nodenum = %d' % (self.nodenum))
            if not isBundledMesh:
                for _ in range(self.nodenum):
                    self.nodes.append(read_matrix4(fo))
    
    def export_nodes(self, fo, version, isBundledMesh, isSkinnedMesh):
        write_float3(fo, *self.min)
        write_float3(fo, *self.max)

        if version <= 6:
            write_float3(fo, *self.pivot)
        
        if isSkinnedMesh:
            write_long(fo, self.rignum)
            for rig in self.rigs:
                rig.export(fo)
        else:
            write_long(fo, self.nodenum)
            if not isBundledMesh:
                for node in self.nodes:
                    write_matrix4(fo, node)
    
    def load_materials(self, fo, version, isSkinnedMesh):
        self.matnum = read_long(fo)
        logging.debug('lod.matnum = %d' % (self.matnum))
        self.materials = [_bf2mat() for i in range(self.matnum)]
        for material_id, material in enumerate(self.materials):
            logging.debug('reading material%d at %d' % (material_id, fo.tell()))
            material.load(fo, version, isSkinnedMesh)
    
    def export_materials(self, fo, version, isSkinnedMesh):
        write_long(fo, self.matnum)
        for material in self.materials:
            material.export(fo, version, isSkinnedMesh)

class _bf2rig:
    def __init__(self):
        self.bonenum = 0
        self.bones = [_bf2bone() for i in range(self.bonenum)]

    def __eq__(self, other):
        if self.bonenum != other.bonenum:
            logging.debug('\nrig.bonenum = %d\nother.bonenum = %d' % (self.bonenum, other.bonenum))
            return False
        for boneId, bone in enumerate(self.bones):
            other_bone = other.bones[boneId]
            if bone != other_bone:
                logging.debug('\nrig.bones[%d] = %s\nrig.bones[%d] = %s' % (boneId, str(bone), boneId, str(other_bone)))
                return False
        return True

    def load(self, fo):
        self.bonenum = read_long(fo)
        if self.bonenum > 0:
            self.bones = [_bf2bone() for i in range(self.bonenum)]
            for bone in self.bones:
                bone.id = read_long(fo)
                bone.matrix = read_matrix4(fo)
    
    def export(self, fo):
        write_long(fo, self.bonenum)
        for bone in self.bones:
            write_long(fo, bone.id)
            write_matrix4(fo, bone.matrix)

class _bf2bone:

    def __init__(self):
        self.id = None
        self.matrix = []
    
    def __eq__(self, other):
        if self.id != other.id:
            logging.debug('\nbone.id = %d\nother.id = %d' % (self.id, other.id))
            return False
        if self.matrix != other.matrix:
            logging.debug('\nbone.matrix = %s\nother.id = %s' % (str(self.matrix), str(other.matrix)))
            return False
        return True

class _bf2vertattrib:
    
    """
    Vertex attributes table, holds info how vertex data packed in .vertices array

    """
    def __init__(self, flag=None, offset=None, vartype=None, usage=None):
        self.flag = flag # USED\UNUSED
        self.offset = offset # offset from block start, in bytes
        self.vartype = vartype # DX SDK 'Include/d3d9types.h' enum _D3DDECLTYPE
        self.usage = usage # DX SDK 'Include/d3d9types.h' enum _D3DDECLUSAGE
    
    def load(self, fo):
        self.flag = read_short(fo)
        self.offset = read_short(fo)
        self.vartype = read_short(fo)
        self.usage = read_short(fo)
    
    def export(self, fo):
        write_short(fo, self.flag)
        write_short(fo, self.offset)
        write_short(fo, self.vartype)
        write_short(fo, self.usage)
    
    def __eq__(self, other):
        if not isinstance(other, _bf2vertattrib): return False
        if self.flag != other.flag: return False
        if self.offset != other.offset: return False
        if self.vartype != other.vartype: return False
        if self.usage != other.usage: return False
        return True
    
    def __str__(self):
        return 'flag: %s, offset: %s, vartype: %s of size %s, usage: %s' % (self.flag, self.offset, D3DDECLTYPE(self.vartype), len(D3DDECLTYPE(self.vartype)), D3DDECLUSAGE(self.usage).name)
