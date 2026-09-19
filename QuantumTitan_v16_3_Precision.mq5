// Derived from git HEAD QuantumTitan_v16_Velocity.mq5 (v16.00), not v16.55/V16.1.
// Candidate only. Defaults require broker-specific backtesting; no profit guarantee.
#property version "16.30"
#property description "M1 Precision: closed-bar EMA retest, wick rejection, squeeze slopes"
#include <Trade\Trade.mqh>

input bool InpDemoOnly=true;
input ulong InpAllowedAccount=112468807; // Mandatory exact account allowlist outside Strategy Tester
input string InpSymbolPrefix="XAUUSD"; // Allows broker suffixes, e.g. XAUUSD.a
input ulong InpMagicNumber=991613;
input double InpMaxAccountLots=0.20;
input double InpMaxSpreadPoints=35.0;
input double InpHardEquityFloor=30.0;
input int InpBBLength=20;
input double InpBBMult=2.0;
input int InpKCLength=20;
input double InpKCMult=1.5;
input int InpFastEmaPeriod=14;
input int InpSlowEmaPeriod=50;
input double InpWickRatioThreshold=0.25;
input double InpBaseLot=0.01;
input double InpTakeProfitPoints=220.0;
input double InpStopLossPoints=220.0;
input double InpBreakevenTriggerPts=130.0;
input double InpBreakevenLockPts=20.0;
input int InpCooldownBars=2; // Completed M1 intervals after exit
input bool InpUseSessionFilter=false;
input int InpSessionStartHour=7; // Broker server hour, inclusive
input int InpSessionEndHour=22; // Exclusive; equal hours allow all day
input double InpRetestTolerancePts=15.0;
input double InpMomentumTolerancePts=5.0; // Slope price/bar converted to points/bar
input bool InpRequireMomentumExpansion=false; // Optional tighter filter affects frequency
input bool InpEnableHUD=true;

CTrade g_trade;
int g_fast=INVALID_HANDLE,g_slow=INVALID_HANDLE,g_bands=INVALID_HANDLE;
int g_atr=INVALID_HANDLE,g_rsi=INVALID_HANDLE;
datetime g_lastBarTime=0,g_lastExitTime=0;
string g_lockKey,g_exitKey;
bool g_entryPending=false;

struct SqueezeState
{
   bool isSqueezeOn,isBreakout,isMomentumBullish,isMomentumBearish;
   double momentum,prevMomentum;
};
struct EntryState
{
   ulong ticket;
   double openPrice,initialRisk,tp,beTrigger,beLock;
};
EntryState g_entries[];

