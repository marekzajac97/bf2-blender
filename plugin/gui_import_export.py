import bpy

from .import_export import gui_animation
from .import_export import gui_skeleton
from .import_export import gui_mesh
from .import_export import gui_collisionmesh
from .import_export import gui_game_object

class IMPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "IMPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        gui_animation.draw_import(self.layout)
        gui_skeleton.draw_import(self.layout)
        gui_mesh.draw_import(self.layout)
        gui_collisionmesh.draw_import(self.layout)
        gui_game_object.draw_import(self.layout)


def menu_func_import(self, context):
    self.layout.menu(IMPORT_MT_bf2_submenu.bl_idname, text="BF2")

class EXPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EXPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        gui_animation.draw_export(self.layout)
        gui_skeleton.draw_export(self.layout)
        gui_mesh.draw_export(self.layout)
        gui_collisionmesh.draw_export(self.layout)
        gui_game_object.draw_export(self.layout)

def menu_func_export(self, context):
    self.layout.menu(EXPORT_MT_bf2_submenu.bl_idname, text="BF2")


# ----------------------------------------------------------

def register():
    gui_animation.register()
    gui_skeleton.register()
    gui_mesh.register()
    gui_collisionmesh.register()
    gui_game_object.register()

    bpy.utils.register_class(IMPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    bpy.utils.register_class(EXPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_MT_bf2_submenu)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_MT_bf2_submenu)

    gui_game_object.unregister()
    gui_collisionmesh.unregister()
    gui_mesh.unregister()
    gui_skeleton.unregister()
    gui_animation.unregister()
