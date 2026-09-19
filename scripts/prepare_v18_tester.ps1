$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; $src=Join-Path $root '.mt5-v17.local'; $lab=Join-Path $root '.mt5-v18.local'
if(!(Test-Path -LiteralPath $src)) {throw 'Prepare v17 tester first to obtain the local MT5 tester runtime.'}
New-Item -ItemType Directory -Force -Path (Join-Path $lab 'MQL5\Experts'),(Join-Path $lab 'MQL5\Profiles\Tester'),(Join-Path $lab 'Config'),(Join-Path $lab 'reports') | Out-Null
foreach($file in @('terminal64.exe','metatester64.exe')) {Copy-Item -LiteralPath (Join-Path $src $file) -Destination $lab -Force}
foreach($file in @('accounts.dat','servers.dat','common.ini')) {if(Test-Path (Join-Path $src "Config\$file")){Copy-Item -LiteralPath (Join-Path $src "Config\$file") -Destination (Join-Path $lab 'Config') -Force}}
Write-Output "Isolated v18 tester prepared at $lab. No live terminal or VM files were changed."
