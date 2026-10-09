//+------------------------------------------------------------------+
//|                                          ResearchCandidate_R1.mq5   |
//|                                  Copyright 2026, Quant Architect |
//|       Aegis Predator V23 - Institutional Liquidity Engine        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "24.98"
#property description "Research Candidate R8 continuation-quality factorial, tester-only. Not a V25 release."
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Input Parameters
input group "=== Session & Execution Gates ==="
input bool     InpEnableSessionGuard = false;    // Guard 1: Session Time Guard (Disabled - 24H Alpha Mode)
input bool     InpEnableSpreadGuard  = false;    // Guard 2: Max Spread Gate
input bool     InpEnableMarginGuard  = true;     // Guard 4: Margin Pre-Check Guard
input bool     InpEnableHardSL       = true;     // Guard 6: Broker-Side Emergency Hard SL
input int      InpStartHour        = 11;       // Start Hour (Broker time EET/EEST)
input int      InpEndHour          = 16;       // End Hour (Broker time, trades strictly < EndHour)
input int      InpMaxSpreadPts     = 25;       // Max Allowed Spread (Points)
input int      InpMaxHoldBars      = 60;       // Max Holding Bars (M1 bars)

input group "=== Signal & Risk Parameters ==="
input int      InpDonchianPeriod   = 20;       // Donchian Channel Period
input int      InpATRPeriod        = 14;       // ATR Volatility Period
input double   InpStopLossATRMul   = 1.5;      // Stop Loss ATR Multiplier
input double   InpTakeProfitRRMul  = 2.0;      // Take Profit Risk:Reward Ratio (2.0R)
input int      InpMinSLPoints      = 150;      // Minimum Stop Loss (Points = $1.50)
input double   InpLotSize          = 0.01;     // Trade Volume
input bool     InpFadeBreakouts    = false;     // Liquidity Fade Mode (Counter-Retail Breakout Trap)
input ulong    InpMagicNumber      = 992300;   // Expert Magic Number
input ulong    InpTargetAccount    = 0;        // Target Account (0 = Any Demo)

input group "=== Circuit Breaker & Safety ==="
input bool     InpEnableCircuitBreaker = true; // Guard 7: Consecutive Loss Circuit Breaker
input int      InpMaxConsecutiveLosses = 4;    // Max Consecutive Losses Before Pause
input int      InpCooldownMinutes      = 90;   // Cooldown Pause Duration (Minutes)

//--- Global Variables
CTrade         trade;
CPositionInfo  posInfo;
CSymbolInfo    symInfo;

int            atrHandle = INVALID_HANDLE;
datetime       lastBarTime = 0;
datetime       cooldownUntil = 0;
ulong          lastBreakerDealTicket = 0;

string benchGate="none";
bool benchAttempt=false;
int rawFile=INVALID_HANDLE;
datetime observedBar=0;
long seenTicks=0,firstTick=0,lastTick=0;
int monthIds[12];
double monthPeak[12],monthDD[12],monthDDPct[12];
long monthTicks[12],monthFirst[12],monthLast[12];
int monthN=0;
double overallPeak=0,overallDD=0;
long beModifyAttempts=0,beModifyRejected=0;
struct PathObservation
{
   ulong position;
   long opened;
   double entry,risk,mfe,mae;
   long mfeTime,maeTime;
};
PathObservation paths[];

// Inlined by hash-guarded build_v25.py. Tester only. No BE/martingale/grid.
input string InpRunTag="v25bench";
input int InpExperimentMode=0; // R8: 0 exact V24 parity, 1 frozen R1 continuation
input int InpEntryStrength=0; // R8 parity P0; continuation fixed P2
input bool InpRequireEfficiency=false;
input bool InpRequireNearMean=false;
input bool InpUseGridIndices=false;
input int InpTPGridIndex=2; // {1,1.5,2,3}
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
int r8FeatureFile=INVALID_HANDLE;
int r8FixtureChecks=0;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;

