//+------------------------------------------------------------------+
//|                                          ResearchCandidate_R1.mq5   |
//|                                  Copyright 2026, Quant Architect |
//|       Aegis Predator V23 - Institutional Liquidity Engine        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "24.93"
#property description "R11 one-bar persistence entry research clone, tester-only. Not a V25 release."
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
input int InpExperimentMode=0; // 0 exact V24, 1 continuation, 2 reclaim, 3 breakout
input int InpEntryStrength=0; // body/ATR .1/.2/.3, close location .6/.7/.8, buffer 0/.05/.1ATR
input bool InpUseGridIndices=false;
input int InpTPGridIndex=2; // {1,1.5,2,3}
input bool InpDelayOneBar=false; // R11 symmetric one-completed-M1-bar persistence confirmation
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;
double candidateDecisionBid=0,candidateDecisionAsk=0;
bool r11Pending=false,r11SuppressCandidate=false,r11OverrideConsumed=false;
int r11PendingSide=0,r11OverrideSignal=0,r11ArmSignalCandidate=0;
datetime r11PendingSignalBar=0,r11PendingDueBar=0,r11ArmSignalBar=0;
double r11PendingBid=0,r11PendingAsk=0,r11PendingATR=0;
double r11ArmBid=0,r11ArmAsk=0,r11ArmATR=0;
string r11SuppressReason="";
int r11ConfirmTrend=0;
string r11ReportStatus="";
datetime r11ReportOriginBar=0,r11ReportDueBar=0,r11ReportConfirmBar=0;
int r11ReportSide=0,r11ReportConfirmTrend=0;
double r11ReportOriginBid=0,r11ReportOriginAsk=0,r11ReportOriginATR=0;
double r11ReportConfirmClose=0,r11ReportConfirmEMA9=0;
double r11ReportDecisionBid=0,r11ReportDecisionAsk=0,r11ReportDecisionATR=0;

double EffectiveTPR()
{
   if(!InpUseGridIndices)return InpTakeProfitRRMul;
   double values[4]={1.0,1.5,2.0,3.0};return values[InpTPGridIndex];
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
bool ValidateR11Inputs()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION) || !ValidateV25Inputs() || InpMaxHoldBars!=60
      || InpUseGridIndices || InpTPGridIndex!=2
      || InpEnableSessionGuard || InpEnableSpreadGuard || !InpEnableMarginGuard || !InpEnableHardSL
      || InpStartHour!=11 || InpEndHour!=16 || InpMaxSpreadPts!=25
      || InpMinSLPoints!=150 || InpLotSize!=0.01 || InpMagicNumber!=992300 || InpTargetAccount!=0
      || !InpEnableCircuitBreaker || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90
      || InpDonchianPeriod!=20 || InpATRPeriod!=14) return false;
   if(InpExperimentMode==0)
      return InpEntryStrength==0 && InpStopLossATRMul==1.5 && EffectiveTPR()==2.0 && !InpDelayOneBar;
   if(InpExperimentMode==1)
      return InpEntryStrength==2 && InpStopLossATRMul==2.0 && EffectiveTPR()==3.0;
   return false;
}
enum ENUM_R11_DELAY_ACTION
{
   R11_DELAY_NONE=0,
   R11_DELAY_BYPASS,
   R11_DELAY_ARM,
   R11_DELAY_WAIT,
   R11_DELAY_CONFIRM,
   R11_DELAY_EXPIRE_BLOCKED,
   R11_DELAY_EXPIRE_HISTORY,
   R11_DELAY_EXPIRE_GAP,
   R11_DELAY_EXPIRE_TREND,
   R11_DELAY_EXPIRE_CLOSE,
   R11_DELAY_EXPIRE_SKIPPED,
   R11_DELAY_EXPIRE_HELD
};

