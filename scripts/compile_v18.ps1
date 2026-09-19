param([string]$MetaEditor='C:\Program Files\MetaTrader 5\metaeditor64.exe')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent; $source=Join-Path $root 'QuantumTitan_v18.mq5'; $binary=Join-Path $root 'QuantumTitan_v18.ex5'; $log=Join-Path $root 'v18_compile.log'
if(!(Test-Path -LiteralPath $MetaEditor)) { throw "MetaEditor was not found: $MetaEditor" }
$before=if(Test-Path -LiteralPath $binary) {(Get-Item -LiteralPath $binary).LastWriteTimeUtc} else {[datetime]::MinValue}
$compiledDir=Join-Path $root 'compiled'
New-Item -ItemType Directory -Path $compiledDir -Force | Out-Null
if(Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
$compileStarted=[datetime]::UtcNow
$process=Start-Process -FilePath $MetaEditor -ArgumentList "/compile:$source","/log:$log" -WindowStyle Hidden -PassThru -Wait
if(!(Test-Path -LiteralPath $log)) { throw "MetaEditor did not create a compile log: $log" }
if((Get-Item -LiteralPath $log).LastWriteTimeUtc -lt $compileStarted.AddSeconds(-2)) { throw "MetaEditor did not refresh the compile log: $log" }
$result=Get-Content -LiteralPath $log -Raw
if($result -notmatch 'Result:\s*0 errors,\s*0 warnings') { throw "v18 compilation failed. MetaEditor exit code $($process.ExitCode). See $log" }
if(!(Test-Path -LiteralPath $binary) -or (Get-Item -LiteralPath $binary).LastWriteTimeUtc -le $before) { throw 'v18 binary was not freshly produced.' }
$manifest=[ordered]@{source=(Get-FileHash $source -Algorithm SHA256).Hash; binary=(Get-FileHash $binary -Algorithm SHA256).Hash; signalHeader=(Get-FileHash (Join-Path $root 'Include\QuantumTitan\V18Signal.mqh') -Algorithm SHA256).Hash; signalTests=(Get-FileHash (Join-Path $root 'tests\V18SignalTests.mqh') -Algorithm SHA256).Hash; compiledAt=(Get-Date).ToUniversalTime().ToString('o')}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $compiledDir 'QuantumTitan_v18.build.json') -Encoding UTF8
Write-Output 'QuantumTitan_v18 compiled with 0 errors and 0 warnings.'
