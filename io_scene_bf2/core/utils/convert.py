"""Blender <-> BF2 conversion utilities"""

import math

from mathutils import Vector, Matrix, Quaternion # type: ignore
from ..bf2.bf2_common import Mat4, Quat, Vec3

def to_matrix(pos, rot):
    matrix = rot.to_matrix()
    matrix.resize_4x4()
    matrix.translation = pos
    return matrix

def swap_zy(vec):
    return (vec[0], vec[2], vec[1])

def invert_face(verts):
    return (verts[2], verts[1], verts[0])

def flip_uv(uv):
    u, v = uv
    return (u, 1 - v)

def conv_pos(pos):
    z = pos.z
    y = pos.y
    pos.z = y
    pos.y = z

def conv_rot(rot):
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
            conv_pos(pos)
            conv_rot(rot)
            m = to_matrix(pos, rot)
            ret.append(m)
        elif isinstance(arg, Vec3):
            v = Vector((arg.x, arg.y, arg.z))
            conv_pos(v)
            ret.append(v)
        elif isinstance(arg, Quat):
            q = Quaternion((arg.w, arg.x, arg.y, arg.z))
            conv_rot(q)
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
            conv_pos(pos)
            conv_rot(rot)
            m = to_matrix(pos, rot)
            m.invert()
            m.transpose()
            ret.append(Mat4(m))
        elif isinstance(arg, Vector):
            v = Vec3(arg.x, arg.y, arg.z)
            conv_pos(v)
            ret.append(v)
        elif isinstance(arg, Quaternion):
            q = Quat(arg.x, arg.y, arg.z, arg.w)
            conv_rot(q)
            ret.append(q)
        else:
            raise ValueError(f"bad conv type {type(arg)}")
    if len(ret) == 1:
        return ret[0]
    else:
        return tuple(ret)

def yaw_pitch_roll_to_matrix(rotation):
    rotation = tuple(map(lambda x: -math.radians(x), rotation))
    yaw   = Matrix.Rotation(rotation[0], 4, 'Z')
    pitch = Matrix.Rotation(rotation[1], 4, 'X')
    roll  = Matrix.Rotation(rotation[2], 4, 'Y')
    return (yaw @ pitch @ roll)

def matrix_to_yaw_pitch_roll(m):
    yaw = math.atan2(m[0][1], m[1][1])
    pitch = math.asin(-m[2][1])
    roll = math.atan2(m[2][0], m[2][2])
    return tuple(map(math.degrees, (yaw, pitch, roll)))
