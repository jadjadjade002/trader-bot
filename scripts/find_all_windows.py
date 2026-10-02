import subprocess
import os

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

py_script = """
import subprocess, os

env = os.environ.copy()
env['DISPLAY'] = ':0'

# Check running terminals
ps = subprocess.run(['pgrep', '-af', 'terminal64.exe'], capture_output=True, text=True).stdout
print('Running terminals:\\n', ps)

# Find all windows on desktop
windows = subprocess.run(['xdotool', 'search', '--onlyvisible', '--class', 'terminal64.exe'], env=env, capture_output=True, text=True).stdout.splitlines()
if not windows:
    windows = subprocess.run(['xdotool', 'search', '--class', 'wine'], env=env, capture_output=True, text=True).stdout.splitlines()

print('Found window IDs:', windows)
for wid in windows:
    name = subprocess.run(['xdotool', 'getwindowname', wid], env=env, capture_output=True, text=True).stdout.strip()
    pid = subprocess.run(['xdotool', 'getwindowpid', wid], env=env, capture_output=True, text=True).stdout.strip()
    print(f'WID: {wid} | PID: {pid} | Title: {name}')
"""

import base64
b64 = base64.b64encode(py_script.encode('utf-8')).decode('ascii')
cmd_ssh = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""
print(ssh(cmd_ssh))
