from collections import OrderedDict
from copy import deepcopy

import pytest

from research.candidate_cash_risk_audit import (
    RAW_COLUMNS,
    SIGNAL_COLUMNS,
    CashRiskAuditError,
    audit_cash_risk,
)


def row(columns, values):
    return OrderedDict((name, str(values.get(name, ""))) for name in columns)


def fixture_rows(*, enabled=True, evaluated=True, valid=True, gate="order_attempt",
                 side=1, quote="2000.00", sl="1996.00", equity="70.00",
                 cash="1.0000", cap="1.7500", tick="1791453600123"):
    raw = row(RAW_COLUMNS, {
        "bar": "2026.10.08 12:00:00", "tick_msc": tick,
        "original": side, "closeback": side, "dc_low": "1999.00",
        "dc_high": "2001.00", "atr": "2.0", "break_close": "2000",
        "retest_open": "1999.5", "retest_close": "2000", "retest_high": "2001",
        "retest_low": "1999", "bid": "1999.99", "ask": "2000.00",
        "held_before": "0", "cooldown_before": "0", "gate": gate,
        "order_attempt": "1" if gate == "order_attempt" else "0",
        "retcode": "10009", "order_ticket": "42", "deal_ticket": "43",
    })
    signal = row(SIGNAL_COLUMNS, {
        "bar": raw["bar"], "tick_msc": raw["tick_msc"], "mode": "1",
        "entry_strength": "2", "signal": side, "trend": side, "reason": "signal",
        "body_atr": "0.5", "close_location": "0.75", "entry_level": "2000",
        "execution_gate": gate, "held_before": "0",
        "order_attempt": raw["order_attempt"],
        "cash_risk_enabled": "1" if enabled else "0",
        "cash_risk_evaluated": "1" if evaluated else "0",
        "cash_risk_quote": quote if evaluated else "",
        "cash_risk_sl": sl if evaluated else "",
        "cash_risk_equity": equity if evaluated else "",
        "cash_risk_estimate": cash if evaluated and valid else "",
        "cash_risk_cap": cap if evaluated else "",
        "cash_risk_calc_valid": "1" if evaluated and valid else "0",
    })
    return [raw], [signal]


def audit(raw, signals, *, enabled=True):
    return audit_cash_risk(raw, signals, enabled=enabled, point="0.01", tick_size="0.01")


def test_valid_buy_join_and_cap_pass():
    raw, signals = fixture_rows()
    result = audit(raw, signals)
    assert result["joined_rows"] == 1
    assert result["risk_valid"] == result["risk_checked_order_attempts"] == 1
    assert result["risk_vetoes"] == 0


def test_cap_allows_full_precision_equity_behind_two_decimal_export():
    raw, signals = fixture_rows(equity="70.00", cap="1.7501")
    # Underlying equity may be 70.004; R10 exports 70.00 but computes cap
    # before formatting, so cap 1.7501 is consistent with the source.
    assert audit(raw, signals)["risk_valid"] == 1


def test_sell_uses_bid_and_outward_ceil_stop():
    raw, signals = fixture_rows(side=-1, quote="1999.99", sl="2003.99")
    result = audit(raw, signals)
    assert result["risk_valid"] == 1


@pytest.mark.parametrize(
    ("side", "bid", "ask", "quote", "sl"),
    [
        (1, "4229.47", "4229.64", "4229.64", "4226.10"),
        (-1, "4229.47", "4229.64", "4229.47", "4233.01"),
    ],
)
def test_mql_binary_floor_ceil_boundary_rows(side, bid, ask, quote, sl):
    raw, signals = fixture_rows(side=side, quote=quote, sl=sl,
                                tick="1764557580408")
    raw[0]["bid"], raw[0]["ask"] = bid, ask
    raw[0]["atr"] = "1.7700000000000649"
    assert audit(raw, signals)["risk_valid"] == 1


def test_tick_size_must_land_on_point_grid():
    raw, signals = fixture_rows()
    with pytest.raises(CashRiskAuditError, match="point grid"):
        audit_cash_risk(raw, signals, enabled=True, point="0.01", tick_size="0.015")


def test_actual_native_boundary_does_not_allow_wrong_adjacent_tick():
    raw, signals = fixture_rows(quote="4229.64", sl="4226.09")
    raw[0]["bid"], raw[0]["ask"] = "4229.47", "4229.64"
    raw[0]["atr"] = "1.7700000000000649"
    with pytest.raises(CashRiskAuditError, match="original outward-rounded stop"):
        audit(raw, signals)


