from .core.mesh import (import_mesh, import_bundledmesh, export_bundledmesh,
                        import_staticmesh, export_staticmesh,
                        import_skinnedmesh, export_skinnedmesh)
from .core.animation import import_animation, export_animation
from .core.collision_mesh import import_collisionmesh, export_collisionmesh
from .core.skeleton import import_skeleton, export_skeleton
from .core.object_template import import_object_template, export_object_template
from .core.occluders import import_occluders, export_occluders
from .core.anim_utils import reparent_bones, setup_controllers as setup_anim_controllers
from .core.lightmaps import load_level, tweak_materials, ObjectBaker, TerrainBaker

def get_mod_dirs(context):
    return [prop.mod_directory for prop in context.preferences.addons[__package__].preferences.mod_directories if prop.mod_directory]

from .operators import ops_main

def register():
    ops_main.register()

def unregister():
    ops_main.unregister()

if __name__ == "__main__":
    register()
