import bpy
from bpy.types import Mesh, Armature, Camera
from .exceptions import ExportException

def to_matrix(pos, rot):
    matrix = rot.to_matrix()
    matrix.resize_4x4()
    matrix.translation = pos
    return matrix

def convert_bf2_pos_rot(pos, rot):
    z = pos.z
    y = pos.y
    pos.z = y
    pos.y = z
    
    z = rot.z
    y = rot.y
    rot.z = y
    rot.y = z
    rot.invert()

def delete_object(obj, recursive=True):
    if recursive:
        for child in obj.children:
            delete_object(child, recursive=True)
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is None:
        return
    if isinstance(data, Mesh):
        bpy.data.meshes.remove(data, do_unlink=True)
    elif isinstance(data, Armature):
        bpy.data.armatures.remove(data, do_unlink=True)
    elif isinstance(data, Camera):
        bpy.data.cameras.remove(data, do_unlink=True)
    else:
        raise ValueError(f"unknown object data type {type(data)}")

def delete_object_if_exists(obj_name, recursive=True):
    if obj_name in bpy.data.objects:
        delete_object(bpy.data.objects[obj_name], recursive=recursive)


def _delete_if_exists(mesh_name, collection):
    if mesh_name in collection:
        collection.remove(collection[mesh_name])

def delete_mesh_if_exists(name):
    _delete_if_exists(name, bpy.data.meshes)

def delete_material_if_exists(name):
    _delete_if_exists(name, bpy.data.meshes)

def check_prefix(name, fmt):

    def _bad_format():
        expected = ''
        for identifier in fmt:
            expected += f'{identifier}<index>'
        raise ExportException(f"Object '{name}' has invalid prefix format, expected '{expected}', where <index> is a number")

    s = name
    indexes = list()
    for identifier in fmt:
        if not s.startswith(identifier):
            _bad_format()
        else:
            s = s[len(identifier):]
            index = ''
            for char in s:
                if char.isdigit():
                    index += char
                else:
                    break
            if not index:
                _bad_format()
            indexes.append(int(index))
            s = s[len(index):]
    return indexes[0] if len(indexes) == 1 else tuple(indexes)

def check_suffix(name, expected_suffix):
    index = ''
    for char in name[::-1]:
        if char.isdigit():
            index += char
        else:
            break
    index = index[::-1]
    if not index:
        raise ExportException(f"{name} must contain numeric suffix")
    n = name[0:-len(index)]
    if not n.endswith(f'{expected_suffix}'):
        raise ExportException(f"{name} must be suffixed with '{expected_suffix}' and an index")
    return int(index)
