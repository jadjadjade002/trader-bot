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
path = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/Profiles/Charts/Default/chart01.chr'
content = open(path, encoding='utf-16-le', errors='ignore').read()
for line in content.splitlines():
    if 'Inp' in line:
        print(line)
"""
import base64
b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')
cmd = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""
print("Chart in Profiles/Charts/Default:\n", ssh(cmd))

script2 = """
path = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/MQL5/Profiles/Charts/Default/chart01.chr'
if open(path, 'rb'):
    content = open(path, encoding='utf-16-le', errors='ignore').read()
    for line in content.splitlines():
        if 'Inp' in line:
            print(line)
"""
b64_2 = base64.b64encode(script2.encode('utf-8')).decode('ascii')
cmd2 = f"python3 -c \"import base64; exec(base64.b64decode('{b64_2}').decode('utf-8'))\""
print("Chart in MQL5/Profiles/Charts/Default:\n", ssh(cmd2))
