"""Fail-closed offline auditor for R12 structural retest/risk telemetry.

The auditor checks emitted native context, quote geometry and native cash-risk
results. It never computes account-currency risk from tick-value metadata and
never assigns PnL to a rejected or censored setup.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Iterable, Mapping


RAW_COLUMNS = (
    "bar", "tick_msc", "original", "closeback", "dc_low", "dc_high", "atr",
    "break_close", "retest_open", "retest_close", "retest_high", "retest_low",
    "bid", "ask", "held_before", "cooldown_before", "gate", "order_attempt",
    "retcode", "order_ticket", "deal_ticket",
)
PARENT_SIGNAL_COLUMNS = (
    "bar", "tick_msc", "mode", "entry_strength", "signal", "trend", "reason",
    "body_atr", "close_location", "entry_level", "execution_gate", "held_before",
    "order_attempt",
)
STRUCTURAL_COLUMNS = (
    "structural_enabled", "features_evaluated", "bid_chart_mode",
    "signal_bar_s1", "setup_bar_s2", "reference_bar_s3", "signal_bid", "signal_ask",
    "decision_bid", "decision_ask", "s1_open", "s1_high", "s1_low", "s1_close",
    "s2_open", "s2_high", "s2_low", "s2_close", "s3_high", "s3_low", "atr_s1",
    "atr_s2", "ema9_s1", "ema9_s2", "setup_body_atr", "setup_close_location",
    "setup_range_atr", "retest_body_atr", "retest_close_location", "structural_sl",
    "structural_tp", "point", "tick_size", "stops_level", "freeze_level",
    "stop_distance_close_side", "target_distance_close_side", "equity", "planned_risk",
    "cash_risk_cap", "risk_calc_valid", "geometry_evaluated", "risk_evaluated",
)
SIGNAL_COLUMNS = PARENT_SIGNAL_COLUMNS + STRUCTURAL_COLUMNS

STRUCTURAL_REASONS = {
    "structural_invalid_atr", "structural_trend_unaligned",
    "structural_chart_mode_unsupported", "structural_history_unavailable",
    "structural_bar_gap", "structural_invalid_bar", "structural_indicator_unavailable",
    "structural_setup_absent", "structural_retest_absent",
    "structural_quote_unavailable", "structural_cost_or_chase",
    "structural_geometry_invalid", "structural_broker_distance",
    "structural_cash_risk_calc_failed", "structural_cash_risk_veto",
    "structural_entry",
}
EXECUTION_GATES = {
    "structural_quote_unavailable", "structural_cost_or_chase",
    "structural_geometry_invalid", "structural_broker_distance",
    "structural_cash_risk_calc_failed", "structural_cash_risk_veto",
}
SUCCESS_RETCODES = {10009, 10010}
SERIAL_HALF = Decimal("0.00000000000000005")  # DoubleToString(...,16) output interval
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
NUMERIC_FIELDS = tuple(c for c in STRUCTURAL_COLUMNS if c not in {
    "structural_enabled", "features_evaluated", "bid_chart_mode",
    "signal_bar_s1", "setup_bar_s2", "reference_bar_s3",
    "risk_calc_valid", "geometry_evaluated", "risk_evaluated",
})
CONTEXT_FIELDS = (
    "signal_bar_s1", "setup_bar_s2", "reference_bar_s3", "signal_bid", "signal_ask",
    "decision_bid", "decision_ask", "s1_open", "s1_high", "s1_low", "s1_close",
    "s2_open", "s2_high", "s2_low", "s2_close", "s3_high", "s3_low", "atr_s1",
    "atr_s2", "ema9_s1", "ema9_s2", "setup_body_atr", "setup_close_location",
    "setup_range_atr", "retest_body_atr", "retest_close_location", "structural_sl",
    "structural_tp", "point", "tick_size", "stops_level", "freeze_level",
    "stop_distance_close_side", "target_distance_close_side", "equity", "planned_risk",
    "cash_risk_cap",
)
QUOTE_FIELDS = ("signal_bid", "signal_ask", "decision_bid", "decision_ask")
OHLC_FIELDS = (
    ("s1_open", "s1_high", "s1_low", "s1_close"),
    ("s2_open", "s2_high", "s2_low", "s2_close"),
)
PRECONTEXT_REASONS = {
    "structural_invalid_atr", "structural_trend_unaligned",
    "structural_chart_mode_unsupported", "structural_history_unavailable",
    "structural_bar_gap", "structural_invalid_bar", "structural_indicator_unavailable",
}
BLOCKED_BEFORE_SIGNAL = "not_evaluated_execution_block"


class StructuralAuditError(ValueError):
    """R12 rows violate the preregistered native telemetry contract."""


def _fail(message: str) -> None:
    raise StructuralAuditError(message)


def _bool(value, label: str) -> bool:
    if isinstance(value, bool):
        _fail(f"{label} must serialize as true/false/1/0")
    token = str(value).strip().lower()
    if token in ("true", "1"):
        return True
    if token in ("false", "0"):
        return False
    _fail(f"{label} must serialize as true/false/1/0")


def _int(value, label: str, *, minimum: int | None = None) -> int:
    token = str(value).strip()
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", token):
        _fail(f"{label} is not a canonical integer")
    result = int(token)
    if minimum is not None and result < minimum:
        _fail(f"{label} is below minimum")
    return result


def _float(value, label: str, *, blank_ok: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if blank_ok:
            return None
        _fail(f"{label} is blank")
    if isinstance(value, bool):
        _fail(f"{label} is not numeric")
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        _fail(f"{label} is not numeric")
    if not math.isfinite(result):
        _fail(f"{label} is nonfinite")
    return result


def _decimal(value, label: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        _fail(f"{label} is not a decimal token")
    if not result.is_finite():
        _fail(f"{label} is nonfinite")
    return result


def _cash_relation(risk_value, cap_value) -> str:
    risk, cap = _decimal(risk_value, "planned_risk"), _decimal(cap_value, "cash_risk_cap")
    if risk - SERIAL_HALF > cap + SERIAL_HALF:
        return "over"
    if risk + SERIAL_HALF <= cap - SERIAL_HALF:
        return "under_or_equal"
    return "ambiguous"


def _cap_matches_equity(equity_value, cap_value) -> bool:
    equity, cap = _decimal(equity_value, "equity"), _decimal(cap_value, "cash_risk_cap")
    expected = equity * Decimal("0.025")
    arithmetic = Decimal(str(math.ulp(float(expected)))) / 2
    tol = SERIAL_HALF * Decimal("1.025") + arithmetic
    return abs(cap - expected) <= tol


def _time(value, label: str, *, blank_ok: bool = False) -> datetime | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if blank_ok:
            return None
        _fail(f"{label} is blank")
    if not isinstance(value, str):
        _fail(f"{label} must be a timestamp string")
    try:
        parsed = datetime.strptime(value, TIME_FORMAT)
    except ValueError:
        _fail(f"{label} has invalid timestamp")
    if parsed.strftime(TIME_FORMAT) != value:
        _fail(f"{label} is not canonical")
    return parsed


def _rows(source: Iterable[Mapping], columns: tuple[str, ...], label: str) -> list[Mapping]:
    if isinstance(source, (str, bytes)):
        _fail(f"{label} must be CSV row mappings")
    result = list(source)
    if not result:
        _fail(f"{label} is empty")
    for i, row in enumerate(result):
        if not isinstance(row, Mapping) or tuple(row.keys()) != columns:
            _fail(f"{label} exact {len(columns)}-column schema/order mismatch at row {i}")
    return result


def _key(row: Mapping, label: str) -> tuple[str, int]:
    bar = row.get("bar")
    _time(bar, f"{label}.bar")
    tick = _int(row.get("tick_msc"), f"{label}.tick_msc", minimum=1)
    return bar, tick


def _unique(rows: list[Mapping], label: str) -> dict[tuple[str, int], Mapping]:
    result = {}
    for i, row in enumerate(rows):
        key = _key(row, f"{label}[{i}]")
        if key in result:
            _fail(f"{label} duplicate (bar,tick_msc) key {key}")
        result[key] = row
    return result


def _blank(value, label: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return
    _fail(f"{label} must be blank when unevaluated")


def _near(actual: float, expected: float, label: str, *, tol: float = 1e-10) -> None:
    if abs(actual - expected) > tol:
        _fail(f"{label} differs from reconstructed value: {actual} != {expected}")


def _mql_tick_round(price: float, tick: float, digits: int, upward: bool) -> float:
    units = price / tick
    units = math.ceil(units) if upward else math.floor(units)
    # R12 multiplies by tick directly; no NormalizeDouble call in native source.
    return units * tick


def _setup(side: int, s: Mapping) -> bool:
    o, h, l, c = (_float(s[x], x) for x in ("s2_open", "s2_high", "s2_low", "s2_close"))
    atr, ema, level = (_float(s[x], x) for x in ("atr_s2", "ema9_s2", "entry_level"))
    span = h - l
    if span <= 0:
        return False
    body = c - o if side == 1 else o - c
    body_atr = abs(c - o) / atr
    location = (c - l) / span if side == 1 else (h - c) / span
    range_atr = span / atr
    return (
        body > 0 and not (body_atr < 0.30) and not (location < 0.80) and not (range_atr > 2.0)
        and (c > level + 0.10 * atr if side == 1 else c < level - 0.10 * atr)
        and (c > ema if side == 1 else c < ema)
    )


def _retest(side: int, s: Mapping) -> bool:
    o, h, l, c = (_float(s[x], x) for x in ("s1_open", "s1_high", "s1_low", "s1_close"))
    ema, level = (_float(s[x], x) for x in ("ema9_s1", "entry_level"))
    if side == 1:
        return l <= level and c > o and c > level and c > ema
    return h >= level and c < o and c < level and c < ema


def _quote_ok(side: int, bid: float, ask: float, close: float, atr: float) -> bool:
    if bid <= 0 or ask < bid or atr <= 0:
        return False
    return ask - bid <= 0.10 * atr and abs((ask + bid) / 2.0 - close) <= 0.50 * atr


def audit_structural(raw_rows: Iterable[Mapping], signal_rows: Iterable[Mapping], *,
                     enabled: bool, mode: int, point, tick_size, digits: int) -> dict:
    """Audit R12 setup/retest, executable quote, stop/TP, broker and cash-risk fields.

    `planned_risk` is accepted only as a native OrderCalcProfit result. It is
    never reconstructed from price movement or tick-value metadata.
    """
    if type(enabled) is not bool:
        _fail("enabled must be an exact bool")
    if type(mode) is not int or mode not in (0, 1):
        _fail("mode must be exact integer 0 or 1")
    if type(digits) is not int or not 0 <= digits <= 12:
        _fail("digits must be an exact integer in [0,12]")
    p = _float(point, "point")
    ts = _float(tick_size, "tick_size")
    if p <= 0 or ts <= 0:
        _fail("point and tick_size must be positive")
    point_units = ts / p
    if abs(point_units - round(point_units)) > 1e-9:
        _fail("tick_size must be representable on point grid")

    raw = _rows(raw_rows, RAW_COLUMNS, "raw_rows")
    diag = _rows(signal_rows, SIGNAL_COLUMNS, "signal_rows")
    rmap, smap = _unique(raw, "raw_rows"), _unique(diag, "signal_rows")
    if rmap.keys() != smap.keys():
        _fail("raw/signals joins are not exact 1:1")
    ordered = sorted(rmap, key=lambda k: (datetime.strptime(k[0], TIME_FORMAT), k[1]))
    if list(rmap) != ordered:
        _fail("raw rows are not chronologically ordered")

    counts = {
        "rows": len(raw), "joined_rows": 0, "off_bypass_rows": 0,
        "features_evaluated": 0, "setup_pass": 0, "retest_pass": 0,
        "quote_pass": 0, "geometry_evaluated": 0, "broker_distance_pass": 0,
        "risk_evaluated": 0, "risk_valid": 0, "cash_risk_veto": 0,
        "cash_risk_calc_failures": 0, "margin_blocks": 0,
        "order_attempts": 0, "successful_fills": 0, "cash_threshold_ambiguous": 0,
        "risk_ambiguous_serialization": 0,
        "reason_counts": {}, "gate_counts": {},
    }
    successful_order_events = []
    active = enabled
    expected_preset = 2 if mode == 1 else 0
    if enabled and mode != 1:
        _fail("structural switch may be on only in mode 1")

    for key in ordered:
        r, s = rmap[key], smap[key]
        counts["joined_rows"] += 1
        row_mode = _int(s["mode"], f"mode at {key}")
        preset = _int(s["entry_strength"], f"entry_strength at {key}")
        if row_mode != mode or preset != expected_preset:
            _fail(f"mode/preset differs from fixed R12 contract at {key}")
        signal = _int(s["signal"], f"signal at {key}")
        raw_side = _int(r["original"], f"raw original at {key}")
        if signal not in (-1, 0, 1) or raw_side not in (-1, 0, 1) or signal != raw_side:
            _fail(f"raw/diagnostic side mismatch at {key}")
        attempt = _bool(r["order_attempt"], f"raw.order_attempt at {key}")
        if attempt != _bool(s["order_attempt"], f"signals.order_attempt at {key}"):
            _fail(f"raw/diagnostic order_attempt mismatch at {key}")
        held = _bool(r["held_before"], f"raw.held_before at {key}")
        if held != _bool(s["held_before"], f"signals.held_before at {key}"):
            _fail(f"raw/diagnostic held state mismatch at {key}")
        if r["gate"] != s["execution_gate"] or not r["gate"]:
            _fail(f"raw/diagnostic execution gate mismatch at {key}")
        if attempt != (r["gate"] == "order_attempt"):
            _fail(f"raw order_attempt inconsistent with gate at {key}")
        reason = str(s["reason"]).strip()
        gate = str(r["gate"]).strip()
        counts["reason_counts"][reason] = counts["reason_counts"].get(reason, 0) + 1
        counts["gate_counts"][gate] = counts["gate_counts"].get(gate, 0) + 1
        retcode = _int(r["retcode"], f"raw.retcode at {key}", minimum=0)
        order_ticket_value = _int(r["order_ticket"], f"raw.order_ticket at {key}", minimum=0)
        deal_ticket_value = _int(r["deal_ticket"], f"raw.deal_ticket at {key}", minimum=0)
        if attempt and retcode == 0:
            _fail(f"native order attempt lacks returned trade retcode at {key}")
        if not attempt and (retcode != 0 or order_ticket_value != 0 or deal_ticket_value != 0):
            _fail(f"native trade result fields populated without order attempt at {key}")
        if attempt:
            counts["order_attempts"] += 1
            if retcode in SUCCESS_RETCODES:
                order_ticket = _int(r["order_ticket"], f"order_ticket at {key}", minimum=1)
                deal_ticket = _int(r["deal_ticket"], f"deal_ticket at {key}", minimum=1)
                counts["successful_fills"] += 1
                successful_order_events.append({
                    "bar": key[0], "tick_msc": key[1], "side": _int(s["signal"], f"signal at {key}"),
                    "retcode": retcode, "order_ticket": order_ticket, "deal_ticket": deal_ticket,
                    "decision_bid": s["decision_bid"], "decision_ask": s["decision_ask"],
                    "structural_sl": s["structural_sl"], "structural_tp": s["structural_tp"],
                })
        if gate == "margin_block":
            counts["margin_blocks"] += 1

        enabled_row = _bool(s["structural_enabled"], f"structural_enabled at {key}")
        features = _bool(s["features_evaluated"], f"features_evaluated at {key}")
        chart = str(s["bid_chart_mode"]).strip().lower()
        geometry = _bool(s["geometry_evaluated"], f"geometry_evaluated at {key}")
        risk_eval = _bool(s["risk_evaluated"], f"risk_evaluated at {key}")
        valid_token = s["risk_calc_valid"]
        if valid_token is None or not str(valid_token).strip():
            if risk_eval:
                _fail(f"risk_calc_valid blank after actual native call at {key}")
            valid_calc = False
        else:
            if not risk_eval:
                _fail(f"risk_calc_valid populated without native call at {key}")
            valid_calc = _bool(valid_token, f"risk_calc_valid at {key}")
        if enabled_row is not active:
            _fail(f"structural_enabled differs from fixed run contract at {key}")
        if valid_calc and not risk_eval:
            _fail(f"risk_calc_valid without native risk evaluation at {key}")

        if not active:
            if features or geometry or risk_eval or valid_calc or chart not in {"false", "0"}:
                _fail(f"structural OFF row evaluated or enabled telemetry at {key}")
            for name in CONTEXT_FIELDS:
                _blank(s[name], f"OFF {name} at {key}")
            if attempt:
                if retcode not in SUCCESS_RETCODES and retcode == 0:
                    _fail(f"OFF order attempt lacks native trade result at {key}")
            counts["off_bypass_rows"] += 1
            continue

        if reason not in STRUCTURAL_REASONS and reason != BLOCKED_BEFORE_SIGNAL:
            _fail(f"unknown R12 reason {reason!r} at {key}")
        if features:
            counts["features_evaluated"] += 1
            if chart not in {"true", "1"}:
                _fail(f"features evaluated on non-Bid chart at {key}")
            event_bar = datetime.strptime(key[0], TIME_FORMAT)
            bars = {
                "signal_bar_s1": event_bar - timedelta(minutes=1),
                "setup_bar_s2": event_bar - timedelta(minutes=2),
                "reference_bar_s3": event_bar - timedelta(minutes=3),
            }
            for field, expected in bars.items():
                if _time(s[field], f"{field} at {key}") != expected:
                    _fail(f"R12 completed-bar time/index mismatch at {key}: {field}")
            vals = {name: _float(s[name], f"{name} at {key}") for name in NUMERIC_FIELDS
                    if name not in {"signal_bid", "signal_ask", "decision_bid", "decision_ask",
                                    "structural_sl", "structural_tp", "point", "tick_size",
                                    "stops_level", "freeze_level", "stop_distance_close_side",
                                    "target_distance_close_side", "equity", "planned_risk", "cash_risk_cap",
                                    "setup_body_atr", "setup_close_location", "setup_range_atr",
                                    "retest_body_atr", "retest_close_location"}}
            for name in ("s1_open", "s1_high", "s1_low", "s1_close",
                         "s2_open", "s2_high", "s2_low", "s2_close",
                         "s3_high", "s3_low"):
                x = _float(s[name], f"{name} at {key}")
                if x <= 0:
                    _fail(f"nonpositive OHLC price at {key}: {name}")
            for o, h, l, c in OHLC_FIELDS:
                ov, hv, lv, cv = (_float(s[n], f"{n} at {key}") for n in (o, h, l, c))
                if hv < max(ov, cv, lv) or lv > min(ov, cv, hv):
                    _fail(f"incoherent OHLC at {key}")
            s3h, s3l = _float(s["s3_high"], "s3_high"), _float(s["s3_low"], "s3_low")
            if s3h < s3l:
                _fail(f"incoherent s3 high/low at {key}")
            atr1 = _float(s["atr_s1"], "atr_s1 at key")
            atr2 = _float(s["atr_s2"], "atr_s2 at key")
            ema1 = _float(s["ema9_s1"], "ema9_s1 at key")
            ema2 = _float(s["ema9_s2"], "ema9_s2 at key")
            if min(atr1, atr2, ema1, ema2) <= 0:
                _fail(f"nonpositive ATR/EMA in evaluated context at {key}")
            for name, expected in (("point", p), ("tick_size", ts)):
                value = _float(s[name], f"{name} at {key}", blank_ok=True)
                if value is not None:
                    if value <= 0:
                        _fail(f"invalid exported {name} at {key}")
                    _near(value, expected, f"exported {name}", tol=1e-14)
            for a, b, label in (("stops_level", "freeze_level", "broker levels"),):
                av = _float(s[a], f"{a} at {key}", blank_ok=True)
                bv = _float(s[b], f"{b} at {key}", blank_ok=True)
                if (av is None) != (bv is None):
                    _fail(f"partial {label} telemetry at {key}")
                if av is not None and (av < 0 or bv < 0 or av != math.floor(av) or bv != math.floor(bv)):
                    _fail(f"invalid {label} telemetry at {key}")
            side = _int(s["trend"], f"trend at {key}")
            if side not in (-1, 0, 1):
                _fail(f"trend outside -1/0/1 at {key}")
            if signal != 0 and (side == 0 or signal != side):
                _fail(f"signal side does not match inherited trend at {key}")
            level = _float(s["entry_level"], f"entry_level at {key}", blank_ok=(side == 0))
            if side != 0:
                expected_level = s3h if side == 1 else s3l
                if level is None:
                    _fail(f"trend-directed level missing at {key}")
                _near(level, expected_level, "entry level / s3 reference", tol=1e-10)
                numeric_context = {name: _float(s[name], f"{name} at {key}") for name in (
                    "s2_open", "s2_high", "s2_low", "s2_close", "atr_s2", "ema9_s2",
                    "s1_open", "s1_high", "s1_low", "s1_close", "atr_s1", "ema9_s1")}
                setup_context = {**s, **numeric_context, "entry_level": level}
                setup_ok = _setup(side, setup_context)
                s2o, s2h, s2l, s2c = (_float(s[n], n) for n in ("s2_open", "s2_high", "s2_low", "s2_close"))
                s1o, s1h, s1l, s1c = (_float(s[n], n) for n in ("s1_open", "s1_high", "s1_low", "s1_close"))
                s2range, s1range = s2h - s2l, s1h - s1l
                s2location = ((s2c - s2l) / s2range if side == 1 else (s2h - s2c) / s2range) if s2range > 0 else None
                s1location = ((s1c - s1l) / s1range if side == 1 else (s1h - s1c) / s1range) if s1range > 0 else None
                ratio_specs = []
                if reason not in {"structural_trend_unaligned", "structural_quote_unavailable"} or level is not None:
                    if s2range > 0:
                        ratio_specs.extend((
                            ("setup_body_atr", abs(s2c - s2o) / atr2),
                            ("setup_close_location", s2location),
                            ("setup_range_atr", s2range / atr2),
                        ))
                    else:
                        ratio_specs.extend((name, None) for name in ("setup_body_atr", "setup_close_location", "setup_range_atr"))
                    retest_stage_reached = reason not in {
                        "structural_setup_absent", "structural_trend_unaligned",
                        "structural_invalid_atr",
                    } and (reason != "structural_quote_unavailable" or level is not None)
                    if retest_stage_reached:
                        if s1range > 0:
                            ratio_specs.extend((
                                ("retest_body_atr", abs(s1c - s1o) / atr1),
                                ("retest_close_location", s1location),
                            ))
                        else:
                            ratio_specs.extend((name, None) for name in ("retest_body_atr", "retest_close_location"))
                for field, expected_ratio in ratio_specs:
                    observed = _float(s[field], f"{field} at {key}", blank_ok=True)
                    if expected_ratio is None:
                        if observed is not None:
                            _fail(f"undefined {field} must be blank at {key}")
                    elif observed is None:
                        _fail(f"defined {field} missing at {key}")
                    else:
                        _near(observed, expected_ratio, field)
                retest_body = _float(s["retest_body_atr"], f"retest_body_atr at {key}", blank_ok=True)
                retest_close = _float(s["retest_close_location"], f"retest_close_location at {key}", blank_ok=True)
                parent_body = _float(s["body_atr"], f"parent body_atr at {key}", blank_ok=True)
                parent_close = _float(s["close_location"], f"parent close_location at {key}", blank_ok=True)
                if retest_body is not None:
                    if retest_close is None or parent_body is None or parent_close is None:
                        _fail(f"computed retest metrics missing from parent diagnostics at {key}")
                    _near(parent_body, retest_body, "parent retest body diagnostic")
                    _near(parent_close, retest_close, "parent retest close-location diagnostic")
                elif any(value is not None for value in (retest_close, parent_body, parent_close)):
                    _fail(f"parent/retest diagnostics populated without valid retest metrics at {key}")
                if setup_ok:
                    counts["setup_pass"] += 1
                retest_ok = setup_ok and _retest(side, setup_context)
                if retest_ok:
                    counts["retest_pass"] += 1
                if reason == "structural_setup_absent" and setup_ok:
                    _fail(f"setup_absent reason contradicts measured setup at {key}")
                if reason == "structural_retest_absent" and (not setup_ok or retest_ok):
                    _fail(f"retest_absent reason contradicts measured setup/retest at {key}")
                if reason == "structural_entry" and not retest_ok:
                    _fail(f"entry reason contradicts measured setup/retest at {key}")
                if reason == "structural_trend_unaligned":
                    _fail(f"trend-unapplied reason has directional trend at {key}")
            elif reason == "structural_entry" or signal != 0:
                _fail(f"directional entry with unaligned trend at {key}")
            elif reason == "structural_trend_unaligned" and side != 0:
                _fail(f"trend-unapplied reason has directional signal at {key}")

            signal_quote = [_float(s[n], f"{n} at {key}", blank_ok=True) for n in ("signal_bid", "signal_ask")]
            decision_quote = [_float(s[n], f"{n} at {key}", blank_ok=True) for n in ("decision_bid", "decision_ask")]
            if any(x is not None for x in signal_quote):
                if any(x is None for x in signal_quote) or signal_quote[0] <= 0 or signal_quote[1] < signal_quote[0]:
                    _fail(f"invalid partial initial signal quote at {key}")
            if any(x is not None for x in decision_quote):
                if any(x is None for x in decision_quote) or decision_quote[0] <= 0 or decision_quote[1] < decision_quote[0]:
                    _fail(f"invalid partial decision quote at {key}")

            shape_ok = False
            side_for_shape = side if side != 0 else (_int(s["trend"], f"trend at {key}") or 0)
            if side_for_shape in (-1, 1):
                shape_ok = _setup(side_for_shape, {**s, "entry_level": level}) and _retest(side_for_shape, {**s, "entry_level": level})
            initial_ok = False
            decision_ok = False
            if shape_ok and all(v is not None for v in signal_quote):
                initial_ok = _quote_ok(side_for_shape, signal_quote[0], signal_quote[1],
                                       _float(s["s1_close"], "s1_close"), atr1)
            if shape_ok and all(v is not None for v in decision_quote):
                decision_ok = _quote_ok(side_for_shape, decision_quote[0], decision_quote[1],
                                        _float(s["s1_close"], "s1_close"), atr1)
            if reason == "structural_quote_unavailable":
                if all(v is not None for v in signal_quote) and all(v is not None for v in decision_quote):
                    _fail(f"quote-unavailable reason contradicts measured quote availability at {key}")
            if reason == "structural_cost_or_chase":
                if (not shape_ok or not all(v is not None for v in signal_quote)
                        or (initial_ok and (not all(v is not None for v in decision_quote) or decision_ok))):
                    _fail(f"cost/chase reason contradicts measured setup or quote thresholds at {key}")
            elif shape_ok and all(v is not None for v in signal_quote) and all(v is not None for v in decision_quote):
                if not (initial_ok and decision_ok):
                    _fail(f"setup/retest passed but quote cost/chase guard failed at {key}")

            broker_fields = ("point", "tick_size", "stops_level", "freeze_level")
            broker_values = [s[name] for name in broker_fields]
            broker_present = [v is not None and str(v).strip() for v in broker_values]
            if any(broker_present) and not all(broker_present):
                _fail(f"partial broker-property telemetry at {key}")
            geometry_fields = ("structural_sl", "structural_tp", "stop_distance_close_side", "target_distance_close_side")
            geometry_present = [s[name] is not None and str(s[name]).strip() for name in geometry_fields]
            if geometry and not all(geometry_present):
                _fail(f"geometry-evaluated row lacks complete price distances at {key}")
            if not geometry and any(geometry_present):
                _fail(f"geometry fields populated before successful geometry build at {key}")
            if geometry:
                if not shape_ok or not (initial_ok and decision_ok):
                    _fail(f"geometry was evaluated before setup/retest/quote passed at {key}")
                counts["quote_pass"] += 1
                if not all(broker_present):
                    _fail(f"geometry row lacks successful broker properties at {key}")
                _near(_float(s["point"], "point"), p, "exported point", tol=1e-14)
                _near(_float(s["tick_size"], "tick_size"), ts, "exported tick size", tol=1e-14)
                dbid, dask = decision_quote
                sl = _float(s["structural_sl"], f"structural_sl at {key}")
                tp = _float(s["structural_tp"], f"structural_tp at {key}")
                stops = _int(s["stops_level"], f"stops_level at {key}", minimum=0)
                freeze = _int(s["freeze_level"], f"freeze_level at {key}", minimum=0)
                stop_distance = _float(s["stop_distance_close_side"], f"stop distance at {key}")
                target_distance = _float(s["target_distance_close_side"], f"target distance at {key}")
                if side_for_shape == 1:
                    expected_sl = _mql_tick_round(_float(s["s1_low"], "s1_low") - ts, ts, digits, False)
                    risk_width = dask - expected_sl
                    expected_tp = _mql_tick_round(dask + 3.0 * risk_width, ts, digits, True)
                    expected_stop_distance = dbid - sl
                    expected_target_distance = tp - dbid
                else:
                    expected_sl = _mql_tick_round(
                        _float(s["s1_high"], "s1_high") + (dask - dbid) + ts, ts, digits, True)
                    risk_width = expected_sl - dbid
                    expected_tp = _mql_tick_round(dbid - 3.0 * risk_width, ts, digits, False)
                    expected_stop_distance = sl - dask
                    expected_target_distance = dask - tp
                _near(sl, expected_sl, "structural SL", tol=min(ts * 1e-7, 1e-9))
                _near(tp, expected_tp, "structural TP", tol=min(ts * 1e-7, 1e-9))
                if risk_width <= 0 or (side_for_shape == 1 and not (sl < dask and tp > dask)) or (side_for_shape == -1 and not (sl > dbid and tp < dbid)):
                    _fail(f"structural SL/TP side invalid at {key}")
                _near(stop_distance, expected_stop_distance, "stop distance from close-side quote")
                _near(target_distance, expected_target_distance, "target distance from close-side quote")
                broker_min = max(stops, freeze) * p + ts
                broker_ok = expected_stop_distance >= broker_min and expected_target_distance >= broker_min
                if broker_ok:
                    counts["broker_distance_pass"] += 1
                if reason == "structural_broker_distance":
                    if broker_ok or risk_eval or valid_calc or attempt:
                        _fail(f"broker-distance rejection contradicts reconstructed geometry at {key}")
                elif reason in {"structural_entry", "structural_cash_risk_veto", "structural_cash_risk_calc_failed"} or gate in {"margin_block", "order_attempt"}:
                    if not broker_ok:
                        _fail(f"later-stage outcome passed failed broker-distance guard at {key}")
            elif reason in {"structural_broker_distance", "structural_cash_risk_veto", "structural_cash_risk_calc_failed"} or gate in {"margin_block", "order_attempt"}:
                _fail(f"later-stage R12 outcome lacks completed geometry at {key}")
        else:
            if chart not in {"", "false", "0", "true", "1"}:
                _fail(f"unevaluated feature row has unsupported chart telemetry at {key}")
            if reason not in PRECONTEXT_REASONS and reason != BLOCKED_BEFORE_SIGNAL:
                _fail(f"features unavailable without pre-context failure reason at {key}")
            if reason == "structural_chart_mode_unsupported" and chart not in {"false", "0"}:
                _fail(f"unsupported chart reason does not report Bid-chart=false at {key}")
            if reason != "structural_chart_mode_unsupported" and chart in {"false", "0"} and reason not in {"structural_invalid_atr", BLOCKED_BEFORE_SIGNAL}:
                _fail(f"non-chart failure reports unsupported chart mode at {key}")
            allowed_nonblank = {"bid_chart_mode"}
            for name in CONTEXT_FIELDS:
                if name not in allowed_nonblank:
                    _blank(s[name], f"unevaluated {name} at {key}")
            if geometry or risk_eval or valid_calc or attempt:
                _fail(f"unevaluated context reached geometry/risk/order stage at {key}")

        if gate == "margin_block":
            if reason != "structural_entry" or signal not in (-1, 1):
                _fail(f"margin block without a qualified structural entry at {key}")
            if not risk_eval or not valid_calc:
                _fail(f"margin block did not follow a valid native cash-risk calculation at {key}")
        if gate == "order_attempt":
            if reason != "structural_entry" or signal not in (-1, 1):
                _fail(f"order attempt without a qualified structural entry at {key}")
            if not (features and geometry and risk_eval and valid_calc):
                _fail(f"order attempt skipped structural geometry/native risk at {key}")
        if reason == "structural_entry" and gate not in {"margin_block", "order_attempt"}:
            _fail(f"structural entry did not terminate in native margin/order gate at {key}")
        if reason in STRUCTURAL_REASONS - {"structural_entry"} and gate != reason:
            _fail(f"execution-stage reason/gate mismatch at {key}")
        if reason == BLOCKED_BEFORE_SIGNAL and gate not in {"held_position", "circuit_breaker", "no_new_bar"}:
            _fail(f"execution-block reason disagrees with gate at {key}")
        if reason == BLOCKED_BEFORE_SIGNAL and (features or signal != 0 or attempt):
            _fail(f"execution-blocked row must not evaluate or trade at {key}")

        if geometry:
            if not features:
                _fail(f"geometry evaluated without feature context at {key}")
        if active and geometry:
            counts["geometry_evaluated"] += 1
        if risk_eval:
            counts["risk_evaluated"] += 1
            if not geometry:
                _fail(f"native cash risk evaluated without geometry at {key}")
        if valid_calc:
            counts["risk_valid"] += 1
            equity = _float(s["equity"], f"equity at {key}")
            risk = _float(s["planned_risk"], f"planned_risk at {key}")
            cap = _float(s["cash_risk_cap"], f"cash_risk_cap at {key}")
            if min(equity, risk, cap) <= 0:
                _fail(f"valid cash-risk values must be positive loss/equity/cap at {key}")
            if not _cap_matches_equity(s["equity"], s["cash_risk_cap"]):
                _fail(f"cash-risk cap is not 2.5% of reported equity at {key}")
            relation = _cash_relation(s["planned_risk"], s["cash_risk_cap"])
            if relation == "ambiguous":
                counts["cash_threshold_ambiguous"] += 1
            if relation == "over":
                if gate != "structural_cash_risk_veto":
                    _fail(f"above-cap native planned risk was not vetoed at {key}")
            elif gate == "structural_cash_risk_veto" and relation == "under_or_equal":
                _fail(f"cash-risk veto is at/below cap at {key}")
        elif risk_eval:
            if gate != "structural_cash_risk_calc_failed" or attempt:
                _fail(f"invalid native cash-risk result lacks fail-closed calc gate at {key}")
            equity = _float(s["equity"], f"equity at {key}", blank_ok=True)
            risk = _float(s["planned_risk"], f"planned_risk at {key}", blank_ok=True)
            cap = _float(s["cash_risk_cap"], f"cash_risk_cap at {key}", blank_ok=True)
            if risk is not None:
                _fail(f"invalid native cash-risk result exposes a planned risk at {key}")
            if equity is not None and equity <= 0 or cap is not None and cap <= 0:
                _fail(f"invalid native cash-risk context has nonpositive equity/cap at {key}")
            if equity is not None and cap is not None and not _cap_matches_equity(s["equity"], s["cash_risk_cap"]):
                _fail(f"pre-call cash-risk cap is not 2.5% of equity at {key}")
        else:
            equity = _float(s["equity"], f"equity at {key}", blank_ok=True)
            risk = _float(s["planned_risk"], f"planned_risk at {key}", blank_ok=True)
            cap = _float(s["cash_risk_cap"], f"cash_risk_cap at {key}", blank_ok=True)
            if risk is not None:
                _fail(f"planned risk populated without a valid native result at {key}")
            if (equity is None) != (cap is None):
                _fail(f"partial account equity/risk-cap telemetry at {key}")
            if equity is not None:
                if equity <= 0 or cap <= 0:
                    _fail(f"invalid pre-call equity/risk-cap values at {key}")
                if not _cap_matches_equity(s["equity"], s["cash_risk_cap"]):
                    _fail(f"pre-call cash-risk cap is not 2.5% of equity at {key}")
        if gate == "structural_cash_risk_veto":
            counts["cash_risk_veto"] += 1
            if attempt or not valid_calc:
                _fail(f"cash-risk veto must be valid and before order at {key}")
        if gate == "structural_cash_risk_calc_failed":
            counts["cash_risk_calc_failures"] += 1
            if attempt or valid_calc:
                _fail(f"cash-risk calc failure must fail closed at {key}")

    counts["successful_order_events"] = successful_order_events
    return counts
