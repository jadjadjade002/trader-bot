from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from types import SimpleNamespace

import pytest

from research import run_candidate_r12_capital70 as runner
from research import run_v25_native as native


def settings_values(mode, overrides):
    return dict(line.split("=", 1) for line in native.settings(
        "fixture", mode, overrides, r2=True, r12=True).splitlines())


def test_policy_off_and_on_are_single_input_ablation():
    parity = settings_values(0, {})
    assert parity["InpExperimentMode"] == "0"
    assert parity["InpEntryStrength"] == "0"
    assert parity["InpStopLossATRMul"] == "1.5"
    assert parity["InpTakeProfitRRMul"] == "2.0"
    assert parity["InpStructuralRetest"] == "false"
    off, on = (settings_values(1, runner.parameters(flag)) for flag in (False, True))
    assert {key for key in off if off[key] != on[key]} == {"InpStructuralRetest"}
    assert off["InpEntryStrength"] == on["InpEntryStrength"] == "2"
    assert off["InpStopLossATRMul"] == on["InpStopLossATRMul"] == "2.0"
    assert off["InpTakeProfitRRMul"] == on["InpTakeProfitRRMul"] == "3.0"
    assert off["InpMaxHoldBars"] == on["InpMaxHoldBars"] == "60"
    assert off["InpLotSize"] == on["InpLotSize"] == "0.01"


@pytest.mark.parametrize("mode,overrides", [
    (0, {"InpStructuralRetest": True}), (2, {}),
    (1, {**runner.parameters(True), "InpLotSize": .02}),
    (1, {**runner.parameters(True), "InpMaxHoldBars": 90}),
    (1, {**runner.parameters(True), "InpStopLossATRMul": 1.5}),
    (1, {**runner.parameters(True), "InpEnableCashRiskVeto": True}),
    (1, {**runner.parameters(True), "InpStructuralRetest": "garbage"}),
])
def test_contract_drift_rejected(mode, overrides):
    with pytest.raises(ValueError):
        settings_values(mode, overrides)


@pytest.mark.parametrize("extra", [dict(production=True), dict(optimize=True),
    dict(r8=True), dict(r10=True), dict(r11=True), dict(control_r1=True), dict(r12=1)])
def test_profiles_cannot_be_mixed(extra):
    kwargs = dict(r2=True, r12=True)
    kwargs.update(extra)
    with pytest.raises(ValueError):
        native.settings("fixture", 1, runner.parameters(True), **kwargs)


@pytest.mark.parametrize("flag", [1, "true", None])
def test_treatment_flag_must_be_boolean(flag):
    with pytest.raises(ValueError):
        runner.parameters(flag)


def audit_fixture(tmp_path, monkeypatch, *, successful_fills=0, preset=2, enabled=True):
    monkeypatch.setattr(runner, "NATIVE_FIXTURE_COUNT", 7)
    specs = [dict(key="point", value="0.01"), dict(key="digits", value="2"),
        dict(key="tick_size", value="0.01"), dict(key="chart_mode", value="0"),
        dict(key="chart_mode_valid", value="true"), dict(key="leverage", value="500"),
        dict(key="structural_retest_enabled", value=str(enabled).lower()),
        dict(key="cash_risk_fraction", value="0.025"), dict(key="stops_level", value="0"),
        dict(key="freeze_level", value="0")]
    monkeypatch.setattr(runner.native, "csv_rows", lambda path: specs)
    (tmp_path / "journal_1.txt").write_text(
        f"R12_NATIVE_FIXTURES_PASS checks=7 preset={preset}\nR12_NATIVE_PLATFORM_PROFIT_PASS checks=2\n", encoding="utf-8")
    auditor = SimpleNamespace(audit_structural=lambda *a, **k: {"successful_fills": successful_fills,
        "evaluated": 5, "accepted": successful_fills, "rejected": 4})
    monkeypatch.setitem(sys.modules, "research.candidate_structural_audit", auditor)


