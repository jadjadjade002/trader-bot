param(
    [string]$From='2026.08.03',
    [string]$To='2026.08.08',
    [double]$Deposit=100.0
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v16_1.local'
$terminalExe=Join-Path $lab 'terminal64.exe'

if(!(Test-Path -LiteralPath $terminalExe)) {
    throw "Terminal executable missing in $lab. Run prepare_v16_1_tester.ps1 first."
}

function Run-Tester-Run([string]$expertName, [string]$reportName) {
    Write-Output "=== Running Tester for $expertName ($From to $To) ==="
    $iniPath = Join-Path $lab ("tester_" + $expertName + ".ini")
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
Expert=$expertName.ex5
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
"@
    $iniContent | Set-Content -LiteralPath $iniPath -Encoding UTF8

    $proc = Start-Process -FilePath $terminalExe -ArgumentList "/config:$iniPath" -PassThru
    $start = Get-Date
    while(!$proc.HasExited) {
        Start-Sleep -Seconds 2
        $elapsed = (Get-Date) - $start
        if($elapsed.TotalSeconds -gt 180) {
            $proc.Kill()
            throw "Tester run timed out after 180 seconds for $expertName."
        }
    }

    if(Test-Path -LiteralPath $reportAbs) {
        Write-Output "Success: Report generated at $reportAbs"
    } else {
        Write-Warning "Report was not generated for $expertName. Checking tester logs..."
        $logDir = Join-Path $lab 'Tester\logs'
        if(Test-Path $logDir) {
            Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Get-Content $_.FullName -Tail 20 }
        }
    }
}

# Run V16 Velocity Baseline
Run-Tester-Run 'QuantumTitan_v16_Velocity' 'v16_velocity_baseline'

# Run V16.1 M1 Candidate
Run-Tester-Run 'QuantumTitan_v16_1_M1' 'v16_1_m1_candidate'

Write-Output "Tester comparison completed."
