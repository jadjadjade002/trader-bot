from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import tempfile
from unittest.mock import patch
import pytest

from research import build_candidate_r5 as builder
from research import run_candidate_r5 as runner
from research import analyze_candidate_r5 as analyzer


ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "research/ResearchCandidate_R4.mq5"
R5 = ROOT / "research/ResearchCandidate_R5.mq5"


def test_r5_generation_is_reproducible_and_r4_unchanged():
    before = sha256(R4.read_bytes()).hexdigest().upper()
    assert before == builder.EXPECTED_R4_SHA256
    assert builder.generate() == R5.read_text(encoding="utf-8")
    assert sha256(R4.read_bytes()).hexdigest().upper() == before


def test_mode5_adds_only_optional_completed_m1_alignment_gate():
    source = R5.read_text(encoding="utf-8")
    assert 'input bool InpRequireM1Alignment=false' in source
    context = re.search(r"bool ReadR2Context\(.*?\n}\n", source, re.S).group(0)
    assert "ReadClosed(entryFast,1,ema9)" in context
    assert "ReadClosed(entrySlow,1,ema20)" in context
    assert "PERIOD_M1,1" in source and "CopyR2Rates(23,r)" in source
    assert "InpRequireM1Alignment && !closedM1Aligned" in source
    assert "candidateSide=R2Exhaustion(atr,direction,r,ema9,e9prev)" in source
    assert "m1_alignment_missing" in source
    assert "m1_aligned_observed" in source and "m1_not_aligned_observed" in source
    assert '"F_m1_alignment_sides"' in source and '"F_m1_alignment_equality"' in source


def test_four_c0_cells_and_selection_release_gates_frozen():
    cells = runner.configurations()
    assert len(cells) == 4
    assert {(p["InpEntryStrength"], p["InpRequireM1Alignment"]) for _, p, _ in cells} == set(product((0, 1), (False, True)))
    assert all(mode == 5 and p["InpStopLossATRMul"] == 1.5 and p["InpTakeProfitRRMul"] == 1.0 for mode, p, _ in cells)
    source = (ROOT / "research/run_candidate_r5.py").read_text(encoding="utf-8")
    assert "[:3]" in source
    assert "qualify(confirm, 40, 1.10)" in source and "qualify(full, 150, 1.15)" in source
    assert "positive_months >= 7" in source and "full[\"net\"] > baseline[\"net\"]" in source


def test_schedule_dependent_configs_are_explicitly_unrun():
    source = (ROOT / "research/run_candidate_r5.py").read_text(encoding="utf-8")
    assert 'schedule_status="UNRUN_SCHEDULE_UNVERIFIED"' in source
    assert 'R5-P0-A0-C1' in source and 'R5-P1-A1-C1' in source


def test_diagnostics_schema_marks_context_and_censors_blocked_rows():
    source = R5.read_text(encoding="utf-8")
    header = re.search(r'FileWrite\(diagnosticFile,"bar".*?\);', source, re.S).group(0)
    assert '"body_atr"' not in header and '"close_location"' not in header
    for field in ("features_evaluated", "opportunity_status", "m1_ema9", "m1_ema20",
                  "m5_ema20", "m5_ema50", "m5_ema20_past6", "m5_slope_5bar_delta", "m1_atr",
                  "m5_atr", "signed_displacement_atr_5bars", "quote_bid", "quote_ask", "spread",
                  "initial_sl_distance", "initial_tp_distance", "initial_sl_price",
                  "initial_tp_price", "session_id", "session_endpoint", "time_to_close",
                  "signal_bar_open", "signal_bar_high", "signal_bar_low", "signal_bar_close",
                  "signal_body_atr", "close_location_from_low"):
        assert f'"{field}"' in header
    assert '"n/a","n/a","n/a"' in source
    assert '"censored_held_position"' in source and '"censored_circuit_breaker"' in source
    assert '"blocked_before_context"' in source
    assert 'R5FeatureText(r5M1Ema9,haveFeatures)' in source
    assert "r5SignalBodyATR=MathAbs(r[0].close-r[0].open)/atr" in source
    assert "(r[0].close-r[0].low)/signalRange" in source


