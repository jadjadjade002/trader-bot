from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from research import run_v25_native as native

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_candidate_r8", ROOT / "research/run_candidate_r8.py")
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


def _params(k=False, e=False):
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
                InpRequireEfficiency=k, InpRequireNearMean=e)


def test_r8_configuration_matrix_is_three_treatments_only():
    rows = runner.configurations()
    assert [(mode, tag) for mode, _, tag in rows] == [
        (1, "k0_e1"), (1, "k1_e0"), (1, "k1_e1")]
    assert all(params == _params(bool(int(tag[1])), bool(int(tag[-1])))
               for _, params, tag in rows)
    assert _params(False, False) == runner.parameters(0, 0)


@pytest.mark.parametrize("mode,overrides,expected", [
    (0, {}, ("InpStopLossATRMul=1.5", "InpTakeProfitRRMul=2.0",
             "InpRequireEfficiency=false", "InpRequireNearMean=false")),
    (0, dict(InpRequireEfficiency=False, InpRequireNearMean=False),
     ("InpRequireEfficiency=false", "InpRequireNearMean=false")),
    (1, _params(False, True),
     ("InpEntryStrength=2", "InpStopLossATRMul=2.0", "InpTakeProfitRRMul=3.0",
      "InpRequireEfficiency=false", "InpRequireNearMean=true")),
    (1, _params(True, False),
     ("InpRequireEfficiency=true", "InpRequireNearMean=false")),
])
def test_native_adapter_accepts_exact_r8_parity_and_treatment_contract(mode, overrides, expected):
    text = native.settings("r8_test", mode, overrides, r2=True, r8=True)
    assert all(token in text for token in expected)


@pytest.mark.parametrize("mode,overrides", [
    (0, dict(InpRequireEfficiency=True)),
    (0, dict(InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=1, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.5, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=2.5,
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=float("nan"), InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=float("inf"),
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2.5, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=False, InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=float("nan"), InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency="yes", InpRequireNearMean=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
             InpRequireEfficiency=1, InpRequireNearMean=True)),
    (1, dict(_unknown=True)),
])
def test_native_adapter_rejects_drift_fractionals_nan_and_unknowns(mode, overrides):
    with pytest.raises(ValueError):
        native.settings("r8_test", mode, overrides, r2=True, r8=True)


@pytest.mark.parametrize("kwargs", [
    dict(r8=True), dict(r2=True, r5=True, r8=True), dict(r2=True, r6=True, r8=True),
    dict(r2=True, r7=True, r8=True), dict(r2=True, r8=True, production=True),
    dict(r2=True, r8=True, optimize=True),
])
def test_native_adapter_rejects_other_candidate_flags_production_and_optimization(kwargs):
    with pytest.raises(ValueError):
        native.settings("r8_test", 1, _params(False, True), **kwargs)


def test_legacy_native_settings_do_not_gain_r8_factor_inputs():
    text = native.settings("legacy_control", 0, {}, r2=True)
    assert "InpRequireEfficiency=" not in text
    assert "InpRequireNearMean=" not in text


