#!/bin/bash
echo 'Stopping wineserver...'
wineserver -k
sleep 2

export DISPLAY=:0
export WINEDLLOVERRIDES='mscoree,mshtml='
cd '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5'
nohup wine terminal64.exe /portable > /home/ubuntu/mt5_terminal.log 2>&1 &
sleep 5
echo 'MT5 Terminal restarted successfully!'
