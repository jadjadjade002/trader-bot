param(
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name='v18_development',
 [string]$From='2026.08.03',[string]$To='2026.08.22',
 [int]$DelayMs=200,[double]$Deposit=50,[bool]$WaitForCompletion=$true,
 [ValidateRange(10,600)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; $lab=Join-Path $root '.mt5-v18.local'; $exe=Join-Path $lab 'terminal64.exe'
if(!(Test-Path -LiteralPath $exe)) { throw 'Run prepare_v18_tester.ps1 first.' }
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe) { throw 'Isolated v18 tester is already running.' }
Copy-Item -LiteralPath (Join-Path $root 'QuantumTitan_v18.ex5') -Destination (Join-Path $lab 'MQL5\Experts') -Force
$reportsDir=Join-Path $lab 'reports'
New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
$reportArtifacts=@(
 (Join-Path $reportsDir "$Name.htm"),
 (Join-Path $reportsDir "$Name.html"),
 (Join-Path $reportsDir "$Name.json"),
 (Join-Path $reportsDir "$Name.metadata.json"),
 (Join-Path $reportsDir "$Name.png"),
 (Join-Path $reportsDir "$Name.gif"),
 (Join-Path $reportsDir "$Name-holding.png"),
 (Join-Path $reportsDir "$Name-hst.png"),
 (Join-Path $reportsDir "$Name-mfemae.png")
)
foreach($artifact in $reportArtifacts) { if(Test-Path -LiteralPath $artifact) { Remove-Item -LiteralPath $artifact -Force } }
$settings=@"
InpMaxSpreadPoints=40.0
InpCooldownSeconds=60
InpMaxHoldingMinutes=8
InpDeviationPoints=20
InpStopATR=1.2
InpStopBufferATR=0.15
InpMaxStopPoints=450.0
InpRewardRisk=0.75
InpMinTargetPoints=100.0
InpMaxSpreadTargetFraction=0.25
InpBreakevenR=0.70
InpLockPoints=10.0
InpSessionStartHour=18
InpSessionEndHour=2
InpWriteJournal=true
"@
$settings | Set-Content -LiteralPath (Join-Path $lab 'MQL5\Profiles\Tester\v18_run.set') -Encoding Unicode
$files=@((Join-Path $root 'QuantumTitan_v18.mq5'),(Join-Path $root 'QuantumTitan_v18.ex5'),(Join-Path $root 'Include\QuantumTitan\V18Signal.mqh'),(Join-Path $root 'tests\V18SignalTests.mqh')); $meta=[ordered]@{name=$Name;from=$From;to=$To;deposit=$Deposit;delayMs=$DelayMs;sha256=@{}}
foreach($file in $files) {$meta.sha256[(Split-Path $file -Leaf)]=(Get-FileHash $file -Algorithm SHA256).Hash}; $meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $lab "reports\$Name.metadata.json") -Encoding UTF8
$config=@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=QuantumTitan_v18.ex5
ExpertParameters=v18_run.set
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
Report=reports\$Name.htm
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@
$path=Join-Path $lab 'run.ini'; $config | Set-Content -LiteralPath $path -Encoding Unicode; $started=[datetime]::UtcNow; $p=Start-Process -FilePath $exe -ArgumentList '/portable',"/config:$path" -WindowStyle Hidden -PassThru
if(!$WaitForCompletion) { Write-Output "Started $Name PID $($p.Id)"; exit 0 }
$report=Join-Path $lab "reports\$Name.htm"
$deadline=[datetime]::UtcNow.AddSeconds($TimeoutSeconds)
$completed=$false
while([datetime]::UtcNow -lt $deadline)
{
 $labProcesses=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe)
 if(Test-Path -LiteralPath $report)
 {
  $reportItem=Get-Item -LiteralPath $report
  if($reportItem.Length -gt 0 -and $reportItem.LastWriteTimeUtc -ge $started.AddSeconds(-2) -and $labProcesses.Count -eq 0) { $completed=$true; break }
 }
 Start-Sleep -Milliseconds 250
}
if(!$completed)
{
 $cleanupDeadline=[datetime]::UtcNow.AddSeconds(5)
 do
 {
  $remaining=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe)
  foreach($process in $remaining) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
  if($remaining.Count -gt 0) { Start-Sleep -Milliseconds 200 }
 } while($remaining.Count -gt 0 -and [datetime]::UtcNow -lt $cleanupDeadline)
 $remaining=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe)
 if($remaining.Count -eq 0) { throw "v18 tester timed out after $TimeoutSeconds seconds; isolated lab processes were stopped." }
 $remainingIds=($remaining.Id -join ',')
 throw "v18 tester timed out after $TimeoutSeconds seconds; shutdown could not be verified for isolated lab PID(s): $remainingIds"
}
Write-Output "Completed $Name. Report: $report"
