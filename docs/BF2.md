# BF2 glossary

- **Skeleton** - a set of bones with a defined hierarchy and transformations (position + rotation), exclusively used for skinning and animating SkinnedMeshes. Soldier skeletons (`1p_setup` and `3p_setup`) contain special `mesh` bones which are used for animating weapon parts (`mesh1` to `mesh16` for 1P and `mesh1` to `mesh8` for 3P). `3p_setup` also contains bones used for animating kit parts (`mesh9` to `mesh16`)
- **Visible mesh** - refers to one of the following:
  * **StaticMesh** - Used for static, non-movable objects (e.g. bridges, buildings) with baked lighting via light maps.
  * **BundledMesh** - Used for movable objects (e.g. vehicles, weapons)
  * **SkinnedMesh** - Used for deformable objects (e.g. soldiers, flags)
- **Geom** - "geometry". Each visible mesh type may define multiple sub-meshes refered to as geoms, each geom usually represents the same object viewed from a different perspective or in a different state e.g. for Soldiers/Weapons/Vehicles Geom0 and Geom1 refer to 1P and 3P meshes respectively. Statics and Vehicles may also have an extra Geom for their destroyed/wreck variant.
- **Lod** - "level of detail". Multiple Lods can be defined per Geom. Each Lod should be a simplified version of the previous one with Lod0 being the most detailed version. Most BF2 models are rather low-poly and modern GPUs are _fast_, so optimizing the poly count will usually have little to no impact on the performance. Reducing the number of materials on Lods should be prioritized instead to limit the number of draw calls and CPU load, which is the main bottleneck in the BF2 engine.
- **CollisionMesh** - Used for object collision calculations, cosists of three sub-meshes, each used for calculating collision between different object types (projectiles, vehicles and soldiers). Static objects may use additional sub-mesh for AI navmesh generation.
- **ObjectTemplate** - A blueprint for every in-game object, defines object type (e.g. `Bundle`, `PlayerControlObject`), its properties, visible mesh and collision mesh. ObjectTemplates (and objects) in BF2 are hierarchical, they may contain other ObjectTemplates as children (e.g. a root ObjectTemplate "tank" may define "turret" and "engine" as its children)
- **Geometry part** - A fragment of the BundledMesh's geom which can be independently transformed (moved/rotated). Each geometry part is usually bound to one specific child ObjectTemplate. Handheld weapons are one exception in which they can define multiple geometry parts but only a single ObjectTemplate (they are just used for animating).
- **Material** - defines a set of textures and shading properties. Every face and vertex is assigned to a material.
- **Alpha Mode** - transparency mode to use, one of the following:
  * `None` - No transparency
  * `Alpha Test` - parts of the material can be either fully transparent or fully opaque, no in between. It's cheap to compute.
  * `Alpha Blend` - Allows for semi-transparent materials. It's expensive to compute (may increase overdraw) and only supported by BundledMesh shaders.
- **Shader** - name of the shader (.fx) file to use for drawing the material, usually matches the visible mesh type name.
- **Technique** - a combination of names used as modifiers to enable or disable certain shader features when drawing the material. These names are harcoded in the game engine.
- **Animated UVs** - UV (texture) coordinates for BundledMeshes can be animated, BF2 uses this to fake tank track movement and/or road wheel rotation. Vertices that shall use this feature must be mapped to a specific UV transformation matrix depending on whether they belong to a tank track, wheel face or wheel outer rim and left/right side of the vehicle (total of 6 different combinations).

## Materials

A brief explanation of how the material system in BF2 works.

### StaticMesh
StaticMesh materials are designed to use [texture atlases](https://en.wikipedia.org/wiki/Texture_atlas) with four "layers" using up to six texture maps:
- `Base`: provides a basic uniform colour
- `Detail`: contains surface details and patterns like wood or bricks
- `Dirt`: used for adding dirt, stains or ambient occlusion
- `Crack`: used for adding cracks or other decals
- `NDetail`: Normal map for the Detail layer
- `NCrack`: Normal map for the Crack layer

NOTE: Only some combinations of the above texture layers are valid.

The `Base`, `Detail` `Dirt` layers are multiplied with each other, whereas the `Crack` layer is overlayed on top using its alpha channel; all of them combined produce the final diffuse color. Similarly, The `NDetail` and `NCrack` normal maps are mixed together based on the `Crack` layer's alpha channel. The gloss map is embedded in the alpha channel of the `Detail` map when Alpha Mode is set to `None` or the `NDetail` map otherwise.

### BundledMesh
BundledMesh materials may use up to three texture maps: `Diffuse Color`, `Normal` and `Wreck`. The `Wreck` map (if present) gets multiplied with the `Diffuse Color` when an object gets destroyed. The gloss map is embedded in the alpha channel of either the `Diffuse Color` or `Normal` map based on the `ColormapGloss` technique presence.

The following techniques are known to be supported by BundledMesh:
- `ColormapGloss` - if present, alpha channel of the `Diffuse Color` map is used as the `Gloss` map which scales the amount of specular reflections. If absent, the alpha channel is used for transparency.
- `Alpha_Test` - if present, transparency is calculated using RGB values of the `Diffuse Color` map rather than its alpha channel. Only parts of the material where the texture is fully black (RGB == 0,0,0) will be given full transparency. This technique is commonly combined with `ColormapGloss` allowing to spare the alpha channel for the `Gloss` map.
- `AnimatedUV` - enables dynamic transformation of texture coordinate, mostly used on tracked vehicles
- `EnvMap` - adds environment map based reflections (scaled using gloss map), mostly used on glass and stuff like that
- `Cockpit` - makes the lighting static, as the name implies used mostly for first person plane cockpits
- `NoHemiLight` - if present, hemimap will not be used for shading
- `Alpha_One` - special technique used on glow sprites, not sure what exactly is it for

### SkinnedMesh
SkinnedMesh materials may use up to two texture maps: `Diffuse Color` and `Normal`. The material may use either tangent space or object space normal maps with the latter one being more common (the engine differentiates them by `_b` or `_b_os` suffix). The gloss map is always embedded in the alpha channel of the `Normal` map.

The following techniques are known to be supported by SkinnedMesh:
- `Tangent` - must be defined if the material uses tangent space normal maps
- `Alpha_Test` - must be defined if the material uses alpha testing 
- `EnvMap` - not used in vBF2 but is known to be exploited by mods like Project Reality e.g. to make soldiers show up on thermals.
