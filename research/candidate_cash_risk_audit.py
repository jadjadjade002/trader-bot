"""Fail-closed offline audit for R10 risk diagnostics and native event ledger.

This validates exported account-currency results; it never derives cash risk
from symbol tick-value fields and cannot prove a vetoed event's counterfactual.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    "order_attempt", "cash_risk_enabled", "cash_risk_evaluated", "cash_risk_quote",
    "cash_risk_sl", "cash_risk_equity", "cash_risk_estimate", "cash_risk_cap",
    "cash_risk_calc_valid",
)
RISK_GATES = {"cash_risk_veto", "cash_risk_calc_failed"}
RISK_NUMERIC_COLUMNS = (
    "cash_risk_quote", "cash_risk_sl", "cash_risk_equity",
    "cash_risk_estimate", "cash_risk_cap",
)
SERIAL_TOL = Decimal("0.000051")  # four-decimal MQL output rounded to nearest
# Equity is exported to two decimals while the cap is computed from the full
# precision account equity and exported to four. Propagate the half-cent input
# interval through the 2.5% multiplier, then add cap-output rounding tolerance.
CAP_EQUITY_SERIAL_TOL = Decimal("0.005") * Decimal("0.025") + SERIAL_TOL
TICK_EPS = Decimal("0.0000001")


class CashRiskAuditError(ValueError):
    """R10 output violated its frozen offline audit contract."""


def _fail(message: str) -> None:
    raise CashRiskAuditError(message)


def _decimal(value, label: str, *, blank_ok: bool = False) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if blank_ok:
            return None
        _fail(f"{label} is blank")
    if isinstance(value, bool):
        _fail(f"{label} is not a numeric token")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        _fail(f"{label} is not numeric")
    if not result.is_finite():
        _fail(f"{label} is nonfinite")
    return result


def _boolean(value, label: str) -> bool:
    if isinstance(value, bool):
        _fail(f"{label} must be serialized as 0/1/true/false")
    token = str(value).strip().lower()
    if token in ("1", "true"):
        return True
    if token in ("0", "false"):
        return False
    _fail(f"{label} must be serialized as 0/1/true/false")


def _integer(value, label: str, *, minimum: int | None = None) -> int:
    token = str(value).strip()
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", token):
        _fail(f"{label} is not a canonical integer")
    result = int(token)
    if minimum is not None and result < minimum:
        _fail(f"{label} is below its minimum")
    return result


def _validate_rows(rows: Iterable[Mapping], expected: tuple[str, ...], label: str) -> list[Mapping]:
    if isinstance(rows, (str, bytes)):
        _fail(f"{label} must be parsed CSV row mappings")
    materialized = list(rows)
    if not materialized:
        _fail(f"{label} is empty")
    for index, row in enumerate(materialized):
        if not isinstance(row, Mapping) or tuple(row.keys()) != expected:
            _fail(f"{label} schema/order mismatch at row {index}; exact {len(expected)} columns required")
    return materialized


def _key(row: Mapping, label: str) -> tuple[str, int]:
    bar = row.get("bar")
    if not isinstance(bar, str) or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", bar):
        _fail(f"{label} bar key is malformed")
    tick = _integer(row.get("tick_msc"), f"{label} tick_msc", minimum=1)
    return bar, tick


def _unique_keys(rows: list[Mapping], label: str) -> dict[tuple[str, int], Mapping]:
    result = {}
    for index, row in enumerate(rows):
        key = _key(row, f"{label}[{index}]")
        if key in result:
            _fail(f"{label} duplicate (bar,tick_msc) key: {key}")
        result[key] = row
    return result


def _digits(point: Decimal) -> int:
    exponent = point.normalize().as_tuple().exponent
    return max(0, -exponent)


def _expected_sl(side: int, quote: Decimal, atr: Decimal,
                 point: Decimal, tick_size: Decimal) -> Decimal:
    # Mirror the EA's binary-double evaluation order exactly:
    # MathFloor((quote - distance) / tickSize) * tickSize (BUY), with
    # MathCeil((quote + distance) / tickSize) * tickSize (SELL), then
    # NormalizeDouble(..., _Digits). Decimal arithmetic changes boundary
    # outcomes through cancellation (and rejected an actual native R10 row).
    q, a, p, ts = map(float, (quote, atr, point, tick_size))
    distance = max(2.0 * a, 150.0 * p)
    unrounded = q - distance if side == 1 else q + distance
    units = unrounded / ts
    ticks = math.floor(units) if side == 1 else math.ceil(units)
    digits = _digits(point)
    return Decimal(str(round(ticks * ts, digits)))


def _threshold_relation(cash: Decimal, cap: Decimal) -> str:
    """Classify four-decimal serialized values without inventing boundary order."""
    cash_min, cash_max = cash - SERIAL_TOL, cash + SERIAL_TOL
    cap_min, cap_max = cap - SERIAL_TOL, cap + SERIAL_TOL
    if cash_min > cap_max:
        return "over"
    if cash_max <= cap_min:
        return "under_or_equal"
    return "ambiguous"


def audit_cash_risk(raw_rows: Iterable[Mapping], signal_rows: Iterable[Mapping], *,
                    enabled: bool, point, tick_size) -> dict:
    """Validate 1:1 R10 raw/signal rows and risk-veto decision consistency.

    `cash_risk_estimate` is treated as the EA's reported account-currency
    estimate, not recomputed from tick-value metadata. `point` and `tick_size`
    are required only to reconstruct original ATR/minimum-point SL geometry.
    """
    if type(enabled) is not bool:
        _fail("enabled must be a bool")
    p = _decimal(point, "point")
    ts = _decimal(tick_size, "tick_size")
    if p <= 0 or ts <= 0:
        _fail("point and tick_size must be positive")
    tick_points = ts / p
    if abs(tick_points - tick_points.to_integral_value()) > Decimal("0.000000001"):
        _fail("tick_size is not representable on the exported point grid")
    raw = _validate_rows(raw_rows, RAW_COLUMNS, "raw_rows")
    diagnostic = _validate_rows(signal_rows, SIGNAL_COLUMNS, "signal_rows")
    raw_by_key = _unique_keys(raw, "raw_rows")
    diag_by_key = _unique_keys(diagnostic, "signal_rows")
    if raw_by_key.keys() != diag_by_key.keys():
        missing_diag = sorted(raw_by_key.keys() - diag_by_key.keys())[:1]
        missing_raw = sorted(diag_by_key.keys() - raw_by_key.keys())[:1]
        _fail(f"raw/signal joins are not 1:1 (missing signal={missing_diag}, missing raw={missing_raw})")

    counts = {
        "rows": len(raw), "joined_rows": 0, "risk_enabled_rows": 0,
        "risk_evaluated": 0, "risk_valid": 0, "risk_vetoes": 0,
        "risk_calc_failures": 0, "risk_checked_order_attempts": 0,
        "margin_blocks": 0, "ambiguous_rounding_pass": 0,
        "ambiguous_rounding_veto": 0, "off_bypass_rows": 0,
    }
    point_sl_tol = min(p / 2, ts / 2) + TICK_EPS
    quote_tol = p / 2 + TICK_EPS

    for key in sorted(raw_by_key):
        r, s = raw_by_key[key], diag_by_key[key]
        counts["joined_rows"] += 1
        raw_attempt = _boolean(r["order_attempt"], "raw.order_attempt")
        diag_attempt = _boolean(s["order_attempt"], "signals.order_attempt")
        raw_held = _boolean(r["held_before"], "raw.held_before")
        diag_held = _boolean(s["held_before"], "signals.held_before")
        if raw_attempt != diag_attempt:
            _fail(f"order_attempt differs between raw and signals at {key}")
        if raw_held != diag_held:
            _fail(f"held_before differs between raw and signals at {key}")
        if r["gate"] != s["execution_gate"]:
            _fail(f"execution gate differs between raw and signals at {key}")
        if not isinstance(r["gate"], str) or not r["gate"]:
            _fail(f"raw gate is blank at {key}")
        if raw_attempt != (r["gate"] == "order_attempt"):
            _fail(f"raw order_attempt does not match raw gate at {key}")
        side = _integer(s["signal"], "signals.signal")
        raw_side = _integer(r["original"], "raw.original")
        if side not in (-1, 0, 1) or raw_side not in (-1, 0, 1) or side != raw_side:
            _fail(f"raw/diagnostic signal side mismatch at {key}")
        _integer(s["mode"], "signals.mode", minimum=0)
        _integer(s["entry_strength"], "signals.entry_strength", minimum=0)
        row_enabled = _boolean(s["cash_risk_enabled"], "signals.cash_risk_enabled")
        evaluated = _boolean(s["cash_risk_evaluated"], "signals.cash_risk_evaluated")
        valid = _boolean(s["cash_risk_calc_valid"], "signals.cash_risk_calc_valid")
        if row_enabled is not enabled:
            _fail(f"cash_risk_enabled differs from requested profile at {key}")
        if valid and not evaluated:
            _fail(f"calculation marked valid without an evaluation at {key}")
        if not enabled:
            counts["off_bypass_rows"] += 1
        else:
            counts["risk_enabled_rows"] += 1

        numeric = {name: _decimal(s[name], f"signals.{name}", blank_ok=True)
                   for name in RISK_NUMERIC_COLUMNS}
        if not evaluated:
            if valid or any(value is not None for value in numeric.values()):
                _fail(f"unevaluated risk row contains risk calculation fields at {key}")
            if r["gate"] in RISK_GATES:
                _fail(f"risk gate recorded without evaluation at {key}")
            if r["gate"] == "margin_block":
                counts["margin_blocks"] += 1
            if enabled and raw_attempt:
                _fail(f"risk-enabled order attempt skipped risk evaluation at {key}")
            continue

        if not enabled:
            _fail(f"risk-off row evaluated cash risk at {key}")
        if side not in (-1, 1):
            _fail(f"cash risk evaluated without a directional signal at {key}")
        if r["gate"] == "margin_block":
            _fail(f"margin-blocked event was incorrectly risk-evaluated at {key}")
        counts["risk_evaluated"] += 1

        quote, sl, equity, cash, cap = (numeric[name] for name in RISK_NUMERIC_COLUMNS)
        # When present, pre-trade quote/stop/equity/cap must be finite and
        # reproduce the source's Ask/Bid and outward-rounded 2ATR/150-point SL.
        bid = _decimal(r["bid"], "raw.bid")
        ask = _decimal(r["ask"], "raw.ask")
        atr = _decimal(r["atr"], "raw.atr")
        if bid <= 0 or ask < bid:
            _fail(f"raw executable quote invalid at {key}")
        if valid and quote is not None:
            if quote <= 0 or abs(quote - (ask if side == 1 else bid)) > quote_tol:
                _fail(f"cash-risk quote is not same-side raw Ask/Bid at {key}")
        if valid and sl is not None and quote is not None:
            if sl <= 0 or atr <= 0:
                _fail(f"cash-risk SL cannot be reconstructed at {key}")
            expected = _expected_sl(side, quote, atr, p, ts)
            if abs(sl - expected) > point_sl_tol:
                _fail(f"cash-risk SL differs from original outward-rounded stop at {key}")
            units = sl / ts
            if abs(units - units.to_integral_value(rounding=ROUND_HALF_UP)) * ts > point_sl_tol:
                _fail(f"cash-risk SL is off tick grid at {key}")

        if valid:
            if any(value is None for value in numeric.values()):
                _fail(f"valid risk calculation has blank inputs/results at {key}")
            assert quote is not None and sl is not None and equity is not None
            assert cash is not None and cap is not None
            if quote <= 0 or sl <= 0 or equity <= 0 or cash <= 0 or cap <= 0:
                _fail(f"valid risk calculation contains a nonpositive value at {key}")
            if abs(cap - equity * Decimal("0.025")) > CAP_EQUITY_SERIAL_TOL:
                _fail(f"risk cap is not 2.5% of serialized equity at {key}")
            counts["risk_valid"] += 1
            relation = _threshold_relation(cash, cap)
            if r["gate"] == "cash_risk_veto":
                if raw_attempt:
                    _fail(f"risk veto attempted an order at {key}")
                if relation == "under_or_equal":
                    _fail(f"risk veto is definitely at/below cap at {key}")
                if relation == "ambiguous":
                    counts["ambiguous_rounding_veto"] += 1
                counts["risk_vetoes"] += 1
            elif r["gate"] == "order_attempt":
                if not raw_attempt:
                    _fail(f"valid risk pass lacks order attempt at {key}")
                if relation == "over":
                    _fail(f"order attempt is definitely over risk cap at {key}")
                if relation == "ambiguous":
                    counts["ambiguous_rounding_pass"] += 1
                counts["risk_checked_order_attempts"] += 1
            else:
                _fail(f"valid cash-risk result has incompatible gate {r['gate']!r} at {key}")
        else:
            if r["gate"] != "cash_risk_calc_failed" or raw_attempt:
                _fail(f"invalid cash-risk calculation must fail closed without order at {key}")
            if cash is not None:
                _fail(f"invalid cash-risk calculation exposes an estimate at {key}")
            for name in ("cash_risk_quote", "cash_risk_sl", "cash_risk_equity", "cash_risk_cap"):
                value = numeric[name]
                if value is not None and not value.is_finite():
                    _fail(f"invalid calculation has nonfinite {name} at {key}")
            counts["risk_calc_failures"] += 1

    return counts
