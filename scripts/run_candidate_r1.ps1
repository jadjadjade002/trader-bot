param([ValidatePattern('^[a-zA-Z0-9_]+$')][string]$Prefix='r1_a',[ValidateSet('all','smoke')][string]$Action='all',[switch]$R2,[switch]$R3,[switch]$R4)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$localLab=Join-Path $projectRoot '.mt5-v23-tuning.local'
$agentExe=Join-Path $localLab 'metatester64.exe'
$terminalExe=Join-Path $localLab 'terminal64.exe'
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $terminalExe){throw 'Isolated terminal already running'}
if(([int]$R2.IsPresent+[int]$R3.IsPresent+[int]$R4.IsPresent) -gt 1){throw 'Select only one research round'}
$roundName=if($R4){'r4'}elseif($R3){'r3'}elseif($R2){'r2'}else{'r1'}
$candidateSource=Join-Path $projectRoot ("research\ResearchCandidate_"+$roundName.ToUpper()+'.mq5')
$candidateBinary=[IO.Path]::ChangeExtension($candidateSource,'.ex5')
$compileLog=Join-Path $projectRoot ("reports\candidate_${roundName}_compile.log")
if(!(Test-Path -LiteralPath $candidateBinary)){throw 'Candidate binary missing'}
if((Get-Item -LiteralPath $candidateBinary).LastWriteTimeUtc -lt (Get-Item -LiteralPath $candidateSource).LastWriteTimeUtc){throw 'Candidate binary older than source'}
if(!(Test-Path -LiteralPath $compileLog) -or !((Get-Content -LiteralPath $compileLog -Encoding Unicode -Tail 3) -match 'Result: 0 errors, 0 warnings')){throw 'Clean compilation evidence missing'}
$reportsPath=Join-Path $projectRoot 'reports'
$bootstrapName="${Prefix}_bootstrap_"+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss')
$bootstrap=Start-Process -FilePath 'python' -ArgumentList '-m','research.candidate_bootstrap','--prefix',$bootstrapName -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportsPath "${bootstrapName}_stdout.log") -RedirectStandardError (Join-Path $reportsPath "${bootstrapName}_stderr.log")
$deadline=[DateTime]::UtcNow.AddSeconds(60)
do {
 $nativeAgent=Get-CimInstance Win32_Process -Filter "Name='metatester64.exe'" | Where-Object ExecutablePath -eq $agentExe | Select-Object -First 1
 if(!$nativeAgent){Start-Sleep -Milliseconds 500}
}until($nativeAgent -or [DateTime]::UtcNow -ge $deadline)
if(!$nativeAgent){throw 'Isolated native agent did not start'}
# Authentication stays only in memory. Never output it or write it to a file.
$agentArguments=$nativeAgent.CommandLine -replace '^"[^\"]+"\s*',''
Wait-Process -Id $bootstrap.Id -Timeout 180
if(Get-Process -Id $nativeAgent.ProcessId -ErrorAction SilentlyContinue){Wait-Process -Id $nativeAgent.ProcessId -Timeout 10}
Start-Sleep -Seconds 2
$warmed=Start-Process -FilePath $agentExe -ArgumentList $agentArguments -WorkingDirectory $localLab -WindowStyle Hidden -PassThru
try {
 if($R4){ & python -m research.run_candidate_r4 --prefix $Prefix }
 elseif($R3){ & python -m research.run_candidate_r3 --prefix $Prefix }
 elseif($R2){ & python -m research.run_candidate_r2 --prefix $Prefix }
 else { & python -m research.run_v25_native $Action --prefix $Prefix }
 if($LASTEXITCODE -ne 0){throw 'Candidate native batch failed verification. Preserve evidence.'}
}finally {
 if(Get-Process -Id $warmed.Id -ErrorAction SilentlyContinue){Stop-Process -Id $warmed.Id}
 $agentArguments=$null
}
