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
[`prebuilt/`](prebuilt/) has the fork build of this map:

| File | Bytes | SHA-256 |
|---|---|---|
| `pakchunk100-ITR2Map_Test_P.utoc` | 1,549 | `d6459b7c51cdd0d343616f9e357a6be0a41d3d2cb69f468887e1d2b6ce8a9bf8` |
| `pakchunk100-ITR2Map_Test_P.ucas` | 324,944 | `c9a9c31fb98d1102e35e715121c684f2075cdc713ace60c492b9bc606d2cc9bc` |
| `pakchunk100-ITR2Map_Test_P.pak` | 339 | `ae7f446b81a9cbe8f7bb9fcbb93a58ef43fbd8e7f27c306b8d3e8ff3b9ccfeca` |

These are the exact files we tested in VR. Don't rename them: the game only loads the shaders in a mod container
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
     `ITR2_CUSTOM_MATERIALS=1` so it makes the three materials too;
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

   Only have one of the two builds in `~mods` at a time; they're the same map path. The first cook compiles the
   engine's global shaders for SM5 and SM6, which took us well over half an hour. After that it's about 12 minutes on
   stock.
4. Load it with the [loader](../loader-ue4ss/).

To turn it into your own map, change `FOLDER`, `MAP` and the layout in the generator (or build the map in the editor
by hand and pass `-SkipGenerate`). Keep a PrimaryAssetLabel with chunk 100 in your map's folder, and pass `-Map` and
`-Name` to the build script. On the fork route the name has to stay `pakchunk100-<something>_P`. Then add your map
to the loader's `config.lua`.

## What we tested (2026-10-12)
- Fork route: cooked with the patched fork, packaged with stock 5.5.4 (CL 40574608), in VR: the map loads from the
  Hub, the floor is a grey checker, the inner walls red and the pad green, and the pad takes you back to the Hub.
  Those are the `prebuilt/` files. Retested in VR after the lighting port went into the fork (2026-10-12, 22:15): no strobing, and the lit walls and floor look like the game's own materials under the torch and in shade. Only these simple materials were tested, no textures, translucent or masked ones.
- Fog and shader audit (fork route): the generator now adds a mild ExponentialHeightFog and a SkyAtmosphere (the
  `prebuilt/` map was made before that). With `ITR2_FOG_PILLARS=1` (set it in your shell before the build script,
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
