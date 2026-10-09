from collections import OrderedDict
from copy import deepcopy

import pytest

from research.candidate_delay_audit import (
    RAW_COLUMNS,
    SIGNAL_COLUMNS,
    DelayAuditError,
    audit_delay,
)


BASE_TICK = 1764556800000


def ordered(columns, values):
    return OrderedDict((name, str(values.get(name, ""))) for name in columns)


def event(bar, tick, *, mode=1, preset=2, raw_side=0, signal=None, gate="no_signal",
          attempt=False, retcode=0, status="", held=False, origin="", due="", origin_side=0,
          origin_bid=0, origin_ask=0, origin_atr=0, confirm_bar="", close=0,
          ema=0, trend=0, decision_bid=0, decision_ask=0, decision_atr=0):
    raw = ordered(RAW_COLUMNS, {
        "bar": bar, "tick_msc": tick, "original": raw_side, "closeback": 0,
        "dc_low": 0, "dc_high": 0, "atr": 1.0, "break_close": 0,
        "retest_open": 0, "retest_close": 0, "retest_high": 0, "retest_low": 0,
        "bid": 100.0, "ask": 100.1, "held_before": str(held).lower(),
        "cooldown_before": "1970.01.01 00:00:00", "gate": gate,
        "order_attempt": str(attempt).lower(), "retcode": retcode,
        "order_ticket": 1 if attempt else 0, "deal_ticket": 2 if attempt else 0,
    })
    signal = raw_side if signal is None else signal
    diag = ordered(SIGNAL_COLUMNS, {
        "bar": bar, "tick_msc": tick, "mode": mode, "entry_strength": preset,
        "signal": signal, "trend": 0, "reason": "test", "body_atr": 0,
        "close_location": 0, "entry_level": 0, "execution_gate": gate,
        "held_before": str(held).lower(), "order_attempt": str(attempt).lower(),
        "delay_original_bar": origin, "delay_due_bar": due,
        "delay_original_side": origin_side, "delay_origin_bid": origin_bid,
        "delay_origin_ask": origin_ask, "delay_origin_atr": origin_atr,
        "delay_status": status, "delay_confirmation_bar": confirm_bar,
        "delay_confirmation_close": close, "delay_confirmation_ema9": ema,
        "delay_confirmation_trend": trend, "delay_decision_bid": decision_bid,
        "delay_decision_ask": decision_ask, "delay_decision_atr": decision_atr,
    })
    return raw, diag


def pair(*events):
    raw, signals = zip(*events)
    return list(raw), list(signals)


def normal_arm():
    return event("2025.12.01 12:01:00", BASE_TICK, raw_side=1, signal=1,
        gate="delay_armed", status="armed", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=1, origin_bid=100, origin_ask=100.1,
        origin_atr=1.2)


def filled(*, side=1, current="2025.12.01 12:02:00", confirm="2025.12.01 12:01:00",
           raw_side=None, signal=None, retcode=10009, status="confirmed_order_filled",
           gate="order_attempt", attempt=True, close=None, ema=None, trend=None,
           decision_bid=None, decision_ask=None, decision_atr=1.4):
    side_raw = side if raw_side is None else raw_side
    side_diag = side if signal is None else signal
    c = (101 if side == 1 else 99) if close is None else close
    e = 100 if ema is None else ema
    t = side if trend is None else trend
    return event(current, BASE_TICK + 60000, raw_side=side_raw, signal=side_diag,
        gate=gate, attempt=attempt, retcode=retcode, status=status,
        origin="2025.12.01 12:00:00", due="2025.12.01 12:02:00", origin_side=side,
        origin_bid=100, origin_ask=100.1, origin_atr=1.2, confirm_bar=confirm,
        close=c, ema=e, trend=t,
        decision_bid=(101 if side == 1 else 98.9) if decision_bid is None else decision_bid,
        decision_ask=(101.1 if side == 1 else 99) if decision_ask is None else decision_ask,
        decision_atr=decision_atr)


def audit(events, *, enabled=True, mode=1):
    raw, signals = pair(*events)
    return audit_delay(raw, signals, enabled=enabled, mode=mode)


def test_buy_and_sell_confirmations_require_exact_completed_intervening_bar():
    result = audit([normal_arm(), filled()])
    assert result["armed"] == result["confirmed_filled"] == 1
    assert result["expired"] == 0
    assert result["expired_by_status"] == {}
    assert result["pending_censored_at_end"] == 0

    arm = event("2025.12.01 12:01:00", BASE_TICK, raw_side=-1, signal=-1,
        gate="delay_armed", status="armed", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=-1, origin_bid=100, origin_ask=100.1,
        origin_atr=1.2)
    close = event("2025.12.01 12:02:00", BASE_TICK + 60000, raw_side=-1,
        signal=-1, gate="order_attempt", attempt=True, retcode=10010,
        status="confirmed_order_filled", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=-1, origin_bid=100,
        origin_ask=100.1, origin_atr=1.2, confirm_bar="2025.12.01 12:01:00",
        close=99, ema=100, trend=-1, decision_bid=98.9, decision_ask=99,
        decision_atr=1.4)
    assert audit([arm, close])["confirmed_filled"] == 1


