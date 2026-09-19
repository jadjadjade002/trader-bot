param(
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name='v20_development',
 [string]$From='2026.08.03',[string]$To='2026.08.22',
 [double]$Deposit=50,[bool]$WaitForCompletion=$true,
 [ValidateRange(10,600)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop';$root=Split-Path $PSScriptRoot -Parent;$lab=Join-Path $root '.mt5-v20.local';$exe=Join-Path $lab 'terminal64.exe';$delayMs=200
if(!(Test-Path -LiteralPath $exe)){throw 'Run prepare_v20_tester.ps1 first.'};if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe){throw 'Isolated v20 tester is already running.'}
$manifestPath=Join-Path $root 'compiled\QuantumTitan_v20.build.json';if(!(Test-Path -LiteralPath $manifestPath)){throw "Compiled v20 manifest was not found: $manifestPath"};$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
$hashFiles=[ordered]@{source=(Join-Path $root 'QuantumTitan_v20.mq5');binary=(Join-Path $root 'QuantumTitan_v20.ex5');signalHeader=(Join-Path $root 'Include\QuantumTitan\V20Signal.mqh');signalTests=(Join-Path $root 'tests\V20SignalTests.mqh')}
foreach($key in $hashFiles.Keys){$expected=$manifest.PSObject.Properties[$key].Value;$actual=(Get-FileHash -LiteralPath $hashFiles[$key] -Algorithm SHA256).Hash;if([string]::IsNullOrWhiteSpace($expected) -or $actual -ne $expected){throw "Compiled v20 manifest hash mismatch for $key."}}
Copy-Item -LiteralPath (Join-Path $root 'QuantumTitan_v20.ex5') -Destination (Join-Path $lab 'MQL5\Experts') -Force;$reportsDir=Join-Path $lab 'reports';New-Item -ItemType Directory -Path $reportsDir -Force|Out-Null
foreach($artifact in @((Join-Path $reportsDir "$Name.htm"),(Join-Path $reportsDir "$Name.html"),(Join-Path $reportsDir "$Name.json"),(Join-Path $reportsDir "$Name.metadata.json"),(Join-Path $reportsDir "$Name.png"),(Join-Path $reportsDir "$Name.gif"),(Join-Path $reportsDir "$Name-holding.png"),(Join-Path $reportsDir "$Name-hst.png"),(Join-Path $reportsDir "$Name-mfemae.png"))){if(Test-Path -LiteralPath $artifact){Remove-Item -LiteralPath $artifact -Force}}
$settings=@"
InpMaxSpreadPoints=40.0
InpCooldownSeconds=60
InpMaxHoldingMinutes=3
InpDeviationPoints=20
InpSignalExpirySeconds=10
InpStopATR=1.0
InpTargetATR=1.0
InpMaxStopPoints=450.0
InpMaxSpreadTargetFraction=0.20
InpSessionStartHour=18
InpSessionEndHour=2
InpEntryCutoffHour=1
InpEntryCutoffMinute=57
InpWriteJournal=true
"@;$settings|Set-Content -LiteralPath (Join-Path $lab 'MQL5\Profiles\Tester\v20_run.set') -Encoding Unicode
$files=@((Join-Path $root 'QuantumTitan_v20.mq5'),(Join-Path $root 'QuantumTitan_v20.ex5'),(Join-Path $root 'Include\QuantumTitan\V20Signal.mqh'),(Join-Path $root 'tests\V20SignalTests.mqh'));$meta=[ordered]@{name=$Name;from=$From;to=$To;deposit=$Deposit;delayMs=$delayMs;model=4;sha256=@{}};foreach($file in $files){$meta.sha256[(Split-Path $file -Leaf)]=(Get-FileHash $file -Algorithm SHA256).Hash};$meta|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $reportsDir "$Name.metadata.json") -Encoding UTF8
$config=@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=QuantumTitan_v20.ex5
ExpertParameters=v20_run.set
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=$delayMs
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
"@;$path=Join-Path $lab 'run.ini';$config|Set-Content -LiteralPath $path -Encoding Unicode;$started=[datetime]::UtcNow;$process=Start-Process -FilePath $exe -ArgumentList '/portable',"/config:$path" -WindowStyle Hidden -PassThru
if(!$WaitForCompletion){Write-Output "Started $Name PID $($process.Id)";exit 0};$report=Join-Path $reportsDir "$Name.htm";$deadline=[datetime]::UtcNow.AddSeconds($TimeoutSeconds);$completed=$false
while([datetime]::UtcNow-lt$deadline){$labProcesses=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe);if(Test-Path -LiteralPath $report){$item=Get-Item -LiteralPath $report;if($item.Length-gt 0-and$item.LastWriteTimeUtc-ge$started.AddSeconds(-2)-and$labProcesses.Count-eq 0){$completed=$true;break}};Start-Sleep -Milliseconds 250}
if(!$completed){$cleanupDeadline=[datetime]::UtcNow.AddSeconds(5);do{$remaining=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe);foreach($item in $remaining){Stop-Process -Id $item.Id -Force -ErrorAction SilentlyContinue};if($remaining.Count-gt 0){Start-Sleep -Milliseconds 200}}while($remaining.Count-gt 0-and[datetime]::UtcNow-lt$cleanupDeadline);$remaining=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe);if($remaining.Count-eq 0){throw "v20 tester timed out after $TimeoutSeconds seconds; isolated lab processes were stopped."};throw "v20 tester timed out after $TimeoutSeconds seconds; shutdown could not be verified for isolated lab PID(s): $($remaining.Id -join ',')"}
$nativeReport=Get-Content -LiteralPath $report -Raw;$expertMatch=$nativeReport-match '(?is)Expert:</td>\s*<td[^>]*>\s*<b>\s*QuantumTitan_v20\s*</b>';$symbolMatch=$nativeReport-match '(?is)Symbol:</td>\s*<td[^>]*>\s*<b>\s*XAUUSD\s*</b>';$periodMatch=$nativeReport-match '(?is)Period:</td>\s*<td[^>]*>\s*<b>\s*M1(?:\s|\()';$barsMatch=[regex]::Match($nativeReport,'(?is)Bars:</td>\s*<td[^>]*>\s*<b>\s*([0-9 ]+)\s*</b>');$bars=if($barsMatch.Success){[int64]($barsMatch.Groups[1].Value-replace ' ','')}else{0};$historyMatch=[regex]::Match($nativeReport,'(?is)History Quality:</td>\s*<td[^>]*>\s*<b>\s*([^<]+)\s*</b>');$historyUnavailable=(!$historyMatch.Success)-or$historyMatch.Groups[1].Value.Trim()-eq'n/a';if(!$expertMatch-or!$symbolMatch-or!$periodMatch-or$bars-le 0-or$historyUnavailable){throw "v20 native report identity/history validation failed: $report"};Write-Output "Completed $Name. Report: $report"
