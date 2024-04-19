from .bf2_common import Quat, Vec3
from .fileutils import FileUtils
import os


class BF2SkeletonException(Exception):
    pass


class BF2Skeleton:

    class Node:
        def __init__(self, index, name, pos=Vec3(), rot=Quat()):
            self.index : int = index
            self.name : str = name
            self.rot : Quat = rot.copy()
            self.pos : Vec3 = pos.copy()
            self.parent = None
            self.children =  list()

        def append(self, node):
            node.parent = self
            self.children.append(node)

        def __repr__(self):
            return f"BF2Skeleton.Node({id(self)}) {self.name} pos: {self.pos} rot: {self.rot}"

    def __init__(self, ske_file='', name=''):
        self.roots = list()

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

            nodes = list()
            for node_index in range(node_num):
                node_name_char_count = ske_data.read_word()
                char_list = list()
                for _ in range(node_name_char_count):
                    char_list.append(ske_data.read_byte())
                node_name = bytes(char_list).decode('ascii')
                if node_name[-1] == '\0':
                    node_name = node_name[:-1]

                node_parent_index = ske_data.read_word(signed=True)

                rot = Quat.load(ske_data)
                rot.invert()
                pos = Vec3.load(ske_data)

                nodes.append((BF2Skeleton.Node(node_index, node_name, pos, rot), node_parent_index))

            if os.fstat(f.fileno()).st_size != f.tell():
                raise BF2SkeletonException("Corrupted .ske file? Reading finished and file pointer != filesize")

            for node, parent_index in nodes:
                if parent_index == -1:
                    self.roots.append(node)
                elif parent_index < len(nodes):
                    nodes[parent_index][0].append(node)
                else:
                    raise BF2SkeletonException(f"Invalid .ske file, bad parent node index: {parent_index}")

            if not self.roots:
                raise BF2SkeletonException("Invalid .ske file, missing root node")
      
    def export(self, export_path):
        with open(export_path, "wb") as f:
            ske_data = FileUtils(f)
            ske_data.write_dword(2) # version
            nodes = self.node_list()

            ske_data.write_dword(len(nodes))

            for node in nodes:
                if not node.name[-1] == '\0':
                    node.name += '\0'
                ske_data.write_word(len(node.name))
                for char in bytes(node.name, encoding='ascii'):
                    ske_data.write_byte(char)

                if node.parent is None:
                    parent_index = -1
                else:
                    parent_index = nodes.index(node.parent)
 
                ske_data.write_word(parent_index, signed=True)
                node.rot.invert()
                node.rot.save(ske_data)
                node.pos.save(ske_data)

    def _collect_nodes(self, node, nodes):
        nodes.append(node)
        for child in node.children:
            self._collect_nodes(child, nodes)

    def node_list(self):
        nodes = list()
        for root in self.roots:
            self._collect_nodes(root, nodes)
        nodes.sort(key=lambda x: x.index)
        return nodes
    
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
            for child in node.children:
                out_str += (' ' * 2 * level) + child.name + '\n'
                out_str += __node_tree(child, level + 1)
            return out_str
        out_str = ''
        for root in self.roots:
            out_str += root.name + '\n'
            out_str += __node_tree(self.root, 1, out_str) + '\n'
        return out_str

    def __repr__(self):
            return f"BF2Skeleton({id(self)})\n" + self._node_tree()
