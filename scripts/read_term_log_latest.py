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

remote_base = "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo"
print(ssh(f"cat '{remote_base}/logs/20261002.log' | tail -n 25"))
