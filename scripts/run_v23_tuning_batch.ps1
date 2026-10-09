param([ValidatePattern('^[a-zA-Z0-9_]+$')][string]$Prefix='real5m_batch2', [switch]$Resume, [ValidateSet('all','finalize','verify24')][string]$Action='all')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$localLab=Join-Path $projectRoot '.mt5-v23-tuning.local'
$agentExe=Join-Path $localLab 'metatester64.exe'
$terminalExe=Join-Path $localLab 'terminal64.exe'
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $terminalExe){throw 'Isolated terminal already running'}
$reportsPath=Join-Path $projectRoot 'reports'
$bootstrapName="${Prefix}_${Action}_bootstrap_"+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss')
$bootstrap=Start-Process -FilePath 'python' -ArgumentList '-m','research.run_v23_tuning','smoke','--prefix',$bootstrapName -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportsPath "${bootstrapName}_stdout.log") -RedirectStandardError (Join-Path $reportsPath "${bootstrapName}_stderr.log")
$deadline=[DateTime]::UtcNow.AddSeconds(25)
do {
 $nativeAgent=Get-CimInstance Win32_Process -Filter "Name='metatester64.exe'" | Where-Object ExecutablePath -eq $agentExe | Select-Object -First 1
 if(!$nativeAgent){Start-Sleep -Milliseconds 500}
}until($nativeAgent -or [DateTime]::UtcNow -ge $deadline)
if(!$nativeAgent){throw 'Isolated native agent did not start'}
# The local-agent password stays only in memory. Never output or persist it.
$agentArguments=$nativeAgent.CommandLine -replace '^"[^"]+"\s*',''
Wait-Process -Id $bootstrap.Id -Timeout 60
if(Get-Process -Id $nativeAgent.ProcessId -ErrorAction SilentlyContinue){Wait-Process -Id $nativeAgent.ProcessId -Timeout 10}
Start-Sleep -Seconds 2
$warmed=Start-Process -FilePath $agentExe -ArgumentList $agentArguments -WorkingDirectory $localLab -WindowStyle Hidden -PassThru
Write-Output "Warm local agent ready. Batch: $Prefix"
try {
 if($Action -eq 'verify24') { & python -m research.verify_v24_native $Prefix }
 elseif($Action -eq 'finalize') { & python -m research.finalize_v23_tuning $Prefix }
 else { & python -m research.run_v23_tuning all --prefix $Prefix }
 if($LASTEXITCODE -ne 0){throw 'Native batch failed validation. Preserve all evidence.'}
}finally {
 if(Get-Process -Id $warmed.Id -ErrorAction SilentlyContinue){Stop-Process -Id $warmed.Id}
 $agentArguments=$null
}
