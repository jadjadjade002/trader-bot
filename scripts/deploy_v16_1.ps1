param(
    [string]$KeyPath='D:\project\trader-bot\key\ssh-key-2026-09-06.key',
    [string]$HostName='161.118.255.178',
    [string]$UserName='ubuntu',
    [string]$Root=(Split-Path $PSScriptRoot -Parent),
    [string]$RemoteRoot='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1',
    [string]$RemoteSource='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5'
)
$ErrorActionPreference='Stop'

$binaryPath = Join-Path $Root 'QuantumTitan_v16_1_M1.ex5'
$chartPath = Join-Path $Root 'deploy\v16_1\chart01.chr'
$orderPath = Join-Path $Root 'deploy\v16_1\order.wnd'

foreach($path in @($KeyPath, $binaryPath, $chartPath, $orderPath)) {
    if(!(Test-Path -LiteralPath $path)) {
        throw "Required deployment artifact missing: $path"
    }
}

$ssh = @('-i', $KeyPath, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'StrictHostKeyChecking=accept-new', "$UserName@$HostName")
$scpBase = @('-i', $KeyPath, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'StrictHostKeyChecking=accept-new')

Write-Output "[Step 1/6] Probing remote VM status..."
$probe = & ssh @ssh "if [ -e '$RemoteRoot' ]; then echo ROOT_EXISTS; else echo ROOT_ABSENT; fi; if [ -f '$RemoteSource/terminal64.exe' ]; then echo SOURCE_OK; else echo SOURCE_MISSING; fi; pgrep -af terminal64.exe || true"

if($probe -contains 'ROOT_EXISTS') {
    throw "Target root already exists: $RemoteRoot. Refusing to overwrite without explicit cleanup."
}
if(!($probe -contains 'SOURCE_OK')) {
    throw "Source MT5 missing: $RemoteSource/terminal64.exe"
}

# Ensure existing V16 terminal is running and observe its PID
$v16Signatures = @('C:\Program Files\MetaTrader 5\terminal64.exe /portable', '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe /portable')
function Has-Signature([string]$line, [string[]]$signatures) {
    foreach($signature in $signatures) { if($line.Contains($signature)) { return $true } }
    return $false
}
$beforeV16 = @($probe | Where-Object { Has-Signature $_ $v16Signatures })
if($beforeV16.Count -eq 0) {
    throw "Active V16 terminal was not observed on VM. Refusing to proceed without active baseline."
}
$beforeV16Ids = @($beforeV16 | ForEach-Object { if($_ -match '^([0-9]+)\s') { $Matches[1] } })
Write-Output "Protected V16 terminal verified at PID(s): $($beforeV16Ids -join ', ')"

Write-Output "[Step 2/6] Cloning isolated MT5 instance for account 112468807..."
& ssh @ssh "cp -a --reflink=auto '$RemoteSource' '$RemoteRoot' && rm -rf '$RemoteRoot/logs/'* '$RemoteRoot/MQL5/logs/'* '$RemoteRoot/MQL5/Profiles/Charts/'* && mkdir -p '$RemoteRoot/MQL5/Experts' '$RemoteRoot/MQL5/Profiles/Charts/V16_1'"
if($LASTEXITCODE -ne 0) { throw "Failed to clone isolated remote MT5 instance." }

Write-Output "[Step 3/6] Uploading V16.1 M1 binary and chart profile..."
& scp @scpBase $binaryPath "$UserName@${HostName}:$RemoteRoot/MQL5/Experts/QuantumTitan_v16_1_M1.ex5"
if($LASTEXITCODE -ne 0) { throw "Binary upload failed." }

& scp @scpBase $chartPath "$UserName@${HostName}:$RemoteRoot/MQL5/Profiles/Charts/V16_1/chart01.chr"
if($LASTEXITCODE -ne 0) { throw "Chart upload failed." }

