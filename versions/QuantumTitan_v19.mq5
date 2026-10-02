#property strict
#property version "19.00"
#property description "XAUUSD M1 closed-bar breakout research candidate. Fixed 0.01 lot."

#include <Trade/Trade.mqh>
#include "Include/QuantumTitan/V19Signal.mqh"
#include "tests/V19SignalTests.mqh"

input group "Execution"
input double InpMaxSpreadPoints=40.0;
input int InpCooldownSeconds=60;
input int InpMaxHoldingMinutes=3;
input int InpDeviationPoints=20;
input int InpSignalExpirySeconds=10;
input group "Breakout hypothesis"
input double InpStopATR=1.0;
input double InpTargetATR=1.0;
input double InpMaxStopPoints=450.0;
input double InpMaxSpreadTargetFraction=0.20;
input group "Broker time session"
input int InpSessionStartHour=18;
input int InpSessionEndHour=2;
input int InpEntryCutoffHour=1;
input int InpEntryCutoffMinute=57;
input bool InpWriteJournal=true;

const ulong MAGIC=991901;
const double LOT=0.01;
CTrade trade;
int atr14=INVALID_HANDLE;
datetime lastBar=0,lastExit=0,lastAction=0,candidateBar=0;
int candidateSignal=0;
double candidateAtr=0.0;
string candidateReason="NO_BREAKOUT";
int journal=INVALID_HANDLE;
string entryMutexName="";
double entryMutexToken=0.0;
bool entryMutexHeld=false;

void Event(string kind,string detail)
{
   PrintFormat("[QT19] %s | %s",kind,detail);
   if(journal!=INVALID_HANDLE) { FileWrite(journal,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),kind,detail); FileFlush(journal); }
}

bool AcceptedRetcode(uint code)
{
   return code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL;
}

bool CanonicalXauSymbol(string symbol)
{
   StringToUpper(symbol);
   return StringFind(symbol,"XAUUSD")>=0;
}

bool PositionOpenedByUs(ulong positionId)
{
   if(positionId==0 || !HistorySelectByPosition(positionId)) return false;
   for(int i=0;i<HistoryDealsTotal();++i)
   {
      ulong ticket=HistoryDealGetTicket(i); if(ticket==0) continue;
      long entry=HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT)
         return (ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)==MAGIC;
   }
   return false;
}

bool RestoreCooldown()
{
   datetime selectedTo=TimeCurrent();
   if(!HistorySelect(0,selectedTo)) return false;
   for(int i=HistoryDealsTotal()-1;i>=0;--i)
   {
      ulong deal=HistoryDealGetTicket(i); if(deal==0) continue;
      if(!CanonicalXauSymbol(HistoryDealGetString(deal,DEAL_SYMBOL))) continue;
      long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;
      ulong positionId=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      datetime closedAt=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);
      if(PositionOpenedByUs(positionId)) { lastExit=closedAt; return true; }
      if(!HistorySelect(0,selectedTo)) return false;
   }
   return true;
}

bool ReadAtr(int shift,double &value)
{
   double values[1];
   if(atr14==INVALID_HANDLE || CopyBuffer(atr14,0,shift,1,values)!=1) return false;
   value=values[0]; return MathIsValidNumber(value) && value!=EMPTY_VALUE && value>0.0;
}

bool ReadFrame(V19Frame &f)
{
   MqlRates bars[]; ArraySetAsSeries(bars,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,4,bars)!=4) return false;
   f.close1=bars[0].close; f.high1=bars[0].high; f.low1=bars[0].low;
   f.high2=bars[1].high; f.low2=bars[1].low; f.high3=bars[2].high; f.low3=bars[2].low;
   f.high4=bars[3].high; f.low4=bars[3].low;
   return ReadAtr(1,f.atr);
}

bool IsOwnSelectedPosition()
{
   return PositionGetString(POSITION_SYMBOL)==_Symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MAGIC;
}

bool GoldExposure()
{
   for(int i=PositionsTotal()-1;i>=0;--i)
      if(PositionGetTicket(i)>0 && CanonicalXauSymbol(PositionGetString(POSITION_SYMBOL))) return true;
   for(int i=OrdersTotal()-1;i>=0;--i)
      if(OrderGetTicket(i)>0 && CanonicalXauSymbol(OrderGetString(ORDER_SYMBOL))) return true;
   return false;
}

