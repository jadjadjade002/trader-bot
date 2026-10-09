from collections import OrderedDict
from copy import deepcopy

import pytest

from research.candidate_structural_audit import (
    RAW_COLUMNS, SIGNAL_COLUMNS, StructuralAuditError, audit_structural,
)


def make_row(columns, values):
    return OrderedDict((name, str(values.get(name, ""))) for name in columns)


def treatment_rows(*, side=1, gate="order_attempt", reason="structural_entry"):
    if side == 1:
        s1 = (100.5, 101.5, 100.0, 101.3)
        s2 = (100.1, 101.6, 100.0, 101.5)
        s3hi, s3lo, ema1, ema2 = 100.0, 99.2, 100.6, 100.5
        bid, ask = 101.0, 101.05
        sl, tp = 99.99, 104.23
        stop_distance, target_distance = bid - sl, tp - bid
    else:
        s1 = (99.7, 100.0, 99.1, 99.2)
        s2 = (100.9, 101.0, 99.4, 99.5)
        s3hi, s3lo, ema1, ema2 = 100.8, 100.0, 99.6, 99.8
        bid, ask = 99.15, 99.20
        sl, tp = 100.06, 96.42
        stop_distance, target_distance = sl - ask, ask - tp

    attempt = gate == "order_attempt"
    raw = make_row(RAW_COLUMNS, {
        "bar": "2026.10.08 12:00:00", "tick_msc": 1791453600123,
        "original": side, "closeback": side, "dc_low": 99, "dc_high": 101,
        "atr": 1, "break_close": 101.5 if side == 1 else 99.5,
        "retest_open": s1[0], "retest_close": s1[3], "retest_high": s1[1],
        "retest_low": s1[2], "bid": bid, "ask": ask, "held_before": 0,
        "cooldown_before": 0, "gate": gate, "order_attempt": int(attempt),
        "retcode": 10009 if attempt else 0, "order_ticket": 42 if attempt else 0,
        "deal_ticket": 43 if attempt else 0,
    })
    s1o, s1h, s1l, s1c = s1
    s2o, s2h, s2l, s2c = s2
    s1range, s2range = s1h - s1l, s2h - s2l
    s1loc = (s1c - s1l) / s1range if side == 1 else (s1h - s1c) / s1range
    s2loc = (s2c - s2l) / s2range if side == 1 else (s2h - s2c) / s2range
    signal = make_row(SIGNAL_COLUMNS, {
        "bar": raw["bar"], "tick_msc": raw["tick_msc"], "mode": 1,
        "entry_strength": 2, "signal": side, "trend": side, "reason": reason,
        "body_atr": abs(s1c - s1o), "close_location": s1loc, "entry_level": s3hi if side == 1 else s3lo,
        "execution_gate": gate, "held_before": 0, "order_attempt": int(attempt),
        "structural_enabled": "true", "features_evaluated": "true", "bid_chart_mode": "true",
        "signal_bar_s1": "2026.10.08 11:59:00", "setup_bar_s2": "2026.10.08 11:58:00",
        "reference_bar_s3": "2026.10.08 11:57:00", "signal_bid": bid, "signal_ask": ask,
        "decision_bid": bid, "decision_ask": ask,
        "s1_open": s1o, "s1_high": s1h, "s1_low": s1l, "s1_close": s1c,
        "s2_open": s2o, "s2_high": s2h, "s2_low": s2l, "s2_close": s2c,
        "s3_high": s3hi, "s3_low": s3lo, "atr_s1": 1, "atr_s2": 1,
        "ema9_s1": ema1, "ema9_s2": ema2,
        "setup_body_atr": abs(s2c - s2o), "setup_close_location": s2loc,
        "setup_range_atr": s2range, "retest_body_atr": abs(s1c - s1o),
        "retest_close_location": s1loc, "structural_sl": sl, "structural_tp": tp,
        "point": 0.01, "tick_size": 0.01, "stops_level": 0, "freeze_level": 0,
        "stop_distance_close_side": stop_distance, "target_distance_close_side": target_distance,
        "equity": 70, "planned_risk": 1.5, "cash_risk_cap": 1.75,
        "risk_calc_valid": "true", "geometry_evaluated": "true", "risk_evaluated": "true",
    })
    return [raw], [signal]


def audit(raw, signals, *, enabled=True, mode=1, tick_size="0.01"):
    return audit_structural(raw, signals, enabled=enabled, mode=mode,
                            point="0.01", tick_size=tick_size, digits=2)


def test_valid_buy_reconstructs_setup_retest_geometry_and_native_risk():
    raw, signals = treatment_rows()
    counts = audit(raw, signals)
    assert counts["joined_rows"] == 1
    assert counts["setup_pass"] == counts["retest_pass"] == 1
    assert counts["geometry_evaluated"] == counts["risk_valid"] == 1
    assert counts["successful_fills"] == 1


def test_sell_mirror_uses_ask_spread_adjusted_invalidation():
    raw, signals = treatment_rows(side=-1)
    counts = audit(raw, signals)
    assert counts["successful_fills"] == 1
    assert signals[0]["structural_sl"] == "100.06"


