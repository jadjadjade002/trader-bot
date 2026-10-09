"""Strict, read-only attribution for accepted R5 C0 development replays."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from research.analyze_v23_backtest import bucket, csv_rows, finite, parse_deals, report_rows
from research import run_v25_native as native_runner

ROOT = Path(__file__).resolve().parents[1]
R4_BASE = ROOT / "reports/v25_research_20261007"
R5_BASE = ROOT / "reports/v25_research_20261008"
R5_ALLOWED_ROOTS = {
    "reports/v25_research_20261008",
    "reports/v25_research_20261008_postupdate",
}
R5_SOURCE = ROOT / "research/ResearchCandidate_R5.mq5"
R5_BINARY = ROOT / "research/ResearchCandidate_R5.ex5"
R4_SOURCE = ROOT / "research/ResearchCandidate_R4.mq5"
R4_BINARY = ROOT / "research/ResearchCandidate_R4.ex5"
R5_SOURCE_SHA256 = "98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494"
R5_BINARY_SHA256 = "842722988E75991E79996EC0C969B8115ABF18EBFFD5C1E9AD49F217B7F2A320"
R4_SOURCE_SHA256 = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"
R4_BINARY_SHA256 = "1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9"
PERIOD_START, PERIOD_END = "2025.12.01", "2026.06.01"
MONTHS = ("2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05")
R5_CONFIGS = {f"p{preset}_a{int(aligned)}_c0": (preset, aligned)
              for preset in (0, 1) for aligned in (False, True)}
R4_RUNS = {
    0: "r4_a_dev_5_0_sl1p5_tp1p0",
    1: "r4_a_dev_5_1_sl1p5_tp1p0",
}
FEATURE_FIELDS = (
    "m1_ema9", "m1_ema20", "m5_ema20", "m5_ema50", "m5_ema20_past6",
    "m5_slope_5bar_delta", "m1_atr", "m5_atr", "signed_displacement_atr_5bars",
    "signal_bar_open", "signal_bar_high", "signal_bar_low", "signal_bar_close",
    "signal_body_atr",
)
OPTIONAL_FEATURE_FIELDS = (
    "quote_bid", "quote_ask", "spread", "initial_sl_distance", "initial_tp_distance",
    "initial_sl_price", "initial_tp_price", "close_location_from_low",
)
SIGNAL_REQUIRED = {
    "bar", "tick_msc", "mode", "entry_strength", "signal", "trend", "reason",
    "execution_gate", "held_before", "order_attempt", "features_evaluated",
    "opportunity_status", *FEATURE_FIELDS, *OPTIONAL_FEATURE_FIELDS,
    "session_id", "session_endpoint", "time_to_close",
}
RAW_REQUIRED = {"bar", "tick_msc", "original", "held_before", "gate",
                "order_attempt", "retcode", "order_ticket", "deal_ticket"}
RUNTIME_NAMES = ("terminal64.exe", "metatester64.exe")
FIXED_SET = {
    "InpEnableSessionGuard": "false", "InpEnableSpreadGuard": "false",
    "InpEnableMarginGuard": "true", "InpEnableHardSL": "true",
    "InpMaxHoldBars": "60", "InpMinSLPoints": "150", "InpLotSize": "0.01",
    "InpFadeBreakouts": "false", "InpMagicNumber": "992300", "InpTargetAccount": "0",
    "InpEnableCircuitBreaker": "true", "InpMaxConsecutiveLosses": "4",
    "InpCooldownMinutes": "90", "InpATRPeriod": "14", "InpDonchianPeriod": "20",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _finite(value: Any, label: str) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required numeric value: {label}")
    number = finite(value)
    if not math.isfinite(number):
        raise ValueError(f"Nonfinite numeric value: {label}")
    return number


def _strict_int(value: Any, label: str) -> int:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid integer: {label}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Noninteger value: {label}")
    return int(number)


def _bool(value: Any, label: str) -> bool:
    token = str(value).strip().lower()
    if token in ("true", "1"):
        return True
    if token in ("false", "0"):
        return False
    raise ValueError(f"Invalid boolean {label}: {value!r}")


def _decimal_text(value: Any, label: str) -> str:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal {label}: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Nonfinite decimal {label}")
    return format(number.normalize(), "f")


def _parse_set(text: str, label: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError(f"Malformed SET line in {label}")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"Duplicate SET input {key}")
        values[key] = value
    return values


def _load_set(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-16")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"SET file missing or unreadable: {path.name}") from exc
    return _parse_set(text, path.name)


def _check_current_artifacts():
    for path, expected in ((R5_SOURCE, R5_SOURCE_SHA256), (R5_BINARY, R5_BINARY_SHA256),
                           (R4_SOURCE, R4_SOURCE_SHA256), (R4_BINARY, R4_BINARY_SHA256)):
        if not path.is_file() or _sha(path) != expected:
            raise ValueError(f"Current artifact SHA256 mismatch: {path.name}")
    source_text = R5_SOURCE.read_text(encoding="utf-8")
    required_source = (
        "ReadClosed(entryFast,1,ema9)", "ReadClosed(entrySlow,1,ema20)",
        "CopyRates(_Symbol,PERIOD_M1,1,count,r)",
        "r5DisplacementATR=(r[1].close-r[6].close)/atr",
        "r5SignalBodyATR=MathAbs(r[0].close-r[0].open)/atr",
        "(r[0].close-r[0].low)/signalRange",
    )
    for marker in required_source:
        if marker not in source_text:
            raise ValueError(f"R5 source context contract changed: {marker}")


def _validate_signature(signature: dict[str, Any], *, name: str, preset: int,
                        aligned: bool | None, source_sha: str, binary_sha: str,
                        r4: bool, run_dir: Path, evidence_root: Path):
    _require(signature.get("start") == PERIOD_START and signature.get("end") == PERIOD_END,
             f"Wrong replay period in signature: {name}")
    _require(signature.get("mode") == 5 and signature.get("deposit") == 10000,
             f"Wrong mode/deposit in signature: {name}")
    _require(signature.get("optimize") is False and signature.get("production") is False
             and signature.get("delay_ms") == 200, f"Wrong tester execution contract: {name}")
    _require(signature.get("source_sha") == source_sha and signature.get("binary_sha") == binary_sha,
             f"Stored source/binary signature mismatch: {name}")
    overrides = signature.get("overrides")
    expected_overrides: dict[str, Any] = {
        "InpEntryStrength": preset, "InpStopLossATRMul": 1.5,
        "InpTakeProfitRRMul": 1.0,
    }
    if aligned is not None:
        expected_overrides["InpRequireM1Alignment"] = aligned
    _require(overrides == expected_overrides, f"Unexpected inputs in stored signature: {name}")
    ticks = signature.get("tick_cache")
    expected_month_ids = [int(m.replace("-", "")) for m in MONTHS]
    if not isinstance(ticks, list) or [row.get("month") for row in ticks] != expected_month_ids:
        raise ValueError(f"Stored tick cache month coverage mismatch: {name}")
    for row in ticks:
        if not isinstance(row.get("bytes"), int) or row["bytes"] < 1024:
            raise ValueError(f"Stored tick cache size invalid: {name}")
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", str(row.get("sha256", ""))):
            raise ValueError(f"Stored tick cache hash invalid: {name}")
    runtime_path = evidence_root / "runtime_freeze.json"
    if not runtime_path.is_file():
        raise ValueError(f"Runtime freeze missing for {name}")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    _require(signature.get("runtime") == runtime, f"Runtime signature differs from freeze: {name}")
    set_path = run_dir / f"{name}.set"
    if not set_path.is_file():
        raise ValueError(f"SET hash mismatch or missing SET: {name}")
    try:
        set_text = set_path.read_text(encoding="utf-16")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"SET hash mismatch or unreadable SET: {name}") from exc
    normalized_set_sha = hashlib.sha256(set_text.encode("utf-16")).hexdigest()
    if normalized_set_sha.lower() != str(signature.get("set_sha", "")).lower():
        raise ValueError(f"SET hash mismatch or missing SET: {name}")
    values = _parse_set(set_text, set_path.name)
    if values.get("InpRunTag") != name or values.get("InpExperimentMode") != "5":
        raise ValueError(f"SET run identity mismatch: {name}")
    if values.get("InpEntryStrength") != str(preset):
        raise ValueError(f"SET preset mismatch: {name}")
    for key, value in FIXED_SET.items():
        if values.get(key) != value:
            raise ValueError(f"SET fixed gate drift {key}: {name}")
    if values.get("InpStopLossATRMul") != "1.5" or values.get("InpTakeProfitRRMul") != "1.0":
        raise ValueError(f"SET SL/TP mismatch: {name}")
    if not r4:
        if values.get("InpRequireM1Alignment", "").lower() != str(aligned).lower():
            raise ValueError(f"SET alignment mismatch: {name}")
        if values.get("InpEnableSessionGuard") != "false" or values.get("InpEnableSpreadGuard") != "false":
            raise ValueError(f"R5 C0 gate mismatch: {name}")
    elif "InpRequireM1Alignment" in values:
        raise ValueError(f"R4 control SET unexpectedly contains R5 input: {name}")


def _load_run(evidence_root: Path, name: str, preset: int, *, aligned: bool | None,
              r4: bool = False, load_signals: bool = False) -> dict[str, Any]:
    run_dir = evidence_root / "runs" / name
    accepted_path = run_dir / "accepted.json"
    if not accepted_path.is_file():
        raise ValueError(f"Run not accepted; refusing partial or missing artifacts: {name}")
    try:
        accepted = json.loads(accepted_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Accepted record unreadable or incomplete: {name}") from exc
    if not isinstance(accepted, dict) or not isinstance(accepted.get("signature"), dict) or not isinstance(accepted.get("result"), dict):
        raise ValueError(f"Accepted record schema incomplete: {name}")
    signature, result = accepted["signature"], accepted["result"]
    _validate_signature(signature, name=name, preset=preset, aligned=aligned,
        source_sha=R4_SOURCE_SHA256 if r4 else R5_SOURCE_SHA256,
        binary_sha=R4_BINARY_SHA256 if r4 else R5_BINARY_SHA256,
        r4=r4, run_dir=run_dir, evidence_root=evidence_root)
    started_path = run_dir / "started.json"
    if not started_path.is_file():
        raise ValueError(f"Run start manifest missing: {name}")
    try:
        started = json.loads(started_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Run start manifest unreadable: {name}") from exc
    if not isinstance(started, dict) or started.get("signature") != signature:
        raise ValueError(f"Started/accepted signature mismatch: {name}")
    if result.get("evidence_run") != name or result.get("cache_hashes_verified") is not True:
        raise ValueError(f"Accepted result identity/cache status mismatch: {name}")
    if result.get("terminal_cache_read_warnings") not in ([], None):
        raise ValueError(f"Accepted result has terminal cache warnings: {name}")
    if result.get("native_mql_fixture_checks") != (25 if r4 else 27):
        raise ValueError(f"Unexpected native fixture count: {name}")
    native = result.get("native")
    if not isinstance(native, dict) or native.get("History Quality") != "100% real ticks":
        raise ValueError(f"Accepted run lacks 100% real-tick evidence: {name}")
    if "M1 (2025.12.01 - 2026.06.01)" not in native.get("Period", ""):
        raise ValueError(f"Accepted native report period mismatch: {name}")
    report_path = run_dir / f"{name}.htm"
    if not report_path.is_file():
        raise ValueError(f"Native HTML report missing: {name}")
    html_metrics, _ = report_rows(report_path)
    if html_metrics != native:
        raise ValueError(f"Accepted summary differs from native HTML report: {name}")
    deals_path = run_dir / f"{name}_deals.csv"
    if not deals_path.is_file():
        raise ValueError(f"Native deals export missing: {name}")
    deals_rows = csv_rows(deals_path)
    if not deals_rows:
        raise ValueError(f"Native deals export empty: {name}")
    trades, cash = parse_deals(deals_rows)
    _require(len(cash) == 1 and cash[0]["type"] == 2 and abs(cash[0]["net"] - 10000) <= 0.021,
             f"Unexpected cash adjustments: {name}")
    summary = bucket(trades)
    _require(summary["trades"] == int(_finite(native.get("Total Trades"), f"{name} native trades")),
             f"Position count does not reconcile: {name}")
    _require(abs(summary["net"] - _finite(native.get("Total Net Profit"), f"{name} native net")) <= 0.021,
             f"Position net does not reconcile: {name}")
    _require(summary["trades"] == result.get("trades") and abs(summary["net"] - result.get("net", math.inf)) <= 0.021,
             f"Accepted summary differs from deal ledger: {name}")
    specs_path = run_dir / f"{name}_spec.csv"
    if not specs_path.is_file():
        raise ValueError(f"Native history/balance specification export missing: {name}")
    specs = {row.get("key"): row.get("value") for row in csv_rows(specs_path)}
    if specs.get("history_export_ok") not in ("true", "1"):
        raise ValueError(f"Native history export did not reconcile: {name}")
    final_balance = _finite(specs.get("final_balance"), f"{name} final balance")
    if abs(final_balance - 10000 - summary["net"]) > 0.021:
        raise ValueError(f"Native final balance differs from deposit plus ledger net: {name}")
    if result.get("final_balance") is None or abs(final_balance - _finite(result["final_balance"], f"{name} accepted final balance")) > 0.021:
        raise ValueError(f"Accepted final balance differs from native history export: {name}")
    run = dict(name=name, root=evidence_root, directory=run_dir, accepted=accepted,
               signature=signature, result=result, native=native, trades=trades,
               cash=cash, summary=summary, deals_rows=deals_rows, final_balance=final_balance)
    if load_signals:
        signals_path = run_dir / f"{name}_signals.csv"
        if not signals_path.is_file():
            raise ValueError(f"Native signal export missing: {name}")
        signals = csv_rows(signals_path)
        if not signals or not SIGNAL_REQUIRED <= set(signals[0]):
            raise ValueError(f"Native signal schema incomplete: {name}")
        signals = validate_signals(signals, name, preset)
        raw_path = run_dir / f"{name}_raw.csv"
        if not raw_path.is_file():
            raise ValueError(f"Native raw execution export missing: {name}")
        raw_rows = csv_rows(raw_path)
        if not raw_rows or not RAW_REQUIRED <= set(raw_rows[0]):
            raise ValueError(f"Native raw execution schema incomplete: {name}")
        raw = validate_raw(raw_rows, name)
        run["signals"] = signals
        run["raw"] = raw
        run["entry_event_keys"] = _link_raw_events(raw, signals, trades, deals_rows, name)
    return run


def _mql_epoch_ms(label: str, name: str) -> int:
    try:
        moment = datetime.strptime(label, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed broker-encoded MQL bar time in {name}: {label!r}") from exc
    # This is numeric consistency arithmetic only; it makes no UTC market-time claim.
    return int(moment.timestamp() * 1000)


def validate_signals(rows: list[dict[str, str]], name: str, preset: int) -> list[dict[str, Any]]:
    parsed = []
    last_bar = -1
    last_tick = -1
    for index, original in enumerate(rows, 1):
        row = dict(original)
        if _strict_int(row["mode"], f"{name} signal mode") != 5 or _strict_int(row["entry_strength"], f"{name} strength") != preset:
            raise ValueError(f"Signal row identity mismatch {name}:{index}")
        bar_ms = _mql_epoch_ms(row["bar"], name)
        tick_ms = _strict_int(row["tick_msc"], f"{name} tick_msc")
        if bar_ms <= last_bar or tick_ms <= last_tick or not (bar_ms <= tick_ms < bar_ms + 60000):
            raise ValueError(f"Stale or unordered signal context {name}:{index}")
        last_bar, last_tick = bar_ms, tick_ms
        features = _bool(row["features_evaluated"], f"{name} features_evaluated")
        status = row["opportunity_status"]
        if status not in {"context_evaluated", "censored_held_position",
                          "censored_circuit_breaker", "blocked_before_context"}:
            raise ValueError(f"Unknown signal opportunity status {name}:{index}: {status!r}")
        if features != (status == "context_evaluated"):
            raise ValueError(f"Feature/status inconsistency or stale features {name}:{index}")
        if row["session_id"] != "n/a" or row["session_endpoint"] != "n/a" or row["time_to_close"] != "n/a":
            raise ValueError(f"C0 session fields must be explicit n/a: {name}:{index}")
        if status == "censored_held_position":
            if row["execution_gate"] != "held_position" or not _bool(row["held_before"], f"{name} held_before"):
                raise ValueError(f"Held-position censor marker inconsistent: {name}:{index}")
        if status == "censored_circuit_breaker" and row["execution_gate"] != "circuit_breaker":
            raise ValueError(f"Breaker censor marker inconsistent: {name}:{index}")
        if not features:
            if any(str(row[field]).strip() for field in (*FEATURE_FIELDS, *OPTIONAL_FEATURE_FIELDS)):
                raise ValueError(f"Unavailable/stale feature values must be blank: {name}:{index}")
        else:
            for field in FEATURE_FIELDS:
                value = _finite(row[field], f"{name}:{index}:{field}")
                if field in ("m1_ema9", "m1_ema20", "m5_ema20", "m5_ema50", "m5_ema20_past6", "m1_atr", "m5_atr", "signal_bar_open", "signal_bar_high", "signal_bar_low", "signal_bar_close") and value <= 0:
                    raise ValueError(f"Nonpositive feature {name}:{index}:{field}")
                if field == "signal_body_atr" and value < 0:
                    raise ValueError(f"Negative signal body/ATR {name}:{index}")
            signal_range = float(row["signal_bar_high"]) - float(row["signal_bar_low"])
            close_location = row["close_location_from_low"].strip()
            if signal_range == 0:
                if close_location:
                    raise ValueError(f"Flat signal bar must have unavailable close location: {name}:{index}")
            elif not (0 <= _finite(close_location, f"{name}:{index}:close_location_from_low") <= 1):
                raise ValueError(f"Signal close location outside [0,1]: {name}:{index}")
            for field in OPTIONAL_FEATURE_FIELDS[:-1]:
                if row[field].strip():
                    value = _finite(row[field], f"{name}:{index}:{field}")
                    if field in ("quote_bid", "quote_ask", "initial_sl_distance", "initial_tp_distance", "initial_sl_price", "initial_tp_price") and value <= 0:
                        raise ValueError(f"Nonpositive optional feature {name}:{index}:{field}")
                    if field == "spread" and value < 0:
                        raise ValueError(f"Negative spread {name}:{index}")
        row["_bar_msc"] = bar_ms
        row["_tick_msc"] = tick_ms
        row["_features"] = features
        row["_signal"] = _strict_int(row["signal"], f"{name}:{index}:signal")
        row["_trend"] = _strict_int(row["trend"], f"{name}:{index}:trend")
        if row["_signal"] not in (-1, 0, 1) or row["_trend"] not in (-1, 0, 1):
            raise ValueError(f"Signal/trend side outside {-1, 0, 1}: {name}:{index}")
        row["_attempt"] = _bool(row["order_attempt"], f"{name}:{index}:order_attempt")
        row["_held"] = _bool(row["held_before"], f"{name}:{index}:held_before")
        if features:
            e9, e20 = float(row["m1_ema9"]), float(row["m1_ema20"])
            row["_m1_relation"] = "up" if e9 > e20 else "down" if e9 < e20 else "equal"
        else:
            row["_m1_relation"] = "unavailable"
        parsed.append(row)
    return parsed


def validate_raw(rows: list[dict[str, str]], name: str) -> list[dict[str, Any]]:
    parsed = []
    prior_bar = prior_tick = -1
    for index, original in enumerate(rows, 1):
        row = dict(original)
        bar_ms = _mql_epoch_ms(row["bar"], name)
        tick_ms = _strict_int(row["tick_msc"], f"{name} raw tick_msc")
        if bar_ms <= prior_bar or tick_ms <= prior_tick or not (bar_ms <= tick_ms < bar_ms + 60000):
            raise ValueError(f"Stale or unordered raw execution context {name}:{index}")
        prior_bar, prior_tick = bar_ms, tick_ms
        side = _strict_int(row["original"], f"{name} raw side")
        if side not in (-1, 0, 1):
            raise ValueError(f"Raw side outside {-1, 0, 1}: {name}:{index}")
        attempt = _bool(row["order_attempt"], f"{name} raw order_attempt")
        if attempt != (row["gate"] == "order_attempt"):
            raise ValueError(f"Raw attempt/gate mismatch {name}:{index}")
        retcode = _strict_int(row["retcode"], f"{name} raw retcode")
        order_ticket = _strict_int(row["order_ticket"], f"{name} raw order_ticket")
        deal_ticket = _strict_int(row["deal_ticket"], f"{name} raw deal_ticket")
        if min(retcode, order_ticket, deal_ticket) < 0:
            raise ValueError(f"Negative raw execution identifier {name}:{index}")
        if not attempt and (retcode or order_ticket or deal_ticket):
            raise ValueError(f"Raw result IDs present without order attempt {name}:{index}")
        row.update(_bar_msc=bar_ms, _tick_msc=tick_ms, _side=side,
                   _attempt=attempt, _order_ticket=order_ticket, _deal_ticket=deal_ticket)
        parsed.append(row)
    return parsed


def _event_key(row: dict[str, Any]) -> tuple[int, int]:
    return row["_bar_msc"], row["_tick_msc"]


def _link_raw_events(raw: list[dict[str, Any]], signals: list[dict[str, Any]],
                     trades: list[dict[str, Any]], deal_rows: list[dict[str, str]],
                     name: str) -> dict[tuple[int, str, str, str], tuple[int, int]]:
    raw_by_event, signal_by_event = {}, {}
    for label, rows, target in (("raw", raw, raw_by_event), ("signal", signals, signal_by_event)):
        for row in rows:
            key = _event_key(row)
            if key in target:
                raise ValueError(f"Duplicate {label} event key {name}: {key}")
            target[key] = row
    if set(raw_by_event) != set(signal_by_event):
        raise ValueError(f"Raw/signal event sets differ: {name}")
    for key, signal in signal_by_event.items():
        event = raw_by_event[key]
        if (signal["_signal"] != event["_side"]
                or signal["_attempt"] != event["_attempt"]
                or signal["_held"] != _bool(event["held_before"], f"{name} raw held_before")
                or signal["execution_gate"] != event["gate"]):
            raise ValueError(f"Raw/signal event mismatch: {name} {key}")

    opening_by_ticket = {}
    for row in deal_rows:
        if int(row["type"]) in (0, 1) and int(row["entry"]) == 0:
            ticket = _strict_int(row["ticket"], f"{name} opening deal ticket")
            if ticket <= 0 or ticket in opening_by_ticket:
                raise ValueError(f"Duplicate or invalid opening deal ticket: {name} {ticket}")
            opening_by_ticket[ticket] = row
    raw_by_deal = {}
    for event_key, event in raw_by_event.items():
        ticket = event["_deal_ticket"]
        if ticket:
            if not event["_attempt"] or ticket not in opening_by_ticket:
                raise ValueError(f"Raw deal ticket has no matching opening deal: {name} {ticket}")
            if ticket in raw_by_deal:
                raise ValueError(f"Opening deal ticket linked by multiple raw events: {name} {ticket}")
            raw_by_deal[ticket] = event

    linked = {}
    seen_positions = set()
    for trade in trades:
        position = trade["position"]
        if position in seen_positions:
            raise ValueError(f"Multiple positions share opening-event attribution: {name} {position}")
        seen_positions.add(position)
        opens = [deal for deal in trade["deals"] if deal["entry"] == 0]
        if len(opens) != 1:
            raise ValueError(f"Unsupported multiple opening deals for position: {name} {position}")
        opening = opens[0]
        if abs(opening["volume"] - 0.01) > 1e-8 or abs(opening["volume"] - trade["volume"]) > 1e-8:
            raise ValueError(f"Opening volume violates fixed 0.01-lot contract: {name} {position}")
        expected_type = 0 if trade["direction"] == "buy" else 1
        if opening["type"] != expected_type or opening["position"] != position:
            raise ValueError(f"Opening deal side/position mismatch: {name} {position}")
        event = raw_by_deal.get(opening["ticket"])
        if event is None:
            raise ValueError(f"Trade opening has no exact raw deal-ticket event: {name} {position}")
        event_key = _event_key(event)
        signal = signal_by_event[event_key]
        if (not event["_attempt"] or event["_side"] != expected_type_to_side(expected_type)
                or signal["_signal"] != event["_side"]):
            raise ValueError(f"Opening event side/attempt mismatch: {name} {position}")
        if event["_tick_msc"] > opening["time_msc"]:
            raise ValueError(f"Opening deal predates its raw event: {name} {position}")
        if not signal["_features"]:
            raise ValueError(f"Opening event has unavailable signal features: {name} {position}")
        linked[_entry_key(trade)] = event_key
    if len(linked) != len(trades) or len(raw_by_deal) != len(trades):
        raise ValueError(f"Opening positions and exact raw deal events do not reconcile: {name}")
    return linked


def expected_type_to_side(deal_type: int) -> int:
    return 1 if deal_type == 0 else -1


def _entry_key(trade: dict[str, Any]) -> tuple[int, str, str, str]:
    return (int(trade["open_msc"]), trade["direction"],
            _decimal_text(trade["entry_price"], "entry price"),
            _decimal_text(trade["volume"], "entry volume"))


def _side_code(side: str) -> int:
    return 1 if side == "buy" else -1


def _signal_entries(run: dict[str, Any]) -> dict[tuple[int, str, str, str], dict[str, Any]]:
    signals_by_event: dict[tuple[int, int], dict[str, Any]] = {}
    for row in run["signals"]:
        key = _event_key(row)
        if key in signals_by_event:
            raise ValueError(f"Duplicate signal event in attributed run: {run['name']} {key}")
        signals_by_event[key] = row
    contexts = {}
    for trade in run["trades"]:
        key = _entry_key(trade)
        event_key = run.get("entry_event_keys", {}).get(key)
        row = signals_by_event.get(event_key)
        if event_key is None or row is None:
            raise ValueError(f"Entry lacks exact native deal-event signal context: {run['name']} {key}")
        if (not row["_features"] or row["_tick_msc"] > int(trade["open_msc"])
                or row["_signal"] != _side_code(trade["direction"])):
            raise ValueError(f"Entry signal context unavailable, future, or wrong-side: {run['name']} {key}")
        e9, e20 = float(row["m1_ema9"]), float(row["m1_ema20"])
        relation = row["_m1_relation"]
        aligned = relation == ("up" if trade["direction"] == "buy" else "down")
        context = dict(
            m1_ema9=e9, m1_ema20=e20, m1_relation=relation,
            m5_ema20=float(row["m5_ema20"]), m5_ema50=float(row["m5_ema50"]),
            m5_trend=row["_trend"], aligned_with_entry=aligned,
            signal_bar=row["bar"], signal_tick_msc=row["_tick_msc"],
        )
        contexts[key] = context
    return contexts


def _economic_deal_sequence(run: dict[str, Any]) -> list[tuple[Any, ...]]:
    rows = []
    for row in run["deals_rows"]:
        if int(row["type"]) not in (0, 1):
            continue
        rows.append((int(row["time_msc"]), int(row["type"]), int(row["entry"]),
            int(row["reason"]), _decimal_text(row["volume"], "deal volume"),
            _decimal_text(row["price"], "deal price"), _decimal_text(row["profit"], "deal profit"),
            _decimal_text(row["commission"], "deal commission"), _decimal_text(row["swap"], "deal swap"),
            _decimal_text(row["fee"], "deal fee")))
    return rows


def _trade_detail(trade: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {key: trade[key] for key in ("position", "open_msc", "close_msc", "direction",
        "entry_price", "exit_price", "volume", "net", "profit", "commission", "swap", "fee", "exit_reason")}
    if context is not None:
        row["m1_context"] = context
    return row


def _breakdown(trades: list[dict[str, Any]], labeler, labels) -> dict[str, Any]:
    out = {}
    for label in labels:
        selected = [trade for trade in trades if labeler(trade) == label]
        out[str(label)] = bucket(selected)
    return out


def _month_label(trade: dict[str, Any]) -> str:
    # parse_deals formats MQL epoch values as broker-encoded labels; no UTC claim.
    return str(trade["close"])[:7]


def _statistics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(
        total=bucket(trades),
        sides=_breakdown(trades, lambda t: t["direction"], ("buy", "sell")),
        exits=_breakdown(trades, lambda t: str(t["exit_reason"]),
                         sorted({str(t["exit_reason"]) for t in trades})),
        close_months=_breakdown(trades, _month_label, MONTHS),
    )


def _entry_summary(trades: list[dict[str, Any]], contexts: dict[tuple[int, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    decorated = []
    for trade in trades:
        key = _entry_key(trade)
        context = contexts.get(key)
        if context is None:
            raise ValueError(f"Entry cohort lacks EMA context: {key}")
        decorated.append((trade, context))
    alignment = {}
    for side in ("buy", "sell"):
        subset = [(t, c) for t, c in decorated if t["direction"] == side]
        aligned = [(t, c) for t, c in subset if c["aligned_with_entry"]]
        misaligned = [(t, c) for t, c in subset if not c["aligned_with_entry"]]
        alignment[side] = dict(
            entries=len(subset), aligned=len(aligned), misaligned=len(misaligned),
            aligned_entry_net=bucket([t for t, _ in aligned]),
            misaligned_entry_net=bucket([t for t, _ in misaligned]),
        )
    return dict(entries=len(decorated), alignment_by_entry_side=alignment,
        entry_rows=[dict(key=list(_entry_key(t)), trade=_trade_detail(t, c)) for t, c in decorated])


def _signal_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(row["opportunity_status"] for row in rows)
    evaluated = [row for row in rows if row["_features"]]
    relations = Counter(row["_m1_relation"] for row in evaluated)
    by_side = {}
    for side, code in (("buy", 1), ("sell", -1)):
        selected = [row for row in evaluated if row["_trend"] == code]
        by_side[side] = dict(context_rows=len(selected),
            ema9_above_ema20=sum(row["_m1_relation"] == "up" for row in selected),
            ema9_below_ema20=sum(row["_m1_relation"] == "down" for row in selected),
            ema_equal=sum(row["_m1_relation"] == "equal" for row in selected))
    return dict(
        scope="Logged fresh-bar rows only; censored held/breaker rows remain explicit; not all market opportunities.",
        logged_fresh_bar_rows=len(rows), features_evaluated=len(evaluated),
        feature_context_missing=len(rows)-len(evaluated), status_counts=dict(sorted(statuses.items())),
        actual_m1_ema9_vs_ema20=dict(sorted(relations.items())),
        context_by_m5_trend_side=by_side,
        censored_held_position=statuses.get("censored_held_position", 0),
        censored_circuit_breaker=statuses.get("censored_circuit_breaker", 0),
    )


def _delta(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    keys = ("trades", "wins", "losses", "zero", "net", "profit", "commission", "swap", "fee")
    return {key: round(float(b[key])-float(a[key]), 8) for key in keys}


def _pair_comparison(a0: dict[str, Any], a1: dict[str, Any]) -> dict[str, Any]:
    t0, t1 = a0["trades"], a1["trades"]
    m0 = {_entry_key(t): t for t in t0}
    m1 = {_entry_key(t): t for t in t1}
    if len(m0) != len(t0) or len(m1) != len(t1):
        raise ValueError("Duplicate canonical entry key; pairing ambiguous")
    common = sorted(set(m0) & set(m1))
    only0, only1 = sorted(set(m0)-set(m1)), sorted(set(m1)-set(m0))
    paired0, paired1 = [m0[k] for k in common], [m1[k] for k in common]
    unmatched0, unmatched1 = [m0[k] for k in only0], [m1[k] for k in only1]
    all0, all1 = bucket(t0), bucket(t1)
    common0, common1 = bucket(paired0), bucket(paired1)
    left, right = bucket(unmatched0), bucket(unmatched1)
    decomposition = round((common1["net"]-common0["net"])+right["net"]-left["net"], 2)
    if abs(decomposition-(all1["net"]-all0["net"])) > 0.021:
        raise ValueError("Paired/unmatched net decomposition does not reconcile")
    c0, c1 = _signal_entries(a0), _signal_entries(a1)
    details = []
    for key in common:
        details.append(dict(key=list(key), a0=_trade_detail(m0[key], c0[key]),
            a1=_trade_detail(m1[key], c1[key]),
            delta_net=round(m1[key]["net"]-m0[key]["net"], 8)))
    return dict(
        a0=a0["name"], a1=a1["name"],
        totals=dict(a0=all0, a1=all1, a1_minus_a0=_delta(all0, all1)),
        paired=dict(count=len(common), a0=common0, a1=common1,
                    a1_minus_a0=_delta(common0, common1)),
        unmatched=dict(a0_count=len(only0), a0=left, a1_count=len(only1), a1=right,
                       a1_minus_a0_net=round(right["net"]-left["net"], 2)),
        decomposition=dict(paired_delta=round(common1["net"]-common0["net"], 2),
                           a1_unmatched_net=right["net"], a0_unmatched_net=left["net"],
                           reconstructed_total_delta=decomposition,
                           observed_total_delta=round(all1["net"]-all0["net"], 2)),
        all_paired_entries=details,
        all_unmatched_entries=dict(
            a0=[dict(key=list(k), trade=_trade_detail(m0[k], c0[k])) for k in only0],
            a1=[dict(key=list(k), trade=_trade_detail(m1[k], c1[k])) for k in only1]),
        dimensions=dict(
            all_a0=_statistics(t0), all_a1=_statistics(t1),
            paired_a0=_statistics(paired0), paired_a1=_statistics(paired1),
            unmatched_a0=_statistics(unmatched0), unmatched_a1=_statistics(unmatched1),
        ),
        entry_alignment=dict(a0=_entry_summary(t0, c0), a1=_entry_summary(t1, c1)),
        signal_coverage=dict(a0=_signal_coverage(a0["signals"]), a1=_signal_coverage(a1["signals"])),
    )


def _r4_r5_control(r4: dict[str, Any], r5: dict[str, Any]) -> dict[str, Any]:
    r4_seq, r5_seq = _economic_deal_sequence(r4), _economic_deal_sequence(r5)
    if r4_seq != r5_seq:
        raise ValueError(f"R5 A0 deal economics differ from accepted R4 control: {r4['name']}")
    t4 = {_entry_key(t): t for t in r4["trades"]}
    t5 = {_entry_key(t): t for t in r5["trades"]}
    if set(t4) != set(t5):
        raise ValueError(f"R5 A0 entry set differs from accepted R4 control: {r4['name']}")
    return dict(r4_control=r4["name"], r5_a0=r5["name"], passed=True,
                compared_trade_deals=len(r4_seq), positions=len(t4),
                net=r4["summary"]["net"], net_difference=round(r5["summary"]["net"]-r4["summary"]["net"], 8),
                native_metrics_equal=all(r4["native"].get(k) == r5["native"].get(k) for k in
                    ("Total Net Profit", "Gross Profit", "Gross Loss", "Total Trades", "Ticks", "Bars", "History Quality", "Equity Drawdown Maximal", "Balance Drawdown Maximal")))


def _load_r5_progress(r5_base: Path, prefix: str) -> dict[str, Any]:
    progress_path = r5_base / f"{prefix}_progress.json"
    if not progress_path.is_file():
        raise ValueError(f"R5 progress manifest missing; refusing to infer run mapping: {prefix}")
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    if progress.get("round_label") != "R5" or progress.get("schedule_status") != "UNRUN_SCHEDULE_UNVERIFIED":
        raise ValueError(f"R5 progress manifest contract mismatch: {prefix}")
    return progress


def _r5_control_mapping(progress: dict[str, Any], prefix: str) -> tuple[str, dict[int, str]]:
    """Resolve controls only from one of the two frozen root policies."""
    policy = progress.get("control_policy")
    raw_mapping = progress.get("control_mapping")
    if policy not in {"legacy_r4", "fresh_same_cache"}:
        raise ValueError(f"R5 control policy missing or unsupported: {policy!r}")
    if not isinstance(raw_mapping, dict) or set(raw_mapping) != {"0", "1"}:
        raise ValueError("R5 control mapping must contain exact preset keys 0 and 1")
    mapping = {preset: raw_mapping[str(preset)] for preset in (0, 1)}
    if any(not isinstance(name, str) for name in mapping.values()):
        raise ValueError("R5 control mapping names must be strings")
    if policy == "legacy_r4":
        expected = R4_RUNS
    else:
        expected = {preset: f"{prefix}_r4_control_p{preset}" for preset in (0, 1)}
    if mapping != expected:
        raise ValueError(f"R5 control mapping conflicts with {policy} policy")
    expected_alias = "r4_base" if policy == "legacy_r4" else "r5_base"
    expected_roots = {"baseline_production": expected_alias, "r4_controls": expected_alias}
    if progress.get("control_roots") != expected_roots:
        raise ValueError("R5 control root aliases conflict with selected policy")
    evidence_roots = progress.get("evidence_roots")
    if not isinstance(evidence_roots, dict) or set(evidence_roots) != {"r4_base", "r5_base"}:
        raise ValueError("R5 evidence roots must declare exact r4_base and r5_base aliases")
    if evidence_roots.get("r4_base") != "reports/v25_research_20261007":
        raise ValueError("R5 legacy control evidence root is not approved")
    if evidence_roots.get("r5_base") not in R5_ALLOWED_ROOTS:
        raise ValueError("R5 evidence root is not approved")
    expected_baseline = f"{prefix}_production_v24" if policy == "fresh_same_cache" else "r1_b_production_v24"
    if progress.get("baseline_control_run") != expected_baseline:
        raise ValueError("R5 baseline control run conflicts with selected policy")
    provenance = progress.get("r4_control_provenance")
    if not isinstance(provenance, dict) or set(provenance) != {"0", "1"}:
        raise ValueError("R5 control provenance must contain exact preset keys 0 and 1")
    expected_kind = "accepted_reuse" if policy == "legacy_r4" else "fresh_native"
    expected_root = ("reports/v25_research_20261007" if policy == "legacy_r4"
                     else evidence_roots["r5_base"])
    for preset in (0, 1):
        record = provenance[str(preset)]
        if (not isinstance(record, dict)
                or record.get("kind") != expected_kind
                or record.get("evidence_run") != mapping[preset]
                or record.get("evidence_root") != expected_root
                or record.get("source_sha256") != R4_SOURCE_SHA256
                or not re.fullmatch(r"[0-9A-F]{64}", str(record.get("signature_sha256", "")))
                or record.get("native_run_id") != (mapping[preset] if policy == "fresh_same_cache" else None)):
            raise ValueError(f"R5 control provenance missing or inconsistent for preset {preset}")
    return policy, mapping


def _control_root(policy: str, r4_base: Path, r5_base: Path) -> Path:
    if policy == "legacy_r4":
        return r4_base
    if policy == "fresh_same_cache":
        return r5_base
    raise ValueError(f"Unsupported R5 control root policy: {policy!r}")


def _validate_declared_roots(progress: dict[str, Any], r4_base: Path, r5_base: Path) -> None:
    roots = progress["evidence_roots"]
    expected_r4 = (ROOT / "reports/v25_research_20261007").resolve()
    if (ROOT / roots["r4_base"]).resolve() != expected_r4:
        raise ValueError("Manifest R4 root is not the fixed approved root")
    expected_r5 = (ROOT / roots["r5_base"]).resolve()
    if r4_base.resolve() != expected_r4 or r5_base.resolve() != expected_r5:
        raise ValueError("Caller evidence roots differ from validated manifest aliases")


def _validate_control_signature_provenance(progress: dict[str, Any], controls: dict[int, dict[str, Any]]) -> None:
    provenance = progress["r4_control_provenance"]
    for preset, run in controls.items():
        encoded = json.dumps(run["signature"], sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
        actual = hashlib.sha256(encoded).hexdigest().upper()
        if provenance[str(preset)]["signature_sha256"] != actual:
            raise ValueError(f"R5 control signature provenance mismatch for preset {preset}")


def _r5_run_mapping(r5_base: Path, prefix: str) -> dict[str, tuple[str, int, bool]]:
    progress = _load_r5_progress(r5_base, prefix)
    _, control_mapping = _r5_control_mapping(progress, prefix)
    rows = progress.get("development")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError(f"R5 progress manifest must contain exactly four development cells: {prefix}")
    mapped = {}
    for row in rows:
        tag = row.get("config_tag")
        if tag not in R5_CONFIGS or tag in mapped:
            raise ValueError(f"Duplicate or unknown R5 config tag in progress manifest: {tag!r}")
        preset, aligned = R5_CONFIGS[tag]
        parameters = row.get("parameters", {})
        if (row.get("mode") != 5 or parameters.get("InpEntryStrength") != preset
                or parameters.get("InpRequireM1Alignment") is not aligned
                or parameters.get("InpStopLossATRMul") != 1.5
                or parameters.get("InpTakeProfitRRMul") != 1.0):
            raise ValueError(f"R5 progress parameters mismatch: {tag}")
        result = row.get("result")
        name = result.get("evidence_run") if isinstance(result, dict) else None
        expected = re.fullmatch(rf"{re.escape(prefix)}_dev_{re.escape(tag)}(?:_retry[1-2])?", str(name))
        if not expected:
            raise ValueError(f"R5 progress evidence run/prefix mismatch: {tag}: {name!r}")
        mapped[tag] = (name, preset, aligned)
    if set(mapped) != set(R5_CONFIGS):
        raise ValueError("R5 progress manifest does not cover exact frozen four-cell matrix")
    parity = progress.get("r4_control_parity", {})
    expected_alias = "r4_base" if progress["control_policy"] == "legacy_r4" else "r5_base"
    for preset in (0, 1):
        tag = f"p{preset}_a0_c0"
        record = parity.get(str(preset), {})
        if (record.get("passed") is not True
                or record.get("r4_control") != control_mapping[preset]
                or record.get("control_root") != expected_alias
                or record.get("r5_run") != mapped[tag][0]
                or record.get("control_provenance") != progress["r4_control_provenance"][str(preset)]):
            raise ValueError(f"R4 A0 control parity missing or mismatched for preset {preset}")
    return {f"p{p}_a{int(a)}": mapped[f"p{p}_a{int(a)}_c0"]
            for p in (0, 1) for a in (False, True)}


def _validate_cross_run_environment(runs: list[dict[str, Any]]) -> None:
    if not runs:
        raise ValueError("No accepted runs to validate")
    reference_runtime = runs[0]["signature"].get("runtime")
    reference_ticks = runs[0]["signature"].get("tick_cache")
    for run in runs:
        signature = run["signature"]
        if signature.get("runtime") != reference_runtime:
            raise ValueError(f"Runtime differs across accepted runs: {run['name']}")
        if signature.get("tick_cache") != reference_ticks:
            raise ValueError(f"Tick cache manifest differs across accepted runs: {run['name']}")


def _validate_baseline_environment(progress, prefix, r4_base, r5_base, runs):
    """Independently revalidate full-period controls before interpreting six-month cells."""
    baseline = progress.get("baseline")
    name = baseline.get("evidence_run") if isinstance(baseline, dict) else None
    if not re.fullmatch(rf"{re.escape(prefix)}_baseline(?:_retry[1-2])?", str(name)):
        raise ValueError("R5 mode0 baseline identity mismatch")
    production_root = r5_base if progress["control_policy"] == "fresh_same_cache" else r4_base
    production_name = progress["baseline_control_run"]
    records = []
    for result, root, production in ((baseline, r5_base, False),
            ({"evidence_run": production_name}, production_root, True)):
        run_name = result["evidence_run"]
        signature = native_runner.verified_signature(result, root)
        accepted = json.loads((root / "runs" / run_name / "accepted.json").read_text(encoding="utf-8-sig"))
        actual_result = accepted["result"]
        expected_source = native_runner.SOURCE_HASH if production else R5_SOURCE_SHA256
        expected_binary = native_runner.BINARY_HASH if production else R5_BINARY_SHA256
        expected_set = native_runner.settings(run_name, 0, {}, production=production,
                                              r2=not production, r5=not production)
        _require(signature.get("start") == native_runner.START and signature.get("end") == native_runner.END
            and signature.get("mode") == 0 and signature.get("overrides") == {}
            and signature.get("deposit") == 10000 and signature.get("delay_ms") == 200
            and signature.get("optimize") is False and signature.get("production") is production
            and signature.get("source_sha") == expected_source and signature.get("binary_sha") == expected_binary,
            "Full-period baseline source/settings contract mismatch")
        set_path = root / "runs" / run_name / f"{run_name}.set"
        actual_set = set_path.read_text(encoding="utf-16")
        _require(actual_set == expected_set and signature.get("set_sha") ==
            hashlib.sha256(actual_set.encode("utf-16")).hexdigest(), "Baseline SET signature mismatch")
        html, _ = report_rows(root / "runs" / run_name / f"{run_name}.htm")
        _require(actual_result.get("native") == html and html.get("History Quality") == "100% real ticks"
            and actual_result.get("cache_hashes_verified") is True, "Baseline native HTML/cache mismatch")
        if not production:
            _require(actual_result == baseline and actual_result.get("native_mql_fixture_checks") == 27,
                     "Progress mode0 result differs from accepted baseline")
        records.append(actual_result)
    parity = native_runner.parity(records[1], records[0], evidence_base=r5_base,
                                 production_base=production_root)
    for run in runs:
        native_runner.verify_environment(records[0], run["result"], evidence_base=run["root"],
                                         reference_base=r5_base)
    return dict(production=production_name, mode0=name, parity=parity, accepted_environments_checked=2+len(runs))


def analyze(r4_base: Path = R4_BASE, r5_base: Path = R5_BASE,
            prefix: str = "r5_a") -> dict[str, Any]:
    _check_current_artifacts()
    progress = _load_r5_progress(r5_base, prefix)
    control_policy, control_mapping = _r5_control_mapping(progress, prefix)
    _validate_declared_roots(progress, r4_base, r5_base)
    run_mapping = _r5_run_mapping(r5_base, prefix)
    r5: dict[str, dict[str, Any]] = {}
    for cell, (name, preset, aligned) in run_mapping.items():
        r5[cell] = _load_run(r5_base, name, preset, aligned=aligned,
                             load_signals=True)
    control_root = _control_root(control_policy, r4_base, r5_base)
    controls_loaded = {preset: _load_run(control_root, name, preset, aligned=None, r4=True)
                       for preset, name in control_mapping.items()}
    _validate_control_signature_provenance(progress, controls_loaded)
    _validate_cross_run_environment([*r5.values(), *controls_loaded.values()])
    baseline_environment = _validate_baseline_environment(progress, prefix, r4_base, r5_base,
        [*r5.values(), *controls_loaded.values()])
    controls = {}
    comparisons = {}
    for preset in (0, 1):
        a0 = r5[f"p{preset}_a0"]
        a1 = r5[f"p{preset}_a1"]
        controls[str(preset)] = _r4_r5_control(controls_loaded[preset], a0)
        if not controls[str(preset)]["native_metrics_equal"]:
            raise ValueError(f"R5 A0 native metrics mismatch R4 for preset {preset}")
        comparison = _pair_comparison(a0, a1)
        misaligned_a1 = comparison["entry_alignment"]["a1"]["alignment_by_entry_side"]
        if any(metrics["misaligned"] for metrics in misaligned_a1.values()):
            raise ValueError(f"R5 A1 entered with M1 EMA misalignment for preset {preset}")
        comparisons[f"p{preset}"] = comparison
    return dict(
        status="R5 C0 development attribution only; not V25 qualification or release evidence",
        period=dict(start=PERIOD_START, end=PERIOD_END, interval="[start,end)",
                    clock="broker-encoded MQL timestamps; no UTC conversion claim"),
        contract=dict(source_sha256=R5_SOURCE_SHA256, binary_sha256=R5_BINARY_SHA256,
            risk=dict(sl_atr=1.5, tp_r=1.0, minimum_sl_points=150), mode=5, closure_policy="C0",
            control_policy=control_policy, control_mapping={str(k): v for k, v in control_mapping.items()},
            evidence_inputs="accepted.json + native deals + native signals; incomplete runs rejected"),
        baseline_environment=baseline_environment, r4_a0_controls=controls,
        comparisons=comparisons,
        caveat="Signal coverage counts only logged fresh-bar rows. Held/breaker bars are censored and counted. No denominator represents every potential market opportunity.",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-root", type=Path, default=R4_BASE)
    parser.add_argument("--r5-root", type=Path, default=R5_BASE)
    parser.add_argument("--prefix", default="r5_a",
                        help="R5 runner prefix; run identity comes from validated progress manifest")
    parser.add_argument("--output", type=Path,
                        help="Optional authored JSON report; must remain under the R5 evidence root")
    args = parser.parse_args(argv)
    result = analyze(args.r4_root.resolve(), args.r5_root.resolve(), args.prefix)
    rendered = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        out = args.output.resolve()
        if not out.is_relative_to(args.r5_root.resolve()):
            raise ValueError("Output must remain inside R5 evidence root")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return result


if __name__ == "__main__":
    main()
