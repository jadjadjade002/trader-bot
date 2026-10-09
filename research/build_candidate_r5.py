"""Generate the bounded R5 M1-alignment test from immutable R4 source."""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R4_SOURCE = ROOT / "research/ResearchCandidate_R4.mq5"
OUT = ROOT / "research/ResearchCandidate_R5.mq5"
EXPECTED_R4_SHA256 = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Expected exactly one R5 source patch: " + old[:100])
    return text.replace(old, new, 1)


def generate() -> str:
    raw = R4_SOURCE.read_bytes()
    if sha256(raw).hexdigest().upper() != EXPECTED_R4_SHA256:
        raise ValueError("Hash-frozen R4 source changed")
    source = raw.decode("utf-8").replace("\r\n", "\n")
    source = replace_once(source, '#property version   "24.93"', '#property version   "24.94"')
    source = replace_once(source, 'ResearchCandidate_R2.mq5', 'ResearchCandidate_R5.mq5')
    source = replace_once(
        source,
        '#property description "Research Candidate R4 exit ablation, tester-only. R2 exhaustion signal frozen. Not a V25 release."',
        '#property description "Research Candidate R5 M1-alignment test, tester-only. R4 signal and exits frozen. Not a V25 release."',
    )
    source = replace_once(source, "R4_NATIVE_FIXTURE_FAIL", "R5_NATIVE_FIXTURE_FAIL")
    source = replace_once(source, "R4_NATIVE_FIXTURES_PASS", "R5_NATIVE_FIXTURES_PASS")
    source = replace_once(
        source,
        "   bool ok=true;r2FixtureChecks=0;ResetR2State();\n   MqlRates r[],mirror[];ArrayResize(r,23);",
        '   bool ok=true;r2FixtureChecks=0;ResetR2State();\n'
        '   ok=R2Assert(R2M1Aligned(1,1.1,1.0) && R2M1Aligned(-1,0.9,1.0),"F_m1_alignment_sides") && ok;\n'
        '   ok=R2Assert(!R2M1Aligned(1,1.0,1.0) && !R2M1Aligned(-1,1.0,1.0),"F_m1_alignment_equality") && ok;\n'
        '   MqlRates r[],mirror[];ArrayResize(r,23);',
    )
    source = replace_once(
        source,
        'input int InpEntryStrength=0; // one of two predeclared presets per R2 family',
        'input int InpEntryStrength=0; // fixed R4 displacement preset\ninput bool InpRequireM1Alignment=false; // R5: completed M1 EMA9/20 gate, mode 5 only',
    )
    source = replace_once(
        source,
        'double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;',
        '''double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;
bool r5FeaturesEvaluated=false,r5QuoteValid=false,r5GeometryValid=false,r5PricesValid=false;
bool r5SignalShapeValid=false;
string r5OpportunityStatus="not_evaluated";
double r5M5Ema20=0,r5M5Ema50=0,r5M5Ema20Past6=0,r5M5Slope=0;
double r5M1Ema9=0,r5M1Ema20=0,r5M1ATR=0,r5M5ATR=0,r5DisplacementATR=0;
double r5QuoteBid=0,r5QuoteAsk=0,r5Spread=0,r5SLDistance=0,r5TPDistance=0;
double r5SLPrice=0,r5TPPrice=0;
double r5SignalOpen=0,r5SignalHigh=0,r5SignalLow=0,r5SignalClose=0;
double r5SignalBodyATR=0,r5CloseLocationFromLow=0;

void ResetR5Diagnostics()
{
   r5FeaturesEvaluated=false;r5QuoteValid=false;r5GeometryValid=false;r5PricesValid=false;r5SignalShapeValid=false;
   r5OpportunityStatus=(InpExperimentMode==5 ? "blocked_before_context" : "not_applicable_mode");
   r5M5Ema20=0;r5M5Ema50=0;r5M5Ema20Past6=0;r5M5Slope=0;
   r5M1Ema9=0;r5M1Ema20=0;r5M1ATR=0;r5M5ATR=0;r5DisplacementATR=0;
   r5QuoteBid=0;r5QuoteAsk=0;r5Spread=0;r5SLDistance=0;r5TPDistance=0;
   r5SLPrice=0;r5TPPrice=0;
   r5SignalOpen=0;r5SignalHigh=0;r5SignalLow=0;r5SignalClose=0;
   r5SignalBodyATR=0;r5CloseLocationFromLow=0;
}

string R5FeatureText(double value,bool available)
{
   return (available && MathIsValidNumber(value) ? DoubleToString(value,8) : "");
}

void CompleteR5QuoteDiagnostics(const MqlTick &tick)
{
   if(!r5FeaturesEvaluated || !MathIsValidNumber(tick.bid) || !MathIsValidNumber(tick.ask)
      || tick.bid<=0 || tick.ask<tick.bid) return;
   r5QuoteValid=true;
   r5QuoteBid=tick.bid;r5QuoteAsk=tick.ask;r5Spread=tick.ask-tick.bid;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(point<=0 || tickSize<=0) return;
   r5SLDistance=MathMax(InpStopLossATRMul*r5M1ATR,InpMinSLPoints*point);
   r5TPDistance=r5SLDistance*InpTakeProfitRRMul;
   r5GeometryValid=(MathIsValidNumber(r5SLDistance) && MathIsValidNumber(r5TPDistance)
                    && r5SLDistance>0 && r5TPDistance>0);
   if(candidateSide==1)
   {
      r5SLPrice=NormalizeDouble(MathFloor((tick.ask-r5SLDistance)/tickSize)*tickSize,_Digits);
      r5TPPrice=NormalizeDouble(MathCeil((tick.ask+r5TPDistance)/tickSize)*tickSize,_Digits);
      r5PricesValid=true;
   }
   else if(candidateSide==-1)
   {
      r5SLPrice=NormalizeDouble(MathCeil((tick.bid+r5SLDistance)/tickSize)*tickSize,_Digits);
      r5TPPrice=NormalizeDouble(MathFloor((tick.bid-r5TPDistance)/tickSize)*tickSize,_Digits);
      r5PricesValid=true;
   }
}''',
    )
    source = replace_once(
        source,
        '      || !MathIsValidNumber(m5atr) || m5atr<=0) return false;\n   direction=0;',
        '      || !MathIsValidNumber(m5atr) || m5atr<=0) return false;\n'
        '   if(InpExperimentMode==5)\n   {\n'
        '      r5M5Ema20=fast;r5M5Ema50=slow;r5M5Ema20Past6=past;r5M5Slope=fast-past;\n'
        '      r5M1Ema9=ema9;r5M1Ema20=ema20;r5M5ATR=m5atr;\n'
        '   }\n   direction=0;',
    )
    source = replace_once(
        source,
        '   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");',
        '   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","execution_gate","held_before","order_attempt","features_evaluated","opportunity_status","m1_ema9","m1_ema20","m5_ema20","m5_ema50","m5_ema20_past6","m5_slope_5bar_delta","m1_atr","m5_atr","signed_displacement_atr_5bars","quote_bid","quote_ask","spread","initial_sl_distance","initial_tp_distance","initial_sl_price","initial_tp_price","session_id","session_endpoint","time_to_close","signal_bar_open","signal_bar_high","signal_bar_low","signal_bar_close","signal_body_atr","close_location_from_low");',
    )
    source = replace_once(
        source,
        'int CandidateR2Signal(double atr)\n{\n   candidateTrend=0;',
        'int CandidateR2Signal(double atr)\n{\n   ResetR5Diagnostics();\n   candidateTrend=0;',
    )
    source = replace_once(
        source,
        '   if(!ReadR2Context(direction,m5atr,ema9,ema20)) return 0;\n   bool needsTrend=(InpExperimentMode!=3);',
        '   if(!ReadR2Context(direction,m5atr,ema9,ema20)) return 0;\n'
        '   if(InpExperimentMode==5)\n   {\n'
        '      r5FeaturesEvaluated=true;r5OpportunityStatus="context_evaluated";\n'
        '      r5M1ATR=atr;r5DisplacementATR=(r[1].close-r[6].close)/atr;\n'
        '      r5SignalOpen=r[0].open;r5SignalHigh=r[0].high;r5SignalLow=r[0].low;r5SignalClose=r[0].close;\n'
        '      r5SignalBodyATR=MathAbs(r[0].close-r[0].open)/atr;\n'
        '      double signalRange=r[0].high-r[0].low;\n'
        '      if(signalRange>0){r5CloseLocationFromLow=(r[0].close-r[0].low)/signalRange;r5SignalShapeValid=true;}\n'
        '   }\n'
        '   bool needsTrend=(InpExperimentMode!=3);',
    )
    source = replace_once(
        source,
        '   candidateTrend=direction;\n   candidateReason="cost_or_chase";',
        '   candidateTrend=direction;\n   candidateReason="cost_or_chase";',
    )
    source = replace_once(
        source,
        '      observedBar=bar;held=HasOpenPosition();candidateReason="not_evaluated_execution_block";',
        '      observedBar=bar;held=HasOpenPosition();ResetR5Diagnostics();candidateReason="not_evaluated_execution_block";',
    )
    source = replace_once(
        source,
        '   ObservePath();OriginalOnTick();ObservePath();ObserveEquity();',
        '   ObservePath();OriginalOnTick();ObservePath();ObserveEquity();\n   if(fresh)CompleteR5QuoteDiagnostics(tick);',
    )
    source = replace_once(
        source,
        '      FileWrite(diagnosticFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,InpExperimentMode,InpEntryStrength,candidateSide,candidateTrend,candidateReason,diagnosticBody,diagnosticCloseLocation,diagnosticLevel,benchGate,held,benchAttempt);',
        '      bool haveFeatures=r5FeaturesEvaluated;\n'
        '      FileWrite(diagnosticFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,InpExperimentMode,InpEntryStrength,candidateSide,candidateTrend,candidateReason,benchGate,held,benchAttempt,haveFeatures,r5OpportunityStatus,\n'
        '         R5FeatureText(r5M1Ema9,haveFeatures),R5FeatureText(r5M1Ema20,haveFeatures),R5FeatureText(r5M5Ema20,haveFeatures),R5FeatureText(r5M5Ema50,haveFeatures),R5FeatureText(r5M5Ema20Past6,haveFeatures),R5FeatureText(r5M5Slope,haveFeatures),R5FeatureText(r5M1ATR,haveFeatures),R5FeatureText(r5M5ATR,haveFeatures),R5FeatureText(r5DisplacementATR,haveFeatures),R5FeatureText(r5QuoteBid,r5QuoteValid),R5FeatureText(r5QuoteAsk,r5QuoteValid),R5FeatureText(r5Spread,r5QuoteValid),R5FeatureText(r5SLDistance,r5GeometryValid),R5FeatureText(r5TPDistance,r5GeometryValid),R5FeatureText(r5SLPrice,r5PricesValid),R5FeatureText(r5TPPrice,r5PricesValid),"n/a","n/a","n/a",R5FeatureText(r5SignalOpen,haveFeatures),R5FeatureText(r5SignalHigh,haveFeatures),R5FeatureText(r5SignalLow,haveFeatures),R5FeatureText(r5SignalClose,haveFeatures),R5FeatureText(r5SignalBodyATR,haveFeatures),R5FeatureText(r5CloseLocationFromLow,haveFeatures && r5SignalShapeValid));',
    )
    source = replace_once(
        source,
        'if(HasOpenPosition())\n      { benchGate="held_position";',
        'if(HasOpenPosition())\n      { if(InpExperimentMode==5)r5OpportunityStatus="censored_held_position"; benchGate="held_position";',
    )
    source = replace_once(
        source,
        'if(IsCircuitBreakerActive())\n      { benchGate="circuit_breaker";',
        'if(IsCircuitBreakerActive())\n      { if(InpExperimentMode==5)r5OpportunityStatus="censored_circuit_breaker"; benchGate="circuit_breaker";',
    )
    source = replace_once(
        source,
        'bool exhaustion=(InpExperimentMode==5 && InpEntryStrength>=0 && InpEntryStrength<=1\n                    && validStop && validTarget);',
        'bool exhaustion=(InpExperimentMode==5 && InpEntryStrength>=0 && InpEntryStrength<=1\n                    && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==1.0);',
    )
    source = replace_once(
        source,
        'if((!parity && !exhaustion) || InpExperimentMode<0 || InpExperimentMode>5',
        'if((!parity && !exhaustion) || (InpExperimentMode==0 && InpRequireM1Alignment)\n      || InpExperimentMode<0 || InpExperimentMode>5',
    )
    # Mode 5 already reads shift-1 M1 EMA9/20 in ReadR2Context. Filter only
    # this branch, after the unchanged R4 predicate, and preserve execution gates.
    source = replace_once(
        source,
        '   else if(InpExperimentMode==5)\n   {\n      double e9prev;',
        '   else if(InpExperimentMode==5)\n   {\n      bool closedM1Aligned=R2M1Aligned(direction,ema9,ema20);\n      candidateReason=(closedM1Aligned ? "m1_aligned_observed" : "m1_not_aligned_observed");\n      if(InpRequireM1Alignment && !closedM1Aligned)\n      {candidateReason="m1_alignment_missing";return 0;}\n      double e9prev;',
    )
    source = replace_once(
        source,
        '   if(candidateSide!=0){candidateReason="r2_candidate_signal";candidateTrend=direction;}\n   return candidateSide;',
        '   if(candidateSide!=0)\n   {\n      if(InpExperimentMode==5)\n         candidateReason=(candidateReason=="m1_aligned_observed" ? "r2_candidate_signal_m1_aligned" : "r2_candidate_signal_m1_not_aligned");\n      else candidateReason="r2_candidate_signal";\n      candidateTrend=direction;\n   }\n   return candidateSide;',
    )
    return source


if __name__ == "__main__":
    OUT.write_text(generate(), encoding="utf-8", newline="\n")
    print("Generated hash-frozen R5 tester candidate from R4.")
