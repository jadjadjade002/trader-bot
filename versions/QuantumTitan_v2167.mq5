#property strict
#property version "21.67"
#property description "Corrected closed-bar Velocity candidate. Performance unverified. Fixed 0.01 lot."

#include <Trade/Trade.mqh>
#include "Include/QuantumTitan/V2167Signal.mqh"
#include "tests/V2167SignalTests.mqh"

input bool InpEnableDemoOrders=false;
input long InpExpectedDemoLogin=0;
input bool InpWriteJournal=true;

const ulong MAGIC=992167;
const double LOT=0.01;
const double STOP_POINTS=260.0, TARGET_POINTS=180.0;
const double BE_TRIGGER=85.0, BE_LOCK=15.0, MAX_SPREAD=60.0;
const int COOLDOWN=60, HOLD_SECONDS=600, DEVIATION=20;

CTrade trade;
int fastHandle=INVALID_HANDLE, slowHandle=INVALID_HANDLE, rsiHandle=INVALID_HANDLE;
int journal=INVALID_HANDLE;
long boundLogin=0;
datetime lastBar=0, lastExit=0, lastAction=0;
string prefix, ownerKey, attemptKey, pendingKey, reqPriceKey, reqSlKey, reqTpKey;
double ownerToken=0;
bool ownerHeld=false, accountErrorReported=false, stateFault=false;
ulong mustClosePositionId=0;

void Event(const string kind,const string detail)
{
   PrintFormat("[QT21.67] %s | %s",kind,detail);
   if(journal!=INVALID_HANDLE)
   {
      FileWrite(journal,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),kind,detail);
      FileFlush(journal);
   }
}

bool Finite(const double value) { return MathIsValidNumber(value) && value!=EMPTY_VALUE; }
bool InTester() { return (bool)MQLInfoInteger(MQL_TESTER); }
bool ProhibitedLogin(const long login) { return login==112334471 || login==5055724796; }

bool AccountMatches()
{
   if(AccountInfoInteger(ACCOUNT_LOGIN)!=boundLogin) return false;
   if(InTester()) return true;
   return !ProhibitedLogin(boundLogin) &&
          AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO;
}

bool OrdersEnabled()
{
   if(!AccountMatches()) return false;
   // The isolated Strategy Tester must not inherit the live terminal's Algo Trading UI switch.
   if(InTester()) return true;
   if(!InTester() && (!InpEnableDemoOrders || InpExpectedDemoLogin<=0 ||
                     boundLogin!=InpExpectedDemoLogin)) return false;
   return TerminalInfoInteger(TERMINAL_CONNECTED) &&
          TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
          MQLInfoInteger(MQL_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_EXPERT);
}

bool GoldSymbol(string symbol)
{
   StringToUpper(symbol);
   return StringFind(symbol,"XAU")>=0 || StringFind(symbol,"GOLD")>=0;
}

bool OwnSelected()
{
   return PositionGetString(POSITION_SYMBOL)==_Symbol &&
          (ulong)PositionGetInteger(POSITION_MAGIC)==MAGIC;
}

bool GoldExposure()
{
   for(int i=PositionsTotal()-1;i>=0;--i)
      if(PositionGetTicket(i)>0 && GoldSymbol(PositionGetString(POSITION_SYMBOL))) return true;
   for(int i=OrdersTotal()-1;i>=0;--i)
      if(OrderGetTicket(i)>0 && GoldSymbol(OrderGetString(ORDER_SYMBOL))) return true;
   return false;
}

bool ValidVolume()
{
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(!Finite(minimum)||!Finite(maximum)||!Finite(step)||step<=0||LOT<minimum||LOT>maximum)
      return false;
   return MathAbs((LOT-minimum)/step-MathRound((LOT-minimum)/step))<1e-8;
}

// A dedicated terminal instance owns this account/magic. Do not steal a live lock.
bool AcquireOwner()
{
   if(!GlobalVariableCheck(ownerKey) && !GlobalVariableTemp(ownerKey)) return false;
   ownerToken=(double)GetTickCount64()+((double)(ChartID()%1000000))/1000000.0+1.0;
   ownerHeld=GlobalVariableSetOnCondition(ownerKey,ownerToken,0.0);
   return ownerHeld;
}

