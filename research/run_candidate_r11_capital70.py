"""One preregistered one-bar-persistence experiment, USD70/1:500, no release."""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import re

from research import run_candidate_r9_capital70 as r9
from research import run_candidate_r10_capital70 as r10
from research import run_v25_native as native
from research.native_end_accounting import parse_verified_native_deals
from research.candidate_delay_audit import audit_delay
from research.run_v23_tuning import save

ROOT, BASE = r9.ROOT, r9.BASE
SOURCE = "research/ResearchCandidate_R11.mq5"
# Root pins these only after final source review and clean compile.
SOURCE_SHA = "F19DDB56768BD1E02F05DA4FA859F3E428561CECB006FD103967EC072184D246"
BINARY_SHA = "C51AAFEE1E84D3050312F2B3010A1B57EFC4638505A97EF7CEE3ECB1ED320AB0"
DEPOSIT, LEVERAGE = 70, 500


def parameters(delay):
    if type(delay) is not bool:
        raise ValueError("R11 requires one explicit boolean delay treatment")
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpDelayOneBar=delay)


def pinned_preflight():
    r9.pinned_preflight()
    if SOURCE_SHA == "REVIEW_REQUIRED" or BINARY_SHA in ("UNCOMPILED", "REVIEW_REQUIRED"):
        raise ValueError("R11 source/binary review and compile pins are not finalized")
    if native.sha(ROOT / SOURCE) != SOURCE_SHA or native.sha((ROOT / SOURCE).with_suffix(".ex5")) != BINARY_SHA:
        raise ValueError("R11 reviewed source/binary identity differs")
    refs = r10.pinned_preflight()
    completed = json.loads((BASE / "r10_70_a_complete.json").read_text(encoding="utf-8"))
    if (completed.get("qualified") is not False or completed.get("promotion") is not False
            or completed.get("qualification_status") != "FAILED"):
        raise ValueError("R11 requires the completed, failed R10 reference batch")
    return refs


def validate_delay_evidence(folder, name, *, result, enabled, mode=None):
    """Reconcile actual specs, chronological pending state and native positions."""
    if type(mode) is not int or mode not in (0, 1) or type(enabled) is not bool:
        raise ValueError("R11 pending-state diagnostics need exact mode and enable flag")
    rows = native.csv_rows(folder / f"{name}_spec.csv")
    specs = {row["key"]: row["value"] for row in rows}
    required = ("point", "digits", "tick_size", "delay_enabled", "delay_seconds")
    if len(specs) != len(rows) or any(key not in specs for key in required):
        raise ValueError("R11 missing/duplicate instrument/delay specs")
    point, tick = native.finite(specs["point"]), native.finite(specs["tick_size"])
    digits = native.strict_int(specs["digits"], high=10)
    token = specs["delay_enabled"].strip().lower()
    if (point <= 0 or tick <= 0 or abs(point - 10 ** (-digits)) > point * 1e-10
            or token not in ("true", "false", "1", "0")
            or (token in ("true", "1")) is not enabled
            or native.strict_int(specs["delay_seconds"]) != 60):
        raise ValueError("R11 actual instrument/delay spec values differ")
    counts = audit_delay(native.csv_rows(folder / f"{name}_raw.csv"),
        native.csv_rows(folder / f"{name}_signals.csv"), enabled=enabled, mode=mode)
    if enabled and counts["confirmed_filled"] != result.get("trades"):
        raise ValueError("R11 confirmed fills differ from verified native position count")
    return dict(specs={key: specs[key] for key in required}, counts=counts)


