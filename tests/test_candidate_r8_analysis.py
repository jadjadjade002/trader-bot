"""Fail-closed R8 analysis fixtures; never reads native apps or runs a tester."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import tempfile
from pathlib import Path

import pytest

from research import analyze_candidate_r8 as audit


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix="r8-analysis-", dir=Path(__file__).parent) as folder:
        yield Path(folder)


def _write(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path, *, signal_bar="2026.01.01 09:59:00", decision_bar="2026.01.01 10:00:00",
             factor=(False, False), er_available=False, er="", gap="", ext_available=False,
             ext="", reason="parent_ok", parent=1, final=1, side=1, signal_reason=None,
             raw_side=None, include_raw=True, raw_tick_offset=100, feature_tick_offset=100,
             raw_history=None):
    stamp = datetime.strptime(decision_bar, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
    tick = int(stamp.timestamp() * 1000) + 100
    sig = dict(bar=decision_bar, tick_msc=str(tick), mode="1", entry_strength="2",
               signal=str(side), reason=signal_reason or reason, execution_gate="cost_or_chase",
               order_attempt="false")
    raw = dict(bar=decision_bar, tick_msc=str(tick - 100 + raw_tick_offset), original=str(side if raw_side is None else raw_side),
               order_attempt="false", gate="cost_or_chase", deal_ticket="0", order_ticket="0",
               retcode="0", held_before="false", retest_close="100")
    feature = dict(decision_bar=decision_bar, signal_bar=signal_bar,
        tick_msc=str(tick - 100 + feature_tick_offset),
        require_efficiency=str(factor[0]).lower(), require_near_mean=str(factor[1]).lower(),
        efficiency_available=str(er_available).lower(), efficiency=er,
        efficiency_gap_spanning=gap, extension_available=str(ext_available).lower(), extension_atr=ext,
        parent_side=str(parent), final_side=str(final), parent_reason="parent_ok", reason=reason)
    name = "sample"
    signal_rows, raw_rows = [sig], [raw]
    if raw_history is not None:
        signal_rows, raw_rows = [], []
        for historical_bar, close in raw_history:
            historical_stamp = datetime.strptime(historical_bar, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
            historical_tick = int(historical_stamp.timestamp() * 1000) + 100
            historical_signal, historical_raw = dict(sig), dict(raw)
            historical_signal.update(bar=historical_bar, tick_msc=str(historical_tick))
            historical_raw.update(bar=historical_bar, tick_msc=str(historical_tick), retest_close=str(close))
            if historical_bar != decision_bar:
                historical_signal.update(signal="0", reason="no_signal", execution_gate="no_signal")
                historical_raw.update(original="0", gate="no_signal")
            else:
                historical_raw["tick_msc"] = str(tick - 100 + raw_tick_offset)
            signal_rows.append(historical_signal)
            raw_rows.append(historical_raw)
    _write(tmp_path / f"{name}_signals.csv", signal_rows, list(sig))
    _write(tmp_path / f"{name}_raw.csv", raw_rows if include_raw else [], list(raw))
    _write(tmp_path / f"{name}_r8_features.csv", [feature], audit.FEATURE_FIELDS)
    deal_fields = ["ticket", "position", "time_msc", "type", "entry", "reason", "magic", "symbol",
        "volume", "price", "profit", "commission", "swap", "fee", "comment"]
    _write(tmp_path / f"{name}_deals.csv", [], deal_fields)
    return name


def test_fixed_matrix_has_exact_three_treatments_and_no_target_sweep():
    assert set(audit.TREATMENTS) == {"k1_e0", "k0_e1", "k1_e1"}
    assert audit._params(True, False) == dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
        InpTakeProfitRRMul=3.0, InpRequireEfficiency=True, InpRequireNearMean=False)
    assert audit._expected_config("r8_b_dev_k1_e1") == (1, audit._params(True, True), False)
    with pytest.raises(ValueError):
        audit._expected_config("r8_b_dev_tp0p5")


def test_control_retry_identity_is_bounded_and_explicitly_signed():
    assert audit._r1_control_name({"evidence_run": "r8_b_r1_control"}) == "r8_b_r1_control"
    assert audit._r1_control_name({"evidence_run": "r8_b_r1_control_retry1"}) == "r8_b_r1_control_retry1"
    assert audit._r1_control_name({"evidence_run": "r8_b_r1_control_retry2"}) == "r8_b_r1_control_retry2"
    for name in ("r8_b_r1_control_retry3", "other_r1_control", "../r8_b_r1_control"):
        with pytest.raises(ValueError):
            audit._r1_control_name({"evidence_run": name})


def test_legacy_baseline_end_audit_compatibility_is_exact_and_narrow():
    verified_none = {"verified": False, "tickets": []}
    got = audit._accepted_end_audit("r8_b_baseline", None, verified_none)
    assert got["accepted_record_legacy_missing"] is True
    assert audit._accepted_end_audit("r8_b_dev_k1_e0", verified_none, verified_none)[
        "accepted_record_legacy_missing"] is False
    with pytest.raises(ValueError):
        audit._accepted_end_audit("r8_b_dev_k1_e0", None, verified_none)
    with pytest.raises(ValueError):
        audit._accepted_end_audit("r8_b_baseline", {"verified": True, "tickets": [5]}, verified_none)
    with pytest.raises(ValueError):
        audit._accepted_end_audit("r8_b_baseline", None, {"verified": True, "tickets": [5]})


def test_validation_lock_must_precede_confirmation_started_marker():
    lock = {"locked_utc": "2026-10-08T08:00:00+00:00"}
    audit._validate_lock_precedes_confirmation(lock,
        {"started_utc": "2026-10-08T08:00:01+00:00"})
    for started in ({"started_utc": "2026-10-08T07:59:59+00:00"},
                    {"started_utc": "2026-10-08T08:00:01"}, {}):
        with pytest.raises(ValueError):
            audit._validate_lock_precedes_confirmation(lock, started)


def test_off_off_feature_values_blank_and_event_joins(tmp_path):
    name = _fixture(tmp_path)
    result = audit._link_r8_events(tmp_path, name, audit._params(False, False))
    assert result["feature_rows"] == 1
    assert result["feature_reasons"] == {"parent_ok": 1}
    assert result["linked_openings"] == 0
    assert result["gate_counts"] == {"cost_or_chase": 1}
    assert result["feature_sample_clock"]["delay_ms_max"] == 0


def test_positive_123ms_feature_diagnostic_lag_is_preserved(tmp_path):
    name = _fixture(tmp_path, feature_tick_offset=223)
    result = audit._link_r8_events(tmp_path, name, audit._params(False, False))
    assert result["feature_sample_clock"]["shifted_samples"] == 1
    assert result["feature_sample_clock"]["delay_ms_min"] == 123
    assert result["feature_sample_clock"]["delay_ms_max"] == 123
    assert result["feature_sample_clock"]["sample_tick_msc_min"] == result["feature_sample_clock"]["sample_tick_msc_max"]


def test_negative_feature_clock_rejected(tmp_path):
    name = _fixture(tmp_path, feature_tick_offset=99)
    with pytest.raises(ValueError, match="predates original callback"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


@pytest.mark.parametrize("delay_ms", [200, 500])
def test_later_same_minute_feature_diagnostics_are_descriptive_not_capped(tmp_path, delay_ms):
    name = _fixture(tmp_path, feature_tick_offset=100 + delay_ms)
    result = audit._link_r8_events(tmp_path, name, audit._params(False, False))
    assert result["feature_sample_clock"]["delay_ms_max"] == delay_ms
    assert result["feature_sample_clock"]["delay_ms_quantiles"]["p50"] == delay_ms


def test_cross_minute_feature_clock_rejected(tmp_path):
    name = _fixture(tmp_path, feature_tick_offset=60100)
    with pytest.raises(ValueError, match="outside logged M1 bar"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_efficiency_threshold_inclusive_and_closed_signal_timestamp(tmp_path):
    name = _fixture(tmp_path, factor=(True, False), er_available=True, er="0.3", gap="false",
                    reason="r8_quality_pass")
    result = audit._link_r8_events(tmp_path, name, audit._params(True, False))
    assert result["efficiency_evaluated"] == 1
    assert result["efficiency_gap_spanning"] == 0


def _boundary_rows(closes, *, missing_index=None):
    bars = [f"2026.04.28 13:{minute:02d}:00" for minute in range(42, 53)]
    rows = list(zip(bars, closes))
    return [row for i, row in enumerate(rows) if i != missing_index]


def test_boundary_er_reconstructed_from_real_r8_raw_closes_and_rejection_kept(tmp_path):
    # Shift 1 through shift 11 reconstructed from raw decision rows 13:52 back to 13:42.
    closes_shift_order = [4611.27, 4612.73, 4613.49, 4611.76, 4613.52, 4614.72,
                          4613.15, 4613.19, 4614.38, 4615.51, 4614.75]
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, True), er_available=True, er="0.3000000000", gap="false",
        ext_available=True, ext="0.8904887974", reason="r8_efficiency_rejected",
        parent=-1, final=0, side=0, signal_reason="r8_efficiency_rejected",
        raw_history=_boundary_rows(list(reversed(closes_shift_order))))
    result = audit._link_r8_events(tmp_path, name, audit._params(True, True))
    assert result["efficiency_boundary_reconstructed"] == 1
    diagnostic = result["efficiency_boundary_diagnostics"][0]
    assert diagnostic["serialized"] == pytest.approx(.3)
    assert diagnostic["reconstructed"] == pytest.approx(.29999999999995297)
    assert diagnostic["reconstructed"] < .30
    assert result["feature_reasons"] == {"r8_efficiency_rejected": 1}


def test_boundary_er_missing_or_gapped_raw_history_fails_closed(tmp_path):
    closes = [4614.75, 4615.51, 4614.38, 4613.19, 4613.15, 4614.72,
              4613.52, 4611.76, 4613.49, 4612.73, 4611.27]
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, False), er_available=True, er="0.3000000000", gap="false",
        reason="r8_efficiency_rejected", parent=-1, final=0, side=0,
        signal_reason="r8_efficiency_rejected", raw_history=_boundary_rows(list(reversed(closes)), missing_index=4))
    with pytest.raises(ValueError, match="raw close row missing"):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))

    irregular = _boundary_rows(list(reversed(closes)))
    irregular[6] = ("2026.04.28 13:48:30", irregular[6][1])
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, False), er_available=True, er="0.3000000000", gap="false",
        reason="r8_efficiency_rejected", parent=-1, final=0, side=0,
        signal_reason="r8_efficiency_rejected", raw_history=irregular)
    with pytest.raises(ValueError, match="raw close row missing"):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))

    invalid = _boundary_rows(list(reversed(closes)))
    invalid[4] = (invalid[4][0], "NaN")
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, False), er_available=True, er="0.3000000000", gap="false",
        reason="r8_efficiency_rejected", parent=-1, final=0, side=0,
        signal_reason="r8_efficiency_rejected", raw_history=invalid)
    with pytest.raises(ValueError, match="raw close invalid"):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))


def test_boundary_er_raw_reconstruction_must_match_serialized_rounding(tmp_path):
    closes = [4614.75, 4615.51, 4614.38, 4613.19, 4613.15, 4614.72,
              4613.52, 4611.76, 4613.49, 4612.73, 4611.27]
    rows = _boundary_rows(list(reversed(closes)))
    rows[-1] = (rows[-1][0], "4611.37")
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, False), er_available=True, er="0.3000000000", gap="false",
        reason="r8_efficiency_rejected", parent=-1, final=0, side=0,
        signal_reason="r8_efficiency_rejected", raw_history=rows)
    with pytest.raises(ValueError, match="disagrees with export"):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))


def test_boundary_er_exact_inclusive_threshold_passes_from_raw_history(tmp_path):
    shift_closes = [100, 101, 102, 103, 104, 105, 106, 106.5, 105.5, 104.5, 103]
    assert abs(shift_closes[0] - shift_closes[-1]) / sum(
        abs(shift_closes[i] - shift_closes[i + 1]) for i in range(10)) == .3
    name = _fixture(tmp_path, signal_bar="2026.04.28 13:51:00", decision_bar="2026.04.28 13:52:00",
        factor=(True, False), er_available=True, er="0.3000000000", gap="false",
        reason="r8_quality_pass", parent=1, final=1, side=1, signal_reason="r8_quality_pass",
        raw_history=_boundary_rows(list(reversed(shift_closes))))
    result = audit._link_r8_events(tmp_path, name, audit._params(True, False))
    diagnostic = result["efficiency_boundary_diagnostics"][0]
    assert diagnostic["reconstructed"] == .3
    assert diagnostic["reason"] == "r8_quality_pass"


@pytest.mark.parametrize("changes", [
    {"signal_bar": "2026.01.01 10:00:00"},
    {"signal_bar": "2026.01.01 10:01:00"},
])
def test_future_or_nonprior_signal_bar_rejected(tmp_path, changes):
    name = _fixture(tmp_path, **changes)
    with pytest.raises(ValueError, match="non-prior signal bar"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_malformed_factor_flags_and_nonfinite_feature_rejected(tmp_path):
    name = _fixture(tmp_path, factor=(True, False), er_available=True, er="nan", gap="false",
                     reason="r8_quality_pass")
    with pytest.raises(ValueError):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))


def test_factor_config_mismatch_and_nonblank_unavailable_rejected(tmp_path):
    name = _fixture(tmp_path, factor=(False, False), er_available=False, er="0.5", gap="false")
    with pytest.raises(ValueError, match="ER-off event"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))

    name = _fixture(tmp_path, factor=(False, True), ext_available=False, ext="",
        reason="r8_quality_pass")
    with pytest.raises(ValueError, match="factor config mismatch"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_partial_signal_raw_event_ledger_rejected(tmp_path):
    name = _fixture(tmp_path, raw_tick_offset=200)
    with pytest.raises(ValueError, match="event-key sets differ"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_multiple_feature_signal_and_raw_candidates_per_bar_rejected(tmp_path):
    name = _fixture(tmp_path)
    feature_path = tmp_path / f"{name}_r8_features.csv"
    feature = audit.csv_rows(feature_path)[0]
    feature["tick_msc"] = str(int(feature["tick_msc"]) + 1)
    with feature_path.open("a", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=audit.FEATURE_FIELDS).writerow(feature)
    with pytest.raises(ValueError, match="Multiple R8 feature samples"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))

    name = _fixture(tmp_path)
    signal_path, raw_path = tmp_path / f"{name}_signals.csv", tmp_path / f"{name}_raw.csv"
    signal, raw = audit.csv_rows(signal_path)[0], audit.csv_rows(raw_path)[0]
    signal["tick_msc"] = str(int(signal["tick_msc"]) + 1)
    raw["tick_msc"] = str(int(raw["tick_msc"]) + 1)
    for path, row in ((signal_path, signal), (raw_path, raw)):
        with path.open("a", encoding="utf-8", newline="") as stream:
            csv.DictWriter(stream, fieldnames=list(row)).writerow(row)
    with pytest.raises(ValueError, match="Multiple signal candidates"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))

    name = _fixture(tmp_path)
    raw_path = tmp_path / f"{name}_raw.csv"
    raw = audit.csv_rows(raw_path)[0]
    raw["tick_msc"] = str(int(raw["tick_msc"]) + 1)
    with raw_path.open("a", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=list(raw)).writerow(raw)
    with pytest.raises(ValueError, match="Ambiguous raw rows"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_feature_sample_must_precede_actual_opening_fill(tmp_path):
    name = _fixture(tmp_path, feature_tick_offset=223)
    signal_path = tmp_path / f"{name}_signals.csv"
    raw_path = tmp_path / f"{name}_raw.csv"
    signal, raw = audit.csv_rows(signal_path)[0], audit.csv_rows(raw_path)[0]
    signal["order_attempt"] = "true"
    signal["execution_gate"] = "order_attempt"
    raw.update(order_attempt="true", gate="order_attempt", deal_ticket="101",
               order_ticket="101", retcode="10009")
    for path, row in ((signal_path, signal), (raw_path, raw)):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
    event_tick = int(signal["tick_msc"])
    deal_fields = ["ticket", "position", "time_msc", "type", "entry", "reason", "magic", "symbol",
        "volume", "price", "profit", "commission", "swap", "fee", "comment"]
    opening = dict(ticket=101, position=55, time_msc=event_tick + 50, type=0, entry=0, reason=0,
        magic=992300, symbol="XAUUSD", volume=.01, price=4500, profit=0, commission=0,
        swap=0, fee=0, comment="open")
    closing = dict(ticket=102, position=55, time_msc=event_tick + 1000, type=1, entry=1, reason=1,
        magic=992300, symbol="XAUUSD", volume=.01, price=4501, profit=1, commission=0,
        swap=0, fee=0, comment="close")
    _write(tmp_path / f"{name}_deals.csv", [opening, closing], deal_fields)
    with pytest.raises(ValueError, match="future, unmatched"):
        audit._link_r8_events(tmp_path, name, audit._params(False, False))


def test_factor_rejection_preserved_and_logged(tmp_path):
    name = _fixture(tmp_path, factor=(True, False), er_available=True, er="0.29", gap="false",
                     reason="r8_efficiency_rejected", final=0, side=0,
                     signal_reason="r8_efficiency_rejected")
    result = audit._link_r8_events(tmp_path, name, audit._params(True, False))
    assert result["factor_rejections"] == 1
    assert result["feature_reasons"] == {"r8_efficiency_rejected": 1}


def test_feature_final_reason_must_reconcile_to_signal_row(tmp_path):
    name = _fixture(tmp_path, factor=(True, False), er_available=True, er="0.29", gap="false",
                     reason="r8_efficiency_rejected", final=0, side=0, signal_reason="tampered")
    with pytest.raises(ValueError, match="feature does not reconcile"):
        audit._link_r8_events(tmp_path, name, audit._params(True, False))


def test_eligibility_fails_closed_on_missing_or_nonfinite_pf():
    assert audit._passes(dict(net=1, trades=150, net_profit_factor=1.2), 150, 1.2)
    for pf in (None, float("nan"), float("inf"), 1.19):
        assert not audit._passes(dict(net=10, trades=500, net_profit_factor=pf), 150, 1.2)
    assert not audit._passes(dict(net=0, trades=500, net_profit_factor=2), 150, 1.2)