def test_sell_ieee_tick_floor_tp_matches_native_expression_exactly():
    raw, signals = treatment_rows(side=-1)
    r, s = raw[0], signals[0]
    # Native source order: ceil((high + spread + tick) / tick) * tick,
    # then floor((bid - 3 * (SL - bid)) / tick) * tick.
    bid, ask, high, tick = 100.0, 100.2, 101.0, 0.1
    sl = __import__("math").ceil((high + (ask - bid) + tick) / tick) * tick
    tp = __import__("math").floor((bid - 3.0 * (sl - bid)) / tick) * tick
    r.update({"bid": str(bid), "ask": str(ask)})
    s.update({
        "signal_bid": str(bid), "signal_ask": str(ask),
        "decision_bid": str(bid), "decision_ask": str(ask),
        "s1_open": "100.1", "s1_high": "101.0", "s1_low": "99.8", "s1_close": "99.9",
        "s2_open": "100.9", "s2_high": "101.0", "s2_low": "99.4", "s2_close": "99.5",
        "s3_high": "100.3", "s3_low": "100.0", "entry_level": "100.0",
        "atr_s1": "3.0", "atr_s2": "1.0", "ema9_s1": "100.0", "ema9_s2": "99.8",
        "retest_body_atr": str(0.2 / 3.0),
        "retest_close_location": str((101.0 - 99.9) / (101.0 - 99.8)),
        "body_atr": str(0.2 / 3.0),
        "close_location": str((101.0 - 99.9) / (101.0 - 99.8)),
        "structural_sl": repr(sl), "structural_tp": repr(tp),
        "point": "0.01", "tick_size": "0.1",
        "stop_distance_close_side": repr(sl - ask),
        "target_distance_close_side": repr(ask - tp),
    })
    assert sl == 101.30000000000001
    assert tp == 96.0
    result = audit_structural(raw, signals, enabled=True, mode=1,
                              point="0.01", tick_size="0.1", digits=2)
    assert result["successful_fills"] == 1
    s["structural_tp"] = "96.1"
    with pytest.raises(StructuralAuditError, match="structural TP"):
        audit_structural(raw, signals, enabled=True, mode=1,
                         point="0.01", tick_size="0.1", digits=2)


def test_off_control_requires_no_structural_context_but_allows_parent_fill():
    raw, signals = treatment_rows()
    signals[0].update({name: "" for name in SIGNAL_COLUMNS[13:]})
    for name in ("structural_enabled", "features_evaluated", "risk_calc_valid",
                 "geometry_evaluated", "risk_evaluated"):
        signals[0][name] = "false"
    signals[0]["risk_calc_valid"] = ""
    signals[0]["bid_chart_mode"] = "false"
    signals[0]["mode"] = "0"
    signals[0]["entry_strength"] = "0"
    signals[0]["reason"] = "parent_signal"
    signals[0]["execution_gate"] = raw[0]["gate"] = "order_attempt"
    signals[0]["order_attempt"] = raw[0]["order_attempt"] = "1"
    raw[0]["original"] = signals[0]["signal"] = "1"
    raw[0]["retcode"] = "10009"
    assert audit(raw, signals, enabled=False, mode=0)["successful_fills"] == 1


def test_breakout_equality_at_point_one_atr_fails_strict_break_rule():
    raw, signals = treatment_rows(gate="structural_setup_absent", reason="structural_setup_absent")
    signals[0]["signal"] = raw[0]["original"] = "0"
    signals[0]["entry_level"] = "100"
    signals[0]["s2_close"] = "100.1"
    signals[0]["s2_open"] = "99.7"
    signals[0]["s2_low"] = "99.7"
    signals[0]["s2_high"] = "100.11"
    signals[0]["ema9_s2"] = "100.0"
    signals[0]["setup_body_atr"] = "0.4"
    signals[0]["setup_close_location"] = str((100.1 - 99.7) / (100.11 - 99.7))
    signals[0]["setup_range_atr"] = "0.41"
    signals[0]["structural_sl"] = signals[0]["structural_tp"] = ""
    signals[0]["stops_level"] = signals[0]["freeze_level"] = ""
    signals[0]["stop_distance_close_side"] = signals[0]["target_distance_close_side"] = ""
    signals[0]["point"] = signals[0]["tick_size"] = ""
    signals[0]["geometry_evaluated"] = signals[0]["risk_evaluated"] = "false"
    signals[0]["risk_calc_valid"] = ""
    for n in ("equity", "planned_risk", "cash_risk_cap"):
        signals[0][n] = ""
    assert audit(raw, signals)["setup_pass"] == 0


@pytest.mark.parametrize("field,value,match", [
    ("signal_bar_s1", "2026.10.08 11:58:00", "time/index"),
    ("s1_low", "101.4", "OHLC"),
    ("s2_close", "100.05", "entry reason contradicts"),
    ("ema9_s1", "101.4", "retest_absent|setup/retest|entry reason"),
    ("bid_chart_mode", "false", "features evaluated on non-Bid"),
    ("planned_risk", "1.76", "above-cap"),
    ("cash_risk_cap", "1.70", "cash-risk cap"),
])
def test_context_and_cash_risk_mutations_fail_closed(field, value, match):
    raw, signals = treatment_rows()
    signals[0][field] = value
    if field == "s2_close":
        signals[0]["setup_body_atr"] = "0.05"
        signals[0]["setup_close_location"] = "0.03125"
    with pytest.raises(StructuralAuditError, match=match):
        audit(raw, signals)


