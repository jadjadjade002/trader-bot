"""Fail-closed, read-only attribution for the fixed R8 native batch."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from research.analyze_v23_backtest import bucket, csv_rows, finite, parse_deals, report_rows
from research import analyze_candidate_r7 as common
from research import native_end_accounting
from research import run_v25_native as native

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/v25_research_20261008_postupdate"
COMPLETE = "r8_b_complete.json"
SOURCE = ROOT / "research/ResearchCandidate_R8.mq5"
BINARY = ROOT / "research/ResearchCandidate_R8.ex5"
CONTROL_SOURCE = ROOT / "research/ResearchControl_R1_R8.mq5"
CONTROL_BINARY = ROOT / "research/ResearchControl_R1_R8.ex5"
SOURCE_SHA = "03CD489C2C51BDA9F87CA88AA231FFF25206071BFFDBA73ACDDCFD1597431974"
BINARY_SHA = "54693E177FE0FA56CBB4D436AB70796D73D364B8C0A0F32B16667A54ABF27E03"
CONTROL_SOURCE_SHA = "961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B"
CONTROL_BINARY_SHA = "2F59FC1F06CDAFF468F137ACF650C4198CE4BDB68CC6962551CFEBDBC46535CE"
R1_SOURCE = ROOT / "research/ResearchCandidate_R1.mq5"
R1_SOURCE_SHA = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
PRODUCTION_RUN = "r5_d_production_v24"
TESTER_LOGIN = 113802049
R8_CONTROL_RUN = "r8_b_r1_control"
R8_OFF_RUN = "r8_b_control_k0_e0"
START, DEV_END, VAL_END, END = "2025.12.01", "2026.06.01", "2026.08.01", "2026.10.01"
FIXED = {
    "InpEnableSessionGuard": "false", "InpEnableSpreadGuard": "false",
    "InpEnableMarginGuard": "true", "InpEnableHardSL": "true",
    "InpMaxHoldBars": "60", "InpDonchianPeriod": "20", "InpATRPeriod": "14",
    "InpMinSLPoints": "150", "InpLotSize": "0.01", "InpFadeBreakouts": "false",
    "InpMagicNumber": "992300", "InpTargetAccount": "0",
    "InpEnableCircuitBreaker": "true", "InpMaxConsecutiveLosses": "4",
    "InpCooldownMinutes": "90",
}
FEATURE_FIELDS = ["decision_bar", "signal_bar", "tick_msc", "require_efficiency",
    "require_near_mean", "efficiency_available", "efficiency", "efficiency_gap_spanning",
    "extension_available", "extension_atr", "parent_side", "final_side", "parent_reason", "reason"]
TREATMENTS = {"k1_e0": (True, False), "k0_e1": (False, True), "k1_e1": (True, True)}


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _sha(path: Path, expected: str) -> None:
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest().upper() != expected:
        raise ValueError(f"Pinned R8 artifact SHA mismatch: {path.name}")


def _bool(value: Any, label: str) -> bool:
    text = str(value).strip().lower()
    if text not in ("true", "false"):
        raise ValueError(f"Invalid boolean: {label}")
    return text == "true"


def _time(value: Any, label: str) -> datetime:
    try:
        return datetime.strptime(str(value).strip(), "%Y.%m.%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"Bad MQL timestamp {label}: {value!r}") from exc


def _quantiles(values: list[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return {"p50": None, "p90": None, "p95": None, "p99": None}
    def nearest_rank(p: float) -> int:
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    return {f"p{int(p * 100)}": nearest_rank(p) for p in (.50, .90, .95, .99)}


def _event_key(row: dict[str, Any], bar_field="bar") -> tuple[str, int]:
    # Epoch arithmetic joins MQL bar/tick coordinates; it is not a broker-UTC claim.
    return common.event_key({"bar": row.get(bar_field, ""), "tick_msc": row.get("tick_msc")})


def _reconstruct_boundary_efficiency(decision: datetime, signal_bar: datetime,
                                     raw_by_bar: dict[str, dict[str, Any]], name: str) -> float:
    """Rebuild the ER exactly when its 10-decimal export lands on the 0.30 boundary."""
    if signal_bar != decision - timedelta(minutes=1):
        raise ValueError(f"R8 boundary ER signal bar is not decision-1: {name}:{decision}")
    closes = []
    for offset in range(11):
        expected_decision = decision - timedelta(minutes=offset)
        bar = expected_decision.strftime("%Y.%m.%d %H:%M:%S")
        raw = raw_by_bar.get(bar)
        if raw is None:
            raise ValueError(f"R8 boundary ER raw close row missing: {name}:{bar}")
        # Revalidate each event timestamp, and require its bar key to be exact.
        key = _event_key(raw)
        if key[0] != bar or _time(raw.get("bar"), "raw.bar") != expected_decision:
            raise ValueError(f"R8 boundary ER raw bar/tick mismatch: {name}:{bar}")
        try:
            close = finite(raw.get("retest_close", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"R8 boundary ER raw close invalid: {name}:{bar}") from exc
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"R8 boundary ER raw close invalid: {name}:{bar}")
        closes.append(close)
    # Matches R8CalculateEfficiency: series shift1..shift11, left-to-right sum.
    path = 0.0
    for i in range(10):
        step = abs(closes[i] - closes[i + 1])
        if not math.isfinite(step):
            raise ValueError(f"R8 boundary ER step nonfinite: {name}:{decision}")
        path += step
        if not math.isfinite(path):
            raise ValueError(f"R8 boundary ER path nonfinite: {name}:{decision}")
    if path <= 0:
        raise ValueError(f"R8 boundary ER path is flat: {name}:{decision}")
    efficiency = abs(closes[0] - closes[10]) / path
    if not math.isfinite(efficiency) or not 0 <= efficiency <= 1:
        raise ValueError(f"R8 boundary ER result invalid: {name}:{decision}")
    return efficiency


def _params(efficiency: bool, extension: bool) -> dict[str, Any]:
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
                InpRequireEfficiency=efficiency, InpRequireNearMean=extension)


def _expected_config(name: str) -> tuple[int, dict[str, Any], bool]:
    if name == "r8_b_baseline":
        return 0, {}, False
    if name == R8_OFF_RUN or name == R8_CONTROL_RUN:
        return 1, _params(False, False), name == R8_CONTROL_RUN
    match = re.fullmatch(r"r8_b_(?:dev|val)_(k[01]_e[01])", name)
    if match and match.group(1) in TREATMENTS:
        return 1, _params(*TREATMENTS[match.group(1)]), False
    match = re.fullmatch(r"r8_b_(confirmation|locked10m|descriptive10m|capital70|delay500)", name)
    if match:
        # These runs must be tied to the immutable validation selection lock later.
        return 1, {}, False
    raise ValueError(f"Unexpected R8 run identity: {name}")


def _r1_control_name(result: dict[str, Any]) -> str:
    name = result.get("evidence_run")
    if not isinstance(name, str) or not re.fullmatch(r"r8_b_r1_control(?:_retry[12])?", name):
        raise ValueError("R8 R1 control identity outside bounded retry contract")
    return name


def _accepted_end_audit(name: str, stored: Any, computed: dict[str, Any]) -> dict[str, Any]:
    """Permit only the pre-amendment exact R8 mode-0 baseline omission."""
    if (name == "r8_b_baseline" and stored is None
            and computed == dict(verified=False, tickets=[])):
        return dict(computed, accepted_record_legacy_missing=True)
    if stored != computed:
        raise ValueError(f"Accepted native end-close audit differs from verified ledger: {name}")
    return dict(computed, accepted_record_legacy_missing=False)


def _validate_lock_precedes_confirmation(lock: dict[str, Any], started: dict[str, Any]) -> None:
    try:
        locked = datetime.fromisoformat(str(lock["locked_utc"]))
        launched = datetime.fromisoformat(str(started["started_utc"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("R8 selection lock/confirmation start time malformed") from exc
    if locked.tzinfo is None or launched.tzinfo is None or locked > launched:
        raise ValueError("R8 validation lock was not recorded before confirmation launch")


def _validate_run(result: dict[str, Any], name: str, baseline_signature: dict[str, Any], *,
                  start: str, end: str, deposit: float = 10000,
                  mode: int | None = None, params: dict[str, Any] | None = None,
                  is_r1_control: bool = False, production: bool = False,
                  details: bool = False, delay_ms: int = 200,
                  tester_login: int = TESTER_LOGIN) -> dict[str, Any]:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Unsafe R8 evidence run identity")
    accepted_path = BASE / "runs" / name / "accepted.json"
    run_dir = accepted_path.parent
    if not accepted_path.is_file():
        raise ValueError(f"R8 run not accepted: {name}")
    accepted = json.loads(accepted_path.read_text(encoding="utf-8-sig"))
    if not isinstance(accepted.get("signature"), dict) or not isinstance(accepted.get("result"), dict):
        raise ValueError(f"Malformed accepted record: {name}")
    need(accepted["result"] == result, f"Complete/accepted result differs: {name}")
    need(result.get("evidence_run") == name, f"Wrong accepted evidence identity: {name}")
    sig = native.verified_signature(result, BASE)
    set_tag = f"InpRunTag={name}\n"
    if production:
        source, binary = ROOT / "AegisPredator_v24.mq5", ROOT / "AegisPredator_v24.ex5"
        overrides: dict[str, Any] = {}
        expected_mode = 0
        expected_source = native.SOURCE_HASH
        expected_binary = native.BINARY_HASH
        expected_production = True
        expected_settings = native.settings(name, 0, {}, production=True)
    elif is_r1_control:
        source, binary = CONTROL_SOURCE, CONTROL_BINARY
        overrides = dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0)
        expected_mode = 1
        expected_source, expected_binary = CONTROL_SOURCE_SHA, CONTROL_BINARY_SHA
        expected_production = False
        expected_settings = native.settings(name, 1, overrides, r2=True, control_r1=True)
    else:
        source, binary = SOURCE, BINARY
        overrides = {} if params is None else params
        expected_mode = 0 if mode is None else mode
        expected_source, expected_binary = SOURCE_SHA, BINARY_SHA
        expected_production = False
        expected_settings = native.settings(name, expected_mode, overrides, r2=True, r8=True)
    _sha(source, expected_source)
    _sha(binary, expected_binary)
    expected = dict(start=start, end=end, mode=expected_mode, overrides=overrides,
        deposit=deposit, optimize=False, production=expected_production, delay_ms=delay_ms,
        source_sha=expected_source, binary_sha=expected_binary)
    for key, value in expected.items():
        need(sig.get(key) == value, f"Accepted signature drift {name}:{key}")
    need(type(sig.get("tester_connection_login")) is int
         and sig.get("tester_connection_login") == tester_login,
         f"Accepted tester connection login mismatch: {name}")
    months = native.months(start, end)
    ticks = sig.get("tick_cache")
    need(isinstance(ticks, list) and [x.get("month") for x in ticks] == months,
         f"Tick-cache coverage mismatch: {name}")
    if baseline_signature:
        ref_cache = {x["month"]: x for x in baseline_signature["tick_cache"]}
        need(all(ref_cache.get(x["month"]) == x for x in ticks), f"Cache differs from full R8 baseline: {name}")
        need(sig.get("runtime") == baseline_signature.get("runtime"), f"Runtime differs from full R8 baseline: {name}")

    set_path = run_dir / f"{name}.set"
    need(set_path.is_file(), f"Missing accepted SET: {name}")
    set_text = set_path.read_text(encoding="utf-16")
    need(hashlib.sha256(set_text.encode("utf-16")).hexdigest().lower() == str(sig.get("set_sha", "")).lower(),
         f"SET hash mismatch: {name}")
    need(set_text == expected_settings, f"SET differs from frozen R8/native contract: {name}")
    need(set_tag in set_text, f"Signed SET run tag differs: {name}")
    if not production:
        set_values = {}
        for line in set_text.splitlines():
            if not line.strip():
                continue
            if "=" not in line:
                raise ValueError(f"Malformed accepted SET: {name}")
            key, value = line.split("=", 1)
            if key in set_values:
                raise ValueError(f"Duplicate accepted SET input: {name}:{key}")
            set_values[key] = value
        preset = 0 if expected_mode == 0 else 2
        explicit = dict(FIXED, InpRunTag=name, InpExperimentMode=str(expected_mode),
            InpEntryStrength=str(preset), InpUseGridIndices="false", InpTPGridIndex="2")
        if expected_mode == 0:
            explicit.update(InpStopLossATRMul="1.5", InpTakeProfitRRMul="2.0",
                            InpRequireEfficiency="false", InpRequireNearMean="false")
        else:
            explicit.update(InpStopLossATRMul="2.0", InpTakeProfitRRMul="3.0",
                )
            if not is_r1_control:
                explicit.update(InpRequireEfficiency=str(bool(overrides.get("InpRequireEfficiency", False))).lower(),
                    InpRequireNearMean=str(bool(overrides.get("InpRequireNearMean", False))).lower())
        need(all(set_values.get(key) == value for key, value in explicit.items()),
             f"Explicit frozen SET input mismatch: {name}")

    need(result.get("cache_hashes_verified") is True and result.get("terminal_cache_read_warnings") == [],
         f"Accepted cache verification missing: {name}")
    if not is_r1_control and not production:
        need(result.get("native_mql_fixture_checks") == 27, f"R8 native fixture marker missing: {name}")
    metrics = result.get("native")
    need(isinstance(metrics, dict) and metrics.get("History Quality") == "100% real ticks",
         f"No accepted full real-tick result: {name}")
    html, native_rows = report_rows(run_dir / f"{name}.htm")
    need(html == metrics, f"Accepted native metrics differ from HTML: {name}")
    deals = csv_rows(run_dir / f"{name}_deals.csv")
    spec_rows = csv_rows(run_dir / f"{name}_spec.csv")
    specs = {}
    for row in spec_rows:
        key = row.get("key", "")
        if not key or key in specs:
            raise ValueError(f"Malformed/duplicate symbol spec key: {name}:{key}")
        specs[key] = row.get("value", "")
    need(specs.get("history_export_ok") in ("true", "1") and specs.get("symbol") == "XAUUSD",
         f"Native export/spec incomplete: {name}")
    journal = "\n".join(p.read_text(encoding="utf-8-sig")
        for p in sorted(run_dir.glob("journal_*.txt")))
    end_proof = None
    if not production:
        trades, cash, end_proof = native_end_accounting.parse_verified_native_deals(
            deals, metrics, native_rows, specs, journal, end=end, deposit=deposit,
            candidate_source=("research/ResearchControl_R1_R8.mq5" if is_r1_control
                             else "research/ResearchCandidate_R8.mq5"))
        end_proof = _accepted_end_audit(name, result.get("native_end_close_audit"), end_proof)
    else:
        trades, cash = parse_deals(deals)
    summary = bucket(trades)
    need(len(cash) == 1 and cash[0]["type"] == 2 and abs(cash[0]["net"] - deposit) <= .021,
         f"Unexpected cash/deposit ledger: {name}")
    need(summary["trades"] == int(finite(metrics["Total Trades"]))
         and abs(summary["net"] - finite(metrics["Total Net Profit"])) <= .021,
         f"Native/deal ledger mismatch: {name}")
    need(summary["trades"] == result.get("trades") and abs(summary["net"] - finite(result.get("net"))) <= .021,
         f"Accepted deal summary mismatch: {name}")
    for key in ("wins", "losses", "zero", "profit", "commission", "swap", "fee"):
        need(result.get(key) == summary[key], f"Accepted deal component mismatch {name}:{key}")
    need(result.get("net_profit_factor") == summary["net_profit_factor"]
         and result.get("win_rate_pct") == summary["win_rate_pct"],
         f"Accepted PF/win-rate mismatch: {name}")
    final_balance = finite(specs.get("final_balance"))
    need(abs(final_balance - deposit - summary["net"]) <= .021
         and abs(final_balance - finite(result.get("final_balance"))) <= .021,
         f"Native final-balance mismatch: {name}")
    expected_dd = native.dd_percent(metrics)
    need(abs(finite(result.get("native_equity_dd_pct")) - expected_dd) <= .001,
         f"Native equity drawdown mismatch: {name}")
    need(result.get("native_stopout") is any(t["exit_reason"] == 6 for t in trades),
         f"Native stopout summary mismatch: {name}")
    if "extra_cost_stress" in result:
        expected_stress = {str(cost): round(summary["net"] - cost * summary["trades"], 2)
                           for cost in (.2, .5)}
        need(result["extra_cost_stress"] == expected_stress, f"Extra-cost accounting mismatch: {name}")
    observed = native.strict_int(specs.get("observed_ticks"), low=1)
    native_ticks = native.strict_int(finite(metrics.get("Ticks")), low=1)
    coverage = native.validate_coverage(csv_rows(run_dir / f"{name}_coverage.csv"), start, end, {0})
    need(coverage["total_ticks"]["0"] == observed and observed <= native_ticks,
         f"Monthly coverage totals mismatch: {name}")
    for suffix in ("_equity.csv", "_paths.csv", "_raw.csv", "_signals.csv"):
        need((run_dir / f"{name}{suffix}").is_file(), f"Required native export missing: {name}{suffix}")
    run = dict(name=name, trades=trades, summary=summary, cash=cash, final_balance=final_balance,
               signature=sig, result=result, specs=specs, native_end_close=end_proof)
    ledger_months = {m: bucket([t for t in trades if t["close"].startswith(m)])
                     for m in (f"{v // 100:04d}-{v % 100:02d}" for v in months)}
    if "monthly" in result:
        need(result["monthly"] == ledger_months, f"Monthly accepted ledger mismatch: {name}")
    if "sides" in result:
        ledger_sides = {side: bucket([t for t in trades if t["direction"] == side]) for side in ("buy", "sell")}
        need(result["sides"] == ledger_sides, f"Side accepted ledger mismatch: {name}")
    if "exits" in result:
        ledger_exits = {str(k): bucket([t for t in trades if str(t["exit_reason"]) == str(k)])
                        for k in sorted({t["exit_reason"] for t in trades})}
        need(result["exits"] == ledger_exits, f"Exit accepted ledger mismatch: {name}")
    if details and expected_mode == 1:
        run["events"] = _link_r8_events(run_dir, name, params or overrides, trades)
        if isinstance(result.get("candidate_gate_counts"), dict):
            need(result["candidate_gate_counts"] == run["events"]["gate_counts"],
                 f"Accepted gate-count ledger mismatch: {name}")
        if "candidate_order_attempts" in result:
            attempts = sum(_bool(row.get("order_attempt"), "raw.order_attempt")
                           for row in csv_rows(run_dir / f"{name}_raw.csv"))
            need(result["candidate_order_attempts"] == attempts,
                 f"Accepted order-attempt count mismatch: {name}")
    return run


def _link_r8_events(run_dir: Path, name: str, params: dict[str, Any], verified_trades=None) -> dict[str, Any]:
    signals = csv_rows(run_dir / f"{name}_signals.csv")
    raw = csv_rows(run_dir / f"{name}_raw.csv")
    features_path = run_dir / f"{name}_r8_features.csv"
    if not signals or not raw or not features_path.is_file():
        raise ValueError(f"Missing R8 signal/raw/feature exports: {name}")
    features = csv_rows(features_path)
    with features_path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream), [])
    if header != FEATURE_FIELDS:
        raise ValueError(f"R8 feature header mismatch: {name}")
    signal_by, raw_by = {}, {}
    signal_by_bar, raw_by_bar = {}, {}
    for i, row in enumerate(signals, 1):
        key = _event_key(row)
        if key in signal_by:
            raise ValueError(f"Duplicate signal event: {name}:{key}")
        if key[0] in signal_by_bar:
            raise ValueError(f"Multiple signal candidates in one decision bar: {name}:{key[0]}")
        if native.strict_int(row.get("mode"), low=0, high=3) != 1 or native.strict_int(row.get("entry_strength"), high=2) != 2:
            raise ValueError(f"R8 signal config mismatch: {name}:{i}")
        side = native.strict_int(row.get("signal"), low=-1, high=1)
        attempt = _bool(row.get("order_attempt"), "signal.order_attempt")
        signal_by[key] = dict(row, _key=key, _side=side, _attempt=attempt)
        signal_by_bar[key[0]] = signal_by[key]
    for i, row in enumerate(raw, 1):
        key = _event_key(row)
        if key in raw_by:
            raise ValueError(f"Duplicate raw event: {name}:{key}")
        if key[0] in raw_by_bar:
            raise ValueError(f"Ambiguous raw rows in one decision bar: {name}:{key[0]}")
        side = native.strict_int(row.get("original"), low=-1, high=1)
        attempt = _bool(row.get("order_attempt"), "raw.order_attempt")
        gate = str(row.get("gate", ""))
        ticket = native.strict_int(row.get("deal_ticket"))
        order_ticket = native.strict_int(row.get("order_ticket"))
        retcode = native.strict_int(row.get("retcode"))
        if (attempt != (gate == "order_attempt") or (not attempt and any((ticket, order_ticket, retcode)))):
            raise ValueError(f"Raw attempt/gate/ticket mismatch: {name}:{i}")
        raw_by[key] = dict(row, _side=side, _attempt=attempt, _gate=gate,
                           _deal_ticket=ticket, _order_ticket=order_ticket, _retcode=retcode)
        raw_by_bar[key[0]] = raw_by[key]
    if set(signal_by) != set(raw_by):
        raise ValueError(f"Signal/raw event-key sets differ: {name}")
    for key, sig in signal_by.items():
        rawrow = raw_by[key]
        if (sig["_side"] != rawrow["_side"] or sig["_attempt"] != rawrow["_attempt"]
                or sig.get("execution_gate") != rawrow["_gate"]):
            raise ValueError(f"Signal/raw identity mismatch: {name}:{key}")

    use_er = bool(params.get("InpRequireEfficiency", False))
    use_ext = bool(params.get("InpRequireNearMean", False))
    feature_by = {}
    reason_counts = Counter()
    boundary_reconstructions = []
    for i, row in enumerate(features, 1):
        if set(row) != set(FEATURE_FIELDS):
            raise ValueError(f"R8 feature schema mismatch: {name}:{i}")
        key = _event_key(row, "decision_bar")
        decision_key = key[0]
        if decision_key in feature_by:
            raise ValueError(f"Multiple R8 feature samples in one decision bar: {name}:{decision_key}")
        decision = _time(row["decision_bar"], "decision_bar")
        signal_bar = _time(row["signal_bar"], "signal_bar")
        if signal_bar >= decision:
            raise ValueError(f"R8 feature uses non-prior signal bar: {name}:{i}")
        if decision_key not in signal_by_bar or decision_key not in raw_by_bar:
            raise ValueError(f"R8 feature decision bar missing from signal/raw ledger: {name}:{decision_key}")
        original_event_tick = signal_by_bar[decision_key]["_key"][1]
        feature_sample_tick = key[1]
        sample_delay = feature_sample_tick - original_event_tick
        if sample_delay < 0:
            raise ValueError(f"R8 feature sample predates original callback: {name}:{decision_key}")
        if _bool(row["require_efficiency"], "require_efficiency") != use_er or _bool(row["require_near_mean"], "require_near_mean") != use_ext:
            raise ValueError(f"R8 feature factor config mismatch: {name}:{key}")
        er_available = _bool(row["efficiency_available"], "efficiency_available")
        ext_available = _bool(row["extension_available"], "extension_available")
        er_gap = row["efficiency_gap_spanning"].strip()
        er_text, ext_text = row["efficiency"].strip(), row["extension_atr"].strip()
        if not use_er and (er_available or er_text or er_gap):
            raise ValueError(f"ER-off event contains evaluated values: {name}:{key}")
        if not use_ext and (ext_available or ext_text):
            raise ValueError(f"Extension-off event contains evaluated values: {name}:{key}")
        er_value = None
        if er_available:
            er_value = finite(er_text)
            if not 0 <= er_value <= 1 or er_gap.lower() not in ("true", "false"):
                raise ValueError(f"Malformed available ER values: {name}:{key}")
        elif er_text or er_gap:
            raise ValueError(f"Unavailable ER must be blank: {name}:{key}")
        ext_value = None
        if ext_available:
            ext_value = finite(ext_text)
            if ext_value < 0:
                raise ValueError(f"Negative extension value: {name}:{key}")
        elif ext_text:
            raise ValueError(f"Unavailable extension must be blank: {name}:{key}")
        parent = native.strict_int(row["parent_side"], low=-1, high=1)
        final = native.strict_int(row["final_side"], low=-1, high=1)
        if parent == 0:
            raise ValueError(f"Feature row must represent nonzero parent signal: {name}:{key}")
        reason = row["reason"]
        er_reconstructed = None
        if use_er and er_available and er_text == "0.3000000000":
            if er_gap.lower() != "false":
                raise ValueError(f"R8 boundary ER requires known nongap context: {name}:{key}")
            er_reconstructed = _reconstruct_boundary_efficiency(
                decision, signal_bar, raw_by_bar, name)
            if f"{er_reconstructed:.10f}" != er_text:
                raise ValueError(f"R8 boundary ER raw reconstruction disagrees with export: {name}:{key}")
            boundary_reconstructions.append(dict(decision_bar=row["decision_bar"],
                signal_bar=row["signal_bar"], serialized=er_value,
                reconstructed=er_reconstructed, reason=reason))
        er_for_predicate = er_reconstructed if er_reconstructed is not None else er_value
        passed = ((not use_er) or (er_available and er_for_predicate is not None and er_for_predicate >= .30)) and \
                 ((not use_ext) or (ext_available and ext_value is not None and ext_value <= 1.0))
        if not use_er and not use_ext:
            expected_reason = row["parent_reason"]
        elif use_er and not er_available:
            expected_reason = "r8_efficiency_unavailable"
        elif use_er and er_for_predicate is not None and er_for_predicate < .30:
            expected_reason = "r8_efficiency_rejected"
        elif use_ext and not ext_available:
            expected_reason = "r8_extension_unavailable"
        elif use_ext and ext_value is not None and ext_value > 1.0:
            expected_reason = "r8_extension_rejected"
        else:
            expected_reason = "r8_quality_pass"
        if final != (parent if passed else 0) or reason != expected_reason:
            raise ValueError(f"R8 factor result/reason disagrees with closed features: {name}:{key}")
        signal = signal_by_bar[decision_key]
        rawrow = raw_by_bar[decision_key]
        if signal["_side"] != final or rawrow["_side"] != final or signal.get("reason") != reason:
            raise ValueError(f"R8 feature does not reconcile to signal/raw: {name}:{key}")
        if final and not signal["_attempt"] and rawrow["_gate"] not in ("held_position", "circuit_breaker"):
            # Nonzero signal may be blocked by a quote/execution gate; preserve it, never infer a fill.
            pass
        row_out = dict(row, _key=key, _decision_bar=decision_key,
            _original_event_tick_msc=original_event_tick, _sample_tick_msc=feature_sample_tick,
            _sample_delay_ms=sample_delay, _parent=parent, _final=final,
            _er=er_value, _er_serialized=er_value, _er_reconstructed=er_reconstructed,
            _er_for_predicate=er_for_predicate, _extension=ext_value)
        feature_by[decision_key] = row_out
        reason_counts[reason] += 1
    # Any surviving nonzero candidate signal must have a feature record. Rejected
    # parent events live only in the feature ledger and remain visible there.
    missing = [bar for bar, row in signal_by_bar.items() if row["_side"] != 0 and bar not in feature_by]
    if missing:
        raise ValueError(f"R8 surviving signal missing feature row: {name}:{missing[0]}")

    deals = csv_rows(run_dir / f"{name}_deals.csv")
    openings = {}
    for row in deals:
        if native.strict_int(row["type"]) in (0, 1) and native.strict_int(row["entry"]) == 0:
            ticket = native.strict_int(row["ticket"], low=1)
            if ticket in openings:
                raise ValueError(f"Duplicate opening ticket: {name}:{ticket}")
            openings[ticket] = row
    by_ticket = {}
    for key, row in raw_by.items():
        ticket = row["_deal_ticket"]
        if ticket:
            if not row["_attempt"] or ticket not in openings or ticket in by_ticket:
                raise ValueError(f"Unmatched ResultDeal ticket: {name}:{ticket}")
            by_ticket[ticket] = (key, row)
    if verified_trades is None:
        trades, _ = parse_deals(deals)
    else:
        trades = verified_trades
    used = set()
    attributed = []
    for trade in trades:
        entry_deals = [d for d in trade["deals"] if d["entry"] == 0]
        if len(entry_deals) != 1:
            raise ValueError(f"Ambiguous opening deal: {name}:{trade['position']}")
        deal = entry_deals[0]
        ticket = deal["ticket"]
        if abs(deal["volume"] - .01) > 1e-8 or abs(deal["volume"] - trade["volume"]) > 1e-8:
            raise ValueError(f"Entry volume outside fixed contract: {name}:{trade['position']}")
        side = 1 if trade["direction"] == "buy" else -1
        if deal["type"] != (0 if side == 1 else 1) or deal["position"] != trade["position"]:
            raise ValueError(f"Opening side/position mismatch: {name}:{trade['position']}")
        if ticket not in by_ticket or ticket in used:
            raise ValueError(f"Opening lacks unique raw ResultDeal: {name}:{ticket}")
        key, event = by_ticket[ticket]
        feature = feature_by.get(key[0])
        if (feature is None or feature["_final"] != side or key[1] > deal["time_msc"]
                or feature["_sample_tick_msc"] > deal["time_msc"]):
            raise ValueError(f"Opening event/feature sample is future, unmatched or wrong-side: {name}:{ticket}")
        used.add(ticket)
        attributed.append(dict(trade, entry_event=key))
    if len(used) != len(openings) or len(used) != len(by_ticket):
        raise ValueError(f"Unattributed opening or raw ResultDeal: {name}")
    gates = Counter(row["_gate"] for row in raw_by.values())
    held_before = sum(_bool(row.get("held_before"), "raw.held_before") for row in raw)
    delays = [row["_sample_delay_ms"] for row in feature_by.values()]
    return dict(trades=attributed, feature_rows=len(feature_by), feature_reasons=dict(sorted(reason_counts.items())),
        factor_rejections=sum(reason.endswith(("_rejected", "_unavailable")) for reason in reason_counts.elements()),
        efficiency_evaluated=sum(row["_er"] is not None for row in feature_by.values()),
        efficiency_boundary_reconstructed=len(boundary_reconstructions),
        efficiency_boundary_diagnostics=boundary_reconstructions,
        efficiency_unavailable=sum(use_er and row["_er"] is None for row in feature_by.values()),
        extension_evaluated=sum(row["_extension"] is not None for row in feature_by.values()),
        extension_unavailable=sum(use_ext and row["_extension"] is None for row in feature_by.values()),
        efficiency_gap_spanning=sum(_bool(row["efficiency_gap_spanning"], "efficiency_gap_spanning")
            for row in feature_by.values() if row["efficiency_available"] == "true"),
        decision_bar_join=dict(signal_rows=len(signal_by), raw_rows=len(raw_by),
            matched_event_rows=len(signal_by), feature_rows=len(feature_by),
            features_without_signal_raw_bar=0, signal_raw_unique_bars=len(signal_by_bar)),
        feature_sample_clock=dict(shifted_samples=sum(row["_sample_delay_ms"] > 0 for row in feature_by.values()),
            delay_ms_min=min(delays, default=None), delay_ms_max=max(delays, default=None),
            delay_ms_quantiles=_quantiles(delays),
            sample_tick_msc_min=min((row["_sample_tick_msc"] for row in feature_by.values()), default=None),
            sample_tick_msc_max=max((row["_sample_tick_msc"] for row in feature_by.values()), default=None),
            delay_counts_ms=dict(sorted(Counter(str(row["_sample_delay_ms"])
                for row in feature_by.values()).items()))),
        held_events=gates.get("held_position", 0), circuit_breaker_events=gates.get("circuit_breaker", 0),
        held_before_events=held_before, gate_counts=dict(sorted(gates.items())),
        event_rows=len(raw_by), surviving_nonzero_events=sum(x["_side"] != 0 for x in signal_by.values()),
        linked_openings=len(used))


def _reference(name: str, *, production: bool, preset: int = 0,
               tester_login: int = TESTER_LOGIN) -> dict[str, Any]:
    accepted = json.loads((BASE / "runs" / name / "accepted.json").read_text(encoding="utf-8-sig"))
    result = accepted.get("result", {})
    sig = native.verified_signature(result, BASE)
    source = ROOT / "AegisPredator_v24.mq5" if production else CONTROL_SOURCE
    binary = ROOT / "AegisPredator_v24.ex5" if production else CONTROL_BINARY
    overrides = {} if production else dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                                            InpTakeProfitRRMul=3.0)
    mode = 0 if production else 1
    expected = dict(start=START, end=END if production else DEV_END, mode=mode,
        overrides=overrides, deposit=10000, optimize=False, production=production, delay_ms=200,
        source_sha=hashlib.sha256(source.read_bytes()).hexdigest().upper(),
        binary_sha=hashlib.sha256(binary.read_bytes()).hexdigest().upper())
    if production:
        need(expected["source_sha"] == native.SOURCE_HASH and expected["binary_sha"] == native.BINARY_HASH,
             "Frozen production V24 artifact hashes changed")
    for key, value in expected.items():
        need(sig.get(key) == value, f"Reference control signature mismatch: {name}:{key}")
    need(type(sig.get("tester_connection_login")) is int
         and sig.get("tester_connection_login") == tester_login,
         f"Reference tester connection login mismatch: {name}")
    set_text = (BASE / "runs" / name / f"{name}.set").read_text(encoding="utf-16")
    need(hashlib.sha256(set_text.encode("utf-16")).hexdigest().lower() == str(sig.get("set_sha", "")).lower(),
         f"Reference SET hash mismatch: {name}")
    expected_set = native.settings(name, mode, overrides, production=production,
                                   r2=not production, control_r1=not production)
    need(set_text == expected_set, f"Reference SET differs: {name}")
    html, _ = report_rows(BASE / "runs" / name / f"{name}.htm")
    need(html == result.get("native") and result.get("cache_hashes_verified") is True,
         f"Reference HTML/cache mismatch: {name}")
    return result


def _passes(result: dict[str, Any], n: int, pf: float) -> bool:
    value = result.get("net_profit_factor")
    return (finite(result.get("net")) > 0 and native.strict_int(result.get("trades"), low=0) >= n
            and isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= pf)


def _metric_summary(run: dict[str, Any], deposit: float = 10000) -> dict[str, Any]:
    stats = common._stats(run["trades"])
    audit = run.get("native_end_close")
    return dict(name=run["name"], stats=stats, final_balance=run["final_balance"],
                account_delta=round(run["final_balance"] - deposit, 2),
                extra_cost_stress=run["result"].get("extra_cost_stress"),
                native_end_close_verified=(audit.get("verified") if isinstance(audit, dict) else None),
                verified_native_end_close_count=(len(audit.get("tickets", [])) if isinstance(audit, dict) else 0))


def analyze() -> dict[str, Any]:
    for path, digest in ((SOURCE, SOURCE_SHA), (BINARY, BINARY_SHA),
                         (CONTROL_SOURCE, CONTROL_SOURCE_SHA), (CONTROL_BINARY, CONTROL_BINARY_SHA),
                         (R1_SOURCE, R1_SOURCE_SHA)):
        _sha(path, digest)
    batch = json.loads((BASE / COMPLETE).read_text(encoding="utf-8-sig"))
    need(batch.get("round_label") == "R8" and batch.get("release_status") == "NOT_A_RELEASE"
         and batch.get("promotion") is False and batch.get("genuinely_unseen_oos") is False,
         "R8 release/identity guard mismatch")
    need(batch.get("source_sha") == SOURCE_SHA and batch.get("immutable_r1_parent_sha") == R1_SOURCE_SHA
         and batch.get("reporting_control_source") == "research/ResearchControl_R1_R8.mq5"
         and batch.get("reporting_control_sha") == CONTROL_SOURCE_SHA,
         "R8 complete manifest source identity mismatch")
    need(batch.get("evidence_root") == "reports/v25_research_20261008_postupdate",
         "R8 evidence root is not the approved fixed root")
    need(type(batch.get("tester_connection_login")) is int
         and batch["tester_connection_login"] == TESTER_LOGIN,
         "R8 batch tester login differs from the preregistered demo context")
    need(batch.get("baseline_control_run") == PRODUCTION_RUN, "R8 production control mapping mismatch")
    dev = batch.get("development")
    if not isinstance(dev, list) or len(dev) != 3:
        raise ValueError("R8 must contain exactly three fixed treatments")
    treatment_rows = {}
    for row in dev:
        tag = row.get("config_tag")
        if tag not in TREATMENTS or tag in treatment_rows:
            raise ValueError(f"Unexpected/duplicate R8 treatment: {tag}")
        eff, ext = TREATMENTS[tag]
        expected_params = _params(eff, ext)
        if row.get("mode") != 1 or row.get("parameters") != expected_params:
            raise ValueError(f"R8 treatment config drift: {tag}")
        treatment_rows[tag] = row
    need(set(treatment_rows) == set(TREATMENTS), "R8 fixed factorial incomplete")

    baseline_result = batch.get("baseline")
    if not isinstance(baseline_result, dict):
        raise ValueError("R8 exact V24 mode0 baseline missing")
    baseline = _validate_run(baseline_result, "r8_b_baseline", {}, start=START, end=END,
                             mode=0, params={}, details=False, tester_login=batch["tester_connection_login"])
    baseline_sig = baseline["signature"]
    production = _reference(PRODUCTION_RUN, production=True, tester_login=batch["tester_connection_login"])
    need(batch.get("parity", {}).get("passed") is True, "R8 V24 parity marker absent/failed")
    v24_parity = native.parity(production, baseline_result, evidence_base=BASE, production_base=BASE)

    r1_result, off_result = batch.get("r1_control"), batch.get("control")
    if not isinstance(r1_result, dict) or not isinstance(off_result, dict):
        raise ValueError("R8 exact R1/off-off controls missing")
    r1_name = _r1_control_name(r1_result)
    r1 = _validate_run(r1_result, r1_name, baseline_sig, start=START, end=DEV_END,
        is_r1_control=True, details=False, tester_login=batch["tester_connection_login"])
    off = _validate_run(off_result, R8_OFF_RUN, baseline_sig, start=START, end=DEV_END,
        mode=1, params=_params(False, False), details=True, tester_login=batch["tester_connection_login"])
    native.verify_environment(baseline_result, r1_result, evidence_base=BASE)
    native.verify_environment(baseline_result, off_result, evidence_base=BASE)
    parity_row = batch.get("control_parity", {})
    need(isinstance(parity_row, dict) and parity_row.get("passed") is True,
         "R8 exact R1/off-off parity missing/failed")
    r1_reference = _reference(r1_name, production=False, tester_login=batch["tester_connection_login"])
    actual_control_parity = native.parity(r1_reference, off_result, evidence_base=BASE, production_base=BASE)
    need(all(parity_row.get(k) == v for k, v in actual_control_parity.items()),
         "R8 off/off parity manifest differs from recomputed native comparison")

    treatments = {}
    pairs = {}
    for tag, row in sorted(treatment_rows.items()):
        name = f"r8_b_dev_{tag}"
        result = row.get("result")
        need(isinstance(result, dict), f"R8 development result missing: {tag}")
        run = _validate_run(result, name, baseline_sig, start=START, end=DEV_END,
            mode=1, params=_params(*TREATMENTS[tag]), details=True,
            tester_login=batch["tester_connection_login"])
        need(row.get("eligible") is _passes(result, 150, 1.20), f"R8 development eligibility flag mismatch: {tag}")
        treatments[tag] = run
        pairs[tag] = common._pair(off, run)

    output_treatments = {}
    for tag, run in sorted(treatments.items()):
        pair = pairs[tag]
        control_unmatched = [t for t in off["trades"] if common.entry_key(t) not in
            {common.entry_key(x) for x in run["trades"]}]
        treatment_event = run["events"]
        output_treatments[tag] = dict(**_metric_summary(run), pair_vs_off_off=pair,
            events={k: v for k, v in treatment_event.items() if k != "trades"},
            unmatched_control_winners=dict(count=sum(t["net"] > 1e-8 for t in control_unmatched),
                net=round(sum(t["net"] for t in control_unmatched if t["net"] > 1e-8), 2),
                scope="descriptive unmatched control winners; not counterfactual saved-loss proof"))

    validation = batch.get("validation", [])
    if not isinstance(validation, list):
        raise ValueError("R8 validation list malformed")
    survivors_dev = {tag for tag, row in treatment_rows.items() if _passes(row["result"], 150, 1.20)}
    if {row.get("config_tag") for row in validation} != survivors_dev or len(validation) != len(survivors_dev):
        raise ValueError("R8 validation does not contain all and only development survivors")
    val_runs = {}
    for row in validation:
        tag = row["config_tag"]
        if row.get("mode") != 1 or row.get("parameters") != _params(*TREATMENTS[tag]):
            raise ValueError(f"R8 validation config drift: {tag}")
        result = row.get("result", {})
        name = f"r8_b_val_{tag}"
        run = _validate_run(result, name, baseline_sig, start=DEV_END, end=VAL_END,
            mode=1, params=_params(*TREATMENTS[tag]), details=True,
            tester_login=batch["tester_connection_login"])
        need(row.get("eligible") is _passes(result, 40, 1.20), f"R8 validation eligibility flag mismatch: {tag}")
        val_runs[tag] = run

    lock = batch.get("selection_lock")
    descriptive = batch.get("descriptive_failed_candidate")
    selected_tag = None
    if val_runs:
        eligible = [row for row in validation if row.get("eligible") is True]
        if eligible:
            winner = min(eligible, key=lambda x:(x["result"]["native_equity_dd_pct"],
                -x["result"]["net"], x["config_tag"]))
            selected_tag = winner["config_tag"]
            need(isinstance(lock, dict) and lock.get("config_tag") == selected_tag
                 and lock.get("mode") == 1 and lock.get("parameters") == _params(*TREATMENTS[selected_tag])
                 and lock.get("selected_using") == "validation_dd_then_net_then_stable_id"
                 and lock.get("reselect_after_confirmation") is False,
                 "R8 validation selection lock mismatch")
            lock_path = BASE / "r8_b_selection_lock.json"
            need(lock_path.is_file() and json.loads(lock_path.read_text(encoding="utf-8-sig")) == lock,
                 "R8 durable selection-lock artifact differs from completed manifest")
            started_path = BASE / "runs" / "r8_b_confirmation" / "started.json"
            need(started_path.is_file(), "R8 confirmation start provenance missing")
            _validate_lock_precedes_confirmation(lock,
                json.loads(started_path.read_text(encoding="utf-8-sig")))
        else:
            need(lock is None, "R8 lock exists without validation-qualified treatment")
    elif lock is not None:
        raise ValueError("R8 lock exists without validation runs")

    confirmation_report = full_report = robustness_report = None
    if selected_tag is not None:
        params = _params(*TREATMENTS[selected_tag])
        confirm = _validate_run(batch.get("confirmation", {}), "r8_b_confirmation", baseline_sig,
            start=VAL_END, end=END, mode=1, params=params, details=True,
            tester_login=batch["tester_connection_login"])
        full = _validate_run(batch.get("full", {}), "r8_b_locked10m", baseline_sig,
            start=START, end=END, mode=1, params=params, details=True,
            tester_login=batch["tester_connection_login"])
        confirm_pass = _passes(confirm["result"], 40, 1.10)
        full_months = full["result"].get("monthly", {})
        positive_months = sum(finite(x["net"]) > 0 for x in full_months.values())
        historical = (confirm_pass and _passes(full["result"], 150, 1.15) and positive_months >= 7
            and full["result"]["net"] > baseline["result"]["net"]
            and full["result"]["native_equity_dd_pct"] <= baseline["result"]["native_equity_dd_pct"])
        need(batch.get("historical_candidate_passed") is historical,
             "R8 historical gate summary flag mismatch")
        capital = _validate_run(batch.get("capital70", {}), "r8_b_capital70", baseline_sig,
            start=START, end=END, deposit=70, mode=1, params=params, details=False,
            tester_login=batch["tester_connection_login"])
        delay = _validate_run(batch.get("delay500", {}), "r8_b_delay500", baseline_sig,
            start=START, end=END, mode=1, params=params, details=False, delay_ms=500,
            tester_login=batch["tester_connection_login"])
        # Existing economic robustness gate; descriptive result is never input.
        from research.candidate_release_evidence import evaluate
        robustness = evaluate(dict(qualified=historical, full=full["result"],
                                  capital70=capital["result"], delay500=delay["result"]))
        need(batch.get("economic_robustness") == robustness
             and batch.get("qualified") is (historical and robustness["historically_robust"])
             and batch.get("promotion") is False,
             "R8 economic/final qualification flags mismatch")
        confirmation_report = _metric_summary(confirm)
        full_report = dict(**_metric_summary(full), positive_months=positive_months,
            historical_candidate_passed=historical,
            same_config_full_control_available=False,
            causal_comparison="No same-config 10-month off/off counterfactual; descriptive totals are not full-period causal attribution.")
        robustness_report = dict(**robustness, capital70=_metric_summary(capital, 70),
                                 delay500=_metric_summary(delay))
    elif descriptive:
        if (descriptive.get("eligible") is not False or descriptive.get("promotion") is not False
                or batch.get("qualified") is not False or lock is not None):
            raise ValueError("R8 descriptive replay must remain ineligible")
        tag = descriptive.get("config_tag")
        if tag not in TREATMENTS or descriptive.get("selected_from") != "development_only":
            raise ValueError("R8 descriptive selection provenance mismatch")
        row = treatment_rows[tag]
        chosen = max(treatment_rows.values(), key=lambda x:(x["result"]["net"],
                     -x["result"]["native_equity_dd_pct"], x["config_tag"]))
        if survivors_dev:
            chosen = max((cell for key, cell in treatment_rows.items() if key in survivors_dev),
                         key=lambda x:(x["result"]["net"], -x["result"]["native_equity_dd_pct"], x["config_tag"]))
        need(chosen["config_tag"] == tag, "R8 descriptive replay does not match frozen development-only choice")
        detail = _validate_run(descriptive.get("result", {}), "r8_b_descriptive10m", baseline_sig,
            start=START, end=END, mode=1, params=_params(*TREATMENTS[tag]), details=True,
            tester_login=batch["tester_connection_login"])
        full_report = dict(**_metric_summary(detail), eligible=False,
            same_config_full_control_available=False,
            causal_comparison="No same-config 10-month off/off counterfactual; descriptive totals are not full-period causal attribution.")
    else:
        if batch.get("qualified") is not False or lock is not None:
            raise ValueError("R8 has neither validation selection nor eligible descriptive branch")

    return dict(qualification="ATTRIBUTION_ONLY_NOT_RELEASE_QUALIFICATION",
        evidence_root="reports/v25_research_20261008_postupdate", promotion=False,
        genuinely_unseen_oos=False,
        baseline=dict(**_metric_summary(baseline), native_v24_parity=v24_parity),
        controls=dict(r1_control=r1_name, off_off=R8_OFF_RUN,
            parity=parity_row, off_off_stats=_metric_summary(off), r1_dev_stats=_metric_summary(r1)),
        treatments=output_treatments, selection_lock=lock,
        validation={tag: _metric_summary(run) for tag, run in sorted(val_runs.items())},
        confirmation=confirmation_report, full_period=full_report,
        economic_robustness=robustness_report,
        warnings=["Post-selection historical mechanism research, not genuinely unseen OOS.",
            "Unmatched control winners are descriptive; no removed trade is called a saved loss.",
            "No same-config 10-month off/off control exists; no full-period causal claim.",
            "Held/breaker callbacks are censored execution contexts, retained in gate counts, not strategy exclusions."])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    report = analyze()
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.stdout:
        print(text)
    else:
        target = BASE / "r8_b_attribution.json"
        target.write_text(text + "\n", encoding="utf-8")
        print(json.dumps(dict(report=str(target.relative_to(ROOT)), qualification=report["qualification"],
                              treatments=len(report["treatments"]))))


if __name__ == "__main__":
    main()
