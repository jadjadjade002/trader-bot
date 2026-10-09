"""Read-only, fail-closed attribution for the fixed R7 accepted native batch."""
from __future__ import annotations
import argparse, hashlib, json, math, re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from research.analyze_v23_backtest import bucket, csv_rows, finite, parse_deals, report_rows
from research import run_v25_native as native
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/v25_research_20261008_postupdate"
COMPLETE = "r7_a_complete.json"
SOURCE = ROOT / "research/ResearchCandidate_R7.mq5"
BINARY = ROOT / "research/ResearchCandidate_R7.ex5"
SOURCE_SHA = "1EEED145819D57B6F4D85CE1D13A7AF4DF5DC3E0FCBEB885EDE2B624DED2B38C"
BINARY_SHA = "CCAA1D266B2306348CAFE40FCDA12209DA812CADD8EE170F5359AE8D9A4E778E"
START, DEV_END, END = "2025.12.01", "2026.06.01", "2026.10.01"
FIXED = {
    "InpEnableSessionGuard": "false", "InpEnableSpreadGuard": "false",
    "InpEnableMarginGuard": "true", "InpEnableHardSL": "true",
    "InpMaxHoldBars": "60", "InpDonchianPeriod": "20", "InpATRPeriod": "14",
    "InpMinSLPoints": "150", "InpLotSize": "0.01", "InpFadeBreakouts": "false",
    "InpMagicNumber": "992300", "InpTargetAccount": "0",
    "InpEnableCircuitBreaker": "true", "InpMaxConsecutiveLosses": "4",
    "InpCooldownMinutes": "90",
}
def need(ok: bool, message: str) -> None:
    if not ok: raise ValueError(message)
def number(value: Any, label: str) -> float:
    if value is None or str(value).strip() == "": raise ValueError(f"Missing number: {label}")
    value = finite(value)
    if not math.isfinite(value): raise ValueError(f"Nonfinite number: {label}")
    return value
def integer(value: Any, label: str) -> int:
    try:
        n = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc: raise ValueError(f"Invalid integer: {label}") from exc
    if not n.is_finite() or n != n.to_integral_value(): raise ValueError(f"Noninteger: {label}")
    return int(n)