bool SaveState(const string key,const double value)
{
   if(GlobalVariableSet(key,value)==0)
   { stateFault=true; Event("STATE_ERROR",key+" set failed; new entries disabled until restart"); return false; }
   GlobalVariablesFlush();
   if(!GlobalVariableCheck(key) || GlobalVariableGet(key)!=value)
   { stateFault=true; Event("STATE_ERROR",key+" verification failed; new entries disabled until restart"); return false; }
   return true;
}

bool SaveIntent(const datetime bar,const datetime stamp,const double price,const double sl,const double tp)
{
   // Put the pending marker first. Any later failure leaves this process fail-closed.
   if(GlobalVariableSet(pendingKey,(double)stamp)==0 ||
      GlobalVariableSet(attemptKey,(double)bar)==0 || GlobalVariableSet(reqPriceKey,price)==0 ||
      GlobalVariableSet(reqSlKey,sl)==0 || GlobalVariableSet(reqTpKey,tp)==0)
   {
      stateFault=true;
      Event("STATE_ERROR","Intent batch set failed; new entries disabled until restart");
      return false;
   }
   GlobalVariablesFlush();
   bool verified=GlobalVariableCheck(pendingKey)&&GlobalVariableGet(pendingKey)==(double)stamp&&
      GlobalVariableCheck(attemptKey)&&GlobalVariableGet(attemptKey)==(double)bar&&
      GlobalVariableCheck(reqPriceKey)&&GlobalVariableGet(reqPriceKey)==price&&
      GlobalVariableCheck(reqSlKey)&&GlobalVariableGet(reqSlKey)==sl&&
      GlobalVariableCheck(reqTpKey)&&GlobalVariableGet(reqTpKey)==tp;
   if(!verified)
   {
      stateFault=true;
      Event("STATE_ERROR","Intent batch verification failed; new entries disabled until restart");
   }
   return verified;
}

bool ValidTick(MqlTick &tick)
{
   return SymbolInfoTick(_Symbol,tick) && Finite(tick.bid) && Finite(tick.ask) &&
          tick.bid>0 && tick.ask>tick.bid;
}

// HistorySelectByPosition replaces the selected history. Callers snapshot fields first.
bool PositionLedger(const ulong positionId,double &net,double &opened,double &closed,
                    datetime &exitTime)
{
   net=0; opened=0; closed=0; exitTime=0;
   if(positionId==0 || !HistorySelectByPosition(positionId)) return false;
   bool ours=false;
   for(int i=0;i<HistoryDealsTotal();++i)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(deal==0 || HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_IN)
      {
         if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=MAGIC) return false;
         ours=true;
         opened+=HistoryDealGetDouble(deal,DEAL_VOLUME);
      }
      else if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
      {
         closed+=HistoryDealGetDouble(deal,DEAL_VOLUME);
         datetime stamp=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);
         if(stamp>exitTime) exitTime=stamp;
      }
      else if(entry==DEAL_ENTRY_INOUT) return false;
      net+=HistoryDealGetDouble(deal,DEAL_PROFIT)+HistoryDealGetDouble(deal,DEAL_COMMISSION)+
           HistoryDealGetDouble(deal,DEAL_SWAP)+HistoryDealGetDouble(deal,DEAL_FEE);
   }
   return ours && Finite(net) && opened>0;
}

bool RestoreCooldown()
{
   if(!HistorySelect(0,TimeCurrent())) return false;
   ulong ids[];
   int count=0;
   for(int i=HistoryDealsTotal()-1;i>=0;--i)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(deal==0 || HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;
      ArrayResize(ids,count+1);
      ids[count++]=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   }
   for(int i=0;i<count;++i)
   {
      double net,opened,closed; datetime stamp;
      if(PositionLedger(ids[i],net,opened,closed,stamp) && MathAbs(opened-closed)<1e-8)
      {
         if(stamp>lastExit) lastExit=stamp;
         break;
      }
   }
   return true;
}

