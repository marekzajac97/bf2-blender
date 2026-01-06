import bpy # type: ignore
from bpy.props import StringProperty, CollectionProperty, IntProperty # type: ignore

from . import ops_import_export
from . import ops_view_3d
from . import ops_material_props
from . import ops_object_props

from .. import __package__

class BF2_OT_bf2_mod_path_add(bpy.types.Operator):
    bl_idname = "bf2.mod_path_add"
    bl_label = "Add BF2 mod directory slot"
    bl_description = "Adds a slot for a directory path containing unpacked mod contents, it will be used as the texture search path"

    def execute(self, context):
        context.preferences.addons[__package__].preferences.mod_directories.add()
        return {'FINISHED'}

class BF2_OT_bf2_mod_path_remove(bpy.types.Operator):
    bl_idname = "bf2.mod_path_remove"
    bl_label = "Remove BF2 mod directory slot"
    bl_description = "Removes this mod directory path"

    path_index: IntProperty() # type: ignore

    def execute(self, context):
        context.preferences.addons[__package__].preferences.mod_directories.remove(self.path_index)
        return {'FINISHED'}

class ModPathCollection(bpy.types.PropertyGroup):
    mod_directory: StringProperty (
            name="BF2 mod directory",
            subtype="DIR_PATH"
        ) # type: ignore

class BF2AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mod_directories: CollectionProperty(type=ModPathCollection) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="BF2 mod directories")
        for i, prop in enumerate(self.mod_directories):
            row = layout.row()
            row.prop(prop, 'mod_directory', text='', expand=True)
            op = row.operator(BF2_OT_bf2_mod_path_remove.bl_idname, text='', icon='REMOVE')
            op.path_index = i

        row = layout.row()
        row.operator(BF2_OT_bf2_mod_path_add.bl_idname, icon='ADD')

# ----------------------------------------------------------

def register():
    ops_object_props.register()
    ops_material_props.register()
    ops_import_export.register()
    ops_view_3d.register()
    bpy.utils.register_class(ModPathCollection)
    bpy.utils.register_class(BF2AddonPreferences)
    bpy.utils.register_class(BF2_OT_bf2_mod_path_remove)
    bpy.utils.register_class(BF2_OT_bf2_mod_path_add)

    # debug_set_mod_path()

def unregister():
    bpy.utils.unregister_class(BF2_OT_bf2_mod_path_add)
    bpy.utils.unregister_class(BF2_OT_bf2_mod_path_remove)
    bpy.utils.unregister_class(BF2AddonPreferences)
    bpy.utils.unregister_class(ModPathCollection)
    ops_view_3d.unregister()
    ops_import_export.unregister()
    ops_material_props.unregister()
    ops_object_props.unregister()

import sys


def is_debug_enabled():
    try:
        if sys.gettrace() is not None:
            return True
    except AttributeError:
        pass
    try:
        if sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None:
            return True
    except AttributeError:
        pass
    return False

# in debug mode only, having to set this up everytime add-on is reloaded is annoying af
def debug_set_mod_path():
    if not is_debug_enabled():
        return
    prefs = bpy.context.preferences.addons[__package__].preferences
    if len(prefs.mod_directories) != 0:
        return
    import os
    BF2_PATHS = [r'D:\Battlefield 2\mods\fh2', r'D:\Battlefield 2\mods\bf2']
    for path in BF2_PATHS:
        if not os.path.isdir(path):
            continue
        item = prefs.mod_directories.add()
        item.mod_directory = path
        print(f"DEBUG: Auto-configured BF2 path {path}")
