"""Bounded native candidate search against frozen V24. No VM or deployment.

Internal v25 project label does not name any bot a V25 release.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager

from research.analyze_v23_backtest import csv_rows, parse_deals, report_rows, bucket, finite
from research.run_v23_tuning import sha, save, money, dd_percent, PARAMS as OLD_PARAMS
from research.v23_tuning_matrix import metrics
from research.candidate_release_evidence import evaluate as release_evidence
from research.native_end_accounting import parse_verified_native_deals

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / ".mt5-v23-tuning.local"
BASE = ROOT / "reports/v25_research_20261007"
SOURCE_HASH = "5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E"
BINARY_HASH = "5A11086D05F7AA5C4E0B3D806B58BFF446BE08CC0EC8A48944A7681D42A539AF"
START, DEV_END, VAL_END, END = "2025.12.01", "2026.06.01", "2026.08.01", "2026.10.01"
TP_VALUES = (1.0, 1.5, 2.0, 3.0)
SL_VALUES = (1.0, 1.5, 2.0)
MODE_NAMES = {0: "baseline", 1: "continuation", 2: "reclaim", 3: "breakout"}
# Finalize only after independent review of the R12 deterministic native fixtures.
R12_NATIVE_FIXTURE_COUNT = None
PARAMS = {k: v for k, v in OLD_PARAMS.items() if k not in
          ("InpRequireCloseBackInside", "InpExperimentMode", "InpBETriggerR", "InpBELockR")}
PARAMS["InpFadeBreakouts"] = "false"


def months(start, end):
    a, b = (datetime.strptime(x, "%Y.%m.%d") for x in (start, end))
    if a.day != 1 or b.day != 1 or b <= a:
        raise ValueError("Require complete calendar months")
    result = []
    while a < b:
        result.append(a.year * 100 + a.month)
        a = datetime(a.year + (a.month == 12), a.month % 12 + 1, 1)
    return result


def cache_manifest(start=START, end=END):
    folder = LAB / "bases/MetaQuotes-Demo/ticks/XAUUSD"
    result = []
    for month in months(start, end):
        p = folder / f"{month}.tkc"
        if not p.exists() or p.stat().st_size < 1024:
            raise ValueError(f"Monthly real tick cache missing: {month}")
        result.append(dict(month=month, bytes=p.stat().st_size, sha256=sha(p)))
    return result


def freeze(evidence_base=None):
    if sha(ROOT / "AegisPredator_v24.mq5") != SOURCE_HASH or sha(ROOT / "AegisPredator_v24.ex5") != BINARY_HASH:
        raise ValueError("Production V24 baseline changed")
    runtime = {name: sha(LAB / name) for name in ("terminal64.exe", "metatester64.exe")}
    previous = (BASE if evidence_base is None else Path(evidence_base)) / "runtime_freeze.json"
    if previous.exists() and json.loads(previous.read_text()) != runtime:
        raise ValueError("Runtime drift, new batch required")
    save(previous, runtime)
    return runtime


def settings(name, mode, overrides, optimize=False, production=False, r2=False, r5=False, r6=False, r7=False, r8=False, control_r1=False, r9_hold=False, r10=False, r11=False, r12=False):
    if any(type(profile) is not bool for profile in (r10, r11, r12)):
        raise ValueError("R10/R11/R12 profile must be boolean")
    if type(r9_hold) is not bool or (r9_hold and not control_r1):
        raise ValueError("R9 hold profile requires the reviewed R1 reporting control")
    p = dict(PARAMS)
    if not production:
        p.update(InpRunTag=name, InpExperimentMode=mode, InpEntryStrength=0)
        if not r2:
            p.update(InpUseGridIndices="false", InpTPGridIndex=2)
    if r2 and (production or optimize):
        raise ValueError("R2 adapter supports isolated standalone tests only")
    if control_r1:
        if not r2 or r5 or r6 or r7 or r8 or production or optimize or mode != 1:
            raise ValueError("R8 reporting control supports the exact R1 continuation only")
        allowed = {"InpEntryStrength", "InpStopLossATRMul", "InpTakeProfitRRMul"}
        if r9_hold:
            allowed.add("InpMaxHoldBars")
        if set(overrides) - allowed:
            raise ValueError("R8 reporting control has a frozen three-input contract")
        p.update(InpUseGridIndices="false", InpTPGridIndex=2)
    if r5:
        if not r2 or production or optimize or mode not in (0, 5):
            raise ValueError("R5 adapter supports tester-only parity/exhaustion standalone tests")
        p["InpRequireM1Alignment"] = "false"
    if r6:
        if not r2 or r5 or production or optimize or mode not in (0, 6, 7):
            raise ValueError("R6 adapter supports tester-only parity and four standalone cells")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul", "InpTakeProfitRRMul"}:
            raise ValueError("R6 overrides must stay within the frozen three-input contract")
        p["InpRequireM1Alignment"] = "false"
    if r7:
        if not r2 or r5 or r6 or production or optimize or mode not in (0, 5):
            raise ValueError("R7 adapter supports tester-only parity and low-target cells")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul", "InpTakeProfitRRMul"}:
            raise ValueError("R7 overrides must stay within the frozen three-input contract")
    if r8:
        if not r2 or r5 or r6 or r7 or production or optimize or mode not in (0, 1):
            raise ValueError("R8 adapter supports tester-only parity and continuation-quality cells")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul", "InpTakeProfitRRMul",
                             "InpRequireEfficiency", "InpRequireNearMean"}:
            raise ValueError("R8 overrides must stay within the frozen five-input contract")
        p.update(InpUseGridIndices="false", InpTPGridIndex=2,
                 InpRequireEfficiency="false", InpRequireNearMean="false")
    if r10:
        if (not r2 or production or optimize or mode not in (0, 1)
                or any((r5, r6, r7, r8, control_r1, r9_hold, r11, r12))):
            raise ValueError("R10 supports isolated parity and one cash-risk veto only")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul",
                             "InpTakeProfitRRMul", "InpEnableCashRiskVeto"}:
            raise ValueError("R10 has a frozen four-input contract")
        p.update(InpUseGridIndices="false", InpTPGridIndex=2,
                 InpEnableCashRiskVeto="false")
    if r11:
        if (not r2 or production or optimize or mode not in (0, 1)
                or any((r5, r6, r7, r8, control_r1, r9_hold, r10, r12))):
            raise ValueError("R11 supports isolated parity and one-bar persistence only")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul",
                             "InpTakeProfitRRMul", "InpDelayOneBar"}:
            raise ValueError("R11 has a frozen four-input contract")
        p.update(InpUseGridIndices="false", InpTPGridIndex=2, InpDelayOneBar="false")
    if r12:
        if (not r2 or production or optimize or mode not in (0, 1)
                or any((r5, r6, r7, r8, control_r1, r9_hold, r10, r11))):
            raise ValueError("R12 supports isolated parity and one structural-retest policy only")
        if set(overrides) - {"InpEntryStrength", "InpStopLossATRMul",
                             "InpTakeProfitRRMul", "InpStructuralRetest"}:
            raise ValueError("R12 has a frozen four-input contract")
        if "InpStructuralRetest" in overrides and type(overrides["InpStructuralRetest"]) is not bool:
            raise ValueError("R12 structural policy requires an actual boolean override")
        p.update(InpUseGridIndices="false", InpTPGridIndex=2, InpStructuralRetest="false")
    if set(overrides) - set(p):
        raise ValueError("Unknown experiment inputs")
    p.update(overrides)
    if control_r1 and (strict_int(p["InpEntryStrength"], high=2) != 2
                       or finite(p["InpStopLossATRMul"]) != 2.0
                       or finite(p["InpTakeProfitRRMul"]) != 3.0):
        raise ValueError("R8 reporting control requires P2/SL2/TP3")
    if r9_hold and strict_int(p["InpMaxHoldBars"]) not in (60, 90):
        raise ValueError("R9 permits only frozen hold60 and hold90")
    if r5 and str(p["InpRequireM1Alignment"]).lower() not in ("false", "true"):
        raise ValueError("R5 alignment input must be a boolean setting")
    if r5:
        p["InpRequireM1Alignment"] = str(p["InpRequireM1Alignment"]).lower()
    if r5 and mode == 0 and str(p["InpRequireM1Alignment"]).lower() != "false":
        raise ValueError("R5 parity must not enable candidate alignment")
    if r6:
        preset = strict_int(p["InpEntryStrength"], high=1)
        if (float(p["InpStopLossATRMul"]) != 1.5 or float(p["InpTakeProfitRRMul"]) != 2.0
                or (mode == 0 and preset != 0)):
            raise ValueError("R6 fixed exits/preset or exact parity contract changed")
    if r7:
        preset = strict_int(p["InpEntryStrength"], high=1)
        target = finite(p["InpTakeProfitRRMul"])
        if (finite(p["InpStopLossATRMul"]) != 1.5
                or (mode == 0 and (preset != 0 or target != 2.0))
                or (mode == 5 and target not in (0.5, 0.6, 1.0))):
            raise ValueError("R7 fixed stop/target/preset or exact parity contract changed")
    if r8:
        factors = ("InpRequireEfficiency", "InpRequireNearMean")
        for factor in factors:
            if str(p[factor]).lower() not in ("false", "true"):
                raise ValueError("R8 factors must be boolean settings")
            p[factor] = str(p[factor]).lower()
        preset = strict_int(p["InpEntryStrength"], high=2)
        stop, target = finite(p["InpStopLossATRMul"]), finite(p["InpTakeProfitRRMul"])
        if ((mode == 0 and (preset != 0 or stop != 1.5 or target != 2.0
                           or any(p[k] != "false" for k in factors)))
                or (mode == 1 and (preset != 2 or stop != 2.0 or target != 3.0))):
            raise ValueError("R8 continuation/parity exits or preset contract changed")
    if r10:
        veto = str(p["InpEnableCashRiskVeto"]).lower()
        if veto not in ("false", "true"):
            raise ValueError("R10 veto must be a boolean setting")
        p["InpEnableCashRiskVeto"] = veto
        preset = strict_int(p["InpEntryStrength"], high=2)
        stop, target = finite(p["InpStopLossATRMul"]), finite(p["InpTakeProfitRRMul"])
        if (strict_int(p["InpMaxHoldBars"]) != 60
                or (mode == 0 and (preset != 0 or stop != 1.5 or target != 2.0 or veto != "false"))
                or (mode == 1 and (preset != 2 or stop != 2.0 or target != 3.0))):
            raise ValueError("R10 frozen mode, exits, hold or parity contract changed")
    if r11:
        delayed = str(p["InpDelayOneBar"]).lower()
        if delayed not in ("false", "true"):
            raise ValueError("R11 delay must be a boolean setting")
        p["InpDelayOneBar"] = delayed
        preset = strict_int(p["InpEntryStrength"], high=2)
        stop, target = finite(p["InpStopLossATRMul"]), finite(p["InpTakeProfitRRMul"])
        if (strict_int(p["InpMaxHoldBars"]) != 60
                or (mode == 0 and (preset != 0 or stop != 1.5 or target != 2.0 or delayed != "false"))
                or (mode == 1 and (preset != 2 or stop != 2.0 or target != 3.0))):
            raise ValueError("R11 frozen mode, exits, hold or parity contract changed")
    if r12:
        structural = str(p["InpStructuralRetest"]).lower()
        if structural not in ("false", "true"):
            raise ValueError("R12 structural policy must be a boolean setting")
        p["InpStructuralRetest"] = structural
        preset = strict_int(p["InpEntryStrength"], high=2)
        stop, target = finite(p["InpStopLossATRMul"]), finite(p["InpTakeProfitRRMul"])
        if (strict_int(p["InpMaxHoldBars"]) != 60
                or (mode == 0 and (preset != 0 or stop != 1.5 or target != 2.0 or structural != "false"))
                or (mode == 1 and (preset != 2 or stop != 2.0 or target != 3.0))):
            raise ValueError("R12 frozen mode, exits, hold or parity contract changed")
    if str(p["InpFadeBreakouts"]).lower() != "false":
        raise ValueError("V24 baseline is not inverted")
    lines = []
    for k, v in p.items():
        if optimize and k == "InpStopLossATRMul":
            lines.append(f"{k}={v}||1.0||0.5||2.0||Y")
        elif optimize and k == "InpTPGridIndex":
            lines.append(f"{k}=2||0||1||3||Y")
        elif optimize and k == "InpEntryStrength":
            lines.append(f"{k}=0||0||1||2||Y")
        elif optimize and k == "InpUseGridIndices":
            lines.append(f"{k}=true")
        else:
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


def validate_coverage(rows, start, end, expected_passes):
    expected_months = months(start, end)
    grouped = {}
    for row in rows:
        pid, month = strict_int(row["pass"]), strict_int(row["month"])
        key = (pid, month)
        if key in grouped:
            raise ValueError("Duplicate pass/month coverage")
        ticks = finite(row["ticks"])
        first, last = (datetime.fromtimestamp(finite(row[k]) / 1000, timezone.utc).replace(tzinfo=None)
                       for k in ("first_tick_msc", "last_tick_msc"))
        if ticks <= 0 or ticks != int(ticks) or first > last:
            raise ValueError("Empty or malformed monthly tick observations")
        a = datetime(month // 100, month % 100, 1)
        b = datetime(a.year + (a.month == 12), a.month % 12 + 1, 1)
        # Allow weekends and New Year closure. Five days does not hide a missing month.
        if not a <= first < a + timedelta(days=5) or not b - timedelta(days=5) <= last < b:
            raise ValueError("Incomplete monthly edge coverage")
        grouped[key] = int(ticks)
    required = {(pid, month) for pid in expected_passes for month in expected_months}
    if set(grouped) != required:
        raise ValueError("Incomplete requested pass/month coverage")
    return dict(months=expected_months, passes=len(expected_passes), observations=len(grouped),
                metric="EA callbacks, not every raw native tick", interior_gap_free_proven=False,
                total_ticks={str(pid): sum(grouped[pid, m] for m in expected_months) for pid in expected_passes})


def validate_r12_native_fixtures(journal, preset):
    if (type(R12_NATIVE_FIXTURE_COUNT) is not int or R12_NATIVE_FIXTURE_COUNT <= 0
            or type(preset) is not int or preset not in (0, 2)):
        raise ValueError("R12 native fixture identity is not finalized")
    if ("R12_NATIVE_FIXTURE_FAIL" in journal
            or "R12_NATIVE_PLATFORM_PROFIT_FAIL" in journal
            or not re.search(rf"R12_NATIVE_FIXTURES_PASS checks={R12_NATIVE_FIXTURE_COUNT} preset={preset}\b", journal)
            or not re.search(r"R12_NATIVE_PLATFORM_PROFIT_PASS checks=2\b", journal)):
        raise ValueError("R12 requires frozen structural fixtures and native BUY/SELL OrderCalcProfit smoke checks")


def strict_int(value, low=0, high=None):
    n = finite(value)
    if n != int(n) or n < low or (high is not None and n > high):
        raise ValueError("Noninteger/out-of-bounds identifier")
    return int(n)


def native_sequence(path):
    _, rows = report_rows(path)
    return [r for r in rows if r and re.match(r"20\d\d\.\d\d\.\d\d", r[0])
            and any(v in ("buy", "sell") for v in r)]


def audit_xml(path, frames):
    ns = {"s": "urn:schemas-microsoft-com:office:spreadsheet"}
    tree = ET.parse(path)
    rows = [[c.find("s:Data", ns).text for c in row.findall("s:Cell", ns)]
            for row in tree.findall(".//s:Table/s:Row", ns)]
    native = [dict(zip(rows[0], r)) for r in rows[1:]]
    by_pass = {strict_int(r["Pass"]): r for r in native}
    if len(native) != 36 or len(by_pass) != 36:
        raise ValueError("Incomplete native XML grid")
    for f in frames:
        n = by_pass[strict_int(f["pass"])]
        params = (finite(n["InpStopLossATRMul"]), TP_VALUES[strict_int(n["InpTPGridIndex"], high=3)], strict_int(n["InpEntryStrength"], high=2))
        if params != (finite(f["sl_atr"]), finite(f["tp_r"]), strict_int(f["entry_strength"], high=2)):
            raise ValueError("Native XML/input frame mismatch")
        if abs(finite(n["Profit"]) - finite(f["net"])) > .021 or int(n["Trades"]) != int(finite(f["positions"])):
            raise ValueError("Native XML economics mismatch")
        if abs(finite(n["Equity DD %"]) - finite(f["equity_dd_pct"])) > .00011:
            raise ValueError("Native XML drawdown mismatch")
    return dict(native_rows=36, independently_reconciled=36)


def _logs():
    return {p: p.stat().st_size for p in LAB.rglob("*.log") if p.parent.name.lower() == "logs"}


def lab_processes():
    """Read process identity only. Never stop a terminal or expose its arguments."""
    if os.name != "nt":
        raise RuntimeError("Native lab process checks require Windows")
    # Includes an updater executable outside LAB only when its invocation targets
    # this exact data directory. Command lines are inspected but never emitted.
    lab_literal = str(LAB.resolve()).replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop'; "
        f"$candidateLab='{lab_literal}'; "
        "@(Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe' OR Name='metatester64.exe'\" | "
        "Where-Object { ($_.ExecutablePath -and "
        "$_.ExecutablePath.StartsWith($candidateLab + '\\',[StringComparison]::OrdinalIgnoreCase)) "
        "-or ($_.CommandLine -and $_.CommandLine.Contains('/path:\"' + $candidateLab + '\"')) } | "
        "Select-Object ProcessId,Name) | ConvertTo-Json -Compress"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, timeout=20, check=True)
    payload = json.loads(result.stdout.strip() or "[]")
    rows = [payload] if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or any(not isinstance(row, dict)
            or type(row.get("ProcessId")) is not int or row["ProcessId"] <= 0
            or row.get("Name") not in ("terminal64.exe", "metatester64.exe") for row in rows):
        raise RuntimeError("Cannot verify isolated native lab process identity")
    return rows


def assert_lab_idle(wait_seconds=0):
    """Bounded drain of a previous tester. Busy never grants kill permission."""
    deadline = time.monotonic() + wait_seconds
    while True:
        active = lab_processes()
        if not active:
            return
        if time.monotonic() >= deadline:
            ids = ",".join(str(row["ProcessId"]) for row in active)
            raise RuntimeError(f"Isolated native lab still busy (PIDs {ids}). No new launch.")
        time.sleep(.5)


def completion_ok(journal, optimize=False):
    if re.search(r"LiveUpdate[^\n]*\bstart\b", journal, re.I):
        return False
    if optimize:
        return ("optimization finished, total passes 36" in journal
                and "local 36 tasks (100%), remote 0 tasks (0%), cloud 0 tasks (0%)" in journal
                and "processing stopped" in journal)
    legacy = "automatic testing finished" in journal
    updated = ('last test passed with result "successfully finished"' in journal
               and bool(re.search(r"test Experts\\[^\n]+ thread finished", journal))
               and bool(re.search(r"Tester\s+final balance [-\d.]+ [A-Z]{3}", journal)))
    return legacy or updated


def optimization_result(output, report, name, mode, start, end):
    frames = csv_rows(output / f"{name}_optimization.csv")
    wanted = set(product(SL_VALUES, TP_VALUES, range(3)))
    actual = {(finite(r["sl_atr"]), finite(r["tp_r"]), strict_int(r["entry_strength"], high=2)) for r in frames}
    pass_ids = {strict_int(r["pass"]) for r in frames}
    if len(frames) != 36 or len(pass_ids) != 36 or actual != wanted:
        raise ValueError("Candidate grid incomplete or duplicate")
    for r in frames:
        metrics(r)
        if strict_int(r["mode"], high=3) != mode or finite(r["be_r"]) != 0:
            raise ValueError("Unexpected mode/BE")
    coverage = validate_coverage(csv_rows(output / f"{name}_coverage.csv"), start, end, pass_ids)
    for r in frames:
        if strict_int(r["observed_ticks"], low=1) != coverage["total_ticks"][str(strict_int(r["pass"]))]:
            raise ValueError("Monthly tick total disagrees with main frame")
    return dict(rows=frames, coverage=coverage, xml_audit=audit_xml(output / report.name, frames), in_sample_only=True)


def recover_completed_optimization(output, signature, name, mode, start, end):
    """Reconcile a false completion rejection, never fabricate or re-run outcomes."""
    started = output / "started.json"
    report = LAB / "reports" / f"{name}.xml"
    journals = sorted(output.glob("journal_*.txt"))
    if not started.exists() or not report.exists() or not journals:
        return None
    if json.loads(started.read_text())["signature"] != signature:
        raise ValueError("Interrupted optimization signature drift")
    journal = "\n".join(p.read_text(encoding="utf-8") for p in journals)
    if not completion_ok(journal, True) or "exit with code 0" not in journal:
        return None
    if re.search(r"tester agent authorization error|tester not started|no real ticks|generated ticks|ticks?[^\n]*(?:discarded|replaced|missing)|history[^\n]*error", journal, re.I):
        raise ValueError("Recovered optimization quality error")
    normalized_set = (output / f"{name}.set").read_text(encoding="utf-16")
    if __import__("hashlib").sha256(normalized_set.encode("utf-16")).hexdigest() != signature["set_sha"]:
        raise ValueError("Interrupted optimization SET drift")
    for original in [report, LAB / "MQL5/Files" / f"{name}_optimization.csv", LAB / "MQL5/Files" / f"{name}_coverage.csv"]:
        target = output / original.name
        if target.exists() and sha(target) != sha(original):
            raise ValueError("Interrupted optimization artifact drift")
        if not target.exists():
            shutil.copy2(original, target)
    result = optimization_result(output, report, name, mode, start, end)
    result.update(evidence_run=name, cache_hashes_verified=True, terminal_cache_read_warnings=[],
                  reconciled_completion_rejection=True)
    save(output / "accepted.json", dict(signature=signature, result=result))
    print(f"RECONCILE ACCEPT {name}", flush=True)
    return result


@contextmanager
def lab_lease():
    """OS releases this lock on interruption. Never stale-lock another run."""
    import msvcrt
    with (LAB / "candidate_native.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another candidate batch owns the isolated lab") from exc
        try:
            assert_lab_idle()
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def completion_failure(journal, exit_code, report_exists, optimize=False):
    """Classify setup failure without accepting it or guessing account expiry."""
    account_missing = bool(re.search(
        r"tester not started because the account is not specified", journal, re.I))
    update_relaunch = bool(re.search(r"LiveUpdate[^\n]*\bstart\b", journal, re.I))
    category = ("TESTER_ACCOUNT_UNAVAILABLE" if account_missing else
                "NATIVE_RUNTIME_UPDATE_RELAUNCH" if update_relaunch else "NATIVE_COMPLETION_FAILED")
    return dict(category=category,
                native_exit_code=exit_code, report_exists=bool(report_exists),
                completion_observed=completion_ok(journal, optimize), accepted=False,
                strategy_result_available=False,
                account_expiry_proven=False if account_missing else None)


def execute(name, mode=0, overrides=None, *, start=START, end=END, deposit=10000,
            optimize=False, production=False, delay=200, timeout=1800, candidate_source=None,
            evidence_base=None, tester_login=None, r9_hold=False, leverage=200):
    if type(leverage) is not int or leverage not in (200, 500):
        raise ValueError("Native research permits only explicit leverage 200 or 500")
    if isinstance(deposit, bool) or finite(deposit) <= 0:
        raise ValueError("Native research deposit must be finite and positive")
    if type(r9_hold) is not bool or (r9_hold and
            (candidate_source != "research/ResearchControl_R1_R8.mq5"
             or mode != 1 or production or optimize)):
        raise ValueError("R9 hold profile requires the reviewed R1 reporting control")
    if tester_login is not None and (isinstance(tester_login, bool)
                                    or not isinstance(tester_login, int) or tester_login <= 0):
        raise ValueError("Tester connection login must be a positive integer")
    connection_login = 5055578643 if tester_login is None else tester_login
    r2 = candidate_source is not None
    r5 = candidate_source == "research/ResearchCandidate_R5.mq5"
    r6 = candidate_source == "research/ResearchCandidate_R6.mq5"
    r7 = candidate_source == "research/ResearchCandidate_R7.mq5"
    r8 = candidate_source == "research/ResearchCandidate_R8.mq5"
    r10 = candidate_source == "research/ResearchCandidate_R10.mq5"
    r11 = candidate_source == "research/ResearchCandidate_R11.mq5"
    r12 = candidate_source == "research/ResearchCandidate_R12.mq5"
    control_r1 = candidate_source == "research/ResearchControl_R1_R8.mq5"
    if r2 and candidate_source not in ("research/ResearchCandidate_R2.mq5", "research/ResearchCandidate_R3.mq5", "research/ResearchCandidate_R4.mq5", "research/ResearchCandidate_R5.mq5", "research/ResearchCandidate_R6.mq5", "research/ResearchCandidate_R7.mq5", "research/ResearchCandidate_R8.mq5", "research/ResearchCandidate_R10.mq5", "research/ResearchCandidate_R11.mq5", "research/ResearchCandidate_R12.mq5", "research/ResearchControl_R1_R8.mq5"):
        raise ValueError("Unsupported isolated candidate source")
    allowed_modes = ((1,) if control_r1 else (0, 1) if r8 or r10 or r11 or r12 else (0, 6, 7) if r6 else (0, 5) if candidate_source in
                     ("research/ResearchCandidate_R4.mq5", "research/ResearchCandidate_R5.mq5", "research/ResearchCandidate_R7.mq5")
                     else range(4) if candidate_source == "research/ResearchCandidate_R3.mq5"
                     else range(6) if r2 else MODE_NAMES)
    if not re.fullmatch(r"[A-Za-z0-9_]+", name) or mode not in allowed_modes:
        raise ValueError("Invalid run name/mode")
    overrides = overrides or {}
    output_base = BASE if evidence_base is None else Path(evidence_base).resolve()
    if not output_base.resolve().is_relative_to((ROOT / "reports").resolve()):
        raise ValueError("Native evidence output must remain in project reports")
    runtime, before_cache = freeze(output_base), cache_manifest(start, end)
    source = ROOT / ("AegisPredator_v24.mq5" if production else candidate_source or "research/ResearchCandidate_R1.mq5")
    binary = source.with_suffix(".ex5")
    text = settings(name, mode, overrides, optimize, production, r2, r5, r6, r7, r8, control_r1, r9_hold, r10, r11, r12)
    signature = dict(start=start, end=end, mode=mode, overrides=overrides, deposit=deposit,
                     optimize=optimize, production=production, delay_ms=delay, runtime=runtime,
                     source_sha=sha(source), binary_sha=sha(binary),
                     set_sha=__import__("hashlib").sha256(text.encode("utf-16")).hexdigest(),
                     tick_cache=before_cache)
    # Preserve old signatures for explicitly reused controls. A user-selected
    # fresh lab connection is part of each new run's provenance, never a secret.
    if tester_login is not None:
        signature["tester_connection_login"] = tester_login
    if r9_hold:
        signature["research_profile"] = "R9_HOLD_60_90"
    # Historical signatures implicitly used 1:200. Do not rewrite old evidence.
    # A new 1:500 run must never reuse an accepted 1:200 outcome.
    if leverage != 200:
        signature["leverage"] = leverage
    output = output_base / "runs" / name
    if (output / "accepted.json").exists():
        accepted = json.loads((output / "accepted.json").read_text())
        if accepted["signature"] != signature:
            raise ValueError("Existing accepted signature differs")
        return accepted["result"]
    if output.exists():
        if optimize:
            recovered = recover_completed_optimization(output, signature, name, mode, start, end)
            if recovered is not None:
                return recovered
        retry = re.search(r"_retry(\d+)$", name)
        count = int(retry.group(1)) if retry else 0
        if count >= 2:
            raise ValueError("Incomplete run after two bounded retries. Preserve evidence.")
        original_name = name[:retry.start()] if retry else name
        print(f"RETRY preserved unaccepted run {name}", flush=True)
        return execute(f"{original_name}_retry{count+1}", mode, overrides, start=start, end=end,
                       deposit=deposit, optimize=optimize, production=production,
                       delay=delay, timeout=timeout, candidate_source=candidate_source,
                       evidence_base=output_base, tester_login=tester_login, r9_hold=r9_hold,
                       leverage=leverage)
    assert_lab_idle(wait_seconds=15)
    output.mkdir(parents=True)
    shutil.copy2(binary, LAB / "MQL5/Experts" / binary.name)
    set_path = LAB / "MQL5/Profiles/Tester" / f"{name}.set"
    set_path.write_text(text, encoding="utf-16")
    ext = "xml" if optimize else "htm"
    report = LAB / "reports" / f"{name}.{ext}"
    if report.exists():
        raise ValueError("Refuse existing report overwrite")
    ini = LAB / f"{name}.ini"
    ini.write_text(f"""[Common]
