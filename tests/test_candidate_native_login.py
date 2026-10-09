"""Regression tests for tester-login signature compatibility and retry propagation."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from research import run_v25_native as native


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence_root():
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tester_login_test_", dir=reports) as temp:
        yield Path(temp)


def _mock_execution_environment():
    runtime = {"terminal64.exe": "terminal-hash", "metatester64.exe": "tester-hash"}
    ticks = [dict(month=202512, bytes=2048, sha256="a" * 64)]
    return (
        patch.object(native, "freeze", return_value=runtime),
        patch.object(native, "cache_manifest", return_value=ticks),
        patch.object(native, "sha", side_effect=lambda path: "source-hash" if Path(path).suffix == ".mq5" else "binary-hash"),
    ), runtime, ticks


def test_accepted_legacy_signature_reuses_without_login_field(evidence_root):
    name = "r5_legacy_signature"
    mode, overrides = 5, {"InpEntryStrength": 0, "InpStopLossATRMul": 1.5,
                          "InpTakeProfitRRMul": 1.0, "InpRequireM1Alignment": False}
    start, end, deposit, delay = native.START, native.END, 10000, 200
    runtime = {"terminal64.exe": "terminal-hash", "metatester64.exe": "tester-hash"}
    ticks = [dict(month=202512, bytes=2048, sha256="a" * 64)]
    text = native.settings(name, mode, overrides, False, False, True, True)
    signature = dict(start=start, end=end, mode=mode, overrides=overrides,
        deposit=deposit, optimize=False, production=False, delay_ms=delay,
        runtime=runtime, source_sha="source-hash", binary_sha="binary-hash",
        set_sha=hashlib.sha256(text.encode("utf-16")).hexdigest(), tick_cache=ticks)
    run_dir = evidence_root / "runs" / name
    run_dir.mkdir(parents=True)
    accepted_result = {"evidence_run": name, "net": 12.34}
    (run_dir / "accepted.json").write_text(json.dumps(
        dict(signature=signature, result=accepted_result)), encoding="utf-8")

    patches, _, _ = _mock_execution_environment()
    with patches[0], patches[1], patches[2], patch.object(native.subprocess, "Popen") as popen:
        result = native.execute(name, mode, overrides, candidate_source="research/ResearchCandidate_R5.mq5",
                                evidence_base=evidence_root)
    assert result == accepted_result
    assert "tester_connection_login" not in signature
    popen.assert_not_called()


def test_retry_recursion_carries_explicit_login_without_launching_native(evidence_root):
    name = "r5_retry_login"
    run_dir = evidence_root / "runs" / name
    run_dir.mkdir(parents=True)
    original_execute = native.execute
    captured = {}

    class RetryIntercept(Exception):
        pass

    def intercept_retry(retry_name, *args, **kwargs):
        captured.update(name=retry_name, kwargs=kwargs)
        raise RetryIntercept

    patches, _, _ = _mock_execution_environment()
    with patches[0], patches[1], patches[2], patch.object(native, "execute", side_effect=intercept_retry):
        with pytest.raises(RetryIntercept):
            original_execute(name, mode=5,
                overrides={"InpEntryStrength": 0, "InpStopLossATRMul": 1.5,
                           "InpTakeProfitRRMul": 1.0, "InpRequireM1Alignment": False},
                candidate_source="research/ResearchCandidate_R5.mq5",
                evidence_base=evidence_root, tester_login=123456789)
    assert captured["name"] == f"{name}_retry1"
    assert captured["kwargs"]["tester_login"] == 123456789
    assert captured["kwargs"]["candidate_source"] == "research/ResearchCandidate_R5.mq5"
    assert captured["kwargs"]["evidence_base"] == evidence_root.resolve()
