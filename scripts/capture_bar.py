import subprocess
import sys

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

def ssh(cmd):
    res = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return res.stdout, res.stderr

# Take live screenshot and get account bar
remote_py = """
import os
os.system('DISPLAY=:0 import -window root /tmp/live_now.png')
os.system('DISPLAY=:0 xdotool getactivewindow windowfocus 2>/dev/null')
"""
ssh(f"python3 -c \"{remote_py}\"")

# Fetch screenshot to local
subprocess.run(["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{HOST}:/tmp/live_now.png", "tmp_live.png"])

# Let's crop the bottom bar (balance/equity) using python PIL
import PIL.Image as Image
img = Image.open("tmp_live.png")
w, h = img.size
print(f"Screen size: {w}x{h}")
# Crop bottom status bar
trade_bar = img.crop((0, h - 180, w, h))
trade_bar.save("tmp_trade_bar.png")
print("Saved tmp_trade_bar.png")
