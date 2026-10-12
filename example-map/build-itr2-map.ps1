<#
.SYNOPSIS
  Makes the ITR2 example map headlessly, cooks it with stock UE 5.5.4 as an IoStore container, patches the rendering
  version (the kludge, see map-making/guide.md) and, with -Install, copies it into the game's Content\Paks\~mods.
.EXAMPLE
  .\build-itr2-map.ps1                                 # generate + cook + package + patch, output in .\build\mod
  .\build-itr2-map.ps1 -SkipGenerate -Install -Game "D:\SteamLibrary\steamapps\common\IntoTheRadius2"
#>
param(
    [string]$Engine = "C:\Program Files\Epic Games\UE_5.5",   # the folder with Engine\ in it
    [string]$Project = (Join-Path $PSScriptRoot "IntoTheRadius2.uproject"),
    [string]$Out = (Join-Path $PSScriptRoot "build"),
    [string]$Map = "/Game/ITR2Mods/TestMap/L_ITR2Test",
    [string]$Name = "zzz_ITR2Map_Test_P",
    [int]$Chunk = 100,                 # must match the PrimaryAssetLabel's chunk (CHUNK in the generator)
    [switch]$SkipGenerate,             # keep the map you already have (or made by hand) and just cook it
    [switch]$Compressed,               # compressed container; patch_inplace.py can't edit those, so no patch either
    [switch]$Unversioned,              # cook with -unversioned. Stock 5.5.4's property layouts don't match the game's, so don't
    [switch]$Install,
    [string]$Game = "C:\Program Files (x86)\Steam\steamapps\common\IntoTheRadius2"
)
$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
New-Item -ItemType Directory -Force $Out | Out-Null

if (-not $SkipGenerate) {
    # The full editor with no rendering: the -run=pythonscript commandlet crashes in new_level/new_blank_map on 5.5.
    & "$Engine\Engine\Binaries\Win64\UnrealEditor.exe" $Project "-ExecutePythonScript=$Here\Scripts\build_itr2_testmap.py" `
        -nullrhi -unattended -nosplash -nosound "-abslog=$Out\generate.log" | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Select-String -Path "$Out\generate.log" -Pattern "ITR2 test map built" -Quiet)) { throw "Map generation failed; see $Out\generate.log" }
}

# The project ini says bCompressed=True, and UAT applies that even without -compressed, so flip it for this run.
$GameIni = Join-Path (Split-Path $Project) "Config\DefaultGame.ini"
$IniText = Get-Content $GameIni -Raw
if (-not $Compressed) { Set-Content $GameIni ($IniText -replace 'bCompressed=True', 'bCompressed=False') -NoNewline }

# Cook + stage + pak + IoStore. Blueprint-only project, so nothing to compile. Chunk $Chunk is our container.
# The first run compiles the engine's global shaders for SM5 and SM6 and takes a long time.
try {
    & "$Engine\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$Project" -platform=Win64 -clientconfig=Shipping `
        -cook "-map=$Map" -skipbuild -nocompile -nocompileuat -stage -pak -iostore $(if ($Compressed) { "-compressed" } else { "" }) `
        $(if ($Unversioned) { '-unversioned' } else { '-VersionCookedContent' }) -utf8output -nodebuginfo -skipcompilingdll `
        "-stagingdirectory=$Out\stage" "-abslog=$Out\uat.log" -unattended
    $UatExit = $LASTEXITCODE
} finally {
    if (-not $Compressed) { Set-Content $GameIni $IniText -NoNewline }
}
if ($UatExit -ne 0) { throw "BuildCookRun failed ($UatExit); see $Out\uat.log" }

$Paks = Get-ChildItem "$Out\stage" -Recurse -Filter "pakchunk$Chunk-*" | Where-Object { $_.Extension -in ".utoc", ".ucas", ".pak" }
if (-not $Paks) { throw "No pakchunk$Chunk-* in the staged output; check the PrimaryAssetLabel's chunk" }
New-Item -ItemType Directory -Force "$Out\mod" | Out-Null
foreach ($f in $Paks) { Copy-Item $f.FullName (Join-Path "$Out\mod" ($Name + $f.Extension)) -Force }

# The kludge: rendering version 49 -> 48 in the container (map-making/guide.md explains why).
if (-not $Compressed) {
    python (Join-Path $Here "Scripts\patch_inplace.py") (Join-Path "$Out\mod" "$Name.ucas")
    if ($LASTEXITCODE -ne 0) { throw "patch_inplace.py failed" }
}
Get-ChildItem "$Out\mod" | Select-Object Name, Length

if ($Install) {
    if (Get-Process -Name "IntoTheRadius2-Win64-Shipping" -ErrorAction SilentlyContinue) { throw "Close the game first." }
    $Dst = Join-Path $Game "IntoTheRadius2\Content\Paks\~mods"
    if (-not (Test-Path (Split-Path $Dst))) { throw "Not found: $(Split-Path $Dst) (pass -Game)" }
    New-Item -ItemType Directory -Force $Dst | Out-Null
    foreach ($e in ".utoc", ".ucas", ".pak") { Copy-Item (Join-Path "$Out\mod" "$Name$e") $Dst -Force }
    Write-Host "Installed into $Dst"
}
