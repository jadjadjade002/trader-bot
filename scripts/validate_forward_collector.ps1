param([string]$Root=(Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
$source=Join-Path $Root 'QuantumTitan_ForwardCollector.mq5'
$binary=Join-Path $Root 'QuantumTitan_ForwardCollector.ex5'
$manifestPath=Join-Path $Root 'compiled\QuantumTitan_ForwardCollector.build.json'
foreach($path in @($source,$binary,$manifestPath,(Join-Path $Root 'deploy\forward\chart01.chr'),(Join-Path $Root 'deploy\forward\order.wnd'))){if(!(Test-Path -LiteralPath $path)){throw "Required artifact missing: $path"}}
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash-ne$manifest.source){throw 'Source hash does not match the build manifest.'}
if((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash-ne$manifest.binary){throw 'Binary hash does not match the build manifest. Recompile after source changes.'}
$sourceText=Get-Content -LiteralPath $source -Raw
foreach($token in @('const string RUN_ID="FWD_20260909_4W";','const datetime PLANNED_END=D''2026.10.07 15:00:00'';','const string DATA_DIR="QTForward\\";','EventSetTimer(HEALTH_SECONDS)','QTForward_XAUUSD_M1_','QTForward_health_')){if(!$sourceText.Contains($token)){throw "Forward contract token missing: $token"}}
if($sourceText -match '(?i)CTrade|MqlTrade|OrderSend|PositionModify|PositionClose|GlobalVariable|ChartApplyTemplate|RiskGuardian|WebRequest'){throw 'Forbidden trade or terminal-mutation token found.'}
$chart=Get-Content -LiteralPath (Join-Path $Root 'deploy\forward\chart01.chr') -Raw
foreach($token in @('symbol=XAUUSD','period_size=1','name=QuantumTitan_ForwardCollector','path=Experts\QuantumTitan_ForwardCollector.ex5','expertmode=1')){if($chart -notmatch [regex]::Escape($token)){throw "Chart profile token missing: $token"}}
Write-Output "Forward collector package is locally consistent. run=$($manifest.runId) source=$($manifest.source.Substring(0,12)) binary=$($manifest.binary.Substring(0,12))"