def event_key(row: dict[str, Any]) -> tuple[str, int]:
    bar, tick = str(row.get("bar", "")).strip(), integer(row.get("tick_msc"), "event tick_msc")
    try:
        bar_ms = int(datetime.strptime(bar, "%Y.%m.%d %H:%M:%S")
                     .replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError as exc:
        raise ValueError(f"Bad MQL event bar: {bar!r}") from exc
    if not bar_ms <= tick < bar_ms + 60000: raise ValueError(f"Event tick is outside logged M1 bar: {bar!r}:{tick}")
    return bar, tick
def entry_key(trade: dict[str, Any]) -> tuple[int, str, str, str]:
    def d(x: Any) -> str:
        value = Decimal(str(x))
        if not value.is_finite():
            raise ValueError("Nonfinite canonical entry value")
        return format(value.normalize(), "f")
    return int(trade["open_msc"]), trade["direction"], d(trade["entry_price"]), d(trade["volume"])
def _check_artifacts() -> None:
    for path, expected in ((SOURCE, SOURCE_SHA), (BINARY, BINARY_SHA)):
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest().upper() != expected: raise ValueError(f"Current R7 artifact SHA mismatch: {path.name}")

def _reference(name: str, *, production: bool, preset: int = 0) -> dict[str, Any]:
    """Recheck actual fixed reference artifacts, never trust a manifest pass flag."""
    accepted = json.loads((BASE / "runs" / name / "accepted.json").read_text(encoding="utf-8-sig"))
    result = accepted["result"]
    signature = native.verified_signature(result, BASE)
    source = ROOT / ("AegisPredator_v24.mq5" if production else "research/ResearchCandidate_R4.mq5")
    overrides = {} if production else dict(InpEntryStrength=preset, InpStopLossATRMul=1.5,
                                           InpTakeProfitRRMul=1.0)
    for key, value in dict(start=START, end=END if production else DEV_END, mode=0 if production else 5,
        overrides=overrides, deposit=10000, optimize=False, production=production, delay_ms=200,
        source_sha=hashlib.sha256(source.read_bytes()).hexdigest().upper(),
        binary_sha=hashlib.sha256(source.with_suffix(".ex5").read_bytes()).hexdigest().upper()).items():
        need(signature.get(key) == value, f"Reference control signature mismatch: {name}:{key}")
    set_text = (BASE / "runs" / name / f"{name}.set").read_text(encoding="utf-16")
    # Native signature hashes serialized UTF16 settings with LF, while Windows
    # write_text may store CRLF. Validate the identical normalized logical text.
    need(hashlib.sha256(set_text.encode("utf-16")).hexdigest() == signature["set_sha"], f"Reference SET hash mismatch: {name}")
    need(set_text == native.settings(name, signature["mode"], overrides,
        production=production, r2=not production), f"Reference SET contract mismatch: {name}")
    html, _ = report_rows(BASE / "runs" / name / f"{name}.htm")
    need(html == result["native"], f"Reference HTML differs from accepted record: {name}")
    need(html.get("History Quality") == "100% real ticks" and result.get("cache_hashes_verified") is True,
         f"Reference native quality mismatch: {name}")
    return result
def _set_values(run_dir: Path, name: str, signature: dict[str, Any], mode: int,
                preset: int, tp: float | None, overrides: dict[str, Any]) -> None:
    path = run_dir / f"{name}.set"
    if not path.is_file(): raise ValueError(f"Missing accepted SET: {name}")
    text = path.read_text(encoding="utf-16")
    if hashlib.sha256(text.encode("utf-16")).hexdigest().lower() != str(signature.get("set_sha", "")).lower():
        raise ValueError(f"SET hash mismatch: {name}")
    if text != native.settings(name, mode, overrides, r2=True, r7=True):
        raise ValueError(f"SET differs from native.settings R2/R7 contract: {name}")
    values = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError(f"Malformed SET: {name}")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"Duplicate SET key: {name}:{key}")
        values[key] = value
    expected = dict(FIXED, InpRunTag=name, InpExperimentMode=str(mode), InpEntryStrength=str(preset))
    if mode == 5:
        expected.update(InpStopLossATRMul="1.5", InpTakeProfitRRMul=str(tp))
    for key, value in expected.items():
        if values.get(key) != value:
            raise ValueError(f"SET input mismatch {name}:{key}")
def _expect_sig(result: dict[str, Any], name: str, mode: int, overrides: dict[str, Any],
                end: str, reference: dict[str, Any]) -> dict[str, Any]:
    need(result.get("evidence_run") == name, f"Wrong result run id: {name}")
    sig = native.verified_signature(result, BASE)
    expected = dict(start=START, end=end, mode=mode, overrides=overrides, deposit=10000,
                    optimize=False, production=False, delay_ms=200,
                    source_sha=SOURCE_SHA, binary_sha=BINARY_SHA)
    for key, value in expected.items():
        need(sig.get(key) == value, f"Accepted signature drift {name}:{key}")
    ticks = sig.get("tick_cache")
    need(isinstance(ticks, list) and [r.get("month") for r in ticks] == native.months(START, end),
         f"Tick-cache coverage mismatch: {name}")
    ref = {row["month"]: row for row in reference["tick_cache"]}
    need(all(ref.get(row["month"]) == row for row in ticks), f"Cache differs from R7 mode0: {name}")
    need(sig.get("runtime") == reference.get("runtime"), f"Runtime differs from R7 mode0: {name}")
    _set_values(BASE / "runs" / name, name, sig, mode, overrides.get("InpEntryStrength", 0),
                overrides.get("InpTakeProfitRRMul"), overrides)
    return sig
