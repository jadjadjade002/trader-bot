import subprocess
import time

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def ssh(cmd):
    p = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return p.stdout, p.stderr

remote_base = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo"

cmd = f"""
pkill -9 -f "MetaTrader 5 V16.59 V22 New Demo" || true
sleep 2
cd "{remote_base}"
export DISPLAY=:0
export WINEDLLOVERRIDES="mscoree,mshtml="
DISPLAY=:0 nohup wine "{remote_base}/terminal64.exe" /portable /skipupdate > /dev/null 2>&1 &
sleep 5
ps aux | grep -i "V16.59 V22 New Demo" | grep -v grep
"""

out, err = ssh(cmd)
print("Out:\n", out)
if err:
    print("Err:\n", err)
