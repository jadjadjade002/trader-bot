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

remote_base = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo"

cmd = f"""
export DISPLAY=:0
cd "{remote_base}"
timeout 4 wine terminal64.exe /portable /skipupdate
"""

out, err = ssh(cmd)
print("Out:\n", out)
print("Err:\n", err)
