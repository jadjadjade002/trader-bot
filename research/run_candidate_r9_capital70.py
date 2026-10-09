"""One hold-horizon experiment, all native runs USD70 / 1:500, no deployment."""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from research import run_v25_native as native
from research.native_end_accounting import parse_verified_native_deals
from research.run_v23_tuning import save

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/v25_research_20261008_capital70"
OLD_BASE = ROOT / "reports/v25_research_20261008_postupdate"
CONTROL_SOURCE = "research/ResearchControl_R1_R8.mq5"
CONTROL_SHA = "961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B"
CONTROL_BINARY_SHA = "2F59FC1F06CDAFF468F137ACF650C4198CE4BDB68CC6962551CFEBDBC46535CE"
PARITY_SOURCE = "research/ResearchCandidate_R8.mq5"
PARITY_SHA = "03CD489C2C51BDA9F87CA88AA231FFF25206071BFFDBA73ACDDCFD1597431974"
PARITY_BINARY_SHA = "54693E177FE0FA56CBB4D436AB70796D73D364B8C0A0F32B16667A54ABF27E03"
R1_SHA = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
DEPOSIT, LEVERAGE = 70, 500


def parameters(hold):
    if type(hold) is not int or hold not in (60, 90):
        raise ValueError("R9 has only hold60 and hold90")
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpMaxHoldBars=hold)


def pinned_preflight():
    for relative, expected in (
        ("research/ResearchCandidate_R1.mq5", R1_SHA),
        (CONTROL_SOURCE, CONTROL_SHA),
        (str(Path(CONTROL_SOURCE).with_suffix(".ex5")), CONTROL_BINARY_SHA),
        (PARITY_SOURCE, PARITY_SHA),
        (str(Path(PARITY_SOURCE).with_suffix(".ex5")), PARITY_BINARY_SHA),
    ):
        if native.sha(ROOT / relative) != expected:
            raise ValueError(f"R9 pinned artifact changed: {relative}")
    # Before any new outcome, require the exact already accepted runtime/cache.
    reference = json.loads((OLD_BASE / "runs/r5_d_baseline/accepted.json").read_text())
    signature = native.verified_signature(reference["result"], OLD_BASE)
    if native.freeze(BASE) != signature["runtime"] or native.cache_manifest() != signature["tick_cache"]:
        raise ValueError("R9 runtime/cache differs from reviewed historical reference")


