-- ITR2MapLoader settings. Edit this file; main.lua reads it.
return {
    -- LevelInstance mode only (not working yet, see TravelMethod): where the map is placed, in cm. The loader adds it to
    -- each map's StartPos/ReturnPad. 2 km below the Hub so the two never overlap. Per-map override: put
    -- InstanceOffset = {X=,Y=,Z=} inside the map entry.
    InstanceOffset = { X = 0, Y = 0, Z = -200000 },

    Maps = {
        {
            Name = "Test",
            -- Level package path as cooked (container: pakchunk100-ITR2Map_Test_P)
            Level = "/Game/ITR2Mods/TestMap/L_ITR2Test",
            -- Where to put the player once the map has loaded (map coordinates, cm). nil = leave the pawn where the game
            -- put it. The example has a PlayerStart at (-1500, 0, 100); we move there ourselves because we don't know
            -- whether the game's GameMode uses it.
            StartPos = { X = -1500, Y = 0, Z = 150, Yaw = 0 },
            -- Return pad: standing within ReturnRadius cm (horizontal) of this point takes you back to the Hub.
            -- Must match PAD_X/PAD_Y in example-map/Scripts/build_itr2_testmap.py (a 2.5 m slab with a 3 m post, green
            -- in the fork build and grey in the stock one, 30 m ahead of the start).
            ReturnPad = { X = 1500, Y = 0, Z = 0 },
        },
    },

    -- The Hub persistent level: substring of the world's full name used to detect "we are in the Hub", and its package path.
    HubNameMatch = "/Hub/L_Hub.",
    HubLevel = "/Game/ITR2/Levels/_GameplayLevels/Hub/L_Hub",

    -- Load this map (a Name above) automatically after arriving in the Hub, or nil.
    AutoLoadInHub = "Test",
    -- Seconds to wait after the Hub is detected (pawn valid) before issuing the travel. Gives the game time to finish
    -- its own post-load work. Raise it if the game crashes right after Hub load.
    HubDelaySeconds = 10,
    -- false: auto-load once per game launch (so returning to the Hub does not bounce you back out). true: every Hub visit.
    AutoLoadEveryVisit = false,

    -- "OpenLevel" = UGameplayStatics::OpenLevel. This is the one that works.
    -- "Console" = KismetSystemLibrary::ExecuteConsoleCommand("open <path>"). Untested.
    -- "LevelInstance" = stream the map into the running Hub world (ULevelStreamingDynamic::LoadLevelInstance) at
    --   InstanceOffset. Needs a UE4SS newer than 3.0.1, and the game still reports the package as missing. Not working yet.
    TravelMethod = "OpenLevel",
    -- LevelInstance: give up if the instance is not loaded+visible after this many seconds.
    InstanceLoadTimeoutSeconds = 60,

    -- Keyboard key: in the Hub loads the map; in a custom map returns to the Hub.
    Key = "F7",

    -- Once per launch, when the main menu loads: write a fresh usmap and UHT headers into Win64\ue4ss\ (no keyboard
    -- needed). Expect a hitch of up to a minute while the headers are written. Set false once you have them.
    DumpOnMainMenu = false,
    MainMenuNameMatch = "/MainMenu/L_MainMenu.",

    ReturnRadius = 200,
    -- After returning, wait this long (s) for the Hub pawn, then teleport to the saved Hub position.
    ReturnTeleportDelaySeconds = 4,
}
