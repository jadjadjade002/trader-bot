"""Generate R6's four-cell tester harness from final hash-frozen R5 source."""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R5_SOURCE = ROOT / "research/ResearchCandidate_R5.mq5"
OUT = ROOT / "research/ResearchCandidate_R6.mq5"
EXPECTED_R5_SHA256 = "98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError("Expected exactly one R6 source patch: " + old[:100])
    return source.replace(old, new, 1)


EXTENSION = r'''
// R6-only completed-bar signal study. No optimization or production path.
int r6FixtureChecks=0;
double r6M1ATR=0,r6M5ATR=0,r6M1EMA9=0,r6M1EMA20=0;
double r6M5EMA20=0,r6M5EMA50=0,r6M5PastEMA20=0;
double r6ReclaimM5EMA20=0,r6ReclaimM5EMA50=0,r6ReclaimM5PastEMA20=0,r6ReclaimM5ATR=0;
double r6ReclaimM1EMA9S2=0,r6ReclaimM1EMA9S3=0,r6ReclaimATR14S2=0;
datetime r6CurrentM5Cutoff=0,r6ReclaimM5Cutoff=0;
int r6CurrentM5Shift=-1,r6ReclaimM5Shift=-1;
double r6ATRMedian=0,r6ContractionRatio=0,r6ChannelHigh=0,r6ChannelLow=0;
double r6SignalOpen=0,r6SignalHigh=0,r6SignalLow=0,r6SignalClose=0;
int r6Direction=0;
bool r6FeaturesEvaluated=false;
string r6OpportunityStatus="not_evaluated";

void ResetR6SignalDiagnostics()
{
   r6M1ATR=0;r6M5ATR=0;r6M1EMA9=0;r6M1EMA20=0;r6ATRMedian=0;r6ContractionRatio=0;
   r6M5EMA20=0;r6M5EMA50=0;r6M5PastEMA20=0;
   r6ReclaimM5EMA20=0;r6ReclaimM5EMA50=0;r6ReclaimM5PastEMA20=0;r6ReclaimM5ATR=0;
   r6ReclaimM1EMA9S2=0;r6ReclaimM1EMA9S3=0;r6ReclaimATR14S2=0;
   r6CurrentM5Cutoff=0;r6ReclaimM5Cutoff=0;r6CurrentM5Shift=-1;r6ReclaimM5Shift=-1;
   r6ChannelHigh=0;r6ChannelLow=0;r6SignalOpen=0;r6SignalHigh=0;r6SignalLow=0;r6SignalClose=0;
   r6Direction=0;r6FeaturesEvaluated=false;r6OpportunityStatus="not_evaluated";
}

bool R6Assert(bool condition,string name)
{
   r6FixtureChecks++;
   if(!condition) Print("R6_NATIVE_FIXTURE_FAIL ",name);
   return condition;
}

double R6CloseLocation(const MqlRates &bar,int side)
{
   double range=bar.high-bar.low;
   if(range<=0 || (side!=1 && side!=-1)) return -1;
   return side>0 ? (bar.close-bar.low)/range : (bar.high-bar.close)/range;
}

bool R6ContiguousRates(const MqlRates &rates[],int count,int seconds)
{
   if(count<2 || ArraySize(rates)<count || seconds<=0) return false;
   for(int i=0;i<count;i++)
   {
      if(!MathIsValidNumber(rates[i].open) || !MathIsValidNumber(rates[i].high)
         || !MathIsValidNumber(rates[i].low) || !MathIsValidNumber(rates[i].close)
         || rates[i].low<=0 || rates[i].high<rates[i].low
         || rates[i].high<MathMax(rates[i].open,rates[i].close)
         || rates[i].low>MathMin(rates[i].open,rates[i].close)) return false;
      if(i>0 && rates[i-1].time-rates[i].time!=seconds) return false;
   }
   return true;
}

bool R6M5FullyClosed(datetime barOpen,datetime cutoff)
{
   return barOpen>0 && cutoff>0 && barOpen+300<=cutoff;
}

bool R6Median60(const double &values[],double &median)
{
   if(ArraySize(values)!=60) return false;
   double sorted[];ArrayResize(sorted,60);
   for(int i=0;i<60;i++)
   {
      if(!MathIsValidNumber(values[i]) || values[i]<=0) return false;
      sorted[i]=values[i];
   }
   ArraySort(sorted);
   median=(sorted[29]+sorted[30])*0.5;
   return MathIsValidNumber(median) && median>0;
}

// Return shift of newest M5 bar fully closed at cutoff; reject missing or irregular
// six-bar context. All EMA/ATR CopyBuffer reads use this exact shift.
bool R6M5ShiftAt(datetime cutoff,int &shift)
{
   if(cutoff<=0) return false;
   int candidate=iBarShift(_Symbol,PERIOD_M5,cutoff-1,false);
   if(candidate<0) return false;
   datetime open=iTime(_Symbol,PERIOD_M5,candidate);
   if(open<=0) return false;
   if(!R6M5FullyClosed(open,cutoff)) candidate++;
   if(candidate<1) return false;
   MqlRates bars[];ArraySetAsSeries(bars,true);
   if(CopyRates(_Symbol,PERIOD_M5,candidate,6,bars)!=6
      || !R6ContiguousRates(bars,6,300)) return false;
   for(int i=0;i<6;i++) if(!R6M5FullyClosed(bars[i].time,cutoff)) return false;
   shift=candidate;
   return true;
}

bool R6ReadM5At(datetime cutoff,double &fast,double &slow,double &past,double &atr,int &shiftOut)
{
   int shift=0;
   if(!R6M5ShiftAt(cutoff,shift)) return false;
   if(!ReadClosed(trendFast,shift,fast) || !ReadClosed(trendSlow,shift,slow)
      || !ReadClosed(trendFast,shift+5,past) || !ReadClosed(trendATR,shift,atr)
      || !MathIsValidNumber(fast) || !MathIsValidNumber(slow)
      || !MathIsValidNumber(past) || !MathIsValidNumber(atr) || atr<=0) return false;
   shiftOut=shift;
   return true;
}

int R6M5Direction(double fast,double slow,double past,double atr)
{
   if(!MathIsValidNumber(fast) || !MathIsValidNumber(slow)
      || !MathIsValidNumber(past) || !MathIsValidNumber(atr) || atr<=0) return 0;
   if(fast>slow && fast>past && fast-slow>=0.10*atr) return 1;
   if(fast<slow && fast<past && slow-fast>=0.10*atr) return -1;
   return 0;
}

bool R6ReclaimPredicate(int direction,const MqlRates &r[],double atrS2,double e9s2,double e9s3)
{
   // Current layout: s1=r[0], s2=r[1], ...; evaluate R2Exhaustion as if s2 were r[0].
   if((direction!=1 && direction!=-1) || ArraySize(r)<14
      || !R6ContiguousRates(r,14,60) || !MathIsValidNumber(atrS2) || atrS2<=0) return false;
   if(!MathIsValidNumber(e9s2) || !MathIsValidNumber(e9s3)) return false;
   double priorExtreme=(direction>0 ? r[4].low : r[4].high);
   for(int i=5;i<=13;i++) priorExtreme=(direction>0 ? MathMin(priorExtreme,r[i].low) : MathMax(priorExtreme,r[i].high));
   bool priorSwing=(direction>0 ? (r[2].low<=priorExtreme || r[3].low<=priorExtreme)
                                : (r[2].high>=priorExtreme || r[3].high>=priorExtreme));
   bool displacement=(direction>0 ? r[2].close-r[7].close<=-1.25*atrS2
                                  : r[2].close-r[7].close>=1.25*atrS2);
   return priorSwing && displacement && MathAbs(r[1].close-e9s2)<=0.25*atrS2
      && R2TrendCandle(r[1],direction>0,atrS2,0.70)
      && (direction>0 ? (r[2].close<=e9s3 && r[1].close>e9s2)
                      : (r[2].close>=e9s3 && r[1].close<e9s2));
}

bool R6ReclaimEvent(int direction,const MqlRates &r[],double atrS2)
{
   double e9s2,e9s3;
   if(!ReadClosed(entryFast,2,e9s2) || !ReadClosed(entryFast,3,e9s3)) return false;
   return R6ReclaimPredicate(direction,r,atrS2,e9s2,e9s3);
}

int R6FailureSignal(int direction,const MqlRates &r[],double atr1,double ema9s1,double b)
{
   if((direction!=1 && direction!=-1) || ArraySize(r)<2 || !MathIsValidNumber(atr1)
      || atr1<=0 || !MathIsValidNumber(ema9s1) || b<0) return 0;
   double midpoint=(r[1].high+r[1].low)*0.5;
   if(direction>0 && r[0].high<=r[1].high
      && r[0].close<midpoint-b*atr1 && r[0].close<r[0].open && r[0].close<ema9s1) return -1;
   if(direction<0 && r[0].low>=r[1].low
      && r[0].close>midpoint+b*atr1 && r[0].close>r[0].open && r[0].close>ema9s1) return 1;
   return 0;
}

bool R6VolatilitySetup(const double &atr[],double q,double &median,double &ratio)
{
   // Closed ATR array starts at shift 1: index 0=shift1, index 1=shift2.
   // Median shifts 7..66 (indices 6..65) precedes contraction shifts 2..6 (1..5).
   if(ArraySize(atr)<66 || (q!=0.60 && q!=0.65)) return false;
   double baseline[];ArrayResize(baseline,60);
   for(int i=0;i<60;i++) baseline[i]=atr[i+6];
   if(!R6Median60(baseline,median)) return false;
   double maxRecent=0;
   for(int s=1;s<=5;s++)
   {
      if(!MathIsValidNumber(atr[s]) || atr[s]<=0) return false;
      maxRecent=MathMax(maxRecent,atr[s]);
   }
   ratio=maxRecent/median;
   return MathIsValidNumber(ratio) && ratio<=q;
}

int R6BreakoutSignal(int direction,const MqlRates &r[],double atr1)
{
   if((direction!=1 && direction!=-1) || ArraySize(r)<21 || !MathIsValidNumber(atr1) || atr1<=0) return 0;
   double hi=r[1].high,lo=r[1].low;
   for(int i=2;i<=20;i++){hi=MathMax(hi,r[i].high);lo=MathMin(lo,r[i].low);}
   if(direction>0 && r[0].close>hi+0.10*atr1 && r[0].close>r[0].open
      && R6CloseLocation(r[0],1)>=0.70) return 1;
   if(direction<0 && r[0].close<lo-0.10*atr1 && r[0].close<r[0].open
      && R6CloseLocation(r[0],-1)>=0.70) return -1;
   return 0;
}

int CandidateR6Signal(double atr)
{
   candidateSide=0;candidateTrend=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   candidateReason="r6_history_or_context_unavailable";r6OpportunityStatus="history_or_context_unavailable";
   r6M1ATR=atr;r6M1EMA9=0;r6M1EMA20=0;r6M5ATR=0;r6ATRMedian=0;r6ContractionRatio=0;
   r6ChannelHigh=0;r6ChannelLow=0;r6Direction=0;
   MqlRates r[];ArraySetAsSeries(r,true);
   int historyCount=(InpExperimentMode==7 ? 80 : 23);
   int atrCount=(InpExperimentMode==7 ? 66 : 2);
   if(!CopyR2Rates(historyCount,r) || !R6ContiguousRates(r,historyCount,60)) return 0;
   double av[];ArraySetAsSeries(av,true);
   if(CopyBuffer(atrHandle,0,1,atrCount,av)!=atrCount) return 0;
   for(int i=0;i<atrCount;i++) if(!MathIsValidNumber(av[i]) || av[i]<=0) return 0;
   r6SignalOpen=r[0].open;r6SignalHigh=r[0].high;r6SignalLow=r[0].low;r6SignalClose=r[0].close;
   double e9s1,e20s1;
   if(!ReadClosed(entryFast,1,e9s1) || !ReadClosed(entrySlow,1,e20s1)) return 0;
   r6M1EMA9=e9s1;r6M1EMA20=e20s1;
   int currentShift=0;double fast=0,slow=0,past=0,m5atr=0;
   if(!R6ReadM5At(r[0].time+60,fast,slow,past,m5atr,currentShift)) return 0;
   int direction=R6M5Direction(fast,slow,past,m5atr);
   if(direction==0) {r6OpportunityStatus="m5_direction_missing";return 0;}
   r6M5ATR=m5atr;r6Direction=direction;candidateTrend=direction;
   r6M5EMA20=fast;r6M5EMA50=slow;r6M5PastEMA20=past;
   r6CurrentM5Cutoff=r[0].time+60;r6CurrentM5Shift=currentShift;
   if(InpExperimentMode==6)
   {
      double oldFast,oldSlow,oldPast,oldATR;int oldShift=0;
      if(!R6ReadM5At(r[1].time+60,oldFast,oldSlow,oldPast,oldATR,oldShift)
         || R6M5Direction(oldFast,oldSlow,oldPast,oldATR)!=direction) return 0;
      double e9s2,e9s3;
      if(!ReadClosed(entryFast,2,e9s2) || !ReadClosed(entryFast,3,e9s3)) return 0;
      r6ReclaimM5EMA20=oldFast;r6ReclaimM5EMA50=oldSlow;r6ReclaimM5PastEMA20=oldPast;
      r6ReclaimM5ATR=oldATR;r6ReclaimM5Cutoff=r[1].time+60;r6ReclaimM5Shift=oldShift;
      r6ReclaimM1EMA9S2=e9s2;r6ReclaimM1EMA9S3=e9s3;r6ReclaimATR14S2=av[1];
      r6FeaturesEvaluated=true;
      if(!R6ReclaimPredicate(direction,r,av[1],e9s2,e9s3))
      {r6OpportunityStatus="canonical_reclaim_absent";return 0;}
      r6OpportunityStatus="reclaim_failure_evaluated";
      double b=(InpEntryStrength==0 ? 0.0 : 0.10);
      candidateSide=R6FailureSignal(direction,r,av[0],e9s1,b);
   }
   else if(InpExperimentMode==7)
   {
      double q=(InpEntryStrength==0 ? 0.60 : 0.65);
      bool contracted=R6VolatilitySetup(av,q,r6ATRMedian,r6ContractionRatio);
      if(!MathIsValidNumber(r6ATRMedian) || r6ATRMedian<=0 || !MathIsValidNumber(r6ContractionRatio)) return 0;
      r6FeaturesEvaluated=true;
      double hi=r[1].high,lo=r[1].low;
      for(int i=2;i<=20;i++){hi=MathMax(hi,r[i].high);lo=MathMin(lo,r[i].low);}
      r6ChannelHigh=hi;r6ChannelLow=lo;
      if(!contracted){r6OpportunityStatus="volatility_contraction_absent";return 0;}
      r6OpportunityStatus="volatility_release_evaluated";
      if(r[0].high-r[0].low>2.0*av[0]) return 0;
      candidateSide=R6BreakoutSignal(direction,r,av[0]);
      diagnosticLevel=(direction>0 ? hi : lo);
   }
   if(candidateSide==0) {candidateReason="r6_pattern_absent";return 0;}
   candidateReason="r6_signal";
   double signalRange=r[0].high-r[0].low;
   if(signalRange<=0 || signalRange>2.0*av[0]) {candidateSide=0;candidateReason="signal_range_rejected";return 0;}
   if(!R2CostGate(r[0],av[0])) {candidateSide=0;candidateReason="cost_or_chase";return 0;}
   double range=r[0].high-r[0].low;
   diagnosticBody=MathAbs(r[0].close-r[0].open)/av[0];
   diagnosticCloseLocation=(range>0 ? (direction>0 ? (r[0].close-r[0].low)/range : (r[0].high-r[0].close)/range) : 0);
   return candidateSide;
}

void R6FixtureBar(MqlRates &r,double o,double h,double l,double c,datetime t)
{
   ZeroMemory(r);r.open=o;r.high=h;r.low=l;r.close=c;r.time=t;r.tick_volume=100;
}

bool RunR6FixtureTests()
{
   bool ok=true;r6FixtureChecks=0;
   MqlRates f[],fm[],v[],vm[];ArrayResize(f,80);ArrayResize(fm,80);ArrayResize(v,80);ArrayResize(vm,80);
   datetime t=2000000000;
   for(int i=0;i<80;i++)
   {
      R6FixtureBar(f[i],100,101,99,100,t-i*60);R6FixtureBar(v[i],100,101,99,100,t-i*60);
   }
   f[1].high=102;f[1].low=100;f[1].open=100;f[1].close=101.8;
   f[0].high=101.9;f[0].low=100.5;f[0].open=101.5;f[0].close=100.7;
   ok=R6Assert(R6FailureSignal(1,f,1,101,0)==-1,"F_buy_direction_fades") && ok;
   for(int i=0;i<79;i++) R6FixtureBar(fm[i],200-f[i].open,200-f[i].low,200-f[i].high,200-f[i].close,t-i*60);
   ok=R6Assert(R6FailureSignal(-1,fm,1,99,0)==1,"F_sell_mirror") && ok;
   ok=R6Assert(R6FailureSignal(1,f,1,100.7,0)==0,"F_ema_equality_rejected") && ok;
   ok=R6Assert(R6FailureSignal(1,f,0,101,0)==0,"F_invalid_atr_rejected") && ok;
   f[2].close=98.5;f[2].low=98.2;f[7].close=100;
   ok=R6Assert(R6ReclaimPredicate(1,f,1,101.7,99),"F_reclaim_buy_and_EMA_cross") && ok;
   ok=R6Assert(!R6ReclaimPredicate(1,f,1,101.8,99),"F_reclaim_EMA_equality_rejected") && ok;
   for(int i=0;i<80;i++) R6FixtureBar(fm[i],200-f[i].open,200-f[i].low,200-f[i].high,200-f[i].close,t-i*60);
   ok=R6Assert(R6ReclaimPredicate(-1,fm,1,98.3,101),"F_reclaim_sell_mirror") && ok;
   MqlRates fgap[];ArrayResize(fgap,14);for(int i=0;i<14;i++)fgap[i]=f[i];fgap[8].time-=60;
   ok=R6Assert(!R6ReclaimPredicate(1,fgap,1,101.7,99),"F_missing_M1_history_rejected") && ok;
   ok=R6Assert(R6M5FullyClosed(1000,1300) && !R6M5FullyClosed(1001,1300),"F_M5_close_boundary") && ok;
   MqlRates m5gap[];ArrayResize(m5gap,6);
   for(int i=0;i<6;i++)R6FixtureBar(m5gap[i],100,101,99,100,t-i*300);
   m5gap[4].time-=300;
   ok=R6Assert(!R6ContiguousRates(m5gap,6,300),"F_missing_M5_history_rejected") && ok;
   ok=R6Assert(R6M5Direction(101,100,100,1)==1 && R6M5Direction(99,100,100,1)==-1,"F_m5_mirror") && ok;
   double vals[],median=0;ArrayResize(vals,60);
   for(int i=0;i<60;i++) vals[i]=1.0;
   vals[0]=2;ok=R6Assert(R6Median60(vals,median) && median==1,"V_median60") && ok;
   double series[];ArrayResize(series,66);for(int i=0;i<66;i++)series[i]=1.0;
   for(int i=1;i<=5;i++)series[i]=0.60;
   double ratio=0;ok=R6Assert(R6VolatilitySetup(series,0.60,median,ratio) && ratio==0.60,"V_threshold_inclusive") && ok;
   ok=R6Assert(R6VolatilitySetup(series,0.65,median,ratio),"V_strict_preset_threshold_pass") && ok;
   series[5]=0.601;ok=R6Assert(!R6VolatilitySetup(series,0.60,median,ratio),"V_threshold_fail") && ok;
   for(int i=0;i<79;i++){R6FixtureBar(v[i],100,100.2,99.8,100,t-i*60);}
   for(int i=1;i<=20;i++){v[i].high=100.2;v[i].low=99.8;}
   v[0].open=100;v[0].high=100.5;v[0].low=99.9;v[0].close=100.4;
   ok=R6Assert(R6BreakoutSignal(1,v,1)==1,"V_breakout_buy") && ok;
   for(int i=0;i<79;i++)R6FixtureBar(vm[i],200-v[i].open,200-v[i].low,200-v[i].high,200-v[i].close,t-i*60);
   ok=R6Assert(R6BreakoutSignal(-1,vm,1)==-1,"V_breakout_sell_mirror") && ok;
   v[0].close=100.3;ok=R6Assert(R6BreakoutSignal(1,v,1)==0,"V_breakout_threshold_fail") && ok;
   v[10].time-=60;ok=R6Assert(!R6ContiguousRates(v,79,60),"V_gap_rejected") && ok;
   ok=R6Assert(R6CloseLocation(v[0],0)<0,"V_invalid_side_rejected") && ok;
   if(ok)
   {
      Print("R6_NATIVE_FIXTURES_PASS checks=20 preset=",InpEntryStrength);
      Print("R6_NATIVE_FIXTURES_TOTAL checks=47 R5=27 R6=20 preset=",InpEntryStrength);
   }
   return ok;
}
'''


