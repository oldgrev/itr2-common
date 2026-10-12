# itr2-common

Bits and pieces for modding **Into the Radius 2** (PC VR). Mostly about getting custom maps into the game, plus the
stuff needed along the way. It's the ITR2 counterpart of [itr-common](https://github.com/oldgrev/itr-common), which
does the same for ITR1, so if you've been through that one this should look familiar.

State as of 2026-10-12: maps with your own materials work, tested in VR. You need a patched build of Meta's UE 5.5.4
fork to make them (the proper route). Lit materials work too now: CM Games changed the lighting shader code, and the
patch ports those changes into the fork. In VR there's no strobing and the lit walls look like the game's own under the
torch and in shade. That was tested on the example map's simple materials only (constants and a checker); textures,
translucent and masked materials haven't been tried (details in the guide, §5).
I also audited the example's 19 compiled shaders against the game's own and fixed the five differences that turned up
(height fog, aerial perspective, fill-sun luminance, volumetric lightmap clamp). The fog ones are checked in VR; the
lightmap clamp needs baked lighting and hasn't been seen in game, and nothing beyond the simple materials has been
audited (details in the guide, §5).
If your map only uses engine meshes and engine materials there's also a quick route with stock UE 5.5.4 and a small
patch to the cooked file, a kludge, which was tested in VR too.

