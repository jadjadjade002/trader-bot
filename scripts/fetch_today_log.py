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
mql_file = root / 'MQL5/logs/20261001.log'
if mql_file.exists():
    print('=== ALL MQL5 LOG 2026-10-01 ===')
    lines = open(mql_file, encoding='utf-16-le', errors='ignore').readlines()
    for line in lines:
        print(line.strip())

term_file = root / 'logs/20261001.log'
if term_file.exists():
    print('=== ALL TERMINAL TRADES 2026-10-01 ===')
    lines = open(term_file, encoding='utf-16-le', errors='ignore').readlines()
    for line in lines:
        if 'Trades' in line or 'deal #' in line:
            print(line.strip())
"""

out, err = ssh(f"python3 -c \"{remote_py}\"")
sys.stdout.reconfigure(encoding='utf-8')
print(out)
