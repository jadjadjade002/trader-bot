$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent; $src=Join-Path $root '.mt5-v18.local'; $lab=Join-Path $root '.mt5-v19.local'; $exe=Join-Path $lab 'terminal64.exe'
if(!(Test-Path -LiteralPath (Join-Path $src 'terminal64.exe'))) { throw 'Run prepare_v18_tester.ps1 first to obtain the isolated local MT5 tester runtime.' }
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe) { throw 'The isolated v19 tester is running.' }
New-Item -ItemType Directory -Force -Path (Join-Path $lab 'MQL5\Experts'),(Join-Path $lab 'MQL5\Profiles\Tester'),(Join-Path $lab 'Config'),(Join-Path $lab 'reports') | Out-Null
foreach($file in @('terminal64.exe','metatester64.exe')) { Copy-Item -LiteralPath (Join-Path $src $file) -Destination $lab -Force }
foreach($file in @('accounts.dat','servers.dat','common.ini')) { $source=Join-Path $src "Config\$file"; if(Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $lab 'Config') -Force } }
$cachePaths=@(
 'bases\MetaQuotes-Demo\history\XAUUSD',
 'bases\MetaQuotes-Demo\ticks\XAUUSD',
 'Tester\bases\MetaQuotes-Demo\history\XAUUSD'
)
foreach($relativePath in $cachePaths)
{
 $cacheSource=Join-Path $src $relativePath
 $cacheDestination=Join-Path $lab $relativePath
 if(!(Test-Path -LiteralPath $cacheSource -PathType Container)) { throw "Required isolated XAUUSD cache was not found: $cacheSource" }
 New-Item -ItemType Directory -Path $cacheDestination -Force | Out-Null
 Get-ChildItem -LiteralPath $cacheSource -Force | Copy-Item -Destination $cacheDestination -Recurse -Force
}
Write-Output "Isolated v19 tester prepared from the v18 local lab at $lab. No live terminal or VM files were changed."
