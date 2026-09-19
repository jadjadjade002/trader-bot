param(
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name='v2167_exposed_engineering',
 [string]$From='2026.08.03',[string]$To='2026.08.22',[double]$Deposit=50,
 [ValidateSet(200,500)][int]$DelayMs=200,[bool]$WaitForCompletion=$true,[string]$Python='',
 [ValidateRange(10,3600)][int]$TimeoutSeconds=600
)
$ErrorActionPreference='Stop';$root=Split-Path $PSScriptRoot -Parent;$lab=Join-Path $root '.mt5-v2167.local';$exe=Join-Path $lab 'terminal64.exe'
if(!(Test-Path -LiteralPath $exe)){throw 'Run prepare_v2167_tester.ps1 first.'}
if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe){throw 'The isolated v21.67 tester is already running.'}
$manifestPath=Join-Path $root 'compiled\QuantumTitan_v2167.build.json';if(!(Test-Path -LiteralPath $manifestPath)){throw 'Compile v21.67 first.'}
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
$paths=[ordered]@{source=(Join-Path $root 'QuantumTitan_v2167.mq5');signalHeader=(Join-Path $root 'Include\QuantumTitan\V2167Signal.mqh');signalTests=(Join-Path $root 'tests\V2167SignalTests.mqh');protocol=(Join-Path $root 'docs\V2167_PROTOCOL.md');evaluator=(Join-Path $root 'research\v2167_evaluate.py');reportParser=(Join-Path $root 'scripts\analyze_v17_report.py');evaluatorTests=(Join-Path $root 'tests\test_v2167_evaluate.py');compileHarness=(Join-Path $root 'scripts\compile_v2167.ps1');prepareHarness=(Join-Path $root 'scripts\prepare_v2167_tester.ps1');runHarness=(Join-Path $root 'scripts\run_v2167_test.ps1');binary=(Join-Path $root 'QuantumTitan_v2167.ex5')}
foreach($item in $paths.GetEnumerator()){$expected=$manifest.files.PSObject.Properties[$item.Key].Value;$actual=(Get-FileHash -LiteralPath $item.Value -Algorithm SHA256).Hash;if([string]::IsNullOrWhiteSpace($expected)-or$actual-ne$expected){throw "v21.67 build hash mismatch: $($item.Key)"}}
$expertDir=Join-Path $lab 'MQL5\Experts';Copy-Item -LiteralPath $paths.binary -Destination $expertDir -Force
$copied=Join-Path $expertDir 'QuantumTitan_v2167.ex5';if((Get-FileHash $copied -Algorithm SHA256).Hash-ne$manifest.files.binary){throw 'Copied tester binary hash mismatch.'}
$reports=Join-Path $lab 'reports';New-Item -ItemType Directory -Path $reports -Force|Out-Null
foreach($ext in @('.htm','.html','.json','.metadata.json','.png','.gif','-holding.png','-hst.png','-mfemae.png')){$artifact=Join-Path $reports "$Name$ext";if(Test-Path -LiteralPath $artifact){Remove-Item -LiteralPath $artifact -Force}}
$setPath=Join-Path $lab 'MQL5\Profiles\Tester\v2167_run.set'
@"
InpEnableDemoOrders=false
InpExpectedDemoLogin=0
InpWriteJournal=true
"@|Set-Content -LiteralPath $setPath -Encoding Unicode
$configPath=Join-Path $lab 'run.ini'
@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=0
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=QuantumTitan_v2167.ex5
ExpertParameters=v2167_run.set
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:500
Model=4
ExecutionMode=$DelayMs
Optimization=0
ForwardMode=0
FromDate=$From
ToDate=$To
Report=reports\$Name.htm
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@|Set-Content -LiteralPath $configPath -Encoding Unicode
$metadata=[ordered]@{schemaVersion=1;name=$Name;version='21.67';evidenceClassification='EXPOSED_ENGINEERING_ONLY';historicalCannotPromote=$true;from=$From;to=$To;deposit=$Deposit;delayMs=$DelayMs;model=4;optimization=0;magic=992167;strategyFreeze='0.01 lot; TP 180; SL 260; BE 85 lock 15; spread 60; cooldown 60s; max hold 10m; 18:00-02:00; cutoff 01:50';sha256=$manifest.files;setSha256=(Get-FileHash $setPath -Algorithm SHA256).Hash;configSha256=(Get-FileHash $configPath -Algorithm SHA256).Hash;startedAt=(Get-Date).ToUniversalTime().ToString('o')}
$metaPath=Join-Path $reports "$Name.metadata.json";$metadata|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $metaPath -Encoding UTF8
$started=[datetime]::UtcNow;$process=Start-Process -FilePath $exe -ArgumentList '/portable',"/config:$configPath" -WindowStyle Hidden -PassThru
if(!$WaitForCompletion){Write-Output "Started isolated $Name PID $($process.Id); evidence is EXPOSED_ENGINEERING_ONLY.";exit 0}
$report=Join-Path $reports "$Name.htm";$deadline=[datetime]::UtcNow.AddSeconds($TimeoutSeconds);$complete=$false
while([datetime]::UtcNow-lt$deadline){
 $running=@(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe)
 if(Test-Path $report){$item=Get-Item $report;if($item.Length-gt 0-and$item.LastWriteTimeUtc-ge$started.AddSeconds(-2)-and$running.Count-eq0){$complete=$true;break}}
 if($running.Count-eq0-and[datetime]::UtcNow-ge$started.AddSeconds(3)){
  $recentLogs=@(Get-ChildItem (Join-Path $lab 'Tester\logs') -Filter '*.log' -File -ErrorAction SilentlyContinue|Where-Object LastWriteTimeUtc -ge $started.AddSeconds(-2))
  $startupFailure=$false;foreach($logFile in $recentLogs){if((Get-Content -LiteralPath $logFile.FullName -Raw)-match'(?i)tester not started|account is not specified'){$startupFailure=$true}}
  if($startupFailure){throw 'Native tester exited before start because cached test account selection was unavailable.'}
  if([datetime]::UtcNow-ge$started.AddSeconds(30)){throw 'Native tester exited before producing a fresh report.'}
 }
 Start-Sleep -Milliseconds 250
}
if(!$complete){$running=@(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe);foreach($item in $running){Stop-Process -Id $item.Id -Force -ErrorAction SilentlyContinue};throw "v21.67 tester timed out after $TimeoutSeconds seconds; only isolated lab processes were stopped."}
$native=Get-Content $report -Raw
foreach($pattern in @('Expert:</td>\s*<td[^>]*>\s*<b>\s*QuantumTitan_v2167\s*</b>','Symbol:</td>\s*<td[^>]*>\s*<b>\s*XAUUSD\s*</b>','Period:</td>\s*<td[^>]*>\s*<b>\s*M1(?:\s|\()')){if($native-notmatch"(?is)$pattern"){throw "Native report identity validation failed: $report"}}
$bars=[regex]::Match($native,'(?is)Bars:</td>\s*<td[^>]*>\s*<b>\s*([0-9 ]+)\s*</b>');$quality=[regex]::Match($native,'(?is)History Quality:</td>\s*<td[^>]*>\s*<b>\s*([^<]+)\s*</b>')
if(!$bars.Success-or[int64]($bars.Groups[1].Value-replace' ','')-le0-or!$quality.Success-or$quality.Groups[1].Value.Trim()-eq'n/a'){throw "Native report history validation failed: $report"}
$freshLogs=@(Get-ChildItem (Join-Path $lab 'Tester\logs') -Filter '*.log' -File -ErrorAction SilentlyContinue|Where-Object LastWriteTimeUtc -ge $started.AddSeconds(-2))
$delayPattern="testing with execution delay $DelayMs milliseconds"
$delayVerified=$false;foreach($logFile in $freshLogs){if((Get-Content -LiteralPath $logFile.FullName -Raw)-match[regex]::Escape($delayPattern)){$delayVerified=$true}}
if(!$delayVerified){throw "Fresh tester logs did not confirm the requested $DelayMs millisecond execution delay."}
$metadata.actualDelayVerified=$true;$metadata.completedAt=(Get-Date).ToUniversalTime().ToString('o');$metadata.testerLogSha256=@{}
foreach($logFile in $freshLogs){$metadata.testerLogSha256[$logFile.Name]=(Get-FileHash $logFile.FullName -Algorithm SHA256).Hash}
$metadataJson=$metadata|ConvertTo-Json -Depth 5;$metadataSaved=$false
for($attempt=0;$attempt-lt20-and!$metadataSaved;$attempt++){try{$metadataJson|Set-Content -LiteralPath $metaPath -Encoding UTF8 -ErrorAction Stop;$metadataSaved=$true}catch [System.IO.IOException]{Start-Sleep -Milliseconds 250}}
if(!$metadataSaved){throw "Completed tester report exists, but metadata remained locked: $metaPath"}
$pythonExe=$Python;if([string]::IsNullOrWhiteSpace($pythonExe)){$pythonExe=(Get-Command python -ErrorAction SilentlyContinue).Source};if([string]::IsNullOrWhiteSpace($pythonExe)){$pythonExe=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
if(!(Test-Path -LiteralPath $pythonExe)){throw 'Python was not found. Pass -Python with an executable path.'}
$analysisPath=Join-Path $reports "$Name.json";& $pythonExe (Join-Path $root 'research\v2167_evaluate.py') $report --metadata $metaPath --output $analysisPath
if($LASTEXITCODE-ne0-or!(Test-Path -LiteralPath $analysisPath)){throw 'v21.67 report evaluation failed.'}
Write-Output "Completed isolated $Name with verified ${DelayMs}ms delay. Evidence remains EXPOSED_ENGINEERING_ONLY. Report: $report Analysis: $analysisPath"