ENUM_R11_DELAY_ACTION R11DecideDelay(bool enabled,int mode,bool fresh,datetime currentBar,
   int freshSignalSide,int pendingSide,datetime pendingSignalBar,datetime dueBar,int trend,
   datetime closedBar,double close,double ema9,bool contextAvailable,bool blocked,bool heldAtStart=false)
{
   if(!enabled || mode!=1)return R11_DELAY_BYPASS;
   if(!fresh)return R11_DELAY_WAIT;
   if(pendingSide==0)
   {
      if(freshSignalSide!=1 && freshSignalSide!=-1)return R11_DELAY_NONE;
      return closedBar==currentBar-PeriodSeconds(PERIOD_M1)
         ? R11_DELAY_ARM : R11_DELAY_EXPIRE_GAP;
   }
   if(pendingSide!=1 && pendingSide!=-1)return R11_DELAY_EXPIRE_HISTORY;
   if(dueBar!=pendingSignalBar+2*PeriodSeconds(PERIOD_M1))return R11_DELAY_EXPIRE_GAP;
   if(currentBar<dueBar)return R11_DELAY_WAIT;
   if(currentBar>dueBar)return R11_DELAY_EXPIRE_SKIPPED;
   if(heldAtStart)return R11_DELAY_EXPIRE_HELD;
   if(blocked)return R11_DELAY_EXPIRE_BLOCKED;
   if(!contextAvailable || !MathIsValidNumber(close) || !MathIsValidNumber(ema9) || close<=0.0 || ema9<=0.0)
      return R11_DELAY_EXPIRE_HISTORY;
   if(closedBar!=pendingSignalBar+PeriodSeconds(PERIOD_M1))return R11_DELAY_EXPIRE_GAP;
   if(trend!=pendingSide)return R11_DELAY_EXPIRE_TREND;
   if((pendingSide==1 && close<=ema9) || (pendingSide==-1 && close>=ema9))
      return R11_DELAY_EXPIRE_CLOSE;
   return R11_DELAY_CONFIRM;
}

bool RunR11DeterministicFixtures()
{
   int checks=0;bool all=true;ENUM_R11_DELAY_ACTION result;
   result=R11DecideDelay(false,1,true,1120,0,0,1000,1120,0,0,0,0,false,false);
   bool ok=(result==R11_DELAY_BYPASS);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL delay_off_bypass");
   result=R11DecideDelay(true,0,true,1120,1,0,1000,1120,0,0,0,0,false,false);
   ok=(result==R11_DELAY_BYPASS);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL mode0_bypass");
   result=R11DecideDelay(true,1,true,1000,0,0,0,0,0,0,0,0,false,false);
   ok=(result==R11_DELAY_NONE);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL no_candidate");
   result=R11DecideDelay(true,1,true,1000,1,0,0,0,0,940,0,0,false,false);
   ok=(result==R11_DELAY_ARM);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL arm_no_order");
   result=R11DecideDelay(true,1,true,1000,-1,0,0,0,0,880,0,0,false,false);
   ok=(result==R11_DELAY_EXPIRE_GAP);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL stale_origin_not_armed");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1119,1,1060,101,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_GAP);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL malformed_due_time");
   result=R11DecideDelay(true,1,true,1119,0,1,1000,1120,0,0,0,0,false,false);
   ok=(result==R11_DELAY_WAIT);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL before_due_wait");
   result=R11DecideDelay(true,1,false,1120,0,1,1000,1120,0,0,0,0,false,false);
   ok=(result==R11_DELAY_WAIT);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL nonfresh_wait");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1060,101,100,true,false);
   ok=(result==R11_DELAY_CONFIRM);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL buy_confirm");
   result=R11DecideDelay(true,1,true,1120,0,-1,1000,1120,-1,1060,99,100,true,false);
   ok=(result==R11_DELAY_CONFIRM);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL sell_confirm");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,-1,1060,101,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_TREND);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL wrong_trend");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1060,99,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_CLOSE);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL buy_close_below_ema");
   result=R11DecideDelay(true,1,true,1120,0,-1,1000,1120,-1,1060,101,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_CLOSE);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL sell_close_above_ema");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1060,101,100,false,false);
   ok=(result==R11_DELAY_EXPIRE_HISTORY);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL unavailable_history");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1059,101,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_GAP);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL confirmation_bar_gap");
   result=R11DecideDelay(true,1,true,1121,0,1,1000,1120,1,1060,101,100,true,false);
   ok=(result==R11_DELAY_EXPIRE_SKIPPED);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL after_due_skipped");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1060,101,100,true,true);
   ok=(result==R11_DELAY_EXPIRE_BLOCKED);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL blocked_due_expiry");
   result=R11DecideDelay(true,1,true,1120,-1,1,1000,1120,1,1060,101,100,true,false);
   ok=(result==R11_DELAY_CONFIRM);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL pending_not_replaced_duplicate");
   result=R11DecideDelay(true,1,true,1120,0,1,1000,1120,1,1060,101,100,true,false,true);
   ok=(result==R11_DELAY_EXPIRE_HELD);checks++;all=ok&&all;if(!ok)Print("R11_NATIVE_FIXTURE_FAIL held_at_due_even_if_management_closes");
   if(checks!=19 || !all)return false;
   PrintFormat("R11_NATIVE_FIXTURES_PASS checks=%d preset=%d",checks,InpEntryStrength);
   return true;
}

