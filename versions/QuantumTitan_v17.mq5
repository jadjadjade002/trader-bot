#property strict
#property version "17.10"
#property description "XAUUSD M1 research candidate. Target win rate is unverified. Fixed 0.01 lots."
#include <Trade/Trade.mqh>
#include "Include/QuantumTitan/V17Signal.mqh"
#include "tests/V17SignalTests.mqh"

input group "Execution (no RiskGuardian)"
input double InpMaxSpreadPoints=35.0;
input int InpCooldownSeconds=30;
input int InpMaxHoldingMinutes=10;
input int InpDeviationPoints=20;
input group "Closed-bar strategy"
input int InpSetupMode=0; // 0=mixed, 1=trend, 2=range, 3=sweep
input ENUM_V17_STOP_MODE InpStopMode=V17_STOP_HYBRID; // Fixed, structural, or the wider of both
input double InpFixedTargetPoints=120.0; // Fixed Take Profit in points (+$1.20)
input double InpFixedStopPoints=180.0; // Fixed or hybrid baseline stop in points
input double InpStopATR=1.2;
input double InpMinStopPoints=140.0;
input double InpMaxStopPoints=350.0;
input double InpRewardRisk=0.8;
input double InpMinTargetPoints=100.0;
input double InpMaxSpreadTargetFraction=0.35;
input group "Fast Breakeven & Micro-Trailing"
input bool InpUseFastBreakeven=true; // Fast Breakeven Lock
input double InpBreakevenTriggerPts=55.0; // Profit points to trigger Breakeven (+0.55$)
input double InpLockPoints=10.0; // Profit points locked at Breakeven (+0.10$)
input double InpBreakevenR=0.50; // Fallback Breakeven R ratio
input bool InpUseMicroTrailing=true; // Micro-trailing behind market
input double InpTrailingTriggerPts=80.0; // Profit points to start trailing (+0.80$)
input double InpTrailingDistancePts=40.0; // Trailing distance in points (0.40$)
input group "Macro Trend Filter (Institutional Direction)"
input bool InpUseMacroFilter=false; // Align M1 scalps with H1 Macro Trend
input int InpMacroPeriod=20; // H1 EMA Period
input group "Session Filter (Prime Liquidity Hours)"
input string InpAllowedHours="3-4,8-9,12-16,18-20"; // Prime Liquidity Hours (10 hrs/day, 71.6% WR)
input int InpSessionStartHour=0; // Legacy Start Hour (used if InpAllowedHours is empty)
input int InpSessionEndHour=0; // Legacy End Hour (used if InpAllowedHours is empty)
input bool InpWriteJournal=true;

const ulong MAGIC=991701;
const double LOT=0.01;
CTrade trade;
int ema14=INVALID_HANDLE,ema50=INVALID_HANDLE,atr14=INVALID_HANDLE,rsi14=INVALID_HANDLE;
int htf14=INVALID_HANDLE,htf50=INVALID_HANDLE,adx14=INVALID_HANDLE,bands=INVALID_HANDLE;
int macroH1=INVALID_HANDLE;
datetime lastBar=0,lastExit=0,lastAction=0,firstTick=0,lastTick=0;
ulong observedPosition=0;
double initialRisk=0;
string state="STARTING",prefix;
int journal=INVALID_HANDLE;

bool IsSessionAllowed(int hour)
{
   if(InpAllowedHours=="" || InpAllowedHours=="*")
      return V17Session(hour, InpSessionStartHour, InpSessionEndHour);
   string segs[];
   int count=StringSplit(InpAllowedHours,',',segs);
   for(int i=0;i<count;++i)
   {
      string s=segs[i];
      StringTrimLeft(s); StringTrimRight(s);
      int dash=StringFind(s,"-");
      if(dash>=0)
      {
         int h1=(int)StringToInteger(StringSubstr(s,0,dash));
         int h2=(int)StringToInteger(StringSubstr(s,dash+1));
         if(h1<=h2 && hour>=h1 && hour<=h2) return true;
         if(h1>h2 && (hour>=h1 || hour<=h2)) return true;
      }
      else if((int)StringToInteger(s)==hour) return true;
   }
   return false;
}