def validate_result(result):
    sig = native.verified_signature(result, BASE)
    name = result["evidence_run"]
    folder = BASE / "runs" / name
    if (sig.get("deposit") != DEPOSIT or sig.get("leverage") != LEVERAGE
            or sig.get("production") is not False or sig.get("optimize") is not False
            or sig.get("delay_ms") not in (200, 500)
            or sig.get("source_sha") != SOURCE_SHA or sig.get("binary_sha") != BINARY_SHA
            or type(sig.get("tester_connection_login")) is not int
            or sig["tester_connection_login"] <= 0):
        raise ValueError("R11 native signature capital/identity differs")
    mode, overrides = sig.get("mode"), sig.get("overrides")
    if not ((mode == 0 and overrides == {})
            or (mode == 1 and isinstance(overrides, dict)
                and overrides in (parameters(False), parameters(True)))):
        raise ValueError("R11 treatment contract differs")
    enabled = bool(overrides.get("InpDelayOneBar", False))
    actual = (folder / f"{name}.set").read_text(encoding="utf-16")
    if (actual != native.settings(name, mode, overrides, r2=True, r11=True)
            or hashlib.sha256(actual.encode("utf-16")).hexdigest() != sig.get("set_sha")):
        raise ValueError("R11 actual SET differs")
    ini = configparser.ConfigParser()
    ini.read(folder / f"{name}.ini", encoding="utf-16")
    expected = {"Deposit": "70", "Leverage": "1:500", "Model": "4", "Optimization": "0",
        "Symbol": "XAUUSD", "Period": "M1", "UseCloud": "0", "UseRemote": "0", "UseLocal": "1",
        "FromDate": sig["start"], "ToDate": sig["end"], "ExecutionMode": str(sig["delay_ms"]),
        "Expert": "ResearchCandidate_R11.ex5", "ExpertParameters": f"{name}.set",
        "ShutdownTerminal": "1"}
    if (any(ini["Tester"].get(k) != v for k, v in expected.items())
            or ini["Common"].get("Login") != str(sig["tester_connection_login"])
            or ini["Common"].get("Server") != "MetaQuotes-Demo"
            or any(ini["Experts"].get(k) != "0" for k in ("Enabled", "AllowLiveTrading", "AllowDllImport"))):
        raise ValueError("R11 actual INI capital/model/isolation differs")
    report, rows = native.report_rows(folder / f"{name}.htm")
    if (report != result.get("native") or report.get("Initial Deposit") != "70.00"
            or report.get("Leverage") != "1:500" or report.get("History Quality") != "100% real ticks"):
        raise ValueError("R11 actual native HTML differs")
    specs = {row["key"]: row["value"] for row in native.csv_rows(folder / f"{name}_spec.csv")}
    if native.strict_int(specs.get("leverage", -1)) != LEVERAGE:
        raise ValueError("R11 exported leverage differs")
    journal = "\n".join(path.read_text(encoding="utf-8") for path in folder.glob("journal_*.txt"))
    if ("R11_NATIVE_FIXTURE_FAIL" in journal
            or not re.search(rf"R11_NATIVE_FIXTURES_PASS checks=19 preset={overrides.get('InpEntryStrength', 0)}\b", journal)):
        raise ValueError("R11 actual native fixtures missing/failed")
    trades, cash, _ = parse_verified_native_deals(native.csv_rows(folder / f"{name}_deals.csv"),
        report, rows, specs, journal, end=sig["end"], deposit=DEPOSIT, candidate_source=SOURCE)
    aggregate = native.bucket(trades)
    if (len(cash) != 1 or cash[0]["net"] != DEPOSIT
            or any(aggregate.get(key) != result.get(key) for key in ("trades", "net", "net_profit_factor"))
            or abs(native.finite(specs["final_balance"]) - DEPOSIT - aggregate["net"]) > .021
            or result.get("native_stopout") is not any(t["exit_reason"] == 6 for t in trades)):
        raise ValueError("R11 actual cash/position/economics/stopout differ")
    return validate_delay_evidence(folder, name, result=result, enabled=enabled, mode=mode)


def execute(name, mode, overrides, *, tester_login, start=native.START, end=native.END, delay=200):
    result = native.execute(name, mode, overrides, candidate_source=SOURCE,
        tester_login=tester_login, evidence_base=BASE, deposit=DEPOSIT, leverage=LEVERAGE,
        start=start, end=end, delay=delay)
    delay_audit = validate_result(result)
    save(BASE / "runs" / result["evidence_run"] / "delay_audit.json", delay_audit)
    return result


