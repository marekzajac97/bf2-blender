import bpy
import bmesh
from mathutils import Quaternion, Vector, Euler, Matrix
import struct
import math
import os
import numpy as np

from .bf2.bf2_animation import BF2Animation, BF2KeyFrame
from .bf2.bf2_skeleton import BF2Skeleton
from .bf2.bf2_mesh import BF2Mesh

def _to_matrix(pos, rot):
    matrix = rot.to_matrix()
    matrix.resize_4x4()
    matrix.translation = pos
    return matrix

def _set_bone_rot(bone, deg, axis):
    bone['bf2_rot_fix'] = Matrix.Rotation(math.radians(deg), 4, axis)

def _get_bone_rot(bone):
    return Matrix(bone['bf2_rot_fix'])

class SceneManipulator:
    
    def __init__(self, scene):
        self.scene = scene
    
    def _convert_bf2_pos_rot(self, pos, rot):
        z = pos.z
        y = pos.y
        pos.z = y
        pos.y = z
        
        z = rot.z
        y = rot.y
        rot.z = y
        rot.y = z
        rot.invert()
    
    def get_bones_for_export(self):
        ske_data = self._find_active_skeleton()
        if not ske_data:
            return dict()
        else:
            rig, skeleton = ske_data

            inc_mesh_bones = set()
            for obj in bpy.data.objects:
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object == rig:
                        vertex_group_id_to_name = dict()
                        for vg in obj.vertex_groups:
                            vertex_group_id_to_name[vg.index] = vg.name
                        for v in obj.data.vertices:
                            if len(v.groups) > 0:
                                inc_mesh_bones.add(vertex_group_id_to_name[v.groups[0].group])

            inc_bones = dict()
            for i, node in enumerate(skeleton.node_list()):
                if i in self._ske_weapon_part_ids(skeleton) and node.name not in inc_mesh_bones:
                    inc_bones[node.name] = False # mesh bone not part of the animated weapon
                else:
                    inc_bones[node.name] = True
            return inc_bones
    
    def export_animation(self, baf_file, bones_to_export=None, fstart=None, fend=None):
        
        if not self._find_active_skeleton():
            raise RuntimeError("No active skeleton found!")
            
        rig, skeleton = self._find_active_skeleton()
        
        fstart = self.scene.frame_start if fstart is None else fstart
        fend = self.scene.frame_end if fend is None else fend
        
        saved_frame = self.scene.frame_current
        
        nodes = skeleton.node_list()

        if bones_to_export is None:
            bones_to_export = [n.name for n in nodes]
        
        # initialize BF2 animation
        baf = BF2Animation()
        baf.frame_num = fend - fstart + 1
        for bone_idx, node in enumerate(nodes):
            if node.name in bones_to_export:
                baf.bones[bone_idx] = list()

        # for each frame...
        for frame_idx in range(fstart, fend + 1):
            self.scene.frame_set(frame_idx)
            bpy.context.view_layer.update()

            # for each bone...
            for bone_idx, node in enumerate(nodes):

                if not bone_idx in baf.bones:
                    continue
                
                pose_bone = rig.pose.bones[node.name]
 
                # convert to parent space and fix rotations
                parent_matrix = Matrix.Identity(4)
                if pose_bone.parent:
                    parent_matrix = pose_bone.parent.matrix @ _get_bone_rot(pose_bone.parent.bone).inverted()
                matrix = parent_matrix.inverted() @ pose_bone.matrix
                matrix @= _get_bone_rot(pose_bone.bone).inverted()

                pos, rot, _ = matrix.decompose()
                self._convert_bf2_pos_rot(pos, rot)
                frame = BF2KeyFrame(pos=pos, rot=rot)
                baf.bones[bone_idx].append(frame)
        
        # revert to frame before export
        self.scene.frame_set(saved_frame)
        
        baf.export(baf_file)
    
    def _create_camera(self, rig):
        armature = rig.data
        if 'Camerabone' in armature.bones:
            cam_name = 'Camerabone_Camera'
            # remove old one
            if cam_name in bpy.data.objects:
                camera_object = bpy.data.objects[cam_name]
                camera_data = camera_object.data
                bpy.data.objects.remove(camera_object, do_unlink=True)
                bpy.data.cameras.remove(camera_data, do_unlink=True)
            
            # create camera
            camera_data = bpy.data.cameras.new(name=cam_name)
            camera_data.lens_unit = 'FOV'
            camera_data.angle = math.radians(90)
            camera_object = bpy.data.objects.new(cam_name, camera_data)
            self.scene.collection.objects.link(camera_object)
            
            # position to bone
            camerabone = armature.bones['Camerabone']
            camera_object.matrix_local = camerabone.matrix_local
            
            # create constrains to follow the camerabone position
            constraint = camera_object.constraints.new(type='CHILD_OF')
            constraint.target = rig
            constraint.subtarget = camerabone.name
    
    def import_animation(self, baf_file):
        baf = BF2Animation(baf_file)
        
        if not self._find_active_skeleton():
            raise RuntimeError("need to import skeleton first!")
            
        rig, skeleton = self._find_active_skeleton()
        armature = rig.data
        
        self._create_camera(rig)
        
        bpy.context.view_layer.objects.active = rig
        
        bpy.ops.object.mode_set(mode='POSE')
        armature.pose_position = "POSE"

        self.scene.frame_start = 0
        self.scene.frame_end = baf.frame_num - 1
        self.scene.render.fps = 24 # BF2 hardcoded default
        
        # fix node pos/rot
        nodes = skeleton.node_list()
        for node in nodes:
            self._convert_bf2_pos_rot(node.pos, node.rot)
        
        # get 'rest' pose matrix in armature space
        node_to_rest_matrix = dict()
        for n in nodes:
            rest_bone = armature.bones[n.name]
            node_to_rest_matrix[rest_bone.name] = rest_bone.matrix_local @ _get_bone_rot(rest_bone).inverted()

        # for each frame...
        for frame_idx in range(baf.frame_num):
            # for each bone...
            for bone_idx, frames in baf.bones.items():
                frame = frames[frame_idx]
                pos = frame.pos.copy()
                rot = frame.rot.copy()
                self._convert_bf2_pos_rot(pos, rot)
                node = nodes[bone_idx]
                pose_bone = rig.pose.bones[node.name]

                # bone transforms in .baf are in parent bone space
                # bone transforms in blender are in parent and 'rest' pose space (wtf seriously)

                # matrix at this frame (parent space)
                matrix = _to_matrix(pos, rot) @ _get_bone_rot(pose_bone.bone)

                # from parent space to armature space
                parent_matrix = Matrix.Identity(4)
                if pose_bone.bone.parent:
                    parent_matrix = node_to_rest_matrix[pose_bone.bone.parent.name]
                matrix = parent_matrix @ matrix

                # back to rest bone space
                pose_bone.matrix_basis = pose_bone.bone.matrix_local.inverted() @ matrix

                pose_bone.keyframe_insert(data_path="location", frame=frame_idx)
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame_idx)

        bpy.ops.object.mode_set(mode='OBJECT')
    
    def _is_3p(self, skeleton):
        return skeleton.name.startswith('3p')
        
    def _ske_weapon_part_ids(self, skeleton):
        ids = list()
        for i, bone in enumerate(skeleton.node_list()):
            if self._is_3p(skeleton):
                max_weapon_parts = 8
            else:
                max_weapon_parts = 32
            if bone.name.startswith('mesh') and int(bone.name[4:]) <= max_weapon_parts:
                ids.append(i)
        return ids

    def _find_active_skeleton(self):
        rig_obj = None
        # check selected ones first
        for obj in bpy.context.selected_objects:
            if 'bf2_skeleton' in obj.data.keys():
                rig_obj = obj
                break
        # try to find any
        for obj in bpy.data.objects:
            if 'bf2_skeleton' in obj.data.keys():
                rig_obj = obj
                break
        if rig_obj:
            skeleton = BF2Skeleton.from_dict(rig_obj.data['bf2_skeleton'].to_dict())
            return (rig_obj, skeleton)
        return None
    
    def _link_to_skeleton(self, rig_obj, skeleton):
        rig_obj.data['bf2_skeleton'] = skeleton.to_dict()
    
    def import_skeleton(self, skeleton_file, reload=False):
        skeleton = BF2Skeleton(skeleton_file)

        if reload and self._find_active_skeleton():
            obj, _ = self._find_active_skeleton()
            armature = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.armatures.remove(armature, do_unlink=True)
        
        armature = bpy.data.armatures.new(skeleton.name)
        rig = bpy.data.objects.new(skeleton.name, armature)
        self.scene.collection.objects.link(rig)
        
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        
        # copy Skeleton and fix node pos/rot
        nodes = skeleton.node_list()
        for node in nodes:
            self._convert_bf2_pos_rot(node.pos, node.rot)
 
        for i, node in enumerate(nodes):
            
            bone = armature.edit_bones.new(node.name)
            
            # transform is in armature space, so first need to move bone to origin
            bone.head = [0, 0, 0]
            
            # this is to unfuck (and refuck during export) rotation of bone in blender
            # head/tail position is directly tied to bone rotation (exept bone roll)
            # so if the bone points "up" then it's the same as if it was rotated by 90 deg
            _set_bone_rot(bone, 90, 'X')

            if node.childs and node.childs[0].pos.z < 0.0:
                # quck hack to fix some bone rotations
                # right ones seem to point in the opposite direction in the BF2 skeleton export
                _set_bone_rot(bone, -90, 'X')

            # get the lenght
            if len(node.childs) == 1:
                bone_len = node.childs[0].pos.length # pos is relative to parrent
                if bone_len < 0.01:
                    bone_len = 0.01
            elif node.parent and not node.childs and not node.name.startswith('mesh'):    
                bone_len = 0.01 # finger ends etc
            else:
                bone_len = 0.03 # 'lone' bones

            bone.tail = [0, 0, bone_len]
            
            # calculate and apply position/rotation in armature space
            armature_space_matrix = Matrix.Identity(4)
            parents = list()
            parent = node.parent
            while parent:
                parents.append(parent)
                parent = parent.parent
            parents.reverse()
            for p in parents:
                armature_space_matrix @= _to_matrix(p.pos, p.rot)
            
            weapon_parts = self._ske_weapon_part_ids(skeleton)
            
            if i in weapon_parts:
                # have to keep all wepon parts in scene origin
                # otherwise weapon parts may not map properly later
                matrix = Matrix.Identity(4)
            else:
                matrix = armature_space_matrix @ _to_matrix(node.pos, node.rot)
            
            # rotate & translate
            bone.matrix = matrix @ _get_bone_rot(bone)
            
            # link bones
            if node.parent:
                bone.parent = armature.edit_bones[node.parent.name]
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # add skeleton metadata to rig
        self._link_to_skeleton(rig, skeleton)
    
    def import_mesh(self, mesh_file, geom=0, lod=0, mod_path='', reload=False):
        bf2_mesh = BF2Mesh(mesh_file)

        mesh_obj = self._import_mesh_geometry(bf2_mesh.name, bf2_mesh, geom, lod, mod_path, reload)
        
        if bf2_mesh.isSkinnedMesh:
            self._import_rig_skinned_mesh(mesh_obj, bf2_mesh, geom, lod)
        elif bf2_mesh.isBundledMesh:
            self._import_rig_bundled_mesh(mesh_obj, bf2_mesh, geom, lod)
    
    def _roatate_uv(self, uv, angle):
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

    def _import_mesh_geometry(self, name, bf2_mesh, geom, lod, mod_path, reload):
        if reload and name in bpy.data.objects:
            obj = bpy.data.objects[name]
            obj_mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(obj_mesh, do_unlink=True)
        
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

            for i in range(mat.vstart, mat.vstart + mat.vnum + 1):
                vi = i * int(bf2_mesh.vertstride /  bf2_mesh.vertformat)
                x = bf2_mesh.vertices[vi + 0]
                y = bf2_mesh.vertices[vi + 1]
                z = bf2_mesh.vertices[vi + 2]
                verts.append((x, z, y))

        bm = bmesh.new()

        for vert in verts:
            bm.verts.new(vert)

        bm.verts.ensure_lookup_table()

        for material_index, _faces in enumerate(faces):
            for face  in _faces:
                face_verts = [bm.verts[i] for i in face]
                bm_face = bm.faces.new(face_verts)
                bm_face.material_index = material_index

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        
        # load normals, UVs
        normal_off = bf2_mesh.get_normal_offset()
        vertex_normals = list()
        
        uv_off = bf2_mesh.get_textc_offset(0)
        vert_uv = list()
        for i, mat in enumerate(bf2_lod.materials):
            for j in range(mat.vstart, mat.vstart + mat.vnum + 1):
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
            uv = self._roatate_uv(vert_uv[l.vertex_index], -90.0) # the only way it can display properly
            uvlayer.data[l.index].uv = uv

        mesh.calc_tangents()

        # textures / materials
        if mod_path:
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
                    diffuse = bpy.data.images.load(os.path.join(mod_path, bf2_mat.maps[0].decode('ascii')))
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
                    normal = bpy.data.images.load(os.path.join(mod_path, bf2_mat.maps[1].decode('ascii')))
                    normal_tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
                    normal_tex_node.image = normal
                    material.node_tree.links.new(normal_tex_node.outputs[0], principled_BSDF.inputs[22]) # color -> normal
                except Exception:
                    pass
    
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)

        return obj
    
    def _import_rig_bundled_mesh(self, mesh_obj, bf2_mesh, geom, lod):
        
        if not self._find_active_skeleton():
            return # ignore if skeleton not loaded
            
        rig, skeleton = self._find_active_skeleton()

        bf2_lod = bf2_mesh.geoms[geom].lods[lod]
        
        off = bf2_mesh.get_wight_offset()
        
        # find which part vertex bbelongs to
        vert_part_id = list()
        for mat in bf2_lod.materials:
            for j in range(mat.vstart, mat.vstart + mat.vnum + 1):
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
    
    def _import_rig_skinned_mesh(self, mesh_obj, bf2_mesh, geom, lod):
        
        if not self._find_active_skeleton():
            return # ignore if skeleton not loaded
            
        rig, skeleton = self._find_active_skeleton()
        armature = rig.data
        
        bpy.context.view_layer.objects.active = rig
        
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
                self._convert_bf2_pos_rot(pos, rot)
                bone_obj = id_to_bone[bf2_bone.id]
                bone_obj.matrix = _to_matrix(pos, rot) @ _get_bone_rot(bone_obj)
                rig_bones.append(bone_obj.name)
            rigs_bones.append(rig_bones)
        
        # get weigths from bf2 mesh
        vert_weigths = list()
        for i, mat in enumerate(bf2_lod.materials):
            rig_bones = rigs_bones[i]
            for j in range(mat.vstart, mat.vstart + mat.vnum + 1):
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
        for i, bone_obj in id_to_bone.items():
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