bool ValidateFilledProtection(const ulong deal);

bool SubmissionReady()
{
   if(!GlobalVariableCheck(pendingKey)) return true;
   datetime pending=(datetime)GlobalVariableGet(pendingKey);
   if(pending<=0) return true;
   if(!HistorySelect(pending,TimeCurrent())) return false;
   for(int i=HistoryDealsTotal()-1;i>=0;--i)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(deal>0 && HistoryDealGetString(deal,DEAL_SYMBOL)==_Symbol &&
         (ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==MAGIC &&
         HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
      {
         if(!ValidateFilledProtection(deal)) return false;
         if(!RestoreCooldown()) return false;
         return SaveState(pendingKey,0.0);
      }
   }
   // An ambiguous submission survives restart. No time-based automatic retry.
   return false;
}

bool ReadValue(const int handle,double &value)
{
   double values[1];
   if(handle==INVALID_HANDLE || CopyBuffer(handle,0,1,1,values)!=1) return false;
   value=values[0];
   return Finite(value);
}

bool ReadFrame(const datetime bar,V2167Frame &frame)
{
   MqlRates bars[];
   ArraySetAsSeries(bars,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,40,bars)!=40 || bars[0].time!=bar-60) return false;
   double priorMomentum;
   if(!V2167Momentum(bars,frame.momentum,priorMomentum)) return false;
   frame.open=bars[0].open; frame.high=bars[0].high;
   frame.low=bars[0].low; frame.close=bars[0].close; frame.point=_Point;
   return ReadValue(fastHandle,frame.fast) && ReadValue(slowHandle,frame.slow) &&
          ReadValue(rsiHandle,frame.rsi);
}

bool Accepted(const uint retcode)
{
   return retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL;
}

bool DefinitivelyRejected(const uint code)
{
   return code==TRADE_RETCODE_REQUOTE || code==TRADE_RETCODE_REJECT ||
      code==TRADE_RETCODE_CANCEL || code==TRADE_RETCODE_INVALID ||
      code==TRADE_RETCODE_INVALID_VOLUME || code==TRADE_RETCODE_INVALID_PRICE ||
      code==TRADE_RETCODE_INVALID_STOPS || code==TRADE_RETCODE_TRADE_DISABLED ||
      code==TRADE_RETCODE_MARKET_CLOSED || code==TRADE_RETCODE_NO_MONEY ||
      code==TRADE_RETCODE_PRICE_CHANGED || code==TRADE_RETCODE_PRICE_OFF ||
      code==TRADE_RETCODE_TOO_MANY_REQUESTS || code==TRADE_RETCODE_INVALID_FILL;
}

bool CloseOwn(const ulong ticket,const string reason)
{
   if(!OrdersEnabled() || TimeCurrent()-lastAction<2 ||
      !PositionSelectByTicket(ticket) || !OwnSelected()) return false;
   lastAction=TimeCurrent();
   bool sent=trade.PositionClose(ticket,DEVIATION);
   uint code=trade.ResultRetcode();
   Event(reason,StringFormat("ticket=%I64u sent=%d retcode=%u",ticket,sent,code));
   // Block same-tick re-entry even before the transaction callback is delivered.
   if(sent && Accepted(code)) lastExit=TimeCurrent();
   return sent && Accepted(code);
}

