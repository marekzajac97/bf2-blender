from .view_3d import ops_view_3d_bf2
from .view_3d import ops_view_3d_edit_mesh
from .view_3d import ops_view_3d_object
from .view_3d import ops_view_3d_pose

def register():
    ops_view_3d_bf2.register()
    ops_view_3d_edit_mesh.register()
    ops_view_3d_object.register()
    ops_view_3d_pose.register()

def unregister():
    ops_view_3d_pose.unregister()
    ops_view_3d_object.unregister()
    ops_view_3d_edit_mesh.unregister()
    ops_view_3d_bf2.unregister()
