import os
import subprocess
import paramiko
import base64

SSH_HOST = "161.118.255.178"
SSH_USER = "ubuntu"
SSH_KEY = "key/ssh-key-2026-09-06.key"
REMOTE_BASE = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo"

# Generate chart01.chr content (UTF-16LE)
chart_content = """<chart>
id=6099023
symbol=XAUUSD
description=Gold vs US Dollar
period_type=0
period_size=1
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
background_color=1710618
foreground_color=7895160
barup_color=10135078
bardown_color=5264367
bullcandle_color=10135078
bearcandle_color=5264367
chartline_color=10135078
volumes_color=7502370
grid_color=2302755
bidline_color=7502370
askline_color=5264367
lastline_color=10135078
stops_color=5264367
windows_total=1

<expert>
name=AegisPredator_v23
path=Experts\\AegisPredator_v23.ex5
expertmode=1
<inputs>
InpEnableSessionGuard=false
InpEnableSpreadGuard=false
InpEnableMarginGuard=true
InpEnableHardSL=true
InpStartHour=11
InpEndHour=16
InpMaxSpreadPts=25
InpMaxHoldBars=60
InpDonchianPeriod=20
InpATRPeriod=14
InpStopLossATRMul=1.5
InpTakeProfitRRMul=2.0
InpMinSLPoints=150
InpLotSize=0.01
InpFadeBreakouts=true
InpMagicNumber=992300
InpTargetAccount=5056497798
InpEnableCircuitBreaker=true
InpMaxConsecutiveLosses=4
InpCooldownMinutes=90
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

# Write locally as UTF-16LE with BOM
local_chr = "scratch_chart01.chr"
with open(local_chr, "wb") as f:
    f.write(chart_content.encode("utf-16"))

print(f"Generated {local_chr} successfully.")

# SCP upload to VM
key_path = os.path.abspath(SSH_KEY)
ex5_local = "AegisPredator_v23.ex5"
mq5_local = "AegisPredator_v23.mq5"

print("Uploading Aegis Predator V23 binary, source, and chart configs via SFTP...")
k = paramiko.RSAKey.from_private_key_file(key_path)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, username=SSH_USER, pkey=k)
sftp = ssh.open_sftp()

# Upload ex5 and mq5 to Experts folder
remote_experts = f"{REMOTE_BASE}/MQL5/Experts"
sftp.put(ex5_local, f"{remote_experts}/AegisPredator_v23.ex5")
sftp.put(mq5_local, f"{remote_experts}/AegisPredator_v23.mq5")
print("Uploaded AegisPredator_v23.ex5 and AegisPredator_v23.mq5.")

# Upload chart01.chr to both MQL5/Profiles and Profiles
sftp.put(local_chr, f"{REMOTE_BASE}/MQL5/Profiles/Charts/Default/chart01.chr")
sftp.put(local_chr, f"{REMOTE_BASE}/Profiles/Charts/Default/chart01.chr")
print("Uploaded chart01.chr to both profiles.")

sftp.close()

# Graceful restart of MT5 process
print("Restarting MT5 terminal on VM...")
py_restart = f"""
import subprocess, os, time
subprocess.run(['pkill', '-9', '-f', 'MetaTrader 5 V16.59 V22 New Demo'])
time.sleep(2)
env = os.environ.copy()
env['DISPLAY'] = ':0'
env['WINEDLLOVERRIDES'] = 'mscoree,mshtml='
remote_base = '{REMOTE_BASE}'
cmd = ['wine', f'{{remote_base}}/terminal64.exe', '/skipupdate:F406D2C8804407B0B5AD6F4C205B4D8B', '/portable']
log_f = open(f'{{remote_base}}/v23_daemon.log', 'w')
proc = subprocess.Popen(cmd, cwd=remote_base, env=env, stdout=log_f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
print('Launched PID:', proc.pid)
"""
b64 = base64.b64encode(py_restart.encode('utf-8')).decode('ascii')
cmd_ssh = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""

stdin, stdout, stderr = ssh.exec_command(cmd_ssh)
output = stdout.read().decode("utf-8")
errors = stderr.read().decode("utf-8")
print("Restart output:\n", output)
if errors:
    print("Restart errors:\n", errors)

ssh.close()
if os.path.exists(local_chr):
    os.remove(local_chr)
print("Deployment of Aegis Predator V23 completed.")
