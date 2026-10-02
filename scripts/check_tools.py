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

print(ssh("which scrot import xwd"))
