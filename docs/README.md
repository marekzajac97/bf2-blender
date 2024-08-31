
# Table of Contents

- [BF2 glossary](#bf2-glossary)
- [Initial setup](#initial-setup)
- [Animating](#animating)
- [ObjectTemplate vs Mesh import/export](#objecttemplate-vs-mesh-import-export)
- [ObjectTemplate exporting](#objecttemplate-exporting)
  * [The object hierarchy](#the-object-hierarchy)
    + [Example object hierarchies](#example-object-hierarchies)
  * [Materials and UVs](#materials-and-uvs)
  * [Collision meshes](#collision-meshes)
  * [Skinning (BundledMesh)](#skinning-bundledmesh)
  * [Animated UVs (BundledMesh)](#animated-uvs-bundledmesh)
  * [Skinning (SkinnedMesh)](#skinning-skinnedmesh)
- [Tutorials](#tutorials)

# BF2 glossary
An explanation of BF2 terms used throughout this documentation.

- **Skeleton** - a set of bones with a defined hierarchy and transformations (position + rotation), exclusively used for skinning and animating SkinnedMeshes. Soldier skeletons (`1p_setup` and `3p_setup`) contain special `mesh` bones which are used for animating weapon parts (`mesh1` to `mesh16` for 1P and `mesh1` to `mesh8` for 3P). `3p_setup` also contains bones used for animating kit parts (`mesh9` to `mesh16`)
- **Visible geometry** - either BundledMesh, SkinnedMesh or StaticMesh
- **Geom** - each visible geometry type may define multiple sub-meshes called geoms, each geom usually represents the same object viewed from a different perspective or in a different state e.g. for Soldiers/Weapons/Vehicles Geom0 and Geom1 refer to 1P and 3P meshes respectively. Statics and Vehicles may also have an extra Geom for the destroyed/wreck variant.
- **Lod** - level of detail. Multiple Lods can be defined per Geom. Each Lod should be a simplified version of the previous one with Lod0 being the most detailed version.
- **StaticMesh** - Used for static, non-movable objects (e.g. bridges, buildings) with baked lighting via light maps.
- **BundledMesh** - Used for movable objects (e.g. vehicles, weapons)
- **SkinnedMesh** - Used for deformable objects (e.g. soldiers, flags)
- **CollisionMesh** - Used for object collision calculations, contains three meshes, each used for calculating collision with different object types (projectiles, vehicles, soldiers). Static objects may use additional mesh for AI navmesh generation.
- **ObjectTemplate** - A blueprint for every object, defines object type (e.g. `Bundle`, `PlayerControlObject`), its properties, visible geometry and collision mesh. ObjectTemplates (and objects) in BF2 are hierarchical, they may contain other ObjectTemplates as children (e.g. a root ObjectTemplate "tank" may define "turret" and "engine" as its children)
- **Geometry part** - A fragment of the BundledMesh which can be independently transformed (moved/rotated). Each geometry part is usually bound to one specific child ObjectTemplate. Handheld weapons are one exception in which they can define multiple geometry parts but only a single ObjectTemplate (they are just used for animating).
- **Material** - defines a set of textures and shading properties. Every face and vertex is assigned to a material.
- **Alpha Mode** - either `None`, `Alpha Test` (cheap, one-bit alpha), `Alpha Blend` (expensive, may increase overdraw)
- **Shader** - name of the shader for drawing the material.
- **Technique** - name that describes the shader permutation (a set of shader features) to use.
- **Animated UVs** - UV coordinates for BundledMeshes can be animated, BF2 uses this to fake tank track movement or wheel rotation (although you can also make the wheels separate objects and have the whole geometry part rotate instead). Each vertex must be assigned to a different UV matrix depending on whether it belongs to a tank track, wheel face or wheel outer rim and left/right side of the vehicle (total of 6 combinations) so it gets transformed correctly.


# Initial setup
After installation, set up your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) (optional but needed to load textures) Then you can use the `BF2` submenu in the `File -> Import/Export` or drag-and-drop any supported BF2 file.

# Animating
- The import order of things does matter! The skeleton (`.ske`) needs to be loaded first, followed by the soldier/kit mesh (`.skinnedMesh`), the animated weapon (`.bundledMesh`) and the animation (`.baf`) loaded at the very end (**IMPORTANT**: DO NOT use `Import -> ObjecTemplate (.con)` for importing soldiers, kit meshes or weapons for animating).
- When importing weapon or soldier meshes, select only Geom0 Lod0 (First Person Animating) or Geom1 Lod0 (Third Person Animating) in the import settings. Each part of the weapon mesh will be automatically assigned to a vertex group from `mesh1` to `mesh16` and their respective bones.
- The skeleton will be imported as Blender's Armature object. The armature can be freely extended e.g. by adding helper bones for animating, but **DO NOT** modify imported bones! You cannot change their name, position, rotation or relations in `Edit Mode` otherwise your export will be all messed up. Instead, create additional helper bones and set up constraints like `Child Of` and/or `Copy Transforms` on the original bones.
- You can use other add-ons such as `Rigify` to create the rig for animating, but also automatically create basic controllers and IK setup using the built-in `Pose -> BF2 -> Setup Controllers` option. This option can also be used after animation import which makes editing existing animations much easier (NOTE: importing an animation with a rig already set up will not work). By default, every controller bone will have no parent, meaning that some weapon parts will be detached from each other, you can use `Pose -> BF2 -> Change Parent` to fix that without messing up the existing position/rotation keyframes.
- TIP: If you plan to modify the imported animation, you can delete redundant keyframes using [Decimate](https://docs.blender.org/manual/en/latest/editors/graph_editor/fcurves/editing.html#decimate) option
- When exporting, you can select/deselect bones for export in the export menu (matters for 3P animations, depending on whether you're making soldier or weapon animations, a different bone set needs to be selected).

# ObjectTemplate vs Mesh import/export
There are two ways of importing BF2 meshes. One is to use the `Import -> BF2` menu to directly import a specific mesh file type (`StaticMesh`, `SkinnedMesh`, `BundledMesh` or `CollisionMesh`). This however will only import the _raw_ mesh data according to its internal file structure lacking information present in the ObjectTemplate (`.con`) definition such as mapping of the geometry part to BF2 ObjectTemplate name and type, geometry part transformations, hierarchy or collmesh material names. This data is not essential for simple meshes or when you intend just to make small tweaks to the mesh, but generally if you don't have a good reason to use those options, **don't** use them. The second (and preferable) way to import a mesh is via the `Import -> BF2 -> ObjecTemplate (.con)` option, which parses the ObjectTemplate definition and imports its visible geometry and (optionally) collision mesh, split all mesh parts into sub-meshes, reposition them, recreate their hierarchy as well as rename collision mesh materials. For re-exporting, always use the corresponding option from the `Export -> BF2` menu.

# ObjectTemplate exporting
- `Export -> BF2 -> ObjecTemplate (.con)` shall be used for exporting objects created from scratch (like 3ds Max exporter, it spits out a `.con` file + visible mesh + collision mesh into `Meshes` sub-directory). The export option will only be available when an object is active in the viewport. Before reading any further, I highly advise you to import any existing BF2 mesh first (`Import -> BF2 -> ObjecTemplate (.con)`) and look at how everything is set up to make the below steps easier to follow.

## The object hierarchy
- The active object needs to be the root of the hierarchy. The root needs to be prefixed with the geometry type (`StaticMesh`, `BundledMesh` or `SkinnedMesh`) followed by an underscore and the name of the root ObjectTemplate. Each child of the root object must be an empty object corresponding to Geom (prefixed with `G<index>__`). A static may also contain an empty child object which defines its anchor point (prefixed with `ANCHOR__`).
- Each child of the Geom object must be an object that corresponds to Lod (prefixed with `G<index>L<index>__`) containing mesh data. There must be at least one Lod.
- For BundledMeshes, each Lod may contain multiple child objects that will be exported as separate geometry parts bound to child ObjectTemplates. Each Lod must contain the same hierarchy of objects (their names and transformations must match between Lods). Geometry parts cannot be empty Blender objects, each one must contain mesh data to export properly! However, the mesh data itself may have no geometry (verts & faces deleted), which is useful for exporting things as invisible but separate logical gameplay objects.
- Each object in the hierarchy should have its corresponding BF2 ObjectTemplate type set. You will find this property in the `Object Properties` tab, it defaults to `SimpleObject`. It can be left empty when an object is intended to be exported as a separate geometry part but not bound to any child ObjectTemplate (mostly applies to exporting handheld weapon parts).

### Example object hierarchies

<details>
  <summary>StaticMesh</summary>

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
</details>

<details>
  <summary>BunldedMesh (a simple weapon)</summary>

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
</details>

<details>
  <summary>BunldedMesh (a simple vehicle)</summary>

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
</details>

<details>
  <summary>SkinnedMesh (a soldier)</summary>

```
SkinnedMesh_soldier
└─G0__soldier
  └─G0L0__soldier [m]
└─G1__soldier
  ├─G1L0__soldier [m]
  ├─G1L1__soldier [m]
  └─G1L2__soldier [m]
```
</details>

`[m]` tag indicates that the object contains mesh data.

## Materials and UVs
- Each material assigned to any visible mesh must be set up for export. To set up BF2 material go to `Material Properties`, you should see the `BF2 Material` panel there. Enable `Is BF2 Material` and choose appropriate settings: `Alpha Mode`, `Shader` and `Technique` (BundledMesh/SkinnedMesh only) as well as desired texture maps to load.
    - For StaticMesh: There will be 6 texture slots for Base, Detail, Dirt, Crack, Detail Normal, and Crack Normal. Only Base texture is mandatory, if others are not meant to be used, leave them empty.
    - For BundledMesh: There should be 3 texture slots for Diffuse, Normal, and Wreck. Only Diffuse texture is mandatory, if others are not meant to be used, leave them empty.
    - For SkinnedMesh: There should be 2 texture slots for Diffuse and Normal. Only the Diffuse texture is mandatory, if Normal is not meant to be used, leave it empty.
- Clicking on `Apply Material` changes some material settings, loads textures and builds a tree of Shader Nodes that try to mimic BF2 rendering.
- Each LOD's mesh must have a minimum of 1 and a maximum of 5 UV layers assigned and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps:
    - For StaticMesh UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, which can also be auto-generated when toggled in the export options.
    - For BundledMesh and SkinnedMesh there's only UV0 for all texture maps.
- Export requires one UV map to be chosen for tangent space calculation, this must be the same UV used to bake the normal map, for static meshes (which reuse textures) it should likely be UV1 (Detail Normal).

## Collision meshes
- Each object may contain collision mesh data. To add it, you must create an empty child object prefixed with `NONVIS__`. This new object should have a maximum of 4 child objects (suffixed with `_COL<index>`) containing collision mesh data, each corresponding to a specific collision type: Projectile = COL0, Vehicle = COL1, Soldier = COL2, AI (navmesh) = COL3. Collision meshes should only be added under the object's Lod0 hierarchies.
- Each COL can have an arbitrary number of materials assigned, no special material settings are required, object's material index-to-name mapping will be saved inside the `.con` file.

## Skinning (BundledMesh)
BF2 BundledMeshes support a basic method of skinning allowing one "bone" per vertex, where the "bone" is another object (geometry part). In other words, it enables "moving" some vertices from one object (geometry part) to another so that individual vertices that make up a face get split among different parts, which can be affected by the in-game physics differently and may cause some faces to stretch and deform. This technique is most commonly used for setting up tank tracks by splitting them up and "linking" track pieces to wheel objects. To achieve this in Blender create a new [Vertex Group](https://docs.blender.org/manual/en/latest/modeling/meshes/properties/vertex_groups/index.html) named **exactly** the same as the child object that the vertices are supposed to be transferred to and add them to the group. A single vertex must be assigned to **exactly one** vertex group, or you will get an export error.

## Animated UVs (BundledMesh)
To set up animated UVs go to `Edit Mode`, select specific parts (vertices/faces) of your mesh that should use UV animation and assign them to proper sets using the `Mesh -> BF2` menu, choosing Left/Right Tracks/Wheels Translation/Rotation. You can also select vertices/faces currently assigned to those sets using the `Select -> BF2` menu. Vertices assigned to the "wheel rotation" set will additionally require setting up the centre point of UV rotation for each wheel individually. Select all vertices, position the 2D cursor to the wheel centre in the UV Editing view, then select `Mesh -> BF2 -> Set Animated UV Rotation Center`. Repeat the process for all wheels.

## Skinning (SkinnedMesh)
In order to skin your model, you must import the BF2 skeleton into your scene. When skinning soldiers you will need two skeletons `1p_setup.ske` for 1P (Geom 0) and `3p_setup.ske` 3P (Geom 1). The first step is to switch to `Pose Mode` and pose the armature(s) to align it with your mesh(es) as best as possible. When you are done, make sure you apply this pose as the rest pose [Pose -> Apply -> Apply Pose As Rest Pose](https://docs.blender.org/manual/en/latest/animation/armatures/posing/editing/apply.html), then switch to `Object Mode` and for each Lod object go to `Modifiers` tab and [Add Modifier -> Deform -> Armature](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html), in modifier settings select 'Object' to point to the name of the imported skeleton. Now the hard part, you have to set vertex weights for each Lod, meaning how much each bone affects each vertex of the mesh. You could use automatic weights (which should be a good starting point) as follows: In `Object Mode` select the Armature, go to `Pose Mode`, click `Select -> All`, go back to `Object Mode`, select the mesh while holding the `Shift` key, go to `Weight Paint` mode use [Weights -> Assign Automatic From Bones](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#assign-automatic-from-bone). Bare in mind that to export properly, each vertex must have at most two weights (be assigned to a maximum of two vertex groups), and all those weights have to be normalized (add-up to 1). You can limit the number of vertex weights in `Weight Paint` mode using [Weights -> Limit Total](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#limit-total) option (make sure it is set to 2). You can normalize weights using [Weights -> Normalize All](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#normalize-all) option. Also, make sure that `Auto Normalize` is enabled in [Weight Paint Tools Settings](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/tool_settings/options.html) when skinning in `Weight Paint` mode.

# Tutorials
- [Animation - rig setup, export, import and editing (by Ekiso)](https://youtu.be/xO1848HzetQ)
- [StaticMesh - hierarchy, materials and export (by Ason)](https://www.youtube.com/watch?v=H97o0d3zkoY)
- [BundledMesh - simple weapon export (by Krayt)](https://www.youtube.com/watch?v=crQRXm-4lxQ)
