import bpy # type: ignore
import bmesh # type: ignore
from mathutils import Vector # type: ignore

from bpy.props import IntProperty, BoolProperty # type: ignore

from ..utils import RegisterFactory

from ...core.utils import flip_uv
from ...core.mesh import AnimUv

# --------------------------------------------------------------------

class EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix(bpy.types.Operator):
    bl_idname = "bf2.mesh_select_uv_matrix"
    bl_label = "Select Animated UV Matrix"
    bl_description = "Selects all elements with the common matrix index of the animated UVs"

    uv_matrix_index: IntProperty(
        default=0,
        options={'HIDDEN'},
        min=0,
        max=6
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Mesh has no Animated UV matrix index attribute")
        return (context.object and context.object.type == 'MESH' and
                'animuv_matrix_index' in context.object.data.attributes)

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data

        bm = bmesh.from_edit_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()

        layer = bm.verts.layers.int.get('animuv_matrix_index')

        for vert in bm.verts:
            if layer and vert[layer] == self.uv_matrix_index:
                vert.select_set(True)
            else:
                vert.select_set(False)

        bm.select_mode |= {'VERT'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}


class EDIT_MESH_SELECT_OT_bf2_select_bad_weights(bpy.types.Operator):
    bl_idname = "bf2.mesh_select_bad_weights"
    bl_label = "Select Invalid Skin Weights"
    bl_description = "Selects all elements with BF2 incompatible weights"

    select_unassigned: BoolProperty(
        name="Select Unassigned Weights",
        description="Select elements which don't have any weights assigned",
        default=True
    ) # type: ignore

    select_unnormalized: BoolProperty(
        name="Select Unnormalized Weights",
        description="Select elements whose weights don't add-up to 1",
        default=True
    ) # type: ignore

    select_too_many: BoolProperty(
        name="Select Too Many Weights",
        description="Select elements with weight count over the BF2 limit (two weights per vertex)",
        default=True
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Object has no vertex groups")
        return context.object and len(context.object.vertex_groups)

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data

        bm = bmesh.from_edit_mesh(mesh)

        deform_layer = bm.verts.layers.deform.active
        if deform_layer is None:
            self.report({'INFO'}, "No vertex groups found")
            return {'CANCELLED'}

        # Iterate over all vertices
        for vert in bm.verts:
            group_weights = vert[deform_layer].values()
            select = False
            if self.select_too_many:
                select |= len(group_weights) > 2
            if self.select_unassigned:
                select |= len(group_weights) == 0
            if self.select_unnormalized:
                select |= len(group_weights) > 1 and abs(sum(group_weights) - 1.0) > 0.0001

            vert.select_set(select)

        bm.select_mode |= {'VERT'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class EDIT_MESH_SELECT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EDIT_MESH_SELECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(EDIT_MESH_SELECT_OT_bf2_select_bad_weights.bl_idname)
        self.layout.separator(factor=1.0, type='LINE')
        op_name = EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix.bl_idname
        self.layout.operator(op_name, text="Select Left Wheel Rotation").uv_matrix_index = AnimUv.L_WHEEL_ROTATION
        self.layout.operator(op_name, text="Select Left Wheel Translation").uv_matrix_index = AnimUv.L_WHEEL_TRANSLATION
        self.layout.operator(op_name, text="Select Right Wheel Rotation").uv_matrix_index = AnimUv.R_WHEEL_ROTATION
        self.layout.operator(op_name, text="Select Right Wheel Translation").uv_matrix_index = AnimUv.R_WHEEL_TRANSLATION
        self.layout.operator(op_name, text="Select Left Track Translation").uv_matrix_index = AnimUv.L_TRACK_TRANSLATION
        self.layout.operator(op_name, text="Select Right Track Translation").uv_matrix_index = AnimUv.R_TRACK_TRANSLATION

def menu_func_edit_mesh_select(self, context):
    self.layout.menu(EDIT_MESH_SELECT_MT_bf2_submenu.bl_idname, text="BF2")

class EDIT_MESH_OT_bf2_set_anim_uv_rotation_center(bpy.types.Operator):
    bl_idname = "bf2.mesh_set_uv_rotation_center"
    bl_label = "Set Animated UV Roation Center"
    bl_description = "Sets the UV rotation center for the selected elements from either the 2D cursor location or the midpoint of all UV coordinates"

    from_2d_cursor: BoolProperty(
        default=False,
        options={'HIDDEN'},
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No mesh object is active")
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        mesh = obj.data

        uv = None
        if self.from_2d_cursor:
            uv = self. _get_2d_cursor_location(context)
        else:
            uv = self._get_uv_midpoint(obj)

        if uv is None:
            return {'CANCELLED'}

        uv = flip_uv(uv)

        if 'animuv_rot_center' not in mesh.attributes:
            mesh.attributes.new('animuv_rot_center', 'FLOAT2', 'POINT')
        mesh.attributes.active = mesh.attributes['animuv_rot_center']
        bpy.ops.mesh.attribute_set(value_float_vector_2d=uv)
        return {'FINISHED'}

    def _get_2d_cursor_location(self, context):
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                return area.spaces.active.cursor_location

        self.report({'ERROR'}, "No UV / Image Editor area found")
        return None

    def _get_uv_midpoint(self, obj):
        current_mode = bpy.context.object.mode
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        uv_layer = bm.loops.layers.uv.verify()

        uv_coords = []
        selected_verts = [v for v in bm.verts if v.select]

        if not selected_verts:
            self.report({'ERROR'}, "No vertices selected")
            bm.free()
            return None

        for vert in selected_verts:
            for loop in vert.link_loops:
                uv = loop[uv_layer].uv
                uv_coords.append(Vector((uv.x, uv.y)))

        if not uv_coords:
            self.report({'ERROR'}, "No UV coordinates found for selected vertices")
            bm.free()
            return None

        midpoint = Vector((0, 0))
        for uv in uv_coords:
            midpoint += uv
        
        midpoint /= len(uv_coords)

        bm.free()

        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=current_mode)

        return midpoint

class EDIT_MESH_OT_bf2_set_anim_uv_matrix(bpy.types.Operator):
    bl_idname = "bf2.mesh_set_uv_matrix"
    bl_label = "Assign Animated UV Matrix"
    bl_description = "Assign the matrix index for the the animated UVs"

    uv_matrix_index: IntProperty(
        default=0,
        options={'HIDDEN'},
        min=0,
        max=6
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No mesh object is active")
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.view_layer.objects.active
        mesh = obj.data
        if 'animuv_matrix_index' not in mesh.attributes:
            mesh.attributes.new('animuv_matrix_index', 'INT', 'POINT')
        mesh.attributes.active = mesh.attributes['animuv_matrix_index']
        bpy.ops.mesh.attribute_set(value_int=self.uv_matrix_index)
        return {'FINISHED'}

class EDIT_MESH_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EDIT_MESH_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        op_matrix = EDIT_MESH_OT_bf2_set_anim_uv_matrix.bl_idname
        op_rot_center = EDIT_MESH_OT_bf2_set_anim_uv_rotation_center.bl_idname
        self.layout.operator(op_rot_center, text="Set Animated UV Rotation Center (from 2D cursor)").from_2d_cursor = True
        self.layout.operator(op_rot_center, text="Set Animated UV Rotation Center (from midpoint)").from_2d_cursor = False
        self.layout.operator(op_matrix, text="Clear Wheel/Track Rotation/Translation").uv_matrix_index = AnimUv.NONE
        self.layout.operator(op_matrix, text="Assign To Left Wheel Rotation").uv_matrix_index = AnimUv.L_WHEEL_ROTATION
        self.layout.operator(op_matrix, text="Assign To Left Wheel Translation").uv_matrix_index = AnimUv.L_WHEEL_TRANSLATION
        self.layout.operator(op_matrix, text="Assign To Right Wheel Rotation").uv_matrix_index = AnimUv.R_WHEEL_ROTATION
        self.layout.operator(op_matrix, text="Assign To Right Wheel Translation").uv_matrix_index = AnimUv.R_WHEEL_TRANSLATION
        self.layout.operator(op_matrix, text="Assign To Left Track Translation").uv_matrix_index = AnimUv.L_TRACK_TRANSLATION
        self.layout.operator(op_matrix, text="Assign To Right Track Translation").uv_matrix_index = AnimUv.R_TRACK_TRANSLATION

def menu_func_edit_mesh(self, context):
    self.layout.menu(EDIT_MESH_MT_bf2_submenu.bl_idname, text="BF2")

def init(rc : RegisterFactory):
    rc.reg_class(EDIT_MESH_OT_bf2_set_anim_uv_rotation_center)
    rc.reg_class(EDIT_MESH_OT_bf2_set_anim_uv_matrix)
    rc.reg_class(EDIT_MESH_MT_bf2_submenu)
    rc.add_menu(bpy.types.VIEW3D_MT_edit_mesh, menu_func_edit_mesh)

    rc.reg_class(EDIT_MESH_SELECT_OT_bf2_select_bad_weights)
    rc.reg_class(EDIT_MESH_SELECT_OT_bf2_select_anim_uv_matrix)
    rc.reg_class(EDIT_MESH_SELECT_MT_bf2_submenu)
    rc.add_menu(bpy.types.VIEW3D_MT_select_edit_mesh, menu_func_edit_mesh_select)

register, unregister = RegisterFactory.create(init)
