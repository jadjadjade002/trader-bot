param(
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Name='m1_development',
 [ValidatePattern('^\d{4}\.\d{2}\.\d{2}$')][string]$From='2026.08.03',
 [ValidatePattern('^\d{4}\.\d{2}\.\d{2}$')][string]$To='2026.08.22',
 [ValidateRange(0.00000001,100.0)][double]$Point=0.01,
 [ValidateRange(0.00000001,100.0)][double]$TickSize=0.01,
 [string]$Python='',
 [switch]$SkipAnalysis,
 [ValidateRange(10,600)][int]$TimeoutSeconds=180
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v20.local'
$exe=Join-Path $lab 'terminal64.exe'
$source=Join-Path $root 'QuantumTitan_M1Export.mq5'
$binary=Join-Path $root 'QuantumTitan_M1Export.ex5'
$manifestPath=Join-Path $root 'compiled\QuantumTitan_M1Export.build.json'
$exportName='QuantumTitan_M1Export.csv'
$delayMs=200
$culture=[System.Globalization.CultureInfo]::InvariantCulture
$dateStyle=[System.Globalization.DateTimeStyles]::AssumeUniversal
$fromEpoch=[DateTimeOffset]::ParseExact($From,'yyyy.MM.dd',$culture,$dateStyle).ToUnixTimeSeconds()
$toEpoch=[DateTimeOffset]::ParseExact($To,'yyyy.MM.dd',$culture,$dateStyle).ToUnixTimeSeconds()
if($toEpoch-le$fromEpoch){throw 'To must be later than From.'}
if(!(Test-Path -LiteralPath $exe)){throw 'The isolated v20 lab is not prepared.'}
if(Get-Process terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe){throw 'The isolated tester is already running.'}
foreach($path in @($source,$binary,$manifestPath)){if(!(Test-Path -LiteralPath $path)){throw "Required exporter artifact was not found: $path"}}
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash-ne$manifest.source){throw 'Exporter source changed after compilation.'}
if((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash-ne$manifest.binary){throw 'Exporter binary does not match its build manifest.'}

$expertsDir=Join-Path $lab 'MQL5\Experts'
$profilesDir=Join-Path $lab 'MQL5\Profiles\Tester'
$reportsDir=Join-Path $lab 'reports'
$dataDir=Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $expertsDir,$profilesDir,$reportsDir,$dataDir|Out-Null
Copy-Item -LiteralPath $binary -Destination $expertsDir -Force
$report=Join-Path $reportsDir "$Name.htm"
$metadataPath=Join-Path $dataDir "$Name.metadata.json"
$destinationCsv=Join-Path $dataDir "$Name.csv"
foreach($artifact in @($report,$metadataPath,$destinationCsv)){if(Test-Path -LiteralPath $artifact){Remove-Item -LiteralPath $artifact -Force}}
$agentRoots=@(Get-ChildItem -LiteralPath (Join-Path $lab 'Tester') -Directory -Filter 'Agent-*' -ErrorAction SilentlyContinue)
foreach($agent in $agentRoots){$old=Join-Path $agent.FullName "MQL5\Files\$exportName";if(Test-Path -LiteralPath $old){Remove-Item -LiteralPath $old -Force}}

@"
InpOutputFile=$exportName
InpExpectedPoint=$Point
InpExpectedTickSize=$TickSize
InpMinimumEpoch=$fromEpoch
InpMaximumEpochExclusive=$toEpoch
"@|Set-Content -LiteralPath (Join-Path $profilesDir 'data_export.set') -Encoding Unicode
@"
[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=QuantumTitan_M1Export.ex5
ExpertParameters=data_export.set
Symbol=XAUUSD
Period=M1
Deposit=50
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
"@|Set-Content -LiteralPath (Join-Path $lab 'run_data_export.ini') -Encoding Unicode

$started=[datetime]::UtcNow
$process=Start-Process -FilePath $exe -ArgumentList '/portable','/skipupdate',"/config:$(Join-Path $lab 'run_data_export.ini')" -WindowStyle Hidden -PassThru
$deadline=$started.AddSeconds($TimeoutSeconds)
$completed=$false
while([datetime]::UtcNow-lt$deadline){
 $labProcesses=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe)
 if((Test-Path -LiteralPath $report)-and$labProcesses.Count-eq 0){$item=Get-Item -LiteralPath $report;if($item.Length-gt 0-and$item.LastWriteTimeUtc-ge$started.AddSeconds(-2)){$completed=$true;break}}
 Start-Sleep -Milliseconds 250
}
if(!$completed){
 $remaining=@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue|Where-Object Path -eq $exe)
 foreach($item in $remaining){Stop-Process -Id $item.Id -Force -ErrorAction SilentlyContinue}
 throw "Data export timed out after $TimeoutSeconds seconds; isolated lab processes were stopped."
}