def test_wrong_tp_and_stop_distance_fail_reconstruction():
    raw, signals = treatment_rows()
    signals[0]["structural_tp"] = "104.22"
    with pytest.raises(StructuralAuditError, match="structural TP"):
        audit(raw, signals)
    raw, signals = treatment_rows()
    signals[0]["stop_distance_close_side"] = "0.99"
    with pytest.raises(StructuralAuditError, match="stop distance"):
        audit(raw, signals)


def test_freeze_and_stop_distance_equality_passes_but_below_fails():
    raw, signals = treatment_rows()
    signals[0]["stops_level"] = "10"
    # Required = 10 * .01 + .01 = .11; both measured distances exceed it.
    assert audit(raw, signals)["broker_distance_pass"] == 1
    signals[0]["stops_level"] = "100"
    signals[0]["reason"] = "structural_entry"
    signals[0]["execution_gate"] = raw[0]["gate"] = "order_attempt"
    assert audit(raw, signals)["broker_distance_pass"] == 1
    signals[0]["stops_level"] = "101"
    signals[0]["reason"] = signals[0]["execution_gate"] = raw[0]["gate"] = "structural_broker_distance"
    signals[0]["order_attempt"] = raw[0]["order_attempt"] = "0"
    raw[0]["retcode"] = raw[0]["order_ticket"] = raw[0]["deal_ticket"] = "0"
    signals[0]["risk_calc_valid"] = ""
    signals[0]["risk_evaluated"] = "false"
    for n in ("equity", "planned_risk", "cash_risk_cap"):
        signals[0][n] = ""
    assert audit(raw, signals)["broker_distance_pass"] == 0


def test_cash_veto_requires_valid_above_cap_result_and_no_order():
    raw, signals = treatment_rows(gate="structural_cash_risk_veto", reason="structural_cash_risk_veto")
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "0"
    raw[0]["retcode"] = raw[0]["order_ticket"] = raw[0]["deal_ticket"] = "0"
    signals[0]["planned_risk"] = "1.80"
    assert audit(raw, signals)["cash_risk_veto"] == 1
    signals[0]["planned_risk"] = "1.70"
    with pytest.raises(StructuralAuditError, match="cash-risk veto is at/below cap"):
        audit(raw, signals)


def test_cash_calc_failure_fails_closed_without_planned_risk():
    raw, signals = treatment_rows(gate="structural_cash_risk_calc_failed", reason="structural_cash_risk_calc_failed")
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "0"
    raw[0]["retcode"] = raw[0]["order_ticket"] = raw[0]["deal_ticket"] = "0"
    signals[0]["risk_calc_valid"] = "false"
    signals[0]["planned_risk"] = ""
    assert audit(raw, signals)["cash_risk_calc_failures"] == 1


def test_bad_join_duplicate_schema_bool_and_order_attempt_are_rejected():
    raw, signals = treatment_rows()
    bad = deepcopy(signals)
    bad[0]["tick_msc"] = "1791453600124"
    with pytest.raises(StructuralAuditError, match="1:1"):
        audit(raw, bad)
    raw, signals = treatment_rows()
    with pytest.raises(StructuralAuditError, match="duplicate"):
        audit(raw + [deepcopy(raw[0])], signals + [deepcopy(signals[0])])
    raw, signals = treatment_rows()
    del signals[0]["cash_risk_cap"]
    with pytest.raises(StructuralAuditError, match="schema/order"):
        audit(raw, signals)
    raw, signals = treatment_rows()
    signals[0]["features_evaluated"] = "yes"
    with pytest.raises(StructuralAuditError, match="serialize"):
        audit(raw, signals)
    raw, signals = treatment_rows()
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "0"
    with pytest.raises(StructuralAuditError, match="raw order_attempt inconsistent"):
        audit(raw, signals)


def test_unavailable_feature_context_is_blank_and_cannot_trade():
    raw, signals = treatment_rows(gate="structural_history_unavailable", reason="structural_history_unavailable")
    raw[0]["original"] = signals[0]["signal"] = "0"
    signals[0]["features_evaluated"] = "false"
    signals[0]["bid_chart_mode"] = "true"
    for name in SIGNAL_COLUMNS[16:]:
        signals[0][name] = ""
    for name in ("structural_enabled", "features_evaluated", "risk_calc_valid", "geometry_evaluated", "risk_evaluated"):
        signals[0][name] = "true" if name == "structural_enabled" else "false"
    signals[0]["risk_calc_valid"] = ""
    assert audit(raw, signals)["features_evaluated"] == 0
    signals[0]["atr_s1"] = "0"
    with pytest.raises(StructuralAuditError, match="unevaluated atr_s1"):
        audit(raw, signals)
