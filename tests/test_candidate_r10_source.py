from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "research" / "ResearchControl_R1_R8.mq5"
R10 = ROOT / "research" / "ResearchCandidate_R10.mq5"
CONTROL_SHA256 = "961756d0742caf124fe5eadf1abd7d0ab62082fc92b831daf0b16f9727e9140b"
R10_CAP = "R10_CASH_RISK_FRACTION=0.025"


def _function(source: str, name: str) -> str:
    match = re.search(rf"\b(?:void|bool|int|double|ENUM_R10_CASH_RISK_RESULT)\s+{name}\s*\([^)]*\)\s*\{{", source)
    assert match, f"missing function {name}"
    start = match.start()
    brace = source.index("{", match.start())
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError(f"unterminated function {name}")


def _argument_count(call: str) -> int:
    inside = call[call.index("(") + 1 : call.rindex(")")]
    depth = 0
    quoted = False
    escaped = False
    commas = 0
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


def test_r8_control_is_hash_pinned_and_untouched():
    data = CONTROL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == CONTROL_SHA256


def test_r10_is_tester_only_fixed_cap_mode1_and_production_disabled():
    s = R10.read_text(encoding="utf-8")
    assert '#property version   "24.92"' in s
    assert "tester-only. Not a V25 release." in s
    assert "input bool InpEnableCashRiskVeto=false" in s
    assert R10_CAP in s
    assert "InpEnableCashRiskVeto && (InpExperimentMode!=1 || !InpEnableHardSL || InpLotSize!=0.01)" in s
    assert "if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;" in s
    assert "cash_risk_cap" in s
    assert "bool ValidateR10Inputs()" in s
    assert "InpUseGridIndices" in s


def test_r10_accepts_only_frozen_control_and_treatment_contracts():
    s = R10.read_text(encoding="utf-8")
    validate = _function(s, "ValidateR10Inputs")
    assert "InpExperimentMode==0" in validate
    assert "InpEntryStrength==0 && InpStopLossATRMul==1.5 && EffectiveTPR()==2.0" in validate
    assert "&& !InpEnableCashRiskVeto" in validate
    assert "InpExperimentMode==1" in validate
    assert "InpEntryStrength==2 && InpStopLossATRMul==2.0 && EffectiveTPR()==3.0" in validate
    assert "InpMaxHoldBars!=60" in validate
    for frozen_setting in (
        "MQL_OPTIMIZATION", "InpUseGridIndices", "InpTPGridIndex!=2",
        "InpEnableSessionGuard", "InpEnableSpreadGuard", "!InpEnableMarginGuard", "!InpEnableHardSL",
        "InpStartHour!=11", "InpEndHour!=16", "InpMaxSpreadPts!=25", "InpMinSLPoints!=150",
        "InpLotSize!=0.01", "InpMagicNumber!=992300", "InpTargetAccount!=0",
        "!InpEnableCircuitBreaker", "InpMaxConsecutiveLosses!=4", "InpCooldownMinutes!=90",
        "InpDonchianPeriod!=20", "InpATRPeriod!=14",
    ):
        assert frozen_setting in validate
    assert "return false;" in validate


def test_control_execution_body_changes_only_by_two_post_margin_veto_hooks():
    control = CONTROL.read_text(encoding="utf-8")
    r10 = R10.read_text(encoding="utf-8")
    original = _function(control, "OriginalOnTick")
    candidate = _function(r10, "OriginalOnTick")
    hook = re.compile(
        r'\n      if\(InpEnableCashRiskVeto\)\n      \{\n'
        r'         ENUM_R10_CASH_RISK_RESULT riskResult=R10EvaluateCashRisk\(signal,(?:ask|bid),sl\);\n'
        r'         if\(riskResult==R10_CASH_RISK_CALC_FAILED\) \{ benchGate="cash_risk_calc_failed"; return; \}\n'
        r'         if\(riskResult==R10_CASH_RISK_VETO\) \{ benchGate="cash_risk_veto"; return; \}\n'
        r'      \}\n'
    )
    stripped, n = hook.subn("\n", candidate)
    assert n == 2
    assert stripped == original
    for order_type in ("BUY", "SELL"):
        margin = candidate.index(f'CheckMargin(ORDER_TYPE_{order_type}')
        risk = candidate.index("R10EvaluateCashRisk", margin)
        send = candidate.index(f"trade.{order_type.title()}(", risk)
        assert margin < risk < send


def test_cash_estimate_uses_executable_side_and_original_normalized_sl():
    s = R10.read_text(encoding="utf-8")
    eval_body = _function(s, "R10EvaluateCashRisk")
    assert "SymbolInfoTick" not in eval_body
    assert "signal!=1 && signal!=-1" in eval_body
    assert "intendedPrice<=0.0" in eval_body
    assert "ENUM_ORDER_TYPE orderType=(signal==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);" in eval_body
    assert "R10SLValid(signal,intendedPrice,sl)" in eval_body
    assert "riskQuote=intendedPrice;riskSL=sl;" in eval_body
    assert "OrderCalcProfit(orderType,_Symbol,InpLotSize,intendedPrice,sl,estimatedProfit)" in eval_body
    assert "R10_CASH_RISK_FRACTION" in eval_body
    assert "if(!MathIsValidNumber(riskEquity) || riskEquity<=0.0)" in eval_body
    quote = _function(s, "R10ExecutableQuote")
    assert "price=ask;orderType=ORDER_TYPE_BUY" in quote
    assert "price=bid;orderType=ORDER_TYPE_SELL" in quote
    assert "sl<price" in _function(s, "R10SLValid")
    assert "sl>price" in _function(s, "R10SLValid")