double EffectiveTPR()
{
   if(!InpUseGridIndices)return InpTakeProfitRRMul;
   double values[4]={1.0,1.5,2.0,3.0};return values[InpTPGridIndex];
}
bool R8CalculateEfficiency(const double &closes[],const datetime &times[],
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
   if(r8FixtureChecks!=27)ok=false;
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

bool ValidateV25Inputs()
{
   if(InpExperimentMode<0 || InpExperimentMode>3 || InpEntryStrength<0 || InpEntryStrength>2
      || InpTPGridIndex<0 || InpTPGridIndex>3 || InpFadeBreakouts) return false;
   if(!MathIsValidNumber(InpStopLossATRMul) || InpStopLossATRMul<0.5 || InpStopLossATRMul>3.0
      || !MathIsValidNumber(EffectiveTPR()) || EffectiveTPR()<0.5 || EffectiveTPR()>4.0
      || InpMaxHoldBars<15 || InpMaxHoldBars>120) return false;
   return true;
}
bool BenchInit()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   r8FeatureFile=FileOpen(InpRunTag+"_r8_features.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE || r8FeatureFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");
   FileWrite(r8FeatureFile,"decision_bar","signal_bar","tick_msc","require_efficiency","require_near_mean","efficiency_available","efficiency","efficiency_gap_spanning","extension_available","extension_atr","parent_side","final_side","parent_reason","reason");
   return true;
}
int ClosedTrendDirection()
{
   double fast,slow,past,a,e9,e20;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,6,past) || !ReadClosed(trendATR,1,a)
      || !ReadClosed(entryFast,1,e9) || !ReadClosed(entrySlow,1,e20) || a<=0) return 0;
   if(fast>slow && fast>past && fast-slow>=0.1*a && e9>e20) return 1;
   if(fast<slow && fast<past && slow-fast>=0.1*a && e9<e20) return -1;
   return 0;
}
int R8ParentSignal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   if(InpExperimentMode==0)
   {
      candidateReason="v24_exact_signal";
      candidateSide=ProposedSignal(atr);
      return candidateSide;
   }
   candidateReason="invalid_atr";
   if(!MathIsValidNumber(atr) || atr<=0) return 0;
   candidateTrend=ClosedTrendDirection();candidateReason="trend_unaligned";
   if(candidateTrend==0) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   candidateReason="closed_history_unavailable";
   if(CopyRates(_Symbol,PERIOD_M1,1,11,r)!=11) return 0;
   double e9;if(!ReadClosed(entryFast,1,e9)) return 0;
   MqlTick q;candidateReason="quote_unavailable";
   if(!SymbolInfoTick(_Symbol,q) || !MathIsValidNumber(q.ask) || !MathIsValidNumber(q.bid)
      || q.bid<=0 || q.ask<q.bid) return 0;
   candidateReason="cost_or_chase";
   if(q.ask-q.bid>0.1*atr || MathAbs((q.ask+q.bid)/2-r[0].close)>0.5*atr) return 0;
   double range=r[0].high-r[0].low;
   candidateReason="zero_or_oversized_candle";
   if(range<=0 || range>2.0*atr) return 0;
   double minBody[3]={0.10,0.20,0.30},minClose[3]={0.60,0.70,0.80},buffer[3]={0.0,0.05,0.10};
   bool buy=candidateTrend==1;
   diagnosticBody=MathAbs(r[0].close-r[0].open)/atr;
   diagnosticCloseLocation=buy?(r[0].close-r[0].low)/range:(r[0].high-r[0].close)/range;
   candidateReason="weak_body_or_close";
   if(diagnosticBody<minBody[InpEntryStrength] || diagnosticCloseLocation<minClose[InpEntryStrength]
      || (buy && r[0].close<=r[0].open) || (!buy && r[0].close>=r[0].open)) return 0;
   double pad=buffer[InpEntryStrength]*atr;
   candidateReason="entry_pattern_absent";
   if(InpExperimentMode==1)
   {
      diagnosticLevel=buy?r[1].high:r[1].low;
      if((buy && r[0].close>e9 && r[0].close>diagnosticLevel+pad)
         || (!buy && r[0].close<e9 && r[0].close<diagnosticLevel-pad)) candidateSide=candidateTrend;
   }
   else if(InpExperimentMode==2)
   {
      diagnosticLevel=e9;
      if((buy && r[0].low<=e9 && r[0].close>e9+pad)
         || (!buy && r[0].high>=e9 && r[0].close<e9-pad)) candidateSide=candidateTrend;
   }
   else if(InpExperimentMode==3)
   {
      diagnosticLevel=buy?r[1].high:r[1].low;
      // r[1..10] = completed shifts 2..11, excludes signal bar r[0].
      for(int i=2;i<11;i++)diagnosticLevel=buy?MathMax(diagnosticLevel,r[i].high):MathMin(diagnosticLevel,r[i].low);
      if((buy && r[0].close>e9 && r[0].close>diagnosticLevel+pad)
         || (!buy && r[0].close<e9 && r[0].close<diagnosticLevel-pad)) candidateSide=candidateTrend;
   }
   if(candidateSide!=0)candidateReason="trend_aligned_entry";
   return candidateSide;
}
void OnTick()
{
   MqlTick tick;if(!SymbolInfoTick(_Symbol,tick))return;
   if(firstTick==0)firstTick=tick.time_msc;
   lastTick=tick.time_msc;seenTicks++;
   ObserveEquity();if(monthN>0)monthTicks[monthN-1]++;
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   bool fresh=bar>0 && bar!=observedBar;
   bool held=false;datetime cd=cooldownUntil;
   if(fresh)
   {
      observedBar=bar;held=HasOpenPosition();candidateReason="not_evaluated_execution_block";
      candidateSide=0;candidateTrend=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   }
   benchGate="no_new_bar";benchAttempt=false;
   ObservePath();OriginalOnTick();ObservePath();ObserveEquity();
   if(fresh && rawFile!=INVALID_HANDLE)
   {
      // Diagnostic reads occur after economic execution, never affect its inputs.
      if(InpExperimentMode==0)candidateTrend=ClosedTrendDirection();
      MqlRates r[];double a[];ArraySetAsSeries(r,true);
      double atr=0,bc=0,ro=0,rc=0,rh=0,rl=0;
      if(CopyRates(_Symbol,PERIOD_M1,1,2,r)==2)
      {bc=r[1].close;ro=r[0].open;rc=r[0].close;rh=r[0].high;rl=r[0].low;}
      if(CopyBuffer(atrHandle,0,1,1,a)==1)atr=a[0];
      FileWrite(rawFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,candidateSide,0,0,0,atr,bc,ro,rc,rh,rl,tick.bid,tick.ask,held,cd,benchGate,benchAttempt,benchAttempt?trade.ResultRetcode():0,benchAttempt?trade.ResultOrder():0,benchAttempt?trade.ResultDeal():0);
      FileWrite(diagnosticFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,InpExperimentMode,InpEntryStrength,candidateSide,candidateTrend,candidateReason,diagnosticBody,diagnosticCloseLocation,diagnosticLevel,benchGate,held,benchAttempt);
   }
}
void ExportCoverage()
{
   int f=FileOpen(InpRunTag+"_coverage.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE)return;
   FileWrite(f,"pass","month","ticks","first_tick_msc","last_tick_msc");
   for(int k=0;k<monthN;k++)FileWrite(f,0,monthIds[k],monthTicks[k],monthFirst[k],monthLast[k]);
   FileClose(f);
}
double ExportOptimizationFrame()
{
   double pnl[];ulong ids[];
   if(!HistorySelect(0,TimeCurrent()))return -DBL_MAX;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong t=HistoryDealGetTicket(i);
      ENUM_DEAL_TYPE type=(ENUM_DEAL_TYPE)HistoryDealGetInteger(t,DEAL_TYPE);
      if((type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL)
         || HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagicNumber
         || HistoryDealGetString(t,DEAL_SYMBOL)!=_Symbol)continue;
      ulong id=(ulong)HistoryDealGetInteger(t,DEAL_POSITION_ID);int k=-1;
      for(int j=ArraySize(ids)-1;j>=0;j--)if(ids[j]==id){k=j;break;}
      if(k<0){k=ArraySize(ids);ArrayResize(ids,k+1);ArrayResize(pnl,k+1);ids[k]=id;pnl[k]=0;}
      pnl[k]+=HistoryDealGetDouble(t,DEAL_PROFIT)+HistoryDealGetDouble(t,DEAL_COMMISSION)
         +HistoryDealGetDouble(t,DEAL_SWAP)+HistoryDealGetDouble(t,DEAL_FEE);
   }
   double net=0,pos=0,loss=0;int wins=0;
   for(int i=0;i<ArraySize(pnl);i++){net+=pnl[i];if(pnl[i]>0){pos+=pnl[i];wins++;}else loss-=pnl[i];}
   double d[19];
   d[0]=InpExperimentMode;d[1]=InpStopLossATRMul;d[2]=EffectiveTPR();d[3]=0;d[4]=0.05;
   d[5]=net;d[6]=pos;d[7]=loss;d[8]=ArraySize(pnl);d[9]=wins;
   d[10]=TesterStatistics(STAT_EQUITY_DD);d[11]=TesterStatistics(STAT_EQUITYDD_PERCENT);
   d[12]=TesterStatistics(STAT_PROFIT);d[13]=0;d[14]=0;d[15]=(double)seenTicks;
   d[16]=(double)firstTick;d[17]=(double)lastTick;d[18]=InpEntryStrength;
   if(!FrameAdd("v25_native_grid",InpExperimentMode,net,d))return -DBL_MAX;
   for(int k=0;k<monthN;k++)
   {
      double coverage[4];coverage[0]=monthIds[k];coverage[1]=(double)monthTicks[k];
      coverage[2]=(double)monthFirst[k];coverage[3]=(double)monthLast[k];
      if(!FrameAdd("v25_month_coverage",InpExperimentMode,net,coverage))return -DBL_MAX;
   }
   return net;
}
void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name=="v25_month_coverage" && ArraySize(d)==4)
      {
         if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,pass,d[0],d[1],d[2],d[3]);
         continue;
      }
      if(name!="v25_native_grid" || ArraySize(d)!=19)continue;
      FileWrite(frameFile,pass,d[0],d[1],d[2],d[3],d[4],d[5],d[6],d[7],d[8],d[9],d[10],d[11],d[12],d[13],d[14],d[15],d[16],d[17],d[18]);
   }
   FileFlush(frameFile);
   if(frameMonthFile!=INVALID_HANDLE)FileFlush(frameMonthFile);
}
void OnTesterInit()
{
   frameFile=FileOpen(InpRunTag+"_optimization.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   frameMonthFile=FileOpen(InpRunTag+"_coverage.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,"pass","month","ticks","first_tick_msc","last_tick_msc");
   if(frameFile!=INVALID_HANDLE)FileWrite(frameFile,"pass","mode","sl_atr","tp_r","be_r","be_lock_r","net","gross_net_wins","gross_net_losses","positions","wins","equity_dd","equity_dd_pct","native_net","be_attempts","be_rejected","observed_ticks","first_tick_msc","last_tick_msc","entry_strength");
}
void OnTesterPass(){DrainOptimizationFrames();}
void OnTesterDeinit()
{
   DrainOptimizationFrames();
   if(frameFile!=INVALID_HANDLE){FileClose(frameFile);frameFile=INVALID_HANDLE;}
   if(frameMonthFile!=INVALID_HANDLE){FileClose(frameMonthFile);frameMonthFile=INVALID_HANDLE;}
}