def validate_capital_result(result, *, production=False):
    """Recheck accepted evidence, not just a claimed result or requested deposit."""
    signature = native.verified_signature(result, BASE)
    if signature.get("deposit") != DEPOSIT or signature.get("leverage") != LEVERAGE:
        raise ValueError("R9 accepted signature does not use USD70 / 1:500")
    if signature.get("optimize") is not False or signature.get("delay_ms") not in (200, 500):
        raise ValueError("R9 accepted model/optimization/execution profile differs")
    if signature.get("production") is not production:
        raise ValueError("R9 accepted production/research profile differs")
    name = result["evidence_run"]
    directory = BASE / "runs" / name
    setting = (directory / f"{name}.set").read_text(encoding="utf-16")
    if hashlib.sha256(setting.encode("utf-16")).hexdigest() != signature["set_sha"]:
        raise ValueError("R9 actual SET differs from accepted signature")
    if production:
        expected_setting = native.settings(name, 0, {}, production=True)
    elif signature["mode"] == 0:
        if signature.get("overrides") != {}:
            raise ValueError("R9 parity settings were changed")
        expected_setting = native.settings(name, 0, {}, r2=True, r8=True)
    elif signature["mode"] == 1:
        overrides = signature.get("overrides", {})
        if overrides != parameters(overrides.get("InpMaxHoldBars")) \
                or signature.get("research_profile") != "R9_HOLD_60_90":
            raise ValueError("R9 hold treatment settings were changed")
        expected_setting = native.settings(name, 1, overrides, r2=True, control_r1=True, r9_hold=True)
    else:
        raise ValueError("R9 unsupported accepted strategy mode")
    if setting != expected_setting:
        raise ValueError("R9 actual SET does not implement the frozen strategy")
    config = configparser.ConfigParser()
    config.read(directory / f"{name}.ini", encoding="utf-16")
    if (config["Tester"].get("Deposit") != "70"
            or config["Tester"].get("Leverage") != "1:500"
            or config["Tester"].get("Model") != "4"
            or config["Tester"].get("Optimization") != "0"
            or config["Tester"].get("Symbol") != "XAUUSD"
            or config["Tester"].get("Period") != "M1"
            or config["Tester"].get("FromDate") != signature["start"]
            or config["Tester"].get("ToDate") != signature["end"]
            or config["Tester"].get("UseCloud") != "0"
            or config["Tester"].get("UseRemote") != "0"
            or config["Common"].get("Server") != "MetaQuotes-Demo"
            or config["Common"].get("Login") != str(signature["tester_connection_login"])
            or config["Tester"].get("ExecutionMode") != str(signature["delay_ms"])
            or config["Experts"].get("Enabled") != "0"
            or config["Experts"].get("AllowLiveTrading") != "0"
            or config["Experts"].get("AllowDllImport") != "0"):
        raise ValueError("R9 actual tester capital/model/isolation differs")
    report, rows = native.report_rows(directory / f"{name}.htm")
    if (report != result.get("native") or native.money(report.get("Initial Deposit", -1)) != DEPOSIT
            or report.get("Leverage") != "1:500" or report.get("History Quality") != "100% real ticks"):
        raise ValueError("R9 actual native report capital/leverage/quality differs")
    if production:
        if signature.get("production") is not True or signature["source_sha"] != native.SOURCE_HASH \
                or signature["binary_sha"] != native.BINARY_HASH:
            raise ValueError("R9 production baseline identity differs")
        return
    specs = {row["key"]: row["value"] for row in native.csv_rows(directory / f"{name}_spec.csv")}
    if native.strict_int(specs.get("leverage", -1)) != LEVERAGE:
        raise ValueError("R9 exported account leverage differs")
    source = PARITY_SOURCE if signature["mode"] == 0 else CONTROL_SOURCE
    expected = (PARITY_SHA, PARITY_BINARY_SHA) if signature["mode"] == 0 else (CONTROL_SHA, CONTROL_BINARY_SHA)
    if (signature["source_sha"], signature["binary_sha"]) != expected:
        raise ValueError("R9 accepted artifact identity differs")
    journals = "\n".join(p.read_text(encoding="utf-8") for p in sorted(directory.glob("journal_*.txt")))
    trades, cash, _ = parse_verified_native_deals(
        native.csv_rows(directory / f"{name}_deals.csv"), report, rows, specs, journals,
        end=signature["end"], deposit=DEPOSIT, candidate_source=source)
    if len(cash) != 1 or cash[0]["type"] != 2 or abs(cash[0]["net"] - DEPOSIT) > .021:
        raise ValueError("R9 has cash adjustment/redeposit")
    aggregate = native.bucket(trades)
    if (aggregate["trades"] != result["trades"] or abs(aggregate["net"] - result["net"]) > .021
            or aggregate["trades"] != int(native.money(report["Total Trades"]))
            or abs(aggregate["net"] - native.money(report["Total Net Profit"])) > .021
            or aggregate["net_profit_factor"] != result["net_profit_factor"]
            or abs(native.finite(specs["final_balance"]) - DEPOSIT - aggregate["net"]) > .021
            or result["native_stopout"] is not any(t["exit_reason"] == 6 for t in trades)):
        raise ValueError("R9 grouped economics/capital/stopout do not reconcile")


def run_native(name, mode, overrides, *, tester_login, source=None, production=False,
               start=native.START, end=native.END, delay=200):
    result = native.execute(name, mode, overrides, candidate_source=source,
        production=production, start=start, end=end, deposit=DEPOSIT, leverage=LEVERAGE,
        delay=delay, tester_login=tester_login, evidence_base=BASE,
        r9_hold=(source == CONTROL_SOURCE))
    validate_capital_result(result, production=production)
    return result


def operational_pass(result, n=150, pf=1.20):
    return (native.qualify(result, n, pf) and result.get("native_stopout") is False
            and result.get("extra_cost_stress", {}).get("0.2", -float("inf")) > 0)


def _aware_timestamp(value, label):
    if not isinstance(value, str):
        raise ValueError(f"R9 {label} timestamp missing or malformed")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"R9 {label} timestamp missing or malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"R9 {label} timestamp must be timezone-aware")
    return parsed


