param(
    [string]$KeyPath='D:\project\trader-bot\key\ssh-key-2026-09-06.key',
    [string]$HostName='161.118.255.178',
    [string]$UserName='ubuntu',
    [string]$RemoteRoot='/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1'
)
$ErrorActionPreference='Stop'

$ssh = @('-i', $KeyPath, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'StrictHostKeyChecking=accept-new', "$UserName@$HostName")

Write-Output "Step 1: Check baseline PIDs..."
$before = & ssh @ssh "pgrep -af terminal64.exe"
Write-Output $before

# Verify protected V16 PID 100324 is running
if(!($before | Where-Object { $_ -match "^100324\s" })) {
    throw "CRITICAL: Protected V16 baseline (PID 100324) not observed!"
}

Write-Output "Step 2: Update chart01.chr and restart MetaTrader 5 v16_1..."
$remoteCmd = @"
python3 -c "
from pathlib import Path
import os, signal, subprocess, time

root = Path('$RemoteRoot')
tmp = root / 'MQL5/Profiles/Charts/V16_1/chart01_utf8.tmp'
dst = root / 'MQL5/Profiles/Charts/V16_1/chart01.chr'

if tmp.exists():
    raw = tmp.read_text(encoding='utf-8')
    dst.write_bytes(b'\xff\xfe' + raw.encode('utf-16le'))
    tmp.unlink()
    print('CHART_CONVERTED_OK')

# Find and terminate only MetaTrader 5 v16_1
try:
    pids = subprocess.check_output(['pgrep', '-f', 'MetaTrader 5 v16_1']).decode().split()
    for pid in pids:
        print('Killing target PID', pid)
        os.kill(int(pid), signal.SIGKILL)
except Exception as e:
    print('No existing v16_1 pid or error:', e)

time.sleep(2)
"
DISPLAY=:0 nohup wine "$RemoteRoot/terminal64.exe" /portable /profile:V16_1 /skipupdate > "$RemoteRoot/v16_1_terminal.log" 2>&1 < /dev/null &
"@

& ssh @ssh $remoteCmd
Start-Sleep -Seconds 6

Write-Output "Step 3: Verifying processes after launch..."
$after = & ssh @ssh "pgrep -af terminal64.exe"
Write-Output $after

if(!($after | Where-Object { $_ -match "^100324\s" })) {
    throw "CRITICAL: Protected V16 baseline (PID 100324) was affected!"
}

Write-Output "Step 4: Check V22 Swing MT5 logs..."
& ssh @ssh "find '$RemoteRoot/logs/' '$RemoteRoot/MQL5/logs/' -name '*.log' -exec tail -n 15 {} +"
