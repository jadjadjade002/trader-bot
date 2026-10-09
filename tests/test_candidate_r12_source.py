from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "research" / "ResearchControl_R1_R8.mq5"
R10 = ROOT / "research" / "ResearchCandidate_R10.mq5"
R12 = ROOT / "research" / "ResearchCandidate_R12.mq5"
CONTROL_SHA256 = "961756d0742caf124fe5eadf1abd7d0ab62082fc92b831daf0b16f9727e9140b"
R10_SHA256 = "8b1bc2b768326fcd305672bad9b6ebb2879dff94170c7b0f8315bf29a02c5e68"


def _function(source: str, name: str) -> str:
    match = re.search(
        rf"\b(?:void|bool|int|double|string|ENUM_R12_CASH_RISK_RESULT)\s+{name}\s*\([^)]*\)\s*\{{",
        source,
    )
    assert match, f"missing function {name}"
    brace = source.index("{", match.start())
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : i + 1]
    raise AssertionError(f"unterminated function {name}")


def _argument_count(call: str) -> int:
    inside = call[call.index("(") + 1 : call.rindex(")")]
    depth = commas = 0
    quoted = escaped = False
    for char in inside:
        if quoted:
            if char == '"' and not escaped:
                quoted = False
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            commas += 1
    return commas + 1


def _header(source: str, filevar: str, first: str) -> list[str]:
    call = re.search(rf'FileWrite\({filevar},"{first}"[^;]+;', source)
    assert call
    return re.findall(r'"([a-z0-9_]+)"', call.group(0))


def test_parent_and_r10_clone_sources_are_hash_pinned():
    assert hashlib.sha256(CONTROL.read_bytes()).hexdigest() == CONTROL_SHA256
    assert hashlib.sha256(R10.read_bytes()).hexdigest() == R10_SHA256


def test_r12_is_tester_only_and_accepts_only_frozen_off_on_contracts():
    s = R12.read_text(encoding="utf-8")
    assert '#property version   "24.94"' in s
    assert "tester-only. Not a V25 release." in s
    assert "input bool InpStructuralRetest=false" in s
    assert "if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;" in s
    validate = _function(s, "ValidateR12Inputs")
    for frozen in (
        "InpExperimentMode==0", "InpEntryStrength==0 && InpStopLossATRMul==1.5 && EffectiveTPR()==2.0",
        "&& !InpStructuralRetest", "InpExperimentMode==1",
        "InpEntryStrength==2 && InpStopLossATRMul==2.0 && EffectiveTPR()==3.0",
        "InpMaxHoldBars!=60", "InpUseGridIndices", "InpTPGridIndex!=2",
        "InpEnableSessionGuard", "InpEnableSpreadGuard", "!InpEnableMarginGuard", "!InpEnableHardSL",
        "InpStartHour!=11", "InpEndHour!=16", "InpMaxSpreadPts!=25", "InpMinSLPoints!=150",
        "InpLotSize!=0.01", "InpMagicNumber!=992300", "InpTargetAccount!=0",
        "!InpEnableCircuitBreaker", "InpMaxConsecutiveLosses!=4", "InpCooldownMinutes!=90",
        "InpDonchianPeriod!=20", "InpATRPeriod!=14",
    ):
        assert frozen in validate
    assert "InpStructuralRetest && (InpExperimentMode!=1 || !InpEnableHardSL || InpLotSize!=0.01)" in s
    assert "InpEnableCashRiskVeto" not in s and "R10_" not in s and "R10" not in s


def test_parent_economic_helpers_remain_identical_to_pinned_r10_clone():
    r10 = R10.read_text(encoding="utf-8")
    r12 = R12.read_text(encoding="utf-8")
    for name in ("ClosedTrendDirection", "ProposedSignal", "ManageOpenPositions", "HasOpenPosition",
                 "CheckMargin", "IsCircuitBreakerActive"):
        a = _function(r10, name)
        b = _function(r12, name)
        assert a == b, name


def test_candidate_signal_and_original_execution_are_exact_when_policy_off():
    r10 = R10.read_text(encoding="utf-8")
    r12 = R12.read_text(encoding="utf-8")
    c10 = _function(r10, "CandidateSignal")
    c12 = _function(r12, "CandidateSignal")
    c12 = c12.replace("   if(InpExperimentMode==1 && InpStructuralRetest)return R12CandidateSignal(atr);\n", "")
    assert c12 == c10

    o10 = _function(r10, "OriginalOnTick")
    o12 = _function(r12, "OriginalOnTick")
    o12 = o12.replace(
        '   if(signal == 0)\n      {\n         benchGate=(InpStructuralRetest && InpExperimentMode==1 && StringFind(candidateReason,"structural_")==0)\n            ? candidateReason : "no_signal";\n         V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return;\n      }\n',
        '   if(signal == 0)\n      { benchGate="no_signal"; V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }\n',
    )
    o12 = o12.replace('   if(InpExperimentMode==1 && InpStructuralRetest)\n   {R12ExecuteStructural(signal);return;}\n', "")
    o12 = o12.replace("\n\n\n   // Liquidity Fade Mode", "\n\n   // Liquidity Fade Mode")
    veto_hook = re.compile(
        r'\n      if\(InpEnableCashRiskVeto\)\n      \{\n'
        r'         ENUM_R10_CASH_RISK_RESULT riskResult=R10EvaluateCashRisk\(signal,(?:ask|bid),sl\);\n'
        r'         if\(riskResult==R10_CASH_RISK_CALC_FAILED\) \{ benchGate="cash_risk_calc_failed"; return; \}\n'
        r'         if\(riskResult==R10_CASH_RISK_VETO\) \{ benchGate="cash_risk_veto"; return; \}\n'
        r'      \}\n'
    )
    o10, removed = veto_hook.subn("\n", o10)
    assert removed == 2
    o12 = "\n".join(line for line in o12.splitlines() if line.strip())
    o10 = "\n".join(line for line in o10.splitlines() if line.strip())
    assert o12 == o10


