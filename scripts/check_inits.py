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
for p in sorted((root / 'MQL5/logs').glob('*.log')):
    lines = open(p, encoding='utf-16-le', errors='ignore').readlines()
    inits = [l.strip() for l in lines if 'INITIALIZED' in l or 'V23' in l]
    if inits:
        print(p.name, '->', len(inits), 'events. First:', inits[0])
"""

out, err = ssh(f"python3 -c \"{remote_py}\"")
sys.stdout.reconfigure(encoding='utf-8')
print(out)
