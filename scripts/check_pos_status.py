import subprocess

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def ssh(cmd):
    return subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    ).stdout

script = """
from pathlib import Path
root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/logs')
log_file = sorted(root.glob('20261001.log'))[-1]
lines = open(log_file, encoding='utf-16-le', errors='ignore').readlines()
trades = [l.strip() for l in lines if '5056497798' in l and ('deal #' in l or 'order #' in l or 'Trades' in l)]
for t in trades[-10:]:
    print(t)
"""
import base64
b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')
cmd = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""
print(ssh(cmd))