def test_veto_over_cap_and_ambiguous_boundary_counted():
    raw, signals = fixture_rows(gate="cash_risk_veto", cash="1.8000")
    signals[0]["order_attempt"] = raw[0]["order_attempt"] = "0"
    result = audit(raw, signals)
    assert result["risk_vetoes"] == 1
    assert result["ambiguous_rounding_veto"] == 0

    raw, signals = fixture_rows(gate="cash_risk_veto", cash="1.7500")
    signals[0]["order_attempt"] = raw[0]["order_attempt"] = "0"
    result = audit(raw, signals)
    assert result["ambiguous_rounding_veto"] == 1


def test_fail_closed_calculation_failure():
    raw, signals = fixture_rows(gate="cash_risk_calc_failed", valid=False)
    signals[0]["order_attempt"] = raw[0]["order_attempt"] = "0"
    signals[0]["cash_risk_quote"] = "0"
    signals[0]["cash_risk_sl"] = "0"
    signals[0]["cash_risk_equity"] = "0"
    signals[0]["cash_risk_cap"] = "0"
    assert audit(raw, signals)["risk_calc_failures"] == 1


def test_off_bypass_requires_blank_fields_and_no_evaluation():
    raw, signals = fixture_rows(enabled=False, evaluated=False, valid=False)
    assert audit(raw, signals, enabled=False)["off_bypass_rows"] == 1
    bad = deepcopy(signals)
    bad[0]["cash_risk_quote"] = "0"
    with pytest.raises(CashRiskAuditError):
        audit(raw, bad, enabled=False)


@pytest.mark.parametrize("mutation", ["schema", "duplicate", "join", "side", "quote", "sl", "gate", "bool"])
def test_bad_ledger_mutations_fail_closed(mutation):
    raw, signals = fixture_rows()
    if mutation == "schema":
        signals[0].pop("cash_risk_cap")
    elif mutation == "duplicate":
        raw.append(deepcopy(raw[0]))
    elif mutation == "join":
        signals[0]["tick_msc"] = "1791453600124"
    elif mutation == "side":
        signals[0]["signal"] = "-1"
    elif mutation == "quote":
        signals[0]["cash_risk_quote"] = "1999.99"  # BUY must use Ask
    elif mutation == "sl":
        signals[0]["cash_risk_sl"] = "1995.99"
    elif mutation == "gate":
        raw[0]["gate"] = signals[0]["execution_gate"] = "cash_risk_veto"
    elif mutation == "bool":
        signals[0]["cash_risk_enabled"] = "yes"
    with pytest.raises(CashRiskAuditError):
        audit(raw, signals)


def test_attempt_before_veto_and_margin_risk_evaluation_rejected():
    raw, signals = fixture_rows(gate="cash_risk_veto", cash="2.0")
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "1"
    with pytest.raises(CashRiskAuditError):
        audit(raw, signals)

    raw, signals = fixture_rows(gate="margin_block")
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "0"
    with pytest.raises(CashRiskAuditError):
        audit(raw, signals)


def test_margin_block_is_counted_but_not_risk_eligible():
    raw, signals = fixture_rows(evaluated=False, valid=False, gate="margin_block")
    raw[0]["order_attempt"] = signals[0]["order_attempt"] = "0"
    result = audit(raw, signals)
    assert result["margin_blocks"] == 1
    assert result["risk_evaluated"] == 0


def test_order_attempt_cannot_exceed_cap_even_if_gate_says_attempt():
    raw, signals = fixture_rows(cash="1.8000")
    with pytest.raises(CashRiskAuditError, match="definitely over"):
        audit(raw, signals)


def test_strict_bool_and_input_parameters():
    raw, signals = fixture_rows()
    signals[0]["cash_risk_enabled"] = True
    with pytest.raises(CashRiskAuditError):
        audit(raw, signals)
    with pytest.raises(CashRiskAuditError):
        audit_cash_risk(raw, fixture_rows()[1], enabled=1, point="0.01", tick_size="0.01")
    with pytest.raises(CashRiskAuditError):
        audit_cash_risk(raw, fixture_rows()[1], enabled=True, point="NaN", tick_size="0.01")
