param(
    [ValidateSet('QuantumTitan_v17')][string]$Expert='QuantumTitan_v17',
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name='v17_development',
    [string]$From='2026.08.03', [string]$To='2026.08.22',
    [ValidateRange(0,3)][int]$SetupMode=0,
    [ValidateRange(0,2)][int]$StopMode=2,
    [int]$DelayMs=200,
    [double]$Deposit=50,
    [bool]$WaitForCompletion=$true,
    [ValidateRange(10,600)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v17.local'
$exe=Join-Path $lab 'terminal64.exe'
if(!(Test-Path -LiteralPath $exe)) { throw 'Run prepare_v17_tester.ps1 first.' }
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe) {
    throw 'Isolated tester is already running. Wait for it to finish.'
}
Copy-Item -LiteralPath (Join-Path $root ($Expert+'.ex5')) -Destination (Join-Path $lab 'MQL5\Experts')
# Freeze every v17 input in the generated set file. Do not inherit a terminal's
# last-used settings, which can silently turn a test into a different strategy.
$settings=@"
InpMaxSpreadPoints=35.0
InpCooldownSeconds=30
InpMaxHoldingMinutes=10
InpDeviationPoints=20
InpSetupMode=$SetupMode
InpStopMode=$StopMode
InpFixedTargetPoints=120.0
InpFixedStopPoints=180.0
InpStopATR=1.2
InpMinStopPoints=140.0
InpMaxStopPoints=350.0
InpRewardRisk=0.8
InpMinTargetPoints=100.0
InpMaxSpreadTargetFraction=0.35
InpUseFastBreakeven=true
InpBreakevenTriggerPts=55.0
InpLockPoints=10.0
InpBreakevenR=0.5
InpUseMicroTrailing=true
InpTrailingTriggerPts=80.0
InpTrailingDistancePts=40.0
InpUseMacroFilter=false
InpMacroPeriod=20
InpAllowedHours=3-4,8-9,12-16,18-20
InpSessionStartHour=0
InpSessionEndHour=0
InpWriteJournal=true
"@
$settings | Set-Content -LiteralPath (Join-Path $lab 'MQL5\Profiles\Tester\v17_run.set') -Encoding Unicode
$fingerprintFiles=@(
    (Join-Path $root 'QuantumTitan_v17.mq5'),
    (Join-Path $root 'QuantumTitan_v17.ex5'),
    (Join-Path $root 'Include\QuantumTitan\V17Signal.mqh'),
    (Join-Path $root 'tests\V17SignalTests.mqh')
)
$metadata=[ordered]@{
    name=$Name; expert=$Expert; from=$From; to=$To; setupMode=$SetupMode; stopMode=$StopMode
    deposit=$Deposit; delayMs=$DelayMs; createdAt=(Get-Date).ToUniversalTime().ToString('o')
    sha256=@{}
}
foreach($file in $fingerprintFiles) { $metadata.sha256[(Split-Path $file -Leaf)]=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $lab ("reports\$Name.metadata.json")) -Encoding UTF8
$model=4
$config=@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=$Expert.ex5
ExpertParameters=v17_run.set
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=$model
ExecutionMode=$DelayMs
Optimization=0
FromDate=$From
ToDate=$To
Report=reports\$Name.htm
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@
$path=Join-Path $lab 'run.ini'
$config | Set-Content -LiteralPath $path -Encoding Unicode
$startedAt=[datetime]::UtcNow
$tester=Start-Process -FilePath $exe -ArgumentList '/portable',"/config:$path" -WindowStyle Hidden -PassThru
$report=Join-Path $lab ("reports\$Name.htm")
if(!$WaitForCompletion) {
    Write-Output "Started $Name ($Expert mode $SetupMode); PID $($tester.Id). Report: $report"
    exit 0
}
try { Wait-Process -Id $tester.Id -Timeout $TimeoutSeconds -ErrorAction Stop }
catch { throw "Tester did not finish within $TimeoutSeconds seconds. It remains isolated at PID $($tester.Id)." }
if(!(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -eq 0) {
    throw "Tester exited without report: $report"
}
if((Get-Item -LiteralPath $report).LastWriteTimeUtc -lt $startedAt.AddSeconds(-2)) {
    throw "Tester did not refresh the report for this run: $report"
}
Write-Output "Completed $Name. Report: $report"
Write-Output "Metadata: $lab\reports\$Name.metadata.json"
