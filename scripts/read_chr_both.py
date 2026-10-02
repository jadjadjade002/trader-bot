import subprocess
import sys

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def ssh(cmd):
    res = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return res.stdout, res.stderr

remote_py = """
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo')
for p in [root / 'Profiles/Charts/Default/chart01.chr', root / 'MQL5/Profiles/Charts/Default/chart01.chr']:
    if p.exists():
        print('=== PATH:', p, '===')
        lines = open(p, errors='ignore').readlines()
        print(''.join(lines[:40]))
"""

out, err = ssh(f"python3 -c \"{remote_py}\"")
sys.stdout.reconfigure(encoding='utf-8')
print(out)
