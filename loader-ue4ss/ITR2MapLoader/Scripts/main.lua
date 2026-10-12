-- ITR2MapLoader: gets you from the Hub into a custom map in Into the Radius 2 (UE 5.5.4) and back, with UE4SS.
-- Ported from the ITR1 ITRMapLoader (itr-common). Settings are in config.lua.
--
-- TravelMethod "OpenLevel" (the default, and the one that works):
--   Hub detected (world name matches, pawn valid) -> wait HubDelaySeconds -> remember the Hub pawn's position ->
--   OpenLevel(map) -> the new world has the map's name and a pawn -> teleport to StartPos ->
--   standing on ReturnPad (or F7) -> OpenLevel(Hub) -> back in the Hub -> teleport to the remembered position.
-- TravelMethod "Console" does the same travel through the "open" console command. Not tested.
-- TravelMethod "LevelInstance" streams the map into the running Hub world at InstanceOffset instead
--   (ULevelStreamingDynamic::LoadLevelInstance), the way the ITR1 loader works. It needs a UE4SS build with the fix
--   for RE-UE4SS #1454 to make the call at all, and even then the game says the package doesn't exist
--   (bOutSuccess=false) for a map OpenLevel loads fine. We don't know why yet, so it's kept for later.
--
-- The game's own travel, URadiusLevelSubsystem:LoadLevel(FGameplayTag LevelTag, bHardTravel, bDisconnect,
-- bTransitionBetweenLevels) and URadiusCheatSubsystem:TravelTo(FGameplayTag), needs a level tag from the game's data,
-- and a custom map doesn't have one. Noted here for whoever wants to try registering one.
--
-- Everything is logged to UE4SS.log with the prefix [ITR2MapLoader].

local UEHelpers = require("UEHelpers")
local Config = require("config")

local TAG = "[ITR2MapLoader] "
local function Log(fmt, ...) print(TAG .. string.format(fmt, ...) .. "\n") end
local function Valid(o) return o ~= nil and o.IsValid ~= nil and o:IsValid() end

-- State (Lua state survives level changes; only a UE4SS hot reload or restart clears it)
local S = {
    Phase = "idle",       -- idle | traveling_out | in_map | traveling_back | returned_wait
    LastWorld = "",
    HubSeen = 0,          -- consecutive 1 s polls with Hub + valid pawn
    HubReturn = nil,      -- {Loc=,Rot=} Hub pawn pose before leaving
    Map = nil,
    PhaseTime = 0,        -- seconds spent in current phase
    AutoDone = false,
    PadSeen = 0,
    Instance = nil,       -- ULevelStreamingDynamic of the loaded level instance (LevelInstance mode)
    InstOffset = nil,     -- {X,Y,Z} offset used for it
}
local LI = Config.TravelMethod == "LevelInstance"

local function SetPhase(p) Log("phase %s -> %s", S.Phase, p); S.Phase = p; S.PhaseTime = 0 end

local function WorldName()
    local W = UEHelpers.GetWorld()
    if not Valid(W) then return nil end
    return W:GetFullName()
end

local function InHub(name) return name ~= nil and name:find(Config.HubNameMatch, 1, true) ~= nil end
local function InMap(name, Map)
    if not name then return false end
    local leaf = Map.Level:match("([^/]+)$")
    return name:find("/" .. leaf .. ".", 1, true) ~= nil
end

local function GetPawn()
    local P = UEHelpers.GetPlayer()
    if Valid(P) then return P end
    return nil
end

local function PawnPose(Pawn)
    local L, R = Pawn:K2_GetActorLocation(), Pawn:K2_GetActorRotation()
    return { Loc = { X = L.X, Y = L.Y, Z = L.Z }, Rot = { Pitch = R.Pitch, Yaw = R.Yaw, Roll = R.Roll } }
end

local function Travel(LevelPath)
    local World = UEHelpers.GetWorld()
    if not Valid(World) then Log("travel: no world"); return false end
    Log("travel issued: %s via %s", LevelPath, Config.TravelMethod)
    if Config.TravelMethod == "Console" then
        local KSL = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
        local PC = UEHelpers.GetPlayerController()
        KSL:ExecuteConsoleCommand(World, "open " .. LevelPath, PC)
    else
        local GS = StaticFindObject("/Script/Engine.Default__GameplayStatics")
        if not Valid(GS) then Log("travel: GameplayStatics not found"); return false end
        GS:OpenLevel(World, FName(LevelPath), true, "")
    end
    return true
end

local function MapByName(Name)
    for _, M in ipairs(Config.Maps) do if M.Name == Name then return M end end
end

-- ===== LevelInstance mode =====
local function OffsetOf(Map) return Map.InstanceOffset or Config.InstanceOffset or { X = 0, Y = 0, Z = -200000 } end

