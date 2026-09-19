param([string]$MetaEditor='C:\Program Files\MetaTrader 5\metaeditor64.exe',[switch]$StaticOnly)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$source=Join-Path $root 'QuantumTitan_ForwardCollector.mq5'
$binary=Join-Path $root 'QuantumTitan_ForwardCollector.ex5'
$manifestPath=Join-Path $root 'compiled\QuantumTitan_ForwardCollector.build.json'
$dailySchema='schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,real_volume,bar_spread_points,open_spread_points,open_bid,open_ask,open_tick_time_msc,close_observed_time_msc,flags'
$healthSchema='schema_version,collector_version,run_id,broker_time_epoch,broker_time_iso,terminal_connected,symbol_synchronized,last_tick_age_seconds,last_closed_bar_epoch,rows_written,duplicate_skips,gap_count,write_errors,status'
if(!(Test-Path -LiteralPath $source)){throw "Source was not found: $source"}
$text=Get-Content -LiteralPath $source -Raw
$forbidden='(?i)\b(?:CTrade|MqlTrade\w*|Order\w*|Position\w*|History\w*|GlobalVariable\w*|Chart\w*|Object\w*|WebRequest|CopyTicks\w*|OnTrade\w*|RiskGuardian|FileDelete|FileMove|FileCopy|SendMail|SendNotification|SendFTP)\b|#\s*(?:include|import|define)\b|\btrade\s*\.'
if($text -match $forbidden){throw "Forbidden trade/state API token: $($Matches[0])"}
foreach($schema in @(@('BAR_HEADER',$dailySchema),@('HEALTH_HEADER',$healthSchema))){
    if($text -notmatch ('const string '+$schema[0]+'="'+[regex]::Escape($schema[1])+'";')){throw "Exact schema check failed: $($schema[0])"}
}
$required=@('const string RUN_ID="FWD_20260909_4W";',"const datetime PLANNED_END=D'2026.10.07 15:00:00';",'const int HEALTH_SECONDS=300;','EventSetTimer(HEALTH_SECONDS)','void OnTimer()','CopyRates(_Symbol,PERIOD_M1,activeBar,1,rates)','rates[0].time!=activeBar','_Symbol!="XAUUSD"','_Period!=PERIOD_M1','QTForward_XAUUSD_M1_','QTForward_health_')
foreach($token in $required){if(!$text.Contains($token)){throw "Required contract token missing: $token"}}
if(([regex]::Matches($text,'\bCopyRates\s*\(')).Count -ne 1){throw 'Only one exact-bar CopyRates call is allowed.'}
if($text -notmatch '(?s)void OnDeinit\([^)]*\)\s*\{\s*EventKillTimer\(\);\s*//[^\r\n]*\s*\}') {throw 'OnDeinit must only disable the timer; no final bar write is allowed.'}
if($StaticOnly){Write-Output 'Forward collector static contract checks passed (19 bar columns, 14 health columns).';return}
if(!(Test-Path -LiteralPath $MetaEditor)){throw "MetaEditor was not found: $MetaEditor"}
$before=if(Test-Path -LiteralPath $binary){(Get-Item -LiteralPath $binary).LastWriteTimeUtc}else{[datetime]::MinValue}
$sourceHash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
New-Item -ItemType Directory -Path (Split-Path $manifestPath -Parent) -Force|Out-Null
$log=Join-Path $root ('forward_collector_compile_'+[guid]::NewGuid().ToString('N')+'.log')
$started=[datetime]::UtcNow
$process=Start-Process -FilePath $MetaEditor -ArgumentList ('/compile:"'+$source+'"'),('/log:"'+$log+'"') -WindowStyle Hidden -PassThru -Wait
if(!(Test-Path -LiteralPath $log)){throw "MetaEditor did not create a compile log: $log"}
if((Get-Item -LiteralPath $log).LastWriteTimeUtc -lt $started.AddSeconds(-2)){throw "MetaEditor did not refresh the compile log: $log"}
$result=Get-Content -LiteralPath $log -Raw
if($result -notmatch '(?m)^Result:\s*0 errors,\s*0 warnings\b' -or $result -match '(?im)\b(?:error|warning)\s+\d+\b'){throw "Forward collector compilation failed. MetaEditor exit code $($process.ExitCode). See $log"}
if(!(Test-Path -LiteralPath $binary) -or (Get-Item -LiteralPath $binary).LastWriteTimeUtc -le $before -or (Get-Item -LiteralPath $binary).LastWriteTimeUtc -lt $started.AddSeconds(-2) -or (Get-Item -LiteralPath $binary).Length -eq 0){throw 'Forward collector binary was not freshly produced.'}
if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash){throw 'Source changed during compilation.'}
$manifest=[ordered]@{schemaVersion='1';collectorVersion='2.00';runId='FWD_20260909_4W';plannedEnd='2026-10-07T15:00:00';dailyFile='QTForward_XAUUSD_M1_YYYYMMDD.csv';healthFile='QTForward_health_YYYYMMDD.csv';dailySchema=$dailySchema;healthSchema=$healthSchema;source=$sourceHash;binary=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash;compileLog=$log;errors=0;warnings=0;compiledAt=[datetime]::UtcNow.ToString('o')}
$manifest|ConvertTo-Json|Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output 'QuantumTitan_ForwardCollector compiled with fresh 0 errors and 0 warnings; hashes and exact schemas saved.'
