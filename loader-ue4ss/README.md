# ITR2MapLoader (UE4SS Lua)

A small UE4SS script that gets you into a custom map in Into the Radius 2 and back out again. The game has no way to
load custom maps, so you need something like this to get into one.

When you arrive in the Hub (or press a key), it waits a few seconds, remembers where you're standing, and travels to
your map with `OpenLevel`. Once you're there it moves you to the map's start point. When you step on the map's
return pad, it travels back to the Hub and puts you where you were.

It's a port of the ITR1 loader, but it works differently. The ITR1 one streams the map in next to the Hub; this one
does a full level change, because streaming doesn't work here yet (see the end).

## What we've tested
We tested it on 2026-10-12 with the [example map](../example-map/), in VR (SteamVR), with an experimental UE4SS
build (more on that below), both the stock 5.5.4 build and the fork build:
- the map loaded about 8 s after the Hub did, we were moved onto the start point and could walk around the floor,
  walls and ramp;
- walking onto the return pad took us back to the Hub, and the loader put us back where we'd been standing.

Not tested yet:
- The F7 key. It calls the same code, so it should be fine.
- Whether the Hub is exactly as you left it after coming back. `OpenLevel` back to the Hub isn't the game's own way
  of travelling, so something like the game's state for that area could be off. We haven't looked closely.
- `TravelMethod = "Console"`.
- `enabled.txt`. We started the mod from `mods.txt`; `enabled.txt` is what the ITR1 loader used, and this UE4SS
  build logs that it reads it, so it should work too.
- The game left a UE4SS crash dump when we quit afterwards. We haven't looked at it, and it may have nothing to do
  with the map.

