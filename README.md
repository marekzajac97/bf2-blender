# Blender addon for Battlefield 2
Probably like 15 years too late but anyway, here are some basic tools for importing/exporting Refractor 2 engine files. For now only usable for animating.

## Features:
- Animation (`.baf`) import/export
- Skeleton (`.ske`) import only
- BundledMesh/SkinnedMesh (`.bundledmesh, .skinnedmesh`) import geometry only (with skin weights)

## Usage
After installation, use `BF2` submenu in `File -> Import/Export`

#### Notes:
- Skeleton needs to be loaded first! followed by the soldier/weapon/kitmesh/animation(s) (in any order)
- Make sure to set geom 1 in mesh import options for 3P animations

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