void ObserveEquity()
{
   MqlTick t; if(!SymbolInfoTick(_Symbol,t)) return;
   MqlDateTime d; TimeToStruct(t.time,d); int id=d.year*100+d.mon;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(overallPeak==0) overallPeak=eq;
   overallPeak=MathMax(overallPeak,eq); overallDD=MathMax(overallDD,overallPeak-eq);
   int k=monthN-1;
   if(k<0 || monthIds[k]!=id)
   {
      if(monthN>=12) return;
      k=monthN++; monthIds[k]=id; monthPeak[k]=eq; monthFirst[k]=t.time_msc;
   }
   monthPeak[k]=MathMax(monthPeak[k],eq);
   monthDD[k]=MathMax(monthDD[k],monthPeak[k]-eq);
   if(monthPeak[k]>0) monthDDPct[k]=MathMax(monthDDPct[k],100*(monthPeak[k]-eq)/monthPeak[k]);
   monthLast[k]=t.time_msc;
}
void ObservePath()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i) || posInfo.Symbol()!=_Symbol || posInfo.Magic()!=InpMagicNumber) continue;
      ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      int k=-1;
      for(int j=ArraySize(paths)-1;j>=0;j--) if(paths[j].position==id){k=j;break;}
      if(k<0)
      {
         k=ArraySize(paths);ArrayResize(paths,k+1);
         paths[k].position=id;paths[k].opened=posInfo.Time();paths[k].entry=posInfo.PriceOpen();
         paths[k].risk=MathAbs(posInfo.PriceOpen()-posInfo.StopLoss());
         paths[k].mfe=0;paths[k].mae=0;paths[k].mfeTime=0;paths[k].maeTime=0;
      }
      MqlTick q;if(!SymbolInfoTick(_Symbol,q)) continue;
      double move=posInfo.PositionType()==POSITION_TYPE_BUY?q.bid-paths[k].entry:paths[k].entry-q.ask;
      if(move>paths[k].mfe){paths[k].mfe=move;paths[k].mfeTime=q.time_msc;}
      if(-move>paths[k].mae){paths[k].mae=-move;paths[k].maeTime=q.time_msc;}
   }
}

