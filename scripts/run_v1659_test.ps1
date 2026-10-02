param(
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name = 'v1659_r4',
    [string]$From = '2026.08.03',
    [string]$To = '2026.08.21',
    [ValidateRange(0,5000)][int]$DelayMs = 200,
    [ValidateRange(10.0,1000000.0)][double]$Deposit = 60.0,
    [ValidateRange(30,1800)][int]$TimeoutSeconds = 600,
    [bool]$EmergencyStop = $false
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lab = Join-Path $root '.mt5-v17.local'
$terminal = Join-Path $lab 'terminal64.exe'
$expert = 'QuantumTitan_v16_59_R4StateTransition'
$source = Join-Path $root "$expert.mq5"
$binary = Join-Path $root "$expert.ex5"
$report = Join-Path $lab "reports\$Name.htm"
$setName = "$Name.set"
$setPath = Join-Path $lab "MQL5\Profiles\Tester\$setName"
$iniPath = Join-Path $lab "run_$Name.ini"
$metadataPath = Join-Path $lab "reports\$Name.metadata.json"

if (!(Test-Path $terminal) -or !(Test-Path $source) -or !(Test-Path $binary)) { throw 'Missing tester or V16.59 artifact.' }
if (Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $terminal) { throw 'Isolated tester is already running.' }
Copy-Item $binary (Join-Path $lab "MQL5\Experts\$expert.ex5") -Force
if (Test-Path $report) { Remove-Item $report -Force }
@"
InpTargetAccount=0
InpIndicatorSeedStart=2025.08.11 00:00
InpEmergencyStop=$($EmergencyStop.ToString().ToLowerInvariant())
"@ | Set-Content $setPath -Encoding Unicode
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
"@ | Set-Content $iniPath -Encoding Unicode
$meta = [ordered]@{
    name=$Name; expert=$expert; from=$From; to=$To; delayMs=$DelayMs; deposit=$Deposit
    emergencyStop=$EmergencyStop; createdAt=(Get-Date).ToUniversalTime().ToString('o')
    sha256=@{
        source=(Get-FileHash $source -Algorithm SHA256).Hash
        binary=(Get-FileHash $binary -Algorithm SHA256).Hash
        settings=(Get-FileHash $setPath -Algorithm SHA256).Hash
        config=(Get-FileHash $iniPath -Algorithm SHA256).Hash
    }
}
$meta | ConvertTo-Json -Depth 4 | Set-Content $metadataPath -Encoding UTF8
$startedAt = [datetime]::UtcNow
$process = Start-Process $terminal -ArgumentList '/portable',"/config:$iniPath" -WindowStyle Hidden -PassThru
try { Wait-Process -Id $process.Id -Timeout $TimeoutSeconds -ErrorAction Stop }
catch { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue; throw "Tester timed out after $TimeoutSeconds seconds." }
if (!(Test-Path $report) -or (Get-Item $report).Length -eq 0) { throw "Missing report: $report" }
if ((Get-Item $report).LastWriteTimeUtc -lt $startedAt.AddSeconds(-2)) { throw "Stale report: $report" }
Write-Output $report
Write-Output $metadataPath
