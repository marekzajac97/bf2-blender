from . import ops_view_3d_bf2
from . import ops_view_3d_edit_mesh
from . import ops_view_3d_object
from . import ops_view_3d_pose

from ..utils import RegisterFactory

def init(rc : RegisterFactory):
    rc.reg_module(ops_view_3d_bf2)
    rc.reg_module(ops_view_3d_edit_mesh)
    rc.reg_module(ops_view_3d_object)
    rc.reg_module(ops_view_3d_pose)

register, unregister = RegisterFactory.create(init)