void ExportPaths()
{
   int f=FileOpen(InpRunTag+"_paths.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE)return;
   FileWrite(f,"position","opened","entry","initial_risk","mfe_price_sampled","mae_price_sampled","mfe_time_msc","mae_time_msc");
   for(int i=0;i<ArraySize(paths);i++) FileWrite(f,paths[i].position,paths[i].opened,paths[i].entry,paths[i].risk,
      paths[i].mfe,paths[i].mae,paths[i].mfeTime,paths[i].maeTime);
   FileClose(f);
   f=FileOpen(InpRunTag+"_be.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f!=INVALID_HANDLE){FileWrite(f,"modify_attempts","modify_rejected");FileWrite(f,beModifyAttempts,beModifyRejected);FileClose(f);}
}
double OnTester()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return ExportOptimizationFrame();
   ExportPaths();
   ObserveEquity();
   ExportCoverage();
   if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}
   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}
   int f=FileOpen(InpRunTag+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"ticket","position","time_msc","type","entry","reason","magic","symbol","volume","price","profit","commission","swap","fee","comment");
   bool historyOK=HistorySelect(0,D'3000.12.31 23:59:59');
   if(historyOK)
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong t=HistoryDealGetTicket(i);
      FileWrite(f,t,HistoryDealGetInteger(t,DEAL_POSITION_ID),HistoryDealGetInteger(t,DEAL_TIME_MSC),HistoryDealGetInteger(t,DEAL_TYPE),HistoryDealGetInteger(t,DEAL_ENTRY),HistoryDealGetInteger(t,DEAL_REASON),HistoryDealGetInteger(t,DEAL_MAGIC),HistoryDealGetString(t,DEAL_SYMBOL),HistoryDealGetDouble(t,DEAL_VOLUME),HistoryDealGetDouble(t,DEAL_PRICE),HistoryDealGetDouble(t,DEAL_PROFIT),HistoryDealGetDouble(t,DEAL_COMMISSION),HistoryDealGetDouble(t,DEAL_SWAP),HistoryDealGetDouble(t,DEAL_FEE),HistoryDealGetString(t,DEAL_COMMENT));
   }
   FileClose(f);
   f=FileOpen(InpRunTag+"_equity.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"month","observed_ticks","first_msc","last_msc","observed_equity_dd","observed_equity_dd_pct");
   for(int k=0;k<monthN;k++) FileWrite(f,monthIds[k],monthTicks[k],monthFirst[k],monthLast[k],monthDD[k],monthDDPct[k]);
   FileClose(f);
   f=FileOpen(InpRunTag+"_spec.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"key","value");
   FileWrite(f,"symbol",_Symbol);FileWrite(f,"first_tick",firstTick);FileWrite(f,"last_tick",lastTick);FileWrite(f,"observed_ticks",seenTicks);
   FileWrite(f,"history_export_ok",historyOK);
   FileWrite(f,"contract_size",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE));
   FileWrite(f,"tick_size",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE));
   FileWrite(f,"tick_value_profit",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_PROFIT));
   FileWrite(f,"tick_value_loss",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_LOSS));
   FileWrite(f,"volume_min",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN));
   FileWrite(f,"volume_max",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX));
   FileWrite(f,"volume_step",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP));
   FileWrite(f,"stops_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL));
   FileWrite(f,"freeze_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL));
   FileWrite(f,"calc_mode",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_CALC_MODE));
   FileWrite(f,"swap_mode",SymbolInfoInteger(_Symbol,SYMBOL_SWAP_MODE));
   FileWrite(f,"swap_long",SymbolInfoDouble(_Symbol,SYMBOL_SWAP_LONG));
   FileWrite(f,"swap_short",SymbolInfoDouble(_Symbol,SYMBOL_SWAP_SHORT));
   FileWrite(f,"margin_initial",SymbolInfoDouble(_Symbol,SYMBOL_MARGIN_INITIAL));
   FileWrite(f,"margin_maintenance",SymbolInfoDouble(_Symbol,SYMBOL_MARGIN_MAINTENANCE));
   FileWrite(f,"account_margin_mode",AccountInfoInteger(ACCOUNT_MARGIN_MODE));
   FileWrite(f,"stopout_mode",AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE));
   FileWrite(f,"stopout_level",AccountInfoDouble(ACCOUNT_MARGIN_SO_SO));
   FileWrite(f,"leverage",AccountInfoInteger(ACCOUNT_LEVERAGE));
   FileWrite(f,"final_balance",AccountInfoDouble(ACCOUNT_BALANCE));
   FileWrite(f,"final_equity",AccountInfoDouble(ACCOUNT_EQUITY));
   FileWrite(f,"observed_overall_equity_dd",overallDD);
   FileClose(f);
   return historyOK ? TesterStatistics(STAT_PROFIT) : -DBL_MAX;
}

