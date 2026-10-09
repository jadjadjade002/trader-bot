from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "research" / "ResearchControl_R1_R8.mq5"
R11 = ROOT / "research" / "ResearchCandidate_R11.mq5"
CONTROL_SHA256 = "961756d0742caf124fe5eadf1abd7d0ab62082fc92b831daf0b16f9727e9140b"


def _function(source: str, name: str) -> str:
    match = re.search(
        rf"\b(?:void|bool|int|double|ENUM_R11_DELAY_ACTION)\s+{name}\s*\([^)]*\)\s*\{{",
        source,
    )
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


def test_frozen_parent_hash_unchanged():
    assert hashlib.sha256(CONTROL.read_bytes()).hexdigest() == CONTROL_SHA256


def test_tester_only_strict_inputs_and_no_r10_risk_code():
    s = R11.read_text(encoding="utf-8")
    assert '#property version   "24.93"' in s
    assert 'one-bar persistence entry research clone, tester-only. Not a V25 release.' in s
    assert "input bool InpDelayOneBar=false" in s
    assert "#property" in s and "if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;" in s
    assert "InpEnableCashRiskVeto" not in s and "R10_CASH_RISK" not in s
    validate = _function(s, "ValidateR11Inputs")
    for frozen in (
        "MQL_OPTIMIZATION", "InpMaxHoldBars!=60", "InpUseGridIndices", "InpTPGridIndex!=2",
        "InpEnableSessionGuard", "InpEnableSpreadGuard", "!InpEnableMarginGuard", "!InpEnableHardSL",
        "InpStartHour!=11", "InpEndHour!=16", "InpMaxSpreadPts!=25", "InpMinSLPoints!=150",
        "InpLotSize!=0.01", "InpMagicNumber!=992300", "InpTargetAccount!=0",
        "!InpEnableCircuitBreaker", "InpMaxConsecutiveLosses!=4", "InpCooldownMinutes!=90",
        "InpDonchianPeriod!=20", "InpATRPeriod!=14",
    ):
        assert frozen in validate
    assert "InpEntryStrength==0 && InpStopLossATRMul==1.5 && EffectiveTPR()==2.0 && !InpDelayOneBar" in validate
    assert "InpEntryStrength==2 && InpStopLossATRMul==2.0 && EffectiveTPR()==3.0" in validate


def test_offline_control_economic_functions_are_exact_parent():
    control = CONTROL.read_text(encoding="utf-8")
    candidate = R11.read_text(encoding="utf-8")
    ontester = _function(candidate, "OnTester")
    for row in (
        '   FileWrite(f,"point",SymbolInfoDouble(_Symbol,SYMBOL_POINT));\n',
        '   FileWrite(f,"digits",SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));\n',
        '   FileWrite(f,"delay_enabled",InpDelayOneBar);\n',
        '   FileWrite(f,"delay_seconds",60);\n',
    ):
        assert row in ontester
        ontester = ontester.replace(row, "", 1)
    assert ontester == _function(control, "OnTester")

    parent = _function(control, "OriginalOnTick")
    r11 = _function(candidate, "OriginalOnTick")
    reporting_hooks = (
        "      if(r11OverrideConsumed){r11ReportDecisionBid=symInfo.Bid();r11ReportDecisionAsk=ask;r11ReportDecisionATR=atr;}\n",
        "      if(r11OverrideConsumed){r11ReportDecisionBid=bid;r11ReportDecisionAsk=symInfo.Ask();r11ReportDecisionATR=atr;}\n",
    )
    for hook in reporting_hooks:
        assert hook in r11
        r11 = r11.replace(hook, "", 1)
    assert r11 == parent


def test_candidate_signal_off_path_is_exact_parent_after_delay_hooks_removed():
    control = CONTROL.read_text(encoding="utf-8")
    candidate = R11.read_text(encoding="utf-8")
    parent = _function(control, "CandidateSignal")
    r11 = _function(candidate, "CandidateSignal")
    r11 = r11.replace("   candidateDecisionBid=0;candidateDecisionAsk=0;\n", "", 1)
    override = (
        "   if(InpExperimentMode==1 && InpDelayOneBar)\n"
        "   {\n"
        "      if(r11SuppressCandidate){candidateReason=r11SuppressReason;return 0;}\n"
        "      if(r11OverrideSignal!=0)\n"
        "      {\n"
        "         candidateSide=r11OverrideSignal;candidateTrend=r11ConfirmTrend;\n"
        "         candidateReason=\"delay_confirmed\";r11OverrideConsumed=true;return candidateSide;\n"
        "      }\n"
        "   }\n"
    )
    assert override in r11
    r11 = r11.replace(override, "", 1)
    quote_assignment = "   candidateDecisionBid=q.bid;candidateDecisionAsk=q.ask;\n"
    assert quote_assignment in r11
    r11 = r11.replace(quote_assignment, "", 1)
    arm = (
        "   if(candidateSide!=0 && InpExperimentMode==1 && InpDelayOneBar)\n"
        "   {\n"
        "      r11ArmSignalCandidate=candidateSide;r11ArmSignalBar=r[0].time;\n"
        "      r11ArmBid=candidateDecisionBid;r11ArmAsk=candidateDecisionAsk;r11ArmATR=atr;\n"
        "      candidateReason=\"delay_armed\";return 0;\n"
        "   }\n"
    )
    assert arm in r11
    r11 = r11.replace(arm, "", 1)
    assert r11 == parent


def test_signal_context_risk_and_exit_helpers_remain_parent_exact():
    control = CONTROL.read_text(encoding="utf-8")
    candidate = R11.read_text(encoding="utf-8")
    for name in (
        "ClosedTrendDirection", "ProposedSignal", "ManageOpenPositions", "HasOpenPosition",
        "CheckMargin", "IsCircuitBreakerActive", "EffectiveTPR",
    ):
        assert _function(candidate, name) == _function(control, name), name


