import bpy
from bpy.props import StringProperty

from . import gui_import_export
from . import gui_view_3d
from . import gui_material_props
from . import gui_object_props

from .. import PLUGIN_NAME

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
    gui_object_props.register()
    gui_material_props.register()
    gui_import_export.register()
    gui_view_3d.register()
    bpy.utils.register_class(BF2AddonPreferences)

def unregister():
    bpy.utils.unregister_class(BF2AddonPreferences)
    gui_view_3d.unregister()
    gui_import_export.unregister()
    gui_material_props.unregister()
    gui_object_props.unregister()

