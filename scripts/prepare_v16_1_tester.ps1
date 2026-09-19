param(
    [string]$InstalledTerminal='C:\Program Files\MetaTrader 5',
    [string]$DataDirectory='C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075'
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v16_1.local'
New-Item -ItemType Directory -Path $lab -Force | Out-Null
foreach($folder in @('Config','MQL5\Experts','MQL5\Profiles\Tester','reports','bases','Tester\bases')) {
    New-Item -ItemType Directory -Path (Join-Path $lab $folder) -Force | Out-Null
}

foreach($exe in @('terminal64.exe','metatester64.exe')) {
    Copy-Item -LiteralPath (Join-Path $InstalledTerminal $exe) -Destination $lab -Force
}

foreach($file in @('accounts.dat','servers.dat','common.ini')) {
    $source=Join-Path $DataDirectory ('config\'+$file)
    if(Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $lab 'Config') -Force
    }
}

# Copy cached XAUUSD history/ticks from existing local tester to avoid slow re-download
$existingLab=Join-Path $root '.mt5-v17.local'
if(Test-Path -LiteralPath $existingLab) {
    if(Test-Path -LiteralPath (Join-Path $existingLab 'bases\MetaQuotes-Demo')) {
        Copy-Item -LiteralPath (Join-Path $existingLab 'bases\MetaQuotes-Demo') -Destination (Join-Path $lab 'bases') -Recurse -Force
    }
    if(Test-Path -LiteralPath (Join-Path $existingLab 'Tester\bases\MetaQuotes-Demo')) {
        Copy-Item -LiteralPath (Join-Path $existingLab 'Tester\bases\MetaQuotes-Demo') -Destination (Join-Path $lab 'Tester\bases') -Recurse -Force
    }
}

# Copy both EAs into MQL5\Experts
foreach($name in @('QuantumTitan_v16_Velocity','QuantumTitan_v16_1_M1')) {
    $src = Join-Path $root ($name+'.ex5')
    if(Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $lab 'MQL5\Experts') -Force
    }
}
Write-Output "Isolated V16 vs V16.1 tester environment prepared: $lab"
