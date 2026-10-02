import subprocess
import time
import sys
from pathlib import Path

SSH_KEY = r"D:\project\trader-bot\key\ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def run_ssh(cmd):
    full_cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def run_scp(local_path, remote_path):
    full_cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", local_path, f"{HOST}:{remote_path}"]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.returncode

print("=== Step 1: Check running processes before replacement ===")
out, err, code = run_ssh("pgrep -af terminal64.exe")
print(out)

print("\n=== Step 2: Upload updated binary to MetaTrader 5 ===")
ret = run_scp(r"D:\project\trader-bot\QuantumTitan_v22_Swing.ex5", "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/QuantumTitan_v22_Swing.ex5")
print(f"Binary upload status: {ret}")
if ret != 0:
    print("Failed to upload binary!")
    sys.exit(1)

print("\n=== Step 3: Upload and run remote chart setup script ===")
remote_script = '''import os
from pathlib import Path

root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default')
root.mkdir(parents=True, exist_ok=True)

# Remove old multi-grid charts
for f in root.glob('chart0[3-9].chr'):
    print(f'Removing old chart: {f.name}')
    f.unlink()

chart1_content = """<chart>
id=6099001
symbol=XAUUSD
description=Gold vs US Dollar
period_type=0
period_size=15
digits=2
tick_size=0.010000
scale_fix=0
scale_bar=0
scale=16
mode=1
fore=0
grid=0
volume=1
scroll=1
shift=1
shift_size=15.000000
fixed_pos=0.000000
ticker=1
ohlc=1
one_click=0
one_click_btn=0
bidline=1
askline=1
lastline=0
days=0
descriptions=0
tradelines=0
tradehistory=0
window_left=0
window_top=0
window_right=960
window_bottom=540
window_type=1
floating=0
floating_left=0
floating_top=0
floating_right=0
floating_bottom=0
floating_type=1
floating_toolbar=1
floating_tbstate=
background_color=2234131
foreground_color=12496805
barup_color=10135078
bardown_color=5264367
bullcandle_color=10135078
bearcandle_color=5264367
chartline_color=10135078
volumes_color=10135078
grid_color=3023388
bidline_color=10135078
askline_color=5264367
lastline_color=49152
stops_color=255
windows_total=1

<expert>
name=QuantumTitan_v22_Swing
path=Experts\\QuantumTitan_v22_Swing.ex5
expertmode=1
<inputs>
InpDemoOnly=true
InpTargetAccount=112334471
InpBaseMagicNumber=991600
InpBaseLotSize=0.01
InpScaledLotSize=0.01
InpEquityScaleThreshold=999999.0
InpLogOrdersToCsv=true
InpMaxSpreadPoints=52.0
InpMaxSlippagePoints=25
InpMinConfidenceScore=80
InpMacroFastEma=50
InpMacroSlowEma=200
InpStructureFastEma=20
InpStructureSlowEma=50
InpRsiPeriod=14
InpAdxPeriod=14
InpMinAdxStrength=20.0
InpWickRatioThreshold=0.35
InpAtrPeriod=14
InpAtrStopMultiplier=1.8
InpRewardRiskRatio=2.2
InpEnableBreakeven=true
InpBreakevenTriggerR=1.0
InpBreakevenLockPoints=25.0
InpEnableChandelier=true
InpChandelierTriggerR=1.5
InpChandelierAtrMult=1.5
InpCooldownBars=2
InpMaxDailyDrawdownPct=5.0
InpFridayLockout=true
InpFridayCutoffHour=20
InpEnableHUD=true
</inputs>
</expert>

<window>
height=100.000000
objects=0

<indicator>
name=Main
path=
apply=1
show_data=1
scale_inherit=0
scale_line=0
scale_line_percent=50
scale_line_value=0.000000
scale_fix_min=0
scale_fix_min_val=0.000000
scale_fix_max=0
scale_fix_max_val=0.000000
expertmode=0
fixed_height=-1
</indicator>
</window>
</chart>
"""

chart2_content = chart1_content.replace('id=6099001', 'id=6099002').replace('period_type=0\nperiod_size=15', 'period_type=1\nperiod_size=1')

(root / 'chart01.chr').write_bytes(b'\xff\xfe' + chart1_content.encode('utf-16le'))
(root / 'chart02.chr').write_bytes(b'\xff\xfe' + chart2_content.encode('utf-16le'))
(root / 'order.wnd').write_bytes(b'\xff\xfe' + 'chart01.chr\r\nchart02.chr\r\n'.encode('utf-16le'))

print('Chart01 bytes:', len((root / 'chart01.chr').read_bytes()))
print('Chart02 bytes:', len((root / 'chart02.chr').read_bytes()))
print('Order.wnd bytes:', len((root / 'order.wnd').read_bytes()))
print('Profile configuration complete.')
'''

Path('scripts/remote_setup_profile.py').write_text(remote_script, encoding='utf-8')
ret = run_scp(r'scripts\remote_setup_profile.py', '/tmp/remote_setup_profile.py')
print(f'Uploaded remote setup script: {ret}')

out, err, code = run_ssh('python3 /tmp/remote_setup_profile.py')
print(out)
if err:
    print('Stderr:', err)

print('\n=== Step 4: Stop target MetaTrader 5 instance only & restart ===')
out, _, _ = run_ssh('pgrep -af terminal64.exe')
target_pids = []
for line in out.splitlines():
    if ('MetaTrader 5/terminal64.exe' in line or 'MetaTrader 5\\terminal64.exe' in line) and 'v16_1' not in line and 'v21' not in line:
        pid = line.split()[0]
        target_pids.append(pid)

print(f'Target PIDs to terminate: {target_pids}')
for pid in target_pids:
    print(f'Killing old baseline PID {pid}')
    run_ssh(f'kill -9 {pid}')

time.sleep(3)

print('Starting MetaTrader 5 with clean Default profile (V22 Swing)...')
launch_cmd = "DISPLAY=:0 nohup wine '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe' /portable /skipupdate > '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/v16_terminal.log' 2>&1 < /dev/null &"
run_ssh(launch_cmd)

print('Waiting 8 seconds for terminal initialization...')
time.sleep(8)

print('\n=== Step 5: Verify post-launch state ===')
out, _, _ = run_ssh('pgrep -af terminal64.exe')
print(out)

print('\n=== Step 6: Check latest terminal logs on 112334471 ===')
log_checker = '''python3 -c "
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5')
logs = sorted((root / 'logs').glob('202609*.log'))
if logs:
    with open(logs[-1], 'r', encoding='utf-16-le', errors='ignore') as f:
        print(''.join(f.readlines()[-20:]))
" '''
out, _, _ = run_ssh(log_checker)
print('--- Terminal Log ---')
print(out.encode('ascii', errors='replace').decode('ascii'))

mql_checker = '''python3 -c "
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5')
logs = sorted((root / 'MQL5/logs').glob('202609*.log'))
if logs:
    with open(logs[-1], 'r', encoding='utf-16-le', errors='ignore') as f:
        print(''.join(f.readlines()[-25:]))
" '''
out, _, _ = run_ssh(mql_checker)
print('--- MQL5 Log ---')
print(out.encode('ascii', errors='replace').decode('ascii'))
print('\nDEPLOYMENT_FINISHED_SUCCESSFULLY')