void R11ResetReport()
{
   r11ReportStatus="";r11ReportOriginBar=0;r11ReportDueBar=0;r11ReportConfirmBar=0;
   r11ReportSide=0;r11ReportConfirmTrend=0;
   r11ReportOriginBid=0;r11ReportOriginAsk=0;r11ReportOriginATR=0;
   r11ReportConfirmClose=0;r11ReportConfirmEMA9=0;
   r11ReportDecisionBid=0;r11ReportDecisionAsk=0;r11ReportDecisionATR=0;
}
void R11CopyPendingToReport(string status)
{
   r11ReportStatus=status;r11ReportOriginBar=r11PendingSignalBar;r11ReportDueBar=r11PendingDueBar;
   r11ReportSide=r11PendingSide;r11ReportOriginBid=r11PendingBid;r11ReportOriginAsk=r11PendingAsk;
   r11ReportOriginATR=r11PendingATR;
}
void R11ConsumePending(string status)
{
   if(!r11Pending)return;
   R11CopyPendingToReport(status);
   r11Pending=false;r11PendingSide=0;r11PendingSignalBar=0;r11PendingDueBar=0;
   r11PendingBid=0;r11PendingAsk=0;r11PendingATR=0;
}
void R11ArmPending()
{
   r11Pending=true;r11PendingSide=r11ArmSignalCandidate;
   r11PendingSignalBar=r11ArmSignalBar;r11PendingDueBar=lastBarTime+PeriodSeconds(PERIOD_M1);
   r11PendingBid=r11ArmBid;r11PendingAsk=r11ArmAsk;r11PendingATR=r11ArmATR;
   R11CopyPendingToReport("armed");
}
void R11ResetRuntimeState()
{
   r11Pending=false;r11SuppressCandidate=false;r11OverrideConsumed=false;
   r11PendingSide=0;r11OverrideSignal=0;r11ArmSignalCandidate=0;
   r11PendingSignalBar=0;r11PendingDueBar=0;r11ArmSignalBar=0;
   r11PendingBid=0;r11PendingAsk=0;r11PendingATR=0;
   r11ArmBid=0;r11ArmAsk=0;r11ArmATR=0;
   r11SuppressReason="";r11ConfirmTrend=0;
   R11ResetReport();
}

