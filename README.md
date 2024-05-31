# Blender addon for Battlefield 2
I'm probably like 15 years late but anyway, here are some tools for importing and exporting Refractor 2 engine asset files for Blender!

## Features:
- Skeleton (`.ske`) import/export
- Animation (`.baf`) import/export
- StaticMesh (`.staticMesh`) import/export
- SkinnedMesh (`.skinnedMesh`) import/export
- BundledMesh (`.bundledMesh`) import/export
- CollisionMesh (`.collisionMesh`) import/export

## Compatibility
Blender 4.1 only, pre-build binaries available for Windows, Linux and macOS (Intel). For other platforms see building instructions at [BSP Builder](bsp_builder/README.md).

## Installation
Download the latest package from [Releases](https://github.com/marekzajac97/bf2-blender/releases/latest) and follow the steps at [Installing Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-add-ons)

NOTE: Removing the add-on through Blender **will not work properly**, you have to delete the add-on's directory (by default located in `%APPDATA%\Blender Foundation\Blender\4.1\scripts\addons`) manually when Blender is closed.

## Usage
- Head over to the [Documentation](docs/README.md) for details on how to use this add-on

## Limitations and known issues:
- Generating `.samples` for StaticMeshes is not yet supported, use [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/)!
- SkinnedMeshes using Object Space normal maps will have shading issues when deformed/animated inside of Blender.
- Blender does not allow to import custom tangent data, therefore when re-exporting meshes, vertex tangents always get re-calculated. This may increase the number of unique vertices being exported. Generated tangents may also be totally wrong if the normal map used was not generated using Mikk TSpace method (which Blender uses).
- CollisionMesh exports to a slightly older file version (9) than 3DsMax exporter (10). Latest file version contains some extra data for drawing debug meshes which is disabled by default in-game anyway.

Please report any other issues found!

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
- Ason and DeWolfe for testing and feedback
