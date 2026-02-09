from . import ops_import_export
from . import ops_view_3d
from . import ops_material_props
from . import ops_object_props
from . import ops_prefs

from .utils import RegisterFactory

def init(rc : RegisterFactory):
    rc.reg_module(ops_object_props)
    rc.reg_module(ops_material_props)
    rc.reg_module(ops_import_export)
    rc.reg_module(ops_view_3d)
    rc.reg_module(ops_prefs)

register, unregister = RegisterFactory.create(init)
