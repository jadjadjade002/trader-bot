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

launch_cmd = f"""
cd "{remote_base}"
export DISPLAY=:0
export WINEDLLOVERRIDES="mscoree,mshtml="
nohup wine "{remote_base}/terminal64.exe" /portable /skipupdate > "{remote_base}/launch_v23_clean.log" 2>&1 < /dev/null &
sleep 5
ps aux | grep -i "V16.59 V22 New Demo" | grep -v grep
"""

out, err = ssh(launch_cmd)
print("Output:\n", out)
if err:
    print("Err:\n", err)