def _load_run(result: dict[str, Any], name: str, mode: int, preset: int,
              tp: float | None, baseline_sig: dict[str, Any], *, details: bool,
              end: str | None = None) -> dict[str, Any]:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Unsafe evidence run identity")
    run_dir = BASE / "runs" / name
    accepted_path = run_dir / "accepted.json"
    if not accepted_path.is_file(): raise ValueError(f"Run not accepted: {name}")
    accepted = json.loads(accepted_path.read_text(encoding="utf-8-sig"))
    need(isinstance(accepted.get("signature"), dict) and isinstance(accepted.get("result"), dict),
         f"Malformed accepted record: {name}")
    signature = accepted["signature"]
    overrides = {} if mode == 0 else dict(InpEntryStrength=preset, InpStopLossATRMul=1.5, InpTakeProfitRRMul=tp)
    _expect_sig(result, name, mode, overrides, end or (END if mode == 0 else DEV_END), baseline_sig)
    need(accepted["result"].get("evidence_run") == name
         and accepted["result"].get("native_mql_fixture_checks") == 31
         and accepted["result"].get("cache_hashes_verified") is True
         and accepted["result"].get("terminal_cache_read_warnings") == [],
         f"Accepted result marker mismatch: {name}")
    need(accepted["result"] == result, f"Progress/accepted result differs: {name}")
    metrics = result.get("native")
    need(isinstance(metrics, dict) and metrics.get("History Quality") == "100% real ticks",
         f"No full real-tick result: {name}")
    html, _ = report_rows(run_dir / f"{name}.htm")
    need(html == metrics, f"Accepted native result differs from HTML: {name}")
    deal_rows = csv_rows(run_dir / f"{name}_deals.csv")
    trades, cash = parse_deals(deal_rows)
    summary = bucket(trades)
    need(len(cash) == 1 and cash[0]["type"] == 2 and abs(cash[0]["net"] - 10000) <= .021,
         f"Cash/deposit mismatch: {name}")
    need(summary["trades"] == int(number(metrics.get("Total Trades"), "native trades"))
         and abs(summary["net"] - number(metrics.get("Total Net Profit"), "native net")) <= .021,
         f"Native/deal ledger mismatch: {name}")
    need(summary["trades"] == result.get("trades") and abs(summary["net"] - number(result.get("net"), "accepted net")) <= .021,
         f"Accepted summary/deal ledger mismatch: {name}")
    specs = {r["key"]: r["value"] for r in csv_rows(run_dir / f"{name}_spec.csv")}
    need(specs.get("history_export_ok") in ("true", "1"), f"History export failed: {name}")
    final_balance = number(specs.get("final_balance"), "final balance")
    need(abs(final_balance - 10000 - summary["net"]) <= .021, f"Final balance mismatch: {name}")
    need(abs(final_balance - number(result.get("final_balance"), "accepted final balance")) <= .021,
         f"Accepted final balance mismatch: {name}")
    run = dict(name=name, trades=trades, summary=summary, cash=cash, final_balance=final_balance,
               signature=signature, result=result)
    if details:
        run["trades"] = _link_events(run_dir, name, preset, trades, deal_rows)
    return run
