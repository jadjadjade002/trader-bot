"""One preregistered closed-breakout/structural-risk policy, USD70/1:500, no release."""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import importlib
import json
import re

from research import run_candidate_r9_capital70 as r9
from research import run_candidate_r10_capital70 as r10
from research import run_candidate_r11_capital70 as r11
from research import run_v25_native as native
from research.analyze_v23_backtest import timestamp
from research.native_end_accounting import parse_verified_native_deals
from research.run_v23_tuning import save

ROOT, BASE = r9.ROOT, r9.BASE
SOURCE = "research/ResearchCandidate_R12.mq5"
# Root pins source, binary and fixture count only after independent source review/compile.
SOURCE_SHA = "REVIEW_REQUIRED"
BINARY_SHA = "UNCOMPILED"
NATIVE_FIXTURE_COUNT = None
DEPOSIT, LEVERAGE = 70, 500


def parameters(enabled):
    if type(enabled) is not bool:
        raise ValueError("R12 requires one explicit boolean structural-policy treatment")
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpStructuralRetest=enabled)


def pinned_preflight():
    r9.pinned_preflight()
    if (SOURCE_SHA == "REVIEW_REQUIRED" or BINARY_SHA in ("UNCOMPILED", "REVIEW_REQUIRED")
            or type(NATIVE_FIXTURE_COUNT) is not int or NATIVE_FIXTURE_COUNT <= 0):
        raise ValueError("R12 reviewed source/binary/fixture pins are not finalized")
    if (native.sha(ROOT / SOURCE) != SOURCE_SHA
            or native.sha((ROOT / SOURCE).with_suffix(".ex5")) != BINARY_SHA):
        raise ValueError("R12 reviewed source/binary identity differs")
    refs = r10.pinned_preflight()
    r11.pinned_preflight()
    r11_complete = json.loads((BASE / "r11_70_a_complete.json").read_text(encoding="utf-8"))
    if (r11_complete.get("qualified") is not False or r11_complete.get("promotion") is not False
            or r11_complete.get("qualification_status") != "FAILED"):
        raise ValueError("R12 requires the reconciled failed R11 reference batch")
    complete = json.loads((BASE / "r10_70_a_complete.json").read_text(encoding="utf-8"))
    if (complete.get("qualified") is not False or complete.get("promotion") is not False
            or complete.get("qualification_status") != "FAILED"):
        raise ValueError("R12 requires the completed failed R10 reference batch")
    return refs


