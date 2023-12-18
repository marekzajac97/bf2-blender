import bpy
import bmesh
import math
import struct
import os

from mathutils import Vector, Matrix
from .bf2.bf2_mesh import BF2Mesh
from .utils import to_matrix, convert_bf2_pos_rot, delete_object_if_exists
from .skeleton import find_active_skeleton, ske_get_bone_rot, ske_weapon_part_ids

def import_mesh(context, mesh_file, geom=0, lod=0, texture_path='', reload=False):
    bf2_mesh = BF2Mesh(mesh_file)

    mesh_obj = _import_mesh_geometry(bf2_mesh.name, bf2_mesh, geom, lod, texture_path, reload)

    if bf2_mesh.isSkinnedMesh:
        _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, geom, lod)
    elif bf2_mesh.isBundledMesh:
        _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod)

    context.scene.collection.objects.link(mesh_obj)

def _roatate_uv(uv, angle):
    uv = Vector(uv)
    pivot = Vector((0.5, 0.5))
    angle = math.radians(angle)
    uv -= pivot
    uv_len = uv.length
    uv.normalize()
    uv = Vector((uv.x * math.cos(angle) - uv.y * math.sin(angle),
                    uv.x * math.sin(angle) + uv.y * math.cos(angle)))
    uv *= uv_len
    uv += pivot
    return uv