bool ValidateFilledProtection(const ulong deal)
{
   if(deal==0 || !HistoryDealSelect(deal)) return false;
   ulong positionId=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   ulong ticket=0;
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong candidate=PositionGetTicket(i);
      if(candidate>0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER)==positionId)
      { ticket=candidate; break; }
   }
   if(ticket==0)
   {
      double net,opened,closed; datetime stamp;
      return PositionLedger(positionId,net,opened,closed,stamp) && opened>0 &&
             MathAbs(opened-closed)<1e-8;
   }
   if(!PositionSelectByTicket(ticket) || !OwnSelected()) return false;
   if(!GlobalVariableCheck(reqPriceKey) || !GlobalVariableCheck(reqSlKey) ||
      !GlobalVariableCheck(reqTpKey))
   {
      stateFault=true;
      Event("STATE_ERROR","Missing requested-protection record; new entries disabled until restart");
      mustClosePositionId=positionId;
      CloseOwn(ticket,"UNRECONCILED_PROTECTION_EXIT");
      return false;
   }
   double requested=GlobalVariableGet(reqPriceKey);
   double requestedSl=GlobalVariableGet(reqSlKey),requestedTp=GlobalVariableGet(reqTpKey);
   double fill=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
   long type=PositionGetInteger(POSITION_TYPE);
   double risk=type==POSITION_TYPE_BUY ? (fill-sl)/_Point : (sl-fill)/_Point;
   double target=type==POSITION_TYPE_BUY ? (tp-fill)/_Point : (fill-tp)/_Point;
   double slip=type==POSITION_TYPE_BUY ? (fill-requested)/_Point : (requested-fill)/_Point;
   double tolerance=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE)/_Point+1e-8;
   bool oriented=type==POSITION_TYPE_BUY ? sl<fill && tp>fill : sl>fill && tp<fill;
   bool safe=Finite(fill)&&Finite(sl)&&Finite(tp)&&oriented&&
             target>=TARGET_POINTS-DEVIATION-tolerance && risk<=STOP_POINTS+DEVIATION+tolerance &&
             MathAbs(sl-requestedSl)<=tolerance*_Point &&
             MathAbs(tp-requestedTp)<=tolerance*_Point;
   Event("FILL_PROTECTION",StringFormat("position=%I64u requested=%.5f fill=%.5f sl_req=%.5f sl=%.5f tp_req=%.5f tp=%.5f adverse_slip=%.1f risk=%.1f target=%.1f safe=%d deviation_is_not_guaranteed=1",
         positionId,requested,fill,requestedSl,sl,requestedTp,tp,slip,risk,target,safe));
   if(!safe)
   {
      mustClosePositionId=positionId;
      CloseOwn(ticket,"FILL_PROTECTION_EXIT");
      return false;
   }
   return true;
}

void Manage(const MqlTick &tick)
{
   MqlDateTime now; TimeToStruct(TimeCurrent(),now);
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !OwnSelected() || !PositionSelectByTicket(ticket)) continue;
      ulong positionId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(positionId==mustClosePositionId)
      { CloseOwn(ticket,"FILL_PROTECTION_RETRY_EXIT"); return; }
      long type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
      if(!Finite(sl)||!Finite(tp)||sl<=0||tp<=0)
      { CloseOwn(ticket,"UNPROTECTED_EXIT"); return; }
      // Leave a crossed server stop/target for broker execution, not a competing close.
      bool crossed=type==POSITION_TYPE_BUY ? tick.bid<=sl||tick.bid>=tp : tick.ask>=sl||tick.ask<=tp;
      if(crossed) return;
      if(now.hour>=2 && now.hour<18) { CloseOwn(ticket,"SESSION_EXIT"); return; }
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      if(opened>0 && TimeCurrent()-opened>=HOLD_SECONDS)
      { CloseOwn(ticket,"TIME_EXIT"); return; }
      double profit=type==POSITION_TYPE_BUY ? (tick.bid-open)/_Point : (open-tick.ask)/_Point;
      if(profit<BE_TRIGGER || TimeCurrent()-lastAction<2 || !OrdersEnabled()) return;
      double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      // Round away from the market, so the requested stop is not too close.
      double target=V2167Round(open+(type==POSITION_TYPE_BUY ? 1.0 : -1.0)*BE_LOCK*_Point,
                              step,type==POSITION_TYPE_SELL);
      double distance=(MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
                              SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))+1)*_Point;
      bool improve=type==POSITION_TYPE_BUY ? target>sl && tick.bid-target>distance :
                                            target<sl && target-tick.ask>distance;
      if(!Finite(target)||target<=0||!improve || !PositionSelectByTicket(ticket)||!OwnSelected()) return;
      lastAction=TimeCurrent();
      bool sent=trade.PositionModify(ticket,NormalizeDouble(target,_Digits),tp);
      Event("BE_RESULT",StringFormat("ticket=%I64u price=%.5f sent=%d retcode=%u",
                                    ticket,target,sent,trade.ResultRetcode()));
      return;
   }
}

