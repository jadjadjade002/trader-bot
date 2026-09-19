param(
    [string]$From='2026.08.03',
    [string]$To='2026.08.08',
    [double]$Deposit=40.0
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v16_1.local'
$terminal=Join-Path $lab 'terminal64.exe'
$expert='QuantumTitan_v22_1_Precision'
Copy-Item (Join-Path $root "$expert.ex5") (Join-Path $lab "MQL5\Experts\$expert.ex5") -Force

foreach($tf in @('M5','M15','H1')) {
    $reportRel="reports\v22_1_precision_$($tf.ToLower()).htm"
    $reportAbs=Join-Path $lab $reportRel
    if(Test-Path $reportAbs){ Remove-Item $reportAbs -Force }
    $ini=Join-Path $lab "tester_v221_$tf.ini"
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
Period=$tf
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
"@ | Set-Content $ini -Encoding Unicode
    $p=Start-Process $terminal -ArgumentList '/portable',"/config:$ini" -PassThru
    if(-not $p.WaitForExit(180000)){ $p.Kill(); throw "Tester timeout: $tf" }
    if(-not (Test-Path $reportAbs)){ throw "Missing report: $reportAbs" }
    Write-Output $reportAbs
}
