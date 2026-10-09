from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from research import run_candidate_r10_capital70 as runner
from research import run_v25_native as native


def read_set(mode, overrides):
    return dict(line.split("=", 1) for line in native.settings(
        "fixture", mode, overrides, r2=True, r10=True).splitlines())


def test_exact_parity_and_single_veto_contract():
    parity = read_set(0, {})
    assert parity["InpEnableCashRiskVeto"] == "false"
    assert parity["InpEntryStrength"] == "0"
    assert parity["InpStopLossATRMul"] == "1.5"
    assert parity["InpTakeProfitRRMul"] == "2.0"
    off, on = (read_set(1, runner.parameters(flag)) for flag in (False, True))
    assert {key for key in off if off[key] != on[key]} == {"InpEnableCashRiskVeto"}
    assert off["InpMaxHoldBars"] == on["InpMaxHoldBars"] == "60"
    assert off["InpLotSize"] == on["InpLotSize"] == "0.01"


@pytest.mark.parametrize("mode,overrides", [
    (0, {"InpEnableCashRiskVeto": True}), (2, {}),
    (1, {**runner.parameters(True), "InpLotSize": .02}),
    (1, {**runner.parameters(True), "InpMaxHoldBars": 90}),
    (1, {**runner.parameters(True), "InpStopLossATRMul": 1.5}),
    (1, {**runner.parameters(True), "InpEnableCashRiskVeto": "garbage"}),
])
def test_contract_drift_rejected(mode, overrides):
    with pytest.raises(ValueError):
        read_set(mode, overrides)


@pytest.mark.parametrize("extra", [dict(production=True), dict(optimize=True),
    dict(r8=True), dict(control_r1=True), dict(r10=1)])
def test_profiles_cannot_be_mixed(extra):
    kwargs = dict(r2=True, r10=True)
    kwargs.update(extra)
    with pytest.raises(ValueError):
        native.settings("fixture", 1, runner.parameters(True), **kwargs)


def test_every_native_stage_is_70_500(monkeypatch):
    captured = {}
    def fake_execute(*args, **kwargs):
        captured.update(kwargs)
        return {"evidence_run": args[0]}
    monkeypatch.setattr(runner.native, "execute", fake_execute)
    monkeypatch.setattr(runner, "validate_result", lambda result: None)
    monkeypatch.setattr(runner, "save", lambda *args: None)
    runner.execute("r10_70_fixture", 1, runner.parameters(True), tester_login=1234)
    assert captured["deposit"] == 70 and captured["leverage"] == 500
    assert captured["candidate_source"] == runner.SOURCE
    assert captured["tester_login"] == 1234


@pytest.mark.parametrize("flag", [1, "true", None])
def test_treatment_must_be_boolean(flag):
    with pytest.raises(ValueError):
        runner.parameters(flag)


def batch_fixture(tmp_path, monkeypatch, *, dev_pass=False, parity_pass=True, val_pass=True):
    monkeypatch.setattr(runner, "BASE", tmp_path)
    monkeypatch.setattr(runner.r9, "BASE", tmp_path)
    baseline = dict(evidence_run="reference", net=-59.37, native_equity_dd_pct=88.11)
    monkeypatch.setattr(runner, "pinned_preflight", lambda: dict(
        baseline=baseline, production=dict(evidence_run="production"),
        control=dict(evidence_run="reference_control")))
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
        directory.mkdir(parents=True)
        (directory / "started.json").write_text(json.dumps({
            "started_utc": "2099-01-01T00:00:00+00:00"}))
        passing = (dev_pass if name.endswith("veto_dev") else
                   val_pass if name.endswith("veto_val") else True)
        return dict(evidence_run=name, net=30 if passing else -10,
            trades=200, net_profit_factor=1.5 if passing else .8, native_equity_dd_pct=20,
            native_stopout=False, extra_cost_stress={"0.2": 10, "0.5": -70},
            monthly={f"2026-{m:02d}": {"net": 3} for m in range(1, 11)})
    monkeypatch.setattr(runner, "execute", execute)
    return calls, comparisons


def test_controls_first_then_failed_development_remains_rejected(tmp_path, monkeypatch):
    calls, comparisons = batch_fixture(tmp_path, monkeypatch)
    result = runner.run_all("r10_70_fixture", 1234)
    assert [x[0] for x in calls] == ["r10_70_fixture_parity", "r10_70_fixture_control_dev",
        "r10_70_fixture_veto_dev", "r10_70_fixture_descriptive10m"]
    assert len(comparisons) == 2
    assert result["qualified"] is False and result["promotion"] is False
    assert result["selection_lock"] is None and result["validation"] is None
    assert result["qualification_status"] == "FAILED"


def test_parity_failure_prevents_treatments(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, parity_pass=False)
    with pytest.raises(ValueError, match="parity"):
        runner.run_all("r10_70_fixture", 1234)
    assert len(calls) == 1


def test_failed_validation_no_confirmation_or_reselection(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True, val_pass=False)
    result = runner.run_all("r10_70_fixture", 1234)
    assert result["qualified"] is False and result["selection_lock"] is None
    assert not any("confirmation" in x[0] for x in calls)


