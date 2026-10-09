from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from research import run_candidate_r11_capital70 as runner
from research import run_v25_native as native


def set_values(mode, overrides):
    return dict(line.split("=", 1) for line in native.settings(
        "fixture", mode, overrides, r2=True, r11=True).splitlines())


def test_only_delay_changes_between_r11_treatments():
    parity = set_values(0, {})
    assert parity["InpExperimentMode"] == "0"
    assert parity["InpEntryStrength"] == "0"
    assert parity["InpStopLossATRMul"] == "1.5"
    assert parity["InpTakeProfitRRMul"] == "2.0"
    assert parity["InpDelayOneBar"] == "false"
    off, on = (set_values(1, runner.parameters(flag)) for flag in (False, True))
    assert {key for key in off if off[key] != on[key]} == {"InpDelayOneBar"}
    assert off["InpEntryStrength"] == on["InpEntryStrength"] == "2"
    assert off["InpStopLossATRMul"] == on["InpStopLossATRMul"] == "2.0"
    assert off["InpTakeProfitRRMul"] == on["InpTakeProfitRRMul"] == "3.0"
    assert off["InpMaxHoldBars"] == on["InpMaxHoldBars"] == "60"


@pytest.mark.parametrize("mode,overrides", [
    (0, {"InpDelayOneBar": True}), (2, {}),
    (1, {**runner.parameters(True), "InpLotSize": .02}),
    (1, {**runner.parameters(True), "InpMaxHoldBars": 90}),
    (1, {**runner.parameters(True), "InpStopLossATRMul": 1.5}),
    (1, {**runner.parameters(True), "InpEnableCashRiskVeto": True}),
    (1, {**runner.parameters(True), "InpDelayOneBar": "garbage"}),
])
def test_contract_drift_rejected(mode, overrides):
    with pytest.raises(ValueError):
        set_values(mode, overrides)


@pytest.mark.parametrize("extra", [dict(production=True), dict(optimize=True),
    dict(r8=True), dict(r10=True), dict(control_r1=True), dict(r11=1)])
def test_profiles_cannot_be_mixed(extra):
    kwargs = dict(r2=True, r11=True)
    kwargs.update(extra)
    with pytest.raises(ValueError):
        native.settings("fixture", 1, runner.parameters(True), **kwargs)


@pytest.mark.parametrize("flag", [1, "true", None])
def test_treatment_flag_must_be_boolean(flag):
    with pytest.raises(ValueError):
        runner.parameters(flag)


def test_delay_on_is_fail_closed_until_state_auditor_lands(tmp_path):
    with pytest.raises(ValueError, match="pending-state diagnostics"):
        runner.validate_delay_evidence(tmp_path, "fixture", result={}, enabled=True)
    with pytest.raises(ValueError, match="pending-state diagnostics"):
        runner.validate_delay_evidence(tmp_path, "fixture", result={}, enabled=False)


def test_each_native_stage_pins_capital_source_and_profile(monkeypatch):
    captured = {}

    def fake_execute(*args, **kwargs):
        captured.update(kwargs)
        return {"evidence_run": args[0]}

    monkeypatch.setattr(runner.native, "execute", fake_execute)
    monkeypatch.setattr(runner, "validate_result", lambda result: None)
    monkeypatch.setattr(runner, "save", lambda *args: None)
    result = runner.execute("r11_70_fixture", 1, runner.parameters(True), tester_login=1234)
    assert result["evidence_run"] == "r11_70_fixture"
    assert captured["deposit"] == 70 and captured["leverage"] == 500
    assert captured["candidate_source"] == runner.SOURCE
    assert captured["tester_login"] == 1234


