# Blender addon for Battlefield 2
Probably like 15 years too late but anyway, here are some basic tools for importing/exporting Refractor 2 engine files. For now only usable for animating.

## Features:
- Animation (`.baf`) import/export
- Skeleton (`.ske`) import only
- BundledMesh/SkinnedMesh (`.bundledmesh, .skinnedmesh`) import only

## Installation
- To download use [Download ZIP](https://github.com/marekzajac97/bf2-blender/archive/refs/heads/main.zip) option
- To install see [Blender Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html)

## Usage
After installation, setup your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) (optional, it's only required to load textures). Then you can use `BF2` submenu in `File -> Import/Export`

#### Tips and general info:
- When importing, the skeleton needs to be loaded first! followed by the soldier/weapon/kitmesh and animation loaded at the very end.
- Each part of the imported BundledMesh (weapon mesh) will be automatically assigned to a vertex group from `mesh1` to `mesh16`.
- The imported skeleton (armature) can be freely extended e.g. by adding helper bones for animating, but DO NOT modify imported skeleton bones! You should never change their name, position, rotation or relations in `Edit mode`. If you wish to do any of that, create additional helper bones and setup a `Child Of` constraint on the original bones (with those helper bones set as target) instead. See my [example 1P rig (for Blender 3.4)](https://www.mediafire.com/file/qh2km0hsfy2q7s0/bf2_blender_1p_rig.zip/file) for reference.
- You can optionally tick `Setup controllers` during animation import to automatically create basic controllers and IK setup (only works for 1P as of now)
- Make sure to set geom 1 in mesh import options if you wish to import 3P animations.
- When exporting, you can select/deselect bones for export in the export menu.

#### All-in-one import script

Sample script you can use to automate the import

```python
import bpy
import sys
from os import path

MOD_PATH          = r'D:\Battlefield 2\mods\fh2_edit'
SKELETON          = path.join(MOD_PATH, r'objects\soldiers\Common\Animations\1p_setup.ske')
SOLDIER_MESH      = path.join(MOD_PATH, r'objects\soldiers\BA\Meshes\ba_light_soldier.skinnedmesh')
WEAPON_MESH       = path.join(MOD_PATH, r'objects\Weapons\Handheld\03a3\Meshes\03a3.bundledmesh')
WEAPON_ANIMATION  = path.join(MOD_PATH, r'objects\Weapons\Handheld\03a3\Animations\1p\1p_03a3_reload.baf')
SOLDIER_ANIMATION = path.join(MOD_PATH, r'objects\soldiers\Common\Animations\3P\3p_reload.baf') # for 3P only
SETUP_CONTROLLERS = True

is_1p = path.split(SKELETON)[1].startswith('1p')
geom = 0 if is_1p else 1
sm = sys.modules['bf2-blender'].scene_manipulator.SceneManipulator(bpy.context.scene)
sm.import_skeleton(SKELETON, reload=True)
sm.import_mesh(SOLDIER_MESH, geom=geom, lod=0, mod_path=MOD_PATH, reload=True)
sm.import_mesh(WEAPON_MESH, geom=geom, lod=0,  mod_path=MOD_PATH, reload=True)
sm.import_animation(WEAPON_ANIMATION)
if not is_1p and SOLDIER_ANIMATION:
    sm.import_animation(SOLDIER_ANIMATION)
if SETUP_CONTROLLERS:
    sm.setup_controllers()
```

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