bool InEntrySession(const MqlDateTime &now)
{
   return V19InEntryWindow(now.hour,now.min,InpSessionStartHour,InpSessionEndHour,InpEntryCutoffHour,InpEntryCutoffMinute);
}

bool AtOrAfterSessionEnd(const MqlDateTime &now)
{
   if(InpSessionStartHour>InpSessionEndHour) return now.hour>=InpSessionEndHour && now.hour<InpSessionStartHour;
   return now.hour>=InpSessionEndHour;
}

bool ValidVolume()
{
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(!MathIsValidNumber(minimum) || !MathIsValidNumber(maximum) || !MathIsValidNumber(step) || step<=0.0 || LOT<minimum || LOT>maximum) return false;
   double units=(LOT-minimum)/step;
   return MathAbs(units-MathRound(units))<1e-8;
}

ENUM_ORDER_TYPE_FILLING RequestFilling()
{
   long modes=SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((modes & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if((modes & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

bool AcquireEntryMutex()
{
   if(entryMutexHeld) return true;
   if(!GlobalVariableCheck(entryMutexName) && !GlobalVariableTemp(entryMutexName)) return false;
   entryMutexToken=(double)GetTickCount64()+((double)(ChartID()%1000000))/1000000.0;
   if(entryMutexToken==0.0) entryMutexToken=1.0;
   entryMutexHeld=GlobalVariableSetOnCondition(entryMutexName,entryMutexToken,0.0);
   return entryMutexHeld;
}

void ReleaseEntryMutex()
{
   if(!entryMutexHeld) return;
   GlobalVariableSetOnCondition(entryMutexName,0.0,entryMutexToken);
   entryMutexHeld=false; entryMutexToken=0.0;
}

bool CloseOwn(ulong ticket,string reason)
{
   if(TimeCurrent()-lastAction<2) return false;
   lastAction=TimeCurrent();
   bool sent=trade.PositionClose(ticket,InpDeviationPoints); uint code=trade.ResultRetcode(); bool accepted=sent && AcceptedRetcode(code);
   Event(reason,StringFormat("ticket=%I64u ok=%d retcode=%u",ticket,accepted,code));
   if(accepted) lastExit=TimeCurrent();
   return accepted;
}

void Manage()
{
   MqlDateTime now; TimeToStruct(TimeCurrent(),now);
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong ticket=PositionGetTicket(i); if(ticket==0 || !IsOwnSelectedPosition()) continue;
      double sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
      if(sl<=0.0 || tp<=0.0) { Event("SAFETY_VIOLATION","own position is unprotected"); CloseOwn(ticket,"UNPROTECTED_EXIT"); return; }
      if(AtOrAfterSessionEnd(now)) { CloseOwn(ticket,"SESSION_EXIT"); return; }
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      if(opened>0 && TimeCurrent()-opened>=InpMaxHoldingMinutes*60) { CloseOwn(ticket,"TIME_EXIT"); return; }
   }
}

bool EntryChecks(const MqlTick &tick,const MqlDateTime &now,string &state)
{
   if(!InEntrySession(now)) { state="OUTSIDE_ENTRY_SESSION"; return false; }
   if(GoldExposure()) { state="EXISTING_GOLD_EXPOSURE"; return false; }
   if(TimeCurrent()-lastExit<InpCooldownSeconds) { state="POST_EXIT_COOLDOWN"; return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) { state="TRADING_NOT_ALLOWED"; return false; }
   if((tick.ask-tick.bid)/_Point>InpMaxSpreadPoints) { state="SPREAD_TOO_WIDE"; return false; }
   if(!ValidVolume()) { state="INVALID_VOLUME"; return false; }
   state="ELIGIBLE"; return true;
}

void TryEntry(const MqlTick &tick)
{
   if(candidateSignal==0 || candidateBar<=0) return;
   long age=TimeCurrent()-candidateBar;
   if(!V19SignalAlive(age,InpSignalExpirySeconds)) { Event("SIGNAL_EXPIRED",StringFormat("bar=%s age=%I64d",TimeToString(candidateBar),age)); candidateSignal=0; return; }
   MqlDateTime now; TimeToStruct(TimeCurrent(),now); string state;
   if(!EntryChecks(tick,now,state)) return;
   int signal=candidateSignal; double frozenAtr=candidateAtr; string reason=candidateReason;
   double stopDistance=InpStopATR*frozenAtr,targetDistance=InpTargetATR*frozenAtr;
   if(!MathIsValidNumber(stopDistance) || !MathIsValidNumber(targetDistance) || stopDistance<=0.0 || targetDistance<=0.0) { Event("SKIP","INVALID_FROZEN_ATR"); return; }
   if(stopDistance>InpMaxStopPoints*_Point) { Event("SKIP","STOP_TOO_LARGE"); return; }
   double spread=tick.ask-tick.bid;
   if(spread>targetDistance*InpMaxSpreadTargetFraction) { Event("SKIP","SPREAD_TARGET_RATIO"); return; }
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(tickSize) || tickSize<=0.0) { Event("SKIP","INVALID_TICK_SIZE"); return; }
   double entry=signal>0 ? tick.ask : tick.bid;
   double sl=NormalizeDouble(V19Round(entry-signal*stopDistance,tickSize,signal<0),_Digits);
   double tp=NormalizeDouble(V19Round(entry+signal*targetDistance,tickSize,signal>0),_Digits);
   if(sl<=0.0 || tp<=0.0) { Event("SKIP","INVALID_ROUNDED_PRICE"); return; }
   if(MathAbs(entry-sl)>InpMaxStopPoints*_Point) { Event("SKIP","ROUNDED_STOP_TOO_LARGE"); return; }
   double minimumDistance=(MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))+1)*_Point;
   if((signal>0 && (tick.bid-sl<minimumDistance || tp-tick.bid<minimumDistance)) ||
      (signal<0 && (sl-tick.ask<minimumDistance || tick.ask-tp<minimumDistance))) { Event("SKIP","BROKER_STOP_DISTANCE"); return; }
   double margin=0.0;
   ENUM_ORDER_TYPE orderType=signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(orderType,_Symbol,LOT,entry,margin) || margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)) { Event("SKIP","INSUFFICIENT_MARGIN"); return; }
   if(!AcquireEntryMutex()) { Event("SKIP","XAU_ENTRY_MUTEX_BUSY"); return; }
   if(GoldExposure()) { ReleaseEntryMutex(); Event("SKIP","EXISTING_GOLD_EXPOSURE_RECHECK"); return; }
   MqlTradeRequest request={}; MqlTradeCheckResult check={};
   request.action=TRADE_ACTION_DEAL; request.magic=MAGIC; request.symbol=_Symbol; request.volume=LOT; request.type=orderType;
   request.price=entry; request.sl=sl; request.tp=tp; request.deviation=InpDeviationPoints; request.type_filling=RequestFilling();
   if(!OrderCheck(request,check) || !V19OrderCheckAccepted(check.retcode)) { ReleaseEntryMutex(); Event("SKIP",StringFormat("ORDER_CHECK_FAILED retcode=%u comment=%s",check.retcode,check.comment)); return; }
   candidateSignal=0;
   bool sent=signal>0 ? trade.Buy(LOT,_Symbol,entry,sl,tp,"QT19_BUY") : trade.Sell(LOT,_Symbol,entry,sl,tp,"QT19_SELL");
   uint code=trade.ResultRetcode(); bool accepted=sent && AcceptedRetcode(code);
   ReleaseEntryMutex();
   Event("ENTRY_RESULT",StringFormat("reason=%s requested=%.5f fill=%.5f sl=%.5f tp=%.5f ok=%d retcode=%u deal=%I64u",reason,entry,trade.ResultPrice(),sl,tp,accepted,code,trade.ResultDeal()));
}

