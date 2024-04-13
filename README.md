# Blender addon for Battlefield 2

I'm probably like 15 years late but anyway, here are some tools for importing/exporting Refractor 2 engine files for Blender as an alternative to 3ds Max tools. Development is still in its early stages, see below what is supported. Please report any issues found!

## Features:
- Animation (`.baf`) import/export
- Skeleton (`.ske`) import only
- StaticMesh (`.staticMesh`) import/export
- SkinnedMesh (`.skinnedMesh`) import only
- BundledMesh (`.bundledMesh`) import/export
- CollisionMesh (`.collisionMesh`) import/export

## Limitations and known issues:
- CollisionMesh exports to a slightly older file version (9) than 3DsMax exporter (10), which will make BF2 regenerate some missing data on load time, not a big deal.
- Generating `.samples` for StaticMeshes is not yet supported, use [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/)!
- SkinnedMeshes using Object Space normal maps will have shading issues when deformed

## Installation
- Head over to [Releases](https://github.com/marekzajac97/bf2-blender/releases/) for download
- To install see [Blender Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html)

NOTE: Removing the add-on through Blender **will not work properly**, you have to delete the add-on's directory manually when Blender is closed.

## Usage
- Head over to the [documentation](https://github.com/marekzajac97/bf2-blender/blob/main/docs/README.md) for details on how to use this add-on

## Compatibility
- The Add-on is compatible with Blender 4.0 only. It is fully cross-platform, however the pure-python implementation of the collision mesh export is painfully slow, thus this part of export will require a module `bsp_builder` compiled into a `.pyd` or `.so` file. For now, the pre-build binary is only available for Windows (x64), for macOS/Linux you will have to build that yourself!

### Building prerequisites
- A compiler with C++11 support
- CMake >= 3.4 (or 3.14+ on Windows)

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
- Ason and DeWolfe for testing and feedback
