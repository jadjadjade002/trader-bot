"""Grid sweep over AegisPredator_v26_lab inputs. Stage1: Jan-Apr 2026 $10k/1:200; results -> reports/ea_backtests/sw1_*.
Usage: python research/sweep_v26.py stage1"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EX5 = "research/v26/AegisPredator_v26_lab.ex5"
C = {"base": {}}
def add(n, **kw): C[n] = {k: str(v) for k, v in kw.items()}
for v in (1,2,3,5): add(f"mtd{v}", InpMaxTradesPerDay=v)
for a,b in ((7,12),(7,17),(12,20),(13,17),(8,11),(0,12),(12,24)): add(f"hr{a}_{b}", InpHourStart=a, InpHourEnd=b)
for v in (2,3,4): add(f"score{v}", InpMinScore=v)
for v in (15,20,25): add(f"adx{v}", InpAdxMin=v)
add("m15", InpRequireM15Trend="true"); add("h1", InpRequireH1Trend="true")
for v in (1,2): add(f"atrf{v}", InpAtrFilterMode=v)
add("spike3", InpSpikeAtrMul=3.0)
for v in (5,15,30): add(f"cool{v}", InpCooldownAfterCloseMin=v)
add("be1", InpBreakevenAtR=1.0); add("trail1", InpTrailAfterR=1.0, InpTrailAtrMul=1.0)
add("emax", InpEmaCrossExit="true")
for v in (10,15): add(f"ts{v}", InpTimeStopMin=v)
add("chand2", InpChandelierAtrMul=2.0)
for v in (3,10): add(f"slope{v}", InpSlopeBars=v)
for v in (0.2,0.4): add(f"trend{v}", InpTrendStrengthMul=v)
for v in (0.05,0.2): add(f"sprd{v}", InpSignalSpreadMul=v)
add("ema5_13", InpM1FastEMA=5, InpM1SlowEMA=13); add("ema12_26", InpM1FastEMA=12, InpM1SlowEMA=26)
add("m5_10_30", InpM5FastEMA=10, InpM5SlowEMA=30)
add("mtd3_m15", InpMaxTradesPerDay=3, InpRequireM15Trend="true")
add("mtd3_adx20", InpMaxTradesPerDay=3, InpAdxMin=20)
add("mtd3_hr7_17", InpMaxTradesPerDay=3, InpHourStart=7, InpHourEnd=17)
add("m15_adx20", InpRequireM15Trend="true", InpAdxMin=20)
add("m15_score3", InpRequireM15Trend="true", InpMinScore=3)
add("mtd2_cool15", InpMaxTradesPerDay=2, InpCooldownAfterCloseMin=15)

def run(prefix, start, end, dep, lev, names):
    for n in names:
        name = f"{prefix}_{n}"
        if (ROOT/"reports/ea_backtests"/name/"result.json").exists(): continue
        cmd = ["python","research/run_ea_backtest.py",name,EX5,"--start",start,"--end",end,
               "--deposit",str(dep),"--leverage",str(lev),"--model","4"]
        for k,v in C[n].items(): cmd += ["--set",f"{k}={v}"]
        subprocess.run(cmd, cwd=ROOT, capture_output=True)
        print("done", name, flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "stage1": run("sw1","2026.01.01","2026.05.01",10000,200,list(C))
    if sys.argv[1] == "stage2":
        top = ["mtd3_hr7_17","mtd1","mtd2_cool15","hr8_11","mtd2","mtd3","mtd5","hr13_17"]
        run("sw2","2026.01.01","2026.07.01",10000,200,top)
        run("sw2b70","2026.01.01","2026.07.01",70,500,top)
