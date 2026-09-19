"""Read-only report for v16 Velocity expert/terminal logs.

Price PnL is deliberately an estimate: contract_size * volume * signed price
change.  It is not account-currency net PnL (fees, swap and spread unavailable).
"""
from __future__ import annotations
import argparse, json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import Counter, deque

OPEN = re.compile(r"Velocity\] (?P<side>BUY|SELL) SCALP OPENED @ (?P<entry>\d+(?:\.\d+)?) \| SL: (?P<sl>\d+(?:\.\d+)?) .*? TP: (?P<tp>\d+(?:\.\d+)?)(?: \| Lot: (?P<volume>\d+(?:\.\d+)?))?")
BE = re.compile(r"Velocity\] (?P<side>BUY|SELL) BREAKEVEN LOCKED:.*?SL set to (?P<be>\d+(?:\.\d+)?)")
CLOSE = re.compile(r"Velocity Safety\] Deal #(?P<deal>\d+) closed")
DEAL = re.compile(r"'(?P<account>\d+)': deal #(?P<deal>\d+) (?P<side>buy|sell) (?P<volume>\d+(?:\.\d+)?) (?P<symbol>\S+) at (?P<price>\d+(?:\.\d+)?) done \(based on order #(?P<order>\d+)\)")
REC = re.compile(r"^\S+\s+\d+\s+(?P<time>\d\d:\d\d:\d\d\.\d+)\s+(?P<msg>.*)$")

@dataclass
class Event:
    kind: str; date: str; time: str; line: int; side: str|None=None
    entry: float|None=None; sl: float|None=None; tp: float|None=None
    volume: float|None=None; be: float|None=None; deal: str|None=None

@dataclass
class Deal:
    deal: str; side: str; volume: float; symbol: str; price: float; order: str
    date: str; time: str; line: int

def _text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-8", "cp1252"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("utf-8", "replace")

def _records(path: Path):
    date = path.stem
    current = None
    for n, line in enumerate(_text(path).splitlines(), 1):
        m = REC.match(line)
        if m:
            if current is not None: yield current
            current = (date, m.group("time"), n, m.group("msg"))
        elif current is not None:
            # Some MT5 builds wrap long messages at a physical newline.
            current = (current[0], current[1], current[2], current[3] + " " + line.strip())
    if current is not None: yield current

def parse_expert_logs(paths):
    out=[]
    for p in sorted(map(Path, paths)):
        for date,t,n,msg in _records(p):
            if "QuantumTitan_v16_Velocity" not in msg and "[M1 Velocity]" not in msg: continue
            m=OPEN.search(msg)
            if m: out.append(Event("open",date,t,n,m.group("side").lower(),float(m.group("entry")),float(m.group("sl")),float(m.group("tp")),float(m.group("volume") or .01)))
            m=BE.search(msg)
            if m: out.append(Event("be",date,t,n,m.group("side").lower(),be=float(m.group("be"))))
            m=CLOSE.search(msg)
            if m: out.append(Event("close",date,t,n,deal=m.group("deal")))
    return sorted(out, key=lambda e:(e.date,e.time,e.line))

def parse_terminal_logs(paths, account="112334471"):
    out=[]
    for p in sorted(map(Path, paths)):
        for date,t,n,msg in _records(p):
            m=DEAL.search(msg)
            if m and m.group("account")==str(account):
                out.append(Deal(m.group("deal"),m.group("side"),float(m.group("volume")),m.group("symbol"),float(m.group("price")),m.group("order"),date,t,n))
    return sorted(out,key=lambda d:(d.date,d.time,d.line))

def _classify(pos, exit_price, tol):
    if abs(exit_price-pos["tp"])<=tol: return "TP"
    if abs(exit_price-pos["sl"])<=tol and not pos.get("be_locked"): return "INITIAL_SL"
    if pos.get("be") is not None and abs(exit_price-pos["be"])<=tol: return "BE_LOCK"
    signed=(exit_price-pos["entry"])*(1 if pos["side"]=="buy" else -1)
    if abs(signed)<=tol: return "FLAT"
    return "OTHER_WIN" if signed>0 else "OTHER_LOSS"