bool Filling(ENUM_ORDER_TYPE_FILLING &value)
{
   long modes=SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((modes&SYMBOL_FILLING_FOK)!=0) { value=ORDER_FILLING_FOK; return true; }
   if((modes&SYMBOL_FILLING_IOC)!=0) { value=ORDER_FILLING_IOC; return true; }
   if(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_EXEMODE)!=SYMBOL_TRADE_EXECUTION_MARKET)
   { value=ORDER_FILLING_RETURN; return true; }
   return false;
}

void TryEntry(const int signal,const string reason,const datetime bar)
{
   if(stateFault) { Event("SKIP","PERSISTENT_STATE_FAULT"); return; }
   if(!OrdersEnabled()) { Event("SKIP","ORDERS_DISABLED"); return; }
   if(!SubmissionReady()) { Event("SKIP","UNRESOLVED_SUBMISSION"); return; }
   if(GoldExposure()) { Event("SKIP","EXISTING_GOLD_EXPOSURE"); return; }
   if(TimeCurrent()-lastExit<COOLDOWN) { Event("SKIP","POST_EXIT_COOLDOWN"); return; }
   if(!ValidVolume()) { Event("SKIP","INVALID_VOLUME"); return; }
   // The indicator frame is frozen, but execution eligibility uses a fresh quote and clock.
   MqlTick quote;
   if(!V2167SignalAlive(TimeCurrent()-bar) || !ValidTick(quote))
   { Event("SKIP","STALE_OR_REJECTED_EXECUTION_QUOTE"); return; }
   if((quote.ask-quote.bid)/_Point>MAX_SPREAD) { Event("SKIP","SPREAD_TOO_WIDE"); return; }
   double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double price=signal>0 ? quote.ask : quote.bid;
   double sl=NormalizeDouble(V2167Round(price-signal*STOP_POINTS*_Point,step,signal<0),_Digits);
   double tp=NormalizeDouble(V2167Round(price+signal*TARGET_POINTS*_Point,step,signal>0),_Digits);
   if(sl<=0||tp<=0||!Finite(sl)||!Finite(tp) || MathAbs(price-sl)>STOP_POINTS*_Point+1e-8)
   { Event("SKIP","INVALID_TICK_ROUNDING"); return; }
   double distance=(MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
                           SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))+1)*_Point;
   if((signal>0 && (quote.bid-sl<distance || tp-quote.bid<distance)) ||
      (signal<0 && (sl-quote.ask<distance || quote.ask-tp<distance)))
   { Event("SKIP","BROKER_STOP_DISTANCE"); return; }
   ENUM_ORDER_TYPE type=signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double margin=0;
   if(!OrderCalcMargin(type,_Symbol,LOT,price,margin)||!Finite(margin)||margin<0||
      margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)) { Event("SKIP","INSUFFICIENT_MARGIN"); return; }
   MqlTradeRequest req={}; MqlTradeCheckResult check={}; MqlTradeResult result={};
   req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.magic=MAGIC; req.volume=LOT;
   req.type=type; req.price=price; req.sl=sl; req.tp=tp; req.deviation=DEVIATION;
   req.comment=signal>0 ? "QT2167_BUY" : "QT2167_SELL";
   if(!Filling(req.type_filling)) { Event("SKIP","UNSUPPORTED_FILLING"); return; }
   if(!OrderCheck(req,check) || check.retcode!=0)
   { Event("CHECK_REJECT",StringFormat("retcode=%u reason=%s",check.retcode,check.comment)); return; }
   MqlTick finalQuote;
   if(!V2167SignalAlive(TimeCurrent()-bar) || !ValidTick(finalQuote))
   { Event("SKIP","STALE_OR_REJECTED_POSTCHECK_QUOTE"); return; }
   // Do not send protection calculated from an obsolete quote. The consumed bar is not retried.
   if(finalQuote.bid!=quote.bid || finalQuote.ask!=quote.ask)
   { Event("SKIP","QUOTE_CHANGED_AFTER_CHECK"); return; }
   if((finalQuote.ask-finalQuote.bid)/_Point>MAX_SPREAD || GoldExposure() || !OrdersEnabled()) return;
   // Persist intent before submission. A process interruption cannot silently retry.
   if(!SaveIntent(bar,TimeCurrent(),price,sl,tp)) return;
   MqlTick sendQuote;
   if(!V2167SignalAlive(TimeCurrent()-bar) || !ValidTick(sendQuote) ||
      sendQuote.bid!=finalQuote.bid || sendQuote.ask!=finalQuote.ask ||
      (sendQuote.ask-sendQuote.bid)/_Point>MAX_SPREAD || GoldExposure() || !OrdersEnabled())
   {
      Event("SKIP","PRE_SEND_REVALIDATION_FAILED");
      SaveState(pendingKey,0.0);
      return;
   }
   bool sent=OrderSend(req,result);
   Event("ENTRY_RESULT",StringFormat("reason=%s requested=%.5f fill=%.5f sl=%.5f tp=%.5f spread=%.1f sent=%d retcode=%u order=%I64u deal=%I64u",
          reason,price,result.price,sl,tp,(finalQuote.ask-finalQuote.bid)/_Point,sent,result.retcode,result.order,result.deal));
   if(DefinitivelyRejected(result.retcode)) SaveState(pendingKey,0.0);
   else SubmissionReady();
}

