import bpy # type: ignore
from bpy.props import StringProperty # type: ignore

from . import ops_import_export
from . import ops_view_3d
from . import ops_material_props
from . import ops_object_props

from .. import __package__

class BF2AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mod_directory: StringProperty (
            name="BF2 mod directory",
            subtype="DIR_PATH"
        ) # type: ignore

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'mod_directory', expand=True)

# ----------------------------------------------------------

def register():
    ops_object_props.register()
    ops_material_props.register()
    ops_import_export.register()
    ops_view_3d.register()
    bpy.utils.register_class(BF2AddonPreferences)

def unregister():
    bpy.utils.unregister_class(BF2AddonPreferences)
    ops_view_3d.unregister()
    ops_import_export.unregister()
    ops_material_props.unregister()
    ops_object_props.unregister()

