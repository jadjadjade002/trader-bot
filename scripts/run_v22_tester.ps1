param(
    [string]$Expert='QuantumTitan_v22_Swing',
    [string]$Timeframe='M15',
    [string]$From='2026.05.03',
    [string]$To='2026.08.14',
    [double]$Deposit=100.0,
    [int]$Model=1,
    [int]$TimeoutSeconds=600
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v16_1.local'
$terminalExe=Join-Path $lab 'terminal64.exe'

Write-Output "=== Running Tester: $Expert on $Timeframe ($From to $To, Model: $Model) ==="
$iniPath = Join-Path $lab ("tester_run_" + $Expert + "_" + $Timeframe + ".ini")
$reportName = ($Expert.ToLower() + "_" + $Timeframe.ToLower() + "_" + $From.Replace('.','') + "_" + $To.Replace('.',''))
$reportRel = "reports\" + $reportName + ".htm"
$reportAbs = Join-Path $lab $reportRel

if(Test-Path -LiteralPath $reportAbs) {
    Remove-Item -LiteralPath $reportAbs -Force
}

$iniContent = @"
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
Symbol=XAUUSD
Period=$Timeframe
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=$Model
ExecutionMode=0
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
"@
$iniContent | Set-Content -LiteralPath $iniPath -Encoding Unicode

$luPattern = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\*\liveupdate"
Get-Item -Path $luPattern -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

$proc = Start-Process -FilePath $terminalExe -ArgumentList '/portable','/skipupdate',"/config:$iniPath" -PassThru
$start = Get-Date
while(!$proc.HasExited) {
    Start-Sleep -Seconds 2
    $elapsed = (Get-Date) - $start
    if($elapsed.TotalSeconds -gt $TimeoutSeconds) {
        $proc.Kill()
        throw "Tester run timed out after $TimeoutSeconds seconds for $Expert on $Timeframe."
    }
}

if(Test-Path -LiteralPath $reportAbs) {
    Write-Output "Success: Report generated at $reportAbs"
} else {
    Write-Warning "Report was not generated. Checking logs..."
}
