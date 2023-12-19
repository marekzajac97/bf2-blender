from .bf2mesh.visiblemesh import VisibleMesh
import os


class BF2MeshException(Exception):
    pass


class BF2Mesh(VisibleMesh):
    
    def __init__(self, file='', name=''):  
        if name:
            self.name = name
        elif file:
            self.name = os.path.splitext(os.path.basename(file))[0]
        else:
            raise BF2MeshException("file or name required")
            
        if not file:
            return
        
        super().__init__(file)
    
    def _get_attr_offset(self, usageId):
        for vertattr in self.vertex_attributes:
            if vertattr.usage == usageId:
                return int(vertattr.offset / 4)
        return None

    def get_wight_offset(self):
        return self._get_attr_offset(2)
    
    def get_normal_offset(self):
        return self._get_attr_offset(3)
    
    def get_tangent_offset(self):
        return self._get_attr_offset(6)
    
    def get_uv_offset(self, uvchan):
        usage = uvchan << 8 | 5
        return self._get_attr_offset(usage)