def run_all(prefix, tester_login):
    if not isinstance(prefix, str) or not re.fullmatch(r"r11_70_[A-Za-z0-9_]+", prefix):
        raise ValueError("R11 requires a safe capital70 prefix")
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R11 requires explicit research demo login")
    refs = pinned_preflight()
    if tester_login != native.verified_signature(refs["baseline"], BASE)["tester_connection_login"]:
        raise ValueError("R11 research connection differs from reviewed capital70 controls")

    parity = execute(f"{prefix}_parity", 0, {}, tester_login=tester_login)
    mode0_parity = native.parity(refs["production"], parity, evidence_base=BASE)
    if mode0_parity.get("passed") is not True:
        raise ValueError("R11 exact V24 parity failed")
    control = execute(f"{prefix}_control_dev", 1, parameters(False),
                      tester_login=tester_login, end=native.DEV_END)
    control_parity = native.parity(refs["control"], control, evidence_base=BASE)
    if control_parity.get("passed") is not True:
        raise ValueError("R11 delay-off R9 control parity failed")

    progress = dict(project="R11 one-bar persistence, not V25", qualified=False, promotion=False,
        genuinely_unseen_oos=False, independent_review="PENDING", deposit=DEPOSIT,
        leverage=LEVERAGE, source_sha=SOURCE_SHA, binary_sha=BINARY_SHA,
        parity=mode0_parity, control_parity=control_parity, baseline=refs["baseline"],
        control=control, development=None, validation=None, selection_lock=None)
    save(BASE / f"{prefix}_progress.json", progress)

    def checked(tag, enabled, **kwargs):
        result = execute(f"{prefix}_{tag}", 1, parameters(enabled),
                         tester_login=tester_login, **kwargs)
        native.verify_environment(refs["baseline"], result, evidence_base=BASE)
        return result

    dev = checked("delay_dev", True, end=native.DEV_END)
    progress["development"] = dict(result=dev, eligible=r9.operational_pass(dev))
    save(BASE / f"{prefix}_progress.json", progress)
    if not progress["development"]["eligible"]:
        progress["failure_reason"] = "Single one-bar persistence treatment failed development/capital/cost gates"
        progress["descriptive_full"] = checked("descriptive10m", True)
        progress["qualification_status"] = "FAILED"
    else:
        validation = checked("delay_val", True, start=native.DEV_END, end=native.VAL_END)
        progress["validation"] = dict(result=validation, eligible=r9.operational_pass(validation, 40))
        save(BASE / f"{prefix}_progress.json", progress)
        if not progress["validation"]["eligible"]:
            progress["failure_reason"] = "One-bar persistence treatment failed validation/capital/cost gates"
            progress["descriptive_full"] = checked("descriptive10m", True)
            progress["qualification_status"] = "FAILED"
        else:
            contract = dict(mode=1, parameters=parameters(True), deposit=DEPOSIT, leverage=LEVERAGE,
                source_sha=SOURCE_SHA, binary_sha=BINARY_SHA, reselect_after_confirmation=False)
            lock_path = BASE / f"{prefix}_selection_lock.json"
            if lock_path.exists():
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                if any(lock.get(key) != value for key, value in contract.items()):
                    raise ValueError("R11 selection lock changed")
                r9._aware_timestamp(lock.get("locked_utc"), "selection lock")
            else:
                lock = dict(**contract, locked_utc=datetime.now(timezone.utc).isoformat())
                save(lock_path, lock)
            progress["selection_lock"] = lock
            save(BASE / f"{prefix}_progress.json", progress)
            confirmation = checked("confirmation", True, start=native.VAL_END)
            r9._validate_lock_before_confirmation(lock, confirmation)
            full = checked("locked10m", True)
            delay500 = checked("delay500", True, delay=500)
            positive = sum(month["net"] > 0 for month in full["monthly"].values())
            historical = (r9.operational_pass(confirmation, 40, 1.10)
                and r9.operational_pass(full, 150, 1.15) and positive >= 7
                and full["net"] > refs["baseline"]["net"]
                and full["native_equity_dd_pct"] <= refs["baseline"]["native_equity_dd_pct"])
            economic = historical and r9.operational_pass(delay500, 150, 1.10)
            progress.update(confirmation=confirmation, full=full, delay500=delay500,
                positive_months=positive, historical_screen_passed=historical,
                economic_screen_passed=economic,
                qualification_status="AWAIT_INDEPENDENT_REVIEW" if economic else "FAILED")
    save(BASE / f"{prefix}_complete.json", progress)
    print(f"COMPLETE {prefix} qualified=False promotion=False", flush=True)
    return progress


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="r11_70_a")
    parser.add_argument("--tester-login", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    if not args.activate:
        parser.error("Review R11 source, binary, protocol and diagnostics audit before --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login)