def batch_fixture(tmp_path, monkeypatch, *, dev_pass=False, parity_pass=True, val_pass=True):
    monkeypatch.setattr(runner, "BASE", tmp_path)
    monkeypatch.setattr(runner.r9, "BASE", tmp_path)
    baseline = dict(evidence_run="reference", net=-59.30, native_equity_dd_pct=89.51)
    references = dict(baseline=baseline, production={"evidence_run": "production"},
        control={"evidence_run": "r9_control"})
    monkeypatch.setattr(runner, "pinned_preflight", lambda: references)
    monkeypatch.setattr(runner.native, "verified_signature", lambda *a: {"tester_connection_login": 1234})
    comparisons = []

    def parity(*args, **kwargs):
        comparisons.append(args)
        if not parity_pass:
            raise ValueError("parity failed")
        return dict(passed=True)

    monkeypatch.setattr(runner.native, "parity", parity)
    monkeypatch.setattr(runner.native, "verify_environment", lambda *a, **k: dict(passed=True))
    calls = []

    def execute(name, mode, params, **kwargs):
        calls.append((name, mode, params, kwargs))
        directory = tmp_path / "runs" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "started.json").write_text(json.dumps({
            "started_utc": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}))
        passing = (dev_pass if name.endswith("delay_dev") else
                   val_pass if name.endswith("delay_val") else True)
        return dict(evidence_run=name, net=30 if passing else -10,
            trades=200, net_profit_factor=1.5 if passing else .8, native_equity_dd_pct=20,
            native_stopout=False, extra_cost_stress={"0.2": 10, "0.5": -70},
            monthly={f"2026-{m:02d}": {"net": 3} for m in range(1, 11)})

    monkeypatch.setattr(runner, "execute", execute)
    monkeypatch.setattr(runner, "save", lambda path, value: path.write_text(json.dumps(value, default=str)))
    return calls, comparisons


def test_controls_run_before_treatment_and_failed_dev_stops(tmp_path, monkeypatch):
    calls, comparisons = batch_fixture(tmp_path, monkeypatch)
    result = runner.run_all("r11_70_fixture", 1234)
    assert [call[0] for call in calls] == ["r11_70_fixture_parity", "r11_70_fixture_control_dev",
        "r11_70_fixture_delay_dev", "r11_70_fixture_descriptive10m"]
    assert calls[0][1:3] == (0, {})
    assert calls[1][2] == runner.parameters(False)
    assert calls[2][2] == runner.parameters(True)
    assert len(comparisons) == 2
    assert result["qualified"] is False and result["promotion"] is False
    assert result["selection_lock"] is None and result["validation"] is None
    assert result["qualification_status"] == "FAILED"


def test_parity_failure_prevents_treatment(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, parity_pass=False)
    with pytest.raises(ValueError, match="parity"):
        runner.run_all("r11_70_fixture", 1234)
    assert len(calls) == 1


def test_wrong_reference_login_stops_before_native(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="connection"):
        runner.run_all("r11_70_fixture", 5678)
    assert calls == []


def test_failed_validation_has_no_confirmation_or_lock(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True, val_pass=False)
    result = runner.run_all("r11_70_fixture", 1234)
    assert result["qualified"] is False and result["selection_lock"] is None
    assert not any("confirmation" in call[0] for call in calls)


def test_locked_treatment_never_auto_qualifies_or_reselects(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True)
    result = runner.run_all("r11_70_fixture", 1234)
    assert result["economic_screen_passed"] is True
    assert result["qualified"] is False and result["promotion"] is False
    assert result["qualification_status"] == "AWAIT_INDEPENDENT_REVIEW"
    lock = json.loads((tmp_path / "r11_70_fixture_selection_lock.json").read_text())
    assert datetime.fromisoformat(lock["locked_utc"]).tzinfo is not None
    assert lock["parameters"] == runner.parameters(True)
    assert lock["reselect_after_confirmation"] is False
    names = [call[0] for call in calls]
    confirmation_start = json.loads((tmp_path / "runs/r11_70_fixture_confirmation/started.json").read_text())["started_utc"]
    assert datetime.fromisoformat(lock["locked_utc"]) < datetime.fromisoformat(confirmation_start)
    assert len([name for name in names if name.endswith("confirmation")]) == 1
    assert len([name for name in names if name.endswith("locked10m")]) == 1
    assert len([name for name in names if name.endswith("delay500")]) == 1