Login={connection_login}
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
Leverage=1:{leverage}
Model=4
ExecutionMode={delay}
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
    old_logs = _logs()
    save(output / "started.json", dict(signature=signature, started_utc=datetime.now(timezone.utc).isoformat()))
    startup = subprocess.STARTUPINFO() if os.name == "nt" else None
    if startup:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    print(f"START {name}", flush=True)
    process = subprocess.Popen([str(LAB / "terminal64.exe"), "/portable", f"/config:{ini}"], cwd=LAB, startupinfo=startup)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=30)
        save(output / "failure.json", dict(reason="isolated native terminal timeout", report_exists=report.exists()))
        raise RuntimeError("Isolated native terminal timeout. Not accepted.")
    try:
        assert_lab_idle(wait_seconds=15)
    except RuntimeError:
        save(output / "failure.json", dict(category="LAB_BUSY_AFTER_PARENT_EXIT", accepted=False,
            strategy_result_available=False, native_exit_code=code, report_exists=report.exists(),
            lab_processes_remaining=lab_processes()))
        raise
    texts = []
    for i, (p, length) in enumerate(_logs().items()):
        raw = p.read_bytes()
        previous = old_logs.get(p, 0)
        previous = 0 if length < previous else previous
        if length > previous:
            delta = raw[previous:].decode("utf-16-le", errors="replace")
            (output / f"journal_{i}.txt").write_text(delta, encoding="utf-8")
            texts.append(delta)
    journal = "\n".join(texts)
    if code or not report.exists() or not completion_ok(journal, optimize):
        failure = completion_failure(journal, code, report.exists(), optimize)
        failure["lab_processes_remaining"] = lab_processes()
        save(output / "failure.json", failure)
        if failure["category"] == "TESTER_ACCOUNT_UNAVAILABLE":
            raise ValueError("MT5 Tester account unavailable. No strategy result. Restore demo login in isolated lab before retry.")
        raise ValueError(f"Native completion/report missing: {code}")
    fixture_prefix = Path(candidate_source).stem.rsplit("_", 1)[-1] if r2 else "R2"
    if r2 and not control_r1 and (f"{fixture_prefix}_NATIVE_FIXTURE_FAIL" in journal or
               not re.search(rf"{fixture_prefix}_NATIVE_FIXTURES_PASS checks=[1-9]\d* preset={overrides.get('InpEntryStrength', 0)}\b", journal)):
        raise ValueError("Actual MQL behavioral fixtures missing/failed")
    if candidate_source == "research/ResearchCandidate_R4.mq5" and not re.search(rf"R4_NATIVE_FIXTURES_PASS checks=25 preset={overrides.get('InpEntryStrength', 0)}\b", journal):
        raise ValueError("R4 requires all 25 frozen native fixtures")
    if candidate_source == "research/ResearchCandidate_R5.mq5" and not re.search(rf"R5_NATIVE_FIXTURES_PASS checks=27 preset={overrides.get('InpEntryStrength', 0)}\b", journal):
        raise ValueError("R5 requires all 27 frozen native fixtures")
    if r7 and not re.search(rf"R7_NATIVE_FIXTURES_PASS checks=31 preset={overrides.get('InpEntryStrength', 0)}\b", journal):
        raise ValueError("R7 requires all 31 frozen native fixtures")
    if r8 and not re.search(rf"R8_NATIVE_FIXTURES_PASS checks=27 preset={overrides.get('InpEntryStrength', 0)}\b", journal):
        raise ValueError("R8 requires all 27 frozen native fixtures")
    if r10 and ("R10_NATIVE_PLATFORM_PROFIT_FAIL" in journal
                or not re.search(rf"R10_NATIVE_FIXTURES_PASS checks=10 preset={overrides.get('InpEntryStrength', 0)}\b", journal)
                or not re.search(r"R10_NATIVE_PLATFORM_PROFIT_PASS checks=2\b", journal)):
        raise ValueError("R10 requires actual BUY/SELL native OrderCalcProfit smoke fixtures")
    if r11 and not re.search(rf"R11_NATIVE_FIXTURES_PASS checks=19 preset={overrides.get('InpEntryStrength', 0)}\b", journal):
        raise ValueError("R11 requires all19 frozen native delay-state fixtures")
    if r12:
        validate_r12_native_fixtures(journal, overrides.get("InpEntryStrength", 0))
    if r6:
        preset = overrides.get("InpEntryStrength", 0)
        fixture_patterns = (rf"R5_NATIVE_FIXTURES_PASS checks=27 preset={preset}\b",
                            rf"R6_NATIVE_FIXTURES_PASS checks=20 preset={preset}\b",
                            rf"R6_NATIVE_FIXTURES_TOTAL checks=47 R5=27 R6=20 preset={preset}\b")
        if "R5_NATIVE_FIXTURE_FAIL" in journal or any(not re.search(pattern, journal) for pattern in fixture_patterns):
            raise ValueError("R6 requires all 47 frozen native fixtures, including inherited R5 checks")
    warnings = [line for line in journal.splitlines() if re.search(r"History\s+'XAUUSD' file opening or reading error \[32\]", line)]
    checked = "\n".join(line for line in journal.splitlines() if line not in warnings)
    if re.search(r"tester agent authorization error|tester not started|no real ticks|generated ticks|ticks?[^\n]*(?:discarded|replaced|missing)|history[^\n]*error", checked, re.I):
        raise ValueError("Native history/auth/tick-quality error")
    if warnings and "preliminary downloading of M1 history completed" not in journal:
        raise ValueError("Unrecovered history sharing violation")
    shutil.copy2(report, output)
    for p in list((LAB / "Tester").rglob(f"{name}_*.csv")) + list((LAB / "MQL5/Files").glob(f"{name}_*.csv")):
        destination = output / p.name
        if destination.exists():
            raise ValueError("Duplicate native export")
        shutil.copy2(p, destination)
    if sha(source) != signature["source_sha"] or sha(binary) != signature["binary_sha"]:
        raise ValueError("Candidate source/binary changed during run")
    if runtime != freeze(output_base) or before_cache != cache_manifest(start, end):
        raise ValueError("Runtime/tick-cache drift during run")
    if optimize:
        result = optimization_result(output, report, name, mode, start, end)
    else:
        native, native_rows = report_rows(output / report.name)
        if money(native.get("Initial Deposit", -1)) != deposit or native.get("Leverage") != f"1:{leverage}":
            raise ValueError("Native report capital/leverage differs from requested test")
        if native.get("History Quality") != "100% real ticks" or money(native.get("Ticks", 0)) <= 0 or money(native.get("Bars", 0)) <= 0:
            raise ValueError("Native real-tick report invalid")
        result = dict(native=native)
        if not production:
            specs = {r["key"]: r["value"] for r in csv_rows(output / f"{name}_spec.csv")}
            if strict_int(specs.get("leverage", -1)) != leverage:
                raise ValueError("Native account specification leverage differs from requested test")
            try:
                if r8 or control_r1 or r10 or r11 or r12:
                    trades, cash, end_audit = parse_verified_native_deals(
                        csv_rows(output / f"{name}_deals.csv"), native, native_rows, specs, journal,
                        end=end, deposit=deposit, candidate_source=candidate_source)
                    result["native_end_close_audit"] = end_audit
                else:
                    trades, cash = parse_deals(csv_rows(output / f"{name}_deals.csv"))
            except ValueError as exc:
                save(output / "failure.json", dict(category="NATIVE_HISTORY_EXPORT_INVALID", accepted=False,
                    native_exit_code=code, native_completion_observed=True, strategy_result_available=False,
                    exported_economics_accepted=False, reason=str(exc), report_exists=True))
                raise
            if len(cash) != 1 or cash[0]["type"] != 2 or abs(cash[0]["net"] - deposit) > .021:
                raise ValueError("Unexpected account cash adjustments")
            summary = bucket(trades)
            if abs(summary["net"] - money(native["Total Net Profit"])) > .021 or summary["trades"] != int(money(native["Total Trades"])):
                raise ValueError("Native position net/count mismatch")
            if specs.get("history_export_ok") not in ("true", "1") or abs(finite(specs["final_balance"]) - deposit - summary["net"]) > .021:
                raise ValueError("History/balance reconciliation failed")
            coverage = validate_coverage(csv_rows(output / f"{name}_coverage.csv"), start, end, {0})
            observed, native_ticks = strict_int(specs["observed_ticks"], low=1), strict_int(money(native["Ticks"]), low=1)
            if coverage["total_ticks"]["0"] != observed or observed > native_ticks:
                raise ValueError("Monthly callback total vs observed/native ticks mismatch")
            coverage.update(native_raw_ticks=native_ticks, observed_callbacks=observed,
                            callbacks_skipped_by_execution=native_ticks-observed)
            month_keys = [f"{m//100:04d}-{m%100:02d}" for m in months(start, end)]
            result.update(summary, coverage=coverage,
                          monthly={m: bucket([t for t in trades if t["close"].startswith(m)]) for m in month_keys},
                          sides={s: bucket([t for t in trades if t["direction"] == s]) for s in ("buy", "sell")},
                          exits={str(k): bucket([t for t in trades if t["exit_reason"] == k]) for k in sorted({t["exit_reason"] for t in trades})},
                          final_balance=finite(specs["final_balance"]), native_equity_dd_pct=dd_percent(native),
                          native_stopout=any(t["exit_reason"] == 6 for t in trades),
                          extra_cost_stress={str(cost): round(summary["net"] - cost * summary["trades"], 2) for cost in (.2, .5)})
    result.update(evidence_run=name, cache_hashes_verified=True, terminal_cache_read_warnings=warnings)
    if r2 and not control_r1:
        result["native_mql_fixture_checks"] = int(re.search(rf"{fixture_prefix}_NATIVE_FIXTURES_PASS checks=(\d+)", journal).group(1))
        if r6:
            result.update(native_mql_fixture_checks=47,
                          native_mql_fixture_components={"R5": 27, "R6": 20})
    save(output / "accepted.json", dict(signature=signature, result=result))
    print(f"ACCEPT {name}", flush=True)
    return result


