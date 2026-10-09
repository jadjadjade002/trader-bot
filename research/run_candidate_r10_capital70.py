"""One preregistered planned-stop risk veto, native USD70/1:500, no deployment."""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import re

from research import run_candidate_r9_capital70 as r9
from research import run_v25_native as native
from research.native_end_accounting import parse_verified_native_deals
from research.candidate_cash_risk_audit import audit_cash_risk
from research.run_v23_tuning import save

ROOT, BASE = r9.ROOT, r9.BASE
SOURCE = "research/ResearchCandidate_R10.mq5"
SOURCE_SHA = "8B1BC2B768326FCD305672BAD9B6EBB2879DFF94170C7B0F8315BF29A02C5E68"
BINARY_SHA = "4085FCE15A7E3EAD8928031BA4467C6EEA6B14CA63B60B307794A8A715BAF819"
DEPOSIT, LEVERAGE = 70, 500


def validate_risk_evidence(folder, name, *, enabled, mode):
    """Validate reporting against actual instrument specs, never infer cash PnL."""
    spec_rows = native.csv_rows(folder / f"{name}_spec.csv")
    specs = {row["key"]: row["value"] for row in spec_rows}
    if len(specs) != len(spec_rows):
        raise ValueError("R10 duplicate exported spec keys")
    required = ("point", "digits", "tick_size", "cash_risk_fraction", "cash_risk_enabled")
    if any(key not in specs for key in required):
        raise ValueError("R10 missing exported instrument/risk specs")
    digits = native.strict_int(specs["digits"])
    point, tick_size = native.finite(specs["point"]), native.finite(specs["tick_size"])
    if (not 0 <= digits <= 10 or point <= 0 or tick_size <= 0
            or abs(point - 10 ** (-digits)) > point * 1e-10
            or abs(native.finite(specs["cash_risk_fraction"]) - .025) > 1e-12):
        raise ValueError("R10 exported instrument/risk spec values differ")
    serialized = specs["cash_risk_enabled"].strip().lower()
    if serialized not in ("true", "false", "1", "0") or (serialized in ("true", "1")) is not enabled:
        raise ValueError("R10 exported risk enabled differs from requested profile")
    raw = native.csv_rows(folder / f"{name}_raw.csv")
    signals = native.csv_rows(folder / f"{name}_signals.csv")
    if any(native.strict_int(row["mode"]) != mode
            or native.strict_int(row["entry_strength"]) != (2 if mode == 1 else 0)
            for row in signals):
        raise ValueError("R10 diagnostic mode/preset differs from requested profile")
    return dict(specs={key: specs[key] for key in required},
        counts=audit_cash_risk(raw, signals, enabled=enabled,
                              point=specs["point"], tick_size=specs["tick_size"]))


def parameters(veto):
    if type(veto) is not bool:
        raise ValueError("R10 needs one explicit boolean treatment")
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpEnableCashRiskVeto=veto)


