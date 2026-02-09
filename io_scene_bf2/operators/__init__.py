from . import ops_import_export
from . import ops_view_3d
from . import ops_material_props
from . import ops_object_props
from . import ops_prefs

def register():
    ops_object_props.register()
    ops_material_props.register()
    ops_import_export.register()
    ops_view_3d.register()
    ops_prefs.register()

def unregister():
    ops_prefs.unregister()
    ops_view_3d.unregister()
    ops_import_export.unregister()
    ops_material_props.unregister()
    ops_object_props.unregister()
