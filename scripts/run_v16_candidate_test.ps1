param(
    [ValidateSet('QuantumTitan_v16_57_SafetyHotfix','QuantumTitan_v16_58_EvidenceLab')]
    [string]$Expert = 'QuantumTitan_v16_58_EvidenceLab',
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name = 'v1658_candidate',
    [string]$From = '2026.08.03',
    [string]$To = '2026.08.21',
    [ValidateRange(0,4)][int]$EntryMode = 1,
    [ValidateRange(0,3)][int]$ExitMode = 1,
    [ValidateRange(0.0,1.0)][double]$MinBodyRatio = 0.20,
    [ValidateRange(0.0,500.0)][double]$MinM5Separation = 20.0,
    [bool]$MomentumAcceleration = $false,
    [ValidateRange(0,5000)][int]$DelayMs = 200,
    [ValidateRange(10.0,1000000.0)][double]$Deposit = 60.0,
    [ValidateRange(30,1800)][int]$TimeoutSeconds = 600
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lab = Join-Path $root '.mt5-v17.local'
$terminal = Join-Path $lab 'terminal64.exe'
$source = Join-Path $root ($Expert + '.mq5')
$binary = Join-Path $root ($Expert + '.ex5')
$report = Join-Path $lab ("reports\$Name.htm")
$metadataPath = Join-Path $lab ("reports\$Name.metadata.json")
$setName = "$Name.set"
$setPath = Join-Path $lab ("MQL5\Profiles\Tester\$setName")
$iniPath = Join-Path $lab ("run_$Name.ini")

if (!(Test-Path -LiteralPath $terminal)) { throw "Missing isolated tester: $terminal" }
if (!(Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
if (!(Test-Path -LiteralPath $binary)) { throw "Missing binary: $binary" }
if (Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $terminal) {
    throw 'Isolated tester terminal is already running.'
}

New-Item -ItemType Directory -Path (Split-Path $report -Parent) -Force | Out-Null
Copy-Item -LiteralPath $binary -Destination (Join-Path $lab "MQL5\Experts\$Expert.ex5") -Force
if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report -Force }

$settings = @"
InpDemoOnly=true
InpTargetAccount=0
InpMagicNumber=991658
InpMaxSpreadPoints=45.0
InpUseNewsFilter=false
InpEnableLiquiditySweep=true
InpSweepLookbackBars=30
InpEnableFVG=true
InpWickRatioThreshold=0.30
InpStrictTrendSweepLock=true
InpFastEmaPeriod=14
InpSlowEmaPeriod=50
InpM5FastEmaPeriod=20
InpM5SlowEmaPeriod=50
InpMaxDistanceEmaPoints=40.0
InpBBLength=20
InpBBMult=2.0
InpKCLength=20
InpKCMult=1.5
InpUseDynamicAtr=true
InpAtrSlMult=1.5
InpAtrTpMult=2.0
InpMaxStopLossPoints=150.0
InpAtrBeTriggerMult=0.8
InpAtrBeLockMult=0.2
InpMinBeTriggerPts=75.0
InpMaxBeTriggerPts=150.0
InpMinBeLockPts=20.0
InpMaxBeLockPts=50.0
InpEnableStagedProfitLock=false
InpMinAtrPoints=50.0
InpMaxAllowedAtrPoints=650.0
InpTakeProfitPoints=220.0
InpStopLossPoints=180.0
InpBreakevenTriggerPts=75.0
InpBreakevenLockPts=20.0
InpCooldownBars=5
InpLossStreakPauseMins=60
InpExitPolicy=$ExitMode
InpDelayedLockTriggerR=1.0
InpDelayedLockR=0.10
InpPeakTrailTriggerR=1.0
InpPeakTrailDistanceR=0.75
InpPullbackEvidenceMode=$EntryMode
InpMinSignalBodyRatio=$MinBodyRatio
InpMinM5EmaSepPoints=$MinM5Separation
InpRequireMomentumAccel=$($MomentumAcceleration.ToString().ToLowerInvariant())
InpMinEfficiencyRatio=0.25
InpBreakoutLookback=12
InpBreakoutRetestBars=5
InpEnableRiskGuardian=true
InpMaxDailyDrawdownPct=5.0
InpMaxDailyLossCash=3.0
InpMaxTradesPerDay=4
InpMaxLosingTradesDay=2
InpFridayLockout=false
InpDailyRolloverLock=true
InpRolloverFlatHour=22
InpRolloverFlatMinute=30
InpRolloverResumeHour=1
InpRolloverResumeMinute=15
InpEnableHUD=false
"@
$settings | Set-Content -LiteralPath $setPath -Encoding Unicode

$metadata = [ordered]@{
    name=$Name; expert=$Expert; from=$From; to=$To; deposit=$Deposit; delayMs=$DelayMs
    entryMode=$EntryMode; exitMode=$ExitMode; minBodyRatio=$MinBodyRatio
    minM5Separation=$MinM5Separation; momentumAcceleration=$MomentumAcceleration
    createdAt=(Get-Date).ToUniversalTime().ToString('o')
    sha256=@{
        source=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
        binary=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash
        settings=(Get-FileHash -LiteralPath $setPath -Algorithm SHA256).Hash
    }
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

$config = @"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=$Expert.ex5
ExpertParameters=$setName
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=$DelayMs
Optimization=0
FromDate=$From
ToDate=$To
ForwardMode=0
Report=reports\$Name.htm
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@
$config | Set-Content -LiteralPath $iniPath -Encoding Unicode
$metadata.sha256.config = (Get-FileHash -LiteralPath $iniPath -Algorithm SHA256).Hash
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

$startedAt = [datetime]::UtcNow
$process = Start-Process -FilePath $terminal -ArgumentList '/portable', "/config:$iniPath" -WindowStyle Hidden -PassThru
try { Wait-Process -Id $process.Id -Timeout $TimeoutSeconds -ErrorAction Stop }
catch {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "Tester timed out after $TimeoutSeconds seconds."
}
if (!(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -eq 0) {
    throw "Tester exited without report: $report"
}
if ((Get-Item -LiteralPath $report).LastWriteTimeUtc -lt $startedAt.AddSeconds(-2)) {
    throw "Stale tester report: $report"
}
Write-Output $report
Write-Output $metadataPath
