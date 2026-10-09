"""R7 runner and adapter contract tests. Native execution is always mocked."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest

from research import run_candidate_r7 as r7
from research import run_v25_native as native


@pytest.fixture
def harness(monkeypatch):
    temp = tempfile.TemporaryDirectory(prefix=".r7_runner_test_", dir=r7.ROOT)
    base = Path(temp.name) / "reports" / "v25_research_20261008_postupdate"
    monkeypatch.setattr(r7, "BASE", base)
    for name in (r7.PRODUCTION_RUN, *r7.CONTROL_RUNS.values()):
        folder = base / "runs" / name
        folder.mkdir(parents=True)
        (folder / "accepted.json").write_text("{}", encoding="utf-8")

    events = []

    def fake_result(name, *, stage="control", params=None):
        values = dict(evidence_run=name, net=1.0, native_equity_dd_pct=0.5,
                      monthly={f"2026-{month:02d}": {"net": 1.0} for month in range(1, 8)})
        if params is not None:
            values["parameters"] = params
        values["stage"] = stage
        return values

    def candidate_execute(name, mode, parameters, **kwargs):
        events.append(("candidate", name, mode, dict(parameters), kwargs))
        if "_dev_" in name:
            stage = "development"
        elif "_val_" in name:
            stage = "validation"
        elif name.endswith("_confirmation"):
            stage = "confirmation"
        elif name.endswith("_locked10m"):
            stage = "full"
        else:
            stage = "other"
        return fake_result(name, stage=stage, params=parameters)

    def native_execute(name, mode=0, overrides=None, **kwargs):
        events.append(("reference", name, mode, dict(overrides or {}), kwargs))
        return fake_result(name, stage="reference", params=overrides)

    def parity(*args, **kwargs):
        events.append(("parity", args[0]["evidence_run"], args[1]["evidence_run"], kwargs))
        return {"passed": True}

    def verify(reference, result, **kwargs):
        events.append(("environment", result["evidence_run"], kwargs))
        return {"passed": True}

    def save(path, value):
        events.append(("save", Path(path).name, json.loads(json.dumps(value))))

    monkeypatch.setattr(r7, "execute", candidate_execute)
    monkeypatch.setattr(native, "execute", native_execute)
    monkeypatch.setattr(native, "parity", parity)
    monkeypatch.setattr(native, "verify_environment", verify)
    monkeypatch.setattr(r7, "save", save)
    monkeypatch.setattr(r7, "qualify", lambda result, *args: result["stage"] in {"development", "validation"})
    monkeypatch.setattr(r7, "evaluate", lambda evidence: {"historically_robust": False})
    yield base, events
    temp.cleanup()


def test_exact_four_frozen_cells():
    cells = r7.configurations()
    assert len(cells) == 4
    assert [(mode, params["InpEntryStrength"], params["InpTakeProfitRRMul"])
            for mode, params, _ in cells] == [
                (5, 0, 0.5), (5, 0, 0.6), (5, 1, 0.5), (5, 1, 0.6)]
    assert [tag for _, _, tag in cells] == ["p0_tp0p5", "p0_tp0p6", "p1_tp0p5", "p1_tp0p6"]
    assert all(params["InpStopLossATRMul"] == 1.5 and set(params) == {
        "InpEntryStrength", "InpStopLossATRMul", "InpTakeProfitRRMul"}
        for _, params, _ in cells)


@pytest.mark.parametrize("prefix,login,root", [
    ("bad-prefix", 12345, None), ("r7_a", None, None), ("r7_a", True, None),
    ("r7_a", 1.5, None), ("r7_a", "123", None), ("r7_a", 0, None),
    ("r7_a", 12345, Path("reports/not-approved")),
])
def test_invalid_root_login_or_prefix_rejects_before_any_native_call(
        harness, prefix, login, root):
    base, events = harness
    with pytest.raises(ValueError):
        r7.run_all(prefix, login, evidence_base=(root if root is not None else base))
    assert not [event for event in events if event[0] in {"candidate", "reference", "parity"}]


def test_three_controls_complete_before_any_development_cell(harness):
    base, events = harness
    r7.run_all("r7_unit", 113802049, evidence_base=base)
    first_dev = next(i for i, event in enumerate(events)
                     if event[0] == "candidate" and "_dev_" in event[1])
    prefix_events = events[:first_dev]
    references = [event[1] for event in prefix_events if event[0] == "reference"]
    candidate_controls = [event[1] for event in prefix_events
                          if event[0] == "candidate" and "control" in event[1]]
    assert references == [r7.PRODUCTION_RUN, *r7.CONTROL_RUNS.values()]
    assert candidate_controls == ["r7_unit_tp1_control_p0", "r7_unit_tp1_control_p1"]
    assert next(i for i, event in enumerate(prefix_events)
                if event[0] == "candidate" and event[1] == "r7_unit_baseline") < next(
                    i for i, event in enumerate(prefix_events)
                    if event[0] == "candidate" and event[1] == "r7_unit_tp1_control_p0")
    dev_names = [event[1] for event in events[first_dev:] if event[0] == "candidate" and "_dev_" in event[1]]
    assert dev_names == [f"r7_unit_dev_{tag}" for _, _, tag in r7.configurations()]


def test_control_parity_failure_stops_before_development(harness, monkeypatch):
    base, events = harness
    calls = iter((True, False))  # mode-0 parity passes; first R4 TP1 parity fails
    monkeypatch.setattr(native, "parity", lambda *args, **kwargs: {"passed": next(calls)})
    with pytest.raises(ValueError, match="TP1 P0 exact R4 parity failed"):
        r7.run_all("r7_unit", 113802049, evidence_base=base)
    assert not any(event[0] == "candidate" and "_dev_" in event[1] for event in events)


def test_environment_drift_stops_before_qualification(harness, monkeypatch):
    base, events = harness
    qualified = Mock(return_value=True)
    monkeypatch.setattr(r7, "qualify", qualified)

    def drift(reference, result, **kwargs):
        events.append(("environment", result["evidence_run"], kwargs))
        if "_dev_" in result["evidence_run"]:
            raise ValueError("Tick cache differs across accepted controls/candidates")
        return {"passed": True}

    monkeypatch.setattr(native, "verify_environment", drift)
    with pytest.raises(ValueError, match="Tick cache differs"):
        r7.run_all("r7_unit", 113802049, evidence_base=base)
    qualified.assert_not_called()


def test_all_development_survivors_reach_validation_without_top3_truncation(harness):
    base, events = harness
    r7.run_all("r7_unit", 113802049, evidence_base=base)
    validation = [event for event in events if event[0] == "candidate" and "_val_" in event[1]]
    assert len(validation) == 4
    assert [event[1] for event in validation] == [
        f"r7_unit_val_{tag}" for _, _, tag in r7.configurations()]
    assert any(event[0] == "save" and event[1] == "r7_unit_selection_lock.json" for event in events)


def test_lock_is_saved_before_confirmation_and_confirmation_cannot_reselect(harness):
    base, events = harness
    r7.run_all("r7_unit", 113802049, evidence_base=base)
    lock_save = next(i for i, event in enumerate(events)
                     if event[0] == "save" and event[1] == "r7_unit_selection_lock.json")
    confirmation = next(i for i, event in enumerate(events)
                        if event[0] == "candidate" and event[1] == "r7_unit_confirmation")
    assert lock_save < confirmation
    lock = next(event[2] for event in events if event[0] == "save" and event[1] == "r7_unit_selection_lock.json")

    # A prior lock for a different cell must stop before any confirmation replay.
    prior = dict(lock, config_tag="p1_tp0p6", parameters={
        "InpEntryStrength": 1, "InpStopLossATRMul": 1.5, "InpTakeProfitRRMul": 0.6})
    # Use canonical run name to exercise the actual fixed lock path.
    (base / "r7_unit_selection_lock.json").write_text(json.dumps(prior), encoding="utf-8")
    events.clear()
    with pytest.raises(ValueError, match="R7 selection changed, no reselection"):
        r7.run_all("r7_unit", 113802049, evidence_base=base)
    assert not any(event[0] == "candidate" and event[1] == "r7_unit_confirmation" for event in events)


def test_r7_adapter_exact_parity_and_target_cells():
    baseline = native.settings("r7_parity", 0, {}, r2=True, r7=True)
    assert "InpExperimentMode=0\n" in baseline
    assert "InpEntryStrength=0\n" in baseline
    assert "InpStopLossATRMul=1.5\n" in baseline
    assert "InpTakeProfitRRMul=2.0\n" in baseline
    for preset in (0, 1):
        for target in (0.5, 0.6):
            text = native.settings("r7_cell", 5, {"InpEntryStrength": preset,
                "InpStopLossATRMul": 1.5, "InpTakeProfitRRMul": target}, r2=True, r7=True)
            assert f"InpEntryStrength={preset}\n" in text
            assert f"InpTakeProfitRRMul={target}\n" in text


@pytest.mark.parametrize("kwargs", [
    {"r7": True}, {"r2": True, "r5": True, "r7": True},
    {"r2": True, "r6": True, "r7": True},
    {"r2": True, "r7": True, "production": True},
    {"r2": True, "r7": True, "optimize": True},
])
def test_r7_adapter_rejects_cross_adapter_or_nonresearch_modes(kwargs):
    with pytest.raises(ValueError):
        native.settings("r7_bad", 5, {}, **kwargs)


@pytest.mark.parametrize("mode,overrides", [
    (1, {}), (6, {}), (7, {}), (5, {"InpEntryStrength": 1.5}),
    (5, {"InpEntryStrength": "NaN"}), (5, {"InpTakeProfitRRMul": 0.4}),
    (5, {"InpTakeProfitRRMul": 0.75}), (5, {"InpTakeProfitRRMul": 2.0}),
    (5, {"InpStopLossATRMul": 2.0}), (0, {"InpTakeProfitRRMul": 1.0}),
    (0, {"InpEntryStrength": 1}), (5, {"InpLotSize": 0.1}),
])
def test_r7_adapter_rejects_unknown_or_changed_frozen_inputs(mode, overrides):
    with pytest.raises(ValueError):
        native.settings("r7_bad", mode, overrides, r2=True, r7=True)


def test_r7_adapter_rejects_nonfinite_target_and_preserves_older_adapters():
    for target in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            native.settings("r7_bad", 5, {"InpTakeProfitRRMul": target}, r2=True, r7=True)
    assert "InpRequireM1Alignment=false\n" in native.settings("r5_ok", 5,
        {"InpTakeProfitRRMul": 1.0}, r2=True, r5=True)
    assert "InpExperimentMode=6\n" in native.settings("r6_ok", 6,
        {"InpEntryStrength": 0}, r2=True, r6=True)
    assert "ExpertParameters" not in native.settings("production", 0, {}, production=True)
    assert "InpStopLossATRMul=1.5||1.0||0.5||2.0||Y\n" in native.settings(
        "optimize", 1, {}, optimize=True)