## Installing
1. **UE4SS.** You need a build newer than the 3.0.1 release. We used an experimental build from
   https://github.com/UE4SS-RE/RE-UE4SS/releases (the `experimental` ones); `UE4SS.log` calls it
   `v3.0.1 Beta #0 - Git SHA #5e627997`. An older 3.0.1 build did get as far as travelling to the map in an earlier
   test, but the working run was on the experimental one, so start with that or newer. The 3.0.1 release definitely
   can't make the `LoadLevelInstance` call the streaming mode needs (it's RE-UE4SS issue #1454).
   - Put `dwmapi.dll` and the `ue4ss` folder from the zip into `<game>\IntoTheRadius2\Binaries\Win64\`, so you end up
     with `Win64\dwmapi.dll` and `Win64\ue4ss\UE4SS.dll`.
   - In VR you probably want `GuiConsoleEnabled = 0` in `ue4ss\UE4SS-settings.ini`. Everything still goes to
     `UE4SS.log`.
2. Copy the `ITR2MapLoader` folder into `Win64\ue4ss\Mods\`. Either keep the empty `enabled.txt` in it, or add a
   line `ITR2MapLoader : 1` to `Mods\mods.txt` above the `Keybinds` line (that's what we did).
3. Have a look at `ITR2MapLoader\Scripts\config.lua`:
   - `Maps` lists your maps: a name, the level path, where to start (`StartPos`) and where the return pad is
     (`ReturnPad`), both in map coordinates in cm;
   - `AutoLoadInHub` is the map to load when you get to the Hub, which is what you want in VR. `nil` turns it off;
   - `AutoLoadEveryVisit = false` means it only does that once per launch, so coming back to the Hub doesn't throw you
     straight back out;
   - `HubDelaySeconds` is how long it waits in the Hub first (10 s);
   - `TravelMethod` should stay `"OpenLevel"`;
   - `Key` is the keyboard key, F7 by default;
   - `DumpOnMainMenu = true` makes UE4SS write a fresh `.usmap` and UHT headers when the main menu loads. That's only
     useful if a game update changes CM's engine properties and someone has to redo the property stubs. It hitches
     for up to a minute. Leave it `false` otherwise.

To uninstall, delete `dwmapi.dll` and the `ue4ss` folder (or just the `ITR2MapLoader` folder if you use UE4SS for
other things).

## Using it
- In VR, leave `AutoLoadInHub` set. Go into the Hub as normal (Continue from the menu). About 10 s later there's a
  loading screen and you're on the map. To leave, walk onto the return pad (within 2 m of its centre).
- On a keyboard, F7 in the Hub loads the first map in your list, and F7 on the map takes you back.
- It never does anything in the main menu.
- `UE4SS.log` (in `Win64\ue4ss\`) shows what it's doing. Look for lines starting with `[ITR2MapLoader]`. A good run
  looks like this:
  ```
  ready: 1 map(s); key F7; auto-load Test; method OpenLevel
  world changed: World /Game/ITR2/Levels/_GameplayLevels/Hub/L_Hub.L_Hub
  hub detected, pawn found (BP_RadiusPlayerCharacter_Gameplay_C ...); waiting 10s
  Hub position saved: -4671 311 11
  travel issued: /Game/ITR2Mods/TestMap/L_ITR2Test via OpenLevel
  world changed: World /Game/ITR2Mods/TestMap/L_ITR2Test.L_ITR2Test
  teleport to start -1500 0 150: true
  return pad reached
  travel issued: /Game/ITR2/Levels/_GameplayLevels/Hub/L_Hub via OpenLevel
  map loaded: back in the Hub world
  returned to Hub position: teleport=true
  ```

## When it goes wrong
- **The game crashes right after `travel issued: ...` and nothing else.** That means your map didn't load. The crash
  itself is in the game's `URadiusGameInstance::OnPostLoadMap`: when a map fails to load, the engine hands it an empty
  world and it doesn't check. The shipping game doesn't log why the load failed, so the crash is all you get. The
  usual reasons, roughly in order:
  - on the stock 5.5.4 route, the container isn't patched (the kludge in the [guide](../map-making/guide.md)). Then
    the crash report says `Serial size mismatch` instead, or the load just fails;
  - the files aren't in `Content\Paks\~mods`, or one of the three is missing;
  - the level path in `config.lua` doesn't match what you cooked;
  - on the stock route, something in the map that stock 5.5.4 saves differently from the game, like a material
    instance (the guide explains). Crash reports go to `%LOCALAPPDATA%\IntoTheRadius2\Saved\Crashes\`.
- **Crash in `SerializeUnversionedProperties`.** On the stock route: the map was cooked unversioned, or it has
  something whose properties differ between stock 5.5.4 and the game (a material instance did this for us). Cook
  versioned, which `build-itr2-map.ps1` does by default, and stick to plain engine content. On the fork route it
  means the fork isn't patched, or the patch doesn't match your game version.
- **Your materials show up as the grey and white grid.** The game didn't open your container's shader library. The
  container has to be named `pakchunk<N>-<anything>_P` (the example is `pakchunk100-ITR2Map_Test_P`).
- **Your materials are black, unlit ones included.** The fork that cooked them didn't have the
  `DataDrivenPlatformInfo.ini` change from the engine patch (guide §4).
- **Nothing happens in the Hub.** Check the log for `ready:`. If it's not there, the mod didn't start (check
  `mods.txt` or `enabled.txt`). If there's no `hub detected`, look at the `world changed:` lines for the Hub's real
  name and fix `HubNameMatch`.
- **UE4SS itself doesn't start, or the log shows a failed signature scan.** The UE4SS build doesn't match this exe.
  Try a newer one.
- **You land somewhere odd on the map.** `StartPos` doesn't match your map. The loader moves you there itself
  rather than relying on the PlayerStart.

## If you're making a map
- Put a `PlayerStart` where people should arrive, and put the same spot in `StartPos`.
- Put something visible where the return pad is, and put that spot in `ReturnPad`. The example uses a flat slab
  with a tall post.
- Please don't skip the return pad. Without one, people in VR are stuck until they quit to the menu.
- ITR1's loader found its start and exit by tagged `TargetPoint`s. This one uses coordinates in the config for now.

## How it works
Everything that touches the game runs inside `ExecuteInGameThread`, on a 1 s `LoopAsync` timer. It's a small
state machine (`idle`, `traveling_out`, `in_map`, `traveling_back`, `returned_wait`) that watches the world's name.
- **In the Hub**, once the pawn has existed for `HubDelaySeconds`, it saves the pawn's position and calls
  `GameplayStatics::OpenLevel(World, <map>, true, "")`.
- **On the map**, once there's a pawn, it calls `K2_TeleportTo` to `StartPos`. After a 5 s grace period it checks
  every second whether you're within `ReturnRadius` of `ReturnPad`, and if you are it opens the Hub again.
- **Back in the Hub**, it waits `ReturnTeleportDelaySeconds` for the pawn and teleports it to the saved position.

The streaming mode (`TravelMethod = "LevelInstance"`) is still in there. It calls
`LevelStreamingDynamic::LoadLevelInstance` and places the map 2 km below the Hub. With a fixed UE4SS the call itself
works (the out-parameter takes a table in its own position), but the game returns `bOutSuccess = false`, which means
its check that the package exists failed, for the same container `OpenLevel` loads fine. We don't know why yet.
If someone works it out, streaming would be the nicer way: no loading screen, and the Hub stays as it was.
