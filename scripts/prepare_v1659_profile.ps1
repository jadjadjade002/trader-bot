param(
    [string]$Source = '.deploy_new_112882967\chart01_v1657.chr',
    [string]$Output = '.deploy_new_112882967\chart01_v1659.chr',
    [ulong]$TargetAccount = 112882967
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$sourcePath = Join-Path $root $Source
$outputPath = Join-Path $root $Output
if (!(Test-Path -LiteralPath $sourcePath)) { throw "Missing source profile: $sourcePath" }
$text = Get-Content -LiteralPath $sourcePath -Raw
$expert = @"
<expert>
name=QuantumTitan_v16_59_R4StateTransition
path=Experts\QuantumTitan_v16_59_R4StateTransition.ex5
expertmode=1
<inputs>
InpTargetAccount=$TargetAccount
InpIndicatorSeedStart=1754870400
InpEmergencyStop=false
</inputs>
</expert>
"@
$updated = [regex]::Replace($text, '(?s)<expert>.*?</expert>', $expert, 1)
if ($updated -eq $text) { throw 'Expert block was not replaced.' }
$updated | Set-Content -LiteralPath $outputPath -Encoding Unicode
Write-Output $outputPath