def test_structural_signal_uses_only_contiguous_closed_bid_bars_and_exact_mirrors():
    s = R12.read_text(encoding="utf-8")
    cand = _function(s, "R12CandidateSignal")
    assert "SYMBOL_CHART_MODE" in cand and "R12BidChartSupported(r12ChartMode)" in cand
    assert "CopyRates(_Symbol,PERIOD_M1,1,3,bars)" in cand
    assert "!=3)return 0;" in cand
    assert "ReadClosed(atrHandle,2,atr2)" in cand
    assert "ReadClosed(entryFast,1,ema1)" in cand and "ReadClosed(entryFast,2,ema2)" in cand
    assert "R12BarsContinuous(active,bars[0].time,bars[1].time,bars[2].time)" in cand
    assert "CopyRates(_Symbol,PERIOD_M1,0," not in cand
    setup = _function(s, "R12SetupValid")
    retest = _function(s, "R12RetestValid")
    assert "bodyATR<0.30" in setup and "closeLocation<0.80" in setup and "rangeATR>2.0" in setup
    assert "close>level+0.10*atr" in setup and "close<level-0.10*atr" in setup
    assert "low<=level && close>level && close>ema && close>open" in retest
    assert "high>=level && close<level && close<ema && close<open" in retest
    assert 'candidateReason="structural_setup_absent"' in cand
    assert 'candidateReason="structural_retest_absent"' in cand


def test_structural_geometry_matches_frozen_stop_tp_and_broker_distance_formulas():
    s = R12.read_text(encoding="utf-8")
    geometry = _function(s, "R12BuildGeometry")
    assert "MathFloor((s1Low-tick)/tick)*tick" in geometry
    assert "MathCeil((s1High+(ask-bid)+tick)/tick)*tick" in geometry
    assert "MathCeil((ask+3.0*risk)/tick)*tick" in geometry
    assert "MathFloor((bid-3.0*risk)/tick)*tick" in geometry
    assert "stopDistance=side==1 ? bid-sl : sl-ask" in geometry
    assert "targetDistance=side==1 ? tp-bid : ask-tp" in geometry
    broker = _function(s, "R12BrokerDistancesPass")
    assert "MathMax((double)stops,(double)freeze)*point+tick" in broker
    assert "stopDistance>=required && targetDistance>=required" in broker
    assert "stopDistance<required" not in broker
    fixtures = _function(s, "RunR12DeterministicFixtures")
    assert "MathAbs(tp-96.0)<1e-9" in fixtures
    assert "MathAbs(targetDist-4.2)<1e-9" in fixtures


def test_rejected_valid_retest_still_exports_observed_closed_bar_metrics():
    s = R12.read_text(encoding="utf-8")
    cand = _function(s, "R12CandidateSignal")
    invoke = cand.index("bool retestValid=R12RetestValid(")
    assign = cand.index("diagnosticBody=r12RetestBodyATR;diagnosticCloseLocation=r12RetestCloseLocation;")
    reject = cand.index("if(!retestValid)return 0;", invoke)
    assert invoke < assign < reject
    assert "r12RetestMetricsValid=R12ValidBar(r12S1Open,r12S1High,r12S1Low,r12S1Close)" in cand


def test_same_decision_quote_used_for_geometry_margin_risk_and_order():
    s = R12.read_text(encoding="utf-8")
    execute = _function(s, "R12ExecuteStructural")
    assert "SymbolInfoTick(_Symbol,q)" in execute
    assert "R12BuildGeometry(signal,q.bid,q.ask" in execute
    assert "double entry=signal==1 ? q.ask : q.bid" in execute
    assert "R12EvaluateCashRisk(signal,entry,r12StructuralSL)" in execute
    assert "CheckMargin(orderType,InpLotSize,entry)" in execute
    assert "trade.Buy(InpLotSize,_Symbol,q.ask,r12StructuralSL,r12StructuralTP" in execute
    assert "trade.Sell(InpLotSize,_Symbol,q.bid,r12StructuralSL,r12StructuralTP" in execute
    risk = _function(s, "R12EvaluateCashRisk")
    assert "SymbolInfoTick" not in risk
    assert "OrderCalcProfit(orderType,_Symbol,InpLotSize,intendedPrice,sl,estimatedProfit)" in risk
    assert "riskEvaluated=true;r12RiskCallMade=true;" in risk
    assert "R12_CASH_RISK_FRACTION=0.025" in s
    for gate in (
        "structural_quote_unavailable", "structural_cost_or_chase", "structural_geometry_invalid",
        "structural_broker_distance", "structural_cash_risk_calc_failed", "structural_cash_risk_veto",
    ):
        assert f'benchGate="{gate}"' in execute