def pinned_preflight():
    r9.pinned_preflight()
    if native.sha(ROOT / SOURCE) != SOURCE_SHA or native.sha((ROOT / SOURCE).with_suffix(".ex5")) != BINARY_SHA:
        raise ValueError("R10 reviewed source/binary identity differs")
    complete = json.loads((BASE / "r9_70_a_complete.json").read_text(encoding="utf-8"))
    if complete.get("qualified") is not False or complete.get("promotion") is not False:
        raise ValueError("R10 reference is not the reviewed failed R9 batch")
    refs = {}
    for key, name in (("production", "r9_70_a_production"),
                      ("baseline", "r9_70_a_baseline"),
                      ("control", "r9_70_a_dev_hold60")):
        result = json.loads((BASE / "runs" / name / "accepted.json").read_text())["result"]
        r9.validate_capital_result(result, production=(key == "production"))
        refs[key] = result
    native.parity(refs["production"], refs["baseline"], evidence_base=BASE)
    return refs


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
        raise ValueError("R10 native signature capital/identity differs")
    mode, overrides = sig.get("mode"), sig.get("overrides")
    if not ((mode == 0 and overrides == {})
            or (mode == 1 and isinstance(overrides, dict)
                and overrides == parameters(overrides.get("InpEnableCashRiskVeto")))):
        raise ValueError("R10 treatment contract differs")
    actual = (folder / f"{name}.set").read_text(encoding="utf-16")
    if (actual != native.settings(name, mode, overrides, r2=True, r10=True)
            or hashlib.sha256(actual.encode("utf-16")).hexdigest() != sig.get("set_sha")):
        raise ValueError("R10 actual SET differs")
    ini = configparser.ConfigParser()
    ini.read(folder / f"{name}.ini", encoding="utf-16")
    expected = {"Deposit": "70", "Leverage": "1:500", "Model": "4", "Optimization": "0",
        "Symbol": "XAUUSD", "Period": "M1", "UseCloud": "0", "UseRemote": "0", "UseLocal": "1",
        "FromDate": sig["start"], "ToDate": sig["end"], "ExecutionMode": str(sig["delay_ms"]),
        "Expert": "ResearchCandidate_R10.ex5", "ExpertParameters": f"{name}.set",
        "ShutdownTerminal": "1"}
    if (any(ini["Tester"].get(k) != v for k, v in expected.items())
            or ini["Common"].get("Login") != str(sig["tester_connection_login"])
            or ini["Common"].get("Server") != "MetaQuotes-Demo"
            or any(ini["Experts"].get(k) != "0" for k in ("Enabled", "AllowLiveTrading", "AllowDllImport"))):
        raise ValueError("R10 actual INI capital/model/isolation differs")
    report, rows = native.report_rows(folder / f"{name}.htm")
    if (report != result.get("native") or report.get("Initial Deposit") != "70.00"
            or report.get("Leverage") != "1:500" or report.get("History Quality") != "100% real ticks"):
        raise ValueError("R10 actual native HTML differs")
    specs = {r["key"]: r["value"] for r in native.csv_rows(folder / f"{name}_spec.csv")}
    if native.strict_int(specs.get("leverage", -1)) != LEVERAGE:
        raise ValueError("R10 exported leverage differs")
    journal = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("journal_*.txt"))
    if ("R10_NATIVE_FIXTURE_FAIL" in journal or "R10_NATIVE_PLATFORM_PROFIT_FAIL" in journal
            or not re.search(rf"R10_NATIVE_FIXTURES_PASS checks=10 preset={overrides.get('InpEntryStrength', 0)}\b", journal)
            or "R10_NATIVE_PLATFORM_PROFIT_PASS checks=2" not in journal):
        raise ValueError("R10 actual native fixtures missing/failed")
    trades, cash, _ = parse_verified_native_deals(native.csv_rows(folder / f"{name}_deals.csv"),
        report, rows, specs, journal, end=sig["end"], deposit=DEPOSIT, candidate_source=SOURCE)
    aggregate = native.bucket(trades)
    if (len(cash) != 1 or cash[0]["net"] != DEPOSIT
            or any(aggregate.get(k) != result.get(k) for k in ("trades", "net", "net_profit_factor"))
            or abs(native.finite(specs["final_balance"]) - DEPOSIT - aggregate["net"]) > .021
            or result.get("native_stopout") is not any(t["exit_reason"] == 6 for t in trades)):
        raise ValueError("R10 actual cash/position/economics/stopout differ")
    return validate_risk_evidence(folder, name,
        enabled=bool(overrides.get("InpEnableCashRiskVeto", False)), mode=mode)


def execute(name, mode, params, *, tester_login, start=native.START, end=native.END, delay=200):
    result = native.execute(name, mode, params, candidate_source=SOURCE,
        tester_login=tester_login, evidence_base=BASE, deposit=DEPOSIT, leverage=LEVERAGE,
        start=start, end=end, delay=delay)
    risk_audit = validate_result(result)
    save(BASE / "runs" / result["evidence_run"] / "cash_risk_audit.json", risk_audit)
    return result