// Inlined by build_v24.py. Status and account guards do not change signal economics.
int trendFast=INVALID_HANDLE,trendSlow=INVALID_HANDLE,trendATR=INVALID_HANDLE;
int entryFast=INVALID_HANDLE,entrySlow=INVALID_HANDLE;
string v24State="STARTING";

bool InitV24Signal()
{
   trendFast=iMA(_Symbol,PERIOD_M5,20,0,MODE_EMA,PRICE_CLOSE);
   trendSlow=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE);
   trendATR=iATR(_Symbol,PERIOD_M5,14);
   entryFast=iMA(_Symbol,PERIOD_M1,9,0,MODE_EMA,PRICE_CLOSE);
   entrySlow=iMA(_Symbol,PERIOD_M1,20,0,MODE_EMA,PRICE_CLOSE);
   return trendFast!=INVALID_HANDLE && trendSlow!=INVALID_HANDLE && trendATR!=INVALID_HANDLE
      && entryFast!=INVALID_HANDLE && entrySlow!=INVALID_HANDLE;
}
void V24Status(string state)
{
   v24State=state;
   Comment("AEGIS R8 | TESTER RESEARCH | XAUUSD M1\n",
           "M5 trend + M1 pullback/reclaim | BE OFF\n",
           "Account: ",AccountInfoInteger(ACCOUNT_LOGIN)," Magic: ",InpMagicNumber,"\n",
           "Lot: ",DoubleToString(InpLotSize,2)," SL: ",DoubleToString(InpStopLossATRMul,2),
           " ATR TP: ",DoubleToString(InpTakeProfitRRMul,2),"R\n",
           "State: ",state,"\nHistorical five-month net negative. Experimental demo only.");
}
void LogV24Health()
{
   PrintFormat("R8 RESEARCH HEALTH Account=%I64d Mode=DEMO Connected=%d AutoTrading=%d EAAllowed=%d AccountTrading=%d AccountExperts=%d Positions=%d State=%s Balance=%.2f Equity=%.2f FreeMargin=%.2f Magic=%I64u SLATR=%.2f TPR=%.2f BE=OFF",
      AccountInfoInteger(ACCOUNT_LOGIN),(int)TerminalInfoInteger(TERMINAL_CONNECTED),
      (int)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED),(int)MQLInfoInteger(MQL_TRADE_ALLOWED),
      (int)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),(int)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),
      PositionsTotal(),v24State,AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoDouble(ACCOUNT_MARGIN_FREE),InpMagicNumber,InpStopLossATRMul,InpTakeProfitRRMul);
}
void OnTimer()
{
   LogV24Health();
}
void LogV24Order(string direction)
{
   uint code=trade.ResultRetcode();
   PrintFormat("R8 ORDER RESPONSE Side=%s Retcode=%u Order=%I64u Deal=%I64u Description=%s",
       direction,code,trade.ResultOrder(),trade.ResultDeal(),trade.ResultRetcodeDescription());
   V24Status((code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)
      ? "ORDER_EXECUTED" : "ORDER_RESPONSE_NOT_CONFIRMED_FILLED");
}


