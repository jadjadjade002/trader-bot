$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$src=Join-Path $root '.mt5-v20.local'
$lab=Join-Path $root '.mt5-v2167.local'
$exe=Join-Path $lab 'terminal64.exe'
if(!(Test-Path -LiteralPath (Join-Path $src 'terminal64.exe'))){throw 'The isolated v20 tester runtime was not found.'}
if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe){throw 'The isolated v21.67 tester is running.'}
$dirs=@('MQL5\Experts','MQL5\Profiles\Tester','Config','reports')
foreach($dir in $dirs){New-Item -ItemType Directory -Path (Join-Path $lab $dir) -Force|Out-Null}
foreach($file in @('terminal64.exe','metatester64.exe')){Copy-Item -LiteralPath (Join-Path $src $file) -Destination $lab -Force}
# The native tester requires the encrypted cached demo account context. Copy only
# accounts.dat and server discovery, then construct a minimal account selector;
# never copy charts, Experts, presets, or the complete personal common.ini.
$accounts=Join-Path $src 'Config\accounts.dat'
if(!(Test-Path -LiteralPath $accounts)){throw 'The isolated source lab has no cached demo tester account.'}
Copy-Item -LiteralPath $accounts -Destination (Join-Path $lab 'Config\accounts.dat') -Force
$servers=Join-Path $src 'Config\servers.dat'
if(Test-Path -LiteralPath $servers){Copy-Item -LiteralPath $servers -Destination (Join-Path $lab 'Config\servers.dat') -Force}
$sourceCommon=Join-Path $src 'Config\common.ini'
$loginLine=Get-Content -LiteralPath $sourceCommon|Where-Object{$_-match'^Login=\d+$'}|Select-Object -First 1
$serverLine=Get-Content -LiteralPath $sourceCommon|Where-Object{$_-match'^Server=.+'}|Select-Object -First 1
if([string]::IsNullOrWhiteSpace($loginLine)-or[string]::IsNullOrWhiteSpace($serverLine)){throw 'Cached demo tester account selection was not found.'}
@("[Common]",$loginLine,$serverLine,'KeepPrivate=1')|Set-Content -LiteralPath (Join-Path $lab 'Config\common.ini') -Encoding Unicode
$cachePaths=@('bases\MetaQuotes-Demo\history\XAUUSD','bases\MetaQuotes-Demo\ticks\XAUUSD','Tester\bases\MetaQuotes-Demo\history\XAUUSD')
foreach($relative in $cachePaths){
 $from=Join-Path $src $relative;$to=Join-Path $lab $relative
 if(!(Test-Path -LiteralPath $from -PathType Container)){throw "Required isolated XAUUSD cache was not found: $from"}
 New-Item -ItemType Directory -Path $to -Force|Out-Null
 Get-ChildItem -LiteralPath $from -Force|Copy-Item -Destination $to -Recurse -Force
}
Write-Output "Isolated tester-only v21.67 lab prepared at $lab with encrypted cached demo test authentication; no personal profiles, live terminals, or VM files were touched."