def build_report(expert_paths, terminal_paths, account="112334471", contract_size=100.0, tolerance=0.05):
    events=parse_expert_logs(expert_paths); deals=parse_terminal_logs(terminal_paths,account)
    entries=[d for d in deals if d.symbol=="XAUUSD"]
    pending=deque(); used=set(); by_id={d.deal:d for d in deals}; rows=[]; unmatched={"opens":0,"breakeven":0,"closes":0,"deals":0,"ambiguous":0,"restarts":0,"rejected_entry_mismatch":0,"superseded_open_without_close":0}
    # A terminal restart invalidates any in-memory sequential pairing.
    restarts=sum(1 for p in map(Path,terminal_paths) for _,_,_,m in _records(p) if "MetaTrader 5 x64" in m and "started" in m)
    unmatched["restarts"]=max(0,restarts-1)
    for ev in events:
        if ev.kind=="open":
            # Expert and terminal clocks can differ by hours.  Entry price is
            # the stable cross-log key; retain sequential order among ties.
            def sec(x):
                h,m,s=x.split(':'); return int(h)*3600+int(m)*60+float(s)
            candidates=[d for d in entries if d.deal not in used and d.side==ev.side and abs(d.volume-(ev.volume or .01))<1e-9 and d.date==ev.date and abs(sec(d.time)-sec(ev.time))<=5 and abs(d.price-(ev.entry or d.price))<=0.10]
            if not candidates:
                nearby=[d for d in entries if d.deal not in used and d.side==ev.side and abs(d.volume-(ev.volume or .01))<1e-9 and d.date==ev.date and abs(sec(d.time)-sec(ev.time))<=5]
                if nearby: unmatched["rejected_entry_mismatch"]+=1
                unmatched["opens"]+=1; continue
            d=min(candidates,key=lambda x:(x.date,x.time,x.line)); used.add(d.deal)
            if pending:
                pending.clear(); unmatched["superseded_open_without_close"]+=1
            pending.append({"date":ev.date,"time":ev.time,"entry_terminal_time":f"{d.date} {d.time}","side":ev.side,"entry":d.price,"volume":d.volume,"sl":ev.sl,"tp":ev.tp,"entry_deal":d.deal,"be":None,"be_locked":False})
        elif ev.kind=="be":
            if pending and pending[-1]["side"]==ev.side: pending[-1]["be"]=ev.be; pending[-1]["be_locked"]=True
            else: unmatched["breakeven"]+=1
        else:
            d=by_id.get(ev.deal)
            if d is None: unmatched["closes"]+=1; continue
            if not pending: unmatched["closes"]+=1; continue
            pos=pending.popleft(); pos["exit_deal"]=d.deal; pos["exit_date"]=d.date; pos["exit_time"]=d.time; pos["exit_price"]=d.price; pos["class"]= _classify(pos,d.price,tolerance); pos["price_pnl_estimate"]=contract_size*pos["volume"]*((d.price-pos["entry"])*(1 if pos["side"]=="buy" else -1)); rows.append(pos)
    unmatched["deals"]=len(entries)-len(used)
    counts=Counter(r["class"] for r in rows); contributions={k:sum(x["price_pnl_estimate"] for x in rows if x["class"]==k) for k in counts}
    wins=sum(x["price_pnl_estimate"]>tolerance for x in rows); losses=sum(x["price_pnl_estimate"]<-tolerance for x in rows)
    return {"account":str(account),"contract_size":contract_size,"price_tolerance":tolerance,"pnl_definition":"estimate = contract_size * volume * signed price difference; not net PnL","metrics":{"matched":len(rows),"classification_counts":dict(counts),"class_contribution_estimate":contributions,"estimated_price_pnl":sum(r["price_pnl_estimate"] for r in rows),"positive_count":wins,"negative_count":losses,"positive_win_rate":wins/len(rows) if rows else None,"unmatched":unmatched},"positions":rows}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--experts",required=True); ap.add_argument("--terminal",required=True); ap.add_argument("--account",default="112334471"); ap.add_argument("--contract-size",type=float,default=100); ap.add_argument("--tolerance",type=float,default=.05); ap.add_argument("--text",action="store_true")
    a=ap.parse_args(); r=build_report(Path(a.experts).glob("*.log"),Path(a.terminal).glob("*.log"),a.account,a.contract_size,a.tolerance)
    print(json.dumps(r,indent=2) if not a.text else json.dumps(r["metrics"],indent=2))
if __name__=="__main__": main()