//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
   if(!ValidateR8Inputs() || !RunR8FixtureTests()) return INIT_PARAMETERS_INCORRECT;
   if(!BenchInit()) return INIT_PARAMETERS_INCORRECT;
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
   { Print("V24 BLOCKED: demo accounts only"); return INIT_FAILED; }
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || InpFadeBreakouts)
   { Print("V24 BLOCKED: requires XAUUSD M1, FadeBreakouts=false"); return INIT_PARAMETERS_INCORRECT; }
   if(InpATRPeriod<1 || InpDonchianPeriod<1 || InpStopLossATRMul<=0 || InpTakeProfitRRMul<=0
      || InpMinSLPoints<1 || InpMaxHoldBars<1 || InpLotSize<=0
      || InpMaxConsecutiveLosses<1 || InpCooldownMinutes<1) return INIT_PARAMETERS_INCORRECT;
   // Safety: Ensure demo or authorized account
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO && InpTargetAccount == 0)
   {
      Print("CRITICAL: Live deployment requires explicit non-zero InpTargetAccount. Blocked.");
      return INIT_FAILED;
   }
   
   if(InpTargetAccount > 0 && (ulong)AccountInfoInteger(ACCOUNT_LOGIN) != InpTargetAccount)
   {
      PrintFormat("CRITICAL: Account mismatch. Running on %I64u, required %I64u", 
                  AccountInfoInteger(ACCOUNT_LOGIN), InpTargetAccount);
      return INIT_FAILED;
   }

   // Initialize Symbol Info
   if(!symInfo.Name(_Symbol))
   {
      Print("Failed to initialize symbol info for ", _Symbol);
      return INIT_FAILED;
   }
   symInfo.Refresh();

   // Verify Contract Specs
   double minLot  = symInfo.LotsMin();
   double maxLot  = symInfo.LotsMax();
   
   if(InpLotSize < minLot || InpLotSize > maxLot)
   {
      PrintFormat("CRITICAL: InpLotSize %.2f out of bounds [%.2f, %.2f]", InpLotSize, minLot, maxLot);
      return INIT_PARAMETERS_INCORRECT;
   }

   // Set Trade Object
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);

   // Create ATR Indicator Handle
   atrHandle = iATR(_Symbol, PERIOD_M1, InpATRPeriod);
   if(atrHandle == INVALID_HANDLE)
   {
      Print("Failed to create ATR handle. Error: ", GetLastError());
      return INIT_FAILED;
   }

   if(!InitV24Signal())
   { ReleaseExperiment(); Print("V24 BLOCKED: indicator initialization failed"); return INIT_FAILED; }
   if(!EventSetTimer(300))
   { ReleaseExperiment(); Print("V24 BLOCKED: heartbeat initialization failed"); return INIT_FAILED; }
   V24Status("INITIALIZED_WAIT_NEXT_BAR");
   LogV24Health();
   // Apply Charcoal / Teal & Coral Terminal Theme
   ChartSetInteger(0, CHART_MODE, CHART_CANDLES);
   ChartSetInteger(0, CHART_COLOR_BACKGROUND, 1710618);     // #1a1a1a Charcoal Dark
   ChartSetInteger(0, CHART_COLOR_FOREGROUND, 7895160);     // #787878 Muted Gray Axis
   ChartSetInteger(0, CHART_COLOR_GRID, 2302755);           // #232323 Subtle Dark Grid
   ChartSetInteger(0, CHART_COLOR_CHART_UP, 10135078);      // #26a69a Teal Wick/Border
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN, 5264367);     // #ef5350 Coral Wick/Border
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, 10135078);   // #26a69a Teal Candle Body
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, 5264367);    // #ef5350 Coral Candle Body
   ChartSetInteger(0, CHART_COLOR_CHART_LINE, 10135078);    // #26a69a Chart Line
   ChartSetInteger(0, CHART_COLOR_VOLUME, 7502370);         // #227a72 Teal Tick Volume
   ChartSetInteger(0, CHART_COLOR_BID, 7502370);            // #227a72 Teal Bid Line
   ChartSetInteger(0, CHART_COLOR_ASK, 5264367);            // #ef5350 Coral Ask Line
   ChartSetInteger(0, CHART_COLOR_STOP_LEVEL, 5264367);     // #ef5350 Coral Stops
   ChartSetInteger(0, CHART_SHOW_GRID, false);
   ChartSetInteger(0, CHART_SHOW_VOLUMES, CHART_VOLUME_TICK);
   ChartRedraw(0);

   PrintFormat("Aegis Predator V24 INITIALIZED. Symbol=%s Magic=%I64u Window=%s Lot=%.2f SpreadGuard=%s FadeBreakouts=%s CircuitBreaker=%s",
               _Symbol, InpMagicNumber, 
               InpEnableSessionGuard ? StringFormat("%d:00-%d:00", InpStartHour, InpEndHour) : "ALL_HOURS (24H)",
               InpLotSize, 
               InpEnableSpreadGuard ? "ENABLED" : "DISABLED",
               InpFadeBreakouts ? "ENABLED (LIQUIDITY SWEEP)" : "DISABLED",
               InpEnableCircuitBreaker ? StringFormat("ENABLED (%d losses / %dm pause)", InpMaxConsecutiveLosses, InpCooldownMinutes) : "DISABLED");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}
   if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}
   if(r8FeatureFile!=INVALID_HANDLE){FileClose(r8FeatureFile);r8FeatureFile=INVALID_HANDLE;}
   EventKillTimer();
   ReleaseExperiment();
   Comment("");
   if(atrHandle != INVALID_HANDLE)
   {
      IndicatorRelease(atrHandle);
      atrHandle = INVALID_HANDLE;
   }
   Print("Aegis Predator V24 deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Manage Existing Positions (Time-based exit after 60 M1 bars)     |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol() != _Symbol || posInfo.Magic() != InpMagicNumber) continue;

      datetime openTime = posInfo.Time();
      int heldBars = iBarShift(_Symbol, PERIOD_M1, openTime, false);

      if(heldBars >= InpMaxHoldBars)
      {
         PrintFormat("AegisPredator V23 TIME EXIT: Ticket=%I64u held_bars=%d >= %d. Closing position.",
                     posInfo.Ticket(), heldBars, InpMaxHoldBars);
         trade.PositionClose(posInfo.Ticket());
      }
   }
}

