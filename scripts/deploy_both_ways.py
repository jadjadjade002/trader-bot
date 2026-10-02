import subprocess
import time
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SSH_KEY = r"D:\project\trader-bot\key\ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def run_ssh(cmd):
    full_cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def run_scp(local_path, remote_path):
    full_cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", str(local_path), f"{HOST}:{remote_path}"]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.returncode

print("=== 1. Upload Binaries ===")
# V22 Swing to both
r1 = run_scp(Path("QuantumTitan_v22_Swing.ex5"), "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/QuantumTitan_v22_Swing.ex5")
r2 = run_scp(Path("QuantumTitan_v22_Swing.ex5"), "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Experts/QuantumTitan_v22_Swing.ex5")

# V16 Velocity to both
r3 = run_scp(Path("QuantumTitan_v16_Velocity.ex5"), "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/QuantumTitan_v16_Velocity.ex5")
r4 = run_scp(Path("QuantumTitan_v16_Velocity.ex5"), "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Experts/QuantumTitan_v16_Velocity.ex5")
print(f"Binary uploads: V22({r1}, {r2}), Velocity({r3}, {r4})")

print("\n=== 2. Upload Charts for Instance 1 (112334471: M15, H1, M5) ===")
inst1_dir = Path("dist_charts/inst1_112334471")
inst1_remote = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default"
run_ssh(f"rm -f '{inst1_remote}/chart'* '{inst1_remote}/order.wnd'")
for f in inst1_dir.iterdir():
    run_scp(f, f"{inst1_remote}/{f.name}")
print("Instance 1 charts uploaded.")

print("\n=== 3. Upload Charts for Instance 2 (112468807: M15, H1, M5, M1) ===")
inst2_dir = Path("dist_charts/inst2_112468807")
inst2_remote = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Profiles/Charts/V16_1"
run_ssh(f"rm -f '{inst2_remote}/chart'* '{inst2_remote}/order.wnd'")
for f in inst2_dir.iterdir():
    run_scp(f, f"{inst2_remote}/{f.name}")
print("Instance 2 charts uploaded.")

print("\n=== 4. Restart Target MetaTrader 5 (Account 112334471) ===")
out, _, _ = run_ssh("pgrep -af terminal64.exe")
for line in out.splitlines():
    if ("MetaTrader 5/terminal64.exe" in line or "MetaTrader 5\\terminal64.exe" in line) and "v16_1" not in line and "v21" not in line and "v17" not in line:
        pid = line.split()[0]
        print(f"Killing MT5 PID {pid}")
        run_ssh(f"kill -9 {pid}")

time.sleep(2)
launch_cmd1 = "DISPLAY=:0 nohup wine '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe' /portable /skipupdate > '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/v16_terminal.log' 2>&1 < /dev/null &"
run_ssh(launch_cmd1)
print("Started MT5 main instance.")

print("\n=== 5. Restart Test MetaTrader 5 v16_1 (Account 112468807) ===")
out, _, _ = run_ssh("pgrep -af terminal64.exe")
for line in out.splitlines():
    if "MetaTrader 5 v16_1" in line:
        pid = line.split()[0]
        print(f"Killing v16_1 PID {pid}")
        run_ssh(f"kill -9 {pid}")

time.sleep(2)
launch_cmd2 = "DISPLAY=:0 nohup wine '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/terminal64.exe' /portable /profile:V16_1 /skipupdate > '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/v16_1_terminal.log' 2>&1 < /dev/null &"
run_ssh(launch_cmd2)
print("Started MT5 v16_1 instance.")

print("\nWaiting 12 seconds for both terminals to initialize...")
time.sleep(12)

print("\n=== 6. Process State ===")
out, _, _ = run_ssh("pgrep -af terminal64.exe")
print(out)

print("\n=== 7. Instance 1 (112334471) MQL5 Logs ===")
mql1_checker = '''python3 -c "
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5')
logs = sorted((root / 'MQL5/logs').glob('202609*.log'))
if logs:
    with open(logs[-1], 'r', encoding='utf-16-le', errors='ignore') as f:
        print(''.join(f.readlines()[-15:]))
"'''
out, _, _ = run_ssh(mql1_checker)
print(out)

print("\n=== 8. Instance 2 (112468807) MQL5 Logs ===")
mql2_checker = '''python3 -c "
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1')
logs = sorted((root / 'MQL5/logs').glob('202609*.log'))
if logs:
    with open(logs[-1], 'r', encoding='utf-16-le', errors='ignore') as f:
        print(''.join(f.readlines()[-20:]))
"'''
out, _, _ = run_ssh(mql2_checker)
print(out)

print("\nDEPLOYMENT_BOTH_WAYS_COMPLETED")