def test_diagnostic_schema_exactly_appends_43_auditable_fields_and_raw_stays_frozen():
    s = R12.read_text(encoding="utf-8")
    base = ["bar", "tick_msc", "mode", "entry_strength", "signal", "trend", "reason", "body_atr",
            "close_location", "entry_level", "execution_gate", "held_before", "order_attempt"]
    extra = [
        "structural_enabled", "features_evaluated", "bid_chart_mode", "signal_bar_s1", "setup_bar_s2",
        "reference_bar_s3", "signal_bid", "signal_ask", "decision_bid", "decision_ask", "s1_open",
        "s1_high", "s1_low", "s1_close", "s2_open", "s2_high", "s2_low", "s2_close", "s3_high",
        "s3_low", "atr_s1", "atr_s2", "ema9_s1", "ema9_s2", "setup_body_atr",
        "setup_close_location", "setup_range_atr", "retest_body_atr", "retest_close_location",
        "structural_sl", "structural_tp", "point", "tick_size", "stops_level", "freeze_level",
        "stop_distance_close_side", "target_distance_close_side", "equity", "planned_risk",
        "cash_risk_cap", "risk_calc_valid", "geometry_evaluated", "risk_evaluated",
    ]
    cols = _header(s, "diagnosticFile", "bar")
    assert cols == base + extra
    assert len(cols) == 56
    assert _argument_count(re.search(r"FileWrite\(diagnosticFile,\"bar\"[^;]+;", s).group(0)) == 57
    assert _header(s, "rawFile", "bar") == [
        "bar", "tick_msc", "original", "closeback", "dc_low", "dc_high", "atr", "break_close",
        "retest_open", "retest_close", "retest_high", "retest_low", "bid", "ask", "held_before",
        "cooldown_before", "gate", "order_attempt", "retcode", "order_ticket", "deal_ticket",
    ]
    writer = _function(s, "R12WriteDiagnostic")
    assert "R12Bool(InpStructuralRetest)" in writer and "R12Bool(r12FeaturesEvaluated)" in writer
    assert "R12Time(r12FeaturesEvaluated,r12SignalBar)" in writer
    assert 'riskEvaluated ? R12Bool(riskCalcValid) : ""' in writer
    assert "R12Num(r12GeometryEvaluated,r12StructuralSL)" in writer
    assert "DoubleToString(value,16)" in _function(s, "R12Num")


def test_specs_pin_structural_policy_and_actual_chart_mode():
    s = R12.read_text(encoding="utf-8")
    tester = _function(s, "OnTester")
    assert 'FileWrite(f,"cash_risk_fraction",R12_CASH_RISK_FRACTION);' in tester
    assert 'FileWrite(f,"structural_retest_enabled",InpStructuralRetest);' in tester
    assert 'FileWrite(f,"chart_mode_valid",chartModeOK);' in tester
    assert 'FileWrite(f,"chart_mode",chartModeOK?chartMode:-1);' in tester
    assert 'FileWrite(f,"stops_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL));' in tester
    assert 'FileWrite(f,"freeze_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL));' in tester


def test_native_fixtures_pin_24_named_cases_and_real_platform_smoke_marker():
    s = R12.read_text(encoding="utf-8")
    fixtures = _function(s, "RunR12DeterministicFixtures")
    cases = (
        "equality_at_cap", "over_cap", "invalid_calc_or_equity", "nonfinite_inputs", "dynamic_equity_cap",
        "buy_uses_ask", "sell_uses_bid", "invalid_side_or_crossed_quote", "valid_sl_side", "invalid_sl_side",
        "bid_chart_only", "contiguous_s1_s2_s3", "gap_rejected", "buy_setup", "sell_setup", "buy_retest",
        "sell_retest", "buy_retest_not_reclaimed", "sell_retest_not_reclaimed", "buy_structural_geometry",
        "sell_structural_geometry_spread_adjusted", "broker_boundary_equality_pass",
        "broker_boundary_below_reject", "invalid_broker_levels",
    )
    for case in cases:
        assert f"R12_NATIVE_FIXTURE_FAIL {case}" in fixtures
    assert "if(checks!=24 || !all)return false;" in fixtures
    assert 'R12_NATIVE_FIXTURES_PASS checks=%d preset=%d' in fixtures
    assert "R12_NATIVE_PLATFORM_PROFIT_PASS checks=2" in s
    assert "R12_NATIVE_PLATFORM_PROFIT_FAIL checks=2" in s
    assert "r12PlatformSmokeChecked=true" in _function(s, "OnTick")
    assert "R12BidChartSupported(2)" in fixtures
    assert "SYMBOL_CHART_MODE_ASK" not in s
