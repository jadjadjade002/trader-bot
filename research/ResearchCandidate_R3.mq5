//+------------------------------------------------------------------+
//|                                          ResearchCandidate_R3.mq5   |
//|                                  Copyright 2026, Quant Architect |
//|       Aegis Predator V23 - Institutional Liquidity Engine        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "24.92"
#property description "Research Candidate R3, tester-only. Fixed V24 economics. Not a V25 release."
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

// Inlined by build_candidate_r3.py. Tester-only. R3 signal rules only.
input string InpRunTag="r3bench";
input int InpExperimentMode=0; // 0 exact V24; 1 blowoff fade; 2 internal range; 3 efficient flag
input int InpEntryStrength=0; // preset index 0/1; family-specific frozen axis
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;

// R3 has no exit or risk optimizer. V24 SL=1.5 ATR, TP=2R, hold=60, BE off.
bool ValidateR3Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   if(InpExperimentMode<0 || InpExperimentMode>3 || InpEntryStrength<0 || InpEntryStrength>1
      || (InpExperimentMode==0 && InpEntryStrength!=0)
      || InpFadeBreakouts || InpStopLossATRMul!=1.5 || InpTakeProfitRRMul!=2.0
      || InpATRPeriod!=14 || InpMaxHoldBars!=60 || InpEnableHardSL!=true
      || InpEnableMarginGuard!=true || InpEnableCircuitBreaker!=true
      || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90 || InpMinSLPoints!=150
      || InpLotSize!=0.01 || InpEnableSessionGuard!=false || InpEnableSpreadGuard!=false
      || InpTargetAccount!=0) return false;
   return true;
}

bool BenchInitR3()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");
   return true;
}

bool CopyR3Rates(ENUM_TIMEFRAMES tf,int count,MqlRates &r[])
{
   if(count<1) return false;
   ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,tf,1,count,r)!=count) return false;
   datetime latestClosed=iTime(_Symbol,tf,1);
   if(latestClosed<=0 || r[0].time!=latestClosed) return false;
   int seconds=(tf==PERIOD_M5 ? 300 : 60);
   for(int i=0;i<count-1;i++) if(r[i].time-r[i+1].time!=seconds) return false;
   for(int i=0;i<count;i++)
   {
      if(!MathIsValidNumber(r[i].open) || !MathIsValidNumber(r[i].high)
         || !MathIsValidNumber(r[i].low) || !MathIsValidNumber(r[i].close)
         || r[i].low<=0 || r[i].high<r[i].low || r[i].high<MathMax(r[i].open,r[i].close)
         || r[i].low>MathMin(r[i].open,r[i].close) || r[i].tick_volume<=0) return false;
   }
   return true;
}

double R3CloseLocation(const MqlRates &r,int direction)
{
   double range=r.high-r.low;
   if(range<=0) return -1;
   return direction>0 ? (r.close-r.low)/range : (r.high-r.close)/range;
}

bool R3ValidSignalCandle(const MqlRates &r,double atr)
{
   double range=r.high-r.low;
   return MathIsValidNumber(atr) && atr>0 && range>0 && range<=2.0*atr;
}

// Context-injected closed M5 trend direction, shared by A and C fixtures.
int R3Trend(const double &ema20[],double ema50,double m5atr)
{
   if(!MathIsValidNumber(m5atr) || m5atr<=0 || !MathIsValidNumber(ema50)) return 0;
   for(int i=0;i<6;i++) if(!MathIsValidNumber(ema20[i])) return 0;
   if(ema20[0]>ema50 && ema20[0]>ema20[5] && ema20[0]-ema50>=0.10*m5atr) return 1;
   if(ema20[0]<ema50 && ema20[0]<ema20[5] && ema50-ema20[0]>=0.10*m5atr) return -1;
   return 0;
}

// Pure quote economics gate, separated from SymbolInfoTick for fixtures.
bool R3QuoteCost(double bid,double ask,double signalClose,double atr)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(signalClose)
      || !MathIsValidNumber(atr) || bid<=0 || ask<bid || atr<=0) return false;
   return ask-bid<=0.10*atr && MathAbs((ask+bid)/2.0-signalClose)<=0.50*atr;
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

