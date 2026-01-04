import bpy # type: ignore
import traceback
import os
from pathlib import Path

from bpy.props import BoolProperty, StringProperty, EnumProperty, IntVectorProperty # type: ignore

from ... import get_mod_dirs
from ...core.utils import Reporter
from ...core.utils import find_root, save_img_as_dds, next_power_of_2, prev_power_of_2
from ...core.object_template import parse_geom_type, parse_geom_type_safe, NONVIS_PRFX, COL_SUFFIX
from ...core.og_lod_generator import generate_og_lod
from ...core.mesh_material import setup_material


LOD_TEXTURE_MAX_SIZE = 2048
LOD_TEXTURE_MIN_SIZE = 16

def set_txt_size(self, value, index):
    prev_val = getattr(self, f'plane_{index}_txt_size')
    val = list(value)
    for i in range(2):
        if val[i] > prev_val[i]:
            val[i] = next_power_of_2(val[i])
        else:
            val[i] = prev_power_of_2(val[i])
        val[i] = max(LOD_TEXTURE_MIN_SIZE, val[i])
        val[i] = min(LOD_TEXTURE_MAX_SIZE, val[i])
    self[f'plane_{index}_txt_size'] = val

def get_txt_size(self, index):
    def_val = tuple(self.bl_rna.properties[f'plane_{index}_txt_size'].default_array)
    return self.get(f'plane_{index}_txt_size', def_val)

# for some reason lambdas in get/set crash Blender.. so have to do it this way
def make_txt_size_setter(index):
    def fun(self, value):
        set_txt_size(self, value, index)
    return fun

def make_txt_size_getter(index):
    def fun(self):
        return get_txt_size(self, index)
    return fun

class OBJECT_OT_bf2_gen_og_lod(bpy.types.Operator):
    bl_idname = "bf2.gen_og_lod"
    bl_label = "Generate OG LOD"
    bl_description = "Generate Overgrowth low quality mesh from the normal OG mesh"

    texture_dir: StringProperty (
            name="Save texture to",
            subtype="DIR_PATH"
        ) # type: ignore

    dds_compression : EnumProperty(
        name="Texture format",
        default=3,
        items=[
            ('NONE', "NONE", "", 0),
            ('DXT1', "DXT1", "", 1),
            ('DXT3', "DXT3", "", 2),
            ('DXT5', "DXT5", "", 3),
        ]
    ) # type: ignore

    target_channel : EnumProperty(
        name="Target texture channel",
        default=0,
        items=[
            ('BASE', "Base", "", 0),
            ('DETAIL', "Detail", "", 1),
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
        set=make_txt_size_setter(0),
        get=make_txt_size_getter(0)
    ) # type: ignore

    plane_1_txt_size: IntVectorProperty(
        name="Left/Right plane texture size",
        default=(256, 256),
        size=2,
        set=make_txt_size_setter(1),
        get=make_txt_size_getter(1)
    ) # type: ignore

    plane_2_txt_size: IntVectorProperty(
        name="Top/Bottom plane texture size",
        default=(256, 256),
        size=2,
        set=make_txt_size_setter(2),
        get=make_txt_size_getter(2)
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label( text="Texture directory:")
        layout.prop(self, "texture_dir", text='')
        row = layout.row()
        row.column().label( text="DDS format:")
        row.column().prop(self, "dds_fmt", text='')
        row = layout.row()
        row.column().label( text="Target channel:")
        row.column().prop(self, "target_channel", text='')
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

        for mod_path in mod_paths:
            try:
                Path(out_path).relative_to(mod_path).as_posix().lower()
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
            save_img_as_dds(texture, out_path, self.dds_compression)
            bpy.data.images.remove(texture)

            # apply material
            material = bpy.data.materials.new(obj_name + '_material')
            lod0.data.materials.append(material)
            material.bf2_shader = 'STATICMESH'
            material.is_bf2_vegitation = True
            material.bf2_alpha_mode = 'ALPHA_TEST'
            if self.target_channel == 'BASE':
                material.texture_slot_0 = out_path
            else:
                material.texture_slot_1 = out_path
            material.is_bf2_material = True
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

class OBJECT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        self.layout.operator(OBJECT_OT_bf2_gen_og_lod.bl_idname)

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

def register():
    bpy.utils.register_class(OBJECT_SELECT_OT_bf2_by_lm_size)
    bpy.utils.register_class(OBJECT_SELECT_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_select_object.append(menu_func_object_select)

    bpy.utils.register_class(OBJECT_SHOWHIDE_OT_bf2_show_hide)
    bpy.utils.register_class(OBJECT_SHOWHIDE_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_object_showhide.append(menu_func_object_showhide)

    bpy.utils.register_class(OBJECT_OT_bf2_gen_og_lod)
    bpy.utils.register_class(OBJECT_MT_bf2_submenu)
    bpy.types.VIEW3D_MT_object.append(menu_func_object)

def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func_object)
    bpy.utils.unregister_class(OBJECT_MT_bf2_submenu)
    bpy.utils.unregister_class(OBJECT_OT_bf2_gen_og_lod)

    bpy.types.VIEW3D_MT_object_showhide.remove(menu_func_object_showhide)
    bpy.utils.unregister_class(OBJECT_SHOWHIDE_MT_bf2_submenu)
    bpy.utils.unregister_class(OBJECT_SHOWHIDE_OT_bf2_show_hide)

    bpy.types.VIEW3D_MT_select_object.remove(menu_func_object_select)
    bpy.utils.unregister_class(OBJECT_SELECT_MT_bf2_submenu)
    bpy.utils.unregister_class(OBJECT_SELECT_OT_bf2_by_lm_size)
