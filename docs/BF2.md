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
- **Material** - defines how the surface appears and interacts with light, every face and vertex is assigned to a material. Each BF2 material consist of the following:
  - **Texture Maps** - a list of file paths to textures in [DDS](https://en.wikipedia.org/wiki/DirectDraw_Surface) format
  - **Alpha Mode** -  used to control transparency related [Render States](https://learn.microsoft.com/en-us/windows/win32/direct3d9/render-states), one of the following:
    * `None` - No transparency
    * `Alpha Test` - parts of the material can be either fully transparent or fully opaque, no in-between. It's cheap to compute.
    * `Alpha Blend` - Allows for semi-transparent materials. It's expensive to compute (may increase overdraw).
  - **Shader** - name of the shader (.fx) file to use for drawing the material, usually matches the visible mesh type name.
  - **Technique** - a combination of modifiers that enable or disable certain shader features when drawing the material. These modifiers are names harcoded in the game engine and are shader type specific.
- **Animated UVs** - UV (texture) coordinates for BundledMeshes can be animated, BF2 uses this to fake tank track movement and/or road wheel rotation. Vertices that shall use this feature must be mapped to a specific UV transformation matrix depending on whether they belong to a tank track, wheel face or wheel outer rim and left/right side of the vehicle (total of 6 different combinations).
- **Opacity map** - a grayscale image that controls the opacity, a pixel value of 1 makes the surface fully opaque. For optimization this map is always stored in the alpha channel of some other texture map (see [Materials](#materials) for details)
- **Gloss map** - a grayscale image that scales the amount of [specular reflections](https://en.wikipedia.org/wiki/Specular_reflection), a pixel value of 1 applies maximum glossiness to the surface. For optimization this map is always stored in the alpha channel of some other texture map (see [Materials](#materials) for details)

## Materials

An explanation of the BF2's material system. It is generally a huge mess full of inconsistencies so bear with me. Remember that anything described in this section refers to vanilla game as shaders can be modified and to some degree change how all of this works.

### StaticMesh
StaticMesh materials are designed to use [texture atlases](https://en.wikipedia.org/wiki/Texture_atlas) with four "layers" using up to six texture maps:
- `Base`: provides a basic uniform colour
- `Detail`: contains surface details and patterns like wood or bricks
- `Dirt`: used for adding dirt, stains or ambient occlusion
- `Crack`: used for adding cracks or other decals
- `NDetail`: Normal map for the Detail layer
- `NCrack`: Normal map for the Crack layer

NOTE: Only some combinations of the above texture layers are valid.

The `Base`, `Detail` and `Dirt` layers are multiplied with each other, whereas the `Crack` layer is overlayed on top; all of them combined produce the final diffuse color. Similarly, The `NDetail` and `NCrack` normal maps are mixed together based on the `Crack` layer's alpha channel.

StaticMesh only supports `Alpha Testing` render state for transparency. If `Alpha Testing` is used, the opacity map is sored in the `Detail` map's alpha channel and the gloss map is then stored in the `NDetail` map's alpha channel. If `Alpha Testing` is not used, the gloss map is stored int the `Detail` map's alpha channel.

### BundledMesh
BundledMesh materials may use up to three texture maps: `Diffuse Color`, `Normal` and `Wreck`. The `Wreck` map (if present) gets multiplied with the `Diffuse Color` and it's mostly used in Geom2 materials on vehicles. BundledMesh supports both `Alpha Testing` and `Alpha Blending` render states for transparency. The opacity map is always stored in the alpha channel of the `Diffuse Color`, the location of the gloss map however varies based on the technique used.

The following techniques are known to be supported by BundledMesh shader:
- `ColormapGloss` - if present, repurposes the alpha channel of the `Diffuse Color` map to be used as the gloss map instead of the opacity map. Effectively this makes the object fully opaque. If absent, the gloss map is taken from the `Normal` map's alpha channel if the map is present.
- `Alpha_Test` - by itself this technique has zero effect, but if combined with `ColormapGloss` it makes parts of the surface where the `Diffuse Color` is black (RGB == 0,0,0) fully transparent. It's used mainly when you want both transparency and gloss map but there's no `Normal` map present that could store it.
- `AnimatedUV` - enables dynamic transformation of texture coordinates, mostly used on tracked vehicles.
- `EnvMap` - adds environment map based reflections (scaled using gloss map), mostly used on glass and stuff like that.
- `Cockpit` - makes the lighting static, as the name implies used mostly for first person plane cockpits.
- `NoHemiLight` - if present, hemimap will not be used for shading.
- `Alpha_One` - special technique used on glow sprites, not sure what exactly is it for.

NOTE: A common misconception with BundledMesh materials is that you are required to have `Alpha` or `Alpha_Test` in your technique in order for `Alpha Blending` or `Alpha Testing` render states to work, but this is not true (it's just a quirk specific to the 3ds max mesh exporter).

### SkinnedMesh
SkinnedMesh materials may use up to two texture maps: `Diffuse Color` and `Normal`. The material may use either tangent space or object space normal maps with the latter one being more common (the engine differentiates them by `_b` or `_b_os` suffix). The gloss map is always embedded in the alpha channel of the `Normal` map.

The following techniques are known to be supported by SkinnedMesh shader:
- `Tangent` - must be defined if the material uses tangent space normal maps
- `Alpha_Test` - must be defined if the material should use `Alpha Testing` render state
- `EnvMap` - not used in vBF2 but is known to be exploited by mods like Project Reality e.g. to make soldiers show up on thermals.
