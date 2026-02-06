# Blender addon for Battlefield 2
I'm probably like 15 years late but anyway, here are some Blender tools for working with Refractor 2 engine assets!

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
- minimum required: Blender 4.2
- maximum supported: Blender 5.0 (later versions may still work but as of writing this, they have not been tested)

## Installation
Download the latest `io_scene_bf2` package from [Releases](https://github.com/marekzajac97/bf2-blender/releases/latest) compatible with your system and follow the steps at [Installing Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-legacy-add-ons)

## Usage
- Head over to the [Documentation](docs/README.md) for details on how to use this add-on

## License
This repository includes the source code  of the following third-party projects:
- [rectpack](https://github.com/secnot/rectpack) licensed under Apache License Version 2.0
- [Texconv Custom DLL](https://github.com/matyalatte/Texconv-Custom-DLL) including python bindings from [Blender-DDS-Addon](https://github.com/matyalatte/Blender-DDS-Addon) licensed under MIT License
- [bf2mesh](https://github.com/rpoxo/bf2mesh) licensed under MIT License
- [pybind11](https://github.com/pybind/pybind11) licensed under BSD-style license.

Unless stated otherwise, all of the remaining source files in this repository are licensed under MIT License.

## Credits
- [secnot](https://github.com/secnot), [matyalatte](https://github.com/matyalatte) and [rpoxo](https://github.com/rpoxo) as the respective owners of the repositories listed above
- Harmonikater for [BF2-3dsMax-Tools](https://git.cmp-gaming.com/Harmonikater/BF2-3dsMax-Tools) (served as "inspiration" for some of the tools)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
- Ason and DeWolfe for testing and feedback