void Event(string kind,string details)
{
   PrintFormat("[QT17] %s | %s",kind,details);
   if(journal!=INVALID_HANDLE)
   {
      FileWrite(journal,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),kind,details);
      FileFlush(journal);
   }
}

bool ReadValue(int handle,int buffer,int shift,double &value)
{
   double values[1];
   if(CopyBuffer(handle,buffer,shift,1,values)!=1) return false;
   value=values[0];
   return value!=EMPTY_VALUE && MathIsValidNumber(value);
}

bool ReadFrame(V17Frame &f)
{
   MqlRates bars[];
   ArraySetAsSeries(bars,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,7,bars)!=7) return false;
   f.open=bars[0].open; f.high=bars[0].high; f.low=bars[0].low;
   f.close=bars[0].close; f.prevClose=bars[1].close;
   f.swingHigh=bars[1].high; f.swingLow=bars[1].low;
   for(int i=2;i<7;++i) { f.swingHigh=MathMax(f.swingHigh,bars[i].high); f.swingLow=MathMin(f.swingLow,bars[i].low); }
   return ReadValue(ema14,0,1,f.fast) && ReadValue(ema14,0,2,f.prevFast) &&
      ReadValue(ema50,0,1,f.slow) && ReadValue(atr14,0,1,f.atr) &&
      ReadValue(rsi14,0,1,f.rsi) && ReadValue(rsi14,0,2,f.prevRsi) &&
      ReadValue(htf14,0,1,f.htfFast) && ReadValue(htf14,0,2,f.htfPrevFast) &&
      ReadValue(htf50,0,1,f.htfSlow) && ReadValue(adx14,0,1,f.adx) &&
      ReadValue(bands,1,1,f.upper) && ReadValue(bands,2,1,f.lower) &&
      ReadValue(bands,0,1,f.middle);
}

bool IsOurs()
{
   return PositionGetString(POSITION_SYMBOL)==_Symbol &&
          (ulong)PositionGetInteger(POSITION_MAGIC)==MAGIC;
}

bool HasSymbolExposure()
{
   // Avoid netting/hedging interference if v16 or manual gold trades exist.
   for(int i=PositionsTotal()-1;i>=0;--i)
      if(PositionGetTicket(i)>0 && PositionGetString(POSITION_SYMBOL)==_Symbol) return true;
   for(int i=OrdersTotal()-1;i>=0;--i)
      if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==_Symbol) return true;
   return false;
}

bool RestoreHistory()
{
   if(!HistorySelect(0,TimeCurrent())) return false;
   // Attribute exits via position ID, including a manual close with magic 0.
   for(int i=HistoryDealsTotal()-1;i>=0;--i)
   {
      ulong d=HistoryDealGetTicket(i);
      if(HistoryDealGetString(d,DEAL_SYMBOL)!=_Symbol) continue;
      long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;
      ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
      bool ours=((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)==MAGIC);
      for(int j=i-1;!ours && j>=0;--j)
      {
         ulong prior=HistoryDealGetTicket(j);
         ours=((ulong)HistoryDealGetInteger(prior,DEAL_POSITION_ID)==id &&
               (ulong)HistoryDealGetInteger(prior,DEAL_MAGIC)==MAGIC);
      }
      if(ours) { lastExit=(datetime)HistoryDealGetInteger(d,DEAL_TIME); break; }
   }
   return true;
}