// Pure, closed-context predicate. Arrays are series: [0]=shift1, [1]=shift2.
int R3Blowoff(int preset,const MqlRates &m1[],const double &atr[],
              const double &ema20[],double ema50,double m5atr,const double &ema9[])
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0) return 0;
   int d=R3Trend(ema20,ema50,m5atr);
   if(d==0) return 0;
   double slopeNow=d*(ema20[0]-ema20[1]);
   double slopePrior=d*(ema20[1]-ema20[5])/4.0;
   if(slopePrior<=0 || slopeNow<=0 || slopeNow>0.50*slopePrior) return 0;
   double x=(preset==0 ? 1.50 : 2.00);
   if(!MathIsValidNumber(atr[1]) || atr[1]<=0 || d*(m1[1].close-m1[8].close)<x*atr[1]) return 0;
   double priorExtreme=d>0 ? m1[2].high : m1[2].low;
   for(int i=3;i<=11;i++) priorExtreme=d>0 ? MathMax(priorExtreme,m1[i].high) : MathMin(priorExtreme,m1[i].low);
   if(d>0)
   {
      double e9prior=ema9[1];
      if(m1[1].high<=priorExtreme || m1[0].high<m1[1].high+0.05*atr[0]
         || m1[0].close>=m1[1].high || m1[0].close>=m1[0].open
         || m1[1].close<e9prior || m1[0].close>=ema9[0]
         || MathAbs(m1[0].close-ema9[0])>0.50*atr[0]
         || R3CloseLocation(m1[0],-1)<0.70) return 0;
      return -1;
   }
   double e9prior=ema9[1];
   if(m1[1].low>=priorExtreme || m1[0].low>m1[1].low-0.05*atr[0]
      || m1[0].close<=m1[1].low || m1[0].close<=m1[0].open
      || m1[1].close>e9prior || m1[0].close<=ema9[0]
      || MathAbs(m1[0].close-ema9[0])>0.50*atr[0]
      || R3CloseLocation(m1[0],1)<0.70) return 0;
   return 1;
}

// Pure internal-band rejection. Boundary sweep is explicitly disallowed.
int R3Range(int preset,const MqlRates &m1[],const double &atr[],
            const double &ema20[],double ema50,double m5atr)
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0) return 0;
   if(MathAbs(ema20[0]-ema20[5])>0.10*m5atr || MathAbs(ema20[0]-ema50)>0.20*m5atr) return 0;
   double hi=m1[1].high,lo=m1[1].low;
   for(int i=2;i<=20;i++){hi=MathMax(hi,m1[i].high);lo=MathMin(lo,m1[i].low);}
   double width=hi-lo;
   if(width<2.0*atr[0] || width>6.0*atr[0] || width<=0) return 0;
   double range=m1[0].high-m1[0].low;
   if(range<=0) return 0;
   double pos=(m1[0].close-lo)/width;
   double q=(preset==0 ? 0.80 : 0.85);
   double upperWick=(m1[0].high-MathMax(m1[0].open,m1[0].close))/range;
   double lowerWick=(MathMin(m1[0].open,m1[0].close)-m1[0].low)/range;
   if(pos>=q && m1[0].high<hi && m1[0].close<m1[0].open
      && upperWick>=0.25 && R3CloseLocation(m1[0],-1)>=0.60) return -1;
   if(pos<=1.0-q && m1[0].low>lo && m1[0].close>m1[0].open
      && lowerWick>=0.25 && R3CloseLocation(m1[0],1)>=0.60) return 1;
   return 0;
}

// Pure M5 efficiency + three-bar M1 flag predicate.
int R3EfficientFlag(int preset,const MqlRates &m1[],const MqlRates &m5[],const double &atr[],
                    const double &ema20[],double ema50,double m5atr,const double &ema9[])
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0 || !MathIsValidNumber(atr[4]) || atr[4]<=0) return 0;
   double path=0;
   for(int i=0;i<12;i++) path+=MathAbs(m5[i].close-m5[i+1].close);
   if(path<=0) return 0;
   double er=MathAbs(m5[0].close-m5[12].close)/path;
   double e=(preset==0 ? 0.60 : 0.70);
   int d=R3Trend(ema20,ema50,m5atr);
   if(d==0 || er<e || d*(m5[0].close-m5[12].close)<m5atr) return 0;
   double impulse=d*(m1[4].close-m1[7].close);
   if(impulse<atr[4]) return 0;
   if(d*(m1[3].close-m1[3].open)>=0 || d*(m1[2].close-m1[2].open)>=0
      || d*(m1[1].close-m1[1].open)>0) return 0;
   double pullback=d*(m1[4].close-m1[1].close);
   if(pullback<0.15*impulse || pullback>0.60*impulse) return 0;
   double pauseExtreme=d>0 ? m1[1].high : m1[1].low;
   for(int i=2;i<=3;i++) pauseExtreme=d>0 ? MathMax(pauseExtreme,m1[i].high) : MathMin(pauseExtreme,m1[i].low);
   if(d>0 && (m1[0].close<pauseExtreme+0.05*atr[0] || m1[0].close<=ema9[0])) return 0;
   if(d<0 && (m1[0].close>pauseExtreme-0.05*atr[0] || m1[0].close>=ema9[0])) return 0;
   if(R3CloseLocation(m1[0],d)<0.70) return 0;
   return d;
}

