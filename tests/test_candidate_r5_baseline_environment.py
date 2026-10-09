"""Independent analyzer must include full-period production and mode0 controls."""
import hashlib
import json

import pytest

from research import analyze_candidate_r5 as analysis
from research import run_v25_native as native


@pytest.fixture
def controls(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "ROOT", tmp_path)
    root = tmp_path / "reports/batch"
    root.mkdir(parents=True)
    runtime = {"terminal64.exe": "A" * 64, "metatester64.exe": "B" * 64}
    (root / "runtime_freeze.json").write_text(json.dumps(runtime))
    cache = [dict(month=m, bytes=2048, sha256="C" * 64) for m in native.months(native.START, native.END)]
    native_rows = {}
    prefix = "r5_test"
    def record(name, production=False, end=native.END):
        folder = root / "runs" / name
        folder.mkdir(parents=True)
        text = native.settings(name, 0, {}, production=production, r2=not production, r5=not production)
        signature = dict(start=native.START, end=end, mode=0, overrides={}, deposit=10000,
            delay_ms=200, optimize=False, production=production, runtime=runtime,
            tick_cache=[row for row in cache if row["month"] in native.months(native.START, end)],
            source_sha=native.SOURCE_HASH if production else analysis.R5_SOURCE_SHA256,
            binary_sha=native.BINARY_HASH if production else analysis.R5_BINARY_SHA256,
            set_sha=hashlib.sha256(text.encode("utf-16")).hexdigest())
        result = dict(evidence_run=name, native={"History Quality": "100% real ticks"},
            cache_hashes_verified=True, native_mql_fixture_checks=None if production else 27)
        (folder / "accepted.json").write_text(json.dumps(dict(signature=signature, result=result)))
        (folder / "started.json").write_text(json.dumps(dict(signature=signature)))
        (folder / f"{name}.set").write_text(text, encoding="utf-16")
        native_rows[name] = result["native"]
        return result
    baseline = record(prefix + "_baseline")
    production = record(prefix + "_production_v24", True)
    runs = [dict(root=root, result=record("dev"+str(i), end=native.DEV_END)) for i in range(6)]
    monkeypatch.setattr(analysis, "report_rows", lambda path: (native_rows[path.stem], []))
    monkeypatch.setattr(native, "parity", lambda left, right, **kwargs:
        native.verify_environment(left, right, evidence_base=kwargs["evidence_base"],
                                  reference_base=kwargs["production_base"]))
    progress = dict(baseline=baseline, baseline_control_run=production["evidence_run"],
                    control_policy="fresh_same_cache")
    return root, prefix, progress, runs


def test_independent_analyzer_checks_eight_environments(controls):
    root, prefix, progress, runs = controls
    result = analysis._validate_baseline_environment(progress, prefix, root, root, runs)
    assert result["accepted_environments_checked"] == 8
    assert result["parity"]["passed"] is True


def test_production_signature_mode_drift_rejected(controls):
    root, prefix, progress, runs = controls
    folder = root / "runs" / progress["baseline_control_run"]
    accepted = json.loads((folder / "accepted.json").read_text())
    accepted["signature"]["mode"] = 1
    (folder / "accepted.json").write_text(json.dumps(accepted))
    (folder / "started.json").write_text(json.dumps(dict(signature=accepted["signature"])))
    with pytest.raises(ValueError, match="source/settings contract"):
        analysis._validate_baseline_environment(progress, prefix, root, root, runs)


def test_production_cache_drift_blocks_same_economics(controls):
    root, prefix, progress, runs = controls
    folder = root / "runs" / progress["baseline_control_run"]
    accepted = json.loads((folder / "accepted.json").read_text())
    accepted["signature"]["tick_cache"][0]["sha256"] = "D" * 64
    (folder / "accepted.json").write_text(json.dumps(accepted))
    (folder / "started.json").write_text(json.dumps(dict(signature=accepted["signature"])))
    with pytest.raises(ValueError, match="Tick cache differs"):
        analysis._validate_baseline_environment(progress, prefix, root, root, runs)


def test_mutated_set_rejected(controls):
    root, prefix, progress, runs = controls
    name = progress["baseline"]["evidence_run"]
    (root / "runs" / name / f"{name}.set").write_text("InpLotSize=1\n", encoding="utf-16")
    with pytest.raises(ValueError, match="SET signature"):
        analysis._validate_baseline_environment(progress, prefix, root, root, runs)