def _sandbox(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    base = root / "reports" / "v25_research_20261008_postupdate"
    (root / "research").mkdir(parents=True)
    (root / "research/ResearchCandidate_R8.mq5").write_text("// synthetic test source", encoding="utf-8")
    (root / runner.CONTROL_SOURCE).write_text("// synthetic reporting control", encoding="utf-8")
    monkeypatch.setattr(runner, "SOURCE_SHA", hashlib.sha256((root/runner.SOURCE).read_bytes()).hexdigest().upper())
    monkeypatch.setattr(runner, "CONTROL_SHA", hashlib.sha256((root/runner.CONTROL_SOURCE).read_bytes()).hexdigest().upper())
    production = base / "runs" / runner.PRODUCTION_RUN
    production.mkdir(parents=True)
    (production / "accepted.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner, "R1_SHA", hashlib.sha256(runner.R1_SOURCE.read_bytes()).hexdigest().upper())
    monkeypatch.setattr(runner, "R1_SOURCE", root / "research/ResearchCandidate_R1.mq5")
    # Root check is read-only; synthetic pinned source keeps this isolated from the real tree.
    runner.R1_SOURCE.write_text("synthetic R1 source", encoding="utf-8")
    monkeypatch.setattr(runner, "R1_SHA", hashlib.sha256(runner.R1_SOURCE.read_bytes()).hexdigest().upper())
    return root, base


def _install_mocks(monkeypatch, *, dev_eligible=True, val_eligible=True, drift_name=None,
                   parity_fail_at=None, lock_json=None):
    calls, events, saved, qualified = [], [], [], []
    def fake_native_execute(name, mode=0, overrides=None, **kwargs):
        calls.append(("native", name, mode, kwargs))
        return dict(evidence_run=name, net=10.0, native_equity_dd_pct=5.0,
                    monthly={f"m{i}": {"net": 1.0} for i in range(7)})
    def fake_execute(name, mode, params, **kwargs):
        calls.append(("candidate", name, mode, dict(params), kwargs))
        events.append(("execute", name))
        return dict(evidence_run=name, net=10.0, native_equity_dd_pct=5.0,
                    monthly={f"m{i}": {"net": 1.0} for i in range(7)})
    parity_counter = {"n": 0}
    def fake_parity(left, right, **kwargs):
        parity_counter["n"] += 1
        passed = parity_fail_at != parity_counter["n"]
        events.append(("parity", left["evidence_run"], right["evidence_run"], passed))
        return dict(passed=passed)
    def verify(reference, result, **kwargs):
        events.append(("verify", result["evidence_run"]))
        if drift_name == result["evidence_run"]:
            raise ValueError("synthetic cache/runtime drift")
        return dict(passed=True)
    def qualify(result, n=150, pf=1.2):
        qualified.append(result["evidence_run"])
        if n == 40:
            return val_eligible
        return dev_eligible
    def save(path, value):
        path = Path(path)
        saved.append((path.name, json.loads(json.dumps(value))))
        events.append(("save", path.name))
        if path.name.endswith("_selection_lock.json"):
            path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(runner.native, "execute", fake_native_execute)
    monkeypatch.setattr(runner, "execute", fake_execute)
    monkeypatch.setattr(runner.native, "parity", fake_parity)
    monkeypatch.setattr(runner.native, "verify_environment", verify)
    monkeypatch.setattr(runner, "qualify", qualify)
    monkeypatch.setattr(runner, "save", save)
    monkeypatch.setattr(runner, "evaluate", lambda evidence: dict(historically_robust=True))
    return calls, events, saved, qualified


@pytest.mark.parametrize("kwargs", [
    dict(prefix="../bad", tester_login=123),
    dict(prefix="r8_good", tester_login=True),
    dict(prefix="r8_good", tester_login=123.0),
    dict(prefix="r8_good", tester_login=0),
    dict(prefix="r8_good", tester_login=123, evidence_base=Path("outside")),
])
def test_bad_root_prefix_or_login_fails_before_any_execution(tmp_path, monkeypatch, kwargs):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, _, _, _ = _install_mocks(monkeypatch)
    if "evidence_base" not in kwargs:
        kwargs["evidence_base"] = base
    with pytest.raises(ValueError):
        runner.run_all(**kwargs)
    assert calls == []


def test_controls_and_mode0_parity_precede_all_three_treatments(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, events, _, _ = _install_mocks(monkeypatch)
    runner.run_all("r8_test", 123456, evidence_base=base)
    names = [call[1] for call in calls]
    assert names[:4] == [
        runner.PRODUCTION_RUN, "r8_test_baseline", "r8_test_r1_control", "r8_test_control_k0_e0"]
    assert names[4:7] == ["r8_test_dev_k0_e1", "r8_test_dev_k1_e0", "r8_test_dev_k1_e1"]
    assert [x for x in events if x[0] == "parity"][:2] == [
        ("parity", runner.PRODUCTION_RUN, "r8_test_baseline", True),
        ("parity", "r8_test_r1_control", "r8_test_control_k0_e0", True)]
    assert all(call[3].get("tester_login") == 123456 for call in calls if call[0] == "native")
    control_call = next(call for call in calls if call[1] == "r8_test_r1_control")
    assert control_call[3]["candidate_source"] == runner.CONTROL_SOURCE


def test_reporting_control_adapter_preserves_three_inputs_and_no_factor_inputs():
    text = native.settings("r8_control", 1,
        dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0),
        r2=True, control_r1=True)
    assert "InpUseGridIndices=false" in text and "InpTPGridIndex=2" in text
    assert "InpRequireEfficiency" not in text and "InpRequireNearMean" not in text
    assert "InpTakeProfitRRMul=3.0" in text


@pytest.mark.parametrize("mode,params,flags", [
    (0, {}, dict(r2=True)), (2, {}, dict(r2=True)),
    (1, {}, dict(r2=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=2.0), dict(r2=True)),
    (1, dict(InpEntryStrength=2.5, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0), dict(r2=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0, InpLotSize=.1), dict(r2=True)),
    (1, dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0), dict(r2=True, r8=True)),
    (1, {}, dict(r2=True, production=True)), (1, {}, dict(r2=True, optimize=True)),
])
def test_reporting_control_rejects_other_modes_params_and_flags(mode, params, flags):
    with pytest.raises(ValueError):
        native.settings("r8_control", mode, params, control_r1=True, **flags)


@pytest.mark.parametrize("relative", [runner.SOURCE, runner.CONTROL_SOURCE])
def test_reporting_source_drift_blocks_before_any_launch(tmp_path, monkeypatch, relative):
    root, base = _sandbox(tmp_path, monkeypatch)
    calls, _, _, _ = _install_mocks(monkeypatch)
    (root/relative).write_text("changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="Pinned R8 reporting source"):
        runner.run_all("r8_test", 123456, evidence_base=base)
    assert calls == []


def test_failed_off_off_parity_stops_before_treatments(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, _, _, _ = _install_mocks(monkeypatch, parity_fail_at=2)
    with pytest.raises(ValueError, match="off/off"):
        runner.run_all("r8_test", 123456, evidence_base=base)
    assert not any(call[1].startswith("r8_test_dev_") for call in calls)


def test_cache_drift_aborts_candidate_before_eligibility_or_shortlist(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, events, saved, qualified = _install_mocks(monkeypatch, drift_name="r8_test_dev_k0_e1")
    with pytest.raises(ValueError, match="drift"):
        runner.run_all("r8_test", 123456, evidence_base=base)
    assert "r8_test_dev_k0_e1" not in qualified
    assert not any(name.endswith("_selection_lock.json") for name, _ in saved)
    assert not any(call[1].startswith("r8_test_dev_k1_") for call in calls)


def test_all_three_survivors_validate_lock_before_confirmation_without_reselection(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, events, saved, _ = _install_mocks(monkeypatch)
    result = runner.run_all("r8_test", 123456, evidence_base=base)
    names = [call[1] for call in calls]
    assert [n for n in names if "_val_" in n] == [
        "r8_test_val_k0_e1", "r8_test_val_k1_e0", "r8_test_val_k1_e1"]
    lock_save = next(i for i, e in enumerate(events) if e == ("save", "r8_test_selection_lock.json"))
    confirm = next(i for i, e in enumerate(events) if e == ("execute", "r8_test_confirmation"))
    assert lock_save < confirm
    assert result["selection_lock"]["reselect_after_confirmation"] is False
    assert result["promotion"] is False
    assert len(result["development_shortlist"]) == 3


def test_validation_failure_creates_ineligible_descriptive_not_promotion(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    calls, _, _, _ = _install_mocks(monkeypatch, val_eligible=False)
    result = runner.run_all("r8_test", 123456, evidence_base=base)
    desc = result["descriptive_failed_candidate"]
    assert desc["eligible"] is False and desc["promotion"] is False
    assert not any("_confirmation" in call[1] for call in calls)
    assert result["promotion"] is False


def test_preexisting_different_lock_stops_before_confirmation(tmp_path, monkeypatch):
    _, base = _sandbox(tmp_path, monkeypatch)
    lock = dict(mode=1, parameters=_params(True, True), config_tag="k1_e1")
    _install_mocks(monkeypatch)
    lockpath = base / "r8_test_selection_lock.json"
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    lockpath.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="no reselection"):
        runner.run_all("r8_test", 123456, evidence_base=base)
