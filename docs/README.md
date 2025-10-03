
# Table of Contents

- [BF2 glossary](#bf2-glossary)
  * [Texturing](#texturing)
    + [StaticMesh](#staticmesh)
    + [BundledMesh/SkinnedMesh](#bundledmesh-skinnedmesh)
- [Initial Add-on setup](#initial-add-on-setup)
- [Animating](#animating)
  * [Animation Import](#animation-import)
  * [Rig setup](#rig-setup)
  * [Animation Export](#animation-export)
  * [Recommended Extensions](#recommended-extensions)
- [ObjectTemplate vs Mesh import/export](#objecttemplate-vs-mesh-importexport)
- [ObjectTemplate export guide](#objecttemplate-export-guide)
  * [The object hierarchy](#the-object-hierarchy)
    + [Example object hierarchies](#example-object-hierarchies)
  * [Materials and UVs](#materials-and-uvs)
  * [Collision meshes](#collision-meshes)
  * [Skinning (BundledMesh)](#skinning-bundledmesh)
  * [Animated UVs (BundledMesh)](#animated-uvs-bundledmesh)
  * [Skinning (SkinnedMesh)](#skinning-skinnedmesh)
- [Video Tutorials](#video-tutorials)
- [Scripting](#scripting)

# BF2 glossary
An explanation of BF2 terms and systems used throughout this documentation.

- **Skeleton** - a set of bones with a defined hierarchy and transformations (position + rotation), exclusively used for skinning and animating SkinnedMeshes. Soldier skeletons (`1p_setup` and `3p_setup`) contain special `mesh` bones which are used for animating weapon parts (`mesh1` to `mesh16` for 1P and `mesh1` to `mesh8` for 3P). `3p_setup` also contains bones used for animating kit parts (`mesh9` to `mesh16`)
- **Visible mesh** - refers to either the BundledMesh, SkinnedMesh or StaticMesh
- **Geom** - "geometry". Each visible mesh type may define multiple sub-meshes refered to as geoms, each geom usually represents the same object viewed from a different perspective or in a different state e.g. for Soldiers/Weapons/Vehicles Geom0 and Geom1 refer to 1P and 3P meshes respectively. Statics and Vehicles may also have an extra Geom for their destroyed/wreck variant.
- **Lod** - "level of detail". Multiple Lods can be defined per Geom. Each Lod should be a simplified version of the previous one with Lod0 being the most detailed version. Most BF2 models are rather low-poly and modern GPUs are _fast_, so optimizing the poly count will usually have little to no impact on the performance. Reducing the number of materials on Lods should be prioritized instead to limit the number of draw calls and CPU load, which is the main bottleneck in the BF2 engine.
- **StaticMesh** - Used for static, non-movable objects (e.g. bridges, buildings) with baked lighting via light maps.
- **BundledMesh** - Used for movable objects (e.g. vehicles, weapons)
- **SkinnedMesh** - Used for deformable objects (e.g. soldiers, flags)
- **CollisionMesh** - Used for object collision calculations, cosists of three sub-meshes, each used for calculating collision between different object types (projectiles, vehicles and soldiers). Static objects may use additional sub-mesh for AI navmesh generation.
- **ObjectTemplate** - A blueprint for every in-game object, defines object type (e.g. `Bundle`, `PlayerControlObject`), its properties, visible mesh and collision mesh. ObjectTemplates (and objects) in BF2 are hierarchical, they may contain other ObjectTemplates as children (e.g. a root ObjectTemplate "tank" may define "turret" and "engine" as its children)
- **Geometry part** - A fragment of the BundledMesh's geom which can be independently transformed (moved/rotated). Each geometry part is usually bound to one specific child ObjectTemplate. Handheld weapons are one exception in which they can define multiple geometry parts but only a single ObjectTemplate (they are just used for animating).
- **Material** - defines a set of textures and shading properties. Every face and vertex is assigned to a material.
- **Alpha Mode** - either `None`, `Alpha Test` (cheap, one-bit alpha), `Alpha Blend` (expensive, may increase overdraw)
- **Shader** - name of the shader (.fx) file to use for drawing the material, usually matches the visible mesh type name.
- **Technique** - a combination of names that describe the shader permutation (a set of shader features) to use for a particular material. These names are harcoded in the game engine.
- **Animated UVs** - UV (texture) coordinates for BundledMeshes can be animated, BF2 uses this to fake tank track movement and/or wheel rotation. Vertices that shall use this feature must be mapped to a specific UV transformation matrix depending on whether they belong to a tank track, wheel face or wheel outer rim and left/right side of the vehicle (total of 6 different combinations).

## Texturing

A brief explanation of how the texturing system in BF2 works.

### StaticMesh
StaticMesh materials in BF2 are designed to use [texture atlases](https://en.wikipedia.org/wiki/Texture_atlas) and a set of layers, including:
- `Base`: a very basic uniform colour texture.
- `Detail`: contains surface details and patterns like wood or bricks (gets multiplied with the Base texture).
- `Dirt`: used for adding dirt, stains or ambient occlusion (gets multiplied with the Base and Detail textures)
- `Crack`: used for adding cracks or other decals (gets overlayed on top of the Base, Detail and Dirt textures)
- `NDetail`: Normal map for the Detail texture.
- `NCrack`: Normal map for the Crack texture.

NOTE: Only some combinations of the above texture layers are valid.

The roughness map is embeded into the alpha channel of either the `Detail` map when Alpha Mode is set to `None` or the `NDetail` map when Alpha Mode is set to either `Alpha Blend` or `Alpha Test`.

### BundledMesh/SkinnedMesh
BundledMesh and SkinnedMesh materials use two texture maps: `Diffuse Color` and `Normal`. BundledMesh may use an extra `Wreck` texture map which gets multiplied with the `Diffuse Color` when a vehicle gets destroyed. SkinnedMesh materials may use either tangent space or object space normal maps with the latter one being more common, the engine differentiates them by `_b` or `_os` suffix.

For BundledMesh, the roughness map is embeded into the alpha channel of either the `Diffuse Color` map when Alpha Mode is set to `None` or the `Normal` map when Alpha Mode is set to either `Alpha Blend` or `Alpha Test`. SkinnedMesh materials always have their roughness map in the `Normal` map's alpha channel.

# Initial Add-on setup
After installation, set up your `BF2 mod directory` (`Edit -> Preferences -> Add-ons -> BF2 Tools -> Preferences`) (optional but needed to load textures) Then you can use the `BF2` submenu in the `File -> Import/Export` or drag-and-drop any supported BF2 file.

# Animating
The add-on ships with extensive toolset for creating BF2 animations including batch import/export, automated rig setup and more. This section contains all the info you need to get started.

## Animation Import
To import an animation you will generally need these four things imported into your scene in this exact order!
 1. The skeleton (`.ske`)
 2. The soldier mesh (and optionally a kit mesh) (`.skinnedMesh`)
 3. The weapon mesh (`.bundledMesh`)
 4. The animation (`.baf`)

When importing soldier or weapon meshes, select only Geom0/Lod0 (First Person Animating) or Geom1/Lod0 (Third Person Animating) in the import settings. **IMPORTANT**: DO NOT use `Import -> BF2 -> ObjecTemplate (.con)` for that purpose!

TIP: Imported animations are baked so you might need to delete redundant keyframes if you want to edit them, use [Decimate](https://docs.blender.org/manual/en/latest/editors/graph_editor/fcurves/editing.html#decimate) for that.

## Rig Setup
The skeleton will be imported as Blender's Armature object and before you start animating you might need to create a rig for it. You can do that either:
### Manually
The armature can be freely extended by appending more bones to it which can act as helpers (constrain targets), but imported bones **MUST NOT** be modified! You cannot change their name, position, rotation or relations in `Edit Mode` otherwise your export will be all messed up. To alter their relations you can set up constraints (such as [Child Of](https://docs.blender.org/manual/en/latest/animation/constraints/relationship/child_of.html) and/or [Copy Transforms](https://docs.blender.org/manual/en/latest/animation/constraints/transform/copy_transforms.html) to other helper bones) on them instead.
### Automatically
- Using external add-ons such as [Rigify](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/index.html)
- Using this add-on's built-in option found under `Pose -> BF2 -> Setup Controllers`. This option can also be used after animations have been imported for easier editing of existing animations. By default, every controller bone will have no parent, meaning that some weapon parts will be detached from each other, you can use `Pose -> BF2 -> Change Parent` to fix that without messing up the existing animation data. NOTE: importing animations **AFTER** `Setup Controllers` has been run is not supported and will not work!

## Animation Export
Export settings allow you to choose:
- whether to export in Armature space or World space
- which [Actions](https://docs.blender.org/manual/en/latest/animation/actions.html) to export (each Action can be exported as a separate `.baf` file). NOTE: Blender 4.4 or above required
- which bones to export (mostly matters for 3P animations, depending on whether you're making soldier or weapon animations, a different bone set needs to be selected).

## Recommended Extensions:
Some very useful 3rd party add-ons for animating:
  * [Action to Scene Range](https://extensions.blender.org/add-ons/action-to-scene-range/) automatically applies [Action frame range](https://docs.blender.org/manual/en/latest/animation/actions.html#action-properties) to Scene frame range (makes life easier when working with multiple animations)
  * [Unlooped](https://extensions.blender.org/add-ons/unlooped/) prevents Blender from looping scene playback (useful for e.g. checking how smooth your fade outs to base pose are)
  * [Animation Auto Offset](https://extensions.blender.org/add-ons/anim-auto-offset/) works like auto-keying but transform changes affect the whole animation (3ds Max like behaviour)

## Known issues
- Many vBF2 skeleton exports have messy bone orientations. Skeleton importer corrects them for `1p_setup.ske` and `3p_setup.ske` but other skeletons' bones may appear pointing in random directions.
- Blender does not support mesh deformations when using Object Space normal maps. This means most SkinnedMeshes will have shading issues when deformed/animated, no workaround found yet.

# ObjectTemplate vs Mesh import/export
There are two ways of importing BF2 meshes. One is to use the `Import -> BF2` menu to directly import a specific mesh file type (`.staticMesh`, `.skinnedMesh`, `.bundledMesh` or `.collisionMesh`), which only imports the _raw_ mesh data according to its internal file structure lacking some data present in the `.con` file, that's why its usage is limited. The second (and preferred) method is the `ObjecTemplate (.con)` option, which parses the ObjectTemplate definition allowing it to:
- load visible mesh of the proper type
- separate all geometry parts into Blender objects
- transform (move & rotate) all geometry parts
- map geometry parts to ObjectTemplates applying their names, types and hierarchy.
- load collision mesh (with proper material names) and map collision parts to ObjectTemplates

When you want to re-export a mesh that has been imported and modified, a proper option from the `Export -> BF2` menu has to be chosen based on the option used to import the mesh, meaning that when you import `.staticMesh` also export it as `.staticMesh`, other combinations will not work! Bare in mind that the `ObjectTemplate (.con)` exporter not only saves the ObjectTemplate's definition to a `.con` file but also exports visible mesh and collision mesh into the `Meshes` sub-directory.

## Known issues
- Some vBF2 meshes and meshes exported with Autodesk 3ds Max may contain backfaces (another face defined over the same set of vertices but opossing normal directons). Such faces are (rightfully) illegal in Blender but for compatibility reasons are supported by the add-on. To avoid duplication of vertices when importing a mesh, each double-sided face will be tagged using a custom per-face boolean [Attribute](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/attributes_reference.html) called `backface`. When exporting a mesh, each face having attribute `backface` set will be exported as double-sided. To see which faces will be treated as double-sided while in `Edit Mode` select `backface` from [Attributes in Object Data](https://docs.blender.org/manual/en/latest/modeling/meshes/properties/object_data.html#attributes) and use [Select -> By Attribyte](https://docs.blender.org/manual/en/latest/modeling/meshes/selecting/by_attribute.html). To set or clear them use [Mesh -> Set Attribute](https://docs.blender.org/manual/en/latest/modeling/meshes/editing/mesh/set_attribute.html).
- Blender does not allow to import custom tangent data, therefore when re-exporting meshes, vertex tangents always get re-calculated. This may increase the number of unique vertices being exported. Generated tangents may also be totally wrong if the normal map used was not generated using Mikk TSpace method (which Blender uses).

# ObjectTemplate export guide

This section lists all the requirements needed for the finished model to become export-ready and usable in the game engine.

## The object hierarchy
- The root of the hierarchy must be an empty object, must have no parent and needs to be prefixed with the geometry type (`StaticMesh`, `BundledMesh` or `SkinnedMesh`) followed by an underscore and the name of the root ObjectTemplate. Each child of the root object must be an empty object corresponding to Geom (prefixed with `G<index>__`). Statics may also contain an empty child object which defines its anchor point (prefixed with `ANCHOR__`).
- Each child of the Geom object must be an object that corresponds to Lod (prefixed with `G<index>L<index>__`) containing mesh data. There must be at least one Lod.
- Lods should have their [origin set at center of the geometry](https://docs.blender.org/manual/en/latest/scene_layout/object/origin.html#set-origin). This optimizes bounding spheres and avoids frustum culling related bugs (objects disappearing at certain viewing angles).
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
├─G0__soldier
│ └─G0L0__soldier [m]
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
- Clicking on `Apply Material` changes some material settings, loads textures and builds a tree of Shader Nodes that try to mimic BF2 rendering. It's optional and does not affect export.
- Each LOD's mesh must have a minimum of 1 and a maximum of 5 UV layers assigned and each UV layer must be called `UV<index>`, where each one corresponds to the following texture maps:
    - For StaticMesh UV0 = Base, UV1 = Detail, UV2 = Dirt, UV3 (or UV2 if Dirt layer is not present) = Crack and the last one (always UV4) is the Lightmap UV, which can also be auto-generated when toggled in the export options.
    - For BundledMesh and SkinnedMesh there's only UV0 for all texture maps.
- Export requires one UV map to be chosen for tangent space calculation, this must be the same UV used to bake the normal map, for static meshes (which reuse textures) it should likely be UV1 (Detail Normal).

## Collision meshes
- Each object may contain collision mesh data. To add it, you must create an empty child object prefixed with `NONVIS__`. This new object should have a maximum of 4 child objects (suffixed with `_COL<index>`) containing collision mesh data, each corresponding to a specific collision type: Projectile = COL0, Vehicle = COL1, Soldier = COL2, AI (navmesh) = COL3. Collision meshes should only be added under the object's Lod0 hierarchies.
- Each COL can have an arbitrary number of materials assigned, no special material settings are required, object's material index-to-name mapping will be saved inside the `.con` file.
### Known Issues
- CollisionMesh exports to a slightly older file format version (9) than 3ds Max exporter (10). Latest file version contains some extra face adjacency info for drawing debug meshes which is disabled by default in-game anyway.

## Skinning (BundledMesh)
BF2 BundledMeshes support a basic method of skinning allowing one "bone" per vertex, where the "bone" is another object (geometry part). In other words, it enables "moving" some vertices from one object (geometry part) to another so that individual vertices that make up a face get split among different parts, which can be affected by the in-game physics differently and may cause some faces to stretch and deform. This technique is most commonly used for setting up tank tracks by splitting them up and "linking" track pieces to wheel objects. To achieve this in Blender create a new [Vertex Group](https://docs.blender.org/manual/en/latest/modeling/meshes/properties/vertex_groups/index.html) named **exactly** the same as the child object that the vertices are supposed to be transferred to and add them to the group. A single vertex must be assigned to **exactly one** vertex group, or you will get an export error. You can ensure this by using [Weights -> Limit Total](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#limit-total) in `Weight Paint Mode`.

## Animated UVs (BundledMesh)
To set up animated UVs go to `Edit Mode`, select specific parts (vertices/faces) of your mesh that should use UV animation and assign them to proper sets using the `Mesh -> BF2` menu, choosing Left/Right Tracks/Wheels Translation/Rotation. You can also select vertices/faces currently assigned to those sets using the `Select -> BF2` menu. Vertices assigned to the "wheel rotation" set will additionally require setting up the centre point of UV rotation for each wheel individually. Select all vertices, position the 2D cursor to the wheel centre in the UV Editing view, then select `Mesh -> BF2 -> Set Animated UV Rotation Center`. Repeat the process for all wheels.

## Skinning (SkinnedMesh)
In order to skin your model, you must import the BF2 skeleton into your scene. When skinning soldiers you will need two skeletons `1p_setup.ske` for 1P (Geom 0) and `3p_setup.ske` 3P (Geom 1). The first step is to switch to `Pose Mode` and pose the armature(s) to align it with your mesh(es) as best as possible. When you are done, make sure you apply this pose as the rest pose [Pose -> Apply -> Apply Pose As Rest Pose](https://docs.blender.org/manual/en/latest/animation/armatures/posing/editing/apply.html), then switch to `Object Mode` and for each Lod object go to `Modifiers` tab and [Add Modifier -> Deform -> Armature](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html), in modifier settings select 'Object' to point to the name of the imported skeleton. Now the hard part, you have to set vertex weights for each Lod, meaning how much each bone affects each vertex of the mesh. You could use automatic weights (which should be a good starting point) as follows:
  1. In `Object Mode` select the skeleton (armature object).
  2. In `Pose Mode` select all bones which are supposed to affect the mesh deformation.
  3. In `Object Mode` add the mesh object to the selection (left mouse click while holding `Shift`)
  4. In `Weight Paint Mode` click on [Weights -> Assign Automatic From Bones](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#assign-automatic-from-bone).

Bare in mind that to export properly, each vertex must have at most two weights (be assigned to a maximum of two vertex groups), and all those weights have to be normalized (add-up to one). You can limit the number of vertex weights in `Weight Paint Mode` using [Weights -> Limit Total](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#limit-total) option (make sure it is set to 2). You can normalize weights using [Weights -> Normalize All](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html#normalize-all) option. Also, make sure that `Auto Normalize` is enabled in [Weight Paint Tools Settings](https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/tool_settings/options.html) when skinning in `Weight Paint Mode`.

# Video Tutorials
- [Animation - rig setup, export, import and editing (by Ekiso)](https://youtu.be/xO1848HzetQ)
- [StaticMesh - hierarchy, materials and export (by Ason)](https://www.youtube.com/watch?v=H97o0d3zkoY)
- [BundledMesh - simple weapon export (by Krayt)](https://www.youtube.com/watch?v=crQRXm-4lxQ)
- [BundledMesh - tracked vehicle export (by Krayt)](https://www.youtube.com/watch?v=HYPFTYakv1M)

# Scripting
The add-on import/export functions can be used in python scripts to automate tasks, some examples below.

```python
import bpy
from os import path
from bl_ext.user_default.io_scene_bf2 import *

MOD_PATH = get_mod_dir(bpy.context)

SOLDIER = path.join(MOD_PATH, 'Objects/Soldiers/BA/Meshes/ba_light_soldier.skinnedmesh')
KITS = path.join(MOD_PATH, 'Objects/Kits/BA/Meshes/ba_kits.skinnedmesh')
WEAPON = path.join(MOD_PATH, 'Objects/Weapons/Handheld/m91carcano/Meshes/m91carcano.bundledmesh')
SKELETON_1P = path.join(MOD_PATH, 'Objects/Soldiers/Common/Animations/1p_setup.ske')
SKELETON_3P = path.join(MOD_PATH, 'Objects/Soldiers/Common/Animations/3p_setup.ske')
ANIM_3P_SOLDIER = path.join(MOD_PATH, 'Objects/Soldiers/Common/Animations/3P/3p_reload.baf')
ANIM_3P_WEAPON = path.join(MOD_PATH, 'Objects/Weapons/Handheld/m91carcano/Animations/3P/3p_m91carcano_reload.baf')
ANIM_1P = path.join(MOD_PATH, 'Objects/Weapons/Handheld/m91carcano/Animations/1P/1p_m91_reload.baf')
OBJ_TEMP_STATIC = path.join(MOD_PATH, 'Objects/StaticObjects/France/la_horgne/horgne_church/horgne_church.con')
OBJ_TEMP_VEHICLE = path.join(MOD_PATH, 'Objects/vehicles/land/DE/sdkfz251_d/sdkfz251_d.con')

# ---------- Import & export 3P animation ----------
ske = import_skeleton(bpy.context, SKELETON_3P)
IMPORT_OPTS = {'geom': 1, 'lod': 0, 'texture_path': MOD_PATH, 'geom_to_ske': {-1: ske}}
import_mesh(bpy.context, SOLDIER, **IMPORT_OPTS)
import_mesh(bpy.context, KITS, **IMPORT_OPTS)
import_mesh(bpy.context, WEAPON, **IMPORT_OPTS)
import_animation(bpy.context, ske, ANIM_3P_WEAPON)
import_animation(bpy.context, ske, ANIM_3P_SOLDIER)

export_animation(bpy.context, ske, 'export/3p_anim.baf')
# ---------- Import & export 1P animation ----------
ske = import_skeleton(bpy.context, SKELETON_1P)
IMPORT_OPTS = {'geom': 0, 'lod': 0, 'texture_path': MOD_PATH, 'geom_to_ske': {-1: ske}}
import_mesh(bpy.context, SOLDIER, **IMPORT_OPTS)
import_mesh(bpy.context, WEAPON, **IMPORT_OPTS)
import_animation(bpy.context, ske, ANIM_1P)

export_animation(bpy.context, ske, 'export/1p_anim.baf')
# ---------- Import & export static object ----------
obj_temp = import_object_template(bpy.context, OBJ_TEMP_STATIC, texture_path=MOD_PATH)
export_object_template(obj_temp, 'export/static.con', texture_path=MOD_PATH, tangent_uv_map='UV1')
# ---------- Import & export vehicle ----------
obj_temp = import_object_template(bpy.context, OBJ_TEMP_VEHICLE, texture_path=MOD_PATH)
export_object_template(obj_temp, 'export/vehicle.con', texture_path=MOD_PATH, tangent_uv_map='UV0')
```
