param(
    [string]$From = '2026.08.03',
    [string]$To = '2026.08.08',
    [double]$Deposit = 60.0
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lab = Join-Path $root '.mt5-v17.local'
$terminal = Join-Path $lab 'terminal64.exe'
$expert = 'QuantumTitan_v16_57_SafetyHotfix'
$reportRel = 'reports\v16_57_safety_hotfix.htm'
$report = Join-Path $lab $reportRel
$ini = Join-Path $lab 'run_v16_57_safety_hotfix.ini'

if (!(Test-Path -LiteralPath $terminal)) { throw "Missing tester terminal: $terminal" }
Copy-Item (Join-Path $root "$expert.ex5") (Join-Path $lab "MQL5\Experts\$expert.ex5") -Force
if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report -Force }

@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=$expert.ex5
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=200
Optimization=0
FromDate=$From
ToDate=$To
ForwardMode=0
Report=$reportRel
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@ | Set-Content -LiteralPath $ini -Encoding UTF8

$process = Start-Process -FilePath $terminal -ArgumentList '/portable', "/config:$ini" -PassThru
if (!$process.WaitForExit(240000)) {
    $process.Kill()
    throw 'V16.57 tester timed out after 240 seconds.'
}
if (!(Test-Path -LiteralPath $report)) { throw "Tester report missing: $report" }
Write-Output $report
