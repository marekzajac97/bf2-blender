import bpy # type: ignore

from . import ops_animation
from . import ops_skeleton
from . import ops_mesh
from . import ops_collisionmesh
from . import ops_object_template
from . import ops_occluders

class IMPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "IMPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        ops_animation.draw_import(self.layout)
        ops_skeleton.draw_import(self.layout)
        ops_mesh.draw_import(self.layout)
        ops_collisionmesh.draw_import(self.layout)
        ops_object_template.draw_import(self.layout)
        ops_occluders.draw_import(self.layout)

def menu_func_import(self, context):
    self.layout.menu(IMPORT_MT_bf2_submenu.bl_idname, text="BF2")

class EXPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EXPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    def draw(self, context):
        ops_animation.draw_export(self.layout)
        ops_skeleton.draw_export(self.layout)
        ops_mesh.draw_export(self.layout)
        ops_collisionmesh.draw_export(self.layout)
        ops_object_template.draw_export(self.layout)
        ops_occluders.draw_export(self.layout)

def menu_func_export(self, context):
    self.layout.menu(EXPORT_MT_bf2_submenu.bl_idname, text="BF2")


# ----------------------------------------------------------

def register():
    ops_animation.register()
    ops_skeleton.register()
    ops_mesh.register()
    ops_collisionmesh.register()
    ops_object_template.register()
    ops_occluders.register()

    bpy.utils.register_class(IMPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    bpy.utils.register_class(EXPORT_MT_bf2_submenu)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_MT_bf2_submenu)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_MT_bf2_submenu)

    ops_occluders.unregister()
    ops_object_template.unregister()
    ops_collisionmesh.unregister()
    ops_mesh.unregister()
    ops_skeleton.unregister()
    ops_animation.unregister()