def _link_events(run_dir: Path, name: str, preset: int, trades: list[dict[str, Any]],
                 deals: list[dict[str, str]]) -> list[dict[str, Any]]:
    signals, raw = csv_rows(run_dir / f"{name}_signals.csv"), csv_rows(run_dir / f"{name}_raw.csv")
    if not signals or not raw:
        raise ValueError(f"Missing signal/raw exports: {name}")
    sig_by, raw_by = {}, {}
    for i, row in enumerate(signals, 1):
        key = event_key(row)
        if key in sig_by:
            raise ValueError(f"Duplicate signal event: {name}:{key}")
        if integer(row.get("mode"), "signal mode") != 5 or integer(row.get("entry_strength"), "preset") != preset:
            raise ValueError(f"Signal config mismatch: {name}:{i}")
        side = integer(row.get("signal"), "signal side")
        attempt = str(row.get("order_attempt", "")).lower()
        if side not in (-1, 0, 1) or attempt not in ("true", "false"):
            raise ValueError(f"Bad signal side/attempt: {name}:{i}")
        sig_by[key] = dict(row, _side=side, _attempt=attempt == "true")
    for i, row in enumerate(raw, 1):
        key = event_key(row)
        if key in raw_by:
            raise ValueError(f"Duplicate raw event: {name}:{key}")
        side, attempt = integer(row.get("original"), "raw side"), str(row.get("order_attempt", "")).lower()
        ticket = integer(row.get("deal_ticket"), "raw deal ticket")
        order_ticket = integer(row.get("order_ticket"), "raw order ticket")
        retcode = integer(row.get("retcode"), "raw retcode")
        if side not in (-1, 0, 1) or attempt not in ("true", "false") or min(ticket, order_ticket, retcode) < 0:
            raise ValueError(f"Bad raw side/attempt/ticket: {name}:{i}")
        if (attempt == "true") != (row.get("gate") == "order_attempt"):
            raise ValueError(f"Raw attempt/gate mismatch: {name}:{i}")
        if attempt == "false" and (ticket or order_ticket or retcode):
            raise ValueError(f"Deal ticket without order attempt: {name}:{i}")
        raw_by[key] = dict(row, _side=side, _attempt=attempt == "true",
                           _deal_ticket=ticket, _order_ticket=order_ticket, _retcode=retcode)
    if set(sig_by) != set(raw_by):
        raise ValueError(f"Signal/raw event-key sets differ: {name}")
    for key, sig in sig_by.items():
        event = raw_by[key]
        if (sig["_side"] != event["_side"] or sig["_attempt"] != event["_attempt"]
                or sig.get("execution_gate") != event.get("gate")):
            raise ValueError(f"Signal/raw identity mismatch: {name}:{key}")
    openings = {}
    for row in deals:
        if integer(row["type"], "deal type") in (0, 1) and integer(row["entry"], "deal entry") == 0:
            ticket = integer(row["ticket"], "opening ticket")
            if ticket <= 0 or ticket in openings:
                raise ValueError(f"Duplicate/invalid opening ticket: {name}:{ticket}")
            openings[ticket] = row
    by_ticket = {}
    for key, event in raw_by.items():
        ticket = event["_deal_ticket"]
        if ticket:
            if not event["_attempt"] or ticket not in openings or ticket in by_ticket:
                raise ValueError(f"Unmatched/duplicate ResultDeal ticket: {name}:{ticket}")
            by_ticket[ticket] = (key, event)
    attributed, used = [], set()
    for trade in trades:
        opens = [d for d in trade["deals"] if d["entry"] == 0]
        if len(opens) != 1:
            raise ValueError(f"Ambiguous opening deals: {name}:{trade['position']}")
        deal = opens[0]
        ticket = deal["ticket"]
        if abs(number(deal["volume"], "entry volume") - .01) > 1e-8 or abs(deal["volume"] - trade["volume"]) > 1e-8:
            raise ValueError(f"Entry volume outside fixed 0.01 contract: {name}:{trade['position']}")
        expected_side = 1 if trade["direction"] == "buy" else -1
        if deal["type"] != (0 if expected_side == 1 else 1) or deal["position"] != trade["position"]:
            raise ValueError(f"Opening side/position mismatch: {name}:{trade['position']}")
        if ticket not in by_ticket or ticket in used:
            raise ValueError(f"Opening lacks unique raw ResultDeal event: {name}:{ticket}")
        key, event = by_ticket[ticket]
        signal = sig_by[key]
        if (not event["_attempt"] or event["_side"] != expected_side or signal["_side"] != expected_side
                or key[1] > deal["time_msc"]):
            raise ValueError(f"Opening event future/unmatched/wrong-side: {name}:{ticket}")
        used.add(ticket)
        attributed.append(dict(trade, entry_event=key))
    if len(used) != len(openings) or len(used) != len(by_ticket):
        raise ValueError(f"Unattributed opening or raw ResultDeal: {name}")
    return attributed
def _stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    monthly, sides, exits = defaultdict(list), defaultdict(list), defaultdict(list)
    for t in trades:
        monthly[str(t["close"])[:7]].append(t)
        sides[t["direction"]].append(t)
        exits[str(t["exit_reason"])].append(t)
    totals = bucket(trades)
    return dict(total=totals, monthly={k: bucket(v) for k, v in sorted(monthly.items())},
                sides={k: bucket(v) for k, v in sorted(sides.items())},
                exits={k: bucket(v) for k, v in sorted(exits.items())},
                worst_trade=min((t["net"] for t in trades), default=None))
