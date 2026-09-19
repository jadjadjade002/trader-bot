param([string]$MetaEditor='C:\Program Files\MetaTrader 5\metaeditor64.exe')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$source=Join-Path $root 'QuantumTitan_M1Export.mq5'
$binary=Join-Path $root 'QuantumTitan_M1Export.ex5'
$log=Join-Path $root 'data_export_compile.log'
$manifestPath=Join-Path $root 'compiled\QuantumTitan_M1Export.build.json'
if(!(Test-Path -LiteralPath $MetaEditor)){throw "MetaEditor was not found: $MetaEditor"}
if(!(Test-Path -LiteralPath $source)){throw "Source was not found: $source"}
$before=if(Test-Path -LiteralPath $binary){(Get-Item -LiteralPath $binary).LastWriteTimeUtc}else{[datetime]::MinValue}
New-Item -ItemType Directory -Path (Split-Path $manifestPath -Parent) -Force|Out-Null
if(Test-Path -LiteralPath $log){Remove-Item -LiteralPath $log -Force}
$started=[datetime]::UtcNow
$process=Start-Process -FilePath $MetaEditor -ArgumentList "/compile:$source","/log:$log" -WindowStyle Hidden -PassThru -Wait
if(!(Test-Path -LiteralPath $log)){throw "MetaEditor did not create a compile log: $log"}
if((Get-Item -LiteralPath $log).LastWriteTimeUtc -lt $started.AddSeconds(-2)){throw "MetaEditor did not refresh the compile log: $log"}
$result=Get-Content -LiteralPath $log -Raw
if($result -notmatch 'Result:\s*0 errors,\s*0 warnings'){throw "Data exporter compilation failed. MetaEditor exit code $($process.ExitCode). See $log"}
if(!(Test-Path -LiteralPath $binary) -or (Get-Item -LiteralPath $binary).LastWriteTimeUtc -le $before){throw 'Data exporter binary was not freshly produced.'}
$manifest=[ordered]@{source=(Get-FileHash $source -Algorithm SHA256).Hash;binary=(Get-FileHash $binary -Algorithm SHA256).Hash;compiledAt=(Get-Date).ToUniversalTime().ToString('o')}
$manifest|ConvertTo-Json|Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output 'QuantumTitan_M1Export compiled with 0 errors and 0 warnings.'
