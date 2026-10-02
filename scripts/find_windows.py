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

py_code = """
import subprocess
out = subprocess.run(['DISPLAY=:0', 'xdotool', 'search', '--name', 'MetaTrader'], shell=True, capture_output=True, text=True).stdout
wids = [w.strip() for w in out.splitlines() if w.strip()]
print('Found wids:', wids)
for wid in wids:
    name = subprocess.run(['DISPLAY=:0', 'xdotool', 'getwindowname', wid], shell=True, capture_output=True, text=True).stdout.strip()
    print(f'wid={wid} -> {name}')
"""
res = ssh(f"python3 -c \"{py_code}\"")
print(res)
