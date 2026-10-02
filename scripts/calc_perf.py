import subprocess
import re

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

remote_py = """
from pathlib import Path
import re

root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/logs')
log_files = sorted(root.glob('2026*.log'))

# Track balance and deals
deals = []
for f in log_files:
    lines = open(f, encoding='utf-16-le', errors='ignore').readlines()
    for l in lines:
        if '5056497798' in l:
            # Check deal line
            # deal #... buy/sell 0.01 XAUUSD at 4159.32 done
            m = re.search(r'deal #(\\d+) (buy|sell) ([0-9.]+) ([A-Z]+) at ([0-9.]+)', l)
            if m:
                deals.append({
                    'time': l[:20].strip(),
                    'deal_id': m.group(1),
                    'type': m.group(2),
                    'lot': float(m.group(3)),
                    'symbol': m.group(4),
                    'price': float(m.group(5)),
                    'raw': l.strip()
                })

print(f'Total deals: {len(deals)}')
# Pair in and out deals
# In MT5: 
# Buy to enter -> Sell to exit
# Sell to enter -> Buy to exit
pos = None
trades = []
for d in deals:
    if pos is None:
        pos = d
    else:
        # Exit
        if pos['type'] == 'buy' and d['type'] == 'sell':
            profit = (d['price'] - pos['price']) * pos['lot'] * 100 # standard gold 100oz
            trades.append({'in': pos, 'out': d, 'profit': profit, 'dir': 'BUY'})
            pos = None
        elif pos['type'] == 'sell' and d['type'] == 'buy':
            profit = (pos['price'] - d['price']) * pos['lot'] * 100
            trades.append({'in': pos, 'out': d, 'profit': profit, 'dir': 'SELL'})
            pos = None
        else:
            print('Odd sequence:', pos, d)
            pos = d

print(f'Closed roundtrip trades: {len(trades)}')
total_prof = sum(t['profit'] for t in trades)
wins = [t for t in trades if t['profit'] > 0]
losses = [t for t in trades if t['profit'] <= 0]
print(f'Win rate: {len(wins)}/{len(trades)} ({len(wins)/len(trades)*100:.1f}%)')
print(f'Total profit: ${total_prof:.2f}')
print(f'Open position currently: {pos is not None}')
if pos:
    print('Open pos:', pos)

print('\\nLast 10 closed trades:')
for t in trades[-10:]:
    print(f\"{t['dir']} in {t['in']['price']} -> out {t['out']['price']} = ${t['profit']:.2f}\")
"""

res = ssh(f"python3 -c \"{remote_py}\"")
print(res)
