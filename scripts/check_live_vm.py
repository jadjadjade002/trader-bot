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
mql_logs = sorted((root / 'MQL5/logs').glob('*.log'))
if mql_logs:
    print('=== Latest MQL5 Log:', mql_logs[-1].name, '===')
    lines = open(mql_logs[-1], encoding='utf-16-le', errors='ignore').readlines()
    print(''.join(lines[-40:]))

term_logs = sorted((root / 'logs').glob('*.log'))
if term_logs:
    print('=== Latest Terminal Log:', term_logs[-1].name, '===')
    lines = open(term_logs[-1], encoding='utf-16-le', errors='ignore').readlines()
    print(''.join(lines[-30:]))
"""

out, err = ssh(f"python3 -c \"{remote_py}\"")
sys.stdout.reconfigure(encoding='utf-8')
print(out)
if err:
    print("ERR:", err)