int OnInit()
{
   if(MQLInfoInteger(MQL_TESTER) && !V19RunSignalTests()) return INIT_FAILED;
   if(_Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")<0) return INIT_PARAMETERS_INCORRECT;
   if(!MQLInfoInteger(MQL_TESTER) && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) return INIT_FAILED;
   if(InpMaxSpreadPoints<=0.0 || InpCooldownSeconds<0 || InpMaxHoldingMinutes!=3 || InpDeviationPoints<0 || InpSignalExpirySeconds!=10 ||
      InpStopATR!=1.0 || InpTargetATR!=1.0 || InpMaxStopPoints!=450.0 || InpMaxSpreadTargetFraction!=0.20 ||
      InpSessionStartHour!=18 || InpSessionEndHour!=2 || InpEntryCutoffHour!=1 || InpEntryCutoffMinute!=57) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(MAGIC); trade.SetDeviationInPoints(InpDeviationPoints); trade.SetAsyncMode(false);
   if(!trade.SetTypeFillingBySymbol(_Symbol) || !ValidVolume()) return INIT_FAILED;
   entryMutexName=StringFormat("QT_XAU_ENTRY_%I64d",AccountInfoInteger(ACCOUNT_LOGIN));
   atr14=iATR(_Symbol,PERIOD_M1,14); if(atr14==INVALID_HANDLE) return INIT_FAILED;
   if(!RestoreCooldown()) return INIT_FAILED;
   lastBar=iTime(_Symbol,PERIOD_M1,0);
   if(InpWriteJournal) { journal=FileOpen("QT19_events.tsv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_SHARE_READ|FILE_ANSI,'\t',CP_UTF8); if(journal!=INVALID_HANDLE) FileSeek(journal,0,SEEK_END); }
   Event("INIT",StringFormat("v19.00 magic=%I64u lot=%.2f session=18-02 cutoff=01:57 hypothesis=closed-bar-breakout",MAGIC,LOT));
   return INIT_SUCCEEDED;
}

void OnTick()
{
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=tick.bid || tick.bid<=0.0) return;
   Manage();
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   if(bar>0 && bar!=lastBar)
   {
      if(candidateBar!=bar) { candidateBar=bar; candidateSignal=0; candidateAtr=0.0; candidateReason="NO_BREAKOUT"; }
      long age=TimeCurrent()-candidateBar;
      if(V19SignalAlive(age,InpSignalExpirySeconds))
      {
         V19Frame frame={};
         if(ReadFrame(frame)) { candidateAtr=frame.atr; candidateSignal=V19Signal(frame,candidateReason); lastBar=bar; Event("BAR",StringFormat("bar=%s state=%s signal=%d atr=%.5f",TimeToString(bar),candidateReason,candidateSignal,candidateAtr)); }
      }
      else { lastBar=bar; candidateSignal=0; Event("SIGNAL_EXPIRED",StringFormat("bar=%s age=%I64d frame=unavailable",TimeToString(candidateBar),age)); }
   }
   TryEntry(tick);
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if(!CanonicalXauSymbol(HistoryDealGetString(trans.deal,DEAL_SYMBOL))) return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY); if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) return;
   ulong positionId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
   datetime closedAt=(datetime)HistoryDealGetInteger(trans.deal,DEAL_TIME);
   double profit=HistoryDealGetDouble(trans.deal,DEAL_PROFIT),commission=HistoryDealGetDouble(trans.deal,DEAL_COMMISSION),swap=HistoryDealGetDouble(trans.deal,DEAL_SWAP),fee=HistoryDealGetDouble(trans.deal,DEAL_FEE);
   if(!PositionOpenedByUs(positionId)) return;
   lastExit=closedAt;
   Event("CLOSED",StringFormat("position=%I64u profit=%.2f commission=%.2f swap=%.2f fee=%.2f",positionId,profit,commission,swap,fee));
}

double OnTester()
{
   double trades=TesterStatistics(STAT_TRADES),wins=TesterStatistics(STAT_PROFIT_TRADES);
   Event("TEST_SUMMARY",StringFormat("trades=%.0f wins=%.0f winrate=%.2f net=%.2f PF=%.3f equityDD=%.2f%%",trades,wins,trades>0?100.0*wins/trades:0.0,TesterStatistics(STAT_PROFIT),TesterStatistics(STAT_PROFIT_FACTOR),TesterStatistics(STAT_EQUITY_DDREL_PERCENT)));
   return TesterStatistics(STAT_PROFIT);
}

void OnDeinit(const int reason)
{
   ReleaseEntryMutex();
   if(atr14!=INVALID_HANDLE) IndicatorRelease(atr14);
   Event("DEINIT",StringFormat("reason=%d",reason)); if(journal!=INVALID_HANDLE) FileClose(journal);
}