def test_final_pending_arm_is_censored_not_failed():
    result = audit([normal_arm()])
    assert result["armed"] == 1
    assert result["pending_censored_at_end"] == 1


def test_waiting_row_preserves_same_pending_state_until_due():
    arm = normal_arm()
    waiting = event("2025.12.01 12:01:00", BASE_TICK + 1000,
        gate="no_signal", status="waiting", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=1, origin_bid=100,
        origin_ask=100.1, origin_atr=1.2)
    result = audit([arm, waiting])
    assert result["waiting"] == 1
    assert result["pending_censored_at_end"] == 1


def test_terminal_skipped_bar_consumes_once_without_late_confirmation():
    arm = normal_arm()
    skipped = event("2025.12.01 12:03:00", BASE_TICK + 120000,
        gate="delay_expired", status="expired_skipped_bar",
        origin="2025.12.01 12:00:00", due="2025.12.01 12:02:00",
        origin_side=1, origin_bid=100, origin_ask=100.1, origin_atr=1.2)
    result = audit([arm, skipped])
    assert result["expired_by_status"]["expired_skipped_bar"] == 1
    assert result["pending_censored_at_end"] == 0


def test_hold_or_circuit_expiry_after_measurement_is_not_an_order():
    held = filled(status="expired_held_position", gate="held_position",
                  attempt=False, raw_side=0, signal=0, retcode=0,
                  decision_bid=0, decision_ask=0, decision_atr=0)
    result = audit([normal_arm(), held])
    assert result["expired_by_status"]["expired_held_position"] == 1
    assert result["order_attempts"] == 0


def test_already_held_at_due_expires_before_confirmation_read():
    due_held = event("2025.12.01 12:02:00", BASE_TICK + 60000,
        gate="delay_expired", status="expired_held_at_due", held=True,
        origin="2025.12.01 12:00:00", due="2025.12.01 12:02:00",
        origin_side=1, origin_bid=100, origin_ask=100.1, origin_atr=1.2)
    result = audit([normal_arm(), due_held])
    assert result["expired"] == 1
    assert result["expired_by_status"]["expired_held_at_due"] == 1
    assert result["pending_censored_at_end"] == 0

    bad = deepcopy(due_held)
    bad[0]["held_before"] = bad[1]["held_before"] = "false"
    with pytest.raises(DelayAuditError):
        audit([normal_arm(), bad])


def test_rejected_order_is_attempted_but_never_called_filled():
    rejected = filled(status="expired_order_rejected", retcode=10030)
    result = audit([normal_arm(), rejected])
    assert result["order_rejected"] == 1
    assert result["confirmed_filled"] == 0


def test_margin_block_consumes_confirmed_pending_without_request():
    blocked = filled(status="expired_margin_block", gate="margin_block",
                     attempt=False, raw_side=1, signal=1, retcode=0,
                     decision_bid=0, decision_ask=0, decision_atr=0)
    result = audit([normal_arm(), blocked])
    assert result["expired_by_status"]["expired_margin_block"] == 1
    assert result["order_attempts"] == 0


@pytest.mark.parametrize("mutation", ["trend", "close", "bar", "side", "retcode", "gate"])
def test_confirmation_mutations_fail_closed(mutation):
    arm, terminal = normal_arm(), filled()
    if mutation == "trend":
        terminal[1]["delay_confirmation_trend"] = "-1"
    elif mutation == "close":
        terminal[1]["delay_confirmation_close"] = "100"
    elif mutation == "bar":
        terminal[1]["delay_confirmation_bar"] = "2025.12.01 12:02:00"
    elif mutation == "side":
        terminal[0]["original"] = terminal[1]["signal"] = "-1"
    elif mutation == "retcode":
        terminal[0]["retcode"] = "10030"
    elif mutation == "gate":
        terminal[0]["gate"] = terminal[1]["execution_gate"] = "margin_block"
    with pytest.raises(DelayAuditError):
        audit([arm, terminal])


def test_ema_rule_is_strict_and_mirror_symmetric():
    buy_equal = filled(close=100, ema=100)
    with pytest.raises(DelayAuditError):
        audit([normal_arm(), buy_equal])


def test_no_orders_while_arming_or_without_confirmation():
    arm = normal_arm()
    arm[0]["order_attempt"] = arm[1]["order_attempt"] = "true"
    arm[0]["gate"] = arm[1]["execution_gate"] = "order_attempt"
    with pytest.raises(DelayAuditError):
        audit([arm])

    ordinary = event("2025.12.01 12:02:00", BASE_TICK + 60000,
        raw_side=1, signal=1, gate="order_attempt", attempt=True, retcode=10009)
    with pytest.raises(DelayAuditError):
        audit([normal_arm(), ordinary])


def test_off_control_bypasses_delay_but_allows_parent_orders():
    off = event("2025.12.01 12:00:00", BASE_TICK, mode=1, preset=2,
                raw_side=1, signal=1, gate="order_attempt", attempt=True,
                retcode=10009)
    assert audit([off], enabled=False, mode=1)["off_bypass_rows"] == 1
    bad = deepcopy(off)
    bad[1]["delay_status"] = "armed"
    with pytest.raises(DelayAuditError):
        audit([bad], enabled=False, mode=1)


