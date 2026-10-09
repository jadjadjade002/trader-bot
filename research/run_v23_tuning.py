"""Run isolated native V23 comparisons and the predeclared bounded grid.

Generated sets, INIs and evidence are written only to the local research lab
and ignored reports directory. Never controls the VM or production terminal.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta

from research.analyze_v23_backtest import report_rows, parse_deals, bucket, csv_rows
from research.v23_tuning_matrix import MODE_NAMES, grid, metrics, rank

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / ".mt5-v23-tuning.local"
BASE = ROOT / "reports/v23_tuning_20261006"
FROM, TO = "2026.05.01", "2026.10.01"
DEV_TO, VAL_TO = "2026.08.01", "2026.09.01"
SOURCE_HASH = "C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0"
EX5_HASH = "E5B725EC83945B9E2126B72978E02A2EFCA28EC33AD649E575B4F5E2F4021AC0"
PARAMS = dict(InpEnableSessionGuard="false", InpEnableSpreadGuard="false",
              InpEnableMarginGuard="true", InpEnableHardSL="true", InpStartHour=11,
              InpEndHour=16, InpMaxSpreadPts=25, InpMaxHoldBars=60,
              InpDonchianPeriod=20, InpATRPeriod=14, InpStopLossATRMul=1.5,
              InpTakeProfitRRMul=2.0, InpMinSLPoints=150, InpLotSize=0.01,
              InpFadeBreakouts="true", InpMagicNumber=992300, InpTargetAccount=0,
              InpEnableCircuitBreaker="true", InpMaxConsecutiveLosses=4,
              InpCooldownMinutes=90, InpRequireCloseBackInside="false",
              InpExperimentMode=0, InpBETriggerR=0.0, InpBELockR=0.05)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def logs():
    return {p: p.stat().st_size for p in LAB.rglob("*.log") if p.parent.name.lower() == "logs"}


def freeze_runtime():
    baseline_source = ROOT / "AegisPredator_v23.mq5"
    if sha(baseline_source) != SOURCE_HASH or sha(ROOT / "AegisPredator_v23.ex5") != EX5_HASH:
        raise ValueError("Deployed baseline artifacts changed")
    runtime = {k: sha(LAB / k) for k in ("terminal64.exe", "metatester64.exe")}
    frozen = BASE / "runtime_freeze.json"
    if frozen.exists() and json.loads(frozen.read_text()) != runtime:
        raise ValueError("Runtime drift: new batch and parity required")
    if not frozen.exists():
        save(frozen, runtime)
    return runtime


def money(text):
    return float(str(text).replace(" ", "").replace(",", ""))


def dd_percent(native):
    value = native.get("Equity Drawdown Relative", "")
    match = re.match(r"\s*([\d.,]+)%", value)
    if not match:
        raise ValueError("Native relative equity drawdown missing")
    return money(match.group(1))


def check_coverage(first_ms, last_ms, start, end):
    first = datetime.fromtimestamp(float(first_ms)/1000, timezone.utc).replace(tzinfo=None)
    last = datetime.fromtimestamp(float(last_ms)/1000, timezone.utc).replace(tzinfo=None)
    left = datetime.strptime(start, "%Y.%m.%d")
    right = datetime.strptime(end, "%Y.%m.%d")
    if not left <= first < left+timedelta(days=3) or not right-timedelta(days=3) <= last < right:
        raise ValueError("Native five-month/window boundary coverage failed")


def settings(name, mode, overrides, optimize, original):
    p = dict(PARAMS, InpExperimentMode=mode,
             InpFadeBreakouts="true" if mode == 0 else "false", InpRunTag=name)
    p.update(overrides)
    if original:
        p = {k: v for k, v in p.items() if k in PARAMS and k not in
             ("InpRequireCloseBackInside", "InpExperimentMode", "InpBETriggerR", "InpBELockR")}
    lines = []
    for k, v in p.items():
        if optimize and k == "InpStopLossATRMul":
            line = f"{k}={v}||1.0||0.5||2.0||Y"
        elif optimize and k == "InpTakeProfitRRMul":
            # Two separate ranges are not expressible in an MT5 arithmetic set.
            # TP uses index 0..3 mapped to the frozen {1,1.5,2,3} values.
            line = f"{k}={v}"
        elif optimize and k == "InpBETriggerR":
            line = f"{k}={v}"
        else:
            line = f"{k}={v}"
        lines.append(line)
    if optimize:
        lines += ["InpTPGridIndex=0||0||1||3||Y", "InpBEGridIndex=0||0||1||2||Y",
                  "InpUseGridIndices=true"]
    return "\n".join(lines) + "\n"


def execute(name, mode=0, overrides=None, *, start=FROM, end=TO,
            deposit=10000, optimize=False, original=False, timeout=2400, source_override=None):
    overrides = overrides or {}
    runtime = freeze_runtime()
    output = BASE / "runs" / name
    expected_set = settings(name, mode, overrides, optimize, original)
    if source_override is not None and (source_override != "AegisPredator_v24.mq5" or not original or optimize):
        raise ValueError("Only standalone V24 native parity may override the expert")
    source = ROOT / (source_override or ("AegisPredator_v23.mq5" if original else "research/V23_TuningBenchmark.mq5"))
    binary = source.with_suffix(".ex5")
    signature = dict(mode=mode, overrides=overrides, start=start, end=end, deposit=deposit,
                     optimize=optimize, original=original, source_sha=sha(source), binary_sha=sha(binary),
                     set_sha=hashlib.sha256(expected_set.encode("utf-16")).hexdigest(), runtime=runtime)
    if (output / "accepted.json").exists():
        accepted = json.loads((output / "accepted.json").read_text())
        if accepted["signature"] != signature:
            raise ValueError("Cached run settings differ")
        return accepted["result"]
    if output.exists():
        retries=re.search(r"_retry(\d+)$",name)
        count=int(retries.group(1)) if retries else 0
        if count>=2:
            raise ValueError(f"Native run still incomplete after bounded retries: {name}")
        original_name=name[:retries.start()] if retries else name
        return execute(f"{original_name}_retry{count+1}",mode,overrides,start=start,end=end,
                       deposit=deposit,optimize=optimize,original=original,timeout=timeout,source_override=source_override)
    output.mkdir(parents=True)
    shutil.copy2(binary, LAB / "MQL5/Experts" / binary.name)
    set_path = LAB / "MQL5/Profiles/Tester" / f"{name}.set"
    set_path.write_text(expected_set, encoding="utf-16")
    ext = "xml" if optimize else "htm"
    report = LAB / "reports" / f"{name}.{ext}"
    if report.exists():
        raise ValueError("Existing native report cannot be overwritten")
    ini = LAB / f"{name}.ini"
    ini.write_text(f"""[Common]