$nativeReport=Get-Content -LiteralPath $report -Raw
$expertOk=$nativeReport-match '(?is)Expert:</td>\s*<td[^>]*>\s*<b>\s*QuantumTitan_M1Export\s*</b>'
$symbolOk=$nativeReport-match '(?is)Symbol:</td>\s*<td[^>]*>\s*<b>\s*XAUUSD\s*</b>'
$periodOk=$nativeReport-match '(?is)Period:</td>\s*<td[^>]*>\s*<b>\s*M1(?:\s|\()'
$barsMatch=[regex]::Match($nativeReport,'(?is)Bars:</td>\s*<td[^>]*>\s*<b>\s*([0-9 ]+)\s*</b>')
$historyMatch=[regex]::Match($nativeReport,'(?is)History Quality:</td>\s*<td[^>]*>\s*<b>\s*([^<]+)\s*</b>')
$bars=if($barsMatch.Success){[int64]($barsMatch.Groups[1].Value-replace ' ','')}else{0}
if(!$expertOk-or!$symbolOk-or!$periodOk-or$bars-le 0-or!$historyMatch.Success-or$historyMatch.Groups[1].Value.Trim()-eq'n/a'){throw 'Native tester report identity/history validation failed.'}
$ticksDir=Join-Path $lab 'bases\MetaQuotes-Demo\ticks\XAUUSD'
$monthStart=[datetime]::ParseExact($From,'yyyy.MM.dd',[Globalization.CultureInfo]::InvariantCulture)
$monthEnd=[datetime]::ParseExact($To,'yyyy.MM.dd',[Globalization.CultureInfo]::InvariantCulture)
while($monthStart -lt $monthEnd)
{
 $tickFile=Join-Path $ticksDir ("{0:yyyyMM}.tkc" -f $monthStart)
 if(!(Test-Path -LiteralPath $tickFile) -or (Get-Item -LiteralPath $tickFile).Length -le 0){throw "Required nonempty real-tick cache is missing: $tickFile"}
 $monthStart=$monthStart.AddMonths(1)
}
$exports=@(Get-ChildItem -LiteralPath (Join-Path $lab 'Tester') -Directory -Filter 'Agent-*'|ForEach-Object{Get-Item -LiteralPath (Join-Path $_.FullName "MQL5\Files\$exportName") -ErrorAction SilentlyContinue}|Where-Object{$_.Length-gt 0-and$_.LastWriteTimeUtc-ge$started.AddSeconds(-2)})
if($exports.Count-ne 1){throw "Expected exactly one fresh exporter CSV, found $($exports.Count)."}
Copy-Item -LiteralPath $exports[0].FullName -Destination $destinationCsv
$lines=Get-Content -LiteralPath $destinationCsv
if($lines.Count-lt 2){throw 'Exporter CSV contains no data rows.'}
$firstEpoch=[int64](($lines[1]-split ',')[0]);$lastEpoch=[int64](($lines[-1]-split ',')[0])
if($firstEpoch-lt$fromEpoch-or$lastEpoch-ge$toEpoch){throw 'Exporter CSV contains a bar outside the requested period.'}
$coverageSlackSeconds=5*24*60*60
if($firstEpoch-gt($fromEpoch+$coverageSlackSeconds)-or$lastEpoch-lt($toEpoch-$coverageSlackSeconds)){throw 'Exporter CSV does not cover the requested period within the five-day market-closure allowance.'}
$metadata=[ordered]@{
 name=$Name;symbol='XAUUSD';timeframe='M1';digits=2;point=$Point;tickSize=$TickSize;from=$From;to=$To;model=4;delayMs=$delayMs
 localOnly=$true;sourceSha256=$manifest.source;binarySha256=$manifest.binary
 csvSha256=(Get-FileHash -LiteralPath $destinationCsv -Algorithm SHA256).Hash
 rowCount=$lines.Count-1;firstTimestamp=$firstEpoch;lastTimestamp=$lastEpoch
 report=(Resolve-Path -LiteralPath $report).Path;exportedAt=(Get-Date).ToUniversalTime().ToString('o')
}
$metadata|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $metadataPath -Encoding UTF8
Write-Output "Exported $($metadata.rowCount) completed M1 bars to $destinationCsv"
if(!$SkipAnalysis)
{
 $pythonExe=$Python
 if([string]::IsNullOrWhiteSpace($pythonExe)){$pythonExe=(Get-Command python -ErrorAction SilentlyContinue).Source}
 if([string]::IsNullOrWhiteSpace($pythonExe)){$pythonExe=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
 if(!(Test-Path -LiteralPath $pythonExe)){throw 'Python was not found. Pass -Python with an executable path.'}
 $resultPath=Join-Path $root "research\results_$Name.json"
 if(Test-Path -LiteralPath $resultPath){Remove-Item -LiteralPath $resultPath -Force}
 & $pythonExe (Join-Path $root 'research\analyze.py') $destinationCsv --point $Point --output $resultPath
 if($LASTEXITCODE-ne 0-or!(Test-Path -LiteralPath $resultPath)){throw 'Research analysis failed.'}
 $result=Get-Content -LiteralPath $resultPath -Raw|ConvertFrom-Json
 Write-Output "Research selected ATR threshold $($result.selected_threshold_atr); overall pass: $($result.overall_pass); result: $resultPath"
}
