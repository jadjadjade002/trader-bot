$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lab = Join-Path $root 'reports\v23_backtest_20261004\lab'
$recent = Join-Path $root '.mt5-v17.local'
$older = Join-Path $root '.mt5-v20.local'
$exe = Join-Path $lab 'terminal64.exe'
if (Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe) { throw 'V23 isolated tester running.' }
if (Test-Path -LiteralPath $exe) { throw 'Lab already exists; preserve existing evidence.' }
foreach ($dir in @('Config','MQL5\Experts','MQL5\Profiles\Tester','reports')) {
    New-Item -ItemType Directory -Path (Join-Path $lab $dir) -Force | Out-Null
}
foreach ($name in @('terminal64.exe','metatester64.exe')) {
    Copy-Item -LiteralPath (Join-Path $recent $name) -Destination $lab
}
foreach ($name in @('accounts.dat','servers.dat')) {
    Copy-Item -LiteralPath (Join-Path $recent "Config\$name") -Destination (Join-Path $lab "Config\$name")
}
$lines = Get-Content -LiteralPath (Join-Path $recent 'Config\common.ini')
$loginLine = $lines | Where-Object { $_ -match '^Login=\d+$' } | Select-Object -First 1
$serverLine = $lines | Where-Object { $_ -match '^Server=MetaQuotes-Demo$' } | Select-Object -First 1
if (!$loginLine -or !$serverLine) { throw 'Cached demo tester account selector missing.' }
@('[Common]',$loginLine,$serverLine,'KeepPrivate=1','NewsEnable=0','[Experts]','Enabled=0','AllowLiveTrading=0','AllowDllImport=0') | Set-Content -LiteralPath (Join-Path $lab 'Config\common.ini') -Encoding Unicode
$manifest = @()
foreach ($relative in @('bases\MetaQuotes-Demo\history\XAUUSD','Tester\bases\MetaQuotes-Demo\history\XAUUSD')) {
    $dest = Join-Path $lab $relative
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $recent $relative) -File | Where-Object Name -match '^202[56]\.hc[cs]$' | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $dest
        $manifest += [ordered]@{path="$relative\$($_.Name)";origin='.mt5-v17.local';bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}
    }
}
$tickRelative = 'bases\MetaQuotes-Demo\ticks\XAUUSD'
$tickDest = Join-Path $lab $tickRelative
New-Item -ItemType Directory -Path $tickDest -Force | Out-Null
foreach ($month in @('202604','202605','202606','202607','202608','202609')) {
    $origin = if ($month -ge '202608') { $recent } else { $older }
    $file = Get-Item -LiteralPath (Join-Path $origin "$tickRelative\$month.tkc")
    Copy-Item -LiteralPath $file.FullName -Destination $tickDest
    $manifest += [ordered]@{path="$tickRelative\$($file.Name)";origin=(Split-Path $origin -Leaf);bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName).Hash}
}
Copy-Item -LiteralPath (Join-Path $recent "$tickRelative\ticks.dat") -Destination $tickDest
Copy-Item -LiteralPath (Join-Path $root 'AegisPredator_v23.ex5') -Destination (Join-Path $lab 'MQL5\Experts\AegisPredator_v23.ex5')
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $lab '..\cache_seed_manifest.json') -Encoding UTF8
Write-Output "Tester-only lab prepared: $lab"
