"""Capital/leverage identities and R9 staged execution, all native calls mocked."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from research import run_v25_native as native
from research import run_candidate_r9_capital70 as runner


@pytest.mark.parametrize("leverage", [0, 100, 201, 501, 500.0, True, "500", None])
def test_bad_leverage_rejected_before_runtime_or_launch(monkeypatch, leverage):
    monkeypatch.setattr(native, "freeze", lambda *a: pytest.fail("invalid leverage reached runtime"))
    with pytest.raises(ValueError):
        native.execute("invalid_capital", leverage=leverage)


@pytest.mark.parametrize("deposit", [0, -1, True, float("nan"), float("inf"), -float("inf")])
def test_bad_capital_rejected_before_runtime_or_launch(monkeypatch, deposit):
    monkeypatch.setattr(native, "freeze", lambda *a: pytest.fail("invalid capital reached runtime"))
    with pytest.raises(ValueError):
        native.execute("invalid_capital", deposit=deposit)


def _native_fixture(tmp_path, monkeypatch, accepted_leverage=500):
    base = tmp_path / "reports/capital"
    root = tmp_path
    monkeypatch.setattr(native, "ROOT", root)
    monkeypatch.setattr(native, "freeze", lambda *a: {"terminal64.exe": "t", "metatester64.exe": "m"})
    monkeypatch.setattr(native, "cache_manifest", lambda *a: [])
    monkeypatch.setattr(native, "sha", lambda p: "source" if Path(p).suffix == ".mq5" else "binary")
    name = "fixture_capital"
    text = native.settings(name, 0, {})
    signature = dict(start=native.START, end=native.END, mode=0, overrides={}, deposit=70,
        optimize=False, production=False, delay_ms=200,
        runtime={"terminal64.exe": "t", "metatester64.exe": "m"}, source_sha="source",
        binary_sha="binary", set_sha=hashlib.sha256(text.encode("utf-16")).hexdigest(), tick_cache=[])
    if accepted_leverage != 200:
        signature["leverage"] = accepted_leverage
    folder = base / "runs" / name
    folder.mkdir(parents=True)
    (folder / "accepted.json").write_text(json.dumps(dict(signature=signature, result={"fixture": True})))
    return base, name


def test_leverage500_signature_cannot_reuse_implicit200(tmp_path, monkeypatch):
    base, name = _native_fixture(tmp_path, monkeypatch, 200)
    with patch.object(native.subprocess, "Popen") as launch:
        with pytest.raises(ValueError, match="signature differs"):
            native.execute(name, deposit=70, leverage=500, evidence_base=base)
    launch.assert_not_called()


def test_exact500_signature_reuses_without_launch(tmp_path, monkeypatch):
    base, name = _native_fixture(tmp_path, monkeypatch)
    with patch.object(native.subprocess, "Popen") as launch:
        assert native.execute(name, deposit=70, leverage=500, evidence_base=base) == {"fixture": True}
    launch.assert_not_called()


def test_retry_keeps_capital_and_leverage(tmp_path, monkeypatch):
    base, name = _native_fixture(tmp_path, monkeypatch)
    (base / "runs" / name / "accepted.json").unlink()
    original = native.execute
    captured = {}
    class Intercept(Exception):
        pass
    def intercept(name, *args, **kwargs):
        captured.update(name=name, **kwargs)
        raise Intercept
    monkeypatch.setattr(native, "execute", intercept)
    with pytest.raises(Intercept):
        original(name, deposit=70, leverage=500, evidence_base=base, tester_login=1234)
    assert captured["deposit"] == 70 and captured["leverage"] == 500
    assert captured["tester_login"] == 1234


def test_wrapper_forces70_500_and_hold_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(runner.native, "execute", lambda *a, **kw: calls.append((a, kw)) or {"fixture": True})
    monkeypatch.setattr(runner, "validate_capital_result", lambda *a, **kw: None)
    runner.run_native("fixture", 1, runner.parameters(90), tester_login=1234, source=runner.CONTROL_SOURCE)
    args, kwargs = calls[0]
    assert kwargs["deposit"] == 70 and kwargs["leverage"] == 500
    assert kwargs["r9_hold"] is True and kwargs["evidence_base"] == runner.BASE
    assert kwargs["candidate_source"] == runner.CONTROL_SOURCE
    assert args[2]["InpMaxHoldBars"] == 90


@pytest.mark.parametrize("hold", [0, 59, 61, 90.0, True, "90", 120])
def test_parameters_cannot_add_horizons(hold):
    with pytest.raises(ValueError):
        runner.parameters(hold)


@pytest.mark.parametrize("result", [
    dict(net=1, net_profit_factor=1.3, trades=150, native_equity_dd_pct=1,
         native_stopout=True, extra_cost_stress={"0.2": 1}),
    dict(net=1, net_profit_factor=1.3, trades=150, native_equity_dd_pct=1,
         native_stopout=False, extra_cost_stress={"0.2": -1}),
    dict(net=1, net_profit_factor=1.3, trades=149, native_equity_dd_pct=1,
         native_stopout=False, extra_cost_stress={"0.2": 1}),
])
def test_positive_net_alone_does_not_pass(result):
    assert runner.operational_pass(result) is False


def _batch_fixture(tmp_path, monkeypatch, *, dev_pass=False, val_pass=False, confirmation_pass=False, parity_pass=True):
    base = tmp_path / "evidence"
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner, "pinned_preflight", lambda: None)
    monkeypatch.setattr(runner.native, "verify_environment", lambda *a, **kw: {"passed": True})
    monkeypatch.setattr(runner.native, "parity", lambda *a, **kw: {"passed": parity_pass})
    calls, events = [], []
    def fake_run(name, mode, overrides, **kwargs):
        calls.append((name, mode, dict(overrides), dict(kwargs)))
        events.append(("run", name))
        if "confirmation" in name:
            started = base / "runs" / name
            started.mkdir(parents=True, exist_ok=True)
            (started / "started.json").write_text(json.dumps({
                "started_utc": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        is_baseline = name.endswith("baseline") or name.endswith("production")
        passed = (dev_pass if "dev_hold" in name else val_pass if "val_hold" in name
                  else confirmation_pass if "confirmation" in name else True)
        return dict(evidence_run=name, net=1 if is_baseline else 100,
            net_profit_factor=1.3 if passed else 1.0, trades=200,
            native_equity_dd_pct=1 if is_baseline else .5,
            native_stopout=False, extra_cost_stress={"0.2": 60},
            monthly={f"2026-{m:02}": {"net": 1} for m in range(1, 11)})
    def recording_save(path, value):
        events.append(("save", Path(path).name))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(value))
    monkeypatch.setattr(runner, "run_native", fake_run)
    monkeypatch.setattr(runner, "save", recording_save)
    return base, calls, events


def test_controls_first_failed_dev_only_descriptive_no_validation_or_lock(tmp_path, monkeypatch):
    _, calls, _ = _batch_fixture(tmp_path, monkeypatch)
    result = runner.run_all("r9_70_fixture", 1234)
    assert [x[0] for x in calls] == [
        "r9_70_fixture_production", "r9_70_fixture_baseline",
        "r9_70_fixture_dev_hold60", "r9_70_fixture_dev_hold90",
        "r9_70_fixture_descriptive_hold60", "r9_70_fixture_descriptive_hold90"]
    assert result["validation"] is None and result["selection_lock"] is None
    assert result["qualified"] is False and result["promotion"] is False


def test_failed_validation_does_not_run_confirmation(tmp_path, monkeypatch):
    _, calls, _ = _batch_fixture(tmp_path, monkeypatch, dev_pass=True)
    result = runner.run_all("r9_70_fixture", 1234)
    assert any("val_hold90" in x[0] for x in calls)
    assert all("confirmation" not in x[0] for x in calls)
    assert result["selection_lock"] is None and result["qualified"] is False


def test_lock_precedes_confirmation_and_no_release_even_all_screens_pass(tmp_path, monkeypatch):
    _, calls, events = _batch_fixture(tmp_path, monkeypatch, dev_pass=True, val_pass=True, confirmation_pass=True)
    result = runner.run_all("r9_70_fixture", 1234)
    lock_i = events.index(("save", "r9_70_fixture_selection_lock.json"))
    assert lock_i < events.index(("run", "r9_70_fixture_confirmation"))
    assert result["economic_screen_passed"] is True
    assert result["qualification_status"] == "AWAIT_INDEPENDENT_REVIEW"
    assert result["qualified"] is False and result["promotion"] is False
    assert all(x[3].get("source") in (None, runner.PARITY_SOURCE, runner.CONTROL_SOURCE) for x in calls)


def test_failed_confirmation_never_reselects_hold60(tmp_path, monkeypatch):
    _, calls, _ = _batch_fixture(tmp_path, monkeypatch, dev_pass=True, val_pass=True)
    result = runner.run_all("r9_70_fixture", 1234)
    assert result["economic_screen_passed"] is False and result["qualified"] is False
    assert [x[0] for x in calls if "confirmation" in x[0]] == ["r9_70_fixture_confirmation"]
    assert result["selection_lock"]["parameters"]["InpMaxHoldBars"] == 90


@pytest.mark.parametrize("locked_utc", [None, "not-a-time", "2026-10-08T10:00:00"])
def test_lock_timestamp_must_be_present_and_timezone_aware(locked_utc):
    with pytest.raises(ValueError, match="selection lock timestamp"):
        runner._aware_timestamp(locked_utc, "selection lock")


def test_lock_must_precede_confirmation_started_json(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "BASE", tmp_path)
    run = tmp_path / "runs/confirmation_retry1"
    run.mkdir(parents=True)
    (run / "started.json").write_text(json.dumps({
        "started_utc": "2026-10-08T10:00:00+00:00"}), encoding="utf-8")
    with pytest.raises(ValueError, match="must predate"):
        runner._validate_lock_before_confirmation(
            {"locked_utc": "2026-10-08T10:00:01+00:00"},
            {"evidence_run": "confirmation_retry1"})
    runner._validate_lock_before_confirmation(
        {"locked_utc": "2026-10-08T09:59:59+00:00"},
        {"evidence_run": "confirmation_retry1"})


def test_missing_confirmation_started_json_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "BASE", tmp_path)
    with pytest.raises(ValueError, match="started.json is missing"):
        runner._validate_lock_before_confirmation(
            {"locked_utc": "2026-10-08T09:59:59+00:00"},
            {"evidence_run": "confirmation"})


def test_parity_failure_stops_before_treatment(tmp_path, monkeypatch):
    _, calls, _ = _batch_fixture(tmp_path, monkeypatch, parity_pass=False)
    with pytest.raises(ValueError, match="parity"):
        runner.run_all("r9_70_fixture", 1234)
    assert len(calls) == 2


@pytest.mark.parametrize("prefix,login", [("../bad", 1234), ("r9_70_a", True), ("r9_70_a", 0), ("r9_70_a", 123.0)])
def test_bad_identity_fails_before_preflight(monkeypatch, prefix, login):
    monkeypatch.setattr(runner, "pinned_preflight", lambda: pytest.fail("bad identity reached preflight"))
    with pytest.raises(ValueError):
        runner.run_all(prefix, login)


def _capital_validation_fixture(tmp_path, monkeypatch):
    base = tmp_path / "audit"
    name = "fixture_capital_audit"
    folder = base / "runs" / name
    folder.mkdir(parents=True)
    overrides = runner.parameters(60)
    setting = native.settings(name, 1, overrides, r2=True, control_r1=True, r9_hold=True)
    (folder / f"{name}.set").write_text(setting, encoding="utf-16")
    ini = (
        "[Common]\nLogin=1234\nServer=MetaQuotes-Demo\n"
        "[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n"
        "[Tester]\nDeposit=70\nLeverage=1:500\nModel=4\nOptimization=0\n"
        "ExecutionMode=200\nSymbol=XAUUSD\nPeriod=M1\nUseCloud=0\nUseRemote=0\n"
        f"FromDate={native.START}\nToDate={native.END}\n"
    )
    (folder / f"{name}.ini").write_text(ini, encoding="utf-16")
    signature = dict(deposit=70, leverage=500, optimize=False, production=False, delay_ms=200,
        mode=1, overrides=overrides, research_profile="R9_HOLD_60_90", tester_connection_login=1234,
        source_sha=runner.CONTROL_SHA, binary_sha=runner.CONTROL_BINARY_SHA,
        start=native.START, end=native.END,
        set_sha=hashlib.sha256(setting.encode("utf-16")).hexdigest())
    report = {"Initial Deposit": "70.00", "Leverage": "1:500", "History Quality": "100% real ticks",
              "Total Trades": "1", "Total Net Profit": "1.00"}
    specs = [{"key": "leverage", "value": "500"}, {"key": "final_balance", "value": "71"}]
    trade = dict(net=1, profit=1, commission=0, swap=0, fee=0, exit_reason=5)
    cash = [{"type": 2, "net": 70}]
    result = dict(evidence_run=name, native=dict(report), trades=1, net=1,
                  net_profit_factor=None, native_stopout=False)
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner.native, "verified_signature", lambda *a: signature)
    monkeypatch.setattr(runner.native, "report_rows", lambda *a: (report, []))
    monkeypatch.setattr(runner.native, "csv_rows", lambda p: specs if str(p).endswith("_spec.csv") else [])
    monkeypatch.setattr(runner, "parse_verified_native_deals", lambda *a, **kw: ([trade], cash, {}))
    return folder, signature, report, specs, cash, result


def test_capital_audit_accepts_reconciled_unit_fixture(tmp_path, monkeypatch):
    *_, result = _capital_validation_fixture(tmp_path, monkeypatch)
    runner.validate_capital_result(result)


@pytest.mark.parametrize("field,value", [("Deposit", "10000"), ("Leverage", "1:200"),
    ("Model", "1"), ("UseCloud", "1"), ("Symbol", "BTCUSD")])
def test_capital_audit_rejects_changed_actual_ini(tmp_path, monkeypatch, field, value):
    folder, *_, result = _capital_validation_fixture(tmp_path, monkeypatch)
    ini = folder / f"{result['evidence_run']}.ini"
    config = __import__("configparser").ConfigParser()
    config.read(ini, encoding="utf-16")
    config["Tester"][field] = value
    with ini.open("w", encoding="utf-16") as stream:
        config.write(stream)
    with pytest.raises(ValueError, match="actual tester"):
        runner.validate_capital_result(result)


@pytest.mark.parametrize("key,value", [("Initial Deposit", "10000.00"), ("Leverage", "1:200"),
    ("History Quality", "90% real ticks"), ("Total Net Profit", "2.00"), ("Total Trades", "2")])
def test_capital_audit_rejects_native_html_disagreement(tmp_path, monkeypatch, key, value):
    _, _, report, _, _, result = _capital_validation_fixture(tmp_path, monkeypatch)
    report[key] = value
    result["native"] = dict(report)  # Even mutually agreeing claimed metrics must match actual deals/capital.
    with pytest.raises(ValueError):
        runner.validate_capital_result(result)


def test_capital_audit_rejects_redeposit(tmp_path, monkeypatch):
    _, _, _, _, cash, result = _capital_validation_fixture(tmp_path, monkeypatch)
    cash.append({"type": 2, "net": 70})
    with pytest.raises(ValueError, match="redeposit"):
        runner.validate_capital_result(result)


def test_capital_audit_rejects_falsely_hidden_stopout(tmp_path, monkeypatch):
    *_, result = _capital_validation_fixture(tmp_path, monkeypatch)
    result["native_stopout"] = True
    with pytest.raises(ValueError, match="stopout"):
        runner.validate_capital_result(result)