//+------------------------------------------------------------------+
//| Check if an open position already exists for this EA             |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol() == _Symbol && posInfo.Magic() == InpMagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Check Margin Sufficiency                                         |
//+------------------------------------------------------------------+
bool CheckMargin(ENUM_ORDER_TYPE orderType, double volume, double price)
{
   double marginRequired = 0.0;
   if(!OrderCalcMargin(orderType, _Symbol, volume, price, marginRequired))
   {
      Print("OrderCalcMargin failed. Error: ", GetLastError());
      return false;
   }
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(marginRequired > freeMargin * 0.70) // Reserve at least 30% margin buffer
   {
      PrintFormat("MARGIN GATE: Required %.2f exceeds 70%% of free margin %.2f", marginRequired, freeMargin);
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Check Consecutive Loss Circuit Breaker (Guard 7)                 |
//+------------------------------------------------------------------+
bool IsCircuitBreakerActive()
{
   if(!InpEnableCircuitBreaker) return false;
   if(TimeCurrent() < cooldownUntil) return true;

   if(!HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent()))
      return false;

   int totalDeals = HistoryDealsTotal();
   int losses = 0;
   ulong latestOutTicket = 0;

   for(int i = totalDeals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagicNumber) continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;

      if(latestOutTicket == 0) latestOutTicket = ticket;

      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      if(profit < 0.0) losses++;
      else if(profit > 0.0) break;
   }

   if(losses >= InpMaxConsecutiveLosses && latestOutTicket != lastBreakerDealTicket)
   {
      lastBreakerDealTicket = latestOutTicket;
      cooldownUntil = TimeCurrent() + (InpCooldownMinutes * 60);
      PrintFormat("AegisPredator V23 CIRCUIT BREAKER TRIGGERED: %d consecutive losses. Pausing trading for %d min until %s",
                  losses, InpCooldownMinutes, TimeToString(cooldownUntil, TIME_DATE|TIME_MINUTES));
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OriginalOnTick()
{
   // Always manage open positions on every tick
   ManageOpenPositions();

   // Closed-bar execution: only evaluate new signals on bar open
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime <= 0 || currentBarTime == lastBarTime)
      return;

   // Update bar tracker
   datetime prevBar = lastBarTime;
   lastBarTime = currentBarTime;
   if(prevBar == 0) // First tick on attach: wait for completed bar
      return;

   // If already holding position, skip signal evaluation
   if(HasOpenPosition())
      { benchGate="held_position"; V24Status("MANAGING_POSITION"); return; }

   // Check Circuit Breaker (Guard 7)
   if(IsCircuitBreakerActive())
      { benchGate="circuit_breaker"; V24Status("CIRCUIT_BREAKER_PAUSE"); return; }

   // Check Session Window (Guard 1)
   if(InpEnableSessionGuard)
   {
      MqlDateTime dt;
      TimeToStruct(currentBarTime, dt);
      if(dt.hour < InpStartHour || dt.hour >= InpEndHour)
         return;
   }

   // Fetch Spread
   symInfo.Refresh();
   long currentSpread = symInfo.Spread();

   // Check Spread Gate
   if(InpEnableSpreadGuard && currentSpread > InpMaxSpreadPts)
   {
      PrintFormat("AegisPredator V23 SPREAD BLOCK: Spread %d > %d", currentSpread, InpMaxSpreadPts);
      return;
   }

   // Fetch ATR
   double atrValues[];
   ArraySetAsSeries(atrValues, true);
   if(CopyBuffer(atrHandle, 0, 1, 1, atrValues) < 1)
   {
      Print("Failed to copy ATR buffer");
      return;
   }
   double atr = atrValues[0];
   if(atr <= 0) return;

   // Fetch Historical M1 Rates
   // We need bar 1 (retest bar), bar 2 (breakout bar), and bars 3..22 (20-bar Donchian reference)
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int neededBars = InpDonchianPeriod + 3;
   if(CopyRates(_Symbol, PERIOD_M1, 1, neededBars, rates) < neededBars)
   {
      Print("Failed to copy M1 rates");
      return;
   }

   // Calculate 20-bar Donchian High and Low reference (rates[2] to rates[21])
   double donchianHigh = rates[2].high;
   double donchianLow  = rates[2].low;
   for(int b = 3; b <= InpDonchianPeriod + 1; b++)
   {
      if(rates[b].high > donchianHigh) donchianHigh = rates[b].high;
      if(rates[b].low  < donchianLow)  donchianLow  = rates[b].low;
   }

   // Rates index guide (as series):
   // rates[0] = Completed bar 1 (the retest candle)
   // rates[1] = Completed bar 2 (the breakout candle)
   double retestOpen  = rates[0].open;
   double retestClose = rates[0].close;
   double retestHigh  = rates[0].high;
   double retestLow   = rates[0].low;
   double breakClose  = rates[1].close;

   int signal = 0;

   // Breakout pattern recognition
   if(breakClose > donchianHigh && retestLow >= (donchianHigh - 0.5 * atr) && retestClose > retestOpen)
   {
      signal = 1; // Bullish breakout condition
   }
   else if(breakClose < donchianLow && retestHigh <= (donchianLow + 0.5 * atr) && retestClose < retestOpen)
   {
      signal = -1; // Bearish breakout condition
   }

   signal=CandidateSignal(atr);
   if(signal == 0)
      { benchGate="no_signal"; V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }
   benchGate="signal";
   V24Status(signal==1 ? "BUY_CANDIDATE" : "SELL_CANDIDATE");

   // Liquidity Fade Mode: Fade breakout traps (Sweep liquidity against breakout traders)
   if(InpFadeBreakouts)
   {
      signal = -signal;
   }

   // Execution parameters
   double point = symInfo.Point();
   double tickSize = symInfo.TickSize();
   double slDistance = MathMax(InpStopLossATRMul * atr, InpMinSLPoints * point);
   double tpDistance = slDistance * EffectiveTPR();

   symInfo.RefreshRates();
   
   if(signal == 1)
   {
      double ask = symInfo.Ask();
      double sl = 0.0;
      if(InpEnableHardSL)
         sl = NormalizeDouble(MathFloor((ask - slDistance) / tickSize) * tickSize, _Digits);
      double tp = NormalizeDouble(MathCeil((ask + tpDistance) / tickSize) * tickSize, _Digits);

      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_BUY, InpLotSize, ask)) { benchGate="margin_block"; return; }

      PrintFormat("AegisPredator V23 BUY SIGNAL: Ask=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (ConfiguredR) Spread=%d",
                  ask, sl, InpEnableHardSL, slDistance, tp, currentSpread);
      
      benchAttempt=true;benchGate="order_attempt";
      if(trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "AegisPredator V24 Buy"))
      {
         LogV24Order("BUY");
      }
      else
      {
         PrintFormat("BUY FAILED. Retcode=%u (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      }
   }
   else if(signal == -1)
   {
      double bid = symInfo.Bid();
      double sl = 0.0;
      if(InpEnableHardSL)
         sl = NormalizeDouble(MathCeil((bid + slDistance) / tickSize) * tickSize, _Digits);
      double tp = NormalizeDouble(MathFloor((bid - tpDistance) / tickSize) * tickSize, _Digits);

      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_SELL, InpLotSize, bid)) { benchGate="margin_block"; return; }

      PrintFormat("AegisPredator V23 SELL SIGNAL: Bid=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (ConfiguredR) Spread=%d",
                  bid, sl, InpEnableHardSL, slDistance, tp, currentSpread);

      benchAttempt=true;benchGate="order_attempt";
      if(trade.Sell(InpLotSize, _Symbol, bid, sl, tp, "AegisPredator V24 Sell"))
      {
         LogV24Order("SELL");
      }
      else
      {
         PrintFormat("SELL FAILED. Retcode=%u (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      }
   }
}


