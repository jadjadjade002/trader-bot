param(
    [string]$MetaEditor='C:\Program Files\MetaTrader 5\metaeditor64.exe'
)

$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$source=Join-Path $root 'QuantumTitan_v17.mq5'
$binary=Join-Path $root 'QuantumTitan_v17.ex5'
$log=Join-Path $root 'v17_compile.log'
if(!(Test-Path -LiteralPath $MetaEditor)) { throw "MetaEditor was not found: $MetaEditor" }
if(!(Test-Path -LiteralPath $source)) { throw "Source was not found: $source" }

$before=if(Test-Path -LiteralPath $binary) { (Get-Item -LiteralPath $binary).LastWriteTimeUtc } else { [datetime]::MinValue }
$process=Start-Process -FilePath $MetaEditor -ArgumentList "/compile:$source","/log:$log" -WindowStyle Hidden -PassThru -Wait
if(!(Test-Path -LiteralPath $log)) { throw "MetaEditor did not create a compile log: $log" }
$result=Get-Content -LiteralPath $log -Raw
if($result -notmatch 'Result:\s*0 errors,\s*0 warnings') {
    throw "Compilation failed or produced warnings. MetaEditor exit code was $($process.ExitCode). See $log"
}
if(!(Test-Path -LiteralPath $binary)) { throw "Compiler reported success but binary is missing: $binary" }
if((Get-Item -LiteralPath $binary).LastWriteTimeUtc -lt $before) { throw "Compiled binary timestamp did not advance: $binary" }

$manifest=[ordered]@{
    source=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    binary=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash
    signalHeader=(Get-FileHash -LiteralPath (Join-Path $root 'Include\QuantumTitan\V17Signal.mqh') -Algorithm SHA256).Hash
    signalTests=(Get-FileHash -LiteralPath (Join-Path $root 'tests\V17SignalTests.mqh') -Algorithm SHA256).Hash
    compiledAt=(Get-Date).ToUniversalTime().ToString('o')
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'compiled\QuantumTitan_v17.build.json') -Encoding UTF8
Write-Output 'QuantumTitan_v17 compiled with 0 errors and 0 warnings.'