def run_all(prefix, tester_login):
    if not isinstance(prefix, str) or not re.fullmatch(r"r10_70_[A-Za-z0-9_]+", prefix):
        raise ValueError("R10 requires a safe capital70 prefix")
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R10 requires explicit research demo login")
    refs = pinned_preflight()
    if tester_login != native.verified_signature(refs["baseline"], BASE)["tester_connection_login"]:
        raise ValueError("R10 research connection differs from reviewed capital70 controls")
    parity = execute(f"{prefix}_parity", 0, {}, tester_login=tester_login)
    comparison = native.parity(refs["production"], parity, evidence_base=BASE)
    control = execute(f"{prefix}_control_dev", 1, parameters(False),
                      tester_login=tester_login, end=native.DEV_END)
    control_parity = native.parity(refs["control"], control, evidence_base=BASE)
    progress = dict(project="R10 cash-risk veto, not V25", qualified=False, promotion=False,
        genuinely_unseen_oos=False, independent_review="PENDING", deposit=DEPOSIT, leverage=LEVERAGE,
        source_sha=SOURCE_SHA, binary_sha=BINARY_SHA, fixed_risk_fraction=.025,
        parity=comparison, control_parity=control_parity, baseline=refs["baseline"],
        control=control, validation=None, selection_lock=None)
    save(BASE / f"{prefix}_progress.json", progress)

    def checked(tag, **kwargs):
        result = execute(f"{prefix}_{tag}", 1, parameters(True), tester_login=tester_login, **kwargs)
        native.verify_environment(refs["baseline"], result, evidence_base=BASE)
        return result

    dev = checked("veto_dev", end=native.DEV_END)
    progress["development"] = dict(result=dev, eligible=r9.operational_pass(dev))
    save(BASE / f"{prefix}_progress.json", progress)
    if progress["development"]["eligible"]:
        val = checked("veto_val", start=native.DEV_END, end=native.VAL_END)
        progress["validation"] = dict(result=val, eligible=r9.operational_pass(val, 40))
        save(BASE / f"{prefix}_progress.json", progress)
    if not progress["development"]["eligible"] or not progress["validation"]["eligible"]:
        progress["failure_reason"] = "Single cash-risk veto failed frozen development/validation gate"
        progress["descriptive_full"] = checked("descriptive10m")
        progress["qualification_status"] = "FAILED"
    else:
        contract = dict(mode=1, parameters=parameters(True), deposit=DEPOSIT, leverage=LEVERAGE,
            source_sha=SOURCE_SHA, binary_sha=BINARY_SHA, fixed_risk_fraction=.025,
            reselect_after_confirmation=False)
        path = BASE / f"{prefix}_selection_lock.json"
        if path.exists():
            lock = json.loads(path.read_text())
            if any(lock.get(k) != v for k, v in contract.items()):
                raise ValueError("R10 selection lock changed")
            r9._aware_timestamp(lock.get("locked_utc"), "selection lock")
        else:
            lock = dict(**contract, locked_utc=datetime.now(timezone.utc).isoformat())
            save(path, lock)
        progress["selection_lock"] = lock
        save(BASE / f"{prefix}_progress.json", progress)
        confirmation = checked("confirmation", start=native.VAL_END)
        r9._validate_lock_before_confirmation(lock, confirmation)
        full = checked("locked10m")
        delay = checked("delay500", delay=500)
        positive = sum(row["net"] > 0 for row in full["monthly"].values())
        historical = (r9.operational_pass(confirmation, 40, 1.10)
            and r9.operational_pass(full, 150, 1.15) and positive >= 7
            and full["net"] > refs["baseline"]["net"]
            and full["native_equity_dd_pct"] <= refs["baseline"]["native_equity_dd_pct"])
        economic = historical and r9.operational_pass(delay, 150, 1.10)
        progress.update(confirmation=confirmation, full=full, delay500=delay,
            positive_months=positive, historical_screen_passed=historical,
            economic_screen_passed=economic,
            qualification_status="AWAIT_INDEPENDENT_REVIEW" if economic else "FAILED")
    save(BASE / f"{prefix}_complete.json", progress)
    print(f"COMPLETE {prefix} qualified=False promotion=False", flush=True)
    return progress


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prefix", default="r10_70_a")
    p.add_argument("--tester-login", type=int, required=True)
    p.add_argument("--activate", action="store_true")
    args = p.parse_args()
    if not args.activate:
        p.error("Review source, binary, protocol and offline tests before --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login)
