param(
 [string]$KeyPath='D:\project\trader-bot\key\ssh-key-2026-09-06.key',
 [string]$HostName='161.118.255.178',
 [string]$UserName='ubuntu',
 [string]$Root=(Split-Path $PSScriptRoot -Parent),
 [string]$RemoteRoot='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 Forward',
 [string]$RemoteSource='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v17'
)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'validate_forward_collector.ps1') -Root $Root
foreach($path in @($KeyPath,(Join-Path $Root 'QuantumTitan_ForwardCollector.ex5'),(Join-Path $Root 'deploy\forward\chart01.chr'),(Join-Path $Root 'deploy\forward\order.wnd'))){if(!(Test-Path -LiteralPath $path)){throw "Required deployment artifact missing: $path"}}
$allowedRoot='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 Forward'
$allowedSources=@('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5','/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v17')
if($RemoteRoot-ne$allowedRoot){throw "Unsafe collector root: $RemoteRoot"}
if($RemoteSource-notin$allowedSources -or $RemoteSource-eq$RemoteRoot){throw "Unsafe collector source: $RemoteSource"}
$ssh=@('-i',$KeyPath,'-o','BatchMode=yes','-o','ConnectTimeout=20','-o','StrictHostKeyChecking=accept-new',"$UserName@$HostName")
$probe=& ssh @ssh "if [ -e '$RemoteRoot' ] || [ -L '$RemoteRoot' ]; then echo ROOT_EXISTS; else echo ROOT_ABSENT; fi; echo ROOT_CANONICAL=`$(readlink -m -- '$RemoteRoot'); echo SOURCE_CANONICAL=`$(readlink -f -- '$RemoteSource'); if [ -f '$RemoteSource/terminal64.exe' ]; then echo SOURCE_OK; else echo SOURCE_MISSING; fi; pgrep -af terminal64.exe || true"
if($LASTEXITCODE-ne 0){throw 'Remote preflight failed.'}
if($probe-contains'ROOT_EXISTS'){throw "Refusing to reuse an existing remote collector root: $RemoteRoot"}
if(!($probe-contains'SOURCE_OK')){throw "Remote source terminal was not found: $RemoteSource/terminal64.exe"}
if(!($probe-contains"ROOT_CANONICAL=$allowedRoot")){throw 'Remote collector root did not resolve to the dedicated path.'}
if(!($probe-contains"SOURCE_CANONICAL=$RemoteSource")){throw 'Remote source path is missing, aliased, or resolves outside the approved source path.'}
function Has-Signature([string]$line,[string[]]$signatures){foreach($signature in $signatures){if($line.Contains($signature)){return $true}};return $false}
$v16Signatures=@('C:\Program Files\MetaTrader 5\terminal64.exe /portable','/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe /portable')
$collectorSignatures=@('C:\Program Files\MetaTrader 5 Forward\terminal64.exe /portable','/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 Forward/terminal64.exe /portable')
$beforeV16=@($probe|Where-Object{Has-Signature $_ $v16Signatures})
if($beforeV16.Count-eq 0){throw 'Active v16 terminal was not observed before collector deployment.'}
$beforeV16Ids=@($beforeV16|ForEach-Object{if($_-match '^([0-9]+)\s'){$Matches[1]}})
$createdRoot=$false
$collectorIds=@()
try
{
& ssh @ssh "cp -a --reflink=auto '$RemoteSource' '$RemoteRoot' && mkdir -p '$RemoteRoot/MQL5/Experts' '$RemoteRoot/MQL5/Profiles/Charts/ForwardCollector'"
if($LASTEXITCODE-ne 0){throw 'Remote isolated MT5 copy creation failed.'}
$createdRoot=$true
$scpBase=@('-i',$KeyPath,'-o','BatchMode=yes','-o','ConnectTimeout=20','-o','StrictHostKeyChecking=accept-new')
function Copy-Remote([string]$local,[string]$remote){& scp @scpBase $local "$UserName@${HostName}:$remote";if($LASTEXITCODE-ne 0){throw "Collector artifact upload failed: $local"}}
Copy-Remote (Join-Path $Root 'QuantumTitan_ForwardCollector.ex5') "$RemoteRoot/MQL5/Experts/QuantumTitan_ForwardCollector.ex5"
Copy-Remote (Join-Path $Root 'deploy\forward\chart01.chr') "$RemoteRoot/MQL5/Profiles/Charts/ForwardCollector/chart01.chr"
Copy-Remote (Join-Path $Root 'deploy\forward\order.wnd') "$RemoteRoot/MQL5/Profiles/Charts/ForwardCollector/order.wnd"
$remoteScript=@'
from pathlib import Path
import configparser
root=Path(r"REMOTE_ROOT")
profile=root/'MQL5/Profiles/Charts/ForwardCollector'
chart=profile/'chart01.chr'
raw=chart.read_text(encoding='utf-8')
chart.write_bytes(b'\xff\xfe'+raw.encode('utf-16le'))
common=root/'Config/common.ini'
if not common.exists():
    raise SystemExit('common.ini missing')
cfg=configparser.ConfigParser(interpolation=None,strict=False)
cfg.optionxform=str
cfg.read_string(common.read_text(encoding='utf-16'))
if not cfg.has_section('Common'): cfg.add_section('Common')
if not cfg.has_section('Charts'): cfg.add_section('Charts')
if not cfg.has_section('Experts'): cfg.add_section('Experts')
cfg.set('Common','ProfileLast','ForwardCollector')
cfg.set('Charts','ProfileLast','ForwardCollector')
cfg.set('Experts','Enabled','1')
cfg.set('Experts','AllowLiveTrading','0')
with common.open('w',encoding='utf-16',newline='') as handle: cfg.write(handle,space_around_delimiters=False)
for log_dir in (root/'logs',root/'MQL5/logs'):
    if log_dir.exists():
        for old_log in log_dir.glob('*.log'): old_log.unlink()
manifest=root/'forward_collector_deploy_manifest.txt'
manifest.write_text('run_id=FWD_20260909_4W\nprofile=ForwardCollector\nallow_live_trading=0\nno_restart_of_existing_terminals=true\n',encoding='utf-8')
'@
$remoteScript=$remoteScript.Replace('REMOTE_ROOT',$RemoteRoot.Replace('\','/'))
$encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
& ssh @ssh "echo $encoded | base64 -d | python3"
if($LASTEXITCODE-ne 0){throw 'Remote profile preparation failed.'}
& ssh @ssh "DISPLAY=:0 nohup wine '$RemoteRoot/terminal64.exe' /portable /profile:ForwardCollector /skipupdate > '$RemoteRoot/forward_terminal.log' 2>&1 < /dev/null &"
if($LASTEXITCODE-ne 0){throw 'Forward terminal launch failed.'}
Start-Sleep -Seconds 3
$after=@(& ssh @ssh "pgrep -af terminal64.exe || true")
if($LASTEXITCODE-ne 0){throw 'Remote post-launch process probe failed.'}
foreach($processId in $beforeV16Ids){if(!($after|Where-Object{$_-match "^$processId\s" -and (Has-Signature $_ $v16Signatures)})){throw "Existing v16 terminal PID $processId was not observed after launch."}}
$collectorLines=@($after|Where-Object{Has-Signature $_ $collectorSignatures})
$collectorIds=@($collectorLines|ForEach-Object{if($_-match '^([0-9]+)\s'){$Matches[1]}})
if($collectorIds.Count-eq 0){throw 'Forward terminal process was not observed after launch.'}
Write-Output 'Forward collector deployment prepared and launched in a separate portable root. Existing v16 process was observed before and after launch.'
}
catch
{
   $failure=$_
   if($createdRoot)
   {
      $running=@(& ssh @ssh "pgrep -af terminal64.exe || true")
      $rollbackIds=@($running|Where-Object{Has-Signature $_ $collectorSignatures}|ForEach-Object{if($_-match '^([0-9]+)\s'){$Matches[1]}})
      if($rollbackIds.Count-gt 0){& ssh @ssh "kill -- $($rollbackIds-join' ')"|Out-Null}
      $deadline=[datetime]::UtcNow.AddSeconds(5)
      do
      {
         $running=@(& ssh @ssh "pgrep -af terminal64.exe || true")
         $rollbackIds=@($running|Where-Object{Has-Signature $_ $collectorSignatures}|ForEach-Object{if($_-match '^([0-9]+)\s'){$Matches[1]}})
         if($rollbackIds.Count-gt 0){Start-Sleep -Milliseconds 250}
      }while($rollbackIds.Count-gt 0 -and [datetime]::UtcNow-lt$deadline)
      if($rollbackIds.Count-gt 0){throw "Rollback could not stop collector PID(s): $($rollbackIds-join',')"}
      $stamp=[datetime]::UtcNow.ToString('yyyyMMdd_HHmmss')
      $quarantine="/home/ubuntu/failed-deployments/MetaTrader5Forward_$stamp"
      & ssh @ssh "mkdir -p '/home/ubuntu/failed-deployments' && if [ -e '$RemoteRoot' ]; then mv -- '$RemoteRoot' '$quarantine'; fi"|Out-Null
   }
   throw $failure
}