int OnInit()
{
   if(InTester() && !V2167RunSignalTests()) return INIT_FAILED;
   if(_Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")<0 || !Finite(_Point)||_Point<=0)
      return INIT_PARAMETERS_INCORRECT;
   boundLogin=AccountInfoInteger(ACCOUNT_LOGIN);
   if(!AccountMatches()) return INIT_FAILED;
   if(!InTester() && InpEnableDemoOrders &&
      (InpExpectedDemoLogin<=0 || InpExpectedDemoLogin!=boundLogin)) return INIT_PARAMETERS_INCORRECT;
   if(!ValidVolume()) return INIT_FAILED;
   prefix=StringFormat("QT2167_%I64d_",boundLogin);
   ownerKey=prefix+"OWNER"; attemptKey=prefix+"ATTEMPT"; pendingKey=prefix+"PENDING";
   reqPriceKey=prefix+"REQ_PRICE"; reqSlKey=prefix+"REQ_SL"; reqTpKey=prefix+"REQ_TP";
   if(!AcquireOwner()) { Print("[QT21.67] Account instance lock unavailable"); return INIT_FAILED; }
   fastHandle=iMA(_Symbol,PERIOD_M1,14,0,MODE_EMA,PRICE_CLOSE);
   slowHandle=iMA(_Symbol,PERIOD_M1,50,0,MODE_EMA,PRICE_CLOSE);
   rsiHandle=iRSI(_Symbol,PERIOD_M1,14,PRICE_CLOSE);
   if(fastHandle==INVALID_HANDLE || slowHandle==INVALID_HANDLE || rsiHandle==INVALID_HANDLE)
      return INIT_FAILED;
   trade.SetExpertMagicNumber(MAGIC); trade.SetDeviationInPoints(DEVIATION); trade.SetAsyncMode(false);
   if(!trade.SetTypeFillingBySymbol(_Symbol) || !RestoreCooldown()) return INIT_FAILED;
   lastBar=iTime(_Symbol,PERIOD_M1,0);
   if(InpWriteJournal)
   {
      string filename=StringFormat("QT2167_%I64d_events.tsv",boundLogin);
      journal=FileOpen(filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_SHARE_READ|FILE_ANSI,'\t',CP_UTF8);
      if(journal==INVALID_HANDLE) return INIT_FAILED;
      FileSeek(journal,0,SEEK_END);
   }
   // Reconcile a crash-surviving submission before ordinary position management.
   if(GlobalVariableCheck(pendingKey) && GlobalVariableGet(pendingKey)>0) SubmissionReady();
   Event("INIT",StringFormat("version=21.67 login=%I64d magic=%I64u tester=%d demo_enabled=%d expected=%I64d lot=0.01 session=18-02 entry_cutoff=01:50",
                             boundLogin,MAGIC,InTester(),InpEnableDemoOrders,InpExpectedDemoLogin));
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!AccountMatches())
   {
      if(!accountErrorReported) { Event("ACCOUNT_CHANGED","All trade actions disabled"); accountErrorReported=true; }
      return;
   }
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   bool newBar=bar>0 && bar!=lastBar;
   MqlTick tick;
   bool validQuote=ValidTick(tick);
   if(validQuote)
   {
      if(GlobalVariableCheck(pendingKey) && GlobalVariableGet(pendingKey)>0) SubmissionReady();
      Manage(tick);
   }
   if(!newBar) return;
   lastBar=bar; // Consume the bar before any eligibility/indicator failure.
   if(!validQuote) { Event("SKIP","REJECTED_BAR_QUOTE"); return; }
   if(!V2167SignalAlive(TimeCurrent()-bar)) { Event("SKIP","STALE_SIGNAL_BAR"); return; }
   MqlDateTime now; TimeToStruct(bar,now);
   if(!V2167EntryMinute(now.hour,now.min)) return;
   if(GlobalVariableCheck(attemptKey) && GlobalVariableGet(attemptKey)>=(double)bar) return;
   V2167Frame frame={};
   if(!ReadFrame(bar,frame)) { Event("SKIP","INCOMPLETE_FRAME"); return; }
   string reason;
   int signal=V2167Signal(frame,reason);
   Event("BAR",StringFormat("bar=%s state=%s signal=%d momentum=%.6f rsi=%.2f",
                             TimeToString(bar),reason,signal,frame.momentum,frame.rsi));
   if(signal!=0) TryEntry(signal,reason,bar);
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(!AccountMatches() || trans.type!=TRADE_TRANSACTION_DEAL_ADD || trans.deal==0 ||
      !HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   ulong positionId=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
   if(entry==DEAL_ENTRY_IN)
   {
      if((ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)==MAGIC) SubmissionReady();
      return;
   }
   if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) return;
   double net,opened,closed; datetime stamp;
   if(!PositionLedger(positionId,net,opened,closed,stamp)) return;
   if(MathAbs(opened-closed)<1e-8)
   {
      lastExit=stamp;
      if(positionId==mustClosePositionId) mustClosePositionId=0;
      // Position identifier prevents partial exits or repeated callbacks becoming extra wins.
      string marker=prefix+"CLOSED_"+(string)positionId;
      if(!GlobalVariableCheck(marker))
      {
         Event("CLOSED",StringFormat("position=%I64u net=%.8f volume=%.4f deal=%I64u",
                                    positionId,net,opened,trans.deal));
         SaveState(marker,1.0);
      }
   }
}

double OnTester()
{
   Event("TEST_SUMMARY",StringFormat("trades=%.0f native_net=%.2f equityDD=%.2f",
         TesterStatistics(STAT_TRADES),TesterStatistics(STAT_PROFIT),TesterStatistics(STAT_EQUITY_DDREL_PERCENT)));
   return TesterStatistics(STAT_PROFIT);
}

void OnDeinit(const int reason)
{
   if(fastHandle!=INVALID_HANDLE) IndicatorRelease(fastHandle);
   if(slowHandle!=INVALID_HANDLE) IndicatorRelease(slowHandle);
   if(rsiHandle!=INVALID_HANDLE) IndicatorRelease(rsiHandle);
   if(ownerHeld) { GlobalVariableSetOnCondition(ownerKey,0.0,ownerToken); ownerHeld=false; }
   Event("DEINIT",StringFormat("reason=%d",reason));
   if(journal!=INVALID_HANDLE) FileClose(journal);
}
