# Making maps for Into the Radius 2

This is how we got a custom map with our own materials into ITR2 and walked around it in VR. Most of what you need is
in this repo. The bits that aren't are Unreal Engine itself (stock 5.5.4 and Meta's fork), UE4SS, and repak.

There are two routes. The proper one is Meta's UE 5.5.4 fork with our patch on top: you build the editor yourself,
it cooks maps the way the game's own are cooked, and your own materials work. The quick one is stock UE 5.5.4 from
the Epic launcher plus a 4-byte patch to the cooked file, which I'll keep a kludge. That's only
good for maps made of engine meshes and engine materials, but you don't have to build an engine for it.

Where we say *tested* we've done it in game. *Untested* means written but never run, and *unexplored* means nobody
has tried it as far as we know.

I don't love this *we* phrasing but anywhere *we* is used, it's illustrating that some times in the assembly of this puzzle, I have no idea what command i need to run next or how exactly it's cooking a thing this time around. I know how I'd do it normally but things get to be in flux so much that I'm not closely following the latest cook commands and which folder or if it's decided to do it in a different subfolder setc. That said, these documents are to distil and reveal the puzzle for others and if they don't, Lucy will have some splainin to do.s

## 0. Where things are at (2026-10-12)
| You want | Status |
|---|---|
| A map with your own materials | Works with the patched fork (§4, §5), lit ones too. Tested in VR with simple materials only (§5). Compiled shaders audited against the game's, fog proven in VR, baked-lighting clamp not (§5) |
| A map from engine meshes and engine materials only | Works with either route. The stock route (§6) is quicker to set up |
| Material instances | Untested on the fork. On stock 5.5.4, don't: one crashed the game |
| The game's own materials and meshes in your map | Unexplored. Probably fine, if you can get copies at the right paths |
| Navmesh, AI, loot, gates | Unexplored |

The game is UE 5.5.4, but not Epic's: it's Meta's Oculus fork, tag `oculus-5.5.4-release-1.110.0-v78.0` (that's
what the exe's version resource says), with CM Games' own changes on top. It's packaged as IoStore
(`.utoc`/`.ucas` plus a small `.pak`), not encrypted and not signed.
That text grates me so hard because it's close to the ai trope of 'not x but y'
 
## 1. What you'll need
- Into the Radius 2 on PC. Our exe was dated 8 July 2026. If yours is newer, things may have moved; §4 has a check.
- Stock UE 5.5.4 from the Epic launcher, for either route. We had CL 40574608. On the fork route it's only used for
  packaging.