def _import_mesh_geometry(name, bf2_mesh, geom, lod, texture_path, reload):

    if reload:
        delete_object_if_exists(name)

    bf2_lod = bf2_mesh.geoms[geom].lods[lod]

    verts = list()
    faces = list()

    for mat in bf2_lod.materials:
        f_offset = len(verts)
        index_arr = bf2_mesh.index[mat.istart:mat.istart + mat.inum]
        _faces = list()
        for i in range(0, len(index_arr), 3):
            v1 = index_arr[i + 0] + f_offset
            v2 = index_arr[i + 1] + f_offset
            v3 = index_arr[i + 2] + f_offset
            _faces.append((v3, v2, v1))
        faces.append(_faces)

        for i in range(mat.vstart, mat.vstart + mat.vnum):
            vi = i * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            x = bf2_mesh.vertices[vi + 0]
            y = bf2_mesh.vertices[vi + 1]
            z = bf2_mesh.vertices[vi + 2]
            verts.append((x, z, y))

    bm = bmesh.new()
    for vert in verts:
        bm.verts.new(vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    for material_index, _faces in enumerate(faces):
        for face  in _faces:
            face_verts = [bm.verts[i] for i in face]
            try:
                bm_face = bm.faces.new(face_verts)
                bm_face.material_index = material_index
            except ValueError:
                pass
                # XXX: some meshes (e.g. vBF2 usrif_remington11-87)
                # produce "face already exists" error
                # even though vert indexes are unique
                # I don't know wtf is going on, so lets just ignore it

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    
    # load normals, UVs
    normal_off = bf2_mesh.get_normal_offset()
    vertex_normals = list()
    
    uv_off = bf2_mesh.get_textc_offset(0)
    vert_uv = list()
    for i, mat in enumerate(bf2_lod.materials):
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            x = bf2_mesh.vertices[vi + normal_off + 0]
            y = bf2_mesh.vertices[vi + normal_off + 1]
            z = bf2_mesh.vertices[vi + normal_off + 2]
            vertex_normals.append((x, z, y))
            
            u = bf2_mesh.vertices[vi + uv_off + 0]
            v = bf2_mesh.vertices[vi + uv_off + 1]
            vert_uv.append((v, u)) # this is no mistake
    
    # load normals
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.normals_split_custom_set_from_vertices(vertex_normals)
    mesh.use_auto_smooth = True

    bm.normal_update()
    bm.free()
    
    # load UVs
    uvlayer = mesh.uv_layers.new(name='DefaultUV')            
    for l in mesh.loops:
        uv = _roatate_uv(vert_uv[l.vertex_index], -90.0) # the only way it can display properly
        uvlayer.data[l.index].uv = uv

    mesh.calc_tangents()

    # textures / materials
    if texture_path:
        for i, bf2_mat in enumerate(bf2_lod.materials):
            mat_name = f'{bf2_mesh.name}_material_{i}'
            try:
                material = bpy.data.materials[mat_name]
                bpy.data.materials.remove(material, do_unlink=True)
            except:
                pass
            material = bpy.data.materials.new(mat_name)
            mesh.materials.append(material)

            material.use_nodes=True
            principled_BSDF = material.node_tree.nodes.get('Principled BSDF')
            principled_BSDF.inputs[9].default_value = 1 # set roughness

            try:
                diffuse = bpy.data.images.load(os.path.join(texture_path, bf2_mat.maps[0].decode('ascii')))
                diffuse_tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
                diffuse_tex_node.image = diffuse
                material.node_tree.links.new(diffuse_tex_node.outputs[0], principled_BSDF.inputs[0]) # color -> base color
                if bf2_mesh.isBundledMesh:
                    material.node_tree.links.new(diffuse_tex_node.outputs[1], principled_BSDF.inputs[7]) # alpha -> specular
                else:
                    principled_BSDF.inputs[7].default_value = 0 # set specular
            except Exception:
                pass

            try:
                normal = bpy.data.images.load(os.path.join(texture_path, bf2_mat.maps[1].decode('ascii')))
                normal_tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
                normal_tex_node.image = normal
                material.node_tree.links.new(normal_tex_node.outputs[0], principled_BSDF.inputs[22]) # color -> normal
            except Exception:
                pass

    obj = bpy.data.objects.new(name, mesh)
    return obj

def _import_rig_bundled_mesh(context, mesh_obj, bf2_mesh, geom, lod):
    
    if not find_active_skeleton(context):
        return # ignore if skeleton not loaded
        
    rig, skeleton = find_active_skeleton(context)

    bf2_lod = bf2_mesh.geoms[geom].lods[lod]
    
    off = bf2_mesh.get_wight_offset()
    
    # find which part vertex bbelongs to
    vert_part_id = list()
    for mat in bf2_lod.materials:
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            _data_float = bf2_mesh.vertices[vi + off]
            _data = tuple([b for b in struct.pack('f', _data_float)])
            part_id = _data[0]
            vert_part_id.append(part_id)
    
    # create vertex groups and assing verticies to them
    for vertex in mesh_obj.data.vertices:
        part_id = vert_part_id[vertex.index]
        group_name = f'mesh{part_id + 1}'
        if group_name not in mesh_obj.vertex_groups.keys():
            mesh_obj.vertex_groups.new(name=group_name)
        mesh_obj.vertex_groups[group_name].add([vertex.index], 1.0, "REPLACE")

    # parent mesh oject to armature
    mesh_obj.parent = rig
    
    # add armature modifier to the object
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = rig

def _import_rig_skinned_mesh(context, mesh_obj, bf2_mesh, geom, lod):
    
    if not find_active_skeleton(context):
        return # ignore if skeleton not loaded
        
    rig, skeleton = find_active_skeleton(context)
    armature = rig.data
    
    context.view_layer.objects.active = rig
    
    # we're gona change the 'rest' transforms of the bones
    bpy.ops.object.mode_set(mode='EDIT')
    
    bf2_lod = bf2_mesh.geoms[geom].lods[lod]
    
    id_to_bone = dict()
    for i, node in enumerate(skeleton.node_list()):
        id_to_bone[i] = armature.edit_bones[node.name]
    
    rigs_bones = list()
    for bf2_rig in bf2_lod.rigs:
        rig_bones = list()
        for bf2_bone in bf2_rig.bones:    
            m = Matrix(bf2_bone.matrix)
            m.transpose()
            m.invert()
            pos, rot, _ = m.decompose()
            convert_bf2_pos_rot(pos, rot)
            bone_obj = id_to_bone[bf2_bone.id]
            bone_obj.matrix = to_matrix(pos, rot) @ ske_get_bone_rot(bone_obj)
            rig_bones.append(bone_obj.name)
        rigs_bones.append(rig_bones)
    
    # get weigths from bf2 mesh
    vert_weigths = list()
    for i, mat in enumerate(bf2_lod.materials):
        rig_bones = rigs_bones[i]
        for j in range(mat.vstart, mat.vstart + mat.vnum):
            vi = j * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
            WIEGHTS_OFFSET = 6
            w = bf2_mesh.vertices[vi + WIEGHTS_OFFSET + 0]
            _bones_float = bf2_mesh.vertices[vi + WIEGHTS_OFFSET + 1]
            _bone_ids = tuple([b for b in struct.pack('f', _bones_float)])
            weights = [] # max two bones per vert
            
            _bone = rig_bones[_bone_ids[0]]
            weights.append((_bone, w))
            if w < 1.0:
                _bone = rig_bones[_bone_ids[1]]
                weights.append((_bone, 1.0 - w))
            vert_weigths.append(weights)

    # create vertex group for each bone
    mesh_bones = ske_weapon_part_ids(skeleton)
    for i, bone_obj in id_to_bone.items():
        if i in mesh_bones:
            continue
        mesh_obj.vertex_groups.new(name=bone_obj.name)
    
    # assign verticies to vertex groups and apply weights
    for vertex in mesh_obj.data.vertices:
        v_weights = vert_weigths[vertex.index]
        for v_bone, v_bone_weight in v_weights: 
            mesh_obj.vertex_groups[v_bone].add([vertex.index], v_bone_weight, "REPLACE")
    
    bpy.ops.object.mode_set(mode='OBJECT')

    # parent mesh oject to armature
    mesh_obj.parent = rig
    
    # add armature modifier to the object
    modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
    modifier.object = rig