def validate_structural_evidence(folder, name, *, result, enabled, mode):
    """Reconstruct exported structural decisions before accepting native results."""
    if type(enabled) is not bool or type(mode) is not int or mode not in (0, 1):
        raise ValueError("R12 structural audit needs exact mode and treatment flag")
    spec_rows = native.csv_rows(folder / f"{name}_spec.csv")
    specs = {row["key"]: row["value"] for row in spec_rows}
    if len(specs) != len(spec_rows):
        raise ValueError("R12 duplicate exported specification keys")
    required = ("point", "digits", "tick_size", "chart_mode", "chart_mode_valid", "leverage",
                "structural_retest_enabled", "cash_risk_fraction", "stops_level", "freeze_level")
    if any(key not in specs for key in required):
        raise ValueError("R12 missing required symbol/policy specifications")
    digits = native.strict_int(specs["digits"], high=10)
    point, tick = native.finite(specs["point"]), native.finite(specs["tick_size"])
    structural_token = specs["structural_retest_enabled"].strip().lower()
    chart_valid = specs["chart_mode_valid"].strip().lower()
    stop_level = native.strict_int(specs["stops_level"])
    freeze_level = native.strict_int(specs["freeze_level"])
    if (point <= 0 or tick <= 0 or abs(point - 10 ** (-digits)) > point * 1e-10
            or native.strict_int(specs["leverage"]) != LEVERAGE
            or native.strict_int(specs["chart_mode"]) != 0
            or chart_valid not in ("true", "1")
            or structural_token not in ("true", "false", "1", "0")
            or (structural_token in ("true", "1")) is not enabled
            or abs(native.finite(specs["cash_risk_fraction"]) - .025) > 1e-12
            or stop_level < 0 or freeze_level < 0):
        raise ValueError("R12 exported symbol/leverage/chart mode differs")
    if NATIVE_FIXTURE_COUNT is None:
        raise ValueError("R12 native fixture count is not pinned")
    journal = "\n".join(path.read_text(encoding="utf-8")
                         for path in sorted(folder.glob("journal_*.txt")))
    if ("R12_NATIVE_FIXTURE_FAIL" in journal
            or "R12_NATIVE_PLATFORM_PROFIT_FAIL" in journal
            or not re.search(rf"R12_NATIVE_FIXTURES_PASS checks={NATIVE_FIXTURE_COUNT} preset={0 if mode == 0 else 2}\b", journal)
            or "R12_NATIVE_PLATFORM_PROFIT_PASS checks=2" not in journal):
        raise ValueError("R12 actual native fixtures missing/failed")
    try:
        auditor = importlib.import_module("research.candidate_structural_audit")
        audit = auditor.audit_structural(
            native.csv_rows(folder / f"{name}_raw.csv"),
            native.csv_rows(folder / f"{name}_signals.csv"),
            enabled=enabled, mode=mode, point=specs["point"],
            tick_size=specs["tick_size"], digits=digits)
    except (ImportError, AttributeError) as exc:
        raise ValueError("R12 structural row auditor is unavailable") from exc
    if not isinstance(audit, dict):
        raise ValueError("R12 structural auditor returned invalid counts")
    if audit.get("successful_fills") != result.get("trades"):
        raise ValueError("R12 audited successful fills differ from verified native positions")
    return dict(specs={key: specs[key] for key in required}, audit=audit)


