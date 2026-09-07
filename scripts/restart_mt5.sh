#!/bin/bash
# Graceful restart of MT5 terminal64.exe only (keeps Xvfb, x11vnc, websockify running)
killall -9 terminal64.exe 2>/dev/null || true
sleep 2

export DISPLAY=:0
export WINEDLLOVERRIDES="mscoree,mshtml="
cd "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5"
nohup wine terminal64.exe /portable > /home/ubuntu/mt5_terminal.log 2>&1 &

sleep 4
echo "MT5 Terminal restarted successfully. PID: $(pgrep terminal64.exe)"