double OriginalRisk(ulong id,double open)
{
   string key=prefix+"R_"+(string)id;
   if(!MQLInfoInteger(MQL_TESTER) && GlobalVariableCheck(key)) return GlobalVariableGet(key);
   // Reconstruct from the original executed entry order, not the moved SL.
   if(HistorySelectByPosition(id))
      for(int i=0;i<HistoryOrdersTotal();++i)
      {
         ulong o=HistoryOrderGetTicket(i);
         if((ulong)HistoryOrderGetInteger(o,ORDER_MAGIC)!=MAGIC) continue;
         double sl=HistoryOrderGetDouble(o,ORDER_SL);
         if(sl>0) return MathAbs(open-sl);
      }
   return 0; // No reliable initial risk: leave broker stops intact, no BE.
}

void Manage(const MqlTick &tick)
{
   bool found=false;
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !IsOurs()) continue;
      found=true;
      ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      if(observedPosition!=id)
      {
         observedPosition=id;
         initialRisk=OriginalRisk(id,open);
      }
      if(!PositionSelectByTicket(ticket)) continue;
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      long type=PositionGetInteger(POSITION_TYPE);
      double sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
      if(TimeCurrent()-lastAction<2) continue;
      if(TimeCurrent()-opened>=InpMaxHoldingMinutes*60)
      {
         lastAction=TimeCurrent();
         lastExit=TimeCurrent(); // Block same-tick re-entry before the close callback arrives.
         bool ok=trade.PositionClose(ticket,InpDeviationPoints);
         Event("TIME_EXIT",StringFormat("position=%I64u ok=%d retcode=%u",id,ok,trade.ResultRetcode()));
         continue;
      }
      double profitPts=(type==POSITION_TYPE_BUY ? tick.bid-open : open-tick.ask)/_Point;
      double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      double distance=(MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
                               SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))+1)*_Point;

      // 1. Fast Breakeven Lock (+55 pts profit -> lock +10 pts)
      bool canTriggerBE = false;
      if(InpUseFastBreakeven && InpBreakevenTriggerPts>0 && profitPts>=InpBreakevenTriggerPts)
         canTriggerBE = true;
      else if(initialRisk>0 && (profitPts*_Point)>=initialRisk*InpBreakevenR)
         canTriggerBE = true;

      if(canTriggerBE)
      {
         double beTarget=V17Round(open+(type==POSITION_TYPE_BUY ? 1 : -1)*InpLockPoints*_Point,
                                 step,type==POSITION_TYPE_SELL);
         bool improve=type==POSITION_TYPE_BUY ? (beTarget>sl && tick.bid-beTarget>distance) :
                                              ((sl==0 || beTarget<sl) && beTarget-tick.ask>distance);
         if(improve && PositionSelectByTicket(ticket))
         {
            lastAction=TimeCurrent();
            bool ok=trade.PositionModify(ticket,NormalizeDouble(beTarget,_Digits),tp);
            uint code=trade.ResultRetcode();
            Event("BE_RESULT",StringFormat("position=%I64u target=%.5f profitPts=%.1f ok=%d retcode=%u",
                                          id,beTarget,profitPts,ok,code));
            // One broker request per tick. Wait for a fresh quote and position state.
            return;
         }
      }

      // 2. Micro-Trailing Engine
      if(InpUseMicroTrailing && profitPts>=InpTrailingTriggerPts)
      {
         double trailPrice = type==POSITION_TYPE_BUY ? tick.bid - InpTrailingDistancePts*_Point :
                                                       tick.ask + InpTrailingDistancePts*_Point;
         double trailTarget = V17Round(trailPrice, step, type==POSITION_TYPE_SELL);
         bool improveTrail = type==POSITION_TYPE_BUY ? (trailTarget>sl && tick.bid-trailTarget>distance) :
                                                       ((sl==0 || trailTarget<sl) && trailTarget-tick.ask>distance);
         if(improveTrail && PositionSelectByTicket(ticket))
         {
            lastAction=TimeCurrent();
            bool ok=trade.PositionModify(ticket,NormalizeDouble(trailTarget,_Digits),tp);
            Event("TRAIL_RESULT",StringFormat("position=%I64u trail=%.5f profitPts=%.1f ok=%d retcode=%u",
                                             id,trailTarget,profitPts,ok,trade.ResultRetcode()));
            return;
         }
      }
   }
   if(!found && observedPosition!=0)
   {
      // Covers event arrival order, manual closes and broker-side stop fills.
      lastExit=TimeCurrent();
      observedPosition=0; initialRisk=0;
   }
}