def verify_native_entry_links(raw_rows, signal_rows, deal_rows, journal):
    """Require one exact raw order/deal ID pair for every native opening deal."""
    raw_by_key = {}
    signal_by_key = {}
    for row in raw_rows:
        key = (row.get("bar"), native.strict_int(row.get("tick_msc"), low=1))
        if key in raw_by_key:
            raise ValueError("R12 duplicate raw event key")
        raw_by_key[key] = row
    for row in signal_rows:
        key = (row.get("bar"), native.strict_int(row.get("tick_msc"), low=1))
        if key in signal_by_key:
            raise ValueError("R12 duplicate signal event key")
        signal_by_key[key] = row
    if raw_by_key.keys() != signal_by_key.keys():
        raise ValueError("R12 raw/signal event keys differ during native-entry reconciliation")

    successes = {}
    for key, raw in raw_by_key.items():
        if raw.get("order_attempt", "").strip().lower() not in ("true", "1"):
            continue
        retcode = native.strict_int(raw.get("retcode"), low=0)
        if retcode not in (10009, 10010):
            continue
        order = native.strict_int(raw.get("order_ticket"), low=1)
        deal = native.strict_int(raw.get("deal_ticket"), low=1)
        if deal in successes:
            raise ValueError("R12 successful attempts reuse a native deal ticket")
        successes[deal] = (order, key, signal_by_key[key])

    entries = [row for row in deal_rows
               if native.strict_int(row.get("type"), low=0) in (0, 1)
               and native.strict_int(row.get("entry"), low=0) == 0]
    by_ticket = {}
    for row in entries:
        ticket = native.strict_int(row.get("ticket"), low=1)
        if ticket in by_ticket:
            raise ValueError("R12 duplicate native opening deal ticket")
        by_ticket[ticket] = row
    if set(successes) != set(by_ticket):
        raise ValueError("R12 raw successful deals do not exactly match native opening deals")

    linked = []
    for ticket, (order, key, signal) in successes.items():
        deal = by_ticket[ticket]
        side = native.strict_int(signal.get("signal"), low=-1, high=1)
        deal_side = native.strict_int(deal.get("type"), low=0, high=1)
        if (side not in (-1, 1) or deal_side != (0 if side == 1 else 1)
                or native.strict_int(deal.get("magic")) != 992300
                or deal.get("symbol") != "XAUUSD"
                or native.strict_int(deal.get("time_msc"), low=1)
                   < native.strict_int(raw_by_key[key].get("tick_msc"), low=1)
                or abs(native.finite(deal.get("volume")) - .01) > 1e-10):
            raise ValueError("R12 native opening deal owner/side/volume differs from raw signal")
        # MT5 journal records the deal's actual order association. Duplicate
        # journal copies are tolerated only when every matching record agrees.
        pattern = (r"deal #" + str(ticket) + r" (buy|sell) ([\d.]+) XAUUSD at ([\d.]+) done \(based on order #(\d+)\)")
        matches = re.findall(pattern, journal)
        expected_side = "buy" if side == 1 else "sell"
        if (not matches or any(m[0] != expected_side or m[3] != str(order)
                               or abs(native.finite(m[1]) - .01) > 1e-10
                               or abs(native.finite(m[2]) - native.finite(deal["price"])) > 1e-8
                               for m in matches)):
            raise ValueError("R12 native entry deal/order journal link differs")
        deal_events = []
        lines = journal.splitlines()
        for index, line in enumerate(lines):
            event = re.search(r"(20\d\d\.\d\d\.\d\d \d\d:\d\d:\d\d)\s+(.*)", line)
            if event and re.search(rf"\bdeal #{ticket}\b", event.group(2)):
                expected_clock = timestamp(native.strict_int(deal.get("time_msc"), low=1)).strftime(
                    "%Y.%m.%d %H:%M:%S")
                if event.group(1) != expected_clock:
                    raise ValueError("R12 native entry deal timestamp differs from ledger")
                deal_events.append((index, event.group(1)))
        request_pattern = re.compile(
            r"market (buy|sell) ([\d.]+) XAUUSD sl: ([\d.]+) tp: ([\d.]+) "
            r"\(([\d.]+) / ([\d.]+)\)")
        request_evidence = []
        if not deal_events:
            raise ValueError("R12 native entry deal timestamp missing from journal")
        for index, clock in deal_events:
            if index <= 0:
                raise ValueError("R12 native deal has no immediately preceding request record")
            prior_event = re.search(r"(20\d\d\.\d\d\.\d\d \d\d:\d\d:\d\d)\s+(.*)",
                                    lines[index - 1])
            request = (request_pattern.search(prior_event.group(2))
                       if prior_event and prior_event.group(1) == clock else None)
            if request is None:
                raise ValueError("R12 accepted entry lacks immediately adjacent same-time market request")
            if request.group(1) != expected_side or abs(native.finite(request.group(2)) - .01) > 1e-10:
                raise ValueError("R12 native market request side/volume differs")
            if _bool_text(signal.get("structural_enabled")):
                point = native.finite(signal.get("point"))
                for group, field in ((3, "structural_sl"), (4, "structural_tp")):
                    if abs(native.finite(request.group(group)) - native.finite(signal.get(field))) > point * .51:
                        raise ValueError("R12 native order SL/TP differs from audited structural geometry")
            request_evidence.append(dict(time=clock, bid=native.finite(request.group(5)),
                ask=native.finite(request.group(6)), sl=native.finite(request.group(3)),
                tp=native.finite(request.group(4))))
        linked.append(dict(raw_order_ticket=order, raw_deal_ticket=ticket,
                           native_position=native.strict_int(deal.get("position"), low=1),
                           side=expected_side, volume=native.finite(deal["volume"]),
                           native_request=request_evidence[0]))
    return dict(successful_raw_attempts=len(successes), native_opening_deals=len(entries),
                one_to_one_ticket_join=True, linked_entries=linked)


