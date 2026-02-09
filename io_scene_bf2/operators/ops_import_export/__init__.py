from ..utils import RegisterFactory

from . import ops_animation
from . import ops_skeleton
from . import ops_mesh
from . import ops_collisionmesh
from . import ops_object_template
from . import ops_occluders
from . import ops_common

def init(rc : RegisterFactory):
    rc.reg_module(ops_animation)
    rc.reg_module(ops_skeleton)
    rc.reg_module(ops_mesh)
    rc.reg_module(ops_collisionmesh)
    rc.reg_module(ops_object_template)
    rc.reg_module(ops_occluders)
    rc.reg_module(ops_common)

register, unregister = RegisterFactory.create(init)