def qualify(row, min_trades=150, pf=1.2):
    m = metrics(row) if "positions" in row else dict(net=row["net"], pf=row["net_profit_factor"], trades=row["trades"], dd_pct=row["native_equity_dd_pct"])
    return m["net"] > 0 and m["trades"] >= min_trades and m["pf"] is not None and m["pf"] >= pf


def parameters(row):
    return dict(InpStopLossATRMul=finite(row["sl_atr"]), InpTakeProfitRRMul=finite(row["tp_r"]),
                InpEntryStrength=int(finite(row["entry_strength"])))


def verified_signature(result, evidence_base):
    """Validate accepted provenance without launching or following manifest paths."""
    root = Path(evidence_base).resolve()
    name = result.get("evidence_run")
    if not root.is_relative_to((ROOT / "reports").resolve()) or not isinstance(name, str) \
            or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Invalid accepted environment identity")
    directory = root / "runs" / name
    accepted = json.loads((directory / "accepted.json").read_text(encoding="utf-8-sig"))
    started = json.loads((directory / "started.json").read_text(encoding="utf-8-sig"))
    signature = accepted.get("signature")
    if not isinstance(signature, dict) or started.get("signature") != signature \
            or accepted.get("result", {}).get("evidence_run") != name:
        raise ValueError("Accepted/started environment provenance differs")
    runtime = json.loads((root / "runtime_freeze.json").read_text(encoding="utf-8-sig"))
    if signature.get("runtime") != runtime:
        raise ValueError("Accepted runtime differs from batch freeze")
    ticks = signature.get("tick_cache")
    if not isinstance(ticks, list) or [r.get("month") for r in ticks] != months(signature["start"], signature["end"]):
        raise ValueError("Accepted tick-cache month coverage differs")
    return signature