def _pair(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    c, t = control["trades"], treatment["trades"]
    cm, tm = {entry_key(x): x for x in c}, {entry_key(x): x for x in t}
    need(len(cm) == len(c) and len(tm) == len(t), "Duplicate canonical entry key; pairing ambiguous")
    common = set(cm) & set(tm)
    only_c, only_t = set(cm) - common, set(tm) - common
    paired_c, paired_t = [cm[k] for k in common], [tm[k] for k in common]
    unmatched_c, unmatched_t = [cm[k] for k in only_c], [tm[k] for k in only_t]
    all_c, all_t = bucket(c), bucket(t)
    pc, pt, uc, ut = map(bucket, (paired_c, paired_t, unmatched_c, unmatched_t))
    delta = round(all_t["net"] - all_c["net"], 2)
    reconstructed = round(pt["net"] - pc["net"] + ut["net"] - uc["net"], 2)
    need(abs(delta - reconstructed) <= .021, "Pair/unmatched PnL conservation failed")
    transitions = defaultdict(list)
    for key in common:
        transitions[f"{cm[key]['exit_reason']}->{tm[key]['exit_reason']}"].append((cm[key], tm[key]))
    return dict(control=control["name"], treatment=treatment["name"],
        totals=dict(control=all_c, treatment=all_t, delta_net=delta,
                    delta_wins=all_t["wins"]-all_c["wins"], delta_losses=all_t["losses"]-all_c["losses"],
                    delta_zero=all_t["zero"]-all_c["zero"]),
        paired=dict(count=len(common), control=pc, treatment=pt, delta_net=round(pt["net"]-pc["net"], 2),
                    exit_reason_transitions={k:dict(count=len(v), control_net=round(sum(a["net"] for a,_ in v),2),
                        treatment_net=round(sum(b["net"] for _,b in v),2),
                        delta_net=round(sum(b["net"]-a["net"] for a,b in v),2))
                        for k,v in sorted(transitions.items())}),
        unmatched=dict(control_count=len(only_c), control=uc, treatment_count=len(only_t), treatment=ut,
                       delta_net=round(ut["net"]-uc["net"], 2)),
        decomposition=dict(reconstructed_total_delta=reconstructed, observed_total_delta=delta))
def analyze() -> dict[str, Any]:
    _check_artifacts()
    path = BASE / COMPLETE
    batch = json.loads(path.read_text(encoding="utf-8-sig"))
    need(batch.get("round_label") == "R7" and batch.get("release_status") == "NOT_A_RELEASE",
         "Wrong batch/release identity")
    need(batch.get("source_sha") == SOURCE_SHA and batch.get("promotion") is False,
         "R7 manifest source/release guard mismatch")
    dev = batch.get("development")
    if not isinstance(dev, list) or len(dev) != 4 or batch.get("qualified") is not False: raise ValueError("R7 four-cell batch incomplete or improperly qualified")
    baseline_result = batch.get("baseline")
    if not isinstance(baseline_result, dict): raise ValueError("R7 mode0 baseline missing")
    baseline_sig = native.verified_signature(baseline_result, BASE)
    baseline_name = baseline_result.get("evidence_run")
    baseline = _load_run(baseline_result, baseline_name, 0, 0, None, baseline_sig, details=False)
    need(batch.get("parity", {}).get("passed") is True, "R7 V24 mode0 parity missing/failed")
    native.parity(_reference("r5_d_production_v24", production=True), baseline_result,
                  evidence_base=BASE, production_base=BASE)
    controls = {}
    for preset in (0, 1):
        row = batch.get("control_parity", {}).get(str(preset), {})
        need(row.get("comparison", {}).get("passed") is True, f"TP1 P{preset} parity missing/failed")
        need(row.get("reference") == f"r5_d_r4_control_p{preset}",
             f"TP1 P{preset} exact R4 control mapping mismatch")
        name = f"r7_a_tp1_control_p{preset}"
        need(row.get("result", {}).get("evidence_run") == name, f"TP1 run mapping mismatch P{preset}")
        controls[preset] = _load_run(row["result"], name, 5, preset, 1.0, baseline_sig, details=True)
        native.parity(_reference(row["reference"], production=False, preset=preset), row["result"],
                      evidence_base=BASE, production_base=BASE)
    cells = {}
    expected = {f"p{p}_tp{tp}" for p in (0, 1) for tp in ("0p5", "0p6")}
    for row in dev:
        tag = row.get("config_tag")
        if tag not in expected or tag in cells:
            raise ValueError(f"Unexpected/duplicate R7 cell: {tag}")
        preset, tp = int(tag[1]), (.5 if "tp0p5" in tag else .6)
        name = f"r7_a_dev_{tag}"
        need(row.get("mode") == 5 and row.get("parameters") == dict(InpEntryStrength=preset,
             InpStopLossATRMul=1.5, InpTakeProfitRRMul=tp), f"R7 cell config mismatch: {tag}")
        cells[tag] = _load_run(row.get("result", {}), name, 5, preset, tp, baseline_sig, details=True)
    if set(cells) != expected:
        raise ValueError("R7 four-cell matrix incomplete")
    comparisons = {}
    for p in (0, 1):
        for tp in (.5, .6):
            tag = f"p{p}_tp{str(tp).replace('.', 'p')}"
            comparisons[tag] = _pair(controls[p], cells[tag])
    descriptive = batch.get("descriptive10m") or batch.get("descriptive_failed_candidate")
    descriptive_report = None
    if descriptive:
        if descriptive.get("eligible") is not False or descriptive.get("promotion") is not False:
            raise ValueError("Descriptive 10m replay must remain ineligible")
        result = descriptive.get("result", {})
        params = descriptive.get("parameters", {})
        preset, tp = params.get("InpEntryStrength"), params.get("InpTakeProfitRRMul")
        if type(preset) is not int or tp not in (.5, .6):
            raise ValueError("Descriptive config is unsupported")
        name = "r7_a_descriptive10m"
        need(result.get("evidence_run") == name, "Unexpected descriptive evidence identity")
        detail = _load_run(result, name, 5, preset, tp, baseline_sig, details=False, end=END)
        descriptive_report = dict(evidence_run=name, stats=_stats(detail["trades"]),
            extra_cost_stress=result.get("extra_cost_stress"),
            scope="descriptive only; ineligible; no selection input")
    return dict(qualification="ATTRIBUTION_ONLY_NOT_RELEASE_QUALIFICATION",
        evidence_root="reports/v25_research_20261008_postupdate",
        baseline=dict(name=baseline["name"], stats=_stats(baseline["trades"]), final_balance=baseline["final_balance"],
                      account_delta=round(baseline["final_balance"]-10000, 2)),
        control_parity={str(p): batch["control_parity"][str(p)]["comparison"] for p in (0,1)},
        treatments={tag:dict(name=run["name"], stats=_stats(run["trades"]),
            final_balance=run["final_balance"], account_delta=round(run["final_balance"]-10000, 2),
            extra_cost_stress=run["result"].get("extra_cost_stress"))
            for tag,run in sorted(cells.items())},
        paired_vs_tp1=comparisons, descriptive10m=descriptive_report,
        warning="Exact signal/raw bar+tick and ResultDeal ticket attribution; no MFE outcomes inferred.")
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true", help="emit aggregated JSON to stdout")
    args = parser.parse_args()
    report = analyze()
    encoded = json.dumps(report, indent=2, allow_nan=False)
    if args.stdout:
        print(encoded)
    else:
        out = BASE / "r7_a_attribution.json"
        out.write_text(encoded + "\n", encoding="utf-8")
        print(json.dumps(dict(report=str(out.relative_to(ROOT)), qualification=report["qualification"],
                              cells=len(report["treatments"]), comparisons=len(report["paired_vs_tp1"]))))
if __name__ == "__main__":
    main()
