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
import re

root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo')
term_logs = sorted((root / 'logs').glob('2026*.log'))
print(f'Scanning {len(term_logs)} log files...')

all_deals = []
for p in term_logs:
    lines = open(p, encoding='utf-16-le', errors='ignore').readlines()
    for l in lines:
        if '5056497798' in l and 'deal #' in l:
            all_deals.append(l.strip())

print(f'Total deal entries found: {len(all_deals)}')
for d in all_deals:
    print(d)
"""

out, err = ssh(f"python3 -c \"{remote_py}\"")
sys.stdout.reconfigure(encoding='utf-8')
print(out)
