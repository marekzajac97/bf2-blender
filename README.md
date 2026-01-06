# Blender addon for Battlefield 2
I'm probably like 15 years late but anyway, here are some Blender tools for working with Refractor 2 engine asset files and more!

## Features:
Import & export support of:
- Skeleton (`.ske`)
- Animation (`.baf`)
- StaticMesh (`.staticMesh`) including lightmap samples
- SkinnedMesh (`.skinnedMesh`)
- BundledMesh (`.bundledMesh`)
- CollisionMesh (`.collisionMesh`)
- Occlusion Mesh (`.occ`)

As well as many other utilities for:
- Lightmapping
- Skeleton rigging
- Making overgrowth LODs
- BundledMesh skinning

## Compatibility
- Blender 4.2 or later required.
- Supports all platforms with the following exceptions:
  * ARM (Any platform) - CollostionMesh export is significantly slower (see [BSP Builder](bsp_builder/README.md)).
  * Windows ARM - DDS export not supported (ligtmapping/OG lod generations)

## Installation
Download the latest `io_scene_bf2` package from [Releases](https://github.com/marekzajac97/bf2-blender/releases/latest) (NOT `Source code (zip)`!) and follow the steps at [Installing Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-legacy-add-ons)

## Usage
- Head over to the [Documentation](docs/README.md) for details on how to use this add-on

## Credits
- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- [matyalatte](https://github.com/rpoxo) for the [Texconv Custom DLL](https://github.com/matyalatte/Texconv-Custom-DLL) with [Python bindings](https://github.com/matyalatte/Blender-DDS-Addon) (MIT License)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
- Ason and DeWolfe for testing and feedback