def test_all_mocked_passes_never_bypass_independent_release_review(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True)
    result = runner.run_all("r10_70_fixture", 1234)
    assert result["economic_screen_passed"] is True
    assert result["qualified"] is False and result["promotion"] is False
    assert result["qualification_status"] == "AWAIT_INDEPENDENT_REVIEW"
    lock = json.loads((tmp_path / "r10_70_fixture_selection_lock.json").read_text())
    assert datetime.fromisoformat(lock["locked_utc"]).tzinfo is not None
    assert lock["parameters"] == runner.parameters(True)
    assert lock["reselect_after_confirmation"] is False
    assert len([c for c in calls if "confirmation" in c[0]]) == 1


@pytest.mark.parametrize("prefix,login", [("../bad", 1234), ("r10_70_a", True),
    ("r10_70_a", 0), ("r10_70_a", 123.0)])
def test_invalid_identity_stops_before_preflight(prefix, login, monkeypatch):
    monkeypatch.setattr(runner, "pinned_preflight", lambda: pytest.fail("invalid identity reached preflight"))
    with pytest.raises(ValueError):
        runner.run_all(prefix, login)


def test_wrong_research_connection_stops_before_native(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="connection"):
        runner.run_all("r10_70_fixture", 5678)
    assert calls == []


def risk_fixture(monkeypatch, *, enabled=True):
    from research.candidate_cash_risk_audit import RAW_COLUMNS, SIGNAL_COLUMNS
    specs = dict(point="0.01", digits="2", tick_size="0.01",
                 cash_risk_fraction="0.025", cash_risk_enabled="true" if enabled else "false")
    raw = dict.fromkeys(RAW_COLUMNS, "0")
    raw.update(bar="2026.01.02 12:00:00", tick_msc="1767355200001", original="1",
               atr="2", bid="1999.99", ask="2000.00", gate="order_attempt",
               order_attempt="true", held_before="false")
    diagnostic = dict.fromkeys(SIGNAL_COLUMNS, "0")
    diagnostic.update(bar=raw["bar"], tick_msc=raw["tick_msc"], mode="1", entry_strength="2",
        signal="1", execution_gate="order_attempt", order_attempt="true", held_before="false",
        cash_risk_enabled="true" if enabled else "false", cash_risk_evaluated="true" if enabled else "false",
        cash_risk_quote="2000.00" if enabled else "", cash_risk_sl="1996.00" if enabled else "",
        cash_risk_equity="70.00" if enabled else "", cash_risk_estimate="1.0000" if enabled else "",
        cash_risk_cap="1.7500" if enabled else "", cash_risk_calc_valid="true" if enabled else "false")
    def csv_rows(path):
        if str(path).endswith("_spec.csv"):
            return [dict(key=k, value=v) for k, v in specs.items()]
        return [raw] if str(path).endswith("_raw.csv") else [diagnostic]
    monkeypatch.setattr(runner.native, "csv_rows", csv_rows)
    return specs, raw, diagnostic


@pytest.mark.parametrize("enabled", [True, False])
def test_actual_risk_evidence_reconciles_specs_and_diagnostics(tmp_path, monkeypatch, enabled):
    risk_fixture(monkeypatch, enabled=enabled)
    result = runner.validate_risk_evidence(tmp_path, "fixture", enabled=enabled, mode=1)
    assert result["counts"]["risk_checked_order_attempts"] == int(enabled)
    assert result["counts"]["off_bypass_rows"] == int(not enabled)


@pytest.mark.parametrize("key,value", [
    ("point", None), ("digits", "3"), ("tick_size", "NaN"),
    ("cash_risk_fraction", "0.03"), ("cash_risk_enabled", "false"),
    ("cash_risk_enabled", "garbage"), ("digits", "2.5"),
])
def test_missing_or_mismatched_actual_risk_specs_block(tmp_path, monkeypatch, key, value):
    specs, _, _ = risk_fixture(monkeypatch)
    if value is None:
        del specs[key]
    else:
        specs[key] = value
    with pytest.raises(ValueError):
        runner.validate_risk_evidence(tmp_path, "fixture", enabled=True, mode=1)


@pytest.mark.parametrize("mutation", ["no_evaluation", "over_cap", "false_veto", "bad_mode"])
def test_actual_inconsistent_risk_decisions_block(tmp_path, monkeypatch, mutation):
    _, raw, diagnostic = risk_fixture(monkeypatch)
    if mutation == "no_evaluation":
        diagnostic["cash_risk_evaluated"] = "false"
    elif mutation == "over_cap":
        diagnostic["cash_risk_estimate"] = "2.0000"
    elif mutation == "false_veto":
        raw["gate"] = diagnostic["execution_gate"] = "cash_risk_veto"
        raw["order_attempt"] = diagnostic["order_attempt"] = "false"
    else:
        diagnostic["mode"] = "0"
    with pytest.raises(ValueError):
        runner.validate_risk_evidence(tmp_path, "fixture", enabled=True, mode=1)


def test_duplicate_spec_keys_block(tmp_path, monkeypatch):
    risk_fixture(monkeypatch)
    original = runner.native.csv_rows
    def duplicated(path):
        rows = original(path)
        return rows + [rows[0]] if str(path).endswith("_spec.csv") else rows
    monkeypatch.setattr(runner.native, "csv_rows", duplicated)
    with pytest.raises(ValueError, match="duplicate"):
        runner.validate_risk_evidence(tmp_path, "fixture", enabled=True, mode=1)
