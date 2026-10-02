import subprocess
import base64

SSH_KEY = r"key/ssh-key-2026-09-06.key"
HOST = "ubuntu@161.118.255.178"

script = """
from pathlib import Path
import re

root = Path('/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/logs')
log_files = sorted(root.glob('2026*.log'))

deals = []
for f in log_files:
    lines = open(f, encoding='utf-16-le', errors='ignore').readlines()
    for l in lines:
        if '5056497798' in l and 'deal #' in l:
            m = re.search(r'deal #(\\d+) (buy|sell) ([0-9.]+) ([A-Z]+) at ([0-9.]+)', l)
            if m:
                deals.append({
                    'time': l[:20].strip(),
                    'type': m.group(2),
                    'lot': float(m.group(3)),
                    'price': float(m.group(5)),
                    'raw': l.strip()
                })

print(f'Total deals: {len(deals)}')
pos = None
trades = []
for d in deals:
    if pos is None:
        pos = d
    else:
        if pos['type'] == 'buy' and d['type'] == 'sell':
            pnl = (d['price'] - pos['price']) * pos['lot'] * 100
            trades.append({'dir': 'BUY', 'entry': pos['price'], 'exit': d['price'], 'pnl': pnl})
            pos = None
        elif pos['type'] == 'sell' and d['type'] == 'buy':
            pnl = (pos['price'] - d['price']) * pos['lot'] * 100
            trades.append({'dir': 'SELL', 'entry': pos['price'], 'exit': d['price'], 'pnl': pnl})
            pos = None
        else:
            pos = d

print(f'Total closed roundtrips: {len(trades)}')
total_pnl = sum(t['pnl'] for t in trades)
wins = [t for t in trades if t['pnl'] > 0]
print(f'Wins: {len(wins)}, Losses: {len(trades) - len(wins)}, WinRate: {len(wins)/len(trades)*100:.1f}%')
print(f'Net PnL: ${total_pnl:.2f}')
print(f'Current open position: {pos is not None}')
if pos:
    print('Open:', pos)
print('--- All closed trades ---')
for i, t in enumerate(trades, 1):
    print(f\"{i:2d}. {t['dir']} in={t['entry']:.2f} out={t['exit']:.2f} pnl=${t['pnl']:+.2f}\")
"""

b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')
cmd = f"python3 -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'))\""

p = subprocess.run(
    ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace"
)
print(p.stdout)
if p.stderr:
    print("ERR:", p.stderr)
