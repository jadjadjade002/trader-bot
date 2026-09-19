param(
 [string]$From='2026.08.03',
 [string]$To='2026.08.04',
 [ValidateRange(30,300)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v20.local'
$exe=Join-Path $lab 'terminal64.exe'
$binary=Join-Path $root 'QuantumTitan_ForwardCollector.ex5'
& (Join-Path $PSScriptRoot 'validate_forward_collector.ps1') -Root $root
if(!(Test-Path -LiteralPath $exe)){throw 'The isolated local tester is not prepared.'}
if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe){throw 'The isolated tester is already running.'}
Copy-Item -LiteralPath $binary -Destination (Join-Path $lab 'MQL5\Experts\QuantumTitan_ForwardCollector.ex5') -Force
$testerRoot=Join-Path $lab 'Tester'
foreach($agent in @(Get-ChildItem -LiteralPath $testerRoot -Directory -Filter 'Agent-*' -ErrorAction SilentlyContinue))
{
 $generated=Join-Path $agent.FullName 'MQL5\Files\QTForward'
 if(Test-Path -LiteralPath $generated){Remove-Item -LiteralPath $generated -Recurse -Force}
}
$report=Join-Path $lab 'reports\forward_collector_test.htm'
if(Test-Path -LiteralPath $report){Remove-Item -LiteralPath $report -Force}
$config=Join-Path $lab 'run_forward_collector_test.ini'
@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=QuantumTitan_ForwardCollector.ex5
Symbol=XAUUSD
Period=M1
Deposit=50
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=200
Optimization=0
FromDate=$From
ToDate=$To
Report=reports\forward_collector_test.htm
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@|Set-Content -LiteralPath $config -Encoding Unicode
$started=[datetime]::UtcNow
Start-Process -FilePath $exe -ArgumentList '/portable','/skipupdate',"/config:$config" -WindowStyle Hidden|Out-Null
$deadline=$started.AddSeconds($TimeoutSeconds)
$complete=$false
while([datetime]::UtcNow-lt$deadline)
{
 $running=@(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe)
 if((Test-Path -LiteralPath $report)-and$running.Count-eq 0){$item=Get-Item -LiteralPath $report;if($item.Length-gt 0-and$item.LastWriteTimeUtc-ge$started.AddSeconds(-2)){$complete=$true;break}}
 Start-Sleep -Milliseconds 250
}
if(!$complete){foreach($item in @(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe)){Stop-Process -Id $item.Id -Force};throw 'Forward collector local test timed out.'}
$outputDirs=@(Get-ChildItem -LiteralPath $testerRoot -Directory -Filter 'Agent-*'|ForEach-Object{Get-Item -LiteralPath (Join-Path $_.FullName 'MQL5\Files\QTForward') -ErrorAction SilentlyContinue}|Where-Object{$_.LastWriteTimeUtc-ge$started.AddSeconds(-2)})
if($outputDirs.Count-ne 1){throw "Expected one fresh QTForward output directory, found $($outputDirs.Count)."}
$barHeader='schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,real_volume,bar_spread_points,open_spread_points,open_bid,open_ask,open_tick_time_msc,close_observed_time_msc,flags'
$healthHeader='schema_version,collector_version,run_id,broker_time_epoch,broker_time_iso,terminal_connected,symbol_synchronized,last_tick_age_seconds,last_closed_bar_epoch,rows_written,duplicate_skips,gap_count,write_errors,status'
$barFiles=@(Get-ChildItem -LiteralPath $outputDirs[0].FullName -File -Filter 'QTForward_XAUUSD_M1_*.csv')
$healthFiles=@(Get-ChildItem -LiteralPath $outputDirs[0].FullName -File -Filter 'QTForward_health_*.csv')
if($barFiles.Count-lt 1-or$healthFiles.Count-lt 1){throw 'Collector did not create both bar and health files.'}
$seen=[System.Collections.Generic.HashSet[long]]::new();$rows=0
foreach($file in $barFiles)
{
 if((Get-Content -LiteralPath $file.FullName -TotalCount 1)-ne$barHeader){throw "Wrong bar schema: $($file.FullName)"}
 foreach($row in @(Import-Csv -LiteralPath $file.FullName))
 {
  $epoch=[long]$row.time_broker_epoch;$openMsc=[long]$row.open_tick_time_msc;$closeMsc=[long]$row.close_observed_time_msc
  if(!$seen.Add($epoch)){throw "Duplicate bar epoch: $epoch"}
  if($openMsc-lt$epoch*1000-or$openMsc-ge($epoch+60)*1000-or$closeMsc-lt($epoch+60)*1000){throw "Invalid observation timing at epoch $epoch"}
  $open=[double]$row.open;$high=[double]$row.high;$low=[double]$row.low;$close=[double]$row.close
  if($low-gt$open-or$low-gt$close-or$high-lt$open-or$high-lt$close){throw "Invalid OHLC at epoch $epoch"}
  if([long]$row.tick_volume-lt 0-or[long]$row.real_volume-lt 0-or[double]$row.bar_spread_points-lt 0-or[double]$row.open_spread_points-lt 0){throw "Negative market field at epoch $epoch"}
  ++$rows
 }
}
if($rows-lt 100){throw "Too few forward bar rows: $rows"}
foreach($file in $healthFiles)
{
 if((Get-Content -LiteralPath $file.FullName -TotalCount 1)-ne$healthHeader){throw "Wrong health schema: $($file.FullName)"}
 foreach($row in @(Import-Csv -LiteralPath $file.FullName)){if($row.status-notin @('HEALTHY','MARKET_IDLE','STALE_TICKS','UNSYNCHRONIZED','WRITE_ERROR','PLANNED_END')){throw "Invalid health status: $($row.status)"}}
}
Write-Output "Forward collector local real-tick test passed: $rows unique observed closed bars; output=$($outputDirs[0].FullName)"
