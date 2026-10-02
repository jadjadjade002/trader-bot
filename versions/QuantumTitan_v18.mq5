#property strict
#property version "18.02"
#property description "XAUUSD M1 bounded sweep-reclaim research candidate. Fixed 0.01 lot."
#include <Trade/Trade.mqh>
#include "Include/QuantumTitan/V18Signal.mqh"
#include "tests/V18SignalTests.mqh"

input group "Execution"
input double InpMaxSpreadPoints=40.0;
input int InpCooldownSeconds=60;
input int InpMaxHoldingMinutes=8;
input int InpDeviationPoints=20;
input group "Sweep reclaim hypothesis"
input double InpStopATR=1.2;
input double InpStopBufferATR=0.15;
input double InpMaxStopPoints=450.0;
input double InpRewardRisk=0.75;
input double InpMinTargetPoints=100.0;
input double InpMaxSpreadTargetFraction=0.25;
input double InpBreakevenR=0.70;
input double InpLockPoints=10.0;
input group "Broker time session"
input int InpSessionStartHour=18;
input int InpSessionEndHour=2;
input bool InpWriteJournal=true;

const ulong MAGIC=991801;
const double LOT=0.01;
CTrade trade;
int ema14=-1,atr14=-1,rsi14=-1,htf14=-1,htf50=-1,adx14=-1;
datetime lastBar=0,lastExit=0,lastAction=0;
ulong positionId=0;
double initialRisk=0;
int journal=-1;

bool RestoreHistory()
{
   if(!HistorySelect(0,TimeCurrent())) return false;
   for(int i=HistoryDealsTotal()-1;i>=0;--i)
   {
      ulong d=HistoryDealGetTicket(i); if(HistoryDealGetString(d,DEAL_SYMBOL)!=_Symbol) continue;
      if(HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_OUT && HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_OUT_BY) continue;
      ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
      for(int j=i-1;j>=0;--j)
      {
         ulong prior=HistoryDealGetTicket(j);
         if((ulong)HistoryDealGetInteger(prior,DEAL_POSITION_ID)==id && (ulong)HistoryDealGetInteger(prior,DEAL_MAGIC)==MAGIC)
         { lastExit=(datetime)HistoryDealGetInteger(d,DEAL_TIME); return true; }
      }
   }
   return true;
}
double OriginalRisk(ulong id,double open)
{
   if(!HistorySelectByPosition(id)) return 0;
   for(int i=0;i<HistoryOrdersTotal();++i)
   {
      ulong order=HistoryOrderGetTicket(i);
      if((ulong)HistoryOrderGetInteger(order,ORDER_MAGIC)!=MAGIC) continue;
      double sl=HistoryOrderGetDouble(order,ORDER_SL); if(sl>0) return MathAbs(open-sl);
   }
   return 0;
}