def verify_environment(reference_result, result, *, evidence_base, reference_base=None):
    """Every candidate month must match its full-period reference, before selection."""
    left = verified_signature(reference_result, evidence_base if reference_base is None else reference_base)
    right = verified_signature(result, evidence_base)
    if left["runtime"] != right["runtime"]:
        raise ValueError("Runtime differs across accepted controls/candidates")
    reference = {row["month"]: row for row in left["tick_cache"]}
    if any(reference.get(row["month"]) != row for row in right["tick_cache"]):
        raise ValueError("Tick cache differs across accepted controls/candidates")
    return dict(passed=True, compared_months=[r["month"] for r in right["tick_cache"]])


def parity(production, harness, *, evidence_base=None, production_base=None):
    p, h = production["evidence_run"], harness["evidence_run"]
    harness_base = BASE if evidence_base is None else Path(evidence_base)
    baseline_base = harness_base if production_base is None else Path(production_base)
    environment = verify_environment(production, harness, evidence_base=harness_base,
                                     reference_base=baseline_base)
    keys = ("Total Net Profit", "Gross Profit", "Gross Loss", "Total Trades", "Ticks", "Bars", "History Quality", "Equity Drawdown Maximal", "Balance Drawdown Maximal")
    if any(production["native"][k] != harness["native"][k] for k in keys):
        raise ValueError("V24 native metrics differ from mode0")
    left = native_sequence(baseline_base / "runs" / p / f"{p}.htm")
    right = native_sequence(harness_base / "runs" / h / f"{h}.htm")
    if not left or left != right:
        raise ValueError("V24 ordered native economics differ from mode0")
    return dict(passed=True, native_rows=len(left), metrics=list(keys), environment=environment,
                includes_2025=any(r[0].startswith("2025.") for r in left))


