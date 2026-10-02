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

# Capture bottom status bar
import os
ssh("DISPLAY=:0 import -window root /tmp/live_now2.png")
subprocess.run(["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{HOST}:/tmp/live_now2.png", "tmp_live2.png"])

import PIL.Image as Image
img = Image.open("tmp_live2.png")
w, h = img.size
# Crop trade tab
trade_tab = img.crop((0, h - 220, w, h))
trade_tab.save("tmp_trade_tab2.png")
print("Saved tmp_trade_tab2.png")
