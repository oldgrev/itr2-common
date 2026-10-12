<#
.SYNOPSIS
  The proper route: makes the ITR2 example map (with its three materials) in the patched Meta fork editor, cooks it
  with the fork (unversioned, compressed), fixes the cook's ChunkManifest paths, then stages, paks and builds the
  IoStore container with the STOCK UE 5.5.4 UAT (-skipcook), and names it pakchunk<N>-<name>_P. With -Install it copies
  it into the game's Content\Paks\~mods. See map-making/guide.md, sections 4 and 5.
.EXAMPLE
  .\build-itr2-map-fork.ps1 -ForkEngine "C:\ue55"                      # generate + cook + package, output in .\build\mod
  .\build-itr2-map-fork.ps1 -SkipGenerate -SkipCook -Install -Game "D:\SteamLibrary\steamapps\common\IntoTheRadius2"
#>
param(
    [string]$ForkEngine = "C:\ue55",                                    # the patched fork, the folder with Engine\ in it
    [string]$StockEngine = "C:\Program Files\Epic Games\UE_5.5",       # stock 5.5.4 from the Epic launcher, for packaging
    [string]$Project = (Join-Path $PSScriptRoot "IntoTheRadius2.uproject"),
    [string]$Out = (Join-Path $PSScriptRoot "build"),
    [string]$Map = "/Game/ITR2Mods/TestMap/L_ITR2Test",
    [int]$Chunk = 100,                 # must match the PrimaryAssetLabel's chunk (CHUNK in the generator)
    [string]$Name = "pakchunk100-ITR2Map_Test_P",   # must be pakchunk<Chunk>-<anything>_P, or the game won't load its shaders
    [switch]$SkipGenerate,             # keep the map you already have (or made by hand)
    [switch]$SkipCook,                 # repackage the last cook
    [switch]$Install,
    [string]$Game = "C:\Program Files (x86)\Steam\steamapps\common\IntoTheRadius2"
)
$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
if ($Name -notmatch "^pakchunk$Chunk-.+_P$") { throw "-Name must look like pakchunk$Chunk-<something>_P (the game finds a mod's shader library by that chunk number)" }
New-Item -ItemType Directory -Force $Out | Out-Null
$ProjDir = Split-Path $Project

if (-not $SkipGenerate) {
    # The full editor with no rendering: the -run=pythonscript commandlet crashes in new_level/new_blank_map on 5.5.
    $env:ITR2_CUSTOM_MATERIALS = "1"
    try {
        & "$ForkEngine\Engine\Binaries\Win64\UnrealEditor.exe" $Project "-ExecutePythonScript=$Here\Scripts\build_itr2_testmap.py" `
            -nullrhi -unattended -nosplash -nosound "-abslog=$Out\generate.log" | Out-Null
    } finally { Remove-Item Env:ITR2_CUSTOM_MATERIALS -ErrorAction SilentlyContinue }
    if (-not (Select-String -Path "$Out\generate.log" -Pattern "ITR2 test map built" -Quiet)) { throw "Map generation failed; see $Out\generate.log" }
}

if (-not $SkipCook) {
    # Cook with the fork, so the packages and shaders match the game. Unversioned and compressed, like the game's own.
    # The first cook compiles the engine's global shaders for SM5 and SM6 and takes a long time.
    & "$ForkEngine\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" $Project -run=Cook -TargetPlatform=Windows "-Map=$Map" `
        -unversioned -iostore -compressed -manifests -unattended -nosplash -nosound -utf8output "-abslog=$Out\cook.log" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Fork cook failed ($LASTEXITCODE); see $Out\cook.log" }
}

# The cook writes the ChunkManifest paths relative to the engine folder that ran it, and the stock UAT reads them
# relative to its own. Rewrite them for the stock engine. Lines that already resolve from the stock engine are left alone,
# so running this twice is fine.
function Get-RelativeTo([string]$Base, [string]$Path) {
    $b = [IO.Path]::GetFullPath($Base).TrimEnd('\') + '\'
    if ([IO.Path]::GetPathRoot($b) -ne [IO.Path]::GetPathRoot($Path)) { return $Path }
    [Uri]::UnescapeDataString(([Uri]$b).MakeRelativeUri([Uri]$Path).ToString()).Replace('/', '\')
}
$Cooked = Join-Path $ProjDir "Saved\Cooked\Windows"
Get-ChildItem "$Cooked\*\Metadata\ChunkManifest\pakchunk*.txt" | ForEach-Object {
    $lines = Get-Content $_.FullName
    $fixed = foreach ($l in $lines) {
        if (-not $l -or [IO.Path]::IsPathRooted($l)) { $l; continue }
        $fromStock = [IO.Path]::GetFullPath((Join-Path $StockEngine $l))
        $fromFork = [IO.Path]::GetFullPath((Join-Path $ForkEngine $l))
        if (Test-Path (Split-Path $fromStock)) { $l }
        elseif (Test-Path (Split-Path $fromFork)) { Get-RelativeTo $StockEngine $fromFork }
        else { $l }
    }
    if (($fixed -join "`n") -ne ($lines -join "`n")) { Set-Content $_.FullName $fixed }
}

# Stage + pak + IoStore with the stock UAT on the fork's cooked output. A source-built editor has no UnrealGame
# Shipping receipt, so its own UAT won't stage a Shipping build of a blueprint-only project.
if (Test-Path "$Out\stage") { Remove-Item "$Out\stage" -Recurse -Force }
& "$StockEngine\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$Project" -platform=Win64 -clientconfig=Shipping `
    -skipcook -skipbuild -nocompile -nocompileuat -stage -pak -iostore -compressed -unversioned -manifests -utf8output `
    -nodebuginfo -skipcompilingdll "-stagingdirectory=$Out\stage" "-abslog=$Out\uat.log" -unattended
if ($LASTEXITCODE -ne 0) { throw "Stage/pak failed ($LASTEXITCODE); see $Out\uat.log" }

$Paks = Get-ChildItem "$Out\stage" -Recurse -Filter "pakchunk$Chunk-*" | Where-Object { $_.Extension -in ".utoc", ".ucas", ".pak" }
if (-not $Paks) { throw "No pakchunk$Chunk-* in the staged output; check the PrimaryAssetLabel's chunk" }
New-Item -ItemType Directory -Force "$Out\mod" | Out-Null
Get-ChildItem "$Out\mod" -Filter "$Name.*" | Remove-Item -Force
foreach ($f in $Paks) { Copy-Item $f.FullName (Join-Path "$Out\mod" ($Name + $f.Extension)) -Force }
Get-ChildItem "$Out\mod" -Filter "$Name.*" | Select-Object Name, Length

if ($Install) {
    if (Get-Process -Name "IntoTheRadius2-Win64-Shipping" -ErrorAction SilentlyContinue) { throw "Close the game first." }
    $Dst = Join-Path $Game "IntoTheRadius2\Content\Paks\~mods"
    if (-not (Test-Path (Split-Path $Dst))) { throw "Not found: $(Split-Path $Dst) (pass -Game)" }
    New-Item -ItemType Directory -Force $Dst | Out-Null
    foreach ($e in ".utoc", ".ucas", ".pak") { Copy-Item (Join-Path "$Out\mod" "$Name$e") $Dst -Force }
    Write-Host "Installed into $Dst"
}