def run_all(prefix):
    progress = dict(project="V25 research target, not a released bot", development={}, validation=[], qualified=False,
                    genuinely_unseen_oos=False, promotion=False)
    production = execute(f"{prefix}_production_v24", production=True)
    baseline = execute(f"{prefix}_baseline", mode=0)
    progress.update(baseline=baseline, parity=parity(production, baseline))
    save(BASE / f"{prefix}_progress.json", progress)
    for mode in (1, 2, 3):
        development = execute(f"{prefix}_dev_{MODE_NAMES[mode]}", mode, end=DEV_END, optimize=True)
        progress["development"][str(mode)] = development
        ranked = sorted([r for r in development["rows"] if qualify(r)],
                        key=lambda r: (finite(r["equity_dd_pct"]), -finite(r["net"]), finite(r["sl_atr"]), finite(r["tp_r"]), finite(r["entry_strength"])))[:3]
        for i, row in enumerate(ranked):
            params = parameters(row)
            validation = execute(f"{prefix}_val_{mode}_{i}", mode, params, start=DEV_END, end=VAL_END)
            progress["validation"].append(dict(mode=mode, parameters=params, development=row,
                                               result=validation, eligible=qualify(validation, 40)))
        save(BASE / f"{prefix}_progress.json", progress)
    survivors = [r for r in progress["validation"] if r["eligible"]]
    if survivors:
        chosen = min(survivors, key=lambda r: (r["result"]["native_equity_dd_pct"], -r["result"]["net"], r["mode"], json.dumps(r["parameters"], sort_keys=True)))
        lock = dict(mode=chosen["mode"], parameters=chosen["parameters"], selected_using="development_and_validation_only",
                    locked_utc=datetime.now(timezone.utc).isoformat(), reselect_after_confirmation=False)
        lockpath = BASE / f"{prefix}_selection_lock.json"
        if lockpath.exists():
            old = json.loads(lockpath.read_text())
            if old["mode"] != lock["mode"] or old["parameters"] != lock["parameters"]:
                raise ValueError("Selection lock changed")
            lock = old
        else:
            save(lockpath, lock)
        progress["selection_lock"] = lock
        confirm = execute(f"{prefix}_confirmation", lock["mode"], lock["parameters"], start=VAL_END)
        full = execute(f"{prefix}_locked10m", lock["mode"], lock["parameters"])
        positive_months = sum(x["net"] > 0 for x in full["monthly"].values())
        progress.update(confirmation=confirm, full=full, positive_months=positive_months,
                        qualified=qualify(confirm, 40, 1.1) and qualify(full, 150, 1.15)
                        and positive_months >= 7 and full["net"] > baseline["net"]
                        and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"],
                        capital70=execute(f"{prefix}_capital70", lock["mode"], lock["parameters"], deposit=70),
                        baseline70=execute(f"{prefix}_baseline70", mode=0, deposit=70),
                        delay500=execute(f"{prefix}_delay500", lock["mode"], lock["parameters"], delay=500))
    else:
        best = max([(int(mode), row) for mode, dev in progress["development"].items() for row in dev["rows"]],
                   key=lambda x: (finite(x[1]["net"]), -finite(x[1]["equity_dd_pct"])))
        progress["failure_reason"] = "No development/validation-qualified candidate"
        progress["descriptive_failed_candidate"] = dict(mode=best[0], parameters=parameters(best[1]),
            result=execute(f"{prefix}_descriptive10m", best[0], parameters(best[1])),
            selection="Development-only maximum, not validated or promotion-eligible")
    progress["release_evidence"] = release_evidence(progress)
    save(BASE / f"{prefix}_complete.json", progress)
    print(f"COMPLETE qualified={progress['qualified']} promotion=False", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("smoke", "all"))
    parser.add_argument("--prefix", default="r1")
    args = parser.parse_args()
    with lab_lease():
        if args.action == "smoke":
            execute(f"{args.prefix}_smoke", start="2026.09.01", end=END)
        else:
            run_all(args.prefix)