void R11PrepareFreshBar(datetime currentBar,bool heldAtStart)
{
   r11SuppressCandidate=false;r11SuppressReason="";r11OverrideSignal=0;
   r11OverrideConsumed=false;r11ArmSignalCandidate=0;
   r11ArmSignalBar=0;r11ArmBid=0;r11ArmAsk=0;r11ArmATR=0;r11ConfirmTrend=0;
   if(InpExperimentMode!=1 || !InpDelayOneBar || !r11Pending)return;
   if(currentBar<r11PendingDueBar)
   {
      r11SuppressCandidate=true;r11SuppressReason="delay_waiting";
      R11CopyPendingToReport("waiting");return;
   }
   ENUM_R11_DELAY_ACTION action=R11DecideDelay(true,InpExperimentMode,true,currentBar,0,
      r11PendingSide,r11PendingSignalBar,r11PendingDueBar,0,0,0,0,false,false,heldAtStart);
   if(action==R11_DELAY_EXPIRE_SKIPPED)
   {
      R11ConsumePending("expired_skipped_bar");r11SuppressCandidate=true;
      r11SuppressReason="delay_expired_skipped_bar";benchGate="delay_expired";return;
   }
   if(action==R11_DELAY_EXPIRE_HELD)
   {
      R11ConsumePending("expired_held_at_due");r11SuppressCandidate=true;
      r11SuppressReason="delay_expired_held_at_due";benchGate="delay_expired";return;
   }
   if(currentBar!=r11PendingDueBar)return;
   MqlRates closed[];ArraySetAsSeries(closed,true);
   bool ratesOK=(CopyRates(_Symbol,PERIOD_M1,1,1,closed)==1);
   double ema9=0.0,fast=0.0,slow=0.0,past=0.0,trendATRValue=0.0,ema20=0.0;
   bool emaOK=ReadClosed(entryFast,1,ema9);
   bool trendContextOK=ReadClosed(trendFast,1,fast) && ReadClosed(trendSlow,1,slow)
      && ReadClosed(trendFast,6,past) && ReadClosed(trendATR,1,trendATRValue)
      && ReadClosed(entrySlow,1,ema20) && trendATRValue>0.0;
   int trend=ClosedTrendDirection();
   bool contextOK=ratesOK && emaOK && trendContextOK && MathIsValidNumber(closed[0].close)
      && MathIsValidNumber(ema9);
   if(contextOK)
   {
      r11ReportConfirmBar=closed[0].time;r11ReportConfirmClose=closed[0].close;
      r11ReportConfirmEMA9=ema9;r11ReportConfirmTrend=trend;
   }
   action=R11DecideDelay(true,InpExperimentMode,true,currentBar,0,r11PendingSide,
      r11PendingSignalBar,r11PendingDueBar,trend,ratesOK?closed[0].time:0,
      ratesOK?closed[0].close:0.0,ema9,contextOK,false,heldAtStart);
   if(action==R11_DELAY_CONFIRM)
   {
      r11OverrideSignal=r11PendingSide;r11ConfirmTrend=trend;return;
   }
   string reason="expired_history";
   if(action==R11_DELAY_EXPIRE_GAP)reason="expired_bar_gap";
   else if(action==R11_DELAY_EXPIRE_TREND)reason="expired_trend_mismatch";
   else if(action==R11_DELAY_EXPIRE_CLOSE)reason="expired_ema9_close";
   else if(action==R11_DELAY_EXPIRE_HELD)reason="expired_held_at_due";
   R11ConsumePending(reason);r11SuppressCandidate=true;r11SuppressReason="delay_"+reason;
   benchGate="delay_expired";
}

void R11AfterOriginal()
{
   if(InpExperimentMode!=1 || !InpDelayOneBar)return;
   if(r11OverrideSignal!=0 && r11Pending)
   {
      if(r11OverrideConsumed)
      {
         string status="expired_"+benchGate;
         if(benchAttempt)
         {
            uint retcode=trade.ResultRetcode();
            status=(retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL)
               ? "confirmed_order_filled" : "expired_order_rejected";
         }
         if(benchGate=="margin_block")status="expired_margin_block";
         R11ConsumePending(status);
      }
      else R11ConsumePending("expired_"+benchGate);
   }
   else if(r11SuppressCandidate && !r11Pending && StringFind(r11SuppressReason,"delay_expired")==0)
   {
      candidateReason=r11SuppressReason;
      if(r11SuppressReason=="delay_expired_held_at_due" || benchGate=="no_signal")benchGate="delay_expired";
   }
   else if(r11ArmSignalCandidate!=0 && !r11Pending)
   {
      ENUM_R11_DELAY_ACTION armAction=R11DecideDelay(true,InpExperimentMode,true,lastBarTime,
         r11ArmSignalCandidate,0,0,0,0,r11ArmSignalBar,0,0,false,false);
      if(armAction==R11_DELAY_ARM)
      {
         R11ArmPending();candidateSide=r11ArmSignalCandidate;
         candidateReason="delay_armed";benchGate="delay_armed";
      }
      else
      {
         r11ReportOriginBar=r11ArmSignalBar;r11ReportDueBar=lastBarTime+PeriodSeconds(PERIOD_M1);
         r11ReportSide=r11ArmSignalCandidate;r11ReportOriginBid=r11ArmBid;
         r11ReportOriginAsk=r11ArmAsk;r11ReportOriginATR=r11ArmATR;
         r11ReportStatus="expired_origin_bar_gap";candidateSide=r11ArmSignalCandidate;
         candidateReason="delay_expired_origin_bar_gap";benchGate="delay_expired";
      }
   }
   else if(r11Pending && r11SuppressCandidate)R11CopyPendingToReport("waiting");
   r11OverrideSignal=0;r11SuppressCandidate=false;r11SuppressReason="";
   r11OverrideConsumed=false;r11ArmSignalCandidate=0;
}