Login=5055578643
Server=MetaQuotes-Demo
KeepPrivate=1
NewsEnable=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert={binary.name}
ExpertParameters={set_path.name}
Symbol=XAUUSD
Period=M1
Deposit={deposit}
Currency=USD
Leverage=1:200
Model=4
ExecutionMode=200
Optimization={1 if optimize else 0}
OptimizationCriterion=6
FromDate={start}
ToDate={end}
ForwardMode=0
Report=reports\\{name}.{ext}
ReplaceReport=0
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
""", encoding="utf-16")
    shutil.copy2(set_path, output)
    shutil.copy2(ini, output)
    before = logs()
    save(output / "started.json", dict(signature=signature, started_utc=datetime.now(timezone.utc).isoformat()))
    startup = subprocess.STARTUPINFO() if os.name == "nt" else None
    if startup:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    print(f"START {name}", flush=True)
    process = subprocess.Popen([str(LAB / "terminal64.exe"), "/portable", f"/config:{ini}"],
                               cwd=LAB, startupinfo=startup)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=30)
        raise RuntimeError(f"Isolated native run timed out: {name}")
    texts = []
    for index, (p, length) in enumerate(logs().items()):
        previous = before.get(p, 0)
        raw = p.read_bytes()
        if len(raw) < previous:
            previous = 0
        if len(raw) > previous:
            text = raw[previous:].decode("utf-16-le", errors="replace")
            (output / f"journal_{index}.txt").write_text(text, encoding="utf-8")
            texts.append(text)
    journal = "\n".join(texts)
    if runtime != {k: sha(LAB / k) for k in runtime}:
        raise ValueError("Runtime changed during run")
    if code or not report.exists():
        raise RuntimeError(f"No successful native report: exit={code}, name={name}")
    shutil.copy2(report, output)
    cache_warnings=[line for line in journal.splitlines() if re.search(r"History\s+'XAUUSD' file opening or reading error \[32\]",line)]
    # A terminal-side sharing violation can be repaired before native testing.
    # It is disclosed and accepted only after all native quality/coverage checks.
    checked_journal="\n".join(line for line in journal.splitlines() if line not in cache_warnings)
    fatal = re.search(r"tester agent authorization error|tester not started|no real ticks|generated ticks|history[^\n]*error", checked_journal, re.I)
    if fatal:
        raise ValueError(f"Native run invalid: {fatal.group(0)}")
    exports = list((LAB / "Tester").rglob(f"{name}_*.csv"))
    if optimize:
        exports += list((LAB / "MQL5/Files").glob(f"{name}_optimization.csv"))
    for p in exports:
        destination = output / p.name
        if destination.exists():
            raise ValueError("Duplicate native agent exports")
        shutil.copy2(p, destination)
    if optimize:
        rows = csv_rows(output / f"{name}_optimization.csv")
        expected = {(r["sl_atr"], r["tp_r"], r["be_r"]) for r in grid(mode)}
        observed = {(float(r["sl_atr"]), float(r["tp_r"]), float(r["be_r"])) for r in rows}
        if len(rows) != 36 or observed != expected:
            raise ValueError("Optimization grid incomplete or duplicated")
        for row in rows:
            metrics(row)
            if float(row["observed_ticks"]) <= 0:
                raise ValueError("Empty optimization pass")
            check_coverage(row["first_tick_msc"],row["last_tick_msc"],start,end)
        result = dict(rows=rows, eligible=rank(rows), in_sample_only=True)
    else:
        native, _ = report_rows(output / report.name)
        if native.get("History Quality") != "100% real ticks" or float(native.get("Ticks", 0)) <= 0 or float(native.get("Bars", 0)) <= 0:
            raise ValueError("Empty or non-real-tick native report")
        if "Test passed in" not in journal:
            raise ValueError("Native completion evidence missing")
        if original:
            result = dict(native=native)
        else:
            trades, cash = parse_deals(csv_rows(output / f"{name}_deals.csv"))
            result = bucket(trades)
            if abs(result["net"] - money(native["Total Net Profit"])) > 0.03:
                raise ValueError("Native deal reconciliation failed")
            if result["trades"] != int(native["Total Trades"].replace(" ", "")):
                raise ValueError("Native trade count mismatch")
            result.update(native=native, monthly={m: bucket([t for t in trades if t["close"].startswith(m)])
                          for m in sorted({t["close"][:7] for t in trades})},
                          charges={k: sum(t[k] for t in trades) for k in ("commission", "swap", "fee")},
                          exit_reasons={str(reason): sum(t["exit_reason"] == reason for t in trades)
                                        for reason in sorted({t["exit_reason"] for t in trades})},
                          stopout=any(t["exit_reason"] == 6 for t in trades), cash_events=len(cash),
                          sampled_paths=csv_rows(output / f"{name}_paths.csv"),
                          be=csv_rows(output / f"{name}_be.csv"))
            spec_rows=csv_rows(output / f"{name}_spec.csv")
            specs={r["key"]:r["value"] for r in spec_rows}
            if specs.get("history_export_ok") not in ("1","true"):
                raise ValueError("Native history export failed")
            if abs(money(specs["final_balance"])-deposit-result["net"])>0.03:
                raise ValueError("Balance reconciliation failed")
            if not result["stopout"]:
                check_coverage(specs["first_tick"],specs["last_tick"],start,end)
            result["native_equity_dd_pct"]=dd_percent(native)
    if cache_warnings and "preliminary downloading of M1 history completed" not in journal:
        raise ValueError("Unrecovered terminal history sharing violation")
    result["terminal_cache_read_warnings"]=cache_warnings
    result["evidence_run"]=name
    save(output / "accepted.json", dict(signature=signature, result=result))
    print(f"ACCEPT {name}", flush=True)
    return result


def run_all(prefix):
    progress = dict(comparison={}, full_grid={}, development={}, validation={}, confirmation={}, capital={})
    for mode, label in MODE_NAMES.items():
        progress["comparison"][label] = execute(f"{prefix}_compare_{label}", mode,
                    {"InpBETriggerR": 1.2 if mode == 2 else 0})
        save(BASE / f"{prefix}_progress.json", progress)
    original = execute(f"{prefix}_original_parity", original=True)
    for key in ("Total Trades", "Total Net Profit", "Gross Profit", "Gross Loss"):
        if original["native"].get(key) != progress["comparison"]["vm_fade"]["native"].get(key):
            raise ValueError(f"Baseline core parity failed: {key}")
    for mode, label in MODE_NAMES.items():
        progress["full_grid"][label] = execute(f"{prefix}_grid_full_{label}", mode, optimize=True)
        progress["development"][label] = execute(f"{prefix}_grid_dev_{label}", mode, end=DEV_TO, optimize=True)
        candidates = progress["development"][label]["eligible"][:3]
        validated = []
        for index, row in enumerate(candidates):
            params = {"InpStopLossATRMul": float(row["sl_atr"]), "InpTakeProfitRRMul": float(row["tp_r"]),
                      "InpBETriggerR": float(row["be_r"])}
            result = execute(f"{prefix}_val_{label}_{index}", mode, params, start=DEV_TO, end=VAL_TO)
            validated.append(dict(parameters=params, result=result, index=index))
        progress["validation"][label] = validated
        passed = [x for x in validated if x["result"]["net"] > 0 and x["result"]["trades"] >= 30
                  and x["result"]["net_profit_factor"] is not None and x["result"]["net_profit_factor"] >= 1.2]
        if passed:
            selected = min(passed, key=lambda x: (x["result"]["native_equity_dd_pct"], -x["result"]["net"], x["index"]))
            progress["confirmation"][label] = execute(f"{prefix}_confirm_{label}", mode, selected["parameters"], start=VAL_TO)
            progress["capital"][label] = execute(f"{prefix}_capital70_{label}", mode, selected["parameters"], deposit=70)
        save(BASE / f"{prefix}_progress.json", progress)
    save(BASE / f"{prefix}_complete.json", progress)
    print("BATCH COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("smoke", "compare", "all"))
    parser.add_argument("--prefix", default="batch1")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_]+", args.prefix):
        parser.error("Invalid evidence prefix")
    BASE.mkdir(parents=True, exist_ok=True)
    if args.action == "smoke":
        execute(args.prefix + "_smoke", start="2026.09.28", end="2026.09.29", timeout=180)
    elif args.action == "compare":
        for mode, name in MODE_NAMES.items():
            execute(f"{args.prefix}_{name}", mode, {"InpBETriggerR": 1.2 if mode == 2 else 0})
    else:
        run_all(args.prefix)
