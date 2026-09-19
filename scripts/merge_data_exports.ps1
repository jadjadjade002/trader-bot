param(
 [Parameter(Mandatory=$true)][string[]]$Inputs,
 [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$expected='time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,spread_points,real_volume'
$allRows=[System.Collections.Generic.List[string]]::new()
$previous=[int64]-1
$inputHashes=[ordered]@{}
foreach($inputPath in $Inputs)
{
 $resolved=(Resolve-Path -LiteralPath $inputPath).Path
 $lines=Get-Content -LiteralPath $resolved
 if($lines.Count-lt 2-or$lines[0]-ne$expected){throw "Invalid or empty export: $resolved"}
 $inputHashes[$resolved]=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
 foreach($line in $lines[1..($lines.Count-1)])
 {
  $epoch=[int64](($line-split ',',2)[0])
  if($epoch-le$previous){throw "Inputs overlap or are not strictly increasing at epoch $epoch."}
  $allRows.Add($line);$previous=$epoch
 }
}
$outputPath=[IO.Path]::GetFullPath((Join-Path (Get-Location) $Output))
New-Item -ItemType Directory -Path (Split-Path $outputPath -Parent) -Force|Out-Null
@($expected)+$allRows|Set-Content -LiteralPath $outputPath -Encoding utf8
$metadata=[ordered]@{
 inputs=$inputHashes;outputSha256=(Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash
 rowCount=$allRows.Count;firstTimestamp=[int64](($allRows[0]-split ',',2)[0]);lastTimestamp=$previous
 mergedAt=(Get-Date).ToUniversalTime().ToString('o')
}
$metadata|ConvertTo-Json -Depth 4|Set-Content -LiteralPath "$outputPath.metadata.json" -Encoding utf8
Write-Output "Merged $($allRows.Count) strictly ordered rows to $outputPath"
