# Blender addon for Battlefield 2

Probably like 15 years too late but anyway, here are some basic tools for importing/exporting Refractor 2 engine files. Development is still in its early stages and currently the add-on is only usable for animating and static modelling. Please report any issues found!

## Features:

- Animation (`.baf`) import/export
- Skeleton (`.ske`) import only
- StaticMesh (`.staticMesh`) import/export [WIP]
- SkinnedMesh (`.skinnedMesh`) import only
- BundledMesh (`.bundledMesh`) import only
- CollisionMesh (`.collisionMesh`) import/export

## Installation
- To download use [Download ZIP](https://github.com/marekzajac97/bf2-blender/archive/refs/heads/main.zip) option
- To install see [Blender Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html)

## Usage

After installation, setup your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) (optional, but required to load textures and export texture paths). Then you can use `BF2` submenu in `File -> Import/Export`.

#### Animating:

- Import order of things matter! The skeleton needs to be loaded first! followed by the soldier/weapon/kitmesh and the animation loaded at the very end.
- When importing the weapon mesh or the soldier mesh, make sure you import only Geom0 Lod0 (First Person Animating) or Geom1 Lod0 (Third Person Animating). Each part of the weapon mesh will be automatically assigned to a vertex group from `mesh1` to `mesh16` and weighted with their respective bones.
- The skeleton will be imported as Blender's Armature object. The armature can be freely extended e.g. by adding helper bones for animating, but DO NOT modify imported bones! You should never change their name, position, rotation or relations in `Edit mode`. If you wish to do any of that, create additional helper bones and setup a `Child Of` constraint on the original bones (with those helper bones set as target) instead. See my [example 1P rig (for Blender 3.4)](https://www.mediafire.com/file/qh2km0hsfy2q7s0/bf2_blender_1p_rig.zip/file) for reference.
- [WIP] You can optionally enable `Setup controllers` option during animation import to automatically create basic controllers and IK setup (only works for 1P as of now)
- When exporting, you can select/deselect bones for export in the export menu (matters for 3P animations, depending on whether you're making soldier or weapon animations, different bone set needs to be selected).

#### Static modeling:
Export options will only be avaliable when you have an object active in the viewport. This is written 100% in Python which means the export is painfully slow, be patient! If anything described below is unclear just import any mesh and see how everything is set up.

##### StaticMesh exporting:
  - The active object needs to be the root of the hierarchy, each child of the root object must be a GEOM object (suffixed with `_geom<index>`), each child of the GEOM object must be a LOD object (suffixed with `_lod<index>`) containing mesh data.
```
root
└───geom<index>
	└───lod<index>
		└───mesh
```
- To setup StaticMesh material click on `Material Properties` panel, you should see `BF2 Material Tools` panel, expand it and click on `Add Material`.
- Inside the `Shader Editor`, assign texture files to the desired texture map types. There should be be 7 `Image Texture` nodes, each corresponding to Base, Detail, Dirt, Crack, Detail Normal, Crack Normal, the last one (SpecularLUT) can be ignored. Detail, Dirt, Crack and their normal maps are optional (can be removed or left unset). There should also be 5 `UV Map` nodes (linked to their corresponding image texture nodes) assign UV layers to them as described below.
- Each LOD's mesh must have assigned a minimum of 1 and a maximum of 5 UV layers and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps: UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, when Lightmap UV is not present it will be generated.
- Setting material's Blend Mode to `Alpha Blend` or `Alpha Clip` will export the material with BF2's `Alpha Blend` or `Alpha Test` transparency modes respectively.

##### CollisionMesh exporting:
  - The active object needs to be the root of the hierarchy, each child of the root object must be a GEOM object (suffixed with `_geom<index>`), each child of the geom object must be a SUBGEOM object (suffixed with `_subgeom<index>`) , each child of the subgeom object must be a LOD object (suffixed with `_lod<index>`) containing mesh data.
```
root
└───geom<index>
	└───subgeom<index>
		└───lod<index>
			└───mesh
```
- Each GEOM should have a maximum of 4 LODs where the LOD index corresponds to a specific collision type: Projectile = 0, Vehicle = 1, Soldier = 2, AI (navmesh) = 3.
- Each LOD's mesh can have an arbitrary number of materials assigned, matterial settings do not matter, only their existance and order.

## Credits

- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- Remdul for [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (most of the stuff is ported over form there)