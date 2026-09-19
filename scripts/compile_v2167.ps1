param([string]$MetaEditor='C:\Program Files\MetaTrader 5\metaeditor64.exe')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$source=Join-Path $root 'QuantumTitan_v2167.mq5'
$binary=Join-Path $root 'QuantumTitan_v2167.ex5'
$log=Join-Path $root 'v2167_compile.log'
$dependencies=[ordered]@{
 source=$source
 signalHeader=(Join-Path $root 'Include\QuantumTitan\V2167Signal.mqh')
 signalTests=(Join-Path $root 'tests\V2167SignalTests.mqh')
 protocol=(Join-Path $root 'docs\V2167_PROTOCOL.md')
 evaluator=(Join-Path $root 'research\v2167_evaluate.py')
 reportParser=(Join-Path $root 'scripts\analyze_v17_report.py')
 evaluatorTests=(Join-Path $root 'tests\test_v2167_evaluate.py')
 compileHarness=(Join-Path $root 'scripts\compile_v2167.ps1')
 prepareHarness=(Join-Path $root 'scripts\prepare_v2167_tester.ps1')
 runHarness=(Join-Path $root 'scripts\run_v2167_test.ps1')
}
if(!(Test-Path -LiteralPath $MetaEditor)){throw "MetaEditor was not found: $MetaEditor"}
foreach($item in $dependencies.GetEnumerator()){if(!(Test-Path -LiteralPath $item.Value)){throw "Required v21.67 dependency was not found: $($item.Value)"}}
$before=if(Test-Path -LiteralPath $binary){(Get-Item -LiteralPath $binary).LastWriteTimeUtc}else{[datetime]::MinValue}
$compiledDir=Join-Path $root 'compiled';New-Item -ItemType Directory -Path $compiledDir -Force|Out-Null
if(Test-Path -LiteralPath $log){Remove-Item -LiteralPath $log -Force}
$started=[datetime]::UtcNow
$process=Start-Process -FilePath $MetaEditor -ArgumentList "/compile:$source","/log:$log" -WindowStyle Hidden -PassThru -Wait
if(!(Test-Path -LiteralPath $log)){throw "MetaEditor did not create a compile log: $log"}
if((Get-Item -LiteralPath $log).LastWriteTimeUtc-lt$started.AddSeconds(-2)){throw "MetaEditor did not refresh the compile log: $log"}
$result=Get-Content -LiteralPath $log -Raw
if($result-notmatch'Result:\s*0 errors,\s*0 warnings'){throw "v21.67 compilation failed. MetaEditor exit code $($process.ExitCode). See $log"}
if(!(Test-Path -LiteralPath $binary)-or(Get-Item -LiteralPath $binary).LastWriteTimeUtc-le$before){throw 'v21.67 binary was not freshly produced.'}
$hashes=[ordered]@{}
foreach($item in $dependencies.GetEnumerator()){$hashes[$item.Key]=(Get-FileHash -LiteralPath $item.Value -Algorithm SHA256).Hash}
$hashes.binary=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash
$manifest=[ordered]@{schemaVersion=1;version='21.67';magic=992167;compiledAt=(Get-Date).ToUniversalTime().ToString('o');files=$hashes}
$manifest|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $compiledDir 'QuantumTitan_v2167.build.json') -Encoding UTF8
Write-Output 'QuantumTitan_v2167 compiled with 0 errors and 0 warnings; dependency hashes recorded.'
