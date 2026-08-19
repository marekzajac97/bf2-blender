
from . import ops_import_export
from . import ops_view_3d
from . import ops_dopesheet
from . import ops_material_props
from . import ops_object_props
from . import ops_prefs

from .utils import RegisterFactory
from ..directx.texconv import unload_texconv

def init(rc : RegisterFactory):
    rc.reg_module(ops_object_props)
    rc.reg_module(ops_material_props)
    rc.reg_module(ops_import_export)
    rc.reg_module(ops_view_3d)
    rc.reg_module(ops_dopesheet)
    rc.reg_module(ops_prefs)
    rc.reg_fun(
        on_register=None,
        on_unregister=_try_unload_texconv
    )

def _try_unload_texconv():
    try:
        unload_texconv()
    except Exception as e:
        print(e)

register, unregister = RegisterFactory.create(init)