void Event(string kind,string detail)
{
   PrintFormat("[QT18] %s | %s",kind,detail);
   if(journal!=INVALID_HANDLE) { FileWrite(journal,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),kind,detail); FileFlush(journal); }
}
bool ReadValue(int handle,int buffer,int shift,double &value)
{
   double a[1]; if(handle<0 || CopyBuffer(handle,buffer,shift,1,a)!=1) return false;
   value=a[0]; return MathIsValidNumber(value) && value!=EMPTY_VALUE;
}
bool InSession(int hour)
{
   if(InpSessionStartHour==InpSessionEndHour) return true;
   return InpSessionStartHour<InpSessionEndHour ? hour>=InpSessionStartHour && hour<InpSessionEndHour : hour>=InpSessionStartHour || hour<InpSessionEndHour;
}
bool Exposure()
{
   for(int i=PositionsTotal()-1;i>=0;--i) if(PositionGetTicket(i)>0 && PositionGetString(POSITION_SYMBOL)==_Symbol) return true;
   for(int i=OrdersTotal()-1;i>=0;--i) if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==_Symbol) return true;
   return false;
}
bool ReadFrame(V18Frame &f)
{
   MqlRates b[]; ArraySetAsSeries(b,true); if(CopyRates(_Symbol,PERIOD_M1,1,8,b)!=8) return false;
   f.open=b[0].open; f.high=b[0].high; f.low=b[0].low; f.close=b[0].close; f.prevClose=b[1].close;
   f.swingHigh=b[1].high; f.swingLow=b[1].low;
   for(int i=2;i<8;++i) { f.swingHigh=MathMax(f.swingHigh,b[i].high); f.swingLow=MathMin(f.swingLow,b[i].low); }
   return ReadValue(atr14,0,1,f.atr) && ReadValue(rsi14,0,1,f.rsi) && ReadValue(rsi14,0,2,f.prevRsi) &&
      ReadValue(ema14,0,1,f.fast) && ReadValue(htf14,0,1,f.htfFast) && ReadValue(htf50,0,1,f.htfSlow) && ReadValue(adx14,0,1,f.adx);
}
bool IsOurs()
{
   return PositionGetString(POSITION_SYMBOL)==_Symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MAGIC;
}
void Manage(const MqlTick &tick)
{
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong ticket=PositionGetTicket(i); if(ticket==0 || !IsOurs()) continue;
      ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER); double open=PositionGetDouble(POSITION_PRICE_OPEN);
      long type=PositionGetInteger(POSITION_TYPE); double sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
      if(positionId!=id) { positionId=id; initialRisk=0.0; }
      if(initialRisk<=0.0)
      {
         initialRisk=OriginalRisk(id,open);
      }
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      if(TimeCurrent()-lastAction<2) return;
      if(TimeCurrent()-opened>=InpMaxHoldingMinutes*60)
      {
         lastAction=TimeCurrent(); lastExit=TimeCurrent(); bool ok=trade.PositionClose(ticket,InpDeviationPoints);
         Event("TIME_EXIT",StringFormat("id=%I64u ok=%d retcode=%u",id,ok,trade.ResultRetcode())); return;
      }
      double profit=type==POSITION_TYPE_BUY ? tick.bid-open : open-tick.ask;
      if(initialRisk<=0 || profit<initialRisk*InpBreakevenR) return;
      if((type==POSITION_TYPE_BUY && tp>0.0 && tick.bid>=tp) || (type==POSITION_TYPE_SELL && tp>0.0 && tick.ask<=tp)) return;
      double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(!MathIsValidNumber(step) || step<=0.0) { Event("MANAGE_SKIP","INVALID_TICK_SIZE"); return; }
      double gap=(MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))+1)*_Point;
      double target=type==POSITION_TYPE_BUY ? V18Round(open+InpLockPoints*_Point,step,true) : V18Round(open-InpLockPoints*_Point,step,false);
      if(target<=0.0) { Event("MANAGE_SKIP","INVALID_ROUNDED_PRICE"); return; }
      bool improve=type==POSITION_TYPE_BUY ? target>sl && tick.bid-target>gap : (sl==0 || target<sl) && target-tick.ask>gap;
      if(!improve) return;
      lastAction=TimeCurrent(); bool ok=trade.PositionModify(ticket,NormalizeDouble(target,_Digits),tp);
      Event("BE_RESULT",StringFormat("id=%I64u ok=%d retcode=%u",id,ok,trade.ResultRetcode())); return;
   }
}
int OnInit()
{
   if(MQLInfoInteger(MQL_TESTER) && !V18RunSignalTests()) return INIT_FAILED;
   if(_Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")<0) return INIT_PARAMETERS_INCORRECT;
   if(!MQLInfoInteger(MQL_TESTER) && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) return INIT_FAILED;
   if(InpMaxSpreadPoints<=0 || InpCooldownSeconds<0 || InpMaxHoldingMinutes<1 || InpStopATR<=0 || InpStopBufferATR<0 ||
      InpMaxStopPoints<=0 || InpRewardRisk<=0 || InpMinTargetPoints<=0 || InpMaxSpreadTargetFraction<=0 || InpMaxSpreadTargetFraction>=1 ||
      InpBreakevenR<=0 || InpSessionStartHour<0 || InpSessionStartHour>23 || InpSessionEndHour<0 || InpSessionEndHour>23) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(MAGIC); trade.SetDeviationInPoints(InpDeviationPoints); trade.SetAsyncMode(false); if(!trade.SetTypeFillingBySymbol(_Symbol)) return INIT_FAILED;
   ema14=iMA(_Symbol,PERIOD_M1,14,0,MODE_EMA,PRICE_CLOSE); atr14=iATR(_Symbol,PERIOD_M1,14); rsi14=iRSI(_Symbol,PERIOD_M1,14,PRICE_CLOSE);
   htf14=iMA(_Symbol,PERIOD_M5,14,0,MODE_EMA,PRICE_CLOSE); htf50=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE); adx14=iADX(_Symbol,PERIOD_M5,14);
   if(ema14<0 || atr14<0 || rsi14<0 || htf14<0 || htf50<0 || adx14<0) return INIT_FAILED;
   if(!RestoreHistory()) return INIT_FAILED;
   lastBar=iTime(_Symbol,PERIOD_M1,0);
   if(InpWriteJournal) { journal=FileOpen("QT18_events.tsv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_SHARE_READ|FILE_ANSI,'\t',CP_UTF8); if(journal!=INVALID_HANDLE) FileSeek(journal,0,SEEK_END); }
   Event("INIT",StringFormat("v18.02 magic=%I64u lot=%.2f session=%02d-%02d hypothesis=sweep-reclaim risk=none",MAGIC,LOT,InpSessionStartHour,InpSessionEndHour));
   return INIT_SUCCEEDED;
}
void OnTick()
{
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=tick.bid || tick.bid<=0) return;
   Manage(tick); datetime bar=iTime(_Symbol,PERIOD_M1,0); if(bar<=0 || bar==lastBar) return;
   V18Frame f={}; if(!ReadFrame(f)) return; lastBar=bar; string reason; int signal=V18Signal(f,reason);
   MqlDateTime now; TimeToStruct(TimeCurrent(),now); string state=reason;
   if(!InSession(now.hour)) state="OUTSIDE_SESSION"; else if(Exposure()) state="EXISTING_GOLD_EXPOSURE"; else if(TimeCurrent()-lastExit<InpCooldownSeconds) state="POST_EXIT_COOLDOWN";
   else if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) state="TRADING_NOT_ALLOWED";
   else if((tick.ask-tick.bid)/_Point>InpMaxSpreadPoints) state="SPREAD_TOO_WIDE";
   Event("BAR",StringFormat("bar=%s state=%s signal=%d atr=%.5f rsi=%.2f adx=%.2f spread=%.1f",TimeToString(bar),state,signal,f.atr,f.rsi,f.adx,(tick.ask-tick.bid)/_Point));
   if(state!=reason || signal==0) return;
   double entry=signal>0 ? tick.ask : tick.bid; double dist=(signal>0 ? entry-f.low : f.high-entry)+InpStopBufferATR*f.atr;
   dist=MathMax(dist,InpStopATR*f.atr); if(dist>InpMaxStopPoints*_Point) { Event("SKIP","STOP_TOO_LARGE"); return; }
   double target=MathMax(InpMinTargetPoints*_Point,dist*InpRewardRisk); if(tick.ask-tick.bid>target*InpMaxSpreadTargetFraction) { Event("SKIP","SPREAD_TARGET_RATIO"); return; }
   double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(step) || step<=0.0) { Event("SKIP","INVALID_TICK_SIZE"); return; }
   double sl=NormalizeDouble(V18Round(entry-signal*dist,step,signal<0),_Digits); double tp=NormalizeDouble(V18Round(entry+signal*target,step,signal>0),_Digits);
   if(sl<=0.0 || tp<=0.0) { Event("SKIP","INVALID_ROUNDED_PRICE"); return; }
   double stopLevel=(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)+1)*_Point;
   if((signal>0 && (tick.bid-sl<stopLevel || tp-tick.bid<stopLevel)) || (signal<0 && (sl-tick.ask<stopLevel || tick.ask-tp<stopLevel))) { Event("SKIP","BROKER_STOP_DISTANCE"); return; }
   double margin; if(!OrderCalcMargin(signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,LOT,entry,margin) || margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)) { Event("SKIP","INSUFFICIENT_MARGIN"); return; }
   bool sent=signal>0 ? trade.Buy(LOT,_Symbol,entry,sl,tp,"QT18_BUY") : trade.Sell(LOT,_Symbol,entry,sl,tp,"QT18_SELL"); uint code=trade.ResultRetcode();
   Event("ENTRY_RESULT",StringFormat("reason=%s requested=%.5f fill=%.5f sl=%.5f tp=%.5f ok=%d retcode=%u deal=%I64u",reason,entry,trade.ResultPrice(),sl,tp,sent,code,trade.ResultDeal()));
   if(sent && (code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)) for(int i=PositionsTotal()-1;i>=0;--i) if(PositionGetTicket(i)>0 && IsOurs()) { positionId=(ulong)PositionGetInteger(POSITION_IDENTIFIER); initialRisk=MathAbs(PositionGetDouble(POSITION_PRICE_OPEN)-sl); }
}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return; long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY); if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) return;
   ulong id=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID); if(positionId==id) lastExit=TimeCurrent(); Event("CLOSED",StringFormat("id=%I64u profit=%.2f commission=%.2f swap=%.2f fee=%.2f",id,HistoryDealGetDouble(trans.deal,DEAL_PROFIT),HistoryDealGetDouble(trans.deal,DEAL_COMMISSION),HistoryDealGetDouble(trans.deal,DEAL_SWAP),HistoryDealGetDouble(trans.deal,DEAL_FEE)));
}
double OnTester()
{
   double t=TesterStatistics(STAT_TRADES),w=TesterStatistics(STAT_PROFIT_TRADES); Event("TEST_SUMMARY",StringFormat("trades=%.0f wins=%.0f winrate=%.2f net=%.2f PF=%.3f equityDD=%.2f%%",t,w,t>0?100*w/t:0,TesterStatistics(STAT_PROFIT),TesterStatistics(STAT_PROFIT_FACTOR),TesterStatistics(STAT_EQUITY_DDREL_PERCENT))); return TesterStatistics(STAT_PROFIT);
}
void OnDeinit(const int reason)
{
   IndicatorRelease(ema14); IndicatorRelease(atr14); IndicatorRelease(rsi14); IndicatorRelease(htf14); IndicatorRelease(htf50); IndicatorRelease(adx14); Event("DEINIT",StringFormat("reason=%d",reason)); if(journal!=INVALID_HANDLE) FileClose(journal); Comment("");
}