def generate() -> str:
    raw = R5_SOURCE.read_bytes()
    if sha256(raw).hexdigest().upper() != EXPECTED_R5_SHA256:
        raise ValueError("Hash-frozen final R5 source changed")
    source = raw.decode("utf-8").replace("\r\n", "\n")
    source = replace_once(source, '#property version   "24.94"', '#property version   "24.95"')
    source = replace_once(source, 'Research Candidate R5 M1-alignment test, tester-only. R4 signal and exits frozen. Not a V25 release.', 'Research Candidate R6 bounded signal research, tester-only. Not a V25 release.')
    source = replace_once(source, 'ResearchCandidate_R5.mq5', 'ResearchCandidate_R6.mq5')
    source = source.replace("R5FeatureText", "R6FeatureText")
    source = source.replace("ResetR5Diagnostics", "ResetR6Diagnostics")
    # Permit only exact parity and the four fixed R6 cells. R5 alignment is
    # forced off; the R6 run contract never writes that legacy input.
    old_validation = '''bool ValidateR2Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   bool validStop=(InpStopLossATRMul==1.0 || InpStopLossATRMul==1.5);
   bool validTarget=(InpTakeProfitRRMul==0.75 || InpTakeProfitRRMul==1.0
                     || InpTakeProfitRRMul==1.5 || InpTakeProfitRRMul==2.0);
   bool parity=(InpExperimentMode==0 && InpEntryStrength==0
                && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0);
   bool exhaustion=(InpExperimentMode==5 && InpEntryStrength>=0 && InpEntryStrength<=1
                    && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==1.0);
   if((!parity && !exhaustion) || (InpExperimentMode==0 && InpRequireM1Alignment)
      || InpExperimentMode<0 || InpExperimentMode>5
      || InpEntryStrength<0 || InpEntryStrength>1 || InpFadeBreakouts
      || InpMaxHoldBars!=60 || InpEnableHardSL!=true || InpEnableMarginGuard!=true
      || InpEnableCircuitBreaker!=true || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90
      || InpMinSLPoints!=150 || InpLotSize!=0.01 || InpATRPeriod!=14
      || InpDonchianPeriod!=20 || InpMagicNumber!=992300 || InpEnableSessionGuard!=false
      || InpEnableSpreadGuard!=false || InpTargetAccount!=0) return false;
   return true;
}'''
    new_validation = '''bool ValidateR2Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   bool parity=(InpExperimentMode==0 && InpEntryStrength==0
                && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0 && !InpRequireM1Alignment);
   bool r6=(InpExperimentMode==6 || InpExperimentMode==7) && InpEntryStrength>=0
           && InpEntryStrength<=1 && InpStopLossATRMul==1.5
           && InpTakeProfitRRMul==2.0 && !InpRequireM1Alignment;
   if((!parity && !r6) || InpExperimentMode<0 || InpExperimentMode>7
      || InpFadeBreakouts || InpMaxHoldBars!=60 || !InpEnableHardSL || !InpEnableMarginGuard
      || !InpEnableCircuitBreaker || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90
      || InpMinSLPoints!=150 || InpLotSize!=0.01 || InpATRPeriod!=14
      || InpDonchianPeriod!=20 || InpMagicNumber!=992300 || InpEnableSessionGuard
      || InpEnableSpreadGuard || InpTargetAccount!=0) return false;
   return true;
}'''
    source = replace_once(source, old_validation, new_validation)
    source = replace_once(source,
        'int CandidateR2Signal(double atr)\n{\n   ResetR6Diagnostics();',
        'int CandidateR2Signal(double atr)\n{\n   ResetR6Diagnostics();\n   ResetR6SignalDiagnostics();\n   if(InpExperimentMode==6 || InpExperimentMode==7) return CandidateR6Signal(atr);')
    source = replace_once(source, 'int CandidateR2Signal(double atr)\n{',
                          'int CandidateR6Signal(double atr);\nint CandidateR2Signal(double atr)\n{')
    source = replace_once(source,
        'ResetR6Diagnostics();candidateReason="not_evaluated_execution_block";',
        'ResetR6Diagnostics();ResetR6SignalDiagnostics();candidateReason="not_evaluated_execution_block";')
    source = replace_once(source, 'bool RunR2FixtureTests()', 'bool RunR2FixtureTests()')
    source = replace_once(source, 'if(!ValidateR2Inputs() || !RunR2FixtureTests() || !BenchInitR2())',
                          'if(!ValidateR2Inputs() || !RunR2FixtureTests() || !RunR6FixtureTests() || !BenchInitR2())')
    source = replace_once(source, 'int r2FixtureChecks=0;', 'int r2FixtureChecks=0;\n' + EXTENSION)
    source = replace_once(source, 'if(InpExperimentMode==5)r5OpportunityStatus="censored_held_position";',
                          'if(InpExperimentMode==5)r5OpportunityStatus="censored_held_position"; if(InpExperimentMode>=6)r6OpportunityStatus="censored_held_position";')
    source = replace_once(source, 'if(InpExperimentMode==5)r5OpportunityStatus="censored_circuit_breaker";',
                          'if(InpExperimentMode==5)r5OpportunityStatus="censored_circuit_breaker"; if(InpExperimentMode>=6)r6OpportunityStatus="censored_circuit_breaker";')
    # Append R6-specific closed-bar features. Legacy R5 EMA/displacement fields
    # stay empty for modes 6/7 because haveFeatures remains false.
    source = replace_once(source,
        '"signal_body_atr","close_location_from_low");',
        '"signal_body_atr","close_location_from_low","legacy_r5_fields_applicable","r6_status","r6_features_evaluated","r6_direction","r6_m1_atr","r6_m5_atr","r6_m1_ema9","r6_m1_ema20","r6_atr_median_60","r6_contraction_ratio","r6_channel_high","r6_channel_low","r6_signal_open","r6_signal_high","r6_signal_low","r6_signal_close","r6_current_m5_cutoff","r6_current_m5_shift","r6_m5_ema20","r6_m5_ema50","r6_m5_ema20_shift5","r6_reclaim_m5_cutoff","r6_reclaim_m5_shift","r6_reclaim_m5_ema20","r6_reclaim_m5_ema50","r6_reclaim_m5_ema20_shift5","r6_reclaim_m5_atr14","r6_reclaim_m1_ema9_s2","r6_reclaim_m1_ema9_s3","r6_reclaim_m1_atr14_s2");')
    marker = 'R6FeatureText(r5CloseLocationFromLow,haveFeatures && r5SignalShapeValid));'
    source = replace_once(source, marker,
        'R6FeatureText(r5CloseLocationFromLow,haveFeatures && r5SignalShapeValid),'
        '(InpExperimentMode==5 ? "true" : "false"),r6OpportunityStatus,(r6FeaturesEvaluated ? "true" : "false"),'
        'R6FeatureText((double)r6Direction,r6FeaturesEvaluated),R6FeatureText(r6M1ATR,r6FeaturesEvaluated),R6FeatureText(r6M5ATR,r6FeaturesEvaluated),'
        'R6FeatureText(r6M1EMA9,r6FeaturesEvaluated),R6FeatureText(r6M1EMA20,r6FeaturesEvaluated),'
        'R6FeatureText(r6ATRMedian,r6FeaturesEvaluated && InpExperimentMode==7),R6FeatureText(r6ContractionRatio,r6FeaturesEvaluated && InpExperimentMode==7),'
        'R6FeatureText(r6ChannelHigh,r6FeaturesEvaluated && InpExperimentMode==7),R6FeatureText(r6ChannelLow,r6FeaturesEvaluated && InpExperimentMode==7),'
        'R6FeatureText(r6SignalOpen,r6FeaturesEvaluated),R6FeatureText(r6SignalHigh,r6FeaturesEvaluated),'
        'R6FeatureText(r6SignalLow,r6FeaturesEvaluated),R6FeatureText(r6SignalClose,r6FeaturesEvaluated),'
        'R6FeatureText((double)r6CurrentM5Cutoff,r6FeaturesEvaluated),R6FeatureText((double)r6CurrentM5Shift,r6FeaturesEvaluated),'
        'R6FeatureText(r6M5EMA20,r6FeaturesEvaluated),R6FeatureText(r6M5EMA50,r6FeaturesEvaluated),R6FeatureText(r6M5PastEMA20,r6FeaturesEvaluated),'
        'R6FeatureText((double)r6ReclaimM5Cutoff,r6FeaturesEvaluated && InpExperimentMode==6),R6FeatureText((double)r6ReclaimM5Shift,r6FeaturesEvaluated && InpExperimentMode==6),'
        'R6FeatureText(r6ReclaimM5EMA20,r6FeaturesEvaluated && InpExperimentMode==6),R6FeatureText(r6ReclaimM5EMA50,r6FeaturesEvaluated && InpExperimentMode==6),'
        'R6FeatureText(r6ReclaimM5PastEMA20,r6FeaturesEvaluated && InpExperimentMode==6),R6FeatureText(r6ReclaimM5ATR,r6FeaturesEvaluated && InpExperimentMode==6),'
        'R6FeatureText(r6ReclaimM1EMA9S2,r6FeaturesEvaluated && InpExperimentMode==6),R6FeatureText(r6ReclaimM1EMA9S3,r6FeaturesEvaluated && InpExperimentMode==6),'
        'R6FeatureText(r6ReclaimATR14S2,r6FeaturesEvaluated && InpExperimentMode==6));')
    return source


if __name__ == "__main__":
    OUT.write_text(generate(), encoding="utf-8", newline="\n")
    print("Generated R6 four-cell tester candidate from hash-frozen final R5.")
