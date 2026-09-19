param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$From,
    [Parameter(Mandatory=$true)][string]$To,
    [string]$ExpertName='QuantumTitan_v16_3_Precision',
    [string]$BinaryPath='',
    [double]$Deposit=100.0,
    [int]$ExecutionMode=200,
    [double]$TakeProfitPoints=220.0,
    [double]$StopLossPoints=220.0,
    [double]$BreakevenTriggerPts=130.0,
    [double]$BreakevenLockPts=20.0,
    [double]$MaxSpreadPoints=35.0,
    [int]$CooldownBars=2,
    [bool]$RequireMomentumExpansion=$false
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lab = Join-Path $root '.mt5-v16_1.local'
$terminal = Join-Path $lab 'terminal64.exe'
$binary = if ($BinaryPath) { $BinaryPath } else { Join-Path $root "$ExpertName.ex5" }
$expertBinary = Join-Path $lab "MQL5\Experts\$ExpertName.ex5"
$reportRelative = "reports\$Name.htm"
$report = Join-Path $lab $reportRelative
$config = Join-Path $lab "tester_$Name.ini"

if (!(Test-Path -LiteralPath $terminal)) { throw "Missing isolated terminal: $terminal" }
if (!(Test-Path -LiteralPath $binary)) { throw "Missing candidate binary: $binary" }

Copy-Item -LiteralPath $binary -Destination $expertBinary -Force
if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report -Force }

$ini = @"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=$ExpertName.ex5
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=$ExecutionMode
Optimization=0
FromDate=$From
ToDate=$To
ForwardMode=0
Report=$reportRelative
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
[TesterInputs]
InpTakeProfitPoints=$TakeProfitPoints||$TakeProfitPoints||1||$TakeProfitPoints||N
InpStopLossPoints=$StopLossPoints||$StopLossPoints||1||$StopLossPoints||N
InpBreakevenTriggerPts=$BreakevenTriggerPts||$BreakevenTriggerPts||1||$BreakevenTriggerPts||N
InpBreakevenLockPts=$BreakevenLockPts||$BreakevenLockPts||1||$BreakevenLockPts||N
InpMaxSpreadPoints=$MaxSpreadPoints||$MaxSpreadPoints||1||$MaxSpreadPoints||N
InpCooldownBars=$CooldownBars||$CooldownBars||1||$CooldownBars||N
InpRequireMomentumExpansion=$($RequireMomentumExpansion.ToString().ToLower())||false||0||true||N
"@

$ini | Set-Content -LiteralPath $config -Encoding Unicode
$process = Start-Process -FilePath $terminal -ArgumentList '/portable', "/config:$config" -PassThru
if (!$process.WaitForExit(240000)) {
    $process.Kill()
    throw "Tester timeout after 240 seconds: $Name"
}
if (!(Test-Path -LiteralPath $report)) { throw "Tester report missing: $report" }
Write-Output $report
