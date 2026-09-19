param(
    [string]$InstalledTerminal='C:\Program Files\MetaTrader 5',
    [string]$DataDirectory='C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075'
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lab=Join-Path $root '.mt5-v17.local'
New-Item -ItemType Directory -Path $lab -Force | Out-Null
foreach($folder in @('Config','MQL5\Experts','MQL5\Profiles\Tester','reports')) {
    New-Item -ItemType Directory -Path (Join-Path $lab $folder) -Force | Out-Null
}
# No production profiles/EAs are copied; no VM restart or account writes.
foreach($exe in @('terminal64.exe','metatester64.exe')) {
    Copy-Item -LiteralPath (Join-Path $InstalledTerminal $exe) -Destination $lab
}
# Credentials remain only in the ignored local directory, never printed.
foreach($file in @('accounts.dat','servers.dat','common.ini')) {
    $source=Join-Path $DataDirectory ('config\'+$file)
    if(Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $lab 'Config')
    }
}
foreach($name in @('QuantumTitan_v17','QuantumTitan_v16_Velocity','QuantumTitan_v16_Apex')) {
    Copy-Item -LiteralPath (Join-Path $root ($name+'.ex5')) -Destination (Join-Path $lab 'MQL5\Experts')
}
Write-Output "Isolated free tester prepared: $lab"
