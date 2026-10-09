param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name,
 [ValidateSet('fade','momentum','closeback','leveltouch')][string]$Variant='fade',
 [double]$Deposit=10000,
 [string]$From='2026.05.01',
 [string]$To='2026.10.01',
 [switch]$Original,
 [switch]$Probe,
 [int]$TimeoutSeconds=600
)
$ErrorActionPreference='Stop'
function Save-Json($Value,$Path) {
 $json=$Value|ConvertTo-Json -Depth 8
 for($attempt=0;$attempt -lt 20;$attempt++) {
  try {[IO.File]::WriteAllText($Path,$json,[Text.UTF8Encoding]::new($false));return}
  catch {if($attempt -eq 19){throw};Start-Sleep -Milliseconds 100}
 }
}
if($Original -and $Variant -ne 'fade'){throw 'Original EX5 parity permits fade only.'}
if($Probe -and $Variant -eq 'leveltouch'){throw 'Level-touch variant requires candidate harness.'}
if($Original -and $Probe){throw 'Probe and original mutually exclusive.'}
$root=Split-Path $PSScriptRoot -Parent
$base=Join-Path $root 'reports\v23_backtest_20261004'
$lab=Join-Path $base 'lab'
$terminal=Join-Path $lab 'terminal64.exe'
$out=Join-Path $base "runs\$Name"
if(Test-Path -LiteralPath $out){throw 'Unique run name required; existing evidence preserved.'}
if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $terminal){throw 'Lab terminal already running.'}
New-Item -ItemType Directory -Path $out -Force|Out-Null
$expert=if($Original){'AegisPredator_v23'}elseif($Probe){'V23_MarketDataProbe'}elseif($Variant -eq 'leveltouch'){'V23_LevelTouchBenchmark'}else{'V23_BacktestBenchmark'}
$source=if($Original){Join-Path $root 'AegisPredator_v23.mq5'}elseif($Probe){Join-Path $root 'research\V23_MarketDataProbe.mq5'}elseif($Variant -eq 'leveltouch'){Join-Path $root 'research\V23_LevelTouchBenchmark.mq5'}else{Join-Path $root 'research\V23_BacktestBenchmark.mq5'}
$binary=[IO.Path]::ChangeExtension($source,'.ex5')
Copy-Item -LiteralPath $binary -Destination (Join-Path $lab "MQL5\Experts\$expert.ex5") -Force
$settings=@()
Get-Content -LiteralPath (Join-Path $root 'AegisPredator_v23.mq5')|ForEach-Object {
 if($_ -match '^input\s+(?:bool|int|double|ulong)\s+(\w+)\s*=\s*([^;]+);') {
  $key=$Matches[1];$value=$Matches[2].Trim()
  if($key -eq 'InpFadeBreakouts'){$value=if($Variant -in @('momentum','leveltouch')){'false'}else{'true'}}
  $settings+="$key=$value"
 }
}
if($Probe){$settings=@("InpRunTag=$Name")}
elseif(!$Original){$insideValue=($Variant -eq 'closeback').ToString().ToLowerInvariant();$settings+="InpRequireCloseBackInside=$insideValue";if($Variant -eq 'leveltouch'){$settings+='InpRequireLevelTouch=true'};$settings+="InpRunTag=$Name"}
$delay=if($Probe){0}else{200}
$setPath=Join-Path $lab "MQL5\Profiles\Tester\$Name.set"
$settings|Set-Content -LiteralPath $setPath -Encoding Unicode
$iniPath=Join-Path $lab "$Name.ini"
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
ExpertParameters=$Name.set
Symbol=XAUUSD
Period=M1
Deposit=$Deposit
Currency=USD
Leverage=1:200
Model=4
ExecutionMode=$delay
Optimization=0
FromDate=$From
ToDate=$To
ForwardMode=0
Report=reports\$Name.htm
ReplaceReport=0
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@|Set-Content -LiteralPath $iniPath -Encoding Unicode
$files=[ordered]@{source=$source;binary=$binary;settings=$setPath;config=$iniPath;terminal=$terminal;agent=(Join-Path $lab 'metatester64.exe');protocol=(Join-Path $base 'protocol.json')}
$hashes=[ordered]@{}
foreach($item in $files.GetEnumerator()){$hashes[$item.Key]=(Get-FileHash -LiteralPath $item.Value).Hash}
$protocol=Get-Content -LiteralPath $files.protocol -Raw|ConvertFrom-Json
$frozen=$protocol.frozen_artifacts.frozen_runtime
if($hashes.terminal -ne $frozen.terminal_sha256 -or $hashes.agent -ne $frozen.tester_sha256){throw 'Runtime differs from frozen protocol.'}
$journalPaths=@(Get-ChildItem -LiteralPath $lab -Filter *.log -Recurse|Where-Object {$_.FullName -match '\\(?:logs|Logs)\\'})
$beforeLogs=@{}
foreach($log in $journalPaths){$beforeLogs[$log.FullName]=$log.Length}
$meta=[ordered]@{name=$Name;variant=$Variant;original=[bool]$Original;probe=[bool]$Probe;deposit=$Deposit;from=$From;to=$To;delay_ms=$delay;model=4;leverage=200;created_utc=[datetime]::UtcNow.ToString('o');sha256=$hashes;terminal_build=(Get-Item $terminal).VersionInfo.FileVersion;agent_build=(Get-Item $files.agent).VersionInfo.FileVersion}
Save-Json $meta (Join-Path $out 'metadata_start.json')
Copy-Item -LiteralPath $setPath,$iniPath -Destination $out
Copy-Item -LiteralPath $files.protocol -Destination (Join-Path $out 'protocol.json')
$start=[datetime]::UtcNow
$p=Start-Process -FilePath $terminal -ArgumentList '/portable',"/config:$iniPath" -WorkingDirectory $lab -WindowStyle Hidden -PassThru
try {Wait-Process -Id $p.Id -Timeout $TimeoutSeconds -ErrorAction Stop}
catch {Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue;throw 'Isolated tester timed out.'}
$p.Refresh()
$p.WaitForExit()
$meta['exit_code']=$p.ExitCode
$meta['finished_utc']=[datetime]::UtcNow.ToString('o')
$report=Join-Path $lab "reports\$Name.htm"
if(!(Test-Path -LiteralPath $report) -or (Get-Item $report).LastWriteTimeUtc -lt $start.AddSeconds(-2)){throw 'Fresh native report missing.'}
Get-ChildItem -LiteralPath (Join-Path $lab 'reports') -Filter "$Name*" -File|Copy-Item -Destination $out
$exports=@(Get-ChildItem -LiteralPath (Join-Path $lab 'Tester') -Filter "$Name`_*.csv" -Recurse -File)
if(@($exports|Group-Object Name|Where-Object Count -gt 1).Count -gt 0){throw 'Duplicate agent export filenames.'}
$exports|ForEach-Object {
 if($_.LastWriteTimeUtc -lt $start.AddSeconds(-2)){throw 'Stale tester CSV.'}
 Copy-Item -LiteralPath $_.FullName -Destination $out
}
$journals=Join-Path $out 'logs';New-Item -ItemType Directory -Path $journals -Force|Out-Null
$idx=0
foreach($log in @(Get-ChildItem -LiteralPath $lab -Filter *.log -Recurse|Where-Object {$_.FullName -match '\\(?:logs|Logs)\\'})) {
 $offset=if($beforeLogs.ContainsKey($log.FullName)){$beforeLogs[$log.FullName]}else{0}
 $bytes=[IO.File]::ReadAllBytes($log.FullName)
 if($bytes.Length -lt $offset){$offset=0}
 if($bytes.Length -gt $offset){
  # MT5 logs are UTF-16LE. Decode only newly appended evidence, not previous runs.
  [Text.Encoding]::Unicode.GetString($bytes,$offset,$bytes.Length-$offset)|Set-Content -LiteralPath (Join-Path $journals "$idx.txt") -Encoding UTF8
  $idx++
 }
}
$meta['runtime_drift']=((Get-FileHash -LiteralPath $terminal).Hash -ne $hashes.terminal -or (Get-FileHash -LiteralPath $files.agent).Hash -ne $hashes.agent)
Save-Json $meta (Join-Path $out 'metadata.json')
if($meta.runtime_drift){throw 'Runtime build/hash changed; run invalid for comparison.'}
if($p.ExitCode -ne 0){throw "Tester exit code $($p.ExitCode)."}
if(!$Original){$required=if($Probe){@('daily','gaps','sessions','minute_issues')}else{@('deals','raw','equity','spec')};foreach($kind in $required){if(!(Test-Path -LiteralPath (Join-Path $out "$Name`_$kind.csv"))){throw "Native $kind export missing."}}}
$cache=@(Get-ChildItem -LiteralPath (Join-Path $lab 'bases\MetaQuotes-Demo\ticks\XAUUSD') -File|Where-Object Name -match '^(20260[4-9]\.tkc|ticks\.dat)$'|ForEach-Object {[ordered]@{name=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
Save-Json $cache (Join-Path $out 'tick_cache_manifest.json')
Write-Output "Native evidence: $out"