def _bool_text(value):
    token = str(value).strip().lower()
    if token in ("true", "1"):
        return True
    if token in ("false", "0"):
        return False
    raise ValueError("R12 structural enabled telemetry is not a boolean")


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
        raise ValueError("R12 native signature capital/identity differs")
    mode, overrides = sig.get("mode"), sig.get("overrides")
    if not ((mode == 0 and overrides == {})
            or (mode == 1 and isinstance(overrides, dict)
                and type(overrides.get("InpStructuralRetest")) is bool
                and overrides in (parameters(False), parameters(True)))):
        raise ValueError("R12 frozen treatment contract differs")
    enabled = bool(overrides.get("InpStructuralRetest", False))
    actual_set = (folder / f"{name}.set").read_text(encoding="utf-16")
    if (actual_set != native.settings(name, mode, overrides, r2=True, r12=True)
            or hashlib.sha256(actual_set.encode("utf-16")).hexdigest() != sig.get("set_sha")):
        raise ValueError("R12 actual SET differs")
    ini = configparser.ConfigParser()
    ini.read(folder / f"{name}.ini", encoding="utf-16")
    expected = {"Deposit": "70", "Leverage": "1:500", "Model": "4", "Optimization": "0",
        "Symbol": "XAUUSD", "Period": "M1", "UseCloud": "0", "UseRemote": "0", "UseLocal": "1",
        "FromDate": sig["start"], "ToDate": sig["end"], "ExecutionMode": str(sig["delay_ms"]),
        "Expert": "ResearchCandidate_R12.ex5", "ExpertParameters": f"{name}.set",
        "ShutdownTerminal": "1"}
    if (any(ini["Tester"].get(k) != v for k, v in expected.items())
            or ini["Common"].get("Login") != str(sig["tester_connection_login"])
            or ini["Common"].get("Server") != "MetaQuotes-Demo"
            or any(ini["Experts"].get(k) != "0" for k in ("Enabled", "AllowLiveTrading", "AllowDllImport"))):
        raise ValueError("R12 actual INI capital/model/isolation differs")
    report, report_rows = native.report_rows(folder / f"{name}.htm")
    if (report != result.get("native") or report.get("Initial Deposit") != "70.00"
            or report.get("Leverage") != "1:500" or report.get("History Quality") != "100% real ticks"):
        raise ValueError("R12 actual native HTML capital/quality differs")
    specs_rows = native.csv_rows(folder / f"{name}_spec.csv")
    specs = {row["key"]: row["value"] for row in specs_rows}
    journal = "\n".join(path.read_text(encoding="utf-8")
                         for path in sorted(folder.glob("journal_*.txt")))
    deal_rows = native.csv_rows(folder / f"{name}_deals.csv")
    trades, cash, _ = parse_verified_native_deals(
        deal_rows, report, report_rows,
        specs, journal, end=sig["end"], deposit=DEPOSIT, candidate_source=SOURCE)
    aggregate = native.bucket(trades)
    if (len(cash) != 1 or cash[0]["net"] != DEPOSIT
            or any(aggregate.get(k) != result.get(k) for k in ("trades", "net", "net_profit_factor"))
            or abs(native.finite(specs["final_balance"]) - DEPOSIT - aggregate["net"]) > .021
            or result.get("native_stopout") is not any(t["exit_reason"] == 6 for t in trades)):
        raise ValueError("R12 deals/cash/net/fees/stopout do not reconcile")
    evidence = validate_structural_evidence(folder, name, result=result, enabled=enabled, mode=mode)
    raw_rows = native.csv_rows(folder / f"{name}_raw.csv")
    signal_rows = native.csv_rows(folder / f"{name}_signals.csv")
    evidence["native_entry_links"] = verify_native_entry_links(
        raw_rows, signal_rows, deal_rows, journal)
    return evidence