@pytest.mark.parametrize("enabled,mode", [(False, 0), (False, 1), (True, 1)])
def test_specs_fixture_and_auditor_reconcile_owned_fills(tmp_path, monkeypatch, enabled, mode):
    audit_fixture(tmp_path, monkeypatch, successful_fills=3, preset=0 if mode == 0 else 2,
                  enabled=enabled)
    result = runner.validate_structural_evidence(tmp_path, "fixture", result={"trades": 3},
        enabled=enabled, mode=mode)
    assert result["audit"]["successful_fills"] == 3
    assert result["specs"]["chart_mode"] == "0"


def test_structural_auditor_receives_actual_rows_and_instrument_context(tmp_path, monkeypatch):
    audit_fixture(tmp_path, monkeypatch, successful_fills=0)
    calls = []
    auditor = SimpleNamespace(audit_structural=lambda raw, signals, **kw: (
        calls.append((raw, signals, kw)) or {"successful_fills": 0}))
    monkeypatch.setitem(sys.modules, "research.candidate_structural_audit", auditor)
    monkeypatch.setattr(runner.native, "csv_rows", lambda path: (
        [dict(key="point", value="0.01"), dict(key="digits", value="2"),
         dict(key="tick_size", value="0.01"), dict(key="chart_mode", value="0"),
         dict(key="chart_mode_valid", value="true"), dict(key="leverage", value="500"),
         dict(key="structural_retest_enabled", value="true"), dict(key="cash_risk_fraction", value="0.025"),
         dict(key="stops_level", value="0"), dict(key="freeze_level", value="0")] if str(path).endswith("_spec.csv")
        else [{"actual": "raw"}] if str(path).endswith("_raw.csv")
        else [{"actual": "signal"}]))
    runner.validate_structural_evidence(tmp_path, "fixture", result={"trades": 0},
        enabled=True, mode=1)
    assert calls == [([{"actual": "raw"}], [{"actual": "signal"}],
        {"enabled": True, "mode": 1, "point": "0.01", "tick_size": "0.01", "digits": 2})]


def test_fill_count_mismatch_blocks_acceptance(tmp_path, monkeypatch):
    audit_fixture(tmp_path, monkeypatch, successful_fills=2)
    with pytest.raises(ValueError, match="fills"):
        runner.validate_structural_evidence(tmp_path, "fixture", result={"trades": 3},
            enabled=True, mode=1)


def entry_link_fixture():
    raw = [dict(bar="2026.05.01 00:00:00", tick_msc="1777593600123",
                order_attempt="true", retcode="10009", order_ticket="7001", deal_ticket="8001")]
    signals = [dict(bar=raw[0]["bar"], tick_msc=raw[0]["tick_msc"], signal="1",
                    structural_enabled="true", structural_sl="2299.00", structural_tp="2303.00",
                    point="0.01")]
    deals = [dict(ticket="8001", position="9001", time_msc="1777593600200", type="0", entry="0",
                  magic="992300", symbol="XAUUSD", volume="0.01", price="2300.1"),
             dict(ticket="9002", position="0", time_msc="1777593600201", type="2", entry="0",
                  magic="0", symbol="", volume="0", price="0")]
    journal = ("2026.05.01 00:00:00 market buy 0.01 XAUUSD sl: 2299.00 tp: 2303.00 (2300.00 / 2300.10)\n"
               "2026.05.01 00:00:00 deal #8001 buy 0.01 XAUUSD at 2300.1 done (based on order #7001)")
    return raw, signals, deals, journal


def test_native_entry_links_require_exact_ids_and_journal_order():
    args = entry_link_fixture()
    result = runner.verify_native_entry_links(*args)
    assert result["one_to_one_ticket_join"] is True
    assert result["successful_raw_attempts"] == result["native_opening_deals"] == 1
    assert result["linked_entries"][0]["native_position"] == 9001