double LinRegSlope(const double &src[],const int length,const int offset)
{
   double sx=0,sy=0,sxy=0,sxx=0;
   for(int i=0;i<length;i++)
   {
      double x=(double)i,y=src[offset+length-1-i];
      sx+=x; sy+=y; sxy+=x*y; sxx+=x*x;
   }
   return (length*sxy-sx*sy)/(length*sxx-sx*sx);
}
bool ReadClosed(const int handle,const int buffer,const int count,double &out[])
{
   ArrayResize(out,count);
   ArrayInitialize(out,0.0);
   ArraySetAsSeries(out,true);
   if(CopyBuffer(handle,buffer,1,count,out)!=count) return false;
   for(int i=0;i<count;i++)
      if(!MathIsValidNumber(out[i]) || out[i]==EMPTY_VALUE) return false;
   return true;
}
bool CalculateSqueezeMomentum(SqueezeState &state)
{
   ZeroMemory(state);
   const int length=20;
   double basis[],upper[],lower[],atr[];
   if(!ReadClosed(g_bands,0,length+1,basis) || !ReadClosed(g_bands,1,2,upper) ||
      !ReadClosed(g_bands,2,2,lower) || !ReadClosed(g_atr,0,2,atr)) return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   int needed=length+InpKCLength;
   if(CopyRates(_Symbol,PERIOD_M1,1,needed,rates)!=needed) return false;
   state.isSqueezeOn=upper[0]<basis[0]+InpKCMult*atr[0] && lower[0]>basis[0]-InpKCMult*atr[0];
   bool previous=upper[1]<basis[1]+InpKCMult*atr[1] && lower[1]>basis[1]-InpKCMult*atr[1];
   state.isBreakout=previous && !state.isSqueezeOn;
   double delta[];
   ArrayResize(delta,length+1);
   for(int k=0;k<=length;k++)
   {
      double hi=rates[k].high,lo=rates[k].low;
      for(int j=1;j<InpKCLength;j++)
      { hi=MathMax(hi,rates[k+j].high); lo=MathMin(lo,rates[k+j].low); }
      delta[k]=rates[k].close-((hi+lo)/2.0+basis[k])/2.0;
   }
   state.momentum=LinRegSlope(delta,length,0);
   state.prevMomentum=LinRegSlope(delta,length,1);
   state.isMomentumBullish=state.momentum>0 && state.momentum>=state.prevMomentum;
   state.isMomentumBearish=state.momentum<0 && state.momentum<=state.prevMomentum;
   return MathIsValidNumber(state.momentum) && MathIsValidNumber(state.prevMomentum);
}
string StatePrefix()
{ return StringFormat("P163_%I64d_%I64u_",AccountInfoInteger(ACCOUNT_LOGIN),InpMagicNumber); }
string StateKey(const ulong ticket,const string field)
{ return StatePrefix()+StringFormat("%I64u_%s",ticket,field); }
void CleanupClosedState()
{
   // Only this account/magic's per-ticket state, never another EA's globals.
   string prefix=StatePrefix();
   for(int i=GlobalVariablesTotal()-1;i>=0;i--)
   {
      string key=GlobalVariableName(i);
      if(StringFind(key,prefix)!=0) continue;
      string tail=StringSubstr(key,StringLen(prefix));
      int separator=StringFind(tail,"_");
      if(separator<=0) continue;
      ulong ticket=(ulong)StringToInteger(StringSubstr(tail,0,separator));
      if(ticket>0 && !PositionSelectByTicket(ticket)) GlobalVariableDel(key);
   }
   for(int i=ArraySize(g_entries)-1;i>=0;i--)
      if(!PositionSelectByTicket(g_entries[i].ticket)) ArrayRemove(g_entries,i,1);
}