def execute(name, mode, overrides, *, tester_login, start=native.START, end=native.END, delay=200):
    result = native.execute(name, mode, overrides, candidate_source=SOURCE,
        tester_login=tester_login, evidence_base=BASE, deposit=DEPOSIT, leverage=LEVERAGE,
        start=start, end=end, delay=delay)
    audit = validate_result(result)
    save(BASE / "runs" / result["evidence_run"] / "structural_audit.json", audit)
    return result


def run_all(prefix, tester_login):
    if not isinstance(prefix, str) or not re.fullmatch(r"r12_70_[A-Za-z0-9_]+", prefix):
        raise ValueError("R12 requires a safe capital70 prefix")
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R12 requires explicit research demo login")
    refs = pinned_preflight()
    if tester_login != native.verified_signature(refs["baseline"], BASE)["tester_connection_login"]:
        raise ValueError("R12 research connection differs from reviewed capital70 controls")

    parity = execute(f"{prefix}_parity", 0, {}, tester_login=tester_login)
    parity_check = native.parity(refs["production"], parity, evidence_base=BASE)
    if parity_check.get("passed") is not True:
        raise ValueError("R12 exact V24 parity failed")
    control = execute(f"{prefix}_control_dev", 1, parameters(False),
                      tester_login=tester_login, end=native.DEV_END)
    control_check = native.parity(refs["control"], control, evidence_base=BASE)
    if control_check.get("passed") is not True:
        raise ValueError("R12 structural-off R9 hold60 control parity failed")

    progress = dict(project="R12 structural retest policy, not V25", qualified=False, promotion=False,
        genuinely_unseen_oos=False, independent_review="PENDING", deposit=DEPOSIT,
        leverage=LEVERAGE, source_sha=SOURCE_SHA, binary_sha=BINARY_SHA,
        parity=parity_check, control_parity=control_check, baseline=refs["baseline"],
        control=control, development=None, validation=None, selection_lock=None)
    save(BASE / f"{prefix}_progress.json", progress)

    def checked(tag, enabled, **kwargs):
        result = execute(f"{prefix}_{tag}", 1, parameters(enabled),
                         tester_login=tester_login, **kwargs)
        native.verify_environment(refs["baseline"], result, evidence_base=BASE)
        return result

    dev = checked("structural_dev", True, end=native.DEV_END)
    progress["development"] = dict(result=dev, eligible=r9.operational_pass(dev))
    save(BASE / f"{prefix}_progress.json", progress)
    if not progress["development"]["eligible"]:
        progress["failure_reason"] = "Single R12 policy failed development/capital/cost gates"
        progress["descriptive_full"] = checked("descriptive10m", True)
        progress["qualification_status"] = "FAILED"
    else:
        validation = checked("structural_val", True,
                             start=native.DEV_END, end=native.VAL_END)
        progress["validation"] = dict(result=validation, eligible=r9.operational_pass(validation, 40))
        save(BASE / f"{prefix}_progress.json", progress)
        if not progress["validation"]["eligible"]:
            progress["failure_reason"] = "R12 policy failed validation/capital/cost gates"
            progress["descriptive_full"] = checked("descriptive10m", True)
            progress["qualification_status"] = "FAILED"
        else:
            contract = dict(mode=1, parameters=parameters(True), deposit=DEPOSIT, leverage=LEVERAGE,
                source_sha=SOURCE_SHA, binary_sha=BINARY_SHA, reselect_after_confirmation=False)
            lock_path = BASE / f"{prefix}_selection_lock.json"
            if lock_path.exists():
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                if any(lock.get(k) != v for k, v in contract.items()):
                    raise ValueError("R12 selection lock changed")
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
    parser.add_argument("--prefix", default="r12_70_a")
    parser.add_argument("--tester-login", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    if not args.activate:
        parser.error("Review R12 source, binary, protocol and diagnostics auditor before --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login)
