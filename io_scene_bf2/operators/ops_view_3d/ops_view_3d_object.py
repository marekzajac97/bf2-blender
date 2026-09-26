import bpy # type: ignore
import bmesh # type: ignore
import traceback
import re
import os
from pathlib import Path

from bpy.props import BoolProperty, StringProperty, EnumProperty, IntVectorProperty, IntProperty, FloatProperty # type: ignore

from ..utils import RegisterFactory
from ..ops_prefs import get_mod_dirs

from ...core.utils import Reporter
from ...core.utils import (find_root, save_img_as_dds,
                           set_power_of_two_int_array,
                           get_power_of_two_int_array,
                           matrix_to_yaw_pitch_roll, swap_zy,
                           strip_geom_lod_prefix)
from ...core.object_template import parse_geom_type, parse_geom_type_safe, NONVIS_PRFX, COL_SUFFIX, ANCHOR_PREFIX
from ...core.tools.og_lod_generator import generate_og_lod, compute_optimal_texture_sizes
from ...core.tools.fence_generator import make_objects_on_curve
from ...core.material import setup_material

def _strip_numeric_suffix(s):
    if '.' not in s:
        return s
    head, tail = s.rsplit('.', 1)
    if tail.isnumeric():
        return head

class OBJECT_OT_bf2_gen_og_lod(bpy.types.Operator):
    bl_idname = "bf2.gen_og_lod"
    bl_label = "Generate OG LOD"
    bl_description = "Generate Overgrowth low quality mesh from the normal OG mesh"

    texture_dir: StringProperty (
            name="Save texture to",
            subtype="DIR_PATH"
        ) # type: ignore

    dds_fmt : EnumProperty(
        name="Texture format",
        default=3,
        items=[
            ('NONE', "NONE", "", 0),
            ('DXT1', "DXT1", "", 1),
            ('DXT3', "DXT3", "", 2),
            ('DXT5', "DXT5", "", 3),
        ]
    ) # type: ignore

    plane_0_enabled: BoolProperty(
        name="Front/Back plane enabled",
        default=True
    ) # type: ignore

    plane_1_enabled: BoolProperty(
        name="Left/Right plane enabled",
        default=True
    ) # type: ignore

    plane_2_enabled: BoolProperty(
        name="Top/Bottom plane enabled",
        default=False
    ) # type: ignore

    plane_0_side : EnumProperty(
        name="Front/Back plane",
        default=0,
        items=[
            ('FRONT', "Front", "", 0),
            ('BACK', "Back", "", 1),
        ]
    ) # type: ignore

    plane_1_side : EnumProperty(
        name="Left/Right plane",
        default=0,
        items=[
            ('RIGHT', "Right", "", 0),
            ('LEFT', "Left", "", 1),
        ]
    ) # type: ignore

    plane_2_side : EnumProperty(
        name="Top/Bottom plane",
        default=0,
        items=[
            ('TOP', "Top", "", 0),
            ('BOTTOM', "Bottom", "", 1),
        ]
    ) # type: ignore

    plane_0_txt_size: IntVectorProperty(
        name="Front/Back plane texture size",
        default=(256, 256),
        size=2,
        min=16,
        max=2048,
        set=set_power_of_two_int_array('plane_0_txt_size'),
        get=get_power_of_two_int_array('plane_0_txt_size')
    ) # type: ignore

    plane_1_txt_size: IntVectorProperty(
        name="Left/Right plane texture size",
        default=(256, 256),
        size=2,
        min=16,
        max=2048,
        set=set_power_of_two_int_array('plane_1_txt_size'),
        get=get_power_of_two_int_array('plane_1_txt_size')
    ) # type: ignore

    plane_2_txt_size: IntVectorProperty(
        name="Top/Bottom plane texture size",
        default=(256, 256),
        size=2,
        min=16,
        max=2048,
        set=set_power_of_two_int_array('plane_2_txt_size'),
        get=get_power_of_two_int_array('plane_2_txt_size')
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label( text="Texture directory:")
        layout.prop(self, "texture_dir", text='')
        row = layout.row()
        row.column().label( text="DDS format:")
        row.column().prop(self, "dds_fmt", text='')
        row = layout.row()
        for i in range(3):
            row = layout.row()
            row.prop(self, f'plane_{i}_enabled', text='')
            col = row.row()
            col.prop(self, f'plane_{i}_side', text='')
            col.prop(self, f'plane_{i}_txt_size', text='')
            col.enabled = getattr(self, f'plane_{i}_enabled')

    def execute(self, context):
        root = find_root(context.view_layer.objects.active)
        _, obj_name = parse_geom_type(root)
        obj_name += '_lod'
        if not self.texture_dir or not os.path.isdir(self.texture_dir):
            self.report({"ERROR"}, "Provided directory is not valid")
            return {'CANCELLED'}

        out_path = os.path.join(self.texture_dir, obj_name + '.dds')
        out_path = os.path.normpath(out_path)
        mod_paths = get_mod_dirs(context)
        if not mod_paths:
            self.report({"ERROR"}, f'MOD Path must be defined in add-on preferences')
            return {'CANCELLED'}

        test_path = Path(out_path)
        for mod_path in mod_paths:
            try:
                test_path.relative_to(mod_path).as_posix().lower()
                break
            except ValueError:
                mod_path = ''

        if not mod_path:
            self.report({"ERROR"}, f'Given path: "{out_path}" is not relative to one of the MOD paths defined in add-on preferences')
            return {'CANCELLED'}

        try:
            projections = list()
            for i in range(3):
                if not getattr(self, f'plane_{i}_enabled'):
                    continue
                _type = getattr(self, f'plane_{i}_side')
                _size_x, _size_y = getattr(self, f'plane_{i}_txt_size')
                projections.append((_type, _size_x, _size_y))

            if not projections:
                self.report({"ERROR"}, 'At least one plane must be selected')
                return {'CANCELLED'}

            lod0, texture = generate_og_lod(root, projections)
            save_img_as_dds(texture, out_path, self.dds_fmt)
            bpy.data.images.remove(texture)

            # apply material
            material = bpy.data.materials.new(obj_name + '_material')
            lod0.data.materials.append(material)
            material.bf2_shader = 'STATICMESH'
            material.is_bf2_vegitation = True
            material.bf2_alpha_mode = 'ALPHA_TEST'
            material.is_bf2_material = True # must be set before 'texture_slot_X' to properly make the path relative
            material.texture_slot_0 = out_path
            setup_material(material, texture_paths=[mod_path], reporter=Reporter(self.report))

            # build hierarchy
            root = bpy.data.objects.new('StaticMesh_' + obj_name, None)
            geom0 = bpy.data.objects.new('G0__' + obj_name, None)
            geom0.parent = root
            lod0.name = 'G0L0__' + obj_name
            lod0.data.name = lod0.name
            lod0.parent = geom0
            context.scene.collection.objects.link(root)
            context.scene.collection.objects.link(geom0)
            context.scene.collection.objects.link(lod0)

        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        try:
            root = find_root(context.view_layer.objects.active)
            base_sizes = dict()
            for i in range(3):
                side = getattr(self, f'plane_{i}_side')
                base_sizes[side] = max(getattr(self, f'plane_{i}_txt_size'))
            sizes = compute_optimal_texture_sizes(root, base_sizes)
            for i in range(3):
                side = getattr(self, f'plane_{i}_side')
                if side in sizes:
                    setattr(self, f'plane_{i}_txt_size', sizes[side])
        except Exception:
            pass
        return context.window_manager.invoke_props_dialog(self, width=300)

    @classmethod
    def poll(cls, context):
        try:
            if not context.view_layer.objects.active:
                cls.poll_message_set("No object active")
                return False
            root = find_root(context.view_layer.objects.active)
            geom_type, _ = parse_geom_type(root)
            if geom_type != 'StaticMesh':
                cls.poll_message_set("selected object is not BF2 ObjectTemplate or isn't a StaticMesh")
                return False
            return True
        except Exception as e:
            cls.poll_message_set(str(e))
            return False


# --------------------------------------------------------------------

def _vec_to_str(vec):
    return '/'.join(f'{num:.4f}' for num in vec)

class OBJECT_OT_make_object_con_def(bpy.types.Operator):
    bl_idname = "bf2.make_object_con_def"
    bl_label = "Export as .con"
    bl_description = "Generate .con definitions for selected objects and save it to the clipboard"

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No objects selected")
        return context.selected_objects

    def execute(self, context):
        result = ""
        for obj in context.selected_objects:
            matrix_world = obj.matrix_world
            pos = swap_zy(matrix_world.translation)
            rot = matrix_to_yaw_pitch_roll(matrix_world)
            name = _strip_numeric_suffix(obj.name)
            name = strip_geom_lod_prefix(name)
            result += f'rem *** {name} ***\n'
            result += f'Object.create {name}\n'
            if pos != (0.0, 0.0, 0.0):
                result += f'Object.absolutePosition {_vec_to_str(pos)}\n'
            if rot != (0.0, 0.0, 0.0):
                result += f'Object.rotation {_vec_to_str(rot)}\n'
            result += f'Object.layer 1\n\n'
        context.window_manager.clipboard = result
        self.report({"INFO"}, 'The result has been saved to the clipboard')
        return {'FINISHED'}

# --------------------------------------------------------------------

_GEOM_INDEX_RE = re.compile(r'geom(\d+)', re.IGNORECASE)
_LOD_INDEX_RE = re.compile(r'lod(\d+)', re.IGNORECASE)
_COL_INDEX_RE = re.compile(r'col(\d+)', re.IGNORECASE)

def _parse_staticmesh_part(obj):
    name = _strip_numeric_suffix(obj.name) or obj.name
    name = name.lower()
    geom_match = _GEOM_INDEX_RE.search(name)
    geom_idx = int(geom_match.group(1)) if geom_match else 0
    col_match = _COL_INDEX_RE.search(name)
    if col_match:
        return 'col', geom_idx, int(col_match.group(1))
    lod_match = _LOD_INDEX_RE.search(name)
    if lod_match:
        return 'lod', geom_idx, int(lod_match.group(1))
    return None, geom_idx, None

def _generate_decimated_lod(context, base_obj, geom_obj, obj_name, geom_idx, lod_idx, ratio):
    name = f'G{geom_idx}L{lod_idx}__{obj_name}'
    mesh = base_obj.data.copy()
    mesh.name = name
    new_obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(new_obj)

    new_obj.parent = geom_obj
    new_obj.rotation_mode = base_obj.rotation_mode
    new_obj.location = base_obj.location.copy()
    new_obj.rotation_euler = base_obj.rotation_euler.copy()
    new_obj.rotation_quaternion = base_obj.rotation_quaternion.copy()
    new_obj.scale = base_obj.scale.copy()

    modifier = new_obj.modifiers.new(name="Decimate", type='DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = max(ratio, 0.01)

    for prop in ('bf2_object_type', 'bf2_object_type_enum',
                 'bf2_object_type_manual_mode', 'bf2_lightmap_size'):
        if hasattr(base_obj, prop):
            setattr(new_obj, prop, getattr(base_obj, prop))
    return new_obj

def _build_staticmesh_hierarchy(context, obj_name, objects,
                                generate_lods=False, lod_count=1, lod_ratio=0.5):
    if not obj_name:
        raise ValueError("ObjectTemplate name must not be empty")

    visible = dict()
    collisions = dict()
    for obj in objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        kind, geom_idx, part_idx = _parse_staticmesh_part(obj)
        if kind == 'col':
            if not 0 <= part_idx <= 3:
                raise ValueError(f"'{obj.name}': collision index must be in range 0-3")
            cols = collisions.setdefault(geom_idx, dict())
            if part_idx in cols:
                raise ValueError(f"'{obj.name}': duplicated collision mesh COL{part_idx} for geom {geom_idx}")
            cols[part_idx] = obj
        elif kind == 'lod':
            lods = visible.setdefault(geom_idx, dict())
            if part_idx in lods:
                raise ValueError(f"'{obj.name}': duplicated LOD{part_idx} for geom {geom_idx}")
            lods[part_idx] = obj
        else:
            raise ValueError(f"'{obj.name}': name must contain 'lod' (visible mesh) or 'col' (collision mesh)")

    if not visible:
        raise ValueError("No visible mesh objects selected (name them with 'lod', e.g. 'lod0')")

    if generate_lods:
        for geom_idx, lods in visible.items():
            if 0 not in lods:
                raise ValueError(f"Cannot generate LODs for geom {geom_idx}: no LOD0 mesh selected")

    for geom_idx in collisions:
        if geom_idx not in visible or 0 not in visible[geom_idx]:
            raise ValueError(f"Collision meshes selected for geom {geom_idx}, but there is no visible LOD0 mesh for it")

    root_obj = bpy.data.objects.new('StaticMesh_' + obj_name, None)
    context.scene.collection.objects.link(root_obj)

    anchor_obj = bpy.data.objects.new(ANCHOR_PREFIX + obj_name, None)
    anchor_obj.parent = root_obj
    context.scene.collection.objects.link(anchor_obj)

    for geom_idx in sorted(visible):
        geom_obj = bpy.data.objects.new(f'G{geom_idx}__{obj_name}', None)
        geom_obj.parent = root_obj
        context.scene.collection.objects.link(geom_obj)

        lods = visible[geom_idx]
        if generate_lods:
            base_obj = lods[0]
            for lod_idx in range(1, lod_count):
                if lod_idx in lods:
                    continue
                ratio = lod_ratio ** lod_idx
                lods[lod_idx] = _generate_decimated_lod(context, base_obj, geom_obj,
                                                        obj_name, geom_idx, lod_idx, ratio)

        for lod_idx in sorted(lods):
            lod_obj = lods[lod_idx]
            lod_name = f'G{geom_idx}L{lod_idx}__{obj_name}'
            lod_obj.name = lod_name
            lod_obj.data.name = lod_name
            lod_obj.parent = geom_obj

        if geom_idx in collisions:
            nonvis_obj = bpy.data.objects.new(f'{NONVIS_PRFX}_G{geom_idx}__{obj_name}', None)
            nonvis_obj.parent = lods[0]
            context.scene.collection.objects.link(nonvis_obj)
            for col_idx in sorted(collisions[geom_idx]):
                col_obj = collisions[geom_idx][col_idx]
                col_name = f'G{geom_idx}__{obj_name}_{COL_SUFFIX}{col_idx}'
                col_obj.name = col_name
                col_obj.data.name = col_name
                col_obj.parent = nonvis_obj

    return root_obj

class OBJECT_OT_bf2_staticmesh_wizard(bpy.types.Operator):
    bl_idname = "bf2.staticmesh_wizard"
    bl_label = "StaticMesh Wizard"
    bl_description = "Build a StaticMesh ObjectTemplate export hierarchy from the selected mesh objects"

    object_name: StringProperty(
        name="ObjectTemplate Name",
        description="Name of the root ObjectTemplate",
        default=""
    ) # type: ignore

    generate_lods: BoolProperty(
        name="Generate LODs",
        description="Generate lower-detail LODs from LOD0 by applying a Decimate modifier",
        default=False
    ) # type: ignore

    lod_count: IntProperty(
        name="Number of LODs",
        description="Total number of LODs (LOD0 included) to generate for each geom",
        default=3,
        min=1,
        max=6
    ) # type: ignore

    lod_ratio: FloatProperty(
        name="LOD Decimate Ratio",
        description="Fraction of faces kept by each consecutive LOD relative to LOD0",
        default=0.5,
        min=0.01,
        max=1.0
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "object_name")
        layout.prop(self, "generate_lods")
        col = layout.column()
        col.enabled = self.generate_lods
        col.prop(self, "lod_count")
        col.prop(self, "lod_ratio")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def execute(self, context):
        try:
            _build_staticmesh_hierarchy(context, self.object_name, list(context.selected_objects),
                                        generate_lods=self.generate_lods,
                                        lod_count=self.lod_count,
                                        lod_ratio=self.lod_ratio)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        if not context.selected_objects:
            cls.poll_message_set("No objects selected")
            return False
        return True

# --------------------------------------------------------------------

class OBJECT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(OBJECT_OT_bf2_gen_og_lod.bl_idname)
        self.layout.operator(OBJECT_OT_bf2_staticmesh_wizard.bl_idname)
        self.layout.operator(OBJECT_OT_make_object_con_def.bl_idname)

def menu_func_object(self, context):
    self.layout.menu(OBJECT_MT_bf2_submenu.bl_idname, text="BF2")

# --------------------------------------------------------------------

class OBJECT_SHOWHIDE_OT_bf2_show_hide(bpy.types.Operator):
    bl_idname = "bf2.object_hide_col"
    bl_label = "Show/Hide Collision Meshes"
    bl_description = "Show/Hide all Collision Meshes"

    show: BoolProperty(
        name="Show CollisionMesh",
        default=False
    ) # type: ignore

    def _exec(self, obj):
        if obj is None:
            return
        if obj.name.startswith(NONVIS_PRFX):
            for col in obj.children:
                if COL_SUFFIX in col.name:
                    col.hide_set(not self.show)
        for child in obj.children:
            self._exec(child)

    def execute(self, context):
        root = find_root(context.view_layer.objects.active)
        try:
            self._exec(root)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No object active")
        try:
            if not context.view_layer.objects.active:
                return False
            root = find_root(context.view_layer.objects.active)
            return parse_geom_type_safe(root)
        except Exception as e:
            cls.poll_message_set(str(e))
            return False

class OBJECT_SHOWHIDE_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_SHOWHIDE_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(OBJECT_SHOWHIDE_OT_bf2_show_hide.bl_idname, text="Show Collision Meshes").show = True
        self.layout.operator(OBJECT_SHOWHIDE_OT_bf2_show_hide.bl_idname, text="Hide Collision Meshes").show = False

def menu_func_object_showhide(self, context):
    self.layout.menu(OBJECT_SHOWHIDE_MT_bf2_submenu.bl_idname, text="BF2")

# --------------------------------------------------------------------

class OBJECT_SELECT_OT_bf2_by_lm_size(bpy.types.Operator):
    bl_idname = "bf2.select_object_by_lm_size"
    bl_label = "Select By Lightmap Size"

    lm_size: IntVectorProperty(
        name="Lightmap size",
        default=(256, 256),
        size=2
    ) # type: ignore

    def execute(self, context):
        for obj in bpy.data.objects:
            if tuple(obj.bf2_lightmap_size) == tuple(self.lm_size):
                obj.select_set(True)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class OBJECT_SELECT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_SELECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(OBJECT_SELECT_OT_bf2_by_lm_size.bl_idname)

def menu_func_object_select(self, context):
    self.layout.menu(OBJECT_SELECT_MT_bf2_submenu.bl_idname, text="BF2")

# --------------------------------------------------------------------

class ADD_OT_bf2_fence_object(bpy.types.Operator):
    bl_idname = "bf2.new_fence_object"
    bl_label = "(BF2) Fence on Curve"
    bl_description = "Create a fence generator object"

    def execute(self, context):
        mesh = bpy.data.meshes.new('FenceGen')
        mesh.attributes.new('instance_ref', 'INT', 'POINT')
        mesh.attributes.new('instance_pos', 'INT', 'POINT')
        mesh.attributes.new('instance_size', 'FLOAT', 'POINT')
        mesh.attributes.new('instance_offset', 'FLOAT', 'POINT')
        mesh.attributes.new('instance_translation', 'FLOAT_VECTOR', 'POINT')
        mesh.attributes.new('instance_rotation', 'QUATERNION', 'POINT')
        obj = bpy.data.objects.new(mesh.name, mesh)
        obj.location = context.scene.cursor.location
        modifier = obj.modifiers.new(type='NODES', name="GenerateFence")
        modifier.node_group = make_objects_on_curve()
        context.scene.collection.objects.link(obj)
        return {'FINISHED'}

def menu_func_add(self, context):
    self.layout.operator(ADD_OT_bf2_fence_object.bl_idname, icon='CURVE_PATH')

# --------------------------------------------------------------------

def init(rc : RegisterFactory):
    rc.reg_class(ADD_OT_bf2_fence_object)
    rc.add_menu(bpy.types.VIEW3D_MT_add, menu_func_add)

    rc.reg_class(OBJECT_SELECT_OT_bf2_by_lm_size)
    rc.reg_class(OBJECT_SELECT_MT_bf2_submenu)
    rc.add_menu(bpy.types.VIEW3D_MT_select_object, menu_func_object_select)

    rc.reg_class(OBJECT_SHOWHIDE_OT_bf2_show_hide)
    rc.reg_class(OBJECT_SHOWHIDE_MT_bf2_submenu)
    rc.add_menu(bpy.types.VIEW3D_MT_object_showhide, menu_func_object_showhide)

    rc.reg_class(OBJECT_OT_make_object_con_def)
    rc.reg_class(OBJECT_OT_bf2_gen_og_lod)
    rc.reg_class(OBJECT_OT_bf2_staticmesh_wizard)
    rc.reg_class(OBJECT_MT_bf2_submenu)
    rc.add_menu(bpy.types.VIEW3D_MT_object, menu_func_object)

register, unregister = RegisterFactory.create(init)
