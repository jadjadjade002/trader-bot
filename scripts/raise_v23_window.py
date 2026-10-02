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
import subprocess, os, time

env = os.environ.copy()
env['DISPLAY'] = ':0'

target_wid = '41943041'
# If target_wid changed, search fresh
wids = subprocess.run(['xdotool', 'search', '--class', 'terminal64.exe'], env=env, capture_output=True, text=True).stdout.splitlines()
found_wid = None
for wid in wids:
    name = subprocess.run(['xdotool', 'getwindowname', wid], env=env, capture_output=True, text=True).stdout.strip()
    if '5056497798' in name:
        found_wid = wid
        break

if not found_wid:
    found_wid = target_wid

print(f'Activating and raising window {found_wid}...')
subprocess.run(['xdotool', 'windowactivate', '--sync', found_wid], env=env)
subprocess.run(['xdotool', 'windowraise', found_wid], env=env)
subprocess.run(['xdotool', 'windowfocus', '--sync', found_wid], env=env)
subprocess.run(['xdotool', 'windowsize', found_wid, '1920', '1080'], env=env)
subprocess.run(['xdotool', 'windowmove', found_wid, '0', '0'], env=env)
time.sleep(1)

out_img = '/tmp/v23_front.png'
subprocess.run(['scrot', '-o', out_img], env=env)
print('Screenshot taken with scrot:', os.path.exists(out_img))
"""

import base64
b64 = base64.b64encode(py_script.encode('utf-8')).decode('ascii')
cmd_ssh = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""
print(ssh(cmd_ssh))

# Download screenshot to local
subprocess.run(["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{HOST}:/tmp/v23_front.png", "v23_front.png"])
print("Downloaded v23_front.png locally.")
