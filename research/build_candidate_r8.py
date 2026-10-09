"""Generate tester-only R8 quality factors from hash-pinned R1 source."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research" / "ResearchCandidate_R1.mq5"
OUTPUT = ROOT / "research" / "ResearchCandidate_R8.mq5"
PARENT_SHA256 = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
FIXTURE_COUNT = 27


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected one replacement anchor, found {count}: {old[:90]!r}")
    return text.replace(old, new, 1)


def function(text: str, name: str) -> str:
    """Return an MQL function by balanced-brace scan."""
    match = re.search(
        rf"(?m)^[\t ]*(?:[\w*&]+[\t ]+)+{re.escape(name)}[\t ]*\([^;{{}}]*\)\s*\{{",
        text,
    )
    if not match:
        raise ValueError(f"missing function {name}")
    start = match.start()
    depth = 0
    for idx in range(match.end() - 1, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    raise ValueError(f"unterminated function {name}")


def build(source: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    text = source
    text = replace_once(text, '#property version   "24.90"', '#property version   "24.98"')
    text = replace_once(text,
        'Research Candidate R1, tester-only. Not a V25 release. Profitability unverified.',
        'Research Candidate R8 continuation-quality factorial, tester-only. Not a V25 release.')
    text = replace_once(text,
        'input int InpExperimentMode=0; // 0 exact V24, 1 continuation, 2 reclaim, 3 breakout',
        'input int InpExperimentMode=0; // R8: 0 exact V24 parity, 1 frozen R1 continuation')
    text = replace_once(text,
        'input int InpEntryStrength=0; // body/ATR .1/.2/.3, close location .6/.7/.8, buffer 0/.05/.1ATR',
        'input int InpEntryStrength=0; // R8 parity P0; continuation fixed P2')
    text = replace_once(text,
        'input bool InpUseGridIndices=false;',
        'input bool InpRequireEfficiency=false;\ninput bool InpRequireNearMean=false;\ninput bool InpUseGridIndices=false;')

    # R8 owns a narrow validator; original R1 signal/execution functions stay frozen.
    text = text.replace('int CandidateSignal(double atr)', 'int R8ParentSignal(double atr)', 1)
    if text.count('int R8ParentSignal(double atr)') != 1:
        raise ValueError("R1 CandidateSignal rename failed")

    globals_anchor = 'int diagnosticFile=INVALID_HANDLE;'
    text = replace_once(text, globals_anchor,
        globals_anchor + '\nint r8FeatureFile=INVALID_HANDLE;\nint r8FixtureChecks=0;')

    validator_anchor = 'bool ValidateV25Inputs()'
    r8_support = r'''bool R8CalculateEfficiency(const double &closes[],const datetime &times[],
                           double &efficiency,bool &gapSpanning)
{
   efficiency=0.0;gapSpanning=false;
   if(ArraySize(closes)!=11 || ArraySize(times)!=11)return false;
   for(int i=0;i<11;i++)
   {
      if(!MathIsValidNumber(closes[i]) || closes[i]<=0.0 || times[i]<=0)return false;
      if(i<10)
      {
         if(times[i]<=times[i+1])return false;
         if(times[i]-times[i+1]!=60)gapSpanning=true;
      }
   }
   double path=0.0;
   for(int i=0;i<10;i++)
   {
      double step=MathAbs(closes[i]-closes[i+1]);
      if(!MathIsValidNumber(step))return false;
      path+=step;
      if(!MathIsValidNumber(path))return false;
   }
   if(path<=0.0)return false;
   efficiency=MathAbs(closes[0]-closes[10])/path;
   return MathIsValidNumber(efficiency) && efficiency>=0.0 && efficiency<=1.0;
}

bool R8EfficiencyPass(const double efficiency)
{
   return MathIsValidNumber(efficiency) && efficiency>=0.30 && efficiency<=1.0;
}

bool R8CalculateExtension(const double closedPrice,const double closedEMA9,
                          const double closedATR,double &extension)
{
   extension=0.0;
   if(!MathIsValidNumber(closedPrice) || closedPrice<=0.0
      || !MathIsValidNumber(closedEMA9) || closedEMA9<=0.0
      || !MathIsValidNumber(closedATR) || closedATR<=0.0)return false;
   extension=MathAbs(closedPrice-closedEMA9)/closedATR;
   return MathIsValidNumber(extension) && extension>=0.0;
}

bool R8ExtensionPass(const double extension)
{
   return MathIsValidNumber(extension) && extension>=0.0 && extension<=1.0;
}

int R8ApplyFactors(const int parentSide,const bool useEfficiency,const bool useNearMean,
                   const bool efficiencyAvailable,const double efficiency,
                   const bool extensionAvailable,const double extension,string &reason)
{
   reason="r8_quality_pass";
   if(parentSide==0)return 0;
   if(!useEfficiency && !useNearMean)return parentSide;
   if(useEfficiency)
   {
      if(!efficiencyAvailable){reason="r8_efficiency_unavailable";return 0;}
      if(!R8EfficiencyPass(efficiency)){reason="r8_efficiency_rejected";return 0;}
   }
   if(useNearMean)
   {
      if(!extensionAvailable){reason="r8_extension_unavailable";return 0;}
      if(!R8ExtensionPass(extension)){reason="r8_extension_rejected";return 0;}
   }
   return parentSide;
}

bool R8ReadEfficiency(double &efficiency,bool &gapSpanning)
{
   efficiency=0.0;gapSpanning=false;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,11,r)!=11)return false;
   double closes[];datetime times[];
   ArrayResize(closes,11);ArrayResize(times,11);
   for(int i=0;i<11;i++){closes[i]=r[i].close;times[i]=r[i].time;}
   return R8CalculateEfficiency(closes,times,efficiency,gapSpanning);
}

bool R8ReadExtension(const double atr,double &extension)
{
   extension=0.0;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1)return false;
   double ema9=0.0;
   if(!ReadClosed(entryFast,1,ema9))return false;
   return R8CalculateExtension(r[0].close,ema9,atr,extension);
}

void R8WriteFeatureEvent(const int parentSide,const int finalSide,const string parentReason,
                         const string reason,const bool efficiencyAvailable,const double efficiency,
                         const bool gapSpanning,const bool extensionAvailable,const double extension)
{
   if(r8FeatureFile==INVALID_HANDLE)return;
   datetime decisionBar=iTime(_Symbol,PERIOD_M1,0);
   datetime signalBar=iTime(_Symbol,PERIOD_M1,1);
   MqlTick tick;
   if(decisionBar<=0 || signalBar<=0 || signalBar>=decisionBar || !SymbolInfoTick(_Symbol,tick))return;
   string er=efficiencyAvailable ? DoubleToString(efficiency,10) : "";
   string gap=efficiencyAvailable ? (gapSpanning ? "true" : "false") : "";
   string ext=extensionAvailable ? DoubleToString(extension,10) : "";
   FileWrite(r8FeatureFile,TimeToString(decisionBar,TIME_DATE|TIME_SECONDS),
      TimeToString(signalBar,TIME_DATE|TIME_SECONDS),tick.time_msc,
      InpRequireEfficiency ? "true" : "false",InpRequireNearMean ? "true" : "false",
      efficiencyAvailable ? "true" : "false",er,gap,
      extensionAvailable ? "true" : "false",ext,parentSide,finalSide,parentReason,reason);
}

int CandidateSignal(const double atr)
{
   int parentSide=R8ParentSignal(atr);
   string parentReason=candidateReason;
   if(InpExperimentMode==0)return parentSide;
   if(parentSide==0)return 0;
   if(!InpRequireEfficiency && !InpRequireNearMean)
   {
      R8WriteFeatureEvent(parentSide,parentSide,parentReason,parentReason,false,0.0,false,false,0.0);
      return parentSide;
   }
   bool erAvailable=false,extensionAvailable=false,gapSpanning=false;
   double efficiency=0.0,extension=0.0;
   if(InpRequireEfficiency)erAvailable=R8ReadEfficiency(efficiency,gapSpanning);
   if(InpRequireNearMean)extensionAvailable=R8ReadExtension(atr,extension);
   string reason="";
   int finalSide=R8ApplyFactors(parentSide,InpRequireEfficiency,InpRequireNearMean,
      erAvailable,efficiency,extensionAvailable,extension,reason);
   candidateSide=finalSide;candidateReason=reason;
   R8WriteFeatureEvent(parentSide,finalSide,parentReason,reason,erAvailable,efficiency,
      gapSpanning,extensionAvailable,extension);
   return finalSide;
}

bool R8Assert(const bool condition,const string label)
{
   r8FixtureChecks++;
   if(!condition)Print("R8_NATIVE_FIXTURE_FAIL case=",label);
   return condition;
}

bool RunR8FixtureTests()
{
   r8FixtureChecks=0;bool ok=true;
   double trend[],down[],chop[],boundary[],shortCloses[];
   datetime times[],gapTimes[],shortTimes[];
   ArrayResize(trend,11);ArrayResize(down,11);ArrayResize(chop,11);
   ArrayResize(boundary,11);ArrayResize(times,11);ArrayResize(gapTimes,11);
   for(int i=0;i<11;i++)
   {
      trend[i]=100.0+i;down[i]=110.0-i;chop[i]=(i%2==0 ? 100.0 : 101.0);
      times[i]=(datetime)(1200-i*60);gapTimes[i]=(datetime)(1500-i*67);
   }
   boundary[0]=103.0;boundary[1]=96.5;boundary[2]=100.0;
   for(int i=3;i<11;i++)boundary[i]=100.0;
   double er=0.0,ext=0.0;bool gap=false;
   ok=R8Assert(R8CalculateEfficiency(trend,times,er,gap) && MathAbs(er-1.0)<1e-12,"ER_TREND_ONE") && ok;
   ok=R8Assert(R8CalculateEfficiency(down,times,er,gap) && MathAbs(er-1.0)<1e-12,"ER_TREND_DOWN_ONE") && ok;
   ok=R8Assert(R8CalculateEfficiency(chop,times,er,gap) && MathAbs(er)<1e-12,"ER_CHOP_ZERO") && ok;
   double flat[];ArrayResize(flat,11);ArrayInitialize(flat,100.0);
   ok=R8Assert(!R8CalculateEfficiency(flat,times,er,gap),"ER_FLAT_UNAVAILABLE") && ok;
   ArrayResize(shortCloses,10);ArrayResize(shortTimes,10);
   for(int i=0;i<10;i++){shortCloses[i]=100.0+i;shortTimes[i]=(datetime)(1000-i*60);}
   ok=R8Assert(!R8CalculateEfficiency(shortCloses,shortTimes,er,gap),"ER_SHORT_UNAVAILABLE") && ok;
   datetime badTimes[];ArrayCopy(badTimes,times);badTimes[4]=badTimes[3];
   ok=R8Assert(!R8CalculateEfficiency(trend,badTimes,er,gap),"ER_TIME_ORDER_REJECT") && ok;
   ArrayCopy(badTimes,times);badTimes[4]=0;
   ok=R8Assert(!R8CalculateEfficiency(trend,badTimes,er,gap),"ER_NONPOSITIVE_TIME_REJECT") && ok;
   double badClose[];ArrayCopy(badClose,trend);badClose[5]=0.0;
   ok=R8Assert(!R8CalculateEfficiency(badClose,times,er,gap),"ER_NONPOSITIVE_CLOSE_REJECT") && ok;
   double badNumber=MathArcsin(2.0);ArrayCopy(badClose,trend);badClose[5]=badNumber;
   ok=R8Assert(!R8CalculateEfficiency(badClose,times,er,gap),"ER_NONFINITE_CLOSE_REJECT") && ok;
   ok=R8Assert(R8CalculateEfficiency(trend,gapTimes,er,gap) && gap,"ER_GAP_ALLOWED_AND_MARKED") && ok;
   ok=R8Assert(R8CalculateEfficiency(boundary,times,er,gap) && MathAbs(er-0.30)<1e-12,"ER_EXACT_POINT_THREE") && ok;
   ok=R8Assert(R8EfficiencyPass(0.30),"ER_THRESHOLD_INCLUSIVE") && ok;
   ok=R8Assert(!R8EfficiencyPass(0.299999),"ER_BELOW_THRESHOLD_REJECT") && ok;
   ok=R8Assert(!R8EfficiencyPass(1.000001),"ER_ABOVE_DOMAIN_REJECT") && ok;
   ok=R8Assert(R8CalculateExtension(101.0,100.0,1.0,ext) && R8ExtensionPass(ext),"EXTENSION_ONE_INCLUSIVE") && ok;
   ok=R8Assert(R8CalculateExtension(99.0,100.0,1.0,ext) && R8ExtensionPass(ext),"EXTENSION_MIRROR_ONE") && ok;
   ok=R8Assert(R8CalculateExtension(102.0,100.0,1.0,ext) && !R8ExtensionPass(ext),"EXTENSION_ABOVE_ONE_REJECT") && ok;
   ok=R8Assert(!R8CalculateExtension(101.0,100.0,0.0,ext),"EXTENSION_ZERO_ATR_REJECT") && ok;
   ok=R8Assert(!R8CalculateExtension(0.0,100.0,1.0,ext),"EXTENSION_NONPOSITIVE_PRICE_REJECT") && ok;
   ok=R8Assert(!R8CalculateExtension(101.0,badNumber,1.0,ext),"EXTENSION_NONFINITE_EMA_REJECT") && ok;
   string reason="";double nan=MathArcsin(2.0);
   ok=R8Assert(R8ApplyFactors(-1,false,false,false,nan,false,nan,reason)==-1,"FACTORS_OFF_PRESERVE_PARENT") && ok;
   ok=R8Assert(R8ApplyFactors(1,true,true,true,0.30,true,1.0,reason)==1,"BOTH_FACTORS_BUY_PASS") && ok;
   ok=R8Assert(R8ApplyFactors(-1,true,true,true,0.30,true,1.0,reason)==-1,"BOTH_FACTORS_SELL_MIRROR") && ok;
   ok=R8Assert(R8ApplyFactors(1,true,false,false,0.0,false,0.0,reason)==0,"ER_ON_UNAVAILABLE_REJECT") && ok;
   ok=R8Assert(R8ApplyFactors(1,false,true,false,0.0,false,0.0,reason)==0,"EXTENSION_ON_UNAVAILABLE_REJECT") && ok;
   ok=R8Assert(R8ApplyFactors(1,true,false,true,0.30,false,nan,reason)==1,"ER_ONLY_IGNORES_EXTENSION") && ok;
   ok=R8Assert(R8ApplyFactors(-1,false,true,false,nan,true,0.5,reason)==-1,"EXTENSION_ONLY_IGNORES_ER") && ok;
   if(r8FixtureChecks!='$FIXTURE_COUNT')ok=false;
   if(ok)Print("R8_NATIVE_FIXTURES_PASS checks=",r8FixtureChecks," preset=",InpEntryStrength);
   return ok;
}

bool ValidateR8Inputs()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION))return false;
   bool parity=(InpExperimentMode==0 && InpEntryStrength==0
      && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0
      && !InpRequireEfficiency && !InpRequireNearMean);
   bool continuation=(InpExperimentMode==1 && InpEntryStrength==2
      && InpStopLossATRMul==2.0 && InpTakeProfitRRMul==3.0);
   if(!parity && !continuation)return false;
   if(InpUseGridIndices || InpTPGridIndex!=2 || InpEnableSessionGuard || InpEnableSpreadGuard
      || !InpEnableMarginGuard || !InpEnableHardSL || InpStartHour!=11 || InpEndHour!=16
      || InpMaxSpreadPts!=25 || InpMaxHoldBars!=60 || InpDonchianPeriod!=20
      || InpATRPeriod!=14 || InpMinSLPoints!=150 || InpLotSize!=0.01
      || InpFadeBreakouts || InpMagicNumber!=992300 || InpTargetAccount!=0
      || !InpEnableCircuitBreaker || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90)
      return false;
   return MathIsValidNumber(InpStopLossATRMul) && MathIsValidNumber(InpTakeProfitRRMul)
      && MathIsValidNumber(InpLotSize);
}

'''.replace("if(r8FixtureChecks!='$FIXTURE_COUNT')", f"if(r8FixtureChecks!={FIXTURE_COUNT})")
    text = replace_once(text, validator_anchor, r8_support + validator_anchor)

    # Export recovery: allow terminal history to include end-of-test liquidation.
    # This changes only the OnTester export range, not online history queries.
    text = replace_once(text,
        'bool historyOK=HistorySelect(0,TimeCurrent());',
        "bool historyOK=HistorySelect(0,D'3000.12.31 23:59:59');")

    # Separate, bounded signal-event telemetry. No per-tick feature polling.
    text = replace_once(text,
        'diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,\',\');',
        'diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,\',\');\n'
        '   r8FeatureFile=FileOpen(InpRunTag+"_r8_features.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,\',\');')
    text = replace_once(text,
        'if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;',
        'if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE || r8FeatureFile==INVALID_HANDLE) return false;')
    header_anchor = 'FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");'
    header = ('FileWrite(r8FeatureFile,"decision_bar","signal_bar","tick_msc","require_efficiency","require_near_mean",'
              '"efficiency_available","efficiency","efficiency_gap_spanning","extension_available",'
              '"extension_atr","parent_side","final_side","parent_reason","reason");')
    text = replace_once(text, header_anchor, header_anchor + '\n   ' + header)

    # Wire the new wrapper and fixtures before files, handles, or order initialization.
    text = replace_once(text,
        'if(!ValidateV25Inputs() || !BenchInit()) return INIT_PARAMETERS_INCORRECT;',
        'if(!ValidateR8Inputs() || !RunR8FixtureTests()) return INIT_PARAMETERS_INCORRECT;\n'
        '   if(!BenchInit()) return INIT_PARAMETERS_INCORRECT;')
    text = replace_once(text,
        'if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}\n'
        '   EventKillTimer();',
        'if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}\n'
        '   if(r8FeatureFile!=INVALID_HANDLE){FileClose(r8FeatureFile);r8FeatureFile=INVALID_HANDLE;}\n'
        '   EventKillTimer();')

    # Log labels only; trade calculations, parameters, and status flow remain unchanged.
    if source.count('TP=%.2f (2.0R)') != 2:
        raise ValueError("expected two inherited TP log-label anchors")
    for old, new in (
        ('"AEGIS V24 | DEMO RESEARCH | XAUUSD M1\\n"', '"AEGIS R8 | TESTER RESEARCH | XAUUSD M1\\n"'),
        ('"V24 HEALTH Account=', '"R8 RESEARCH HEALTH Account='),
        ('"V24 ORDER RESPONSE Side=', '"R8 ORDER RESPONSE Side='),
    ):
        text = text.replace(old, new)
    text = text.replace('TP=%.2f (2.0R)', 'TP=%.2f (ConfiguredR)')

    # Provenance/invariant checks prevent silent parent drift.
    if function(source, "OnTick") != function(text, "OnTick"):
        raise ValueError("R8 generation changed frozen function OnTick")
    expected_tester = replace_once(function(source, "OnTester"),
        'bool historyOK=HistorySelect(0,TimeCurrent());',
        "bool historyOK=HistorySelect(0,D'3000.12.31 23:59:59');")
    if function(text, "OnTester") != expected_tester:
        raise ValueError("R8 generation changed OnTester beyond export HistorySelect end bound")
    expected_original_tick = function(source, "OriginalOnTick").replace(
        'TP=%.2f (2.0R)', 'TP=%.2f (ConfiguredR)')
    if function(text, "OriginalOnTick") != expected_original_tick:
        raise ValueError("R8 generation changed OriginalOnTick beyond TP log labels")
    parent_signal = function(source, "CandidateSignal")
    renamed_parent = replace_once(parent_signal, "CandidateSignal", "R8ParentSignal")
    if function(text, "R8ParentSignal") != renamed_parent:
        raise ValueError("R8 parent signal changed beyond function rename")

    source_init = function(source, "OnInit")
    expected_init = replace_once(source_init,
        'if(!ValidateV25Inputs() || !BenchInit()) return INIT_PARAMETERS_INCORRECT;',
        'if(!ValidateR8Inputs() || !RunR8FixtureTests()) return INIT_PARAMETERS_INCORRECT;\n'
        '   if(!BenchInit()) return INIT_PARAMETERS_INCORRECT;')
    if function(text, "OnInit") != expected_init:
        raise ValueError("R8 OnInit changed beyond validator and fixture wiring")
    if text.count('R8_NATIVE_FIXTURE_FAIL') != 1 or text.count('R8_NATIVE_FIXTURES_PASS checks=') != 1:
        raise ValueError("R8 fixture reporting contract changed")
    if text.count('FileWrite(r8FeatureFile,') != 2:
        raise ValueError("R8 feature CSV must have one header and one bounded event writer")
    return text


def main() -> None:
    raw = PARENT.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != PARENT_SHA256:
        raise SystemExit(f"pinned R1 source SHA mismatch: {digest}")
    generated = build(raw.decode("utf-8-sig"))
    OUTPUT.write_text(generated, encoding="utf-8", newline="\n")
    print(f"generated={OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(generated.encode()).hexdigest().upper()}")


if __name__ == "__main__":
    main()