@pytest.mark.parametrize("mutation", ["missing_deal", "wrong_side", "foreign_magic", "wrong_volume",
    "wrong_order", "wrong_sl", "missing_request", "nonadjacent_request",
    "precedes_attempt", "duplicate_ticket"])
def test_native_entry_links_reject_unmatched_or_unsafe_openings(mutation):
    raw, signals, deals, journal = entry_link_fixture()
    if mutation == "missing_deal":
        deals.clear()
    elif mutation == "wrong_side":
        deals[0]["type"] = "1"
    elif mutation == "foreign_magic":
        deals[0]["magic"] = "0"
    elif mutation == "wrong_volume":
        deals[0]["volume"] = "0.02"
    elif mutation == "wrong_order":
        journal = journal.replace("order #7001", "order #7002")
    elif mutation == "wrong_sl":
        journal = journal.replace("sl: 2299.00", "sl: 2298.00")
    elif mutation == "missing_request":
        journal = journal.splitlines()[-1]
    elif mutation == "nonadjacent_request":
        journal = journal.replace("\n2026.05.01", "\n2026.05.01 00:00:00 unrelated log event\n2026.05.01")
    elif mutation == "precedes_attempt":
        deals[0]["time_msc"] = "1777593600122"
    elif mutation == "duplicate_ticket":
        deals.append(dict(deals[0]))
    with pytest.raises(ValueError):
        runner.verify_native_entry_links(raw, signals, deals, journal)


@pytest.mark.parametrize("mutation", ["missing_spec", "bad_chart_mode", "bad_chart_validity",
    "bad_structural_spec", "bad_cap", "negative_stop_level", "bad_fixture", "bad_platform_smoke", "no_auditor"])
def test_invalid_policy_evidence_fails_closed(tmp_path, monkeypatch, mutation):
    audit_fixture(tmp_path, monkeypatch)
    if mutation == "missing_spec":
        monkeypatch.setattr(runner.native, "csv_rows", lambda path: [
            dict(key="point", value="0.01"), dict(key="digits", value="2"),
            dict(key="tick_size", value="0.01"), dict(key="leverage", value="500")])
    elif mutation == "bad_chart_mode":
        specs = runner.native.csv_rows("fixture_spec.csv")
        specs[3]["value"] = "1"
    elif mutation == "bad_chart_validity":
        specs = runner.native.csv_rows("fixture_spec.csv")
        specs[4]["value"] = "false"
    elif mutation == "bad_structural_spec":
        specs = runner.native.csv_rows("fixture_spec.csv")
        specs[6]["value"] = "false"
    elif mutation == "bad_cap":
        specs = runner.native.csv_rows("fixture_spec.csv")
        specs[7]["value"] = "0.03"
    elif mutation == "negative_stop_level":
        specs = runner.native.csv_rows("fixture_spec.csv")
        specs[8]["value"] = "-1"
    elif mutation == "bad_fixture":
        (tmp_path / "journal_1.txt").write_text("R12_NATIVE_FIXTURES_PASS checks=6 preset=2\nR12_NATIVE_PLATFORM_PROFIT_PASS checks=2\n", encoding="utf-8")
    elif mutation == "bad_platform_smoke":
        (tmp_path / "journal_1.txt").write_text("R12_NATIVE_FIXTURES_PASS checks=7 preset=2\nR12_NATIVE_PLATFORM_PROFIT_PASS checks=1\n", encoding="utf-8")
    else:
        monkeypatch.setattr(runner.importlib, "import_module",
            lambda name: (_ for _ in ()).throw(ImportError("test auditor unavailable")))
    with pytest.raises(ValueError):
        runner.validate_structural_evidence(tmp_path, "fixture", result={"trades": 0},
            enabled=True, mode=1)


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
        passing = (dev_pass if name.endswith("structural_dev") else
                   val_pass if name.endswith("structural_val") else True)
        return dict(evidence_run=name, net=30 if passing else -10,
            trades=200, net_profit_factor=1.5 if passing else .8, native_equity_dd_pct=20,
            native_stopout=False, extra_cost_stress={"0.2": 10, "0.5": -70},
            monthly={f"2026-{m:02d}": {"net": 3} for m in range(1, 11)})

    monkeypatch.setattr(runner, "execute", execute)
    monkeypatch.setattr(runner, "save", lambda path, value: path.write_text(json.dumps(value, default=str)))
    return calls, comparisons


