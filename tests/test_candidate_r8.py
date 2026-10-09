"""R8 generator contract and feature math tests; builds only in memory."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

import pytest

from research import build_candidate_r8 as generator


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research" / "ResearchCandidate_R1.mq5"


def generated() -> str:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest().upper() == generator.PARENT_SHA256
    return generator.build(raw.decode("utf-8-sig"))


def _er(closes):
    if len(closes) != 11 or any(x <= 0 for x in closes):
        return None
    path = sum(abs(closes[i] - closes[i + 1]) for i in range(10))
    if path <= 0:
        return None
    value = abs(closes[0] - closes[10]) / path
    return value if 0 <= value <= 1 else None


def _filewrite_args(source, marker, index=0):
    start = -1
    cursor = 0
    for _ in range(index + 1):
        start = source.find(marker, cursor)
        assert start >= 0
        cursor = start + len(marker)
    opening = source.find("(", start)
    depth, quoted, escaped = 0, False, False
    args, field_start = [], opening + 1
    for pos in range(opening, len(source)):
        char = source[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                args.append(source[field_start:pos].strip())
                return args
        elif char == "," and depth == 1:
            args.append(source[field_start:pos].strip())
            field_start = pos + 1
    raise AssertionError("unterminated FileWrite call")


def test_parent_hash_and_generation_do_not_modify_source():
    before = PARENT.read_bytes()
    assert hashlib.sha256(before).hexdigest().upper() == generator.PARENT_SHA256
    generated()
    assert PARENT.read_bytes() == before
    assert not generator.OUTPUT.exists() or not generator.OUTPUT.samefile(PARENT)


def test_r8_source_is_tester_only_exact_two_mode_whitelist():
    text = generated()
    assert '#property version   "24.98"' in text
    validator = generator.function(text, "ValidateR8Inputs")
    assert "MQL_OPTIMIZATION" in validator
    assert "InpExperimentMode==0" in validator and "InpExperimentMode==1" in validator
    assert "InpEntryStrength==0" in validator and "InpEntryStrength==2" in validator
    assert "InpStopLossATRMul==1.5" in validator and "InpTakeProfitRRMul==2.0" in validator
    assert "InpStopLossATRMul==2.0" in validator and "InpTakeProfitRRMul==3.0" in validator
    for frozen in ("InpMaxHoldBars!=60", "InpMinSLPoints!=150", "InpLotSize!=0.01",
                   "InpMagicNumber!=992300", "InpTargetAccount!=0", "InpFadeBreakouts",
                   "InpUseGridIndices", "InpTPGridIndex!=2", "InpEnableCircuitBreaker",
                   "InpEnableMarginGuard", "InpEnableHardSL"):
        assert frozen in validator


def test_parent_signal_and_execution_core_are_frozen():
    source = PARENT.read_text(encoding="utf-8-sig")
    text = generated()
    assert generator.function(text, "R8ParentSignal") == generator.replace_once(
        generator.function(source, "CandidateSignal"),
        "CandidateSignal", "R8ParentSignal")
    assert generator.function(text, "OnTick") == generator.function(source, "OnTick")
    expected = generator.function(source, "OriginalOnTick").replace(
        "TP=%.2f (2.0R)", "TP=%.2f (ConfiguredR)")
    assert generator.function(text, "OriginalOnTick") == expected
    for economic_anchor in (
        "ManageOpenPositions();", "IsCircuitBreakerActive()", "CheckMargin(",
        "trade.Buy(InpLotSize", "trade.Sell(InpLotSize", "double slDistance = MathMax("):
        assert economic_anchor in generator.function(text, "OriginalOnTick")
    assert text.count("TP=%.2f (ConfiguredR)") == 2
    assert '"R8 RESEARCH HEALTH Account=' in text


def test_both_off_and_mode0_bypass_feature_reads():
    text = generated()
    wrapper = generator.function(text, "CandidateSignal")
    assert wrapper.index("if(InpExperimentMode==0)return parentSide;") < wrapper.index("R8ReadEfficiency(")
    off = wrapper.index("if(!InpRequireEfficiency && !InpRequireNearMean)")
    assert off < wrapper.index("R8ReadEfficiency(") and off < wrapper.index("R8ReadExtension(")
    assert "return parentSide;" in wrapper[off:]
    assert "R8ParentSignal(atr)" in wrapper


def test_efficiency_definition_allows_irregular_observed_intervals_and_reports_gaps():
    text = generated()
    kernel = generator.function(text, "R8CalculateEfficiency")
    assert "ArraySize(closes)!=11" in kernel
    assert "times[i]<=times[i+1]" in kernel
    assert "closes[i]<=0.0" in kernel
    assert "times[i]-times[i+1]!=60)gapSpanning=true" in kernel
    assert "return MathIsValidNumber(efficiency) && efficiency>=0.0 && efficiency<=1.0" in kernel
    assert "CopyRates(_Symbol,PERIOD_M1,1,11,r)!=11" in generator.function(text, "R8ReadEfficiency")
    assert "ER_GAP_ALLOWED_AND_MARKED" in text
    assert "R8EfficiencyPass(const double efficiency)" in text and "efficiency>=0.30" in text


def test_extension_is_closed_shift_one_symmetric_and_inclusive():
    text = generated()
    calc = generator.function(text, "R8CalculateExtension")
    read = generator.function(text, "R8ReadExtension")
    assert "MathAbs(closedPrice-closedEMA9)/closedATR" in calc
    assert "closedATR<=0.0" in calc
    assert "CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1" in read
    assert "ReadClosed(entryFast,1,ema9)" in read
    assert "extension<=1.0" in generator.function(text, "R8ExtensionPass")
    assert "EXTENSION_ONE_INCLUSIVE" in text and "EXTENSION_MIRROR_ONE" in text


def test_feature_diagnostics_have_exact_header_row_arity_and_blank_unavailable_values():
    text = generated()
    row = _filewrite_args(text, "FileWrite(r8FeatureFile,", 0)
    header = _filewrite_args(text, "FileWrite(r8FeatureFile,", 1)
    assert len(header) == len(row) == 15  # handle + 14 columns
    assert header[0] == "r8FeatureFile"
    assert [x.strip('"') for x in header[1:]] == [
        "decision_bar", "signal_bar", "tick_msc", "require_efficiency", "require_near_mean",
        "efficiency_available", "efficiency", "efficiency_gap_spanning",
        "extension_available", "extension_atr", "parent_side", "final_side",
        "parent_reason", "reason"]
    writer = generator.function(text, "R8WriteFeatureEvent")
    assert "datetime decisionBar=iTime(_Symbol,PERIOD_M1,0);" in writer
    assert "datetime signalBar=iTime(_Symbol,PERIOD_M1,1);" in writer
    assert "decisionBar<=0 || signalBar<=0 || signalBar>=decisionBar" in writer
    assert 'efficiencyAvailable ? DoubleToString(efficiency,10) : ""' in writer
    assert 'efficiencyAvailable ? (gapSpanning ? "true" : "false") : ""' in writer
    assert 'extensionAvailable ? DoubleToString(extension,10) : ""' in writer
    assert "R8WriteFeatureEvent(parentSide" in generator.function(text, "CandidateSignal")


def test_fixture_contract_is_actual_named_mql_assertions_with_exact_count():
    text = generated()
    fixtures = generator.function(text, "RunR8FixtureTests")
    assert len(re.findall(r"ok=R8Assert\(", fixtures)) == generator.FIXTURE_COUNT
    assert f"if(r8FixtureChecks!={generator.FIXTURE_COUNT})ok=false;" in fixtures
    assert 'Print("R8_NATIVE_FIXTURE_FAIL case="' in generator.function(text, "R8Assert")
    assert 'Print("R8_NATIVE_FIXTURES_PASS checks="' in fixtures
    for case in ("ER_TREND_ONE", "ER_CHOP_ZERO", "ER_FLAT_UNAVAILABLE",
                 "ER_SHORT_UNAVAILABLE", "ER_TIME_ORDER_REJECT", "ER_GAP_ALLOWED_AND_MARKED",
                 "ER_EXACT_POINT_THREE", "ER_THRESHOLD_INCLUSIVE", "EXTENSION_ONE_INCLUSIVE",
                 "EXTENSION_MIRROR_ONE", "BOTH_FACTORS_BUY_PASS", "BOTH_FACTORS_SELL_MIRROR",
                 "FACTORS_OFF_PRESERVE_PARENT"):
        assert case in fixtures
    init = generator.function(text, "OnInit")
    assert init.index("RunR8FixtureTests()") < init.index("BenchInit()")
    assert init.index("RunR8FixtureTests()") < init.index("trade.SetExpertMagicNumber")


def test_oninit_only_changes_validator_fixture_wiring():
    source = PARENT.read_text(encoding="utf-8-sig")
    text = generated()
    expected = generator.replace_once(generator.function(source, "OnInit"),
        "if(!ValidateV25Inputs() || !BenchInit()) return INIT_PARAMETERS_INCORRECT;",
        "if(!ValidateR8Inputs() || !RunR8FixtureTests()) return INIT_PARAMETERS_INCORRECT;\n"
        "   if(!BenchInit()) return INIT_PARAMETERS_INCORRECT;")
    assert generator.function(text, "OnInit") == expected


def test_ontester_export_history_bound_only_changes_export_selection():
    source = PARENT.read_text(encoding="utf-8-sig")
    text = generated()
    expected = generator.replace_once(generator.function(source, "OnTester"),
        "bool historyOK=HistorySelect(0,TimeCurrent());",
        "bool historyOK=HistorySelect(0,D'3000.12.31 23:59:59');")
    assert generator.function(text, "OnTester") == expected
    assert "HistorySelect(0,TimeCurrent())" not in generator.function(text, "OnTester")
    # Online safety/breaker history windows remain unchanged.
    assert "HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent())" in text


def test_math_properties_and_inclusive_boundaries():
    trend = [100 + i for i in range(11)]
    chop = [100 if i % 2 == 0 else 101 for i in range(11)]
    boundary = [103.0, 96.5, 100.0] + [100.0] * 8
    for data in (trend, list(reversed(trend))):
        assert _er(data) == pytest.approx(1.0)
        assert _er([x + 1000 for x in data]) == pytest.approx(_er(data))
        assert _er([x * 3 for x in data]) == pytest.approx(_er(data))
    assert _er(chop) == pytest.approx(0.0)
    assert _er(boundary) == pytest.approx(0.30)
    assert abs(0.30 - 0.0) / 1.0 <= 1.0
    assert abs(2.01 - 1.0) / 1.0 > 1.0