def test_delay_requires_exact_single_closed_bar_and_never_active_bar():
    s = R11.read_text(encoding="utf-8")
    prepare = _function(s, "R11PrepareFreshBar")
    decide = _function(s, "R11DecideDelay")
    assert "CopyRates(_Symbol,PERIOD_M1,1,1,closed)" in prepare
    assert "ReadClosed(entryFast,1,ema9)" in prepare
    assert "ClosedTrendDirection()" in prepare
    assert "CopyRates(_Symbol,PERIOD_M1,0," not in prepare
    assert "dueBar!=pendingSignalBar+2*PeriodSeconds(PERIOD_M1)" in decide
    assert "closedBar==currentBar-PeriodSeconds(PERIOD_M1)" in decide
    assert "candidateSignalBar" not in decide
    assert "closedBar!=pendingSignalBar+PeriodSeconds(PERIOD_M1)" in decide
    assert "currentBar>dueBar" in decide and "R11_DELAY_EXPIRE_SKIPPED" in decide
    assert "trend!=pendingSide" in decide
    assert "pendingSide==1 && close<=ema9" in decide
    assert "pendingSide==-1 && close>=ema9" in decide


def test_pending_state_consumed_at_due_gates_and_no_same_callback_resignal():
    s = R11.read_text(encoding="utf-8")
    tick = _function(s, "OnTick")
    signal = _function(s, "CandidateSignal")
    assert "R11PrepareFreshBar(bar,held)" in tick
    assert tick.index("R11PrepareFreshBar(bar,held)") < tick.index("OriginalOnTick()")
    assert tick.index("OriginalOnTick()") < tick.index("R11AfterOriginal()")
    assert "if(r11SuppressCandidate){candidateReason=r11SuppressReason;return 0;}" in signal
    assert "R11ConsumePending(\"expired_skipped_bar\")" in _function(s, "R11PrepareFreshBar")
    after = _function(s, "R11AfterOriginal")
    assert 'status="expired_margin_block"' in after
    assert '"expired_order_rejected"' in after
    assert '"expired_held_at_due"' in _function(s, "R11PrepareFreshBar")
    assert 'r11SuppressReason=="delay_expired_held_at_due"' in after
    assert 'benchGate="delay_expired"' in after
    assert "R11ArmPending();candidateSide=r11ArmSignalCandidate;" in after
    assert "armAction=R11DecideDelay" in after


def test_diagnostic_columns_append_without_changing_first_13_fields():
    control = CONTROL.read_text(encoding="utf-8")
    r11 = R11.read_text(encoding="utf-8")
    def header(source: str) -> list[str]:
        call = re.search(r'FileWrite\(diagnosticFile,"bar"[^;]+;', source).group(0)
        return re.findall(r'"([a-z0-9_]+)"', call)
    base = header(control)
    cols = header(r11)
    assert len(base) == 13 and cols[:13] == base
    assert cols[13:] == [
        "delay_original_bar", "delay_due_bar", "delay_original_side", "delay_origin_bid",
        "delay_origin_ask", "delay_origin_atr", "delay_status", "delay_confirmation_bar",
        "delay_confirmation_close", "delay_confirmation_ema9", "delay_confirmation_trend",
        "delay_decision_bid", "delay_decision_ask", "delay_decision_atr",
    ]
    assert len(cols) == 27
    assert "r11ReportDecisionAsk=ask" in _function(r11, "OriginalOnTick")
    assert "r11ReportDecisionBid=bid" in _function(r11, "OriginalOnTick")


def test_native_state_machine_fixtures_cover_all_required_transitions():
    s = R11.read_text(encoding="utf-8")
    fixtures = _function(s, "RunR11DeterministicFixtures")
    cases = (
        "delay_off_bypass", "mode0_bypass", "no_candidate", "arm_no_order", "before_due_wait",
        "stale_origin_not_armed", "malformed_due_time",
        "nonfresh_wait", "buy_confirm", "sell_confirm", "wrong_trend", "buy_close_below_ema",
        "sell_close_above_ema", "unavailable_history", "confirmation_bar_gap", "after_due_skipped",
        "blocked_due_expiry", "pending_not_replaced_duplicate", "held_at_due_even_if_management_closes",
    )
    for case in cases:
        assert f"R11_NATIVE_FIXTURE_FAIL {case}" in fixtures
    assert "if(checks!=19 || !all)return false;" in fixtures
    assert 'R11_NATIVE_FIXTURES_PASS checks=%d preset=%d' in fixtures


def test_on_tester_adds_only_r11_symbol_and_delay_specs():
    control = CONTROL.read_text(encoding="utf-8")
    r11 = R11.read_text(encoding="utf-8")
    parent = _function(control, "OnTester")
    candidate = _function(r11, "OnTester")
    rows = (
        '   FileWrite(f,"point",SymbolInfoDouble(_Symbol,SYMBOL_POINT));\n',
        '   FileWrite(f,"digits",SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));\n',
        '   FileWrite(f,"delay_enabled",InpDelayOneBar);\n',
        '   FileWrite(f,"delay_seconds",60);\n',
    )
    for row in rows:
        assert row in candidate
        candidate = candidate.replace(row, "", 1)
    assert candidate == parent


def test_held_due_expires_before_any_confirmation_history_read():
    prepare = _function(R11.read_text(encoding="utf-8"), "R11PrepareFreshBar")
    assert "0,0,0,0,false,false,heldAtStart" in prepare
    assert prepare.index("if(action==R11_DELAY_EXPIRE_HELD)") < prepare.index("CopyRates")
