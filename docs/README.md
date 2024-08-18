# Initial setup
After installation, set up your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) it's mandatory to load textures and export texture paths! Then you can use `BF2` submenu in `File -> Import/Export`.

# Animating:
- Import order of things does matter! The skeleton (`.ske`) needs to be loaded first, followed by the soldier/kitmesh (`.skinnedMesh`), the animated weapon (`.bundledMesh`) and the animation (`.baf`) loaded at the very end (**IMPORTANT**: DO NOT use `Import -> ObjecTemplate (.con)` for importing soldiers, kitmeshes or weapons for animating).
- When importing the weapon mesh or the soldier mesh, make sure you select only Geom0 Lod0 (First Person Animating) or Geom1 Lod0 (Third Person Animating) in the import settings. Each part of the weapon mesh will be automatically assigned to a vertex group from `mesh1` to `mesh16` and their respective bones.
- The skeleton will be imported as Blender's Armature object. The armature can be freely extended e.g. by adding helper bones for animating, but **DO NOT** modify imported bones! You must never change their name, position, rotation or relations in `Edit Mode` otherwise your export will be all messed up. Instead, create additional helper bones and set up constraints like `Child Of` and/or `Copy Transforms` on the original bones.
- You can use other add-ons such as `Rigify` to create the rig for animating but you can also automatically create basic controllers and IK setup using the built-in `Pose -> BF2 -> Setup Controlers` option. This option can also be used after animation import which makes editing existing animations much easier (NOTE: importing an animation with a rig already set-up is not going to work). By default, every controller bone will have no parent, meaning that some weapon parts will be detached from each other, you can use `Pose -> BF2 -> Change Parent` to fix that without messing up the exising position/roation keyframes.
- TIP: If you plan to modify the imported animation, you can delete redundant keyframes using [Decimate](https://docs.blender.org/manual/en/latest/editors/graph_editor/fcurves/editing.html#decimate) option
- When exporting, you can select/deselect bones for export in the export menu (matters for 3P animations, depending on whether you're making soldier or weapon animations, a different bone set needs to be selected).

# Import/export of ObjectTemplate vs (Bundled/Skinned/Static/Collision)Mesh
There are two ways of importing BF2 meshes. One is to use `Import -> BF2` menu to directly import a specific mesh file type e.g. `StaticMesh`. This however will only import the "raw" mesh data according to its internal file structure lacking information about objectTemplate's metadata such as geometry part names, their position/rotation, hierarchy, collision material names etc. This is fine for simple meshes or when you intend just to make small tweaks to the mesh, but generally if you don't have a good reason to use those options, **don't** use them. A preferable way to import a mesh is the `Import -> BF2 -> ObjecTemplate (.con)` option, which parses the objectTemplate definition and imports the visible geometry of the object (optionally also its collision mesh), split all mesh parts into sub-meshes, reposition them, recreate their hierarchy as well as rename collision mesh materials. For re-exporting, always use the corresponding option from the `Export -> BF2` menu.

# ObjectTemplate exporting
- `Export -> BF2 -> ObjecTemplate (.con)` shall be used for exporting objects created from scratch (like 3ds Max exporter, it spits out a `.con` file + visible mesh + collision mesh into `Meshes` sub-directory). Export option will only be available when you have an object active in the viewport. Before reading any further, I highly advise you to import any existing BF2 mesh first (`Import -> BF2 -> ObjecTemplate (.con)`), and look at how everything is set up to make below steps easier to follow.

## The object hierarchy
- The active object needs to be the root of the hierarchy. The root needs to be prefixed with the geometry type: `StaticMesh`, `BundledMesh` or `SkinnedMesh`, followed by an underscore and the name of the root ObjectTemplate. Each child of the root object must be an empty object that corresponds to Geom (prefixed with `G<index>__`). A static may also contain an empty child object which defines its anchor point (prefixed with `ANCHOR__`).
- Each Geom usually represents the same object viewed from a different perspective or in a different state e.g. for Soldiers/Weapons/Vehicles Geom0 and Geom1 refer to 1P and 3P meshes respectively. Statics and Vehicles may also have an extra Geom for the destroyed/wreck variant.
- Each child of the Geom object must be an object that corresponds to Lod (Level of detail) (prefixed with `G<index>L<index>__`) containing mesh data. Each Lod should be a simplified version of the previous one. There must be at least one Lod.
- Each Lod may contain multiple child objects that will be exported as separate ObjectTemplates using different geometry parts, each Lod must contain the same hierarchy of them. StaticMeshes or SkinnedMeshes usually don't have any parts, so Lod will be just a single object, but for BundledMeshes you might want to have multiple geometry parts (e.g. "hull" as root and a "turret" and "motor" as its child objects). Those objects cannot be empty, each one must contain mesh data to export properly! However, the mesh data itself may have no geometry (verts & faces deleted), which is useful for exporting things as invisible but separate logical objects (e.g. the `Engine` ObjectTemplate of the vehicle).
- Each object in the hierarchy should have its corresponding BF2 ObjectTemplate type set (e.g. `Bundle`, `PlayerControlObject` etc). You will find this property in the `Object Properties` tab, it defaults to `SimpleObject`. It can be left empty when an object is intended to be exported as a separate geometry part but not as a separate ObjectTemplate (e.g. an animatable weapon part of the handheld `GenericFirearm`).

## Materials and UVs
- Each material that is assigned to any visible mesh must be set up for export. To setup BF2 material go to `Material Properties`, you should see `BF2 Material` panel there. Enable `Is BF2 Material` and choose appropriate settings: `Alpha Mode`, `Shader` and `Technique` (BundledMesh/SkinnedMesh only) as well as desired texture maps to load.
    - For StaticMesh: There will be 6 texture slots for Base, Detail, Dirt, Crack, Detail Normal, and Crack Normal. Only Base texture is mandatory, if others are not meant to be used, leave them empty.
    - For BundledMesh: There should be 3 texture slots for Diffuse, Normal, and Wreck. Only Diffuse texture is mandatory, if others are not meant to be used, leave them empty.
    - For SkinnedMesh: There should be 2 texture slots for Diffuse and Normal. Only Diffuse texture is mandatory, if Normal is not meant to be used, leave it empty.
- Clicking on `Apply Material` changes some material settings, loads textures and builds a tree of Shader Nodes that try to mimic BF2 rendering.
- Each LOD's mesh must have a minimum of 1 and a maximum of 5 UV layers assigned and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps:
    - For StaticMesh UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, which can also be auto-generated when toggled in the export options.
    - For BundledMesh and SkinnedMesh there's only UV0 for all texture maps.
- Export requires one UV map to be chosen for tangent space calculation, this must be the same UV that was used to bake the normal map, for static meshes (which reuse textures) it should likely be UV1 (Detail Normal).

## Collision meshes
- Each object may contain collision mesh data. To add it, you need to create an empty child object that is prefixed with `NONVIS__`. This new object should have a maximum of 4 child objects (suffixed with `_COL<index>`) containing collision mesh data, each corresponding to a specific collision type: Projectile = COL0, Vehicle = COL1, Soldier = COL2, AI (navmesh) = COL3. Collision meshes should only be added under object's Lod0 hierchies.
- Each COL can have an arbitrary number of materials assigned, no special material settings are required, object's material index-to-name mapping will be saved inside the `.con` file.

## Tank tracks skinning (BundledMesh)
BF2 BundledMeshes support a basic method of skinning allowing one "bone" per vertex, where the "bone" is another object (geometry part). In other words, it allows "moving" some of the vertices from one object (geometry part) to another so that individual vertices that make up a face get split among different parts. These parts can be affected by in-game physics differently which may cause some faces to stretch and deform. This technique is most commonly used for setting up tank tracks by splitting them up and "linking" track pieces to wheel objects. To achieve this in Blender create a new [Vertex Group](https://docs.blender.org/manual/en/latest/modeling/meshes/properties/vertex_groups/index.html) named **exactly** the same as the child object that the vertices are supposed to be transferred to and add them to the group. Make sure that a single vertex is assigned to **exactly one** vertex group, or you will get an export error.

## Animated UVs (BundledMesh)
To set up animated UVs go to `Edit Mode`, select specific parts (vertices/faces) of your mesh that should use UV animation and assign them to proper sets using `Mesh -> BF2` menu, choosing Left/Right Tracks/Wheels Translation/Rotation. You can also select vertices/faces currently assigned to those sets using `Select -> BF2` menu. Vertices assinged to "wheel rotation" set will additionaly require setting up the center point of UV rotation for each wheel individually. Select all vertices, and position the 2D cursor to the wheel center in the UV Editing view, then select `Mesh -> BF2 -> Set Animated UV Rotation Center`. Repeat the process for all wheels.

## Rigging (SkinnedMesh)
In order to rig your model, you must import the BF2 skeleton into your scene. When rigging soldiers you will need two skeletons `1p_setup.ske` for 1P (Geom 0) and `3p_setup.ske` 3P (Geom 1). The first step is to switch to `Pose Mode` and pose the armature(s) to best match your mesh(es). When you are done, make sure you apply this pose as the rest pose [Pose -> Apply -> Apply Pose As Rest Pose](https://docs.blender.org/manual/en/latest/animation/armatures/posing/editing/apply.html), then switch to `Object Mode` and for each Lod object go to `Modifiers` tab and [Add Modifier -> Deform -> Armature](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html), in modifier settings select 'Object' to point to the name of the imported skeleton. Now the hard part, you have to set vertex weights for each Lod, meaning how much each bone affects each vertex of the mesh. You could use automatic weights (which should be a good starting point) as follows: In `Object Mode` select the Armature, go to `Pose Mode`, click `Select -> All`, go back to `Object Mode`, select the mesh while holding the `Shift` key, go to `Wieght Paint` mode use [Weights -> Assign Automatic From Bones](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#assign-automatic-from-bone). Bare in mind that to export properly, each vertex must have at most two weights (be assigned to a maximum of two vertex groups), and all those weights have to be normalized (add-up to 1). You can limit the number of vertex weights in `Weight Paint` mode using [Weights -> Limit Total](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#limit-total) option (make sure it is set to 2). You can normalize weights using [Weights -> Normalize All](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#normalize-all) option. Also, make sure that `Auto Normalize` is enabled in [Weight Paint Tools Settings](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/tool_settings/options.html) when rigging in `Weight Paint` mode.

## Example object hierarchies

`[m]` tag indicates that the object contains mesh data.


StatcMesh
```
StaticMesh_house
├─ANCHOR__house
└─G0__house
  ├─G0L0__house [m]
  │ └─NONVIS__G1L0__house
  │   ├─G0L0__house__COL0 [m]
  │   ├─G0L0__house__COL1 [m]
  │   ├─G0L0__house__COL2 [m]
  │   └─G0L0__house__COL3 [m]
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

SkinnedMesh (a soldier)
```
SkinnedMesh_soldier
└─G0__soldier
  └─G0L0__soldier [m]
└─G1__soldier
  ├─G1L0__soldier [m]
  ├─G1L1__soldier [m]
  └─G1L2__soldier [m]
```
