from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research" / "ResearchCandidate_R4.mq5"
GENERATOR = ROOT / "research" / "build_candidate_r7.py"
PINNED_SHA = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"


def load_generator():
    spec = importlib.util.spec_from_file_location("build_candidate_r7", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def generated():
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest().upper() == PINNED_SHA
    return load_generator().build(raw.decode("utf-8-sig"))


def test_parent_is_exact_pinned_r4_and_generation_does_not_write_it():
    before = PARENT.read_bytes()
    assert hashlib.sha256(before).hexdigest().upper() == PINNED_SHA
    generated()
    assert PARENT.read_bytes() == before


def test_only_r7_target_whitelist_and_fixed_stop_rule():
    text = generated()
    assert "bool validStop=(InpStopLossATRMul==1.5);" in text
    assert "bool validTarget=(R7TargetAllowed(InpTakeProfitRRMul) && InpTakeProfitRRMul!=2.0);" in text
    assert "targetR==0.5 || targetR==0.6" in text
    assert "targetR==1.0 || targetR==2.0" in text
    assert "targetR==0.75" not in text
    assert "bool validTarget=(R7TargetAllowed(InpTakeProfitRRMul) && InpTakeProfitRRMul!=2.0);" in text


def test_mode5_validation_excludes_mode0_tp2_parity_target():
    text = generated()
    assert "targetR==1.0 || targetR==2.0" in text
    assert "InpTakeProfitRRMul!=2.0" in text
    assert "InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0" in text


def test_tp_geometry_uses_identical_multiplication_for_allowed_targets():
    text = generated()
    assert "double tpDistance = R7TargetDistance(slDistance,InpTakeProfitRRMul);" in text
    assert "return(slDistance*targetR);" in text
    assert "MathAbs(R7TargetDistance(4.0,0.5)-2.0)<1e-10" in text
    assert "MathAbs(R7TargetDistance(5.0,0.6)-3.0)<1e-10" in text


def test_fixtures_added_and_parity_contract_retained():
    text = generated()
    assert "R7_NATIVE_FIXTURES_PASS" in text
    assert text.count('ok=R2Assert(') >= 6
    assert 'InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0' in text
    assert "InpStopLossATRMul==1.0" not in text


def test_frozen_entry_and_tick_functions_unchanged():
    module = load_generator()
    parent = PARENT.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    result = generated()
    for name in ("OnTick", "CandidateR2Signal", "R2Exhaustion"):
        assert module.function(parent, name) == module.function(result, name)
    expected_original = module.replace_once(
        module.function(parent, "OriginalOnTick"),
        "double tpDistance = slDistance * InpTakeProfitRRMul;",
        "double tpDistance = R7TargetDistance(slDistance,InpTakeProfitRRMul);",
    )
    expected_original = expected_original.replace("TP=%.2f (2.0R)", "TP=%.2f (ConfiguredR)")
    assert module.function(result, "OriginalOnTick") == expected_original


def test_all_six_native_fixtures_use_diagnostic_assertions():
    text = generated()
    checks = [line for line in text.splitlines() if 'R2Assert(' in line and '"R7_' in line]
    assert len(checks) == 6
    assert len(checks) == 6
    assert all(line.lstrip().startswith("ok=R2Assert(") for line in checks)
    assert "r2FixtureChecks+=6;" not in text


def test_signal_log_tp_label_is_parameterized_without_argument_change():
    text = generated()
    assert text.count("TP=%.2f (ConfiguredR)") == 2
    assert "TP=%.2f (2.0R)" not in text
