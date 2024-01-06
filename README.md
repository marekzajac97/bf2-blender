# Blender addon for Battlefield 2

I'm probably like 15 years too late but anyway, here are some tools for importing/exporting Refractor 2 engine files for Blender as an alternative to 3ds Max tools. Development is still in its early stages, see below what is supported. Please report any issues found!

## Features:

- Animation (`.baf`) import/export
- Skeleton (`.ske`) import only
- StaticMesh (`.staticMesh`) import/export
- SkinnedMesh (`.skinnedMesh`) import only
- BundledMesh (`.bundledMesh`) import/export [WIP]
- CollisionMesh (`.collisionMesh`) import/export

## Installation
- Head over to [Releases](https://github.com/marekzajac97/bf2-blender/releases/) for download
- To install see [Blender Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html)

## Usage

After installation, setup your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) it's mandatory to load textures and export texture paths!. Then you can use `BF2` submenu in `File -> Import/Export`.

### Animating:

- Import order of things matter! The skeleton (`.ske`) needs to be loaded first, followed by the soldier/kitmesh (`.skinnedMesh`), the animated weapon (`.bundledMesh`) and the animation (`.baf`) loaded at the very end (**IMPORTANT NOTE**: DO NOT use `Import -> ObjecTemplate (.con)` for importing soldiers, kitmeshes or weapons for animating).
- When importing the weapon mesh or the soldier mesh, make sure you select only Geom0 Lod0 (First Person Animating) or Geom1 Lod0 (Third Person Animating) in the import settings. Each part of the weapon mesh will be automatically assigned to a vertex group from `mesh1` to `mesh16` and their respective bones.
- The skeleton will be imported as Blender's Armature object. The armature can be freely extended e.g. by adding helper bones for animating, but DO NOT modify imported bones! You should never change their name, position, rotation or relations in `Edit mode`. If you wish to do any of that, create additional helper bones and setup a `Child Of` constraint on the original bones (with those helper bones set as target) instead. See my [example 1P rig (for Blender 3.4)](https://www.mediafire.com/file/qh2km0hsfy2q7s0/bf2_blender_1p_rig.zip/file) for reference.
- [WIP] You can optionally enable `Setup controllers` option during animation import to automatically create basic controllers and IK setup (only works for 1P as of now)
- When exporting, you can select/deselect bones for export in the export menu (matters for 3P animations, depending on whether you're making soldier or weapon animations, different bone set needs to be selected).

### Object exporting
- In the curent state only StaticMeshes and some BundledMeshes will export properly, the setup proces is quite similar to the 3ds Max exporting. Export options will only be avaliable when you have an object active in the viewport. If anything described below is unclear just import any mesh and see how everything is set up.
- The active object needs to be the root of the hierarchy. The root needs to be prefixed with the geometry type: `StaticMesh` or `BundledMesh`, followed by an underscore an the name of the root ObjectTemplate. Each child of the root object must be an empty object that corresponds to Geom (suffixed with `G<index>__`):
    - for StaticMeshes: Geom0 = main, Geom1 = destoryed
    - for BundledMeshes: Geom0 = 1P, Geom1 = 3P, Geom2 = wreck.
- Each child of the Geom object must be an object that corresponds to Lod (suffixed with `G<index>L<index>__`) containing mesh data. Each Lod should be a simplified version of the previous one. There must be at least one Lod.
- Each Lod may contain multiple child objects that will be exported as separate ObjectTemplates using different geometry parts, each Lod must contain the same hierarchy of them. StaticMesh usually don't have any parts so Lod will be just a single object, but for BundledMeshes you might want multiple geometry parts like a "hull" as root and "turret" as its child etc.
- Each object must have its corresponding BF2 object type set (e.g. `Bundle`, `PlayerControlObject` etc). You will find this property in `Object Properties` tab.
- Each object may contain collision mesh data. To add it, you need to define an empty object prefixed with `NONVIS__`. The object should have a maximum of 4 child objects (suffixed with `__COL<index>`) containing collision mesh data, each corresponding to a specific collision type: Projectile = COL0, Vehicle = COL1, Soldier = COL2, AI (navmesh) = COL3.
- Each material that is assigned to any mesh must be set up for export. To setup BF2 material go to `Material Properties`, you should see `BF2 Material` panel there. Enable `Is BF2 Material` and choose appropriate settngs: `Alpha Mode`, `Shader` and `Technique` (for BundledMesh only). Click on `Apply Material`, which will apply corresponing blend modes and build a tree of Shader Nodes that tries to mimic BF2 rendering.
- Inside the `Shader Editor`, assign texture files to the desired texture map types:
    - For StaticMesh: There should be be 6 `Image Texture` nodes, each corresponding to Base, Detail, Dirt, Crack, Detail Normal, Crack Normal. Only Base texture is mandatory, if others are not ment to be used delete them, otherwise the mesh will appear all black! There should also be 5 `UV Map` nodes (linked to their corresponding image texture nodes), assign UV layers to them as described in the next bullet point.
    - For BundledMesh: There should be be 3 `Image Texture` nodes, each corresponding to Diffuse and Normal, There should also be 1 `UV Map` node.
- Each LOD's mesh must have assigned a minimum of 1 and a maximum of 5 UV layers and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps:
    - For StaticMesh UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, when Lightmap UV is not present it will be generated.
    - For BundledMesh there's only UV0 = Diffuse, exporting BundledMeshes with more than one UV layer is not supported right now.
- Each COL can have an arbitrary number of materials assigned, no special material settings are required, the matterial mapping will be dumped to the `.con` file.
- NOTE: currently collisionMesh exports to a slightly older file version (9) than 3DsMax exporter (10), which will make BF2 regenerate some missing data on load time, not a big deal.

Example object hierarchies. (`[m]` tag indicates that the object contains mesh data):

StatcMesh
```
StaticMesh_house
└─G0__car
  ├─G0L0__house [m]
  │ ├─NONVIS__G1L0__house
  │ ├─G1L0__house__COL0 [m]
  │ ├─G1L0__house__COL1 [m]
  │ ├─G1L0__house__COL2 [m]
  │ └─G1L0__house__COL3 [m]
  ├─G0L1__house [m]
  └─G0L2__house [m]
```

BunldedMesh
```
BundledMesh_car
├─G0__car
│ └─G0L0__car [m]
│  └─G0L0__car_steering [m]
├─G1__car
│ ├─G1L0__car [m]
│ │ ├─G1L0__car_steering [m]
│ │ ├─NONVIS__G1L0__car
│ │ │ ├─G1L0__car__COL0 [m]
│ │ │ └─G1L0__car__COL1 [m]
│ │ └─G1L0__car_motor [m]
│ │   ├─G1L0__car_navFL [m]
│ │   │ └─G1L0__car_whlFL [m]
│ │   │   └─NONVIS__G1L0__car
│ │   │     ├─G1L0__car_whlFL__COL0 [m]
│ │   │     └─G1L0__car_whlFL__COL1 [m]
│ │   ├─G1L0__car_navFR [m]
│ │   │ └─G1L0__car_whlFR [m]
│ │   │   └─NONVIS__G1L0__car
│ │   │     ├─G1L0__car_whlFR__COL0 [m]
│ │   │     └─G1L0__car_whlFR__COL1 [m]
│ │   ├─G1L0__car_whlRL [m]
│ │   │ └─NONVIS__G1L0__car
│ │   │   ├─G1L0__car_whlRL__COL0 [m]
│ │   │   └─G1L0__car_whlRL__COL1 [m]
│ │   │   
│ │   └─G1L0__car_whlRR [m]
│ │     └─NONVIS__G1L0__car
│ │       ├─G1L0__car_whlRR__COL0 [m]
│ │       └─G1L0__car_whlRR__COL1 [m]
│ ├─G1L1__car [m]
│ │ ├─G1L1__car_steering [m]
│ │ ├─NONVIS__G1L1__car
│ │ │ ├─G1L1__car__COL0 [m]
│ │ │ └─G1L1__car__COL1 [m]
│ │ └─G1L1__car_motor [m]
│ │   ├─G1L1__car_navFL [m]
│ │   │ └─G1L1__car_whlFL [m]
│ │   ├─G1L1__car_navFR [m]
│ │   │ └─G1L1__car_whlFR [m]
│ │   ├─G1L1__car_whlRL [m] 
│ │   └─G1L1__car_whlRR [m]
│ └─G1L2__car [m]
└─G2__car [m]
  ├─G2L0__car [m]
  │ └─NONVIS__G2L0__car
  │   ├─G2L0__car__COL0 [m]
  │   └─G2L0__car__COL1 [m]
  ├─G2L1__car [m]
  └─G2L2__car [m]
``` 

## Credits

- [rpoxo](https://github.com/rpoxo) for the [BF2 mesh file parser](https://github.com/rpoxo/bf2mesh) (MIT License)
- Remdul for guidance and [bfmeshview](http://www.bytehazard.com/bfstuff/bfmeshview/) (a lot of the stuff is ported over from there)
