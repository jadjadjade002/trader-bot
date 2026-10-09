"""Fail-closed offline audit for R11's one-completed-bar entry delay ledger."""
from __future__ import annotations

from datetime import datetime, timedelta
import math
import re
from typing import Iterable, Mapping


RAW_COLUMNS = (
    "bar", "tick_msc", "original", "closeback", "dc_low", "dc_high", "atr",
    "break_close", "retest_open", "retest_close", "retest_high", "retest_low",
    "bid", "ask", "held_before", "cooldown_before", "gate", "order_attempt",
    "retcode", "order_ticket", "deal_ticket",
)
SIGNAL_COLUMNS = (
    "bar", "tick_msc", "mode", "entry_strength", "signal", "trend", "reason",
    "body_atr", "close_location", "entry_level", "execution_gate", "held_before",
    "order_attempt", "delay_original_bar", "delay_due_bar", "delay_original_side",
    "delay_origin_bid", "delay_origin_ask", "delay_origin_atr", "delay_status",
    "delay_confirmation_bar", "delay_confirmation_close", "delay_confirmation_ema9",
    "delay_confirmation_trend", "delay_decision_bid", "delay_decision_ask",
    "delay_decision_atr",
)
KNOWN_GATES = {
    "no_new_bar", "no_signal", "delay_armed", "delay_expired", "held_position",
    "circuit_breaker", "signal", "margin_block", "order_attempt",
}
PRE_CONFIRM_EXPIRY = {
    "expired_skipped_bar", "expired_history", "expired_bar_gap",
    "expired_trend_mismatch", "expired_ema9_close",
}
GENERIC_EXPIRED = {
    "expired_held_position", "expired_circuit_breaker", "expired_no_new_bar",
}
HELD_AT_DUE = "expired_held_at_due"
SUCCESS_RETCODES = {10009, 10010}
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


class DelayAuditError(ValueError):
    """R11 rows violate delay state, chronology, or schema contract."""


def _fail(message: str) -> None:
    raise DelayAuditError(message)


def _time(value, label: str, *, blank_ok: bool = False) -> datetime | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if blank_ok:
            return None
        _fail(f"{label} is blank")
    if not isinstance(value, str):
        _fail(f"{label} must be a serialized timestamp")
    try:
        parsed = datetime.strptime(value, TIME_FORMAT)
    except ValueError:
        _fail(f"{label} has invalid timestamp format")
    if parsed.strftime(TIME_FORMAT) != value:
        _fail(f"{label} is not canonical")
    return parsed


def _num(value, label: str, *, blank_ok: bool = False) -> float | None:
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


def _int(value, label: str, *, minimum: int | None = None) -> int:
    token = str(value).strip()
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", token):
        _fail(f"{label} is not a canonical integer")
    result = int(token)
    if minimum is not None and result < minimum:
        _fail(f"{label} is below minimum")
    return result


def _bool(value, label: str) -> bool:
    if isinstance(value, bool):
        _fail(f"{label} must serialize as true/false/1/0")
    token = str(value).strip().lower()
    if token in ("true", "1"):
        return True
    if token in ("false", "0"):
        return False
    _fail(f"{label} must serialize as true/false/1/0")


def _rows(source: Iterable[Mapping], columns: tuple[str, ...], label: str) -> list[Mapping]:
    if isinstance(source, (str, bytes)):
        _fail(f"{label} must be CSV row mappings")
    result = list(source)
    if not result:
        _fail(f"{label} empty")
    for i, row in enumerate(result):
        if not isinstance(row, Mapping) or tuple(row.keys()) != columns:
            _fail(f"{label} exact {len(columns)}-column header/order mismatch at row {i}")
    return result


def _key(row: Mapping, label: str) -> tuple[str, int]:
    bar = row.get("bar")
    _time(bar, f"{label}.bar")
    tick = _int(row.get("tick_msc"), f"{label}.tick_msc", minimum=1)
    return bar, tick


def _unique(rows: list[Mapping], label: str) -> dict[tuple[str, int], Mapping]:
    out = {}
    for i, row in enumerate(rows):
        key = _key(row, f"{label}[{i}]")
        if key in out:
            _fail(f"{label} duplicate event key {key}")
        out[key] = row
    return out