@pytest.mark.parametrize("prefix,login", [("../bad", 1234), ("r11_70_a", True),
    ("r11_70_a", 0), ("r11_70_a", 123.0)])
def test_invalid_identity_stops_before_preflight(prefix, login, monkeypatch):
    monkeypatch.setattr(runner, "pinned_preflight", lambda: pytest.fail("invalid identity reached preflight"))
    with pytest.raises(ValueError):
        runner.run_all(prefix, login)


def test_unpinned_source_or_binary_fails_closed(monkeypatch):
    monkeypatch.setattr(runner.r9, "pinned_preflight", lambda: None)
    monkeypatch.setattr(runner, "SOURCE_SHA", "REVIEW_REQUIRED")
    with pytest.raises(ValueError, match="pins are not finalized"):
        runner.pinned_preflight()


def diagnostic_fixture(monkeypatch, *, enabled=False):
    from research.candidate_delay_audit import RAW_COLUMNS, SIGNAL_COLUMNS
    specs = dict(point="0.01", digits="2", tick_size="0.01",
                 delay_enabled="true" if enabled else "false", delay_seconds="60")
    raw = dict.fromkeys(RAW_COLUMNS, "0")
    raw.update(bar="2026.01.02 12:00:00", tick_msc="1767355200001", gate="no_signal",
               order_attempt="false", held_before="false")
    diagnostic = dict.fromkeys(SIGNAL_COLUMNS, "0")
    diagnostic.update(bar=raw["bar"], tick_msc=raw["tick_msc"], mode="1", entry_strength="2",
        execution_gate="no_signal", order_attempt="false", held_before="false",
        delay_status="", delay_original_bar="", delay_due_bar="", delay_confirmation_bar="")
    def rows(path):
        if str(path).endswith("_spec.csv"):
            return [dict(key=k, value=v) for k, v in specs.items()]
        return [raw] if str(path).endswith("_raw.csv") else [diagnostic]
    monkeypatch.setattr(runner.native, "csv_rows", rows)
    return specs, raw, diagnostic


@pytest.mark.parametrize("enabled", [True, False])
def test_actual_specs_and_state_audit_required_even_for_controls(tmp_path, monkeypatch, enabled):
    diagnostic_fixture(monkeypatch, enabled=enabled)
    result = runner.validate_delay_evidence(tmp_path, "fixture", result={"trades": 0}, enabled=enabled, mode=1)
    assert result["counts"]["joined_rows"] == 1
    assert result["counts"]["off_bypass_rows"] == int(not enabled)


@pytest.mark.parametrize("key,value", [("point", None), ("digits", "3"),
    ("tick_size", "NaN"), ("delay_seconds", "120"), ("delay_enabled", "true"),
    ("delay_enabled", "garbage")])
def test_actual_spec_mismatch_blocks_before_selection(tmp_path, monkeypatch, key, value):
    specs, _, _ = diagnostic_fixture(monkeypatch)
    if value is None:
        del specs[key]
    else:
        specs[key] = value
    with pytest.raises(ValueError):
        runner.validate_delay_evidence(tmp_path, "fixture", result={"trades": 0}, enabled=False, mode=1)


def test_actual_order_without_confirmation_cannot_be_accepted(tmp_path, monkeypatch):
    _, raw, diagnostic = diagnostic_fixture(monkeypatch, enabled=True)
    raw["order_attempt"] = diagnostic["order_attempt"] = "true"
    raw["gate"] = diagnostic["execution_gate"] = "order_attempt"
    with pytest.raises(ValueError, match="lacks a confirmed"):
        runner.validate_delay_evidence(tmp_path, "fixture", result={"trades": 1}, enabled=True, mode=1)


def test_native_positions_must_match_confirmed_filled_events(tmp_path, monkeypatch):
    diagnostic_fixture(monkeypatch, enabled=True)
    with pytest.raises(ValueError, match="verified native position count"):
        runner.validate_delay_evidence(tmp_path, "fixture", result={"trades": 1}, enabled=True, mode=1)
