# Initial setup
After installation, set up your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) it's mandatory to load textures and export texture paths! Then you can use `BF2` submenu in `File -> Import/Export`.

# Animating:
- Import order of things does matter! The skeleton (`.ske`) needs to be loaded first, followed by the soldier/kitmesh (`.skinnedMesh`), the animated weapon (`.bundledMesh`) and the animation (`.baf`) loaded at the very end (**IMPORTANT**: DO NOT use `Import -> ObjecTemplate (.con)` for importing soldiers, kitmeshes or weapons for animating).
- When importing the weapon mesh or the soldier mesh, make sure you select only Geom0 Lod0 (First Person Animating) or Geom1 Lod0 (Third Person Animating) in the import settings. Each part of the weapon mesh will be automatically assigned to a vertex group from `mesh1` to `mesh16` and their respective bones.
- The skeleton will be imported as Blender's Armature object. The armature can be freely extended e.g. by adding helper bones for animating, but **DO NOT** modify imported bones! You should never change their name, position, rotation or relations in `Edit mode` or your export will be all messed up. Instead, create additional helper bones and set up a `Child Of` constraint on the original bones (with those helper bones set as targets).
- [WIP] You can optionally enable `Setup controllers` option during animation import to automatically create basic controllers and IK setup (only works for 1P as of now)
- When exporting, you can select/deselect bones for export in the export menu (matters for 3P animations, depending on whether you're making soldier or weapon animations, a different bone set needs to be selected).

# Object exporting
- Always use `Export -> ObjecTemplate (.con)` for exporting objects (like 3ds Max exporter, it spits out `.con` file + visible mesh + collision mesh), other options from the `Export` menu for specific mesh types can only be used when you imported the mesh using a corresponding option from the `Import` menu.
- The setup process is quite similar to the 3ds Max exporting. Export options will only be available when you have an object active in the viewport. I advise you to import any BF2 mesh first (`Import -> ObjecTemplate (.con)`), and look at how everything is set up to make below steps easier to follow.

## The object hierarchy
- The active object needs to be the root of the hierarchy. The root needs to be prefixed with the geometry type: `StaticMesh` or `BundledMesh`, followed by an underscore and the name of the root ObjectTemplate. Each child of the root object must be an empty object that corresponds to Geom (prefixed with `G<index>__`):
    - for StaticMeshes: Geom0 = main, Geom1 = destoryed
    - for BundledMeshes: Geom0 = 1P, Geom1 = 3P, Geom2 = wreck.
- Each child of the Geom object must be an object that corresponds to Lod (prefixed with `G<index>L<index>__`) containing mesh data. Each Lod should be a simplified version of the previous one. There must be at least one Lod.
- Each Lod may contain multiple child objects that will be exported as separate ObjectTemplates using different geometry parts, each Lod must contain the same hierarchy of them. StaticMeshes usually don't have any parts, so Lod will be just a single object, but for BundledMeshes you might want to have multiple geometry parts (e.g. "hull" as root and a "turret" and "motor" as its child objects). Those objects cannot be empty, each one must contain mesh data to export properly! However, if you just want them to export as invisible but separate logical objects (e.g. the `Engine` ObjectTemplate of the vehicle) you can delete all geometry (verts/faces) from the mesh object.
- Each object in the hierarchy should have its corresponding BF2 ObjectTemplate type set (e.g. `Bundle`, `PlayerControlObject` etc). You will find this property in the `Object Properties` tab, it defaults to `SimpleObject`. However, you may want some meshes to export as separate geometry parts but at the same time don't export as separate ObjectTemplates (e.g. an animatable magazine that is a part of `GenericFirearm`) in such case simply leave this property empty.

## Materials and UVs
- Each material that is assigned to any visible mesh must be set up for export. To setup BF2 material go to `Material Properties`, you should see `BF2 Material` panel there. Enable `Is BF2 Material` and choose appropriate settings: `Alpha Mode`, `Shader` and `Technique` (applies for BundledMesh only) as well as desired texture maps to load.
    - For StaticMesh: There will be 6 texture slots for Base, Detail, Dirt, Crack, Detail Normal, and Crack Normal. Only Base texture is mandatory, if others are not meant to be used, leave them empty.
    - For BundledMesh: There should be 3 texture slots for Diffuse, Normal, and Shadow. Only Diffuse texture is mandatory, if others are not meant to be used, leave them empty.
- Clicking on `Apply Material` changes some material settings, loads textures and builds a tree of Shader Nodes that try to mimic BF2 rendering.
- Each LOD's mesh must have assigned a minimum of 1 and a maximum of 5 UV layers and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps:
    - For StaticMesh UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, which can also be auto-generated when toggled in the export options.
    - For BundledMesh there's only UV0 for all texture maps.
- Export requires one UV map to be chosen for tangent space calculation, this must be the same UV that was used to bake the normal map, for static meshes (which reuse textures) it should likely be UV1 (Detail Normal).

## Collision meshes
- Each object may contain collision mesh data. To add it, you need to create an empty child object that is prefixed with `NONVIS__`. This new object should have a maximum of 4 child objects (suffixed with `__COL<index>`) containing collision mesh data, each corresponding to a specific collision type: Projectile = COL0, Vehicle = COL1, Soldier = COL2, AI (navmesh) = COL3. Collision meshes should only be added to object's Lod0 hierchies.
- Each COL can have an arbitrary number of materials assigned, no special material settings are required, the material mapping will be dumped to the `.con` file.

## Tank tracks skinning (BundledMesh)
The term "skinning" is probably an exaggeration in the context of BundledMeshes. Essentialy, it comes down to just "moving" some of the vertices of one geometry part to another so that some faces get split among different parts, which can cause them to stretch and deform. This technique is commonly used for setting up tank tracks by linking them to wheel objects. To do this, create a new [Vertex Group](https://docs.blender.org/manual/en/latest/modeling/meshes/properties/vertex_groups/index.html) named **exactly** the same as the child object that the vertices are supposed to be linked to and add them to the group. Make sure that a single vertex is assigned to **exactly one** vertex group, or you will get an export error.

## Animated UVs (BundledMesh)
To set up animated UVs go to `EDIT MODE`, select specific parts (vertices/faces) of your mesh that should use UV animation and assign them to proper sets using `Mesh -> BF2` menu, choosing Left/Right Tracks/Wheels Translation/Rotation. You can also select vertices/faces currently assigned to those sets using `Select -> BF2` menu. Vertices assinged to "wheel rotation" set will additionaly require setting up the center point of UV rotation for each wheel individually. Select all vertices, and position the 2D cursor to the wheel center in the UV Editing view, then select `Mesh -> BF2 -> Set Animated UV Rotation Center`. Repeat the process for all wheels.

## Example object hierarchies

`[m]` tag indicates that the object contains mesh data.


StatcMesh
```
StaticMesh_house
└─G0__house
  ├─G0L0__house [m]
  │ └─NONVIS__G1L0__house
  │   ├─G1L0__house__COL0 [m]
  │   ├─G1L0__house__COL1 [m]
  │   ├─G1L0__house__COL2 [m]
  │   └─G1L0__house__COL3 [m]
  ├─G0L1__house [m]
  └─G0L2__house [m]
```

BunldedMesh (a simple weapon)
```
BunldedMesh_gun
├─G0__gun
│ └─G0L0__gun [m]
│   ├─G0L0__gun_1_mag
│   └─G0L0__gun_2_bolt
└─G1__gun
  ├─G1L0__gun [m]
  │ ├─G1L0__gun_1_mag
  │ ├─G1L0__gun_2_bolt
  │ └─NONVIS__G1L0__gun
  │   ├─G1L0__gun__COL0 [m]
  │   ├─G1L0__gun__COL1 [m]
  │   └─G1L0__gun__COL2 [m]
  ├─G1L1__gun [m]
  │ ├─G1L1__gun_1_mag
  │ ├─G1L1__gun_2_bolt
  └─G1L2__gun [m]
    ├─G1L2__gun_1_mag
    └─G1L2__gun_2_bolt
```

BunldedMesh (a simple vehicle)
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
│ │   │   └─NONVIS__G1L0__car_whlFR
│ │   │     ├─G1L0__car_whlFR__COL0 [m]
│ │   │     └─G1L0__car_whlFR__COL1 [m]
│ │   ├─G1L0__car_whlRL [m]
│ │   │ └─NONVIS__G1L0__car_whlRL
│ │   │   ├─G1L0__car_whlRL__COL0 [m]
│ │   │   └─G1L0__car_whlRL__COL1 [m]
│ │   │   
│ │   └─G1L0__car_whlRR [m]
│ │     └─NONVIS__G1L0__car_whlRR
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