- For the fork route: access to Meta's fork on GitHub, VS 2022, and about 200 GB free (§4).
- Python 3.
- [repak](https://github.com/trumank/repak/releases) to get the game's config out (we used 0.2.3).
  [retoc](https://github.com/trumank/retoc/releases) (0.1.5) is handy for looking inside containers and for the
  shader check in §5, but you don't need it to build a map.
- UE4SS, a build newer than the 3.0.1 release, and our loader (§7).

## 2. Set up the project
1. Copy [`example-map/`](../example-map/) somewhere. It's a blueprint-only project called `IntoTheRadius2`. Keep
   that name, since the `/Game/...` paths have to line up with the game's. If you're going to use both routes, keep
   a separate copy for each. For the fork copy, set `EngineAssociation` in the `.uproject` to the fork's folder (ours
   was `"C:\\ue55"`).
2. Make the project's `DefaultEngine.ini` from the game's:
   ```powershell
   .\extract-game-config.ps1 -Game "<game>" -Repak "<path>\repak.exe"
   ```
   The game's configs are in the small `pakchunk0-Windows.pak`, not in the big utoc. The script pulls them out and
   keeps the PC side: forward shading, static lighting allowed, CSM shadows, instanced stereo, MSAA, Nanite, Lumen
   and virtual shadow maps off, the DX11 SM5 and DX12 SM6 shader formats, and the navmesh settings. It leaves out
   the Quest, online and OculusXR sections, and CM Games' own keys (`CM.*`), which neither engine knows.
3. `Config\DefaultGame.ini` is already set up like the game's packaging: `bUseIoStore=True`, `bUseZenStore=False`,
   chunks on, `bShareMaterialShaderCode=True`, Oodle Mermaid with 512 KB blocks.
4. The `.uproject` only enables the Python and editor scripting plugins. None of the game's plugins are needed for a
   map like the example.

## 3. Building the map
The easiest way to start is the example's generator,
[`example-map/Scripts/build_itr2_testmap.py`](../example-map/Scripts/build_itr2_testmap.py). It's short and worth
reading alongside this. You can run it from the editor (File, Execute Python Script) or let the build scripts run it
headless. With `ITR2_CUSTOM_MATERIALS=1` in the environment (the fork build script sets it) it also makes three
materials: a red DefaultLit, a checker DefaultLit and a green Unlit glow, all plain engine expressions.

On 5.5, the `-run=pythonscript` commandlet that ITR1's example used crashes as soon as the script makes a level. So
the build scripts start the full editor with `-nullrhi -ExecutePythonScript=`, which works.

A few rules we worked out:
- **Where it goes.** Put your map in its own folder, like `/Game/ITR2Mods/<Name>/L_<Name>`. Nothing in the game
  lives under `/Game/ITR2Mods`, so it can't clash.
- **Its own chunk.** Put a `PrimaryAssetLabel` in that folder with a chunk id of its own (the example uses 100),
  "label assets in my directory" on, and cook rule "always cook". The cook then writes your map, your materials and
  their shader library into their own `pakchunk100` container, and that's the one you ship. Everything else the cook
  makes (chunk 0, about 180 MB of engine content) stays behind; the game has its own copies.
- **Materials.** Engine materials work on both routes. Your own materials need the fork. Material instances are
  untested on the fork and crash on stock.
- **Lights.** Movable lights work. The example has a directional light at intensity 3 and a sky light at 1. We
  haven't tried a lighting build.
- **Start and exit.** Put a `PlayerStart` where people should arrive, and something visible for the return pad. The
  loader works from coordinates in its config, so note both down (§7). Put the pad somewhere you won't walk onto by
  accident.
- **Where it sits in the world.** With `OpenLevel` your map is the whole world, so anywhere is fine. The example's
  floor is centred on 0, 0.

## 4. The patched fork
The idea is the same as ITR1: build the same fork the game uses, add CM's changes so the editor writes what the game
expects, and cook with that.

**Getting the source.** The fork is at `github.com/Oculus-VR/UnrealEngine`. You'll only see it with a GitHub account
linked to an Epic account (on unrealengine.com: account, Apps and Accounts, GitHub, then accept the invite to the
EpicGames org). The tag that matches the game is `oculus-5.5.4-release-1.110.0-v78.0`. If the link 404s, it's an
access problem.

**Toolchain.** VS 2022 with the C++ workload. We have 17.14 (MSVC 14.44), plus MSVC 14.38 installed as a fallback
because that's the version UE 5.5 was validated against.

You'll use [`tools/hashpatch.py`](../tools/hashpatch.py) and
[`engine/itr2-cm-compat.hashpatch.json`](../engine/itr2-cm-compat.hashpatch.json).

```bat
:: 1. Get the source at the tag. Keep the path short.
git clone --branch oculus-5.5.4-release-1.110.0-v78.0 --depth 1 https://github.com/Oculus-VR/UnrealEngine.git C:\ue55
cd /d C:\ue55

:: 2. Apply the CM compatibility patch. It checks every file first and won't apply twice.
python <itr2-common>\tools\hashpatch.py apply <itr2-common>\engine\itr2-cm-compat.hashpatch.json C:\ue55

:: 3. Build
Setup.bat
GenerateProjectFiles.bat
Engine\Build\BatchFiles\Build.bat UnrealEditor Win64 Development -WaitMutex
Engine\Build\BatchFiles\Build.bat ShaderCompileWorker Win64 Development -WaitMutex
```
Unlike ITR1's 4.27 fork, `Setup.bat` worked on this tag as it is, so there's no dependency list to fix.

**What the patch changes** (66 files, 7 of them new):
- **The rendering version.** It adds an entry before `DeprecatedHighResSourceMesh`, so the latest is 50 like the
  game, and `FPrecomputedVisibilityHandler` reads and writes the 61 extra bytes (an array of visibility chunks, a
  box and two numbers) from version 49 up. We don't know CM's names for any of this, so they're ours.
- **Properties.** 44 properties and 7 classes CM added to engine types, in the game's order, and `FLightingChannels`
  back to two channels. They're stubs: they exist so things load and save the same as the game, but they don't do
  anything in our editor. The new material expressions (`PlatformSwitch`, `ResponsiveAA`, the sky atmosphere ones)
  pass their input through or return zero. What they really do in CM's renderer, we don't know.
- **Shader layouts.** CM's 40 changes to the uniform buffers material shaders use (§8), in `SceneView.h`,
  `PrimitiveUniformShaderParameters`, `SceneData.ush`, `SceneTypes.h`, `SceneTexturesConfig.h`,
  `BasePassRendering.h`, `SceneRendering.h` and the landscape buffer. The editor fills the new members with zeros or
  dummy textures. That's fine, because only the layout has to match: in game, the game's renderer fills them in.
- **Lighting.** CM's changes to the base-pass, forward and spot light shaders, the light-function atlas for opaque
  materials and the sun fade (§5), with fills for the new constants in the C++ so the editor viewport lights things.
- **Instance transforms.** `bSupportsSceneDataCompressedTransforms=false` for PCD3D_SM5, PCD3D_SM6 and PCD3D_ES3_1 in
  `Engine\Config\Windows\DataDrivenPlatformInfo.ini`. The game ships that file with `false`, the fork has `true`, and
  that's the only real difference between the two. It decides whether vertex shaders read each object's transform
  packed (two float4s) or as three plain rows. The game writes plain rows, so with `true` our vertex shaders read
  garbage, every triangle lands in the wrong place, and the materials come out pitch black, unlit ones included. The
  editor reads this file at startup and the setting is part of the shader cache key, so after changing it the next
  cook recompiles everything by itself. It's engine config; the project can't override it.

**Why a hashpatch instead of a normal patch?** Same reason as ITR1. A normal patch includes engine lines, and Epic's
EULA limits how engine code can be shared publicly. This patch points at the lines it replaces by line number and
hash, and at lines it reuses by where they are in your copy. The only text in it is what we wrote. Applying it to a
clean checkout of the tag gave the same files as the fork we cooked the example with. That's our reading of the
EULA, not legal advice.

**Checking your build.** Once it's built, you can compare its shader layouts with the game's
(`pip install pefile capstone comtypes` first):
```bat
cd <itr2-common>\tools
python ub_extract_stock.py fork.json C:\ue55\Engine\Binaries\Win64\UnrealEditor-Engine.dll C:\ue55\Engine\Binaries\Win64\UnrealEditor-Renderer.dll C:\ue55\Engine\Binaries\Win64\UnrealEditor-RenderCore.dll C:\ue55\Engine\Binaries\Win64\UnrealEditor-Landscape.dll
python ub_compare.py ..\data\ub\game-itr2-5.5.4.json fork.json diff-fork.json
```
The material-shader buffers (`View`, `InstancedView`, `Primitive`, `ForwardLightData`, `SceneTextures`, `BasePass`,
the landscape one) should show no differences. Ours didn't. Other buffers will still differ; those belong to the
game's global shaders, which it ships itself. If the game updates, `ub_extract_pdb.py` makes a new game file from
the exe (see [`tools/README.md`](../tools/README.md)).

## 5. Cook and package with the fork
```powershell
.\build-itr2-map-fork.ps1 -ForkEngine "C:\ue55" -StockEngine "C:\Program Files\Epic Games\UE_5.5" -Install -Game "<game>"
```
[`example-map/build-itr2-map-fork.ps1`](../example-map/build-itr2-map-fork.ps1) does this:
1. Generates the map and its materials in the fork editor (skip with `-SkipGenerate` if you built it by hand).
2. Cooks with the fork: `UnrealEditor-Cmd <project> -run=Cook -TargetPlatform=Windows -Map=<your map> -unversioned
   -iostore -compressed -manifests`. Unversioned and compressed, like the game's own packages. With the fork's
   properties and rendering version matching the game's, there's nothing to work around any more.
3. Fixes the paths in `Saved\Cooked\Windows\IntoTheRadius2\Metadata\ChunkManifest\pakchunk*.txt`. The cook writes
   them relative to the engine folder that did the cook (`..\itr2proj\...` from our `C:\ue55`), and the stock UAT in
   the next step reads them relative to its own folder (`..\..\..\itr2proj\...` from `C:\Program Files\Epic
   Games\UE_5.5`). Left alone, UAT can't find your files.
4. Stages, paks and builds the IoStore container with the **stock** 5.5.4 UAT: `RunUAT BuildCookRun ... -skipcook
   -stage -pak -iostore -compressed -unversioned`. Stock UAT because a source-built editor has no UnrealGame Shipping
   receipt, and staging a Shipping build of a blueprint-only project wants one. With `-skipcook` it only packages
   what the fork cooked.
5. Copies `pakchunk100-Windows.utoc/.ucas/.pak` to `build\mod\pakchunk100-ITR2Map_Test_P.*`. With `-Install`, it
   also copies them to `<game>\IntoTheRadius2\Content\Paks\~mods\`. Restart the game whenever they change.

**The container's name matters.** It must be `pakchunk<N>-<anything>_P`, with `<N>` your chunk id. The engine opens
a mod container's shader library by the chunk number in the file name. Under any other name (our first try was
`zzz_ITR2Map_Test_P`) the map loads but every one of your materials falls back to the grey and white grid material.

The first cook compiles the engine's global shaders for SM5 and SM6, which takes a long time. The container gets
shader libraries for both (`ShaderArchive-IntoTheRadius2_Chunk100-PCD3D_SM5` and `-SM6`). We didn't check which RHI
the game ran on in our test; its default is DX11, so SM5.

**Checking the shaders.** If your materials come out black, check that the `DataDrivenPlatformInfo.ini` change was in
the editor that cooked them (§4). You can see it in the container:
```bat
retoc to-legacy --no-assets --no-script-objects --no-compres-shaders --version UE5_5 build\mod\pakchunk100-ITR2Map_Test_P.utoc legacy
python <itr2-common>\tools\dxbc_scan.py legacy\IntoTheRadius2\Content\ShaderArchive-IntoTheRadius2_Chunk100-PCD3D_SM5-PCD3D_SM5.ushaderbytecode scan
python <itr2-common>\tools\xform_check.py legacy\IntoTheRadius2\Content\ShaderArchive-IntoTheRadius2_Chunk100-PCD3D_SM5-PCD3D_SM5.ushaderbytecode scan\index.tsv
```
`xform_check.py` should count 0 compressed. The game's own shaders are all uncompressed. (If retoc puts the archive
somewhere else, look for the `.ushaderbytecode` under `legacy`.)

### Tested
On 2026-10-12, in VR: the fork-cooked example with its three materials loaded from the Hub, the floor showed the grey
checker, the inner walls were red, the return pad glowed green, and the pad took us back to the Hub. The files are in
[`example-map/prebuilt/`](../example-map/prebuilt/).

### Lit materials
CM Games changed the lighting shader code, and an unpatched fork has Meta's. The layouts match (that's §8), but the
shaders do different things with the lights. Without the port, our lit materials (the red walls and the checker floor)
were close to black in shade and only weakly lit by the torch, while the game's cooked `BasicShapeMaterial` next to
them was lit normally. Unlit materials were always fine.

The patch in `engine/` now ports CM's lighting shader changes into the fork. That was the indirect light and sun fill
terms in the base pass, the directional light attenuation, the spot cone cutoff and the reflection capture guard. It
also needed the light-function atlas set up the way the game has it (stride 9, per-eye matrices; with our first try
of stride 5 the lit materials strobed under the torch), plus fill values for the new constants so the editor viewport
still lights things. Tested in VR on 2026-10-12: no strobing, and the torch and shade look like the game's own
materials. That was only the example's simple materials. Textures, translucent and masked materials haven't been tried,
so expect surprises there. The fill and ambient terms were worked out from the game's compiled shaders, so they're a
close match, not CM's source.

**Audit.** Afterwards I compared all 19 compiled shaders of the example (SM5 and SM6) with the game's equivalents:
same resource slots and signatures, and the instruction streams with registers and constants blanked. Five real
differences were left, and they're fixed in the patch (marked `shader-audit` in the shaders):
- in the base-pass vertex shader, the height fog's exclusion distance (we divided by the cosine to the view
  direction, the game doesn't), its directional inscattering condition, and the clip position the aerial perspective
  looks up (the game recomputes it from the primary view);
- the fill-sun weight takes the luminance before the threshold curve, not after;
- the volumetric lightmap indirection lookup is clamped.

Each was proven offline: a single shader recompiled with the fix matches the game's bytecode. The three fog ones were
also checked in VR with pillar pairs, one with our red material and one with the game's `BasicShapeMaterial`, at
10 to 100 m in strong fog: they fade identically, in DX11 and DX12. The example generator can make that scene
(`ITR2_FOG_PILLARS=1`, see the example's README).

Not checked in game: the volumetric lightmap clamp (it needs baked lighting, which the example never has), and where
the light function atlas gets its eye index from (we read `StereoPassIndex`, the game takes it from an interpolant;
that's the same only if the game fills it with the eye index, which I couldn't check from the shaders). The audit only
covered the example's materials, so textured, masked, translucent and lightmapped ones are still unaudited.

## 6. The quick kludge: stock 5.5.4
For a map that only uses engine meshes and engine materials, you can skip building the fork. This is how we got the
first map in, and it still works.

```powershell
.\build-itr2-map.ps1 -Engine "C:\Program Files\Epic Games\UE_5.5" -Install -Game "<game>"
```
[`example-map/build-itr2-map.ps1`](../example-map/build-itr2-map.ps1) does this:
1. Generates the map, without the materials (skip with `-SkipGenerate` if you built it by hand).
2. Cooks and packages it:
   `RunUAT BuildCookRun -project=... -platform=Win64 -clientconfig=Shipping -cook -map=<your map> -skipbuild -stage -pak -iostore -VersionCookedContent`.
   Two things matter here:
   - `-VersionCookedContent`, not `-unversioned`. The game's own packages are unversioned, which means properties are
     stored by position in the class with no names. CM Games added properties to some engine classes, so stock 5.5.4
     and the game disagree about those positions, and the game reads garbage. A versioned cook writes each
     property's name, so the game matches them up by name and skips what it doesn't know.
   - Uncompressed. The project's ini says `bCompressed=True` and UAT uses that even if you don't pass `-compressed`,
     so the script flips it off for the run and back afterwards. It has to be uncompressed for the next step.
3. Copies `pakchunk100-Windows.utoc/.ucas/.pak` from the staged output to `build\mod\zzz_ITR2Map_Test_P.*`. The name
   doesn't matter here, because there are no shaders in it.
4. Applies the kludge (below).
5. With `-Install`, copies the three files to `<game>\IntoTheRadius2\Content\Paks\~mods\`.

Don't have this and the fork build of the same map in `~mods` at the same time.

The first run compiles the engine's global shaders for SM5 and SM6, which took us well over half an hour. After that
it was about 12 minutes.

### The kludge
CM Games added an entry to the engine's list of rendering versions (`FRenderingObjectVersion`), at position 49. In
the game, a level saved with rendering version 49 or later has 61 more bytes of precomputed visibility data after
the normal stuff (`FPrecomputedVisibilityHandler`). Stock 5.5.4 stamps everything it saves with rendering version 49,
because that's its latest, but doesn't write those bytes. So the game reads 61 bytes past the end of our level and
falls over: "Serial size mismatch 398 vs 459" on `PersistentLevel`.

[`patch_inplace.py`](../example-map/Scripts/patch_inplace.py) finds the rendering version entry in the container
and changes 49 to 48. The game then skips CM's extra read, and nothing else in 5.5.4 depends on 49, so the level
reads exactly as stock wrote it. It's a 4-byte edit, the file stays the same size, so nothing else in the container
needs fixing. It only works on an uncompressed container, and it checks there's exactly one entry and that it says
49 before changing anything.

It's a kludge because it lies about what made the file. It's fine for a map that only has what stock 5.5.4 knows how
to write, and it'll stay fine until the game changes something else under the same version. The fork knows about
CM's entry, so it doesn't need this.

How we found it: we listed the custom versions the game registers (from the exe and its PDB) and compared them with
what the package says. Every one matched stock except rendering, 50 in the game against 49 in stock. The visibility
handler turned out to be the only code in the game that checks for 49 or 50.

### Tested
We built the example this way on 2026-10-12. In VR, from the Hub, the loader travelled to the map, we stood on the
floor at the start, walked around, and the return pad took us back to the Hub.

## 7. Getting into the map
The game's own travel works from level tags in its data, and a custom map doesn't have one, so something has to send
you there. We use a UE4SS Lua script, [`loader-ue4ss/`](../loader-ue4ss/). Its README covers installing and the
settings. In short:
- UE4SS goes in `<game>\IntoTheRadius2\Binaries\Win64\` (`dwmapi.dll` plus the `ue4ss` folder), and the loader in
  `ue4ss\Mods\`. You need a UE4SS build newer than the 3.0.1 release; we used an experimental one.
- In its `config.lua`, each map has a level path, a start position and a return pad position, in map coordinates.
- When you get to the Hub it waits 10 s, saves your position, and calls `GameplayStatics::OpenLevel` with your map.
  On the map it teleports you to the start. On the pad it opens the Hub again and puts you back where you were.

If you want to write your own loader, that's all it does. A few things we learned on the way:
- **A map that fails to load crashes the game**, and the crash doesn't tell you why. When `OpenLevel`'s load fails,
  the engine calls the game's `URadiusGameInstance::OnPostLoadMap` with no world, and it doesn't check. The shipping
  game has logging compiled out, so there's no "failed to load package" anywhere. If you crash right after the travel,
  read that as "my map didn't load" and look at the cook (and on the stock route, the kludge).
- **Streaming the map in next to the Hub** (`LevelStreamingDynamic::LoadLevelInstance`), which is how ITR1's loader
  works, doesn't work yet. The UE4SS 3.0.1 release can't make that call from Lua at all (an out-parameter bug, fixed
  in later builds, RE-UE4SS #1454). With a fixed build the call goes through, but the game says the package doesn't
  exist, for the same container `OpenLevel` loads. We don't know why. It'd be the nicer way if someone works it out:
  no loading screen, and the Hub stays loaded.
- **`OpenLevel` back to the Hub isn't the game's own travel.** It worked, but we haven't checked whether everything
  in the Hub is exactly as the game would have it.

## 8. Why stock 5.5.4 isn't enough
There are four places where the game and stock 5.5.4 don't agree. We found them by comparing the game's exe (its PDB
ships with it, which helps a lot), its `.usmap` and its config with the engine. The fork patch (§4) covers all four.

1. **The rendering version** (§6). On stock, the kludge gets around it.
2. **Properties.** CM Games added 44 properties to engine classes and structs that a normal map or material uses
   (`AActor`, `USceneComponent`, `UPrimitiveComponent`, `UMaterial`, `FMaterialInstanceBasePropertyOverrides`,
   `FPostProcessSettings`, `UDirectionalLightComponent` and so on), removed one (`FLightingChannels` has two channels
   in the game, not three), and has 7 classes the engine doesn't (`EnvironmentMaskActor`/`Component` and some
   material expressions). The game's packages are unversioned, so the property order is the file format, and
   anything stock writes unversioned for those classes is read wrong. That's the `SerializeUnversionedProperties`
   crash we got with a material instance. Versioned cooks get around it for plain actors and components on stock.
3. **Shader layouts.** Like ITR1, the game's shaders read the camera, the object, the lights and so on from blocks of
   memory ("uniform buffers") at fixed offsets, and CM changed some of them. We pulled the game's layouts out of
   the exe ([`data/ub/`](../data/ub/)) and compared them with stock and with the Meta fork:
   - 20 uniform buffers differ from stock, and 3 only exist in the game;
   - of the 50 differences in buffers that material shaders use, 9 are already in the Meta fork, 40 are CM's, and
     there's 1 member the fork has that the game dropped;
   - CM's are mostly 15 extra constants in `View` (and `InstancedView`), 3 environment-mask bindings in `View`, 4
     extra float4s of indirect lighting per object (custom primitive data goes from 9 float4s to 5 and moves to slot
     38; the per-object stride stays 43), plus one or two members in `ForwardLightData`, `SceneTextures`, `BasePass`
     and the landscape buffer.

   A shader compiled against the wrong layout reads the wrong memory.
4. **Instance transforms.** The `DataDrivenPlatformInfo.ini` setting from §4. Same effect: the shader reads the
   right memory in the wrong format.

Engine materials and the game's materials don't care about 3 and 4, because the game already has compiled shaders
for those. Your own materials do, which is why they need the fork.

## 9. What works and what doesn't
| Feature | Status |
|---|---|
| Geometry and collision from engine meshes | Works, both routes |
| Engine materials | Works, both routes |
| Your own materials | Work with the fork, lit ones too (the patch has CM's lighting changes, §5). Only simple ones tested in VR: constants and a UV checker, no textures, translucency or masked. Shader audit and fog check: §5 |
| Movable lights | Work |
| Getting in and back out | Works with the loader and `OpenLevel` |
| Material instances | Crashed with stock 5.5.4. Untested on the fork |
| Textures, translucent materials, decals, landscapes | Untested |
| The game's own meshes and materials | Unexplored. The game has them cooked, so referencing them at the same path should work as it did in ITR1, but you'd need source copies to place them, and there's no SDK for ITR2 we know of |
| Baked lighting | Unexplored. One shader fix for it (volumetric lightmap clamp, §5) has never been seen in game |
| Navmesh, AI spawning, loot | Unexplored. The game's areas have navigation in their own sublevels |
| Streaming the map in next to the Hub | Doesn't work yet (§7) |
| Gates, travel, the map screen, missions, saves | Not available. The game's travel uses level tags from its own data |

## 10. When things go wrong
- Crash reports end up in `%LOCALAPPDATA%\IntoTheRadius2\Saved\Crashes\` (`CrashContext.runtime-xml` plus a
  minidump). The shipping game doesn't write a useful log.
- A crash right after the loader says `travel issued` is the game's way of saying the map didn't load (§7).
- Your materials are the grey and white grid: the container isn't named `pakchunk<N>-<anything>_P` (§5).
- Your materials are black, unlit ones too: the `DataDrivenPlatformInfo.ini` change wasn't there when you cooked (§4,
  and the check in §5).
- Your lit materials are very dark in shade or strobe under the torch: the fork doesn't have the lighting changes from
  the patch (§5).
- "Serial size mismatch" on `PersistentLevel`, on the stock route: the kludge didn't happen. Check that the
  container was built uncompressed and `patch_inplace.py` said `49 -> 48`.
- A crash in `SerializeUnversionedProperties`: on stock, something was cooked unversioned, or the map has something
  whose properties differ between stock and the game, like a material instance. On the fork, check the patch went on
  cleanly and the game hasn't updated.
- If the loader never logs anything, check that UE4SS started (`UE4SS.log` next to `UE4SS.dll`) and that the mod is
  listed in `mods.txt` or has `enabled.txt`.

### Things that tripped us up
| What happened | Why | What to do |
|---|---|---|
| The generator crashes in `new_level`/`new_blank_map` | The `-run=pythonscript` commandlet doesn't work for that on 5.5 | Run the full editor with `-nullrhi -ExecutePythonScript=` (the build scripts do) |
| The fork's UAT won't stage a Shipping build | A source-built editor has no UnrealGame Shipping receipt | Cook with the fork, package with stock UAT and `-skipcook` |
| Stock UAT can't find the fork's cooked files | The ChunkManifest paths are relative to the engine that cooked | The fork build script rewrites them |
| Our materials drew as the grid material | The container was called `zzz_..._P` | Call it `pakchunk100-..._P` |
| Our materials, even the unlit one, drew pitch black | The fork compiled shaders for packed instance transforms, the game writes plain ones | `bSupportsSceneDataCompressedTransforms=false` (in the engine patch) |
| The game crashes in `SerializeUnversionedProperties` <- `UMaterialInstance::Serialize` | Stock 5.5.4, unversioned cook, and CM added properties to engine classes | The fork, or on stock: `-VersionCookedContent` and no material instances |
| "Serial size mismatch 398 vs 459" on the level | CM's rendering version entry (§6) | The fork, or on stock: the kludge |
| The map never loads after patching a compressed container | Our first patcher repacked it with `retoc pack-raw`, and the game never finds repacked containers. We don't know why | On stock: build uncompressed and patch in place |
| The build was compressed even without `-compressed` | UAT takes `bCompressed=True` from the project ini | The stock build script flips it for the run |
| The game crashes in `URadiusGameInstance::OnPostLoadMap` | Any failed map load does that | Treat it as "the map didn't load" |
| UE4SS 3.0.1 rejects the `LoadLevelInstance` call | An out-parameter that isn't last shifts the arguments after it | A newer UE4SS. Or use `OpenLevel` |
| `LoadLevelInstance` says the package doesn't exist | Unknown | `OpenLevel` |
| `/Game/...` arguments turn into `C:/Program Files/Git/Game/...` | Git Bash rewrites anything that looks like a path | Use PowerShell or cmd, or set `MSYS_NO_PATHCONV=1` |

## What's in the repo
| Path | What |
|---|---|
| [`example-map/`](../example-map/) | Project skeleton, the map generator, config extraction, both build scripts, the kludge, the prebuilt fork build |
| [`loader-ue4ss/`](../loader-ue4ss/) | The UE4SS loader |
| [`engine/`](../engine/) | The CM compatibility patch for the Meta fork |
| [`tools/`](../tools/) | `hashpatch.py`, plus the layout and shader checks from §4 and §5 |
| [`data/`](../data/) | The game's shader layouts, for the §4 check |