def test_controls_before_treatment_and_failed_dev_only_descriptive(tmp_path, monkeypatch):
    calls, comparisons = batch_fixture(tmp_path, monkeypatch)
    result = runner.run_all("r12_70_fixture", 1234)
    assert [call[0] for call in calls] == ["r12_70_fixture_parity", "r12_70_fixture_control_dev",
        "r12_70_fixture_structural_dev", "r12_70_fixture_descriptive10m"]
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
        runner.run_all("r12_70_fixture", 1234)
    assert len(calls) == 1


def test_wrong_reference_login_stops_before_native(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="connection"):
        runner.run_all("r12_70_fixture", 5678)
    assert calls == []


def test_failed_validation_has_no_confirmation_or_lock(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True, val_pass=False)
    result = runner.run_all("r12_70_fixture", 1234)
    assert result["qualified"] is False and result["selection_lock"] is None
    assert not any("confirmation" in call[0] for call in calls)


def test_locked_treatment_never_auto_qualifies_or_reselects(tmp_path, monkeypatch):
    calls, _ = batch_fixture(tmp_path, monkeypatch, dev_pass=True)
    result = runner.run_all("r12_70_fixture", 1234)
    assert result["economic_screen_passed"] is True
    assert result["qualified"] is False and result["promotion"] is False
    assert result["qualification_status"] == "AWAIT_INDEPENDENT_REVIEW"
    lock = json.loads((tmp_path / "r12_70_fixture_selection_lock.json").read_text())
    assert datetime.fromisoformat(lock["locked_utc"]).tzinfo is not None
    assert lock["parameters"] == runner.parameters(True)
    assert lock["reselect_after_confirmation"] is False
    confirmation_start = json.loads((tmp_path / "runs/r12_70_fixture_confirmation/started.json").read_text())["started_utc"]
    assert datetime.fromisoformat(lock["locked_utc"]) < datetime.fromisoformat(confirmation_start)
    assert len([call for call in calls if call[0].endswith("confirmation")]) == 1


@pytest.mark.parametrize("prefix,login", [("../bad", 1234), ("r12_70_a", True),
    ("r12_70_a", 0), ("r12_70_a", 123.0)])
def test_invalid_identity_stops_before_preflight(prefix, login, monkeypatch):
    monkeypatch.setattr(runner, "pinned_preflight", lambda: pytest.fail("invalid identity reached preflight"))
    with pytest.raises(ValueError):
        runner.run_all(prefix, login)


def test_source_binary_fixture_placeholders_block_preflight(monkeypatch):
    monkeypatch.setattr(runner.r9, "pinned_preflight", lambda: None)
    monkeypatch.setattr(runner, "NATIVE_FIXTURE_COUNT", None)
    with pytest.raises(ValueError, match="pins are not finalized"):
        runner.pinned_preflight()


def test_native_execution_is_explicit_usd70_500_r12_profile(monkeypatch):
    captured = {}
    monkeypatch.setattr(runner, "NATIVE_FIXTURE_COUNT", 7)
    monkeypatch.setattr(runner.native, "execute", lambda *a, **kw: (captured.update(kw) or {"evidence_run": a[0]}))
    monkeypatch.setattr(runner, "validate_result", lambda result: None)
    monkeypatch.setattr(runner, "save", lambda *a: None)
    result = runner.execute("r12_70_fixture", 1, runner.parameters(True), tester_login=1234)
    assert result["evidence_run"] == "r12_70_fixture"
    assert captured["deposit"] == 70 and captured["leverage"] == 500
    assert captured["candidate_source"] == runner.SOURCE
    assert captured["tester_login"] == 1234
