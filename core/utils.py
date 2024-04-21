import bpy
from bpy.types import Mesh, Armature, Camera
from mathutils import Quaternion, Matrix, Vector
from .exceptions import ExportException
from .bf2.bf2_common import Mat4, Quat, Vec3

class Reporter:
    def __init__(self, report_func) -> None:
        self.report_func = report_func

    def _report(self, level, msg):
        if self.report_func:
            self.report_func({level}, msg)
        else:
            print(f"{level}: {msg}")

    def warning(self, msg):
        self._report("WARNING", msg)

    def error(self, msg):
        self._report("ERROR", msg)

    def info(self, msg):
        self._report("INFO", msg)

DEFAULT_REPORTER = Reporter(None)

def to_matrix(pos, rot):
    matrix = rot.to_matrix()
    matrix.resize_4x4()
    matrix.translation = pos
    return matrix

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
        raise ExportException(f"Object '{name}' has invalid prefix format, expected '{expected}__', where <index> is a number")

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

    if not s.startswith('__'):
        _bad_format()

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

def _convert_pos(pos):
    z = pos.z
    y = pos.y
    pos.z = y
    pos.y = z

def _convert_rot(rot):
    z = rot.z
    y = rot.y
    rot.z = y
    rot.y = z
    rot.invert()

def conv_bf2_to_blender(*args):
    ret = list()
    for arg in args:
        if isinstance(arg, Mat4):
            m = Matrix(arg.m)
            m.transpose()
            m.invert()
            pos, rot, _ = m.decompose()
            _convert_pos(pos)
            _convert_rot(rot)
            m = to_matrix(pos, rot)
            ret.append(m)
        elif isinstance(arg, Vec3):
            v = Vector((arg.x, arg.y, arg.z))
            _convert_pos(v)
            ret.append(v)
        elif isinstance(arg, Quat):
            q = Quaternion((arg.w, arg.x, arg.y, arg.z))
            _convert_rot(q)
            ret.append(q)
        else:
            raise ValueError(f"bad conv type {type(arg)}")
    if len(ret) == 1:
        return ret[0]
    else:
        return tuple(ret)

def conv_blender_to_bf2(*args):
    ret = list()
    for arg in args:
        if isinstance(arg, Matrix):
            pos, rot, _ = arg.decompose()
            _convert_pos(pos)
            _convert_rot(rot)
            m = to_matrix(pos, rot)
            m.invert()
            m.transpose()
            ret.append(Mat4(m))
        elif isinstance(arg, Vector):
            v = Vec3(arg.x, arg.y, arg.z)
            _convert_pos(v)
            ret.append(v)
        elif isinstance(arg, Quaternion):
            q = Quat(arg.x, arg.y, arg.z, arg.w)
            _convert_rot(q)
            ret.append(q)
        else:
            raise ValueError(f"bad conv type {type(arg)}")
    if len(ret) == 1:
        return ret[0]
    else:
        return tuple(ret)