bool R3CostGate(const MqlRates &s1,double atr)
{
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q) || !MathIsValidNumber(q.ask) || !MathIsValidNumber(q.bid)
      || q.bid<=0 || q.ask<q.bid) return false;
   return R3QuoteCost(q.bid,q.ask,s1.close,atr);
}

int CandidateR3Signal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   if(InpExperimentMode==0){candidateReason="v24_exact_signal";candidateSide=ProposedSignal(atr);return candidateSide;}
   candidateReason="invalid_atr";
   if(!MathIsValidNumber(atr) || atr<=0) return 0;
   MqlRates m1[],m5[];
   candidateReason="closed_history_unavailable";
   if(!CopyR3Rates(PERIOD_M1,23,m1) || !CopyR3Rates(PERIOD_M5,13,m5)) return 0;
   double atrM1[],ema20[],ema50[],m5atr[],ema9[];
   ArraySetAsSeries(atrM1,true);ArraySetAsSeries(ema20,true);ArraySetAsSeries(ema50,true);
   ArraySetAsSeries(m5atr,true);ArraySetAsSeries(ema9,true);
   if(CopyBuffer(atrHandle,0,1,23,atrM1)!=23 || CopyBuffer(trendFast,0,1,6,ema20)!=6
      || CopyBuffer(trendSlow,0,1,1,ema50)!=1 || CopyBuffer(trendATR,0,1,1,m5atr)!=1
      || CopyBuffer(entryFast,0,1,2,ema9)!=2) return 0;
   for(int i=0;i<23;i++) if(!MathIsValidNumber(atrM1[i]) || atrM1[i]<=0) return 0;
   for(int i=0;i<6;i++) if(!MathIsValidNumber(ema20[i])) return 0;
   if(!MathIsValidNumber(ema50[0]) || !MathIsValidNumber(m5atr[0]) || m5atr[0]<=0
      || !MathIsValidNumber(ema9[0]) || !MathIsValidNumber(ema9[1])) return 0;
   candidateReason="cost_or_chase";
   if(!R3CostGate(m1[0],atrM1[0])) return 0;
   candidateReason="entry_pattern_absent";
   if(InpExperimentMode==1) candidateSide=R3Blowoff(InpEntryStrength,m1,atrM1,ema20,ema50[0],m5atr[0],ema9);
   else if(InpExperimentMode==2) candidateSide=R3Range(InpEntryStrength,m1,atrM1,ema20,ema50[0],m5atr[0]);
   else if(InpExperimentMode==3) candidateSide=R3EfficientFlag(InpEntryStrength,m1,m5,atrM1,ema20,ema50[0],m5atr[0],ema9);
   if(candidateSide!=0){candidateReason="r3_candidate_signal";candidateTrend=candidateSide;}
   return candidateSide;
}

void ExportCoverageR3()
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
   d[0]=InpExperimentMode;d[1]=InpStopLossATRMul;d[2]=InpTakeProfitRRMul;d[3]=0;d[4]=0;
   d[5]=net;d[6]=pos;d[7]=loss;d[8]=ArraySize(pnl);d[9]=wins;
   d[10]=TesterStatistics(STAT_EQUITY_DD);d[11]=TesterStatistics(STAT_EQUITYDD_PERCENT);
   d[12]=TesterStatistics(STAT_PROFIT);d[13]=0;d[14]=0;d[15]=(double)seenTicks;
   d[16]=(double)firstTick;d[17]=(double)lastTick;d[18]=InpEntryStrength;
   if(!FrameAdd("r3_native_grid",InpExperimentMode,net,d))return -DBL_MAX;
   for(int k=0;k<monthN;k++)
   {
      double coverage[4];coverage[0]=monthIds[k];coverage[1]=(double)monthTicks[k];
      coverage[2]=(double)monthFirst[k];coverage[3]=(double)monthLast[k];
      if(!FrameAdd("r3_month_coverage",InpExperimentMode,net,coverage))return -DBL_MAX;
   }
   return net;
}