-- Teleport the pawn; K2_TeleportTo first, the game's Client_TeleportPlayer if that fails or the pawn did not move.
local function TeleportPawn(Pawn, Loc, Yaw)
    local Rot = { Pitch = 0, Yaw = Yaw or 0, Roll = 0 }
    local ok = false
    local pc = pcall(function() ok = Pawn:K2_TeleportTo({ X = Loc.X, Y = Loc.Y, Z = Loc.Z }, Rot) end)
    local L = Pawn:K2_GetActorLocation()
    local d = math.abs(L.X - Loc.X) + math.abs(L.Y - Loc.Y) + math.abs(L.Z - Loc.Z)
    Log("K2_TeleportTo -> call=%s result=%s, pawn now %.0f %.0f %.0f (off by %.0f)", tostring(pc), tostring(ok), L.X, L.Y, L.Z, d)
    if pc and ok and d < 200 then return "K2_TeleportTo" end
    local h = math.rad(Rot.Yaw) / 2
    local pc2, err = pcall(function()
        Pawn:Client_TeleportPlayer({ Rotation = { X = 0, Y = 0, Z = math.sin(h), W = math.cos(h) },
                                     Translation = { X = Loc.X, Y = Loc.Y, Z = Loc.Z }, Scale3D = { X = 1, Y = 1, Z = 1 } },
                                   { X = 0, Y = 0, Z = 0 }, false, false, 0)
    end)
    L = Pawn:K2_GetActorLocation()
    Log("Client_TeleportPlayer -> call=%s %s, pawn now %.0f %.0f %.0f", tostring(pc2), tostring(err or ""), L.X, L.Y, L.Z)
    return "Client_TeleportPlayer"
end

local function IsObj(o) return type(o) == "userdata" and Valid(o) end

local function LoadInstance(Map)
    local World = UEHelpers.GetWorld()
    local Off = OffsetOf(Map)
    local CDO = StaticFindObject("/Script/Engine.Default__LevelStreamingDynamic")
    if not Valid(CDO) then Log("instance: Default__LevelStreamingDynamic not found"); return false end
    local Cls = StaticFindObject("/Script/Engine.LevelStreamingDynamic")
    Log("instance: LoadLevelInstance(%s) at offset %.0f %.0f %.0f", Map.Level, Off.X, Off.Y, Off.Z)
    -- Signature (5.5): (WorldContext, FString LevelName, FVector Location, FRotator Rotation, bool& bOutSuccess,
    --   FString OptionalLevelNameOverride, TSubclassOf OptionalLevelStreamingClass, bool bLoadAsTempPackage) -> ULevelStreamingDynamic*
    local Loc, Rot = { X = Off.X, Y = Off.Y, Z = Off.Z }, { Pitch = 0, Yaw = 0, Roll = 0 }
    -- The out param bOutSuccess takes a table in its own position. That needs a UE4SS with the fix for RE-UE4SS #1454
    -- (commit 3a4b642); the 3.0.1 release reads the following params from the wrong place. The result lands in
    -- Out.bOutSuccess.
    local Out = {}
    local ok, r1, r2 = pcall(function()
        return CDO:LoadLevelInstance(World, Map.Level, Loc, Rot, Out, "", Cls, false)
    end)
    Log("instance: bOutSuccess=%s", tostring(Out.bOutSuccess))
    Log("instance: LoadLevelInstance call ok=%s ret1=%s ret2=%s", tostring(ok), tostring(r1), tostring(r2))
    if not ok then return false end
    local Obj = r1
    if not IsObj(Obj) and IsObj(r2) then Obj = r2 end   -- return order may differ between UE4SS builds
    if not IsObj(Obj) then
        -- fallback: a LevelStreamingDynamic whose name mentions our level
        local leaf = Map.Level:match("([^/]+)$")
        local all = FindAllOf("LevelStreamingDynamic")
        for _, o in ipairs(all or {}) do
            if Valid(o) and o:GetFullName():find(leaf, 1, true) then Obj = o end
        end
        Log("instance: returned object invalid; FindAllOf fallback -> %s", tostring(Obj))
    end
    if not IsObj(Obj) then return false end
    S.Instance = Obj
    S.InstOffset = Off
    Log("instance: streaming object %s", Obj:GetFullName())
    pcall(function() Obj:SetShouldBeVisible(true) end)
    return true
end

local function UnloadInstance()
    local Inst = S.Instance
    if not IsObj(Inst) then Log("unload: no valid instance"); S.Instance = nil; return end
    local a = pcall(function() Inst:SetShouldBeVisible(false) end)
    local b = pcall(function() Inst:SetShouldBeLoaded(false) end)
    Log("unload: SetShouldBeVisible(false) call=%s, SetShouldBeLoaded(false) call=%s", tostring(a), tostring(b))
    S.Instance = nil