def test_r5_logging_keeps_signal_order_and_buffer_reads_frozen():
    r4 = R4.read_text(encoding="utf-8")
    r5 = R5.read_text(encoding="utf-8")
    for text in (r4, r5):
        held = text.index("if(HasOpenPosition())", text.index("void OriginalOnTick()"))
        breaker = text.index("if(IsCircuitBreakerActive())", held)
        signal = text.index("signal=CandidateR2Signal(atr);", breaker)
        assert held < breaker < signal
    def read_context(source):
        return re.search(r"bool ReadR2Context\(.*?\n}\n", source, re.S).group(0)
    old_reads = re.findall(r"ReadClosed\(", read_context(r4))
    new_reads = re.findall(r"ReadClosed\(", read_context(r5))
    assert len(old_reads) == len(new_reads) == 6
    assert "CopyBuffer(" not in re.search(r"void CompleteR5QuoteDiagnostics\(.*?\n}\n", r5, re.S).group(0)


@pytest.mark.parametrize("fresh_controls", (False, True))
def test_both_r4_a0_controls_reconcile_before_shortlist_and_record_provenance(fresh_controls):
    events = []
    r4_controls = []
    calls = []
    environment_checks = []
    original_save = runner.save
    shortlist_marked = False
    final_progress = {}
    test_base = None
    test_old_base = None

    def signature_for(name, kwargs):
        source = ROOT / ("AegisPredator_v24.mq5" if kwargs.get("production")
                         else kwargs.get("candidate_source", runner.SOURCE))
        return {"source_sha": sha256(source.read_bytes()).hexdigest().upper()}

    def store_or_reuse(name, kwargs, value):
        root = Path(kwargs.get("evidence_base", test_base)).resolve()
        accepted_path = root / "runs" / name / "accepted.json"
        if accepted_path.is_file():
            return json.loads(accepted_path.read_text(encoding="utf-8"))["result"]
        accepted_path.parent.mkdir(parents=True, exist_ok=True)
        accepted = {"signature": signature_for(name, kwargs), "result": value}
        accepted_path.write_text(json.dumps(accepted), encoding="utf-8")
        return value

    def fake_execute(name, *args, **kwargs):
        events.append(name)
        calls.append((name, args, dict(kwargs)))
        if name.startswith("r4_a_dev_") or name.startswith("r5_test_r4_control_"):
            r4_controls.append((name, kwargs.get("candidate_source"), kwargs.get("evidence_base")))
        result = dict(evidence_run=name, net=-1.0, net_profit_factor=0.0,
                    trades=0, native_equity_dd_pct=0.0)
        return store_or_reuse(name, kwargs, result)

    def fake_parity(left, right, **kwargs):
        if left["evidence_run"].startswith("r4_a_dev_") or left["evidence_run"].startswith("r5_test_r4_control_"):
            events.append("reconciled_" + left["evidence_run"])
        return dict(passed=True)

    def fake_verify_environment(reference, result, **kwargs):
        environment_checks.append((reference["evidence_run"], result["evidence_run"], kwargs))

    def tracked_save(path, value):
        nonlocal shortlist_marked, final_progress
        final_progress = value
        if "development_shortlist" in value and not shortlist_marked:
            events.append("shortlist")
            shortlist_marked = True
        original_save(path, value)

    with tempfile.TemporaryDirectory(prefix=".r5_runner_test_", dir=ROOT) as temp_root:
        test_base = Path(temp_root) / "reports" / "v25_research_20261008"
        test_old_base = Path(temp_root) / "reports" / "v25_research_20261007"
        for preset in (0, 1):
            old_name = f"r4_a_dev_5_{preset}_sl1p5_tp1p0"
            old_path = test_old_base / "runs" / old_name / "accepted.json"
            old_path.parent.mkdir(parents=True, exist_ok=True)
            old_record = {"signature": {"source_sha": sha256(R4.read_bytes()).hexdigest().upper()},
                "result": {"evidence_run": old_name}}
            old_path.write_text(json.dumps(old_record), encoding="utf-8")
        sentinels = {p: p.read_bytes() for p in test_old_base.glob("runs/*/accepted.json")}
        with patch.object(runner, "BASE", test_base), \
             patch.object(runner, "OLD_BASE", test_old_base), \
             patch.object(runner, "APPROVED_R5_BASES", {test_base.resolve(), runner.POSTUPDATE_BASE.resolve()}), \
             patch.object(runner.native, "execute", side_effect=fake_execute), \
             patch.object(runner.native, "parity", side_effect=fake_parity), \
             patch.object(runner.native, "verify_environment", return_value={"passed": True}), \
             patch.object(runner.native, "verify_environment", side_effect=fake_verify_environment), \
             patch.object(runner, "save", side_effect=tracked_save):
            runner.run_all("r5_test", tester_login=24680, fresh_controls=fresh_controls)
        assert all(path.read_bytes() == data for path, data in sentinels.items())

    expected_names = (["r5_test_r4_control_p0", "r5_test_r4_control_p1"] if fresh_controls else [
        "r4_a_dev_5_0_sl1p5_tp1p0", "r4_a_dev_5_1_sl1p5_tp1p0"])
    production_name = "r5_test_production_v24" if fresh_controls else "r1_b_production_v24"
    assert [row[0] for row in r4_controls] == expected_names
    assert all(row[1] == "research/ResearchCandidate_R4.mq5" for row in r4_controls)
    assert all(row[2] == (test_base if fresh_controls else test_old_base) for row in r4_controls)
    assert all(events.index("reconciled_" + row[0]) < events.index("shortlist") for row in r4_controls)
    assert environment_checks[0][0:2] == (production_name, "r5_test_baseline")
    assert all(check[0] == "r5_test_baseline" for check in environment_checks[1:])
    assert all(check[2]["evidence_base"] == test_base for check in environment_checks[1:])
    by_name = {name: (args, kwargs) for name, args, kwargs in calls}
    fresh = [name for name in by_name if name.startswith("r5_test_")]
    assert fresh and all(by_name[name][1].get("tester_login") == 24680 for name in fresh)
    if fresh_controls:
        assert by_name[production_name][1].get("tester_login") == 24680
        assert by_name[production_name][1]["evidence_base"] == test_base
    else:
        assert "tester_login" not in by_name[production_name][1]
        assert by_name[production_name][1]["evidence_base"] == test_old_base
    r4_calls = [(name, kwargs) for name, _, kwargs in calls if name in expected_names]
    assert all(kwargs.get("tester_login") == 24680 for _, kwargs in r4_calls) if fresh_controls else all(
        "tester_login" not in kwargs for _, kwargs in r4_calls)
    for preset, aligned in product((0, 1), (False, True)):
        name = f"r5_test_dev_p{preset}_a{int(aligned)}_c0"
        params = by_name[name][0][1]
        assert params["InpEntryStrength"] == preset
        assert params["InpRequireM1Alignment"] is aligned
        assert params["InpStopLossATRMul"] == 1.5 and params["InpTakeProfitRRMul"] == 1.0
    assert final_progress["control_policy"] == ("fresh_same_cache" if fresh_controls else "legacy_r4")
    assert final_progress["control_mapping"] == {str(p): expected_names[p] for p in (0, 1)}
    assert final_progress["baseline_control_run"] == production_name
    expected_alias = "r5_base" if fresh_controls else "r4_base"
    assert final_progress["control_roots"] == {"baseline_production": expected_alias,
                                                "r4_controls": expected_alias}
    assert final_progress["evidence_roots"] == {
        "r4_base": "reports/v25_research_20261007",
        "r5_base": test_base.resolve().relative_to(ROOT.resolve()).as_posix()}
    assert final_progress["r4_control_parity"]["0"]["control_root"] == expected_alias


