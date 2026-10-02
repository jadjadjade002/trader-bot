import subprocess

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def ssh(cmd):
    p = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return p.stdout, p.stderr

py_launch = """
import subprocess, os

pkill = subprocess.run(['pkill', '-9', '-f', 'MetaTrader 5 V16.59 V22 New Demo'])

env = os.environ.copy()
env['DISPLAY'] = ':0'
env['WINEDLLOVERRIDES'] = 'mscoree,mshtml='

remote_base = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo'
cmd = [
    'wine',
    f'{remote_base}/terminal64.exe',
    '/skipupdate:F406D2C8804407B0B5AD6F4C205B4D8B',
    '/portable'
]

log_f = open(f'{remote_base}/v23_daemon.log', 'w')
proc = subprocess.Popen(
    cmd,
    cwd=remote_base,
    env=env,
    stdout=log_f,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True
)
print('Launched PID:', proc.pid)
"""

import base64
b64 = base64.b64encode(py_launch.encode('utf-8')).decode('ascii')
cmd_ssh = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""

out, err = ssh(cmd_ssh)
print("Out:\n", out)
if err:
    print("Err:\n", err)
