#!/bin/bash
set -x

# Kill old instances cleanly
killall -9 terminal64.exe wineserver x11vnc websockify Xvfb 2>/dev/null || true
sleep 2

# Remove X lock files if any
rm -f /tmp/.X0-lock /tmp/.X11-unix/X0

# Start Xvfb display
Xvfb :0 -screen 0 1280x1024x24 &
sleep 2

# Start x11vnc
x11vnc -display :0 -forever -nopw -shared -rfbport 5900 -bg

# Start noVNC
websockify --web /usr/share/novnc 6080 localhost:5900 &

# Start MT5
export DISPLAY=:0
export WINEDLLOVERRIDES="mscoree,mshtml="
cd "/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5"
wine terminal64.exe /portable > /home/ubuntu/mt5_terminal.log 2>&1 &

sleep 5
echo "MT5 started with PID: $(pgrep terminal64.exe)"