// Snapshot once; never derive BE from a moved SL. Persist through parameter changes/restart.
int TrackPosition(const ulong ticket)
{
   for(int i=0;i<ArraySize(g_entries);i++) if(g_entries[i].ticket==ticket) return i;
   if(!PositionSelectByTicket(ticket)) return -1;
   EntryState s;
   ZeroMemory(s); s.ticket=ticket;
   if(GlobalVariableCheck(StateKey(ticket,"ready")))
   {
      string fields[]={"open","risk","tp","trigger","lock"};
      for(int j=0;j<ArraySize(fields);j++) if(!GlobalVariableCheck(StateKey(ticket,fields[j]))) return -1;
      s.openPrice=GlobalVariableGet(StateKey(ticket,"open"));
      s.initialRisk=GlobalVariableGet(StateKey(ticket,"risk"));
      s.tp=GlobalVariableGet(StateKey(ticket,"tp"));
      s.beTrigger=GlobalVariableGet(StateKey(ticket,"trigger"));
      s.beLock=GlobalVariableGet(StateKey(ticket,"lock"));
   }
   else
   {
      // Recover original protective levels from entry order, never from current trailing SL.
      if(!HistorySelectByPosition(PositionGetInteger(POSITION_IDENTIFIER))) return -1;
      ulong entryOrder=0;
      for(int d=0;d<HistoryDealsTotal();d++)
      {
         ulong deal=HistoryDealGetTicket(d);
         if(HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
         { entryOrder=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER); break; }
      }
      if(entryOrder==0 || !HistoryOrderSelect(entryOrder)) return -1;
      s.openPrice=PositionGetDouble(POSITION_PRICE_OPEN);
      double originalSl=HistoryOrderGetDouble(entryOrder,ORDER_SL);
      s.initialRisk=MathAbs(s.openPrice-originalSl);
      s.tp=HistoryOrderGetDouble(entryOrder,ORDER_TP);
      s.beTrigger=InpBreakevenTriggerPts*_Point;
      s.beLock=InpBreakevenLockPts*_Point;
      if(originalSl<=0 || s.tp<=0 || s.initialRisk<=0) return -1;
      if(!GlobalVariableSet(StateKey(ticket,"open"),s.openPrice) ||
         !GlobalVariableSet(StateKey(ticket,"risk"),s.initialRisk) ||
         !GlobalVariableSet(StateKey(ticket,"tp"),s.tp) ||
         !GlobalVariableSet(StateKey(ticket,"trigger"),s.beTrigger) ||
         !GlobalVariableSet(StateKey(ticket,"lock"),s.beLock)) return -1;
      if(!GlobalVariableSet(StateKey(ticket,"ready"),1.0)) return -1;
      GlobalVariablesFlush();
   }
   int n=ArraySize(g_entries); ArrayResize(g_entries,n+1); g_entries[n]=s; return n;
}
double TickRound(const double price)
{
   double tick=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   return tick>0 ? NormalizeDouble(MathRound(price/tick)*tick,_Digits) : 0;
}
bool StopsValid(const bool buy,const double sl,const double tp,const MqlTick &quote,const bool modifying)
{
   double stops=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
   double freeze=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL)*_Point;
   double distance=modifying ? MathMax(stops,freeze) : stops;
   double price=buy ? quote.bid : quote.ask;
   if(sl<=0 || tp<=0) return false;
   return buy ? (price-sl>distance && tp-price>distance) : (sl-price>distance && price-tp>distance);
}
int ActiveForMagic()
{
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
      if(PositionGetTicket(i)>0 && (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagicNumber) count++;
   for(int i=OrdersTotal()-1;i>=0;i--)
      if(OrderGetTicket(i)>0 && (ulong)OrderGetInteger(ORDER_MAGIC)==InpMagicNumber) count++;
   return count;
}
void ManagePositions(const MqlTick &quote)
{
   for(int p=PositionsTotal()-1;p>=0;p--)
   {
      ulong ticket=PositionGetTicket(p);
      if(ticket==0 || PositionGetString(POSITION_SYMBOL)!=_Symbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) continue;
      int n=TrackPosition(ticket);
      if(n<0 || !PositionSelectByTicket(ticket)) continue;
      EntryState s=g_entries[n];
      bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
      double gain=buy ? quote.bid-s.openPrice : s.openPrice-quote.ask;
      if(gain<s.beTrigger) continue;
      double sl=TickRound(s.openPrice+(buy ? s.beLock : -s.beLock));
      double current=PositionGetDouble(POSITION_SL);
      if(current>0 && (buy ? current>=sl : current<=sl)) continue;
      double freeze=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL)*_Point;
      double price=buy ? quote.bid : quote.ask;
      if(current>0 && MathAbs(price-current)<=freeze) continue;
      if(!StopsValid(buy,sl,s.tp,quote,true)) continue;
      bool sent=g_trade.PositionModify(ticket,sl,s.tp);
      uint code=g_trade.ResultRetcode();
      if(sent && code==TRADE_RETCODE_DONE)
         PrintFormat("[Precision] BE LOCKED ticket=%I64u SL=%.5f initialRisk=%.5f",ticket,sl,s.initialRisk);
      else PrintFormat("[Precision] BE FAILED ticket=%I64u code=%u %s",ticket,code,g_trade.ResultRetcodeDescription());
   }
}
bool SessionAllowed()
{
   if(!InpUseSessionFilter || InpSessionStartHour==InpSessionEndHour) return true;
   MqlDateTime t; if(!TimeToStruct(TimeCurrent(),t)) return false;
   return InpSessionStartHour<InpSessionEndHour ?
      (t.hour>=InpSessionStartHour && t.hour<InpSessionEndHour) :
      (t.hour>=InpSessionStartHour || t.hour<InpSessionEndHour);
}
int OnInit()
{
   if(_Period!=PERIOD_M1) return INIT_PARAMETERS_INCORRECT;
   if(!MQLInfoInteger(MQL_TESTER) &&
      (InpAllowedAccount==0 || (ulong)AccountInfoInteger(ACCOUNT_LOGIN)!=InpAllowedAccount)) return INIT_FAILED;
   if(StringLen(InpSymbolPrefix)==0 || StringFind(_Symbol,InpSymbolPrefix)!=0) return INIT_FAILED;
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) return INIT_FAILED;
   if(InpMagicNumber==0 || InpBBLength<2 || InpKCLength<2 || InpBBLength>1000 || InpKCLength>1000 ||
      InpFastEmaPeriod<1 || InpSlowEmaPeriod<=InpFastEmaPeriod || InpBBMult<=0 || InpKCMult<=0 ||
      InpStopLossPoints<=0 || InpTakeProfitPoints<=0 || InpBaseLot<=0 || InpMaxSpreadPoints<=0 ||
      InpBreakevenLockPts<0 || InpBreakevenTriggerPts<=InpBreakevenLockPts ||
      InpBreakevenTriggerPts>=InpTakeProfitPoints || InpCooldownBars<0 ||
      InpSessionStartHour<0 || InpSessionStartHour>23 || InpSessionEndHour<0 || InpSessionEndHour>23 ||
      InpWickRatioThreshold<0 || InpWickRatioThreshold>1 || InpMomentumTolerancePts<0 ||
      InpRetestTolerancePts<0 || InpMaxAccountLots<InpBaseLot ||
      InpHardEquityFloor<0 || _Point<=0) return INIT_PARAMETERS_INCORRECT;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0 || InpBaseLot<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN) ||
      InpBaseLot>SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX) ||
      MathAbs(InpBaseLot/step-MathRound(InpBaseLot/step))>1e-7) return INIT_PARAMETERS_INCORRECT;
   g_lockKey=StringFormat("P163_LOCK_%I64d_%I64u",AccountInfoInteger(ACCOUNT_LOGIN),InpMagicNumber);
   g_exitKey=g_lockKey+"_exit";
   if(!GlobalVariableTemp(g_lockKey)) return INIT_FAILED;
   if(GlobalVariableCheck(g_exitKey)) g_lastExitTime=(datetime)GlobalVariableGet(g_exitKey);
   CleanupClosedState();
   g_trade.SetExpertMagicNumber(InpMagicNumber); g_trade.SetAsyncMode(false);
   g_trade.SetDeviationInPoints(20);
   if(!g_trade.SetTypeFillingBySymbol(_Symbol)) return INIT_FAILED;
   g_fast=iMA(_Symbol,PERIOD_M1,InpFastEmaPeriod,0,MODE_EMA,PRICE_CLOSE);
   g_slow=iMA(_Symbol,PERIOD_M1,InpSlowEmaPeriod,0,MODE_EMA,PRICE_CLOSE);
   g_bands=iBands(_Symbol,PERIOD_M1,InpBBLength,0,InpBBMult,PRICE_CLOSE);
   g_atr=iATR(_Symbol,PERIOD_M1,InpKCLength); g_rsi=iRSI(_Symbol,PERIOD_M1,14,PRICE_CLOSE);
   if(g_fast==INVALID_HANDLE || g_slow==INVALID_HANDLE || g_bands==INVALID_HANDLE ||
      g_atr==INVALID_HANDLE || g_rsi==INVALID_HANDLE) return INIT_FAILED;
   Print("[Precision] Candidate initialized; 220-point TP is not a fixed dollar return.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
   IndicatorRelease(g_fast); IndicatorRelease(g_slow); IndicatorRelease(g_bands);
   IndicatorRelease(g_atr); IndicatorRelease(g_rsi); if(InpEnableHUD) Comment("");
}
void EvaluateEntry(const MqlTick &quote)
{
   if(g_entryPending || ActiveForMagic()>0 || !SessionAllowed()) return;
   // A netting account cannot isolate this EA from another position on same symbol.
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING && PositionSelect(_Symbol)) return;
   if((quote.ask-quote.bid)/_Point>InpMaxSpreadPoints) return;
   datetime lastExit=g_lastExitTime;
   if(GlobalVariableCheck(g_exitKey)) lastExit=(datetime)GlobalVariableGet(g_exitKey);
   if(lastExit>0 && iBarShift(_Symbol,PERIOD_M1,lastExit,false)<InpCooldownBars) return;
   if(AccountInfoDouble(ACCOUNT_EQUITY)<InpHardEquityFloor) return;
   double lots=0;
   for(int i=PositionsTotal()-1;i>=0;i--) if(PositionGetTicket(i)>0) lots+=PositionGetDouble(POSITION_VOLUME);
   if(lots+InpBaseLot>InpMaxAccountLots+1e-8) return;
   double fast[],slow[],rsi[];
   SqueezeState sqz; ZeroMemory(sqz);
   if(!ReadClosed(g_fast,0,1,fast) || !ReadClosed(g_slow,0,1,slow) ||
      !ReadClosed(g_rsi,0,1,rsi) || !CalculateSqueezeMomentum(sqz)) return;
   MqlRates rates[]; ArraySetAsSeries(rates,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,rates)!=1) return;
   MqlRates b=rates[0]; double range=b.high-b.low;
   if(range<=0) return;
   double lower=(MathMin(b.open,b.close)-b.low)/range;
   double upper=(b.high-MathMax(b.open,b.close))/range;
   // Preserve v16 wick OR candle direction, add close reclaim to reject failed pullbacks.
   bool buy=fast[0]>slow[0] && b.close>slow[0] && b.close>=fast[0] &&
      b.low<=fast[0]+InpRetestTolerancePts*_Point &&
      (lower>=InpWickRatioThreshold || b.close>b.open) &&
      sqz.momentum> -InpMomentumTolerancePts*_Point && rsi[0]>=40 && rsi[0]<=70 &&
      (!InpRequireMomentumExpansion || sqz.isMomentumBullish);
   bool sell=fast[0]<slow[0] && b.close<slow[0] && b.close<=fast[0] &&
      b.high>=fast[0]-InpRetestTolerancePts*_Point &&
      (upper>=InpWickRatioThreshold || b.close<b.open) &&
      sqz.momentum<InpMomentumTolerancePts*_Point && rsi[0]>=30 && rsi[0]<=60 &&
      (!InpRequireMomentumExpansion || sqz.isMomentumBearish);
   if(InpEnableHUD) Comment(StringFormat("Precision M1 | TP %.0f SL %.0f BE %.0f | slope %.5f",InpTakeProfitPoints,InpStopLossPoints,InpBreakevenTriggerPts,sqz.momentum));
   if(!buy && !sell) return;
   double entry=buy ? quote.ask : quote.bid;
   double sl=TickRound(entry+(buy ? -InpStopLossPoints : InpStopLossPoints)*_Point);
   double tp=TickRound(entry+(buy ? InpTakeProfitPoints : -InpTakeProfitPoints)*_Point);
   if(!StopsValid(buy,sl,tp,quote,false)) return;
   g_entryPending=true;
   bool sent=buy ? g_trade.Buy(InpBaseLot,_Symbol,entry,sl,tp,"QT163_Precision") :
      g_trade.Sell(InpBaseLot,_Symbol,entry,sl,tp,"QT163_Precision");
   uint code=g_trade.ResultRetcode();
   // Uncertain/placed requests remain blocked; avoid a duplicate retry.
   if(code!=TRADE_RETCODE_PLACED && code!=TRADE_RETCODE_TIMEOUT) g_entryPending=false;
   if(sent && (code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL))
   {
      PrintFormat("[Precision] ENTRY confirmed code=%u deal=%I64u",code,g_trade.ResultDeal());
      for(int p=PositionsTotal()-1;p>=0;p--)
      {
         ulong t=PositionGetTicket(p);
         if(t>0 && (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagicNumber && PositionGetString(POSITION_SYMBOL)==_Symbol) TrackPosition(t);
      }
   }
   else PrintFormat("[Precision] ENTRY result sent=%s code=%u %s",sent?"true":"false",code,g_trade.ResultRetcodeDescription());
}
void OnTick()
{
   if(_Period!=PERIOD_M1) return;
   MqlTick quote; ZeroMemory(quote);
   if(!SymbolInfoTick(_Symbol,quote) || quote.bid<=0 || quote.ask<quote.bid || _Point<=0) return;
   ManagePositions(quote);
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   if(bar<=0 || bar==g_lastBarTime) return;
   g_lastBarTime=bar; // One evaluation/attempt per completed M1 bar, including failures.
   CleanupClosedState();
   if(!GlobalVariableSetOnCondition(g_lockKey,1.0,0.0)) return;
   EvaluateEntry(quote);
   // Keep account/magic lock on uncertain execution until terminal restart/reconciliation.
   if(!g_entryPending) GlobalVariableSetOnCondition(g_lockKey,0.0,1.0);
}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || trans.deal==0 || !HistoryDealSelect(trans.deal)) return;
   bool owned=(ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)==InpMagicNumber;
   if(!owned)
   {
      // Manual/broker exits may have magic 0. Resolve ownership from entry deals.
      long positionId=HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
      if(positionId<=0 || !HistorySelectByPosition(positionId)) return;
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong deal=HistoryDealGetTicket(i);
         if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==InpMagicNumber &&
            HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN) { owned=true; break; }
      }
      if(!owned || !HistoryDealSelect(trans.deal)) return;
   }
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   double profit=HistoryDealGetDouble(trans.deal,DEAL_PROFIT);
   double commission=HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);
   double swap=HistoryDealGetDouble(trans.deal,DEAL_SWAP);
   double fee=HistoryDealGetDouble(trans.deal,DEAL_FEE);
   PrintFormat("[Precision DEAL] deal=%I64u position=%I64d symbol=%s entry=%d type=%d reason=%d volume=%.2f price=%.5f profit=%.2f commission=%.2f swap=%.2f fee=%.2f net=%.2f currency=%s",
      trans.deal,HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID),HistoryDealGetString(trans.deal,DEAL_SYMBOL),
      entry,HistoryDealGetInteger(trans.deal,DEAL_TYPE),HistoryDealGetInteger(trans.deal,DEAL_REASON),
      HistoryDealGetDouble(trans.deal,DEAL_VOLUME),HistoryDealGetDouble(trans.deal,DEAL_PRICE),
      profit,commission,swap,fee,profit+commission+swap+fee,AccountInfoString(ACCOUNT_CURRENCY));
   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY || entry==DEAL_ENTRY_INOUT)
   {
      g_lastExitTime=(datetime)HistoryDealGetInteger(trans.deal,DEAL_TIME);
      GlobalVariableSet(g_exitKey,(double)g_lastExitTime);
   }
   if(g_entryPending && (entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT))
   { g_entryPending=false; GlobalVariableSetOnCondition(g_lockKey,0.0,1.0); }
   if(entry==DEAL_ENTRY_IN && trans.symbol==_Symbol && trans.position>0) TrackPosition(trans.position);
}
