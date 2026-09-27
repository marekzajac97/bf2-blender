import bpy # type: ignore
import traceback
import os

from bpy.props import StringProperty, IntProperty, EnumProperty # type: ignore
from bpy_extras.io_utils import ImportHelper # type: ignore

from ..utils import RegisterFactory
from ..ops_prefs import get_mod_dirs
from ...core.bf2.bf2_engine import BF2Engine, Animation
from ...core.tools.anim_utils import (
    toggle_mesh_mask_mesh_for_active_bone,
    reparent_bones,
    setup_controllers,
    update_nla_setup,
    Mode,
    AnimationContext)
from ...core.skeleton import is_bf2_skeleton
from ...core.utils import Reporter

def _bf2_setup_started(context, rig):
    context.scene['bf2_is_setup'] = rig.name

def _bf2_is_setup(context):
    return context.scene.get('bf2_is_setup')

def _bf2_setup_finished(context):
    if 'bf2_is_setup' in context.scene:
        del context.scene['bf2_is_setup']

class VIEW3D_OT_bf2_anim_ctrl_setup_mask(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_mask"
    bl_label = "Mask mesh for bone"
    bl_description = "Toggle mask for weapon part that corresponds to the active bone"

    def execute(self, context):
        rig = bpy.data.objects[_bf2_is_setup(context)]
        try:
            toggle_mesh_mask_mesh_for_active_bone(context, rig)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Controller setup is not active")
        return _bf2_is_setup(context) and context.active_bone

class VIEW3D_OT_bf2_anim_ctrl_setup_begin(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_begin"
    bl_label = "Setup controllers"
    bl_description = "Setup animation controller bones and basic IK constraints"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Please move each 'meshX.CTRL' bone to the desired loaction,")
        layout.label(text="it will be used as pivot for the corresponding weapon part.")
        layout.label(text="When You are done, click 'Apply' in the Sidebar, BF2 tab (toggled with `N`)")
        layout.label(text="")
        layout.label(text="You can toggle showing only a specific weapon part that corresponds")
        layout.label(text="to the active bone with 'Mask mesh for bone'.")

    @classmethod
    def poll(cls, context):
        rig = context.view_layer.objects.active
        if not rig or not is_bf2_skeleton(rig):
            cls.poll_message_set("No skeleton selected")
            return False
        if _bf2_is_setup(context):
            cls.poll_message_set("Controller setup is already in progress")
            return False
        return True

    def execute(self, context):
        rig = context.view_layer.objects.active
        try:
            setup_controllers(context, rig, step=Mode.MAKE_CTRLS_ONLY)
            _bf2_setup_started(context, rig)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def cancel(self, context):
        bpy.ops.bf2.anim_setup_begin('INVOKE_DEFAULT')


class VIEW3D_OT_bf2_anim_ctrl_setup_end(bpy.types.Operator):
    bl_idname = "bf2.anim_setup_end"
    bl_label = "Finish setup"
    bl_description = "Finish animation controller setup"

    def execute(self, context):
        rig = bpy.data.objects[_bf2_is_setup(context)]
        try:
            with AnimationContext(context.scene, rig):
                setup_controllers(context, rig, step=Mode.APPLY_ANIMATION_ONLY)
            _bf2_setup_finished(context)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("Controller setup is not active")
        return _bf2_is_setup(context)


def _find_file(dir, matcher):
    for f in os.listdir(dir):
        fullpath = os.path.join(dir, f)
        if matcher(f.lower()) and os.path.isfile(fullpath):
            return fullpath

def _find_matching_soldier_animation(directory, anim_filepath):
    if not os.path.isdir(directory):
        return
    anim_fname = os.path.basename(anim_filepath)
    s = anim_fname.lower().split('_')
    if len(s) < 3:
        return
    animtype = s[2]

    def _match(f):
        if not f.endswith('.baf'):
            return False
        sf = f.split('_')
        if len(sf) < 2:
            return False
        if sf[1] != animtype:
            return False
        return True

    return _find_file(directory, _match)

def _parse_animation_system(context, inc_filepath):
    engine = BF2Engine()
    engine.file_manager.root_dirs = get_mod_dirs(context)
    engine.main_console.run_file(inc_filepath)
    manager = engine.get_manager(Animation)
    return list(manager.templates.values()) if manager else []

def _resolve_weapon_anim_path(context, anim_path):
    rel = anim_path.replace('\\', '/').lstrip('/')
    for mod_dir in get_mod_dirs(context):
        candidate = os.path.normpath(os.path.join(mod_dir, *rel.split('/')))
        if os.path.isfile(candidate):
            return candidate

def _anim_path_is_3p(anim_filepath):
    return '3p' in anim_filepath.replace('\\', '/').lower().split('/')

def _on_weapon_anim_system_update(self, context):
    if not self.weapon_anim_system_file or not os.path.isfile(self.weapon_anim_system_file):
        return
    animations = _parse_animation_system(context, self.weapon_anim_system_file)
    if not animations:
        return
    anim_file = _resolve_weapon_anim_path(context, animations[0].path)
    if not anim_file:
        return
    if _anim_path_is_3p(anim_file):
        _set_default_3p_settings(self, context, anim_file)
    else:
        _set_default_1p_settings(self, context)
    _set_weapon_mesh(self, anim_file)

def _set_cutoff_bone(rig, action, bone_id):
    bones = list(rig.get('bf2_bones') or []) if rig else []
    if bone_id < 0 or bone_id >= len(bones):
        return False
    action.bf2_ignore_mother_orientation = bones[bone_id]
    return True

def _set_default_1p_settings(self, context):
    _set_default_soldier_1p_skeleton(self, context)

def _set_default_3p_settings(self, context, anim_filepath):
    _set_default_soldier_3p_skeleton(self, context)
    if self.import_method == 'SINGLE':
        soldier_anim_dir = _get_default_soldier_3p_anim_dir(self, context)
        if not anim_filepath or not soldier_anim_dir:
            return
        if soldier_anim := _find_matching_soldier_animation(soldier_anim_dir, anim_filepath):
            self.soldier_anim_file = soldier_anim
    else:
        self.soldier_anim_dir = _get_default_soldier_3p_anim_dir(self, context)

def _get_default_soldier_3p_anim_dir(self, context):
    for mod_dir in get_mod_dirs(context):
        dir = os.path.join(mod_dir, 'objects', 'soldiers', 'common', 'animations', '3p')
        if os.path.isdir(dir):
            return dir
    return ''

def _get_default_soldier_skeleton(context, fname):
    for mod_dir in get_mod_dirs(context):
        file = os.path.join(mod_dir, 'objects', 'soldiers', 'common', 'animations', fname)
        if os.path.isfile(file):
            return file

def _set_default_soldier_1p_skeleton(self, context):
    self.ske_file = _get_default_soldier_skeleton(context, '1p_setup.ske')

def _set_default_soldier_3p_skeleton(self, context):
    self.ske_file = _get_default_soldier_skeleton(context, '3p_setup.ske')

def _set_weapon_mesh(self, anim_filepath):
    if not anim_filepath:
        return
    anim_dirname = os.path.dirname(anim_filepath)
    anim_fname = os.path.basename(anim_filepath)
    s = anim_fname.split('_')
    if len(s) < 3:
        return

    def _matcher(f):
        weapon_name = ''
        for name_part in s[1:]:
            if weapon_name:
                weapon_name += '_'
            weapon_name += name_part
            if f'{weapon_name}.bundledmesh' == f:
                return True
        return False

    meshes_dir = os.path.join(anim_dirname, '..', '..', 'Meshes')
    meshes_dir = os.path.normpath(meshes_dir)
    if mesh_file := _find_file(meshes_dir, _matcher):
        self.weapon_mesh_file = mesh_file
    else:
        # didn't match animation file exactly, take any .bundledmesh
        for f in os.listdir(meshes_dir):
            fullpath = os.path.join(meshes_dir, f)
            if fullpath.lower().endswith('.bundledmesh') and os.path.isfile(fullpath):
                self.weapon_mesh_file = fullpath
                return

def _find_meshes_dir_recursive(self, dir):
    if not os.path.isdir(dir):
        return
    for f in os.listdir(dir):
        fullpath = os.path.join(dir, f)
        if os.path.isdir(fullpath):
            if f.lower() == 'meshes':
                return fullpath
            else:
                return _find_meshes_dir_recursive(self, fullpath)

def _set_default_soldier_mesh(self, context):
    for mod_dir in get_mod_dirs(context):
        soldiers_dir = os.path.join(mod_dir, 'objects', 'soldiers')
        meshes_dir = _find_meshes_dir_recursive(self, soldiers_dir)
        if not meshes_dir:
            continue
        if mesh_file := _find_file(meshes_dir, lambda f: f.endswith('.skinnedmesh')):
            self.soldier_mesh_file = mesh_file
            return
    self.soldier_mesh_file = ''

_animation_wizard = None

_ANIM_FILE_SELECT_TARGETS = {
    'WEAPON_ANIM': 'weapon_anim_file',
    'SOLDIER_ANIM': 'soldier_anim_file',
    'ANIM_SYSTEM': 'weapon_anim_system_file',
}

class VIEW3D_OT_bf2_anim_file_select(bpy.types.Operator, ImportHelper):
    bl_idname = "bf2.anim_file_select"
    bl_label = "Select BF2 Animation File"
    bl_description = "Select a BF2 animation (.baf) or animation system (.inc) file"
    filename_ext = ".baf"

    target: EnumProperty(
        name="Target",
        items=[
            ('WEAPON_ANIM', "Weapon animation", "Weapon animation file (.baf)"),
            ('SOLDIER_ANIM', "Soldier animation", "Soldier animation file (.baf)"),
            ('ANIM_SYSTEM', "Animation system", "Animation system definition (.inc)"),
        ],
        default='WEAPON_ANIM'
    ) # type: ignore

    filter_glob: StringProperty(default="*.baf", options={'HIDDEN'}) # type: ignore

    def invoke(self, context, event):
        if self.target == 'ANIM_SYSTEM':
            self.filter_glob = "*.inc"
            self.filename_ext = ".inc"
        else:
            self.filter_glob = "*.baf"
            self.filename_ext = ".baf"
        return super().invoke(context, event)

    def execute(self, context):
        if _animation_wizard is not None:
            prop = _ANIM_FILE_SELECT_TARGETS.get(self.target)
            if prop:
                setattr(_animation_wizard, prop, self.filepath)
        return {'FINISHED'}

def _draw_anim_file_row(layout, self, prop, target):
    row = layout.row(align=True)
    row.prop(self, prop)
    op = row.operator(VIEW3D_OT_bf2_anim_file_select.bl_idname, text='', icon='FILEBROWSER')
    op.target = target

class VIEW3D_OT_bf2_animation_wizard(bpy.types.Operator):
    bl_idname = "bf2.anim_wizard"
    bl_label = "Import wizard"
    bl_description = "Automated scene setup for animation editing - import skeleton, soldier/weapon meshes and animations all in one go!"

    def _on_weapon_anim_update(self, context):
        if self.import_method == 'SINGLE':
            if not self.weapon_anim_file or not os.path.isfile(self.weapon_anim_file):
                return
            anim_file = os.path.basename(self.weapon_anim_file)
            s = anim_file.split('_')
            if len(s) < 3:
                return
            if s[0] == '1p':
                _set_default_1p_settings(self, context)
            elif s[0] == '3p':
                _set_default_3p_settings(self, context, self.weapon_anim_file)
            else:
                return
            _set_weapon_mesh(self, self.weapon_anim_file)
        elif self.import_method == 'DIRECTORY':
            if not self.weapon_anim_dir or not os.path.isdir(self.weapon_anim_dir):
                return
            anim_dir = os.path.basename(self.weapon_anim_dir.replace('\\', '/').rstrip('/')).lower()
            anim_file = _find_file(self.weapon_anim_dir, lambda f: f.endswith('.baf') and len(f.split('_')) >= 3)
            if anim_dir == '1p':
                _set_default_1p_settings(self, context)
            elif anim_dir == '3p':
                _set_default_3p_settings(self, context, anim_file)
            else:
                return
            _set_weapon_mesh(self, anim_file)
        else:
            _on_weapon_anim_system_update(self, context)

    import_method: EnumProperty(
        name="Import method",
        description="How the weapon animations are selected",
        items=[
            ('SINGLE', "Single animation", "Import a single animation file"),
            ('DIRECTORY', "Animation directory", "Import every animation from a directory"),
            ('SYSTEM', "Animation system", "Parse a BF2 AnimationSystem .inc file and import every animation it defines"),
        ],
        default='SINGLE',
        update=_on_weapon_anim_update
    ) # type: ignore

    ske_file: StringProperty (
            name="Skeleton file",
            subtype="FILE_PATH"
        ) # type: ignore

    soldier_mesh_file: StringProperty (
            name="Soldier mesh file",
            subtype="FILE_PATH"
        ) # type: ignore

    soldier_anim_file: StringProperty (
            name="Soldier animation file (3P)"
        ) # type: ignore

    soldier_anim_dir: StringProperty (
            name="Soldier animation directory (3P)",
            subtype="DIR_PATH"
        ) # type: ignore

    weapon_mesh_file: StringProperty (
            name="Weapon mesh file",
            subtype="FILE_PATH"
        ) # type: ignore

    weapon_lod_index: IntProperty(
        name="Weapon LOD index",
        description="Which weapon LOD should be imported",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    weapon_anim_file: StringProperty (
            name="Weapon animation file",
            update=_on_weapon_anim_update
        ) # type: ignore

    weapon_anim_dir: StringProperty (
            name="Weapon animation directory",
            subtype="DIR_PATH",
            update=_on_weapon_anim_update
        ) # type: ignore

    weapon_anim_system_file: StringProperty (
            name="Animation system file (.inc)",
            update=_on_weapon_anim_update
        ) # type: ignore

    def execute(self, context):
        try:
            if not self.ske_file or not os.path.isfile(self.ske_file):
                self.report({"ERROR"}, "Skeleton file not provided or does not exist")
                return {'CANCELLED'}

            ske_name = os.path.basename(self.ske_file)
            if ske_name not in ('1p_setup.ske', '3p_setup.ske'):
                self.report({"ERROR"}, "Unknown skeleton file")
                return {'CANCELLED'}
            
            is_3p = ske_name == '3p_setup.ske'

            if not self.soldier_mesh_file or not os.path.isfile(self.soldier_mesh_file):
                self.report({"ERROR"}, "Soldier mesh file not provided or does not exist")
                return {'CANCELLED'}

            if not self.weapon_mesh_file or not os.path.isfile(self.weapon_mesh_file):
                self.report({"ERROR"}, "Weapon mesh file not provided or does not exist")
                return {'CANCELLED'}
 
            if self.import_method == 'SINGLE':
                if not self.weapon_anim_file or not os.path.isfile(self.weapon_anim_file):
                    self.report({"ERROR"}, "Weapon animation file not provided or does not exist")
                    return {'CANCELLED'}
            elif self.import_method == 'DIRECTORY':
                if not self.weapon_anim_dir or not os.path.isdir(self.weapon_anim_dir):
                    self.report({"ERROR"}, "Weapon animation directory not provided or does not exist")
                    return {'CANCELLED'}
            else:
                if not self.weapon_anim_system_file or not os.path.isfile(self.weapon_anim_system_file):
                    self.report({"ERROR"}, "Animation system file (.inc) not provided or does not exist")
                    return {'CANCELLED'}

            if is_3p:
                if self.import_method == 'SINGLE':
                    if not self.soldier_anim_file or not os.path.isfile(self.soldier_anim_file):
                        self.report({"WARNING"}, "Soldier animation file (3P) not provided or does not exist")
                else:
                    if not self.soldier_anim_dir or not os.path.isdir(self.soldier_anim_dir):
                        self.report({"WARNING"}, "Soldier animation directory (3P) not provided or does not exist")
            else:
                self.soldier_anim_file = ''
                self.soldier_anim_dir = ''

            # ------------
            weapon_to_soldier_binding = list()
            bpy.ops.bf2.ske_import(filepath=self.ske_file)
            rig = bpy.context.object
            bpy.ops.bf2.mesh_import(filepath=self.soldier_mesh_file, only_selected_lod=True, geom=1 if is_3p else 0, lod=self.weapon_lod_index)
            bpy.ops.bf2.mesh_import(filepath=self.weapon_mesh_file, only_selected_lod=True, geom=1 if is_3p else 0, lod=self.weapon_lod_index)
            if self.import_method == 'SINGLE':
                bpy.ops.bf2.baf_import(filepath=self.weapon_anim_file, to_new_action=True)
                weapon_action = bpy.context.object.animation_data.action
                if self.soldier_anim_file:
                    bpy.ops.bf2.baf_import(filepath=self.soldier_anim_file, to_new_action=True)
                    soldier_action = bpy.context.object.animation_data.action
                    weapon_to_soldier_binding.append((weapon_action, soldier_action))
            elif self.import_method == 'DIRECTORY':
                for f in os.listdir(self.weapon_anim_dir):
                    path = os.path.join(self.weapon_anim_dir, f)
                    if f.endswith('.baf') and os.path.isfile(path):
                        bpy.ops.bf2.baf_import(filepath=path, to_new_action=True)
                        weapon_action = bpy.context.object.animation_data.action
                    if self.soldier_anim_dir:
                        soldier_anim = _find_matching_soldier_animation(self.soldier_anim_dir, path)
                        if not soldier_anim:
                            self.report({"WARNING"}, f"Couldn't find a matching soldier animation for '{f}'. Try importing and linking them manually")
                            continue
                        bpy.ops.bf2.baf_import(filepath=soldier_anim, to_new_action=True)
                        soldier_action = bpy.context.object.animation_data.action
                        weapon_to_soldier_binding.append((weapon_action, soldier_action))
            else:
                animations = _parse_animation_system(context, self.weapon_anim_system_file)
                if not animations:
                    self.report({"ERROR"}, "No animations found in the animation system file")
                    return {'CANCELLED'}
                for anim in animations:
                    path = _resolve_weapon_anim_path(context, anim.path)
                    if not path or not os.path.isfile(path):
                        self.report({"WARNING"}, f"Animation file '{anim.path}' not found, skipping")
                        continue
                    bpy.ops.bf2.baf_import(filepath=path, to_new_action=True)
                    weapon_action = bpy.context.object.animation_data.action
                    if anim.ignore_mother_orientation is not None:
                        if not _set_cutoff_bone(rig, weapon_action, anim.ignore_mother_orientation):
                            self.report({"WARNING"}, f"Couldn't map ignoreMotherOrientation {anim.ignore_mother_orientation} to a bone for '{anim.path}'")
                    if self.soldier_anim_dir:
                        soldier_anim = _find_matching_soldier_animation(self.soldier_anim_dir, path)
                        if not soldier_anim:
                            self.report({"WARNING"}, f"Couldn't find a matching soldier animation for '{os.path.basename(path)}'. Try importing and linking them manually")
                            continue
                        bpy.ops.bf2.baf_import(filepath=soldier_anim, to_new_action=True)
                        soldier_action = bpy.context.object.animation_data.action
                        weapon_to_soldier_binding.append((weapon_action, soldier_action))

            for weapon_action, soldier_action in weapon_to_soldier_binding:
                weapon_action.bf2_soldier_action = soldier_action

            # the soldier action is a single shared NLA track that has to match
            # whichever action is active, so leave the wizard on a weapon action
            # and rebuild the track for it (otherwise it points at an arbitrary one)
            if weapon_to_soldier_binding and rig.animation_data:
                default_action = weapon_to_soldier_binding[0][0]
                context.view_layer.objects.active = rig
                rig.animation_data.action = default_action
                update_nla_setup(context, default_action)

        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

    def draw(self, context):
        global _animation_wizard
        _animation_wizard = self
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'import_method')
        if self.import_method == 'SINGLE':
            _draw_anim_file_row(layout, self, 'weapon_anim_file', 'WEAPON_ANIM')
        elif self.import_method == 'DIRECTORY':
            layout.prop(self, 'weapon_anim_dir')
        else:
            _draw_anim_file_row(layout, self, 'weapon_anim_system_file', 'ANIM_SYSTEM')

        layout.prop(self, 'weapon_mesh_file')
        layout.prop(self, 'weapon_lod_index')
        layout.prop(self, 'ske_file')
        col = layout.column()
        if self.import_method == 'SINGLE':
            _draw_anim_file_row(col, self, 'soldier_anim_file', 'SOLDIER_ANIM')
        else:
            col.prop(self, 'soldier_anim_dir')
        col.enabled = self.ske_file is None or os.path.basename(self.ske_file) != '1p_setup.ske'
        layout.prop(self, 'soldier_mesh_file')

    def invoke(self, context, event):
        _set_default_soldier_mesh(self, context)
        return context.window_manager.invoke_props_dialog(self, width=600)

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("A mod directory must be defined for this feature")
        return bool(get_mod_dirs(context))

class VIEW3D_OT_bf2_anim_change_parent(bpy.types.Operator):
    bl_idname = "bf2.anim_set_parent"
    bl_label = "Set Parent"
    bl_description = "Parents all selected bones to the active bone while also adjusting all position/rotation keyframes"

    @classmethod
    def poll(cls, context):
        parent = context.active_pose_bone
        if not parent or parent not in context.selected_pose_bones_from_active_object:
            cls.poll_message_set("No active bone")
            return False
        selected = list(filter(lambda b: b.name != parent.name, context.selected_pose_bones_from_active_object))
        if not selected:
            cls.poll_message_set("No bones selected (need at least two, the active one will be the parent)")
            return False
        return True

    def execute(self, context):
        rig = context.view_layer.objects.active
        parent_bone = context.active_pose_bone.name
        bones = list(filter(lambda b: b != parent_bone, map(lambda b: b.name, context.selected_pose_bones_from_active_object)))
        reparent_bones(context, rig, bones, parent_bone, reporter=Reporter(self.report))
        return {'FINISHED'}

class VIEW3D_OT_bf2_anim_clear_parent(bpy.types.Operator):
    bl_idname = "bf2.anim_clear_parent"
    bl_label = "Clear Parent"
    bl_description = "Clears parent of all selected bones while also adjusting all position/rotation keyframes"

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No bones selected")
        return context.selected_pose_bones_from_active_object

    def execute(self, context):
        rig = context.view_layer.objects.active
        bones = list(map(lambda b: b.name, context.selected_pose_bones_from_active_object))
        reparent_bones(context, rig, bones, None, reporter=Reporter(self.report))
        return {'FINISHED'}

class VIEW3D_PT_bf2_animation_Panel(bpy.types.Panel):
    bl_category = "BF2"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Animation"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.operator(VIEW3D_OT_bf2_animation_wizard.bl_idname, icon='SHADERFX', text='Run Import Wizard')
        layout.separator(factor=1.0, type='SPACE')
        box = layout.box()
        box.label(text="Auto controller setup:")
        row = box.row()
        row.operator(VIEW3D_OT_bf2_anim_ctrl_setup_begin.bl_idname, icon='ARMATURE_DATA', text='Run Setup')
        row.operator(VIEW3D_OT_bf2_anim_ctrl_setup_end.bl_idname, icon='CHECKMARK', text='Apply')
        box.operator(VIEW3D_OT_bf2_anim_ctrl_setup_mask.bl_idname, icon='BONE_DATA')
        layout.separator(factor=1.0, type='SPACE')
        box = layout.box()
        box.label(text="Bone relations:")
        row = box.row()
        row.operator(VIEW3D_OT_bf2_anim_change_parent.bl_idname, icon='CON_CHILDOF')
        row.operator(VIEW3D_OT_bf2_anim_clear_parent.bl_idname, icon='MATPLANE')

def init(rc : RegisterFactory):
    # animation
    rc.reg_class(VIEW3D_OT_bf2_anim_ctrl_setup_begin)
    rc.reg_class(VIEW3D_OT_bf2_anim_ctrl_setup_end)
    rc.reg_class(VIEW3D_OT_bf2_anim_ctrl_setup_mask)
    rc.reg_class(VIEW3D_OT_bf2_anim_change_parent)
    rc.reg_class(VIEW3D_OT_bf2_anim_clear_parent)
    rc.reg_class(VIEW3D_OT_bf2_anim_file_select)
    rc.reg_class(VIEW3D_OT_bf2_animation_wizard)
    rc.reg_class(VIEW3D_PT_bf2_animation_Panel)

register, unregister = RegisterFactory.create(init)
