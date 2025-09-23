# Blender addon for Battlefield 2
I'm probably like 15 years late but anyway, here are some tools for importing and exporting Refractor 2 engine asset files for Blender!

## Features:
- Skeleton (`.ske`) import/export
- Animation (`.baf`) import/export
- StaticMesh (`.staticMesh`) import/export (including lightmap samples)
- SkinnedMesh (`.skinnedMesh`) import/export
- BundledMesh (`.bundledMesh`) import/export
- CollisionMesh (`.collisionMesh`) import/export
- Occlusion Mesh (`.occ`) import/export

## Compatibility
- Blender 4.2 or later
- Windows x64, Linux x64 and macOS x64 (Intel). For ARM or other platforms see building instructions at [BSP Builder](bsp_builder/README.md).

## Installation
Download the latest `io_scene_bf2` package from [Releases](https://github.com/marekzajac97/bf2-blender/releases/latest) (NOT `Source code (zip)`!) and follow the steps at [Installing Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-legacy-add-ons)

## Usage
- Head over to the [Documentation](docs/README.md) for details on how to use this add-on

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
- Ason and DeWolfe for testing and feedback
