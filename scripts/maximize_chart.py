import subprocess
import time

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

wid = '41943041'
# Maximize inner chart window using Ctrl+F10
subprocess.run(['xdotool', 'key', '--window', wid, 'ctrl+F10'], env=env)
time.sleep(1)

# Take screenshot
out_img = '/tmp/v23_front.png'
subprocess.run(['scrot', '-o', out_img], env=env)
"""

import base64
b64 = base64.b64encode(py_script.encode('utf-8')).decode('ascii')
cmd_ssh = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""
ssh(cmd_ssh)

subprocess.run(["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{HOST}:/tmp/v23_front.png", "v23_front.png"])
print("Updated v23_front.png")
