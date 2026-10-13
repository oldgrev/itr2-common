# Example map

A small test map for Into the Radius 2. It's a 40 m floor with walls around it, two walls inside, and a ramp up to a
platform. It has a PlayerStart, a Movable sun and sky light, and a return pad 30 m straight ahead of where you start
(a flat slab with a tall post), which takes you back to the Hub.

There are two ways to build it, and the same generator makes both:
- **The fork route** ([`build-itr2-map-fork.ps1`](build-itr2-map-fork.ps1)), the proper one. Cooked with the patched
  Meta fork ([`../engine/`](../engine/)), with three materials of our own: red inner walls, a grey checker floor and
  a green glowing return pad. The container carries those materials' shaders.
- **The stock route** ([`build-itr2-map.ps1`](build-itr2-map.ps1)), the quick kludge. Cooked with stock UE 5.5.4 from
  the Epic launcher, all `/Engine/BasicShapes/Cube` with `BasicShapeMaterial`, so it's all grey and the container
  only carries the map. Then patched with a 4-byte kludge so the game will load it.

The long explanation for both is in [`../map-making/guide.md`](../map-making/guide.md).

## Just want to try it?
[`prebuilt/`](prebuilt/) has the current test build of this map (2026-10-13): the three custom materials, strong blue fog
with a sky atmosphere and the four pillar pairs (ours on the left, the game's material on the right) at 10, 25, 50 and
100 m straight ahead of the start, and to the right of the start a coverage strip of things that use shader
permutations the plain room doesn't: our own static mesh, baked lighting, a masked material, instanced cubes, lit
translucent panes and three cubes that wobble through World Position Offset. All of it rendered in VR.

| File | Bytes | SHA-256 |
|---|---|---|
| `pakchunk100-ITR2Map_Test_P.utoc` | 3,626 | `a3ead5f95fdf12b679764b2922144e30717022102b480aec7850dc619be66963` |
| `pakchunk100-ITR2Map_Test_P.ucas` | 2,624,192 | `fe071c77a84cc1b633be1d4829435eb23ff6c8d8f13a47f836387f4d365f6b6b` |
| `pakchunk100-ITR2Map_Test_P.pak` | 339 | `ae7f446b81a9cbe8f7bb9fcbb93a58ef43fbd8e7f27c306b8d3e8ff3b9ccfeca` |

This one is a normal cook, with nothing swapped in afterwards: generated from source, lighting baked (Preview quality), cooked with the
patched fork and packaged with stock 5.5.4, all by the build script here. The one thing in it that the public generator
doesn't make is the three WPO cubes. I added those with a private Remote Control step that drives the editor over its
web API, which isn't in this repo. To get them yourself, do the manual editor step under "World Position Offset" below.

These are the exact files I tested in VR. Don't rename them: the game only loads the shaders in a mod container
named `pakchunk<N>-<something>_P`. The steps for UE4SS, the loader and the map are at the top of
[the main README](../README.MD#example-map-test).

## Building it yourself
You need Python 3, stock UE 5.5.4 (Epic launcher, also used for packaging on the fork route), and
[repak](https://github.com/trumank/repak/releases) (we used 0.2.3) to pull the game's config out. For the fork route,
the patched fork too (guide §4).

1. Copy this folder somewhere. It's a blueprint-only project called `IntoTheRadius2`, named after the game's project
   so the `/Game/...` paths line up. `Content/` gets created in step 3. If you want both routes, use a separate copy
   for each: they write to the same asset paths. For the fork copy, set `EngineAssociation` in the `.uproject` to your
   fork's folder (ours said `"C:\\ue55"`).
2. Make `Config\DefaultEngine.ini` from the game's own one:
   ```powershell
   .\extract-game-config.ps1 -Game "<game>" -Repak "<path>\repak.exe"
   ```
   `<game>` is the folder with `IntoTheRadius2\` in it. This unpacks `IntoTheRadius2/Config` from
   `pakchunk0-Windows.pak` and keeps the PC rendering, shader platform and navmesh settings
   ([`Scripts/make_engine_ini.py`](Scripts/make_engine_ini.py) lists exactly what). `Config\DefaultGame.ini` is
   already here; it's the game's packaging settings (IoStore, chunks, shared shader code, Oodle).
3. Build it.

   The fork route:
   ```powershell
   .\build-itr2-map-fork.ps1 -ForkEngine "C:\ue55" -StockEngine "C:\Program Files\Epic Games\UE_5.5"
   ```
   - runs [`Scripts/build_itr2_testmap.py`](Scripts/build_itr2_testmap.py) in the fork editor, headless, with
     `ITR2_CUSTOM_MATERIALS=1` so it makes the three materials too. `-FogPillars` also sets `ITR2_FOG_PILLARS=1` (strong
     fog and the pillar pairs) and `-Coverage` sets `ITR2_COVERAGE=1` (the coverage strip). The script's header says what
     each flag adds;
   - with `-BuildLighting` (and `-LightingQuality Preview|Medium|High|Production`, default Medium) bakes the map's
     lighting between generating and cooking, see "To get the prebuilt map" below;
   - cooks with the fork's `UnrealEditor-Cmd -run=Cook`, unversioned and compressed, like the game's own packages;
   - fixes the paths in the cook's `ChunkManifest` files, which the fork writes relative to its own engine folder;
   - stages, paks and makes the IoStore container with the **stock** 5.5.4 UAT (`-skipcook`). A source-built editor
     doesn't have the UnrealGame Shipping receipt UAT wants for that;
   - copies chunk 100 to `build\mod\pakchunk100-ITR2Map_Test_P.*`, and with `-Install -Game "<game>"` into
     `<game>\IntoTheRadius2\Content\Paks\~mods\`.

   The stock route:
   ```powershell
   .\build-itr2-map.ps1 -Engine "C:\Program Files\Epic Games\UE_5.5"
   ```
   - runs the same generator in stock 5.5.4, without the materials;
   - cooks and packages with `RunUAT BuildCookRun ... -iostore -VersionCookedContent`, uncompressed;
   - runs [`Scripts/patch_inplace.py`](Scripts/patch_inplace.py) on the `.ucas`, which changes the package's
     rendering version from 49 to 48 (the kludge);
   - copies the result to `build\mod\zzz_ITR2Map_Test_P.*`, and with `-Install -Game "<game>"` into `~mods`.

   `-PCoreMask` pins the editor, the cook and the shader workers to a CPU affinity mask and keeps them at Normal
   priority. The default, 0, doesn't pin anything. I used `0xFFFF` on an i7-13700K to keep them on the P-cores (logical
   processors 0-15); that mask is tuned for that CPU only.

   Only have one of the two builds in `~mods` at a time; they're the same map path. The first cook compiles the
   engine's global shaders for SM5 and SM6, which took us well over half an hour. After that it's about 12 minutes on
   stock.
4. Load it with the [loader](../loader-ue4ss/).

### To get the prebuilt map
1. Build UnrealLightmass in the fork once, because baking lighting needs it:
   `Engine\Build\BatchFiles\Build.bat UnrealLightmass Win64 Development`, run from the fork's folder.
2. Generate the map and stop: `.\build-itr2-map-fork.ps1 -FogPillars -Coverage -GenerateOnly`.
3. Open the map in the fork editor and do the WPO step below. Skip this if you don't want the wobbling cubes.
4. Bake, cook and package without generating again, which would throw the cubes away:
   `.\build-itr2-map-fork.ps1 -SkipGenerate -BuildLighting`. The lighting step runs
   `UnrealEditor-Cmd -run=resavepackages -buildlighting -MapsOnly` on the map and writes `L_ITR2Test_BuiltData`. If
   the save fails, delete a stale `L_ITR2Test_BuiltData.uasset` from the project's `Content` folder and run it again.

The generator puts `Used with Static Lighting` and `Used with Instanced Static Meshes` on every material
(`recompile_with_usage`). Without them the lightmapped and instanced meshes fall back to the grey grid once lighting is
built (guide §5). Set both on the WPO material too.

### World Position Offset
The generator can't make the wobbling cubes: the Python `MaterialProperty` enum doesn't expose World Position Offset, so
there's no way to wire it headlessly. It needs one manual step in the editor:
1. Make a material (I called it `M_ITR2_WPO`, in `/Game/ITR2Mods/TestMap/Materials`) with scalar parameters that have
   **Use Custom Primitive Data** ticked and indices 0, 1 and 2 (mine were speed, phase and amplitude), and feed them
   into World Position Offset. Mine was `sin(Time * Speed + Phase) * Amp` along X, plus a constant `sin(Time * 2) * 25`
   along Z, so a cube still moves if the primitive data reads zero.
2. Tick **Used with Static Lighting** and **Used with Instanced Static Meshes** on it.
3. Put three cubes in the coverage strip (mine were at x -100 / 100 / 300, y 1300, z 80, scale 0.8), set the mesh
   component's Mobility to Movable, and give them the material.
4. Set each cube's values as the component's **Custom Primitive Data Defaults** in the editor, or from a script with
   `SetDefaultCustomPrimitiveDataFloat(DataIndex, Value)`. Not `SetCustomPrimitiveDataFloat`: that only sets the
   runtime value, it isn't saved or cooked, and the cubes cook with zeroes. My first test did that and the cubes
   stood still.
5. Save the map. In VR, if the cubes only bob up and down, WPO works but the primitive data reads zero. If they also
   sway along X at different speeds, the data is arriving.

To turn it into your own map, change `FOLDER`, `MAP` and the layout in the generator (or build the map in the editor
by hand and pass `-SkipGenerate`). Keep a PrimaryAssetLabel with chunk 100 in your map's folder, and pass `-Map` and
`-Name` to the build script. On the fork route the name has to stay `pakchunk100-<something>_P`. Then add your map
to the loader's `config.lua`.

## What we tested (2026-10-12)
- Fork route: cooked with the patched fork, packaged with stock 5.5.4 (CL 40574608), in VR: the map loads from the
  Hub, the floor is a grey checker, the inner walls red and the pad green, and the pad takes you back to the Hub.
  Those were the earlier `prebuilt/` files. Retested in VR after the lighting port went into the fork (2026-10-12, 22:15): no strobing, and the lit walls and floor look like the game's own materials under the torch and in shade. Only these simple materials were tested, no textures, translucent or masked ones.
- Fog and shader audit (fork route): the generator now adds a mild ExponentialHeightFog and a SkyAtmosphere (the
  current `prebuilt/` map has this too). With `ITR2_FOG_PILLARS=1` (`-FogPillars` on the build script,
  and it needs the custom materials) it also makes strong fog and four pairs of pillars at 10, 25, 50 and 100 m, left
  our red material, right the game's `BasicShapeMaterial`. In VR (DX11 and DX12) the pairs fade
  identically with the audit fixes in [`../engine/`](../engine/). Not checked: the volumetric lightmap clamp (this
  map has no baked lighting), the eye index the light function atlas reads, and materials with textures, masks,
  translucency or lightmaps. See guide §5.
- Stock route: generating, cooking and packaging with stock 5.5.4. In VR, loaded with `OpenLevel`: you arrive on the
  floor, can walk around it and up the ramp, and the return pad takes you back to the Hub.
- Both build scripts are our working scripts with our own paths taken out and the install step folded in. The fork
  one also got a general fix for the manifest paths (ours only handled our folder layout), and the materials moved
  into the public generator behind `ITR2_CUSTOM_MATERIALS`. We checked the manifest fix against our cook's files,
  but neither script has been run end to end in this exact form. If one trips over something, that's why.
- `extract-game-config.ps1` and `make_engine_ini.py` are new for this repo. We checked that the ini it makes has the
  same settings as the one we cooked with, apart from a few mobile and PCG lines and the audio plugin settings,
  which don't matter for a PC map cook.

- Coverage (2026-10-13): baked lighting, our own static mesh, masked, ISM, WPO and lit translucent all rendered in
  VR, in the current `prebuilt/` files. The generator here (`-FogPillars -Coverage -BuildLighting`) makes all of it
  except the WPO cubes, which need the manual editor step above. The open oddity from the first coverage build is in
  guide §5 (the unlit pad also fell back to the grey grid until the usage flags were set). Not tested: landscape,
  skeletal meshes, decals.

What didn't work, so you don't try it again:
- **A container named `zzz_..._P` with our own materials.** It loads, but the materials draw as the engine's grid
  material, because the game finds a mod's shader library by the chunk number in the file name.
- **On stock 5.5.4, compressed containers.** `patch_inplace.py` can't find the version in a compressed `.ucas`, so
  it refuses. Repacking the container with `retoc pack-raw` instead gave containers the game never found.
- **On stock 5.5.4, unversioned cooks and material instances.** The game crashed in
  `SerializeUnversionedProperties` on a material instance. Stock 5.5.4 and the game don't have the same properties
  on some classes. The fork has the game's properties, so it should be fine there, but we haven't tried a material
  instance with it yet.
- **`-run=pythonscript`** for the generator, which is how ITR1's example did it. On 5.5 it crashes in
  `new_level`/`new_blank_map`, so the scripts run the full editor with `-nullrhi` instead.