bool BenchInit()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt","delay_original_bar","delay_due_bar","delay_original_side","delay_origin_bid","delay_origin_ask","delay_origin_atr","delay_status","delay_confirmation_bar","delay_confirmation_close","delay_confirmation_ema9","delay_confirmation_trend","delay_decision_bid","delay_decision_ask","delay_decision_atr");
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
int CandidateSignal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   candidateDecisionBid=0;candidateDecisionAsk=0;
   if(InpExperimentMode==1 && InpDelayOneBar)
   {
      if(r11SuppressCandidate){candidateReason=r11SuppressReason;return 0;}
      if(r11OverrideSignal!=0)
      {
         candidateSide=r11OverrideSignal;candidateTrend=r11ConfirmTrend;
         candidateReason="delay_confirmed";r11OverrideConsumed=true;return candidateSide;
      }
   }
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
   candidateDecisionBid=q.bid;candidateDecisionAsk=q.ask;
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
   if(candidateSide!=0 && InpExperimentMode==1 && InpDelayOneBar)
   {
      r11ArmSignalCandidate=candidateSide;r11ArmSignalBar=r[0].time;
      r11ArmBid=candidateDecisionBid;r11ArmAsk=candidateDecisionAsk;r11ArmATR=atr;
      candidateReason="delay_armed";return 0;
   }
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
   benchGate="no_new_bar";benchAttempt=false;
   if(fresh)
   {
      observedBar=bar;held=HasOpenPosition();candidateReason="not_evaluated_execution_block";
      candidateSide=0;candidateTrend=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
      R11ResetReport();
      if(InpExperimentMode==1 && InpDelayOneBar)R11PrepareFreshBar(bar,held);
   }
   ObservePath();OriginalOnTick();if(fresh)R11AfterOriginal();ObservePath();ObserveEquity();
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
      FileWrite(diagnosticFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,InpExperimentMode,InpEntryStrength,candidateSide,candidateTrend,candidateReason,diagnosticBody,diagnosticCloseLocation,diagnosticLevel,benchGate,held,benchAttempt,r11ReportOriginBar>0?TimeToString(r11ReportOriginBar,TIME_DATE|TIME_SECONDS):"",r11ReportDueBar>0?TimeToString(r11ReportDueBar,TIME_DATE|TIME_SECONDS):"",r11ReportSide,r11ReportOriginBid,r11ReportOriginAsk,r11ReportOriginATR,r11ReportStatus,r11ReportConfirmBar>0?TimeToString(r11ReportConfirmBar,TIME_DATE|TIME_SECONDS):"",r11ReportConfirmClose,r11ReportConfirmEMA9,r11ReportConfirmTrend,r11ReportDecisionBid,r11ReportDecisionAsk,r11ReportDecisionATR);
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
   FileWrite(f,"point",SymbolInfoDouble(_Symbol,SYMBOL_POINT));
   FileWrite(f,"digits",SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));
   FileWrite(f,"delay_enabled",InpDelayOneBar);
   FileWrite(f,"delay_seconds",60);
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
   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
   if(!ValidateR11Inputs() || !RunR11DeterministicFixtures() || !BenchInit()) return INIT_PARAMETERS_INCORRECT;
   R11ResetRuntimeState();
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

      PrintFormat("AegisPredator V23 BUY SIGNAL: Ask=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (2.0R) Spread=%d",
                  ask, sl, InpEnableHardSL, slDistance, tp, currentSpread);
      
      if(r11OverrideConsumed){r11ReportDecisionBid=symInfo.Bid();r11ReportDecisionAsk=ask;r11ReportDecisionATR=atr;}
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

      if(r11OverrideConsumed){r11ReportDecisionBid=bid;r11ReportDecisionAsk=symInfo.Ask();r11ReportDecisionATR=atr;}
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
