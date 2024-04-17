from .bf2_common import Quat, Vec3
from .fileutils import FileUtils
import os


class BF2SkeletonException(Exception):
    pass


class BF2Skeleton:

    class Node:
        def __init__(self, name, pos=Vec3(), rot=Quat()):
            self.name = name
            self.rot = rot.copy()
            self.pos = pos.copy()
            self.parent = None
            self.childs =  list()
        
        def append(self, node):
            node.parent = self
            self.childs.append(node)
        
        def __repr__(self):
            return f"BF2Skeleton.Node({id(self)}) {self.name} pos: {self.pos} rot: {self.rot}"

    def __init__(self, ske_file='', name=''):
        self.camerabone = None
        self.root = None
        self._nodes = list()
        
        if name:
            self.name = name
        elif ske_file:
            self.name = os.path.splitext(os.path.basename(ske_file))[0]
        else:
            raise BF2SkeletonException("ske_file or name required")
            
        if not ske_file:
            return

        with open(ske_file, "rb") as f:
            ske_data = FileUtils(f)
            version = ske_data.read_dword()
            if version != 2:
                raise BF2SkeletonException(f"Unsupported .ske version {version}")
            node_num = ske_data.read_dword()
            
            tmp_nodes = list()
            for _ in range(node_num):
                node_name_char_count = ske_data.read_word()
                char_list = list()
                for _ in range(node_name_char_count):
                    char_list.append(ske_data.read_byte())
                node_name = bytes(char_list).decode('ascii')
                if node_name[-1] == '\0':
                    node_name = node_name[:-1]

                node_parent_index = ske_data.read_word(signed=True)
                
                rot_x = ske_data.read_float()
                rot_y = ske_data.read_float()
                rot_z = ske_data.read_float()
                rot_w = ske_data.read_float()
                
                rot = Quat(rot_x, rot_y, rot_z, rot_w)
                rot.invert()
                
                pos = Vec3(ske_data.read_float(),
                           ske_data.read_float(),
                           ske_data.read_float())

                tmp_nodes.append((BF2Skeleton.Node(node_name, pos, rot), node_parent_index))
                
            
            if os.fstat(f.fileno()).st_size != f.tell():
                raise BF2SkeletonException("Corrupted .ske file? Reading finished and file pointer != filesize")
            
            self._nodes = list()
            for node, parent_index in tmp_nodes:
                self._nodes.append(node)
                if parent_index == -1:
                    if 'Camerabone' == node.name:
                        self.camerabone = node
                    else:
                        self.root = node
                else:
                    tmp_nodes[parent_index][0].append(node)

            
    def export(self, export_path):
        with open(export_path, "wb") as f:
            ske_data = FileUtils(f)
            ske_data.write_dword(2) # version

            ske_data.write_dword(len(self._nodes))

            for node in self._nodes:
                if not node.name[-1] == '\0':
                    node.name += '\0'
                ske_data.write_word(len(node.name))
                for char in bytes(node.name, encoding='ascii'):
                    ske_data.write_byte(char)
                
                if node.parent is None:
                    parent_index = -1
                else:
                    parent_index = self._nodes.index(node.parent)
                
                ske_data.write_word(parent_index, signed=True)
                
                ske_data.write_float(-node.rot.x)
                ske_data.write_float(-node.rot.y)
                ske_data.write_float(-node.rot.z)
                ske_data.write_float( node.rot.w)

                ske_data.write_float(node.pos.x)
                ske_data.write_float(node.pos.y)
                ske_data.write_float(node.pos.z)

    def node_list(self):
        return self._nodes
    
    def bone_index(self, bone_name):
        for bone_id, bone in enumerate(self._nodes):
            if bone_name == bone.name:
                return bone_id   
        raise ValueError(f'no such bone: {bone_name}')
    
    def __getitem__(self, item):
        for node in self.node_list():
            if item == node.name:
                return node
        raise KeyError(f'no such bone: {item}')

    def _node_tree(self):
        def __node_tree(node, level=0, out_str=''):
            for child in node.childs:
                out_str += (' ' * 2 * level) + child.name + '\n'
                out_str += __node_tree(child, level + 1)
            return out_str
        out_str = ''
        if self.camerabone is not None:
            out_str += self.camerabone.name + '\n'
        out_str += self.root.name + '\n'
        return __node_tree(self.root, 1, out_str)

    def __repr__(self):
            return f"BF2Skeleton({id(self)}) nodes: {len(self.node_list())}\n" + self._node_tree()