def test_tester_login_must_be_positive_int():
    for invalid in (None, 0, -1, True, 123.0, "123"):
        with patch.object(runner, "execute") as execute:
            with pytest.raises(ValueError, match="positive integer"):
                runner.run_all("r5_invalid", tester_login=invalid)
            execute.assert_not_called()


def test_evidence_root_override_rejects_unapproved_path_before_execution():
    import pytest
    with patch.object(runner, "execute") as execute:
        with pytest.raises(ValueError, match="approved postupdate root"):
            runner.run_all("r5_bad_root", tester_login=123456789,
                           evidence_base=ROOT / "reports" / "arbitrary")
        execute.assert_not_called()


def test_runner_manifest_passes_analyzer_control_mapping_contract():
    prefix = "r5_integration"
    captured = {}

    def fake_execute(name, *args, **kwargs):
        result = dict(evidence_run=name, net=-1.0, net_profit_factor=0.0,
                      trades=0, native_equity_dd_pct=0.0)
        return result

    def fake_provenance(name, result, root, *, policy, native_run_id):
        return dict(kind="fresh_native", evidence_run=name,
            evidence_root=root.resolve().relative_to(ROOT.resolve()).as_posix(),
            source_sha256=sha256(R4.read_bytes()).hexdigest().upper(),
            signature_sha256="A" * 64, native_run_id=native_run_id)

    def capture_save(path, progress):
        captured.update(json.loads(json.dumps(progress)))

    with patch.object(runner, "execute", side_effect=fake_execute), \
         patch.object(runner.native, "execute", side_effect=fake_execute), \
         patch.object(runner.native, "parity", return_value={"passed": True}), \
         patch.object(runner.native, "verify_environment", return_value={"passed": True}), \
         patch.object(runner, "save", side_effect=capture_save), \
         patch.object(runner, "_r4_control_provenance", side_effect=fake_provenance):
        runner.run_all(prefix, tester_login=123456789, fresh_controls=True,
                       evidence_base=runner.POSTUPDATE_BASE)

    # The progress object was JSON-round-tripped to model the on-disk manifest.
    policy, mapping = analyzer._r5_control_mapping(captured, prefix)
    assert policy == "fresh_same_cache"
    assert mapping == {0: f"{prefix}_r4_control_p0", 1: f"{prefix}_r4_control_p1"}
    with patch.object(analyzer, "_load_r5_progress", return_value=captured):
        mapped = analyzer._r5_run_mapping(runner.POSTUPDATE_BASE, prefix)
    assert mapped["p0_a0"][0] == f"{prefix}_dev_p0_a0_c0"
    assert mapped["p1_a1"][0] == f"{prefix}_dev_p1_a1_c0"
    assert captured["evidence_roots"]["r5_base"] == "reports/v25_research_20261008_postupdate"


def test_cross_run_cache_drift_stops_before_eligibility_or_shortlist():
    saved = []
    def fake_execute(name, *args, **kwargs):
        return dict(evidence_run=name)
    with patch.object(runner, "execute", side_effect=fake_execute), \
         patch.object(runner.native, "parity", return_value={"passed": True}), \
         patch.object(runner.native, "verify_environment", side_effect=[
             {"passed": True}, ValueError("Tick cache differs")]), \
         patch.object(runner, "qualify") as qualify, \
         patch.object(runner, "save", side_effect=lambda path, record: saved.append(json.loads(json.dumps(record)))):
        with pytest.raises(ValueError, match="Tick cache differs"):
            runner.run_all("r5_drift", tester_login=123456789, fresh_controls=True,
                           evidence_base=runner.POSTUPDATE_BASE)
        qualify.assert_not_called()
    assert len(saved) == 1
    assert saved[0]["development"] == []
    assert "development_shortlist" not in saved[0]
