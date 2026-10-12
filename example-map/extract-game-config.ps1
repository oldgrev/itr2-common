<#
.SYNOPSIS
  Makes Config\DefaultEngine.ini for this project from the game's own one.
  The game's configs live in the small pakchunk0-Windows.pak (not the utoc). This pulls them out with repak and
  then keeps the PC settings a map cook needs (Scripts\make_engine_ini.py says which).
.EXAMPLE
  .\extract-game-config.ps1 -Game "D:\SteamLibrary\steamapps\common\IntoTheRadius2" -Repak "C:\tools\repak\repak.exe"
#>
param(
    [string]$Game = "C:\Program Files (x86)\Steam\steamapps\common\IntoTheRadius2",
    [string]$Repak = "repak.exe",   # repak_cli from github.com/trumank/repak releases (we used 0.2.3)
    [string]$Map = "/Game/ITR2Mods/TestMap/L_ITR2Test"
)
$ErrorActionPreference = "Stop"
$Pak = Join-Path $Game "IntoTheRadius2\Content\Paks\pakchunk0-Windows.pak"
if (-not (Test-Path $Pak)) { throw "Not found: $Pak (pass -Game <the folder with IntoTheRadius2 in it>)" }

$Tmp = Join-Path ([IO.Path]::GetTempPath()) "itr2-config"
if (Test-Path $Tmp) { Remove-Item -Recurse -Force $Tmp }
& $Repak unpack -q -i IntoTheRadius2/Config -o $Tmp $Pak
if ($LASTEXITCODE -ne 0) { throw "repak failed ($LASTEXITCODE)" }
$GameIni = Join-Path $Tmp "IntoTheRadius2\Config\DefaultEngine.ini"
if (-not (Test-Path $GameIni)) { throw "DefaultEngine.ini wasn't in the pak" }

New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot "Config") | Out-Null
python (Join-Path $PSScriptRoot "Scripts\make_engine_ini.py") $GameIni (Join-Path $PSScriptRoot "Config\DefaultEngine.ini") $Map
if ($LASTEXITCODE -ne 0) { throw "make_engine_ini.py failed" }
Write-Host "The game's full configs are in $Tmp if you want to look at them."