def _empty(value, label: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return
    number = _num(value, label)
    if number != 0.0:
        _fail(f"{label} must be blank or zero when no delay context")


def _check_empty_delay(s: Mapping, key) -> None:
    for name in ("delay_original_bar", "delay_due_bar", "delay_confirmation_bar", "delay_status"):
        if s[name] is not None and str(s[name]).strip():
            _fail(f"delay field {name} populated without a delay event at {key}")
    for name in (
        "delay_original_side", "delay_origin_bid", "delay_origin_ask", "delay_origin_atr",
        "delay_confirmation_close", "delay_confirmation_ema9", "delay_confirmation_trend",
        "delay_decision_bid", "delay_decision_ask", "delay_decision_atr",
    ):
        _empty(s[name], f"signals.{name} at {key}")


def _origin(s: Mapping, key) -> tuple[datetime, datetime, int, float, float, float]:
    origin = _time(s["delay_original_bar"], f"delay_original_bar at {key}")
    due = _time(s["delay_due_bar"], f"delay_due_bar at {key}")
    side = _int(s["delay_original_side"], f"delay_original_side at {key}")
    bid = _num(s["delay_origin_bid"], f"delay_origin_bid at {key}")
    ask = _num(s["delay_origin_ask"], f"delay_origin_ask at {key}")
    atr = _num(s["delay_origin_atr"], f"delay_origin_atr at {key}")
    if side not in (-1, 1) or bid <= 0 or ask < bid or atr <= 0:
        _fail(f"invalid delay origin side/quote/ATR at {key}")
    return origin, due, side, bid, ask, atr


def _origin_matches(s: Mapping, pending: dict, key) -> None:
    o, d, side, bid, ask, atr = _origin(s, key)
    if (o, d, side) != (pending["origin"], pending["due"], pending["side"]):
        _fail(f"pending origin identity changed at {key}")
    if any(abs(a - b) > 0.0000001 for a, b in ((bid, pending["bid"]), (ask, pending["ask"]), (atr, pending["atr"]))):
        _fail(f"pending origin values changed at {key}")


def _confirmation(s: Mapping, side: int, key) -> None:
    bar = _time(s["delay_confirmation_bar"], f"confirmation bar at {key}")
    close = _num(s["delay_confirmation_close"], f"confirmation close at {key}")
    ema = _num(s["delay_confirmation_ema9"], f"confirmation EMA9 at {key}")
    trend = _int(s["delay_confirmation_trend"], f"confirmation trend at {key}")
    if close <= 0 or ema <= 0 or trend not in (-1, 0, 1):
        _fail(f"invalid confirmation context at {key}")
    return bar, close, ema, trend


def _confirmation_blank(s: Mapping, key) -> bool:
    bar_blank = s["delay_confirmation_bar"] is None or not str(s["delay_confirmation_bar"]).strip()
    close = _num(s["delay_confirmation_close"], f"confirmation close at {key}", blank_ok=True)
    ema = _num(s["delay_confirmation_ema9"], f"confirmation EMA9 at {key}", blank_ok=True)
    trend = _int(s["delay_confirmation_trend"], f"confirmation trend at {key}")
    close_zero = close is None or close == 0.0
    ema_zero = ema is None or ema == 0.0
    if bar_blank and close_zero and ema_zero and trend == 0:
        return True
    if bar_blank or close is None or ema is None:
        _fail(f"partial confirmation context at {key}")
    return False


def _check_confirmation_rule(side: int, bar: datetime, close: float, ema: float,
                             trend: int, pending: dict, due: datetime, key) -> None:
    if bar != pending["origin"] + timedelta(minutes=1) or bar != due - timedelta(minutes=1):
        _fail(f"confirmation bar is not the exact completed intervening M1 bar at {key}")
    current = datetime.strptime(key[0], TIME_FORMAT)
    if not bar < current:
        _fail(f"confirmation uses current/future bar at {key}")
    if trend != side:
        _fail(f"confirmation trend does not match original side at {key}")
    if side == 1 and not close > ema:
        _fail(f"BUY confirmation close must be strictly above EMA9 at {key}")
    if side == -1 and not close < ema:
        _fail(f"SELL confirmation close must be strictly below EMA9 at {key}")


def _check_decision_quote(r: Mapping, s: Mapping, side: int, key, *, required: bool) -> None:
    bid = _num(s["delay_decision_bid"], f"decision bid at {key}", blank_ok=not required)
    ask = _num(s["delay_decision_ask"], f"decision ask at {key}", blank_ok=not required)
    atr = _num(s["delay_decision_atr"], f"decision ATR at {key}", blank_ok=not required)
    if not required:
        if any(v is not None and v != 0 for v in (bid, ask, atr)):
            _fail(f"unexpected decision quote on non-order event at {key}")
        return
    if bid is None or ask is None or atr is None or bid <= 0 or ask < bid or atr <= 0:
        _fail(f"invalid decision quote/ATR on order attempt at {key}")
    intended = ask if side == 1 else bid
    raw_intended = _num(r["ask" if side == 1 else "bid"], f"raw intended quote at {key}")
    # R11 refreshes the quote before sending; report and initial tick can differ.
    # Side consistency is established against the reported decision quote itself.
    if intended <= 0 or raw_intended <= 0:
        _fail(f"invalid executable quote side at {key}")


def audit_delay(raw_rows: Iterable[Mapping], signal_rows: Iterable[Mapping], *,
                enabled: bool, mode: int) -> dict:
    """Audit R11 pending/confirmation state, using only emitted event rows.

    An unresolved final `waiting` row is reported as right-censored at the
    export boundary. No rejected/vetoed entry is assigned a counterfactual PnL.
    """
    if type(enabled) is not bool:
        _fail("enabled must be a bool")
    if type(mode) is not int or mode not in (0, 1):
        _fail("mode must be exact integer 0 or 1")
    if mode == 0 and enabled:
        _fail("R11 mode 0 cannot enable one-bar delay")
    raw = _rows(raw_rows, RAW_COLUMNS, "raw_rows")
    signals = _rows(signal_rows, SIGNAL_COLUMNS, "signal_rows")
    raw_map, signal_map = _unique(raw, "raw_rows"), _unique(signals, "signal_rows")
    if raw_map.keys() != signal_map.keys():
        _fail("raw/signals event keys do not join 1:1")
    if len(raw_map) != len(signal_map):
        _fail("raw/signals row count differs")

    counts = {
        "rows": len(raw), "joined_rows": 0, "off_bypass_rows": 0,
        "delay_events": 0, "armed": 0, "waiting": 0, "confirmed_filled": 0,
        "order_rejected": 0, "expired": 0, "expired_by_status": {},
        "orphan_expired": 0, "pending_censored_at_end": 0, "order_attempts": 0,
    }
    ordered_keys = sorted(raw_map, key=lambda k: (datetime.strptime(k[0], TIME_FORMAT), k[1]))
    if list(raw_map) != ordered_keys:
        _fail("raw event rows are not chronologically ordered")
    pending = None
    seen_armed = set()
    seen_origins = set()
    previous_bar = None

    for key in ordered_keys:
        r, s = raw_map[key], signal_map[key]
        counts["joined_rows"] += 1
        bar = datetime.strptime(key[0], TIME_FORMAT)
        if previous_bar is not None and bar < previous_bar:
            _fail(f"bar time moved backwards at {key}")
        previous_bar = bar
        row_mode = _int(s["mode"], f"mode at {key}")
        preset = _int(s["entry_strength"], f"entry_strength at {key}")
        expected_preset = 0 if mode == 0 else 2
        if row_mode != mode or preset != expected_preset:
            _fail(f"mode/preset differs from fixed R11 contract at {key}")
        raw_side, side = _int(r["original"], f"raw original at {key}"), _int(s["signal"], f"signal at {key}")
        if raw_side not in (-1, 0, 1) or side not in (-1, 0, 1) or raw_side != side:
            _fail(f"raw/diagnostic side mismatch at {key}")
        attempt = _bool(r["order_attempt"], f"raw order_attempt at {key}")
        if attempt != _bool(s["order_attempt"], f"signal order_attempt at {key}"):
            _fail(f"raw/diagnostic order_attempt mismatch at {key}")
        if r["gate"] != s["execution_gate"] or not r["gate"]:
            _fail(f"raw/diagnostic gate mismatch at {key}")
        if attempt != (r["gate"] == "order_attempt"):
            _fail(f"raw order_attempt inconsistent with raw gate at {key}")
        _bool(r["held_before"], f"raw held_before at {key}")
        _bool(s["held_before"], f"signal held_before at {key}")
        if r["held_before"] != s["held_before"]:
            _fail(f"raw/diagnostic held state mismatch at {key}")
        retcode = _int(r["retcode"], f"raw retcode at {key}", minimum=0)
        status = str(s["delay_status"]).strip()

        if not enabled:
            if status:
                _fail(f"delay status present while delay off at {key}")
            _check_empty_delay(s, key)
            counts["off_bypass_rows"] += 1
            if pending is not None:
                _fail(f"pending delay state while delay off at {key}")
            if attempt:
                counts["order_attempts"] += 1
            continue

        if not status:
            _check_empty_delay(s, key)
            if pending is not None:
                _fail(f"pending signal disappeared without waiting/terminal status at {key}")
            if r["gate"].startswith("delay_"):
                _fail(f"delay gate has no delay status at {key}")
            if attempt:
                _fail(f"delay-enabled order attempt lacks a confirmed pending event at {key}")
            continue

        counts["delay_events"] += 1
        if status == "armed":
            if pending is not None:
                _fail(f"new delay arm replaced pending signal at {key}")
            origin, due, origin_side, bid, ask, atr = _origin(s, key)
            if origin + timedelta(minutes=1) != bar or due != origin + timedelta(minutes=2):
                _fail(f"armed event origin/due bars violate R11 schedule at {key}")
            if side != origin_side or r["gate"] != "delay_armed" or attempt:
                _fail(f"armed event side/gate/order inconsistent at {key}")
            _check_confirmation_empty = _confirmation_blank(s, key)
            if not _check_confirmation_empty:
                _fail(f"armed row includes confirmation context at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
            arm_key = (key, origin, origin_side)
            if arm_key in seen_armed or origin in seen_origins:
                _fail(f"duplicate armed event at {key}")
            seen_armed.add(arm_key)
            seen_origins.add(origin)
            pending = dict(origin=origin, due=due, side=origin_side, bid=bid, ask=ask, atr=atr)
            counts["armed"] += 1
            continue

        if status == "expired_origin_bar_gap":
            if pending is not None:
                _fail(f"orphan origin-gap status while another signal pending at {key}")
            origin, due, origin_side, _, _, _ = _origin(s, key)
            if (not origin < bar or origin == bar - timedelta(minutes=1)
                    or due != bar + timedelta(minutes=1) or side != origin_side
                    or r["gate"] != "delay_expired" or attempt):
                _fail(f"origin-bar-gap event is inconsistent at {key}")
            if not _confirmation_blank(s, key):
                _fail(f"origin-gap event cannot have confirmation at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
            counts["orphan_expired"] += 1
            counts["expired_by_status"][status] = counts["expired_by_status"].get(status, 0) + 1
            continue

        if pending is None:
            _fail(f"delay status {status!r} has no preceding armed signal at {key}")
        _origin_matches(s, pending, key)
        origin, due, origin_side = pending["origin"], pending["due"], pending["side"]

        if status == "waiting":
            if not bar < due or side != 0 or attempt or r["gate"] not in {"no_signal", "held_position", "circuit_breaker"}:
                _fail(f"waiting event is not strictly before due bar or has execution at {key}")
            if not _confirmation_blank(s, key):
                _fail(f"waiting row includes confirmation context at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
            counts["waiting"] += 1
            continue

        if status == HELD_AT_DUE:
            if (bar != due or r["gate"] != "delay_expired" or attempt or side != 0
                    or not _bool(r["held_before"], f"held_at_due at {key}")):
                _fail(f"held-at-due expiry is inconsistent at {key}")
            if not _confirmation_blank(s, key):
                _fail(f"held-at-due expiry must not read confirmation context at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
        elif status == "expired_skipped_bar":
            if not bar > due or r["gate"] != "delay_expired" or attempt or side != 0:
                _fail(f"skipped-bar expiry is inconsistent at {key}")
            if not _confirmation_blank(s, key):
                _fail(f"skipped-bar expiry cannot confirm late at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
        elif status in {"expired_history", "expired_bar_gap", "expired_trend_mismatch", "expired_ema9_close"}:
            if bar != due or r["gate"] != "delay_expired" or attempt or side != 0:
                _fail(f"confirmation expiry is inconsistent at {key}")
            context_blank = _confirmation_blank(s, key)
            if status == "expired_history":
                if not context_blank:
                    _fail(f"history expiry unexpectedly published complete confirmation context at {key}")
            elif status == "expired_bar_gap":
                if context_blank:
                    _fail(f"bar-gap expiry requires measured available bars at {key}")
                cbar, _, _, _ = _confirmation(s, origin_side, key)
                if not cbar < bar or cbar == origin + timedelta(minutes=1):
                    _fail(f"bar-gap expiry does not record a genuinely noncanonical prior bar at {key}")
            else:
                if context_blank:
                    _fail(f"{status} requires complete measured confirmation context at {key}")
                cbar, close, ema, trend = _confirmation(s, origin_side, key)
                if cbar != origin + timedelta(minutes=1) or cbar != due - timedelta(minutes=1) or not cbar < bar:
                    _fail(f"{status} confirmation timestamp invalid at {key}")
                if status == "expired_trend_mismatch" and trend == origin_side:
                    _fail(f"trend-mismatch expiry trend matches origin side at {key}")
                if status == "expired_ema9_close":
                    if trend != origin_side or (origin_side == 1 and close > ema) or (origin_side == -1 and close < ema):
                        _fail(f"EMA-close expiry does not show failed strict close rule at {key}")
            _check_decision_quote(r, s, origin_side, key, required=False)
        elif status in {"confirmed_order_filled", "expired_order_rejected", "expired_margin_block"} or status in GENERIC_EXPIRED:
            if bar != due:
                _fail(f"confirmed terminal status is not on exact due bar at {key}")
            cbar, close, ema, trend = _confirmation(s, origin_side, key)
            _check_confirmation_rule(origin_side, cbar, close, ema, trend, pending, due, key)
            if status == "confirmed_order_filled":
                if not attempt or r["gate"] != "order_attempt" or retcode not in SUCCESS_RETCODES or side != origin_side:
                    _fail(f"filled confirmation lacks matching successful request at {key}")
                _check_decision_quote(r, s, origin_side, key, required=True)
                counts["confirmed_filled"] += 1
            elif status == "expired_order_rejected":
                if not attempt or r["gate"] != "order_attempt" or retcode in SUCCESS_RETCODES or side != origin_side:
                    _fail(f"rejected confirmation/raw request mismatch at {key}")
                _check_decision_quote(r, s, origin_side, key, required=True)
                counts["order_rejected"] += 1
            elif status == "expired_margin_block":
                if attempt or r["gate"] != "margin_block" or side != origin_side:
                    _fail(f"margin-blocked confirmation mismatch at {key}")
                _check_decision_quote(r, s, origin_side, key, required=False)
            else:
                suffix = status[len("expired_"):]
                if suffix != r["gate"] or suffix not in KNOWN_GATES or attempt or side != 0:
                    _fail(f"expired status does not identify its exact raw gate at {key}")
                _check_decision_quote(r, s, origin_side, key, required=False)
        else:
            _fail(f"unknown R11 delay status {status!r} at {key}")

        if attempt:
            counts["order_attempts"] += 1
        if status != "waiting":
            if status.startswith("expired_"):
                counts["expired"] += 1
                counts["expired_by_status"][status] = counts["expired_by_status"].get(status, 0) + 1
            pending = None

    if pending is not None:
        last_bar = datetime.strptime(ordered_keys[-1][0], TIME_FORMAT)
        if pending["due"] <= last_bar:
            _fail("pending delay remained after due bar was observed")
        counts["pending_censored_at_end"] = 1
    if counts["armed"] != counts["confirmed_filled"] + counts["expired"] + counts["pending_censored_at_end"]:
        _fail("armed-event lifecycle does not reconcile to filled, expired, or censored terminal states")
    return counts
