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
- The imported skeleton (armature) can be freely extended e.g. by adding helper bones for animating, but DO NOT modify imported skeleton bones! You should never change their position, rotation or relations in edit mode. If you wish to do any of that, create additional helper bones and setup a `Child Of` constraint on the original bones (with those helper bones set as target) instead. See my [example 1P rig (for Blender 3.4)](https://www.mediafire.com/file/qh2km0hsfy2q7s0/bf2_blender_1p_rig.zip/file) for reference.
- You can optionally tick `Setup controllers` during animation import to automatically create basic controllers and IK setup (only works for 1P as of now)
- Make sure to set geom 1 in mesh import options if you wish to import 3P animations.
- When exporting, you can select/deselect bones for export in the export menu.

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