def test_mode0_parity_requires_preset0_and_delay_off():
    row = event("2025.12.01 12:00:00", BASE_TICK, mode=0, preset=0)
    assert audit([row], enabled=False, mode=0)["off_bypass_rows"] == 1
    with pytest.raises(DelayAuditError):
        audit([row], enabled=True, mode=0)
    row[1]["entry_strength"] = "2"
    with pytest.raises(DelayAuditError):
        audit([row], enabled=False, mode=0)


def test_pending_cannot_be_replaced_or_disappear():
    second_arm = event("2025.12.01 12:01:00", BASE_TICK + 1000,
        raw_side=-1, signal=-1, gate="delay_armed", status="armed",
        origin="2025.12.01 12:00:00", due="2025.12.01 12:02:00",
        origin_side=-1, origin_bid=100, origin_ask=100.1, origin_atr=1.2)
    with pytest.raises(DelayAuditError, match="replaced pending"):
        audit([normal_arm(), second_arm])

    plain = event("2025.12.01 12:02:00", BASE_TICK + 60000)
    with pytest.raises(DelayAuditError, match="disappeared"):
        audit([normal_arm(), plain])


def test_wrong_header_duplicate_and_missing_join_fail():
    raw, signals = pair(normal_arm())
    with pytest.raises(DelayAuditError, match="header/order"):
        audit_delay(raw, [OrderedDict(list(signals[0].items())[:-1])], enabled=True, mode=1)
    with pytest.raises(DelayAuditError, match="duplicate event key"):
        audit_delay(raw + [deepcopy(raw[0])], signals, enabled=True, mode=1)
    second_raw, _ = event("2025.12.01 12:02:00", BASE_TICK + 60000)
    with pytest.raises(DelayAuditError, match="join 1:1"):
        audit_delay(raw + [second_raw], signals, enabled=True, mode=1)


def test_nonfinite_and_invalid_origin_rejected():
    arm = normal_arm()
    arm[1]["delay_origin_atr"] = "NaN"
    with pytest.raises(DelayAuditError):
        audit([arm])
    arm = normal_arm()
    arm[1]["delay_origin_ask"] = "99.9"
    with pytest.raises(DelayAuditError):
        audit([arm])


def test_unlisted_expiry_status_rejected_even_with_matching_raw_gate():
    arm = normal_arm()
    unknown = filled(status="expired_no_signal", gate="no_signal", attempt=False,
                     raw_side=0, signal=0, decision_bid=0, decision_ask=0,
                     decision_atr=0)
    with pytest.raises(DelayAuditError):
        audit([arm, unknown])


def test_expired_trend_and_close_are_supported_only_with_measured_context():
    trend = event("2025.12.01 12:02:00", BASE_TICK + 60000, gate="delay_expired",
        status="expired_trend_mismatch", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=1, origin_bid=100,
        origin_ask=100.1, origin_atr=1.2, confirm_bar="2025.12.01 12:01:00",
        close=101, ema=100, trend=-1)
    assert audit([normal_arm(), trend])["expired"] == 1
    bad_close = deepcopy(trend)
    bad_close[1]["delay_status"] = "expired_ema9_close"
    with pytest.raises(DelayAuditError):
        audit([normal_arm(), bad_close])


def test_expired_bar_gap_records_measured_wrong_prior_bar():
    gap = event("2025.12.01 12:02:00", BASE_TICK + 60000, gate="delay_expired",
        status="expired_bar_gap", origin="2025.12.01 12:00:00",
        due="2025.12.01 12:02:00", origin_side=1, origin_bid=100,
        origin_ask=100.1, origin_atr=1.2, confirm_bar="2025.12.01 12:00:00",
        close=101, ema=100, trend=1)
    assert audit([normal_arm(), gap])["expired_by_status"]["expired_bar_gap"] == 1
    bad = deepcopy(gap)
    bad[1]["delay_confirmation_bar"] = "2025.12.01 12:01:00"
    with pytest.raises(DelayAuditError):
        audit([normal_arm(), bad])


def test_orphan_origin_gap_requires_exact_nonprevious_origin_and_next_due():
    orphan = event("2025.12.01 12:02:00", BASE_TICK + 60000,
        raw_side=1, signal=1, gate="delay_expired", status="expired_origin_bar_gap",
        origin="2025.12.01 12:00:00", due="2025.12.01 12:03:00",
        origin_side=1, origin_bid=100, origin_ask=100.1, origin_atr=1.2)
    # Actual producer assigns due from lastBarTime + 60; orphan origin cannot
    # be the immediately preceding completed bar.
    assert audit([orphan])["orphan_expired"] == 1
    bad = deepcopy(orphan)
    bad[1]["delay_original_bar"] = "2025.12.01 12:01:00"
    bad[1]["delay_due_bar"] = "2025.12.01 12:03:00"
    with pytest.raises(DelayAuditError):
        audit([bad])