def _validate_lock_before_confirmation(lock, result):
    locked = _aware_timestamp(lock.get("locked_utc"), "selection lock")
    name = result.get("evidence_run")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("R9 confirmation evidence run identity is invalid")
    started_path = BASE / "runs" / name / "started.json"
    if not started_path.is_file():
        raise ValueError("R9 confirmation started.json is missing")
    try:
        started = json.loads(started_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("R9 confirmation started.json is unreadable") from exc
    started_utc = _aware_timestamp(started.get("started_utc"), "confirmation start")
    if locked >= started_utc:
        raise ValueError("R9 selection lock must predate confirmation start")


def run_all(prefix="r9_70_a", tester_login=None):
    if not isinstance(prefix, str) or not re.fullmatch(r"r9_70_[A-Za-z0-9_]+", prefix):
        raise ValueError("R9 capital70 needs a safe r9_70_ prefix")
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R9 needs an explicit positive research demo login")
    pinned_preflight()
    production = run_native(f"{prefix}_production", 0, {}, tester_login=tester_login, production=True)
    baseline = run_native(f"{prefix}_baseline", 0, {}, tester_login=tester_login, source=PARITY_SOURCE)
    parity = native.parity(production, baseline, evidence_base=BASE)
    if parity.get("passed") is not True:
        raise ValueError("R9 capital70 exact V24 parity failed")
    progress = dict(project="R9 capital70, not V25", deposit=DEPOSIT, leverage=LEVERAGE,
        tester_connection_login=tester_login, qualified=False, promotion=False,
        genuinely_unseen_oos=False, independent_review="PENDING", baseline=baseline,
        parity=parity, development={}, validation=None, selection_lock=None)
    save(BASE / f"{prefix}_progress.json", progress)

    def checked(name, hold, **kwargs):
        result = run_native(name, 1, parameters(hold), tester_login=tester_login,
                            source=CONTROL_SOURCE, **kwargs)
        native.verify_environment(baseline, result, evidence_base=BASE)
        return result

    for hold in (60, 90):
        result = checked(f"{prefix}_dev_hold{hold}", hold, end=native.DEV_END)
        progress["development"][str(hold)] = dict(result=result, eligible=operational_pass(result))
        save(BASE / f"{prefix}_progress.json", progress)
    treatment = progress["development"]["90"]
    if treatment["eligible"]:
        validation = checked(f"{prefix}_val_hold90", 90, start=native.DEV_END, end=native.VAL_END)
        progress["validation"] = dict(result=validation, eligible=operational_pass(validation, 40))
        save(BASE / f"{prefix}_progress.json", progress)
    if not treatment["eligible"] or not progress["validation"]["eligible"]:
        progress["failure_reason"] = "Hold90 failed frozen development/validation or capital/cost gates"
        progress["descriptive_matched_full"] = {
            str(hold): checked(f"{prefix}_descriptive_hold{hold}", hold) for hold in (60, 90)}
    else:
        lock_contract = dict(mode=1, parameters=parameters(90), deposit=DEPOSIT, leverage=LEVERAGE,
            source_sha=CONTROL_SHA, binary_sha=CONTROL_BINARY_SHA, reselect_after_confirmation=False)
        path = BASE / f"{prefix}_selection_lock.json"
        if path.exists():
            lock = json.loads(path.read_text(encoding="utf-8"))
            if any(lock.get(k) != value for k, value in lock_contract.items()):
                raise ValueError("R9 locked configuration changed")
            _aware_timestamp(lock.get("locked_utc"), "selection lock")
        else:
            lock = dict(**lock_contract, locked_utc=datetime.now(timezone.utc).isoformat())
            _aware_timestamp(lock.get("locked_utc"), "selection lock")
            save(path, lock)
        progress["selection_lock"] = lock
        save(BASE / f"{prefix}_progress.json", progress)
        confirmation = checked(f"{prefix}_confirmation", 90, start=native.VAL_END)
        _validate_lock_before_confirmation(lock, confirmation)
        full = checked(f"{prefix}_locked10m", 90)
        positive_months = sum(month["net"] > 0 for month in full["monthly"].values())
        historical = (operational_pass(confirmation, 40, 1.10) and operational_pass(full, 150, 1.15)
            and positive_months >= 7 and full["net"] > baseline["net"]
            and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"])
        delay = checked(f"{prefix}_delay500", 90, delay=500)
        economic = historical and operational_pass(delay, 150, 1.10)
        progress.update(confirmation=confirmation, full=full, positive_months=positive_months,
            delay500=delay, historical_screen_passed=historical, economic_screen_passed=economic,
            qualification_status="AWAIT_INDEPENDENT_REVIEW" if economic else "FAILED")
        # A mocked/claimed economic screen never bypasses independent release review.
        # This runner cannot name, compile, install or deploy a production V25.
    save(BASE / f"{prefix}_complete.json", progress)
    print(f"COMPLETE {prefix} qualified=False promotion=False", flush=True)
    return progress


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="r9_70_a")
    parser.add_argument("--tester-login", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    if not args.activate:
        parser.error("Review capital70 protocol, authenticate research lab, then use --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login)