def test_veto_fails_closed_and_has_distinct_raw_gates():
    s = R10.read_text(encoding="utf-8")
    assert 'benchGate="cash_risk_calc_failed"' in s
    assert 'benchGate="cash_risk_veto"' in s
    assert "return R10_CASH_RISK_CALC_FAILED;" in _function(s, "R10EvaluateCashRisk")
    assert "riskResult==R10_CASH_RISK_VETO" in _function(s, "OriginalOnTick")


def test_diagnostic_csv_schema_is_fixed_and_records_only_pretrade_context():
    s = R10.read_text(encoding="utf-8")
    header = re.search(r'FileWrite\(diagnosticFile,"bar"[^;]+;', s).group(0)
    row = re.search(r'FileWrite\(diagnosticFile,TimeToString\(bar[^;]+;', s).group(0)
    fields = re.findall(r'"([a-z_]+)"', header)
    assert fields[-8:] == [
        "cash_risk_enabled", "cash_risk_evaluated", "cash_risk_quote", "cash_risk_sl",
        "cash_risk_equity", "cash_risk_estimate", "cash_risk_cap", "cash_risk_calc_valid",
    ]
    row_fields = _argument_count(row)
    assert row_fields == len(fields) + 1  # FileWrite handle plus one value per header column.
    assert "tick.time_msc" in row
    assert 'riskEvaluated?DoubleToString(riskQuote,_Digits):""' in row
    assert 'riskEvaluated?DoubleToString(riskSL,_Digits):""' in row
    assert 'riskEvaluated?DoubleToString(riskEquity,2):""' in row
    assert 'riskCalcValid?DoubleToString(riskCash,4):""' in row
    assert "riskCalcValid);" in row
    assert "riskEvaluated=false;riskCalcValid=false;" in s


def test_native_fixtures_cover_equality_over_invalid_sides_and_real_api_smoke():
    s = R10.read_text(encoding="utf-8")
    fixtures = _function(s, "RunR10DeterministicFixtures")
    for case in (
        "equality_at_cap", "over_cap", "invalid_calc_or_equity", "nonfinite_inputs",
        "dynamic_equity_cap", "buy_uses_ask", "sell_uses_bid", "invalid_side_or_crossed_quote",
        "valid_sl_side", "invalid_sl_side",
    ):
        assert f'R10_NATIVE_FIXTURE_FAIL {case}' in fixtures
    assert "R10ClassifyCashRisk(-1.75,70.0" in fixtures
    assert "R10ClassifyCashRisk(-1.7501,70.0" in fixtures
    smoke = _function(s, "R10PlatformOrderCalcSmoke")
    assert "OrderCalcProfit(ORDER_TYPE_BUY" in smoke
    assert "OrderCalcProfit(ORDER_TYPE_SELL" in smoke
    assert 'R10_NATIVE_PLATFORM_PROFIT_PASS checks=2' in s
    assert 'R10_NATIVE_PLATFORM_PROFIT_FAIL checks=2' in s
    assert 'R10_NATIVE_FIXTURES_PASS checks=%d preset=%d' in s
    assert "if(checks!=10 || !all)return false;" in fixtures
    tick = _function(s, "OnTick")
    assert "R10PlatformOrderCalcSmoke(tick.bid,tick.ask)" in tick
    assert tick.index("R10PlatformOrderCalcSmoke") < tick.index("ObserveEquity()")
    assert "trade.Buy" not in smoke and "trade.Sell" not in smoke


def test_on_tester_spec_adds_only_four_r10_reporting_rows():
    control = CONTROL.read_text(encoding="utf-8")
    r10 = R10.read_text(encoding="utf-8")
    parent_tester = _function(control, "OnTester")
    candidate_tester = _function(r10, "OnTester")
    rows = (
        '   FileWrite(f,"point",SymbolInfoDouble(_Symbol,SYMBOL_POINT));\n',
        '   FileWrite(f,"digits",SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));\n',
        '   FileWrite(f,"cash_risk_fraction",R10_CASH_RISK_FRACTION);\n',
        '   FileWrite(f,"cash_risk_enabled",InpEnableCashRiskVeto);\n',
    )
    for row in rows:
        assert row in candidate_tester
        candidate_tester = candidate_tester.replace(row, "", 1)
    assert candidate_tester == parent_tester
    full = _function(r10, "OnTester")
    tick_size = full.index('FileWrite(f,"tick_size"')
    tick_value = full.index('FileWrite(f,"tick_value_profit"')
    row_positions = [full.index(row) for row in rows]
    assert tick_size < min(row_positions) < max(row_positions) < tick_value
