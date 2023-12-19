import bpy
from bpy.props import StringProperty

from . import animation
from . import animation_ctrl_setup
from . import skeleton
from . import mesh
from . import collisionmesh

from .. import PLUGIN_NAME

class IMPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "IMPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        animation.draw_import(self.layout)
        skeleton.draw_import(self.layout)
        mesh.draw_import(self.layout)
        collisionmesh.draw_import(self.layout)


def menu_func_import(self, context):
    self.layout.menu(IMPORT_MT_bf2_submenu.bl_idname, text="BF2")

class EXPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EXPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        animation.draw_export(self.layout)
        skeleton.draw_export(self.layout)
        mesh.draw_export(self.layout)
        collisionmesh.draw_export(self.layout)

def menu_func_export(self, context):
    self.layout.menu(EXPORT_MT_bf2_submenu.bl_idname, text="BF2")

# ----------------------------------------------------------

class BF2AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = PLUGIN_NAME

    mod_directory: StringProperty (
            name="BF2 mod directory",
            subtype="DIR_PATH"
        )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'mod_directory', expand=True)

# ----------------------------------------------------------

def register():
    animation.register()
    animation_ctrl_setup.register()
    skeleton.register()
    mesh.register()
    collisionmesh.register()

    bpy.utils.register_class(BF2AddonPreferences)

    bpy.utils.register_class(IMPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    bpy.utils.register_class(EXPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_MT_bf2_submenu)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_MT_bf2_submenu)

    bpy.utils.unregister_class(BF2AddonPreferences)

    collisionmesh.unregister()
    mesh.unregister()
    skeleton.unregister()
    animation_ctrl_setup.unregister()
    animation.unregister()
