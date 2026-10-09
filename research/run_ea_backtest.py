"""Generic isolated-lab MT5 backtest runner for V25/V26 EAs.

Uses the isolated lab (.mt5-v23-tuning.local), never the desktop terminal.
One run at a time (lock file). Evidence goes to reports/ea_backtests/<name>/.

Usage:
  python research/run_ea_backtest.py NAME AegisPredator_v25.ex5 --start 2026.01.01 --end 2026.10.01 \
      --deposit 70 --leverage 500 [--model 4|1] [--set Key=Value ...]
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / ".mt5-v23-tuning.local"
OUT_BASE = ROOT / "reports" / "ea_backtests"
LOGIN = int(os.environ.get("MT5_LAB_LOGIN", "113802049"))  # research demo connection (see docs/CAPITAL70_RESEARCH_HANDOFF_20261008.md)


def lab_busy():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe' OR Name='metatester64.exe'\" | "
          "Where-Object { $_.ExecutablePath -like '" + str(LAB).replace("'", "''") + "*' } | "
          "Select-Object -ExpandProperty ProcessId")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]


def read_report(path):
    raw = path.read_bytes()
    text = raw.decode("utf-16", errors="ignore") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    def grab(label, cast=float):
        m = re.search(re.escape(label) + r"\s*:?\s*(-?[\d\s]+(?:\.\d+)?)", text)
        if not m:
            return None
        return cast(m.group(1).replace(" ", ""))
    res = dict(
        net=grab("Total Net Profit"), gross_profit=grab("Gross Profit"), gross_loss=grab("Gross Loss"),
        pf=grab("Profit Factor"), trades=grab("Total Trades", int),
        deposit=grab("Initial Deposit"),
    )
    m = re.search(r"Equity Drawdown Maximal\s*:?\s*-?[\d\s.]+\(?\s*([\d.]+)%", text)
    res["max_dd_pct"] = float(m.group(1)) if m else None
    m = re.search(r"Balance Drawdown Maximal\s*:?\s*-?[\d\s.]+\(?\s*([\d.]+)%", text)
    res["bal_dd_pct"] = float(m.group(1)) if m else None
    return res


def run(name, ex5, params, start, end, deposit, leverage, model=4, delay=200, timeout=3600):
    ex5 = Path(ex5)
    if not ex5.is_absolute():
        ex5 = ROOT / ex5
    out = OUT_BASE / name
    if out.exists():
        raise SystemExit(f"Run name exists, evidence preserved: {out}")
    # Holdout guard: months from 2026.07.01 are reserved for the orchestrator.
    if end > "2026.07.01" and os.environ.get("HOLDOUT_OK") != "1":
        raise SystemExit("Holdout window (>=2026.07.01) reserved. Use --end 2026.07.01 or earlier.")
    # Serialize the single lab across concurrent agents via an exclusive lock file.
    lock = LAB / "ea_backtest.lock"
    deadline = time.time() + 7200
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            break
        except FileExistsError:
            if time.time() - lock.stat().st_mtime > 3600:   # stale lock
                lock.unlink(missing_ok=True); continue
            if time.time() > deadline:
                raise SystemExit("timed out waiting for lab lock")
            time.sleep(5)
    try:
        return _run_locked(name, ex5, params, start, end, deposit, leverage, model, delay, timeout, out)
    finally:
        lock.unlink(missing_ok=True)


def _run_locked(name, ex5, params, start, end, deposit, leverage, model, delay, timeout, out):
    for _ in range(24):
        busy = lab_busy()
        if not busy:
            break
        time.sleep(5)
    else:
        raise SystemExit(f"Isolated lab busy (PIDs {busy})")
    if out.exists():
        raise SystemExit(f"Run name exists, evidence preserved: {out}")
    out.mkdir(parents=True)
    shutil.copy2(ex5, LAB / "MQL5/Experts" / ex5.name)
    set_path = LAB / "MQL5/Profiles/Tester" / f"{name}.set"
    set_path.write_text("\n".join(f"{k}={v}" for k, v in params.items()) + "\n", encoding="utf-16")
    ini = LAB / f"{name}.ini"
    ini.write_text(f"""[Common]
Login={LOGIN}
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert={ex5.name}
ExpertParameters={set_path.name}
Symbol=XAUUSD
Period=M1
Deposit={deposit}
Currency=USD
Leverage=1:{leverage}
Model={model}
ExecutionMode={delay}
Optimization=0
FromDate={start}
ToDate={end}
ForwardMode=0
Report=reports\\{name}.htm
ReplaceReport=0
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
""", encoding="utf-16")
    shutil.copy2(set_path, out)
    shutil.copy2(ini, out)
    logs = {p: p.stat().st_size for p in LAB.rglob("*.log") if p.parent.name.lower() == "logs"}
    t0 = time.time()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    proc = subprocess.Popen([str(LAB / "terminal64.exe"), "/portable", f"/config:{ini}"], cwd=LAB, startupinfo=startup)
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise SystemExit("tester timed out")
    report = LAB / "reports" / f"{name}.htm"
    if not report.exists():
        raise SystemExit(f"report missing (exit {code}); see lab logs")
    shutil.copy2(report, out)
    # newly appended journal text only
    jdir = out / "logs"
    jdir.mkdir()
    idx = 0
    for p in LAB.rglob("*.log"):
        if p.parent.name.lower() != "logs":
            continue
        data = p.read_bytes()
        off = logs.get(p, 0)
        if len(data) < off:
            off = 0
        if len(data) > off:
            (jdir / f"{idx}.txt").write_text(data[off:].decode("utf-16", errors="ignore"), encoding="utf-8")
            idx += 1
    res = read_report(report)
    res.update(name=name, ex5=ex5.name, start=start, end=end, deposit_req=deposit, leverage=leverage,
               model=model, delay_ms=delay, params=params, seconds=round(time.time() - t0),
               finished_utc=datetime.now(timezone.utc).isoformat())
    # V25 reject ledger from journal, if present
    for f in jdir.glob("*.txt"):
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "V25 DEINIT" in line or "V26 DEINIT" in line:
                res["ledger"] = line.split("DEINIT", 1)[1].strip()
    (out / "result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("ex5")
    ap.add_argument("--start", default="2026.01.01"); ap.add_argument("--end", default="2026.10.01")
    ap.add_argument("--deposit", type=float, default=70); ap.add_argument("--leverage", type=int, default=500)
    ap.add_argument("--model", type=int, default=4); ap.add_argument("--delay", type=int, default=200)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    params = dict(s.split("=", 1) for s in a.set)
    r = run(a.name, a.ex5, params, a.start, a.end, a.deposit, a.leverage, a.model, a.delay, a.timeout)
    print(json.dumps({k: r.get(k) for k in ("name", "net", "pf", "trades", "max_dd_pct", "seconds", "ledger")}, indent=2))