end

local function InstanceReady()
    local Inst = S.Instance
    if not IsObj(Inst) then return false end
    local loaded, vis, lvl = false, false, nil
    pcall(function() loaded = Inst:IsLevelLoaded() end)
    pcall(function() vis = Inst:IsLevelVisible() end)
    pcall(function() lvl = Inst:GetLoadedLevel() end)
    if S.PhaseTime % 5 == 0 then Log("instance: waiting loaded=%s visible=%s level=%s", tostring(loaded), tostring(vis), tostring(lvl)) end
    return loaded and vis and lvl ~= nil and Valid(lvl)
end

local function ReturnFromInstance(why)
    Log("returning from instance (%s)", why)
    local Pawn = GetPawn()
    if Pawn and S.HubReturn then
        local how = TeleportPawn(Pawn, S.HubReturn.Loc, S.HubReturn.Rot.Yaw)
        Log("returned to Hub position via %s", how)
    else
        Log("return: no pawn or no saved Hub position, unloading anyway")
    end
    UnloadInstance()
    S.HubReturn = nil
    SetPhase("idle")
end

local function GoToMap(Map)
    local Pawn = GetPawn()
    if not Pawn then Log("no pawn, not leaving the Hub"); return end
    S.HubReturn = PawnPose(Pawn)
    Log("Hub position saved: %.0f %.0f %.0f", S.HubReturn.Loc.X, S.HubReturn.Loc.Y, S.HubReturn.Loc.Z)
    S.Map = Map
    if LI then
        SetPhase("loading_instance")
        if not LoadInstance(Map) then Log("instance load failed"); SetPhase("idle") end
        return
    end
    SetPhase("traveling_out")
    Travel(Map.Level)
end

local function GoToHub()
    SetPhase("traveling_back")
    Travel(Config.HubLevel)
end

-- Key: Hub -> load the map; custom map -> back to the Hub
RegisterKeyBind(Key[Config.Key] or Key.F7, function()
    ExecuteInGameThread(function()
        local name = WorldName()
        Log("%s pressed in world %s (phase %s)", Config.Key, tostring(name), S.Phase)
        if LI then
            if S.Phase == "in_map" and S.Instance then ReturnFromInstance("key")
            elseif InHub(name) and S.Phase == "idle" then GoToMap(S.Map or Config.Maps[1])
            else Log("ignored (phase %s)", S.Phase) end
        elseif S.Map and InMap(name, S.Map) then
            GoToHub()
        elseif InHub(name) and (S.Phase == "idle" or S.Phase == "returned_wait") then
            GoToMap(S.Map or Config.Maps[1])
        else
            Log("ignored (not in the Hub or the custom map, or travel in progress)")
        end
    end)
end)