void ReleaseExperiment()
{
   if(trendFast!=INVALID_HANDLE) IndicatorRelease(trendFast);
   if(trendSlow!=INVALID_HANDLE) IndicatorRelease(trendSlow);
   if(trendATR!=INVALID_HANDLE) IndicatorRelease(trendATR);
   if(entryFast!=INVALID_HANDLE) IndicatorRelease(entryFast);
   if(entrySlow!=INVALID_HANDLE) IndicatorRelease(entrySlow);
}

bool ReadClosed(int handle,int shift,double &value)
{
   double a[];
   if(CopyBuffer(handle,0,shift,1,a)!=1 || !MathIsValidNumber(a[0])) return false;
   value=a[0];return true;
}

int ProposedSignal(double atr)
{
   double fast,slow,past,m5atr,e9,e20;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,6,past) || !ReadClosed(trendATR,1,m5atr)
      || !ReadClosed(entryFast,1,e9) || !ReadClosed(entrySlow,1,e20) || m5atr<=0) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1) return 0;
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote)) return 0;
   if(quote.ask-quote.bid>0.1*atr || MathAbs((quote.ask+quote.bid)/2-r[0].close)>0.5*atr) return 0;
   if(fast>slow && fast>past && fast-slow>=0.1*m5atr && e9>e20
      && r[0].low<=e9 && r[0].close>e9 && r[0].close>r[0].open) return 1;
   if(fast<slow && fast<past && slow-fast>=0.1*m5atr && e9<e20
      && r[0].high>=e9 && r[0].close<e9 && r[0].close<r[0].open) return -1;
   return 0;
}
