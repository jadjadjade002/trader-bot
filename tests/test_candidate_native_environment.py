"""Same economics alone cannot prove identical native input provenance."""
import json
from unittest.mock import patch

import pytest

from research import run_v25_native as native


def records(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "ROOT", tmp_path)
    root = tmp_path / "reports" / "batch"
    root.mkdir(parents=True)
    runtime = {"terminal64.exe": "A" * 64, "metatester64.exe": "B" * 64}
    (root / "runtime_freeze.json").write_text(json.dumps(runtime))
    cache = [dict(month=m, bytes=2048, sha256="C" * 64) for m in native.months(native.START, native.END)]

    def record(name, end=native.END, change=None):
        ticks = [dict(row) for row in cache if row["month"] in native.months(native.START, end)]
        signature = dict(start=native.START, end=end, runtime=dict(runtime), tick_cache=ticks)
        if change:
            change(signature)
        folder = root / "runs" / name
        folder.mkdir(parents=True)
        result = dict(evidence_run=name)
        (folder / "accepted.json").write_text(json.dumps(dict(signature=signature, result=result)))
        (folder / "started.json").write_text(json.dumps(dict(signature=signature)))
        return result

    return root, record


def test_six_month_subset_must_match_full_reference(tmp_path, monkeypatch):
    root, record = records(tmp_path, monkeypatch)
    result = native.verify_environment(record("control"), record("dev", native.DEV_END), evidence_base=root)
    assert result == dict(passed=True, compared_months=native.months(native.START, native.DEV_END))


def test_same_size_different_tick_hash_rejected(tmp_path, monkeypatch):
    root, record = records(tmp_path, monkeypatch)
    control = record("control")
    candidate = record("dev", native.DEV_END,
        lambda sig: sig["tick_cache"][0].update(sha256="D" * 64))
    with pytest.raises(ValueError, match="Tick cache differs"):
        native.verify_environment(control, candidate, evidence_base=root)


def test_runtime_drift_rejected_against_own_freeze(tmp_path, monkeypatch):
    root, record = records(tmp_path, monkeypatch)
    control = record("control")
    candidate = record("dev", native.DEV_END,
        lambda sig: sig["runtime"].update({"terminal64.exe": "D" * 64}))
    with pytest.raises(ValueError, match="runtime differs"):
        native.verify_environment(control, candidate, evidence_base=root)


def test_started_signature_cannot_disagree(tmp_path, monkeypatch):
    root, record = records(tmp_path, monkeypatch)
    control, candidate = record("control"), record("dev", native.DEV_END)
    (root / "runs/dev/started.json").write_text(json.dumps(dict(signature={})))
    with pytest.raises(ValueError, match="provenance differs"):
        native.verify_environment(control, candidate, evidence_base=root)


def test_parity_checks_environment_before_report_economics():
    with patch.object(native, "verify_environment", side_effect=ValueError("Tick cache differs")), \
         patch.object(native, "native_sequence") as report:
        with pytest.raises(ValueError, match="Tick cache differs"):
            native.parity(dict(evidence_run="control"), dict(evidence_run="candidate"))
        report.assert_not_called()
