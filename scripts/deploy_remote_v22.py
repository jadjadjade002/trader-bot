import subprocess
import time

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

print("=== Step 1: Check running processes on VM ===")
out, err, code = run_ssh("pgrep -af terminal64.exe")
print(out)
assert "100324" in out, "Protected V16 terminal (PID 100324) missing!"

print("\n=== Step 2: Upload updated binary & chart profile ===")
ret = run_scp(r"D:\project\trader-bot\QuantumTitan_v22_Swing.ex5", "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Experts/QuantumTitan_v22_Swing.ex5")
print("Binary upload returncode:", ret)

ret = run_scp(r"D:\project\trader-bot\deploy\v22_swing\chart01.chr", "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Profiles/Charts/V16_1/chart01_utf8.txt")
print("Chart 01 upload returncode:", ret)

ret = run_scp(r"D:\project\trader-bot\deploy\v22_swing\chart02.chr", "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Profiles/Charts/V16_1/chart02_utf8.txt")
print("Chart 02 upload returncode:", ret)

print("\n=== Step 3: Convert charts to UTF-16LE on VM & configure order.wnd ===")
remote_setup = """python3 -c "
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/Profiles/Charts/V16_1')

c1_txt = root / 'chart01_utf8.txt'
c1_chr = root / 'chart01.chr'
c1_chr.write_bytes(b'\\xff\\xfe' + c1_txt.read_text(encoding='utf-8').encode('utf-16le'))

c2_txt = root / 'chart02_utf8.txt'
c2_chr = root / 'chart02.chr'
c2_chr.write_bytes(b'\\xff\\xfe' + c2_txt.read_text(encoding='utf-8').encode('utf-16le'))

order_wnd = root / 'order.wnd'
order_wnd.write_bytes(b'\\xff\\xfe' + 'chart01.chr\\r\\nchart02.chr\\r\\n'.encode('utf-16le'))

print('Chart01 bytes:', len(c1_chr.read_bytes()))
print('Chart02 bytes:', len(c2_chr.read_bytes()))
print('Order.wnd bytes:', len(order_wnd.read_bytes()))
" """
out, err, code = run_ssh(remote_setup)
print(out)

print("\n=== Step 4: Stop target v16_1 instance only & restart with V22 Swing ===")
# Find pid of v16_1
out, _, _ = run_ssh("pgrep -f 'MetaTrader 5 v16_1'")
for pid in out.split():
    print(f"Killing old v16_1 PID {pid}")
    run_ssh(f"kill -9 {pid}")

time.sleep(2)

# Launch isolated terminal on 112468807
launch_cmd = "DISPLAY=:0 nohup wine '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/terminal64.exe' /portable /profile:V16_1 /skipupdate > '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/v16_1_terminal.log' 2>&1 < /dev/null &"
run_ssh(launch_cmd)

time.sleep(6)

print("\n=== Step 5: Verify post-launch state ===")
out, _, _ = run_ssh("pgrep -af terminal64.exe")
print(out)
assert "100324" in out, "CRITICAL: Protected V16 baseline was killed!"
assert "MetaTrader 5 v16_1" in out, "New V22 terminal did not start!"

log_checker = """python3 -c "
import os
log_dir = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1/MQL5/logs'
files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
if files:
    latest = os.path.join(log_dir, files[-1])
    with open(latest, 'r', encoding='utf-16-le', errors='ignore') as f:
        print(''.join(f.readlines()[-30:]))
" """
out, _, _ = run_ssh(log_checker)
print("--- MQL5 Log ---")
print(out.encode('ascii', errors='replace').decode('ascii'))
print("\nDEPLOYMENT_FINISHED_SUCCESSFULLY")
