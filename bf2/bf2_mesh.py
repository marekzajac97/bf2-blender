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
        return -1
    
    def get_wight_offset(self):
        return self._get_attr_offset(2)
    
    def get_normal_offset(self):
        return self._get_attr_offset(3)
    
    def get_tangent_offset(self):
        return self._get_attr_offset(6)
    
    def get_textc_offset(self, uvchan):
        uvchan_to_usage = {
            0: 5,
            1: 261,
            2: 517,
            3: 733,
            4: 1029
        }
        return self._get_attr_offset(uvchan_to_usage[uvchan])