-- 1 s state machine
LoopAsync(1000, function()
    ExecuteInGameThread(function()
        local name = WorldName()
        S.PhaseTime = S.PhaseTime + 1
        if name ~= nil and name ~= S.LastWorld then
            Log("world changed: %s", name)
            S.LastWorld = name
            S.HubSeen = 0
            S.PadSeen = 0
        end
        if not name then return end
        if Config.DumpOnMainMenu and not S.Dumped and name:find(Config.MainMenuNameMatch, 1, true) then
            S.Dumped = true
            Log("main menu: dumping usmap")
            DumpUSMAP()
            Log("main menu: generating UHT headers")
            GenerateUHTCompatibleHeaders()
            Log("main menu: dumps done")
        end
        local Pawn = GetPawn()

        if LI and InHub(name) then
            -- world stays L_Hub; the loader's phase says whether we are "in the map"
            if S.Phase == "idle" then
                if Pawn then S.HubSeen = S.HubSeen + 1 else S.HubSeen = 0 end
                if Pawn and Config.AutoLoadInHub and not S.Instance and (not S.AutoDone or Config.AutoLoadEveryVisit) then
                    if S.HubSeen == 1 then
                        Log("hub detected, pawn found (%s); waiting %ds", Pawn:GetFullName(), Config.HubDelaySeconds)
                    end
                    if S.HubSeen >= Config.HubDelaySeconds then
                        local Map = MapByName(Config.AutoLoadInHub)
                        S.AutoDone = true
                        if Map then GoToMap(Map) else Log("AutoLoadInHub: no map named %s", Config.AutoLoadInHub) end
                    end
                end
            elseif S.Phase == "loading_instance" then
                if S.PhaseTime > Config.InstanceLoadTimeoutSeconds then
                    Log("instance not loaded+visible after %d s; giving up", S.PhaseTime)
                    UnloadInstance(); S.HubReturn = nil; SetPhase("idle")
                elseif InstanceReady() and Pawn then
                    Log("instance loaded and visible after %d s", S.PhaseTime)
                    local SP, Off = S.Map.StartPos, S.InstOffset
                    if SP then
                        local how = TeleportPawn(Pawn, { X = SP.X + Off.X, Y = SP.Y + Off.Y, Z = SP.Z + Off.Z }, SP.Yaw)
                        Log("teleported to start %.0f %.0f %.0f (+offset) via %s", SP.X, SP.Y, SP.Z, how)
                    end
                    S.PadSeen = 0
                    SetPhase("in_map")
                end
            elseif S.Phase == "in_map" then
                if not IsObj(S.Instance) then
                    Log("instance object gone while in map; treating as returned"); S.Instance = nil; SetPhase("idle")
                elseif Pawn and S.Map.ReturnPad then
                    S.PadSeen = S.PadSeen + 1
                    local P, Off = S.Map.ReturnPad, S.InstOffset
                    local L = Pawn:K2_GetActorLocation()
                    local dx, dy = L.X - (P.X + Off.X), L.Y - (P.Y + Off.Y)
                    if S.PadSeen > 5 and dx * dx + dy * dy < Config.ReturnRadius ^ 2 then
                        Log("return pad reached")
                        ReturnFromInstance("pad")
                    end
                end
            end
        elseif InHub(name) then
            if S.Phase == "traveling_back" then
                Log("map loaded: back in the Hub world")
                SetPhase("returned_wait")
            end
            if Pawn then S.HubSeen = S.HubSeen + 1 else S.HubSeen = 0 end

            if S.Phase == "returned_wait" and S.HubReturn and Pawn and S.HubSeen >= Config.ReturnTeleportDelaySeconds then
                local ok = Pawn:K2_TeleportTo(S.HubReturn.Loc, S.HubReturn.Rot)
                Log("returned to Hub position: teleport=%s", tostring(ok))
                S.HubReturn = nil
                SetPhase("idle")
            elseif S.Phase == "idle" and Config.AutoLoadInHub and (not S.AutoDone or Config.AutoLoadEveryVisit) then
                if S.HubSeen == 1 then
                    Log("hub detected, pawn found (%s); waiting %ds", Pawn:GetFullName(), Config.HubDelaySeconds)
                end
                if S.HubSeen >= Config.HubDelaySeconds then
                    local Map = MapByName(Config.AutoLoadInHub)
                    S.AutoDone = true
                    if Map then GoToMap(Map) else Log("AutoLoadInHub: no map named %s", Config.AutoLoadInHub) end
                end
            end
        elseif not LI and S.Map and InMap(name, S.Map) then
            if S.Phase == "traveling_out" then
                Log("map loaded: world %s", name)
                SetPhase("in_map")
                S.PadSeen = 0
            end
            if S.Phase == "in_map" then
                if not Pawn then
                    if S.PhaseTime % 5 == 0 then Log("in map, no pawn yet (%ds)", S.PhaseTime) end
                else
                    if S.PadSeen == 0 then
                        local L = Pawn:K2_GetActorLocation()
                        Log("pawn found: %s at %.0f %.0f %.0f", Pawn:GetFullName(), L.X, L.Y, L.Z)
                        local SP = S.Map.StartPos
                        if SP then
                            local ok = Pawn:K2_TeleportTo({ X = SP.X, Y = SP.Y, Z = SP.Z },
                                                          { Pitch = 0, Yaw = SP.Yaw or 0, Roll = 0 })
                            Log("teleport to start %.0f %.0f %.0f: %s", SP.X, SP.Y, SP.Z, tostring(ok))
                        end
                    end
                    S.PadSeen = S.PadSeen + 1
                    local P = S.Map.ReturnPad
                    if P and S.PadSeen > 5 then   -- grace period so the start teleport can't trip the pad
                        local L = Pawn:K2_GetActorLocation()
                        local dx, dy = L.X - P.X, L.Y - P.Y
                        if dx * dx + dy * dy < Config.ReturnRadius ^ 2 then
                            Log("return pad reached")
                            GoToHub()
                        end
                    end
                end
            end
        end
        -- Travel stuck? (neither Hub nor map after 90 s)
        if not LI and (S.Phase == "traveling_out" or S.Phase == "traveling_back") and S.PhaseTime > 90 then
            Log("travel did not complete in 90 s (world is %s)", name)
            SetPhase("idle")
        end
    end)
    return false
end)

Log("ready: %d map(s); key %s; auto-load %s; method %s", #Config.Maps, Config.Key,
    tostring(Config.AutoLoadInHub), Config.TravelMethod)