int OnInit()
{
   if(MQLInfoInteger(MQL_TESTER) && !V17RunSignalTests()) return INIT_FAILED;
   if(_Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")<0) return INIT_PARAMETERS_INCORRECT;
   if(!MQLInfoInteger(MQL_TESTER) && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
   { Print("QT17 research build requires a demo account."); return INIT_FAILED; }
   if(InpSetupMode<0 || InpSetupMode>3 || InpCooldownSeconds<0 || InpMaxHoldingMinutes<1 || InpStopATR<=0 ||
      InpMinStopPoints<=0 || InpMaxStopPoints<InpMinStopPoints || InpRewardRisk<=0 ||
      InpMaxSpreadPoints<=0 || InpMinTargetPoints<=0 || InpMaxSpreadTargetFraction<=0 ||
      InpMaxSpreadTargetFraction>=1 || InpBreakevenR<=0 || InpLockPoints<0 ||
      InpStopMode<V17_STOP_FIXED || InpStopMode>V17_STOP_HYBRID ||
      InpFixedTargetPoints<0 || InpFixedStopPoints<0 ||
      (InpStopMode!=V17_STOP_STRUCTURAL && InpFixedStopPoints<=0) || InpBreakevenTriggerPts<0 ||
      InpTrailingTriggerPts<0 || InpTrailingDistancePts<0 ||
      InpSessionStartHour<0 || InpSessionStartHour>23 || InpSessionEndHour<0 || InpSessionEndHour>23)
      return INIT_PARAMETERS_INCORRECT;
   double minlot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxlot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double volstep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(volstep<=0 || LOT<minlot || LOT>maxlot || MathAbs(LOT/volstep-MathRound(LOT/volstep))>1e-6 ||
      SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE)<=0) return INIT_FAILED;
   prefix=StringFormat("QT17_%I64d_%s_",AccountInfoInteger(ACCOUNT_LOGIN),_Symbol);
   trade.SetExpertMagicNumber(MAGIC);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetAsyncMode(false);
   if(!trade.SetTypeFillingBySymbol(_Symbol)) return INIT_FAILED;
   ema14=iMA(_Symbol,PERIOD_M1,14,0,MODE_EMA,PRICE_CLOSE);
   ema50=iMA(_Symbol,PERIOD_M1,50,0,MODE_EMA,PRICE_CLOSE);
   atr14=iATR(_Symbol,PERIOD_M1,14); rsi14=iRSI(_Symbol,PERIOD_M1,14,PRICE_CLOSE);
   htf14=iMA(_Symbol,PERIOD_M5,14,0,MODE_EMA,PRICE_CLOSE);
   htf50=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE);
   adx14=iADX(_Symbol,PERIOD_M5,14); bands=iBands(_Symbol,PERIOD_M1,20,0,2.0,PRICE_CLOSE);
   if(InpUseMacroFilter)
   {
      macroH1=iMA(_Symbol,PERIOD_H1,InpMacroPeriod,0,MODE_EMA,PRICE_CLOSE);
      if(macroH1<0) return INIT_FAILED;
   }
   if(ema14<0 || ema50<0 || atr14<0 || rsi14<0 || htf14<0 || htf50<0 || adx14<0 || bands<0)
      return INIT_FAILED;
   if(!RestoreHistory()) return INIT_FAILED;
   lastBar=iTime(_Symbol,PERIOD_M1,0); // Restart does not reuse an already-open bar.
   if(InpWriteJournal)
   {
      journal=FileOpen("QT17_events.tsv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_SHARE_READ|FILE_ANSI,'\t',CP_UTF8);
      if(journal!=INVALID_HANDLE) FileSeek(journal,0,SEEK_END);
   }
   Event("INIT",StringFormat("v17.10 magic=%I64u lot=%.2f setup=%d stopMode=%d allowedHours=%s; target=UNVERIFIED; no RiskGuardian",
                            MAGIC,LOT,InpSetupMode,InpStopMode,InpAllowedHours));
   return INIT_SUCCEEDED;
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=tick.bid || tick.bid<=0) return;
   if(firstTick==0) firstTick=TimeCurrent();
   lastTick=TimeCurrent();
   Manage(tick);
   Comment("QuantumTitan v17 | DEMO RESEARCH | target 80% UNVERIFIED\n",state,
           "\nLot 0.01 | magic 991701 | one gold position | no RiskGuardian");
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   if(bar<=0 || bar==lastBar) return;
   V17Frame f={};
   if(!ReadFrame(f)) { state="WAIT_DATA"; return; }
   lastBar=bar;
   MqlDateTime now; TimeToStruct(TimeCurrent(),now);
   string reason;
   int signal=V17Signal(f,reason,InpSetupMode);
   state=reason;
   if(!IsSessionAllowed(now.hour)) state="OUTSIDE_SESSION";
   else if(HasSymbolExposure()) state="EXISTING_GOLD_EXPOSURE";
   else if(TimeCurrent()-lastExit<InpCooldownSeconds) state="POST_EXIT_COOLDOWN";
   else if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
           !AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) state="TRADING_NOT_ALLOWED";
   else if((tick.ask-tick.bid)/_Point>InpMaxSpreadPoints) state="SPREAD_TOO_WIDE";
   else if(InpUseMacroFilter)
   {
      double h1=0;
      if(macroH1==INVALID_HANDLE || !ReadValue(macroH1,0,1,h1)) state="MACRO_DATA_NOT_READY";
      else if(signal>0 && f.close<h1) state="AGAINST_H1_TREND";
      else if(signal<0 && f.close>h1) state="AGAINST_H1_TREND";
   }
   Event("BAR",StringFormat("bar=%s state=%s signal=%d close=%.5f fast=%.5f slow=%.5f atr=%.5f rsi=%.2f adxM5=%.2f spread=%.1f",
                           TimeToString(bar),state,signal,f.close,f.fast,f.slow,f.atr,f.rsi,f.adx,(tick.ask-tick.bid)/_Point));
   if(state!=reason || signal==0) return;
   double entry=signal>0 ? tick.ask : tick.bid;
   if(MathAbs((signal>0 ? tick.bid : tick.ask)-f.close)>0.3*f.atr)
   { state="ENTRY_MOVED"; Event("SKIP",state); return; }
   double atrDistance=MathMax(InpMinStopPoints*_Point,InpStopATR*f.atr);
   double structuralDistance=(signal>0 ? entry-f.low : f.high-entry)+0.15*f.atr;
   double dist=0;
   if(!V17SelectStopDistance(InpStopMode,InpFixedStopPoints*_Point,atrDistance,
                             structuralDistance,InpMaxStopPoints*_Point,dist))
   { Event("SKIP","STOP_RULE_REJECTED"); return; }

   double target = InpFixedTargetPoints > 0 ? InpFixedTargetPoints * _Point : MathMax(InpMinTargetPoints * _Point, dist * InpRewardRisk);
   if(StringFind(reason,"RANGE_")==0)
   {
      double room=signal>0 ? f.middle-entry : entry-f.middle;
      target=MathMin(target,room);
      if(target<InpMinTargetPoints*_Point) { Event("SKIP","INSUFFICIENT_RANGE_ROOM"); return; }
   }
   if(tick.ask-tick.bid>target*InpMaxSpreadTargetFraction) { Event("SKIP","SPREAD_TARGET_RATIO"); return; }
   double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double sl=NormalizeDouble(V17Round(entry-signal*dist,step,signal<0),_Digits);
   double tp=NormalizeDouble(V17Round(entry+signal*target,step,signal>0),_Digits);
   double stopLevel=(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)+1)*_Point;
   if((signal>0 && (tick.bid-sl<stopLevel || tp-tick.bid<stopLevel)) ||
      (signal<0 && (sl-tick.ask<stopLevel || tick.ask-tp<stopLevel)))
   { Event("SKIP","BROKER_STOP_DISTANCE"); return; }
   double margin;
   if(!OrderCalcMargin(signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,LOT,entry,margin) ||
      margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)) { Event("SKIP","INSUFFICIENT_MARGIN"); return; }
   // A rejected request is not a win, nor an executed trade. Retry only next bar.
   bool sent=signal>0 ? trade.Buy(LOT,_Symbol,entry,sl,tp,"QT17_TP_BUY") :
                       trade.Sell(LOT,_Symbol,entry,sl,tp,"QT17_TP_SELL");
   uint code=trade.ResultRetcode();
   Event("ENTRY_RESULT",StringFormat("setup=%s requested=%.5f fill=%.5f sl=%.5f tp=%.5f ok=%d retcode=%u deal=%I64u",
                                    reason,entry,trade.ResultPrice(),sl,tp,sent,code,trade.ResultDeal()));
   if(sent && (code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL))
   {
      for(int i=PositionsTotal()-1;i>=0;--i)
         if(PositionGetTicket(i)>0 && IsOurs())
         {
            observedPosition=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
            initialRisk=MathAbs(PositionGetDouble(POSITION_PRICE_OPEN)-sl);
            if(!MQLInfoInteger(MQL_TESTER)) GlobalVariableSet(prefix+"R_"+(string)observedPosition,initialRisk);
         }
   }
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) return;
   ulong id=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
   if(!HistorySelectByPosition(id)) return;
   bool ours=false;
   double net=0;
   for(int i=0;i<HistoryDealsTotal();++i)
   {
      ulong d=HistoryDealGetTicket(i);
      if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)==MAGIC) ours=true;
      net+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+
           HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
   }
   if(!ours) return;
   lastExit=TimeCurrent();
   bool remains=false;
   for(int i=PositionsTotal()-1;i>=0;--i)
      if(PositionGetTicket(i)>0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER)==id) remains=true;
   Event(remains ? "PARTIAL_EXIT" : "CLOSED",StringFormat("position=%I64u cumulative_net=%.2f deal=%I64u",id,net,trans.deal));
   if(!remains && !MQLInfoInteger(MQL_TESTER)) GlobalVariableDel(prefix+"R_"+(string)id);
}

double OnTester()
{
   double trades=TesterStatistics(STAT_TRADES),wins=TesterStatistics(STAT_PROFIT_TRADES);
   double wr=trades>0 ? 100*wins/trades : 0;
   double pf=TesterStatistics(STAT_PROFIT_FACTOR),net=TesterStatistics(STAT_PROFIT);
   Event("TEST_SUMMARY",StringFormat("trades=%.0f wins=%.0f winrate=%.2f net=%.2f PF=%.3f equityDD=%.2f%%; overnight target requires per-session review",
                                    trades,wins,wr,net,pf,TesterStatistics(STAT_EQUITY_DDREL_PERCENT)));
   return net;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(ema14); IndicatorRelease(ema50); IndicatorRelease(atr14); IndicatorRelease(rsi14);
   IndicatorRelease(htf14); IndicatorRelease(htf50); IndicatorRelease(adx14); IndicatorRelease(bands);
   if(macroH1!=INVALID_HANDLE) IndicatorRelease(macroH1);
   Event("DEINIT",StringFormat("reason=%d",reason));
   if(journal!=INVALID_HANDLE) FileClose(journal);
   Comment("");
}
