import bpy
from bpy.types import Mesh, Armature, Camera

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

def delete_object(obj):
    bpy.data.objects.remove(obj, do_unlink=True)
    data = obj.data
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

def delete_object_if_exists(obj_name):
    if obj_name in bpy.data.objects:
        delete_object(bpy.data.objects[obj_name])