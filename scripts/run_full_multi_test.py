import subprocess
import time
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(r"D:\project\trader-bot")
LAB = ROOT / ".mt5-v16_1.local"
TERMINAL_EXE = LAB / "terminal64.exe"
REPORTS_DIR = LAB / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Define the suite of tests to run (2026.05.03 to 2026.08.14)
FROM_DATE = "2026.05.03"
TO_DATE = "2026.08.14"
DEPOSIT = 100.0

TEST_CONFIGS = [
    {"expert": "QuantumTitan_v22_Swing.ex5", "tf": "M15", "name": "v22_swing_m15_long", "model": 1},
    {"expert": "QuantumTitan_v22_Swing.ex5", "tf": "M30", "name": "v22_swing_m30_long", "model": 1},
    {"expert": "QuantumTitan_v22_Swing.ex5", "tf": "H1",  "name": "v22_swing_h1_long",  "model": 1},
    {"expert": "QuantumTitan_v16_1_M1.ex5",   "tf": "M1",  "name": "v16_1_m1_long",      "model": 1},
    {"expert": "QuantumTitan_v16_Velocity.ex5", "tf": "M1", "name": "v16_velocity_long", "model": 1},
]

def make_ini(expert, tf, report_rel, model):
    return f"""[Common]
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert={expert}
Symbol=XAUUSD
Period={tf}
Deposit={DEPOSIT}
Currency=USD
Leverage=1:500
Model={model}
ExecutionMode=0
Optimization=0
FromDate={FROM_DATE}
ToDate={TO_DATE}
ForwardMode=0
Report={report_rel}
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"""

def parse_htm(report_path):
    p = Path(report_path)
    if not p.exists():
        return None
    try:
        soup = BeautifulSoup(p.read_text(encoding="utf-16", errors="replace"), "html.parser")
    except Exception:
        soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "html.parser")
    
    data = {}
    for tr in soup.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        for i in range(0, len(tds) - 1, 2):
            k = tds[i].replace(":", "").strip()
            v = tds[i+1].strip()
            data[k] = v
    return data

results = []

for cfg in TEST_CONFIGS:
    name = cfg["name"]
    expert = cfg["expert"]
    tf = cfg["tf"]
    model = cfg["model"]
    report_rel = f"reports\\{name}.htm"
    report_abs = LAB / report_rel
    ini_path = LAB / f"tester_run_{name}.ini"
    
    if report_abs.exists():
        report_abs.unlink()
        
    ini_content = make_ini(expert, tf, report_rel, model)
    ini_path.write_text(ini_content, encoding="utf-16")
    
    print(f"\n=======================================================")
    print(f"Running: {name} ({expert} on {tf}) from {FROM_DATE} to {TO_DATE}")
    print(f"=======================================================")
    
    # Launch terminal in portable skipupdate mode
    cmd = [str(TERMINAL_EXE), "/portable", "/skipupdate", f"/config:{ini_path}"]
    proc = subprocess.Popen(cmd)
    
    start_t = time.time()
    while proc.poll() is None:
        time.sleep(2)
        if time.time() - start_t > 300: # 5 min timeout per run
            proc.kill()
            print("TIMEOUT REACHED!")
            break
            
    time.sleep(2)
    metrics = parse_htm(report_abs)
    if metrics:
        print("Success! Metrics captured.")
        results.append({
            "name": name,
            "expert": expert,
            "tf": tf,
            "profit": metrics.get("Total Net Profit", "N/A"),
            "gross_profit": metrics.get("Gross Profit", "N/A"),
            "gross_loss": metrics.get("Gross Loss", "N/A"),
            "trades": metrics.get("Total Trades", "N/A"),
            "pf": metrics.get("Profit Factor", "N/A"),
            "dd": metrics.get("Balance Drawdown Maximal", metrics.get("Equity Drawdown Maximal", "N/A")),
        })
    else:
        print("Report not generated or empty. Checking logs...")
        results.append({
            "name": name,
            "expert": expert,
            "tf": tf,
            "profit": "ERROR",
            "trades": "0",
            "pf": "N/A",
            "dd": "N/A"
        })

print("\n\n==================== FINAL RESULTS SUMMARY ====================")
for r in results:
    print(r)