void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name=="r3_month_coverage" && ArraySize(d)==4)
      {
         if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,pass,d[0],d[1],d[2],d[3]);
         continue;
      }
      if(name!="r3_native_grid" || ArraySize(d)!=19)continue;
      FileWrite(frameFile,pass,d[0],d[1],d[2],d[3],d[4],d[5],d[6],d[7],d[8],d[9],d[10],d[11],d[12],d[13],d[14],d[15],d[16],d[17],d[18]);
   }
   FileFlush(frameFile);
   if(frameMonthFile!=INVALID_HANDLE)FileFlush(frameMonthFile);
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

// Actual compiled MQL fixture assertions. Not market data/profit evidence.
int r3FixtureChecks=0;
bool R3Assert(bool condition,string name)
{
   r3FixtureChecks++;
   if(!condition) Print("R3_NATIVE_FIXTURE_FAIL ",name);
   return condition;
}
void R3FixtureBar(MqlRates &r,double o,double h,double l,double c,datetime t)
{
   ZeroMemory(r);r.open=o;r.high=h;r.low=l;r.close=c;r.time=t;r.tick_volume=100;
}
void R3Reflect(const MqlRates &src[],MqlRates &dst[])
{
   ArrayResize(dst,ArraySize(src));
   for(int i=0;i<ArraySize(src);i++)
      R3FixtureBar(dst[i],200-src[i].open,200-src[i].low,200-src[i].high,200-src[i].close,src[i].time);
}
bool RunR3FixtureTests()
{
   bool ok=true;r3FixtureChecks=0;
   MqlRates m1[],m5[],mirror1[],mirror5[];ArrayResize(m1,23);ArrayResize(m5,13);
   double atr[23],e20[6]={100.1,100.05,99.8,99.6,99.3,99.05},mirror20[6];
   double e9[2]={101,101},mirror9[2]={99,99};
   datetime t=2000000000;
   for(int i=0;i<23;i++){atr[i]=1;R3FixtureBar(m1[i],100,101,99,100,t-i*60);}
   for(int i=0;i<13;i++)R3FixtureBar(m5[i],100-i*0.2,100.2-i*0.2,99.8-i*0.2,100-i*0.2,t-i*300);
   for(int i=0;i<6;i++)mirror20[i]=200-e20[i];
   ok=R3Assert(R3Trend(e20,99,1)==1,"trend_buy") && ok;
   ok=R3Assert(R3Trend(mirror20,101,1)==-1,"trend_sell_mirror") && ok;
   ok=R3Assert(R3Trend(e20,99,0)==0,"invalid_trend_atr") && ok;
   R3FixtureBar(m1[1],101.8,102.2,101.7,102,t-60);
   R3FixtureBar(m1[0],102.1,102.3,100.7,100.8,t);
   ok=R3Assert(R3Blowoff(InpEntryStrength,m1,atr,e20,99,1,e9)==-1,"A_fade_sell") && ok;
   R3Reflect(m1,mirror1);
   ok=R3Assert(R3Blowoff(InpEntryStrength,mirror1,atr,mirror20,101,1,mirror9)==1,"A_fade_buy_mirror") && ok;
   double fastSlope[6]={100.3,100.05,99.8,99.6,99.3,99.05};
   ok=R3Assert(R3Blowoff(InpEntryStrength,m1,atr,fastSlope,99,1,e9)==0,"A_accelerating_trend_rejected") && ok;
   for(int i=0;i<23;i++)R3FixtureBar(m1[i],101,103,99,101,t-i*60);
   R3FixtureBar(m1[0],102.55,102.9,102.4,102.5,t);
   double flat[6]={100,100,100,100,100,100};
   ok=R3Assert(R3Range(InpEntryStrength,m1,atr,flat,100,1)==-1,"B_internal_sell") && ok;
   R3Reflect(m1,mirror1);
   ok=R3Assert(R3Range(InpEntryStrength,mirror1,atr,flat,100,1)==1,"B_internal_buy_mirror") && ok;
   m1[0].high=103;
   ok=R3Assert(R3Range(InpEntryStrength,m1,atr,flat,100,1)==0,"B_boundary_sweep_rejected") && ok;
   for(int i=0;i<23;i++)R3FixtureBar(m1[i],100,100.2,99.8,100,t-i*60);
   R3FixtureBar(m1[4],101.8,102.2,101.7,102,t-240);
   R3FixtureBar(m1[3],102,102,101.6,101.7,t-180);
   R3FixtureBar(m1[2],101.7,101.8,101.4,101.5,t-120);
   R3FixtureBar(m1[1],101.5,101.7,101.3,101.4,t-60);
   R3FixtureBar(m1[0],101.5,102.2,101.3,102.1,t);
   e9[0]=101.7;mirror9[0]=98.3;
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,m1,m5,atr,e20,99,1,e9)==1,"C_flag_buy") && ok;
   R3Reflect(m1,mirror1);R3Reflect(m5,mirror5);
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,mirror1,mirror5,atr,mirror20,101,1,mirror9)==-1,"C_flag_sell_mirror") && ok;
   for(int i=0;i<13;i++)m5[i].close=100;
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,m1,m5,atr,e20,99,1,e9)==0,"C_zero_path_rejected") && ok;
   ok=R3Assert(R3QuoteCost(100,100.08,100.04,1),"cost_allowed") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.11,100.055,1),"spread_rejected") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.08,99,1),"midpoint_chase_rejected") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.08,100.04,0),"zero_atr_rejected") && ok;
   if(ok) Print("R3_NATIVE_FIXTURES_PASS checks=",r3FixtureChecks," preset=",InpEntryStrength);
   return ok;
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
   ExportCoverageR3();
   if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}
   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}
   int f=FileOpen(InpRunTag+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"ticket","position","time_msc","type","entry","reason","magic","symbol","volume","price","profit","commission","swap","fee","comment");
   bool historyOK=HistorySelect(0,TimeCurrent());
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
   Comment("AEGIS V24 | DEMO RESEARCH | XAUUSD M1\n",
           "M5 trend + M1 pullback/reclaim | BE OFF\n",
           "Account: ",AccountInfoInteger(ACCOUNT_LOGIN)," Magic: ",InpMagicNumber,"\n",
           "Lot: ",DoubleToString(InpLotSize,2)," SL: ",DoubleToString(InpStopLossATRMul,2),
           " ATR TP: ",DoubleToString(InpTakeProfitRRMul,2),"R\n",
           "State: ",state,"\nHistorical five-month net negative. Experimental demo only.");
}
void LogV24Health()
{
   PrintFormat("V24 HEALTH Account=%I64d Mode=DEMO Connected=%d AutoTrading=%d EAAllowed=%d AccountTrading=%d AccountExperts=%d Positions=%d State=%s Balance=%.2f Equity=%.2f FreeMargin=%.2f Magic=%I64u SLATR=%.2f TPR=%.2f BE=OFF",
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
   PrintFormat("V24 ORDER RESPONSE Side=%s Retcode=%u Order=%I64u Deal=%I64u Description=%s",
       direction,code,trade.ResultOrder(),trade.ResultDeal(),trade.ResultRetcodeDescription());
   V24Status((code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)
      ? "ORDER_EXECUTED" : "ORDER_RESPONSE_NOT_CONFIRMED_FILLED");
}


//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!ValidateR3Inputs() || !RunR3FixtureTests() || !BenchInitR3()) return INIT_PARAMETERS_INCORRECT;
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

   signal=CandidateR3Signal(atr);
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
   double tpDistance = slDistance * InpTakeProfitRRMul;

   symInfo.RefreshRates();
   
   if(signal == 1)
   {
      double ask = symInfo.Ask();
      double sl = 0.0;
      if(InpEnableHardSL)
         sl = NormalizeDouble(MathFloor((ask - slDistance) / tickSize) * tickSize, _Digits);
      double tp = NormalizeDouble(MathCeil((ask + tpDistance) / tickSize) * tickSize, _Digits);

      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_BUY, InpLotSize, ask)) { benchGate="margin_block"; return; }

      PrintFormat("AegisPredator V23 BUY SIGNAL: Ask=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (2.0R) Spread=%d",
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

      PrintFormat("AegisPredator V23 SELL SIGNAL: Bid=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (2.0R) Spread=%d",
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