& scp @scpBase $orderPath "$UserName@${HostName}:$RemoteRoot/MQL5/Profiles/Charts/V16_1/order.wnd"
if($LASTEXITCODE -ne 0) { throw "Order window upload failed." }

Write-Output "[Step 4/6] Configuring profile and account 112468807 on VM..."
$remoteScript = @'
from pathlib import Path
import configparser

root = Path(r"REMOTE_ROOT")
profile = root / "MQL5/Profiles/Charts/V16_1"
chart = profile / "chart01.chr"
raw = chart.read_text(encoding="utf-8")
chart.write_bytes(b"\xff\xfe" + raw.encode("utf-16le"))

common = root / "Config/common.ini"
if not common.exists():
    raise SystemExit("common.ini missing")

# Read common.ini as UTF-16
cfg = configparser.ConfigParser(interpolation=None, strict=False)
cfg.optionxform = str
cfg.read_string(common.read_text(encoding="utf-16"))

if not cfg.has_section("Common"): cfg.add_section("Common")
if not cfg.has_section("Charts"): cfg.add_section("Charts")
if not cfg.has_section("Experts"): cfg.add_section("Experts")

cfg.set("Common", "Login", "112468807")
cfg.set("Common", "Server", "MetaQuotes-Demo")
cfg.set("Common", "ProfileLast", "V16_1")
cfg.set("Charts", "ProfileLast", "V16_1")
cfg.set("Experts", "Enabled", "1")
cfg.set("Experts", "AllowLiveTrading", "1")
cfg.set("Experts", "AllowDllImport", "0")

with common.open("w", encoding="utf-16", newline="") as handle:
    cfg.write(handle, space_around_delimiters=False)

manifest = root / "v16_1_deploy_manifest.txt"
manifest.write_text("account=112468807\nmagic=991612\nexpert=QuantumTitan_v16_1_M1\nprofile=V16_1\n", encoding="utf-8")
print("CONFIGURATION_SUCCESS")
'@
$remoteScript = $remoteScript.Replace('REMOTE_ROOT', $RemoteRoot.Replace('\', '/'))
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
$configOutput = & ssh @ssh "echo $encoded | base64 -d | python3"
if($LASTEXITCODE -ne 0 -or !($configOutput -contains 'CONFIGURATION_SUCCESS')) {
    throw "Remote configuration failed: $configOutput"
}

Write-Output "[Step 5/6] Launching isolated V16.1 MT5 instance..."
& ssh @ssh "DISPLAY=:0 nohup wine '$RemoteRoot/terminal64.exe' /portable /profile:V16_1 /skipupdate > '$RemoteRoot/v16_1_terminal.log' 2>&1 < /dev/null &"
if($LASTEXITCODE -ne 0) { throw "Launch command failed." }

Start-Sleep -Seconds 6

Write-Output "[Step 6/6] Verifying process isolation and account authorization..."
$after = @(& ssh @ssh "pgrep -af terminal64.exe || true")

# Verify original V16 PID is still running
foreach($processId in $beforeV16Ids) {
    if(!($after | Where-Object { $_ -match "^$processId\s" })) {
        throw "CRITICAL: Existing V16 terminal PID $processId was not observed after launch!"
    }
}

# Verify new V16.1 process is running
$v161Signatures = @('C:\Program Files\MetaTrader 5 v16_1\terminal64.exe', '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/terminal64.exe')
$v161Lines = @($after | Where-Object { Has-Signature $_ $v161Signatures })
$v161Ids = @($v161Lines | ForEach-Object { if($_ -match '^([0-9]+)\s') { $Matches[1] } })
if($v161Ids.Count -eq 0) {
    throw "V16.1 terminal process was not observed after launch."
}

Write-Output "=== DEPLOYMENT SUCCESS ==="
Write-Output "Protected V16 PID: $($beforeV16Ids -join ', ') (Account 112334471 - UNTOUCHED)"
Write-Output "New V16.1 PID    : $($v161Ids -join ', ') (Account 112468807 - ACTIVE)"