## Example map test
1. **UE4SS:** you need a build newer than the 3.0.1 release. I used an experimental build from
   https://github.com/UE4SS-RE/RE-UE4SS/releases (its log says `v3.0.1 Beta #0 - Git SHA #5e627997`). The 3.0.1
   release has an out-parameter bug that bit us (RE-UE4SS #1454). There are ITR2 UE4SS repacks on Nexus too; I
   don't know which of them, if any, are new enough.
   - `dwmapi.dll` and the `ue4ss` folder from the zip go into `<game>\IntoTheRadius2\Binaries\Win64\`, so
     `UE4SS.dll` ends up at `Win64\ue4ss\UE4SS.dll`.
   - In VR you probably want `GuiConsoleEnabled = 0` in `ue4ss\UE4SS-settings.ini`.
2. **The loader:** copy [`loader-ue4ss/ITR2MapLoader`](loader-ue4ss/) into `Win64\ue4ss\Mods\`. Its config is already
   set up for the example (`AutoLoadInHub = "Test"`, `TravelMethod = "OpenLevel"`).
3. **The map:** copy the three files in [`example-map/prebuilt/`](example-map/prebuilt/)
   (`pakchunk100-ITR2Map_Test_P.utoc`, `.ucas` and `.pak`) into `<game>\IntoTheRadius2\Content\Paks\~mods\`. Make the
   `~mods` folder if it isn't there.
4. **Play:** start the game and Continue into the Hub. About 10 s after the Hub has loaded there's a loading screen,
   and you're on the example map: a grey checker floor, red inner walls, a ramp and a platform, all in thick blue
   fog. Straight ahead, through a gap in the far wall, there are four pairs of pillars at 10, 25, 50 and 100 m: the
   left one of each pair uses our red material, the right one the game's own material. If the fog fades both the same
   way, our shaders are doing fog like the game's.
5. **Leave:** walk to the green glowing slab with a tall post, 30 m straight ahead of where you start. You're taken back to the
   Hub, to where you were standing. On a keyboard, F7 does the same (untested).

If the game crashes right after the loading screen starts, the map didn't load. The game crashes instead of saying
so; see the [loader README](loader-ue4ss/README.md#when-it-goes-wrong).

To undo it all, delete:
- the three files in `Content\Paks\~mods`;
- `dwmapi.dll` and the `ue4ss` folder in `Binaries\Win64`.

Details and troubleshooting: [`loader-ue4ss/README.md`](loader-ue4ss/README.md).

## Make your own
**Start here: [`map-making/guide.md`](map-making/guide.md)**. It goes from nothing to walking around your own map.

The main route is the patched Meta fork: you build the editor from Meta's UE 5.5.4 fork with our patch on top, cook
with it, and package with stock 5.5.4. Your own materials work that way. The quick route is stock 5.5.4 from the Epic
launcher plus a patch step after the cook; it's only good for maps made of engine meshes and engine materials. Both
are in the guide. Lit custom materials work on the fork route, see above.

What's where:

| Path | What's in it | Tested? |
|---|---|---|
| [`map-making/guide.md`](map-making/guide.md) | The how-to: setting up the project, the patched fork, cooking and packaging, the stock kludge, getting into the map, and why stock 5.5.4 isn't enough | Both routes, in VR. Lit custom materials on the fork route, simple ones only (§5) |
| [`example-map/`](example-map/) | A small example map, scripts to make, cook, package and patch it for either route, and the prebuilt fork build | Yes, in VR (the prebuilt map is the fog and pillar test build). The build scripts are our working ones with our paths taken out; they haven't been run end to end in this exact form |
| [`loader-ue4ss/`](loader-ue4ss/) | The UE4SS Lua script that gets you into a custom map and back out | Yes, in VR, with `OpenLevel`. The level-instance mode doesn't work yet |
| [`engine/`](engine/) | Our patch for Meta's UE 5.5.4 fork so it saves and compiles what the game expects (CM Games' properties, rendering version and shader layouts, and the instance transform setting). It includes CM's lighting shader changes. No Epic code in it; apply it with `tools/hashpatch.py` | Applying it gives the same files we cooked with. The patched fork cooks maps that load in game. Fog fixes checked in VR; the lightmap clamp not yet |
| [`tools/`](tools/) | `hashpatch.py`, a check that your engine build's shader layouts match the game's, and a check of the shaders in your container | We used all of them |
| [`data/`](data/) | The game's shader parameter layouts, read out of `IntoTheRadius2-Win64-Shipping.exe`, for that check | |

A few notes:
- There's no Unreal Engine source in here. The patch refers to the lines it changes by hash and line number and only
  contains our own lines, so you need your own copy of the engine source to apply it.
- `data/` is just names, offsets, sizes and types, read from the game's exe and its PDB. There are
  no game assets in this repo, and none of the game's config files: the example's `DefaultEngine.ini` is made from
  your own copy of the game.
- The Python tools need Python 3, and some need `pip install pefile capstone comtypes`.

## Licence
- Everything here is under the **GNU Affero General Public License v3.0** ([`LICENSE`](LICENSE)), apart from:
  - [`engine/`](engine/), which is **MIT** ([`engine/LICENSE`](engine/LICENSE)). Those lines end up compiled into
    Unreal Engine, and Epic's EULA doesn't let engine code be mixed with copyleft licences like the AGPL. MIT means
    anyone with an engine licence can actually use it.
  - [`example-map/prebuilt/`](example-map/prebuilt/), which is a cooked package built with Unreal Engine. It has
    shader code compiled from Epic's shaders in it, so the Unreal Engine EULA applies to it rather than our licence.
  - [`data/`](data/), which is just data read from the game's exe and schema. We don't claim any licence over it.
- Maps you build with the example scripts are your own work; the AGPL covers the scripts, but I've no idea how it all accumulates for your own maps etc.

## Obligatory AI Usage info
AI writes code about 10x quicker than me and it is often less frustrating than banging my head against why unreal editor wont build for hours on end(only to learn I didn't need *that* component to build anyway) and then needing to learn the ins and outs of shaders to make code edits to generate the right format used by the original game.... So in this case it made a lot happen that wouldn't have happened otherwise and the caveat that that comes with is that the 'owner' of the code in this instance(and probably most instances imho) does not have the depth of knowledge that you'd want. But this is just a basic capture of "how to make a map including your shaders/mats" so it's better to have han not to I hope.

Also the documentation... writing documentation for a repo no one will ever see is unmotivating and so without ai usage it's unlikely to have materialized.

Hopefully I've managed to cross examine and challenge the AI coding assistants enough that the solutions within are somewhat more robust than average, but I'm sure everyone says that...
