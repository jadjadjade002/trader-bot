//+------------------------------------------------------------------+
//|                                          exp_d2.mq5   |
//|                                  Copyright 2026, Quant Architect |
//|   Aegis Predator V25 - V24 signal + risk/execution hardening     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "26.00"
#property description "exp_d2 Bollinger fade in low-ADX regime"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Inputs -----------------------------------------------------------
input group "=== Execution Gates ==="
input bool     InpEnableSpreadGuard  = true;     // Absolute max spread gate
input int      InpMaxSpreadPts       = 60;       // Max spread (points); MetaQuotes-Demo median ~32, p90 ~50
input bool     InpEnableMarginGuard  = true;     // Margin pre-check
input double   InpMinMarginLevelPct  = 300.0;    // Min margin level % to open while a position exists (0 = off)
input bool     InpEnableHardSL       = true;     // Broker-side hard SL
input int      InpMaxHoldBars        = 60;       // Time exit (minutes of wall-clock holding)

input group "=== Signal & Position Parameters (V24 economics) ==="
input int      InpATRPeriod          = 14;       // M1 ATR period
input double   InpStopLossATRMul     = 1.5;      // SL = max(mul*ATR, MinSL)
input double   InpTakeProfitRRMul    = 2.0;      // TP = SL * RR
input int      InpMinSLPoints        = 150;      // Minimum SL (points)
input double   InpLotSize            = 0.01;     // Max trade volume
input ulong    InpMagicNumber        = 9930031;   // Magic (new, not shared with V23/V24)
input ulong    InpTargetAccount      = 0;        // 0 = any demo account

input group "=== exp_d2 ==="
input int InpBBPeriod=20;
input double InpBBDev=2.0;
input double InpADXMax=20.0;

input group "=== Cash Risk (V25) ==="
input bool     InpEnableRiskSizing   = true;     // Skip/shrink trade if planned SL loss > cap
input double   InpMaxRiskPct         = 5.0;      // Planned loss cap % of equity (2.5 blocks ~all entries at $70, see R10)
input bool     InpEnableDayHalt      = true;     // Halt for rest of server day after daily loss
input double   InpDailyLossPct       = 8.0;      // Daily loss limit % of day-start equity
input double   InpEquityFloor        = 0.0;      // Halt below this equity (0 = off)

input group "=== Circuit Breaker (net of costs, persistent) ==="
input bool     InpEnableCircuitBreaker = true;
input int      InpMaxConsecutiveLosses = 4;
input int      InpCooldownMinutes      = 90;

input group "=== Calendar Guards ==="
input bool     InpEnableFridayGuard  = true;     // No new entries / flatten on Friday
input int      InpFridayNoEntryHour  = 21;       // Broker hour: stop new entries
input int      InpFridayFlattenHour  = 22;       // Broker hour: close positions
input bool     InpEnableRolloverBlock = true;    // No entries around server midnight
input int      InpRolloverBeforeMin  = 10;       // Minutes before midnight
input int      InpRolloverAfterMin   = 10;       // Minutes after midnight

input group "=== Order Handling ==="
input int      InpMaxRetries         = 3;
input int      InpRetryDelayMs       = 300;
input int      InpDeviationPts       = 20;

//--- Reject ledger ----------------------------------------------------
enum RejectReason
{
   RJ_BREAKER=0, RJ_DAYHALT, RJ_FLOOR, RJ_FRIDAY, RJ_ROLLOVER, RJ_SPREAD, RJ_ATR,
   RJ_NOSIGNAL, RJ_STOPS, RJ_RISK, RJ_MARGIN, RJ_MARGINLEVEL, RJ_FOREIGNPOS, RJ_ORDER, RJ_COUNT
};
string RJ_NAMES[RJ_COUNT]={"breaker","day_halt","equity_floor","friday","rollover","spread","atr",
                           "no_signal","stops_level","risk_cap","margin","margin_level","foreign_pos","order_fail"};
long   rejects[RJ_COUNT];
long   signalsSeen=0, ordersOK=0;

//--- Globals ----------------------------------------------------------
CTrade         trade;
CPositionInfo  posInfo;
CSymbolInfo    symInfo;

int            atrHandle = INVALID_HANDLE;
datetime       lastBarTime = 0;
datetime       cooldownUntil = 0;
ulong          lastBreakerPosId = 0;
ulong          lastCloseTryMs = 0;
string         gvPrefix="";
string         v25State="exp_d2";

int trendFast=INVALID_HANDLE,trendSlow=INVALID_HANDLE,trendATR=INVALID_HANDLE;
int entryFast=INVALID_HANDLE,entrySlow=INVALID_HANDLE;

//+------------------------------------------------------------------+
void Reject(RejectReason r){ rejects[r]++; }

void ReleaseAll()
{
   if(atrHandle!=INVALID_HANDLE){ IndicatorRelease(atrHandle); atrHandle=INVALID_HANDLE; }
   if(trendFast!=INVALID_HANDLE){ IndicatorRelease(trendFast); trendFast=INVALID_HANDLE; }
   if(trendSlow!=INVALID_HANDLE){ IndicatorRelease(trendSlow); trendSlow=INVALID_HANDLE; }
   if(trendATR!=INVALID_HANDLE){ IndicatorRelease(trendATR); trendATR=INVALID_HANDLE; }
   if(entryFast!=INVALID_HANDLE){ IndicatorRelease(entryFast); entryFast=INVALID_HANDLE; }
   if(entrySlow!=INVALID_HANDLE){ IndicatorRelease(entrySlow); entrySlow=INVALID_HANDLE; }
}

bool InitV25Signal()
{
   trendFast=iMA(_Symbol,PERIOD_M5,20,0,MODE_EMA,PRICE_CLOSE);
   trendSlow=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE);
   trendATR=iATR(_Symbol,PERIOD_M5,14);
   entryFast=iMA(_Symbol,PERIOD_M1,9,0,MODE_EMA,PRICE_CLOSE);
   entrySlow=iMA(_Symbol,PERIOD_M1,20,0,MODE_EMA,PRICE_CLOSE);
   return trendFast!=INVALID_HANDLE && trendSlow!=INVALID_HANDLE && trendATR!=INVALID_HANDLE
      && entryFast!=INVALID_HANDLE && entrySlow!=INVALID_HANDLE;
}

void V25Status(string state)
{
   v25State=state;
   Comment("AEGIS V25 | DEMO RESEARCH | XAUUSD M1\nState: ",state,
           "\nAccount: ",AccountInfoInteger(ACCOUNT_LOGIN)," Magic: ",InpMagicNumber);
}

string RejectSummary()
{
   string s="";
   for(int i=0;i<RJ_COUNT;i++) s+=StringFormat("%s=%I64d ",RJ_NAMES[i],rejects[i]);
   return s;
}

void LogV25Health()
{
   PrintFormat("V25 HEALTH Account=%I64d Connected=%d Positions=%d State=%s Balance=%.2f Equity=%.2f FreeMargin=%.2f Signals=%I64d Orders=%I64d Rejects: %s",
      AccountInfoInteger(ACCOUNT_LOGIN),(int)TerminalInfoInteger(TERMINAL_CONNECTED),PositionsTotal(),v25State,
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoDouble(ACCOUNT_MARGIN_FREE),
      signalsSeen,ordersOK,RejectSummary());
}

void OnTimer(){ LogV25Health(); }

//--- Persistent state ---------------------------------------------------
string GV(string name){ return gvPrefix+name; }

void LoadState()
{
   if(GlobalVariableCheck(GV("COOLDOWN"))) cooldownUntil=(datetime)(long)GlobalVariableGet(GV("COOLDOWN"));
   if(GlobalVariableCheck(GV("LASTPOS"))) lastBreakerPosId=(ulong)GlobalVariableGet(GV("LASTPOS"));
}
void SaveState()
{
   GlobalVariableSet(GV("COOLDOWN"),(double)(long)cooldownUntil);
   GlobalVariableSet(GV("LASTPOS"),(double)lastBreakerPosId);
}

//--- Calendar helpers ---------------------------------------------------
bool IsFridayNoEntry(datetime t)
{
   if(!InpEnableFridayGuard) return false;
   MqlDateTime d; TimeToStruct(t,d);
   return d.day_of_week==5 && d.hour>=InpFridayNoEntryHour;
}
bool IsFridayFlatten(datetime t)
{
   if(!InpEnableFridayGuard) return false;
   MqlDateTime d; TimeToStruct(t,d);
   return d.day_of_week==5 && d.hour>=InpFridayFlattenHour;
}
bool IsRolloverWindow(datetime t)
{
   if(!InpEnableRolloverBlock) return false;
   MqlDateTime d; TimeToStruct(t,d);
   int m=d.hour*60+d.min;
   return m>=1440-InpRolloverBeforeMin || m<InpRolloverAfterMin;
}

//--- Daily loss / equity floor -----------------------------------------
bool IsDayHalted()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(InpEquityFloor>0.0 && eq<InpEquityFloor){ Reject(RJ_FLOOR); return true; }
   if(!InpEnableDayHalt) return false;
   long day=(long)(TimeCurrent()/86400);
   double dayKey=GlobalVariableCheck(GV("DAYKEY"))?GlobalVariableGet(GV("DAYKEY")):-1;
   if((long)dayKey!=day)
   {
      GlobalVariableSet(GV("DAYKEY"),(double)day);
      GlobalVariableSet(GV("DAYEQ"),eq);
      return false;
   }
   double startEq=GlobalVariableGet(GV("DAYEQ"));
   if(startEq>0.0 && eq<startEq*(1.0-InpDailyLossPct/100.0)){ Reject(RJ_DAYHALT); return true; }
   return false;
}

//--- Circuit breaker: net P/L per closed position, persistent -----------
bool IsCircuitBreakerActive()
{
   if(!InpEnableCircuitBreaker) return false;
   datetime now=TimeCurrent();
   if(now<cooldownUntil) return true;

   if(!HistorySelect(now-86400*7,now+60))
   {
      Print("V25 BREAKER: HistorySelect failed, blocking entries (fail-closed)");
      return true;
   }
   ulong   ids[]; double net[]; datetime lastOut[]; bool closed[];
   ArrayResize(ids,0); ArrayResize(net,0); ArrayResize(lastOut,0); ArrayResize(closed,0);
   int order[]; ArrayResize(order,0);
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
   {
      ulong tk=HistoryDealGetTicket(i);
      if(tk==0) continue;
      if((ulong)HistoryDealGetInteger(tk,DEAL_MAGIC)!=InpMagicNumber) continue;
      if(HistoryDealGetString(tk,DEAL_SYMBOL)!=_Symbol) continue;
      ENUM_DEAL_TYPE dt=(ENUM_DEAL_TYPE)HistoryDealGetInteger(tk,DEAL_TYPE);
      if(dt!=DEAL_TYPE_BUY && dt!=DEAL_TYPE_SELL) continue;
      ulong pid=(ulong)HistoryDealGetInteger(tk,DEAL_POSITION_ID);
      int idx=-1;
      for(int k=ArraySize(ids)-1;k>=0;k--) if(ids[k]==pid){ idx=k; break; }
      if(idx<0)
      {
         idx=ArraySize(ids);
         ArrayResize(ids,idx+1); ArrayResize(net,idx+1); ArrayResize(lastOut,idx+1); ArrayResize(closed,idx+1);
         ids[idx]=pid; net[idx]=0.0; lastOut[idx]=0; closed[idx]=false;
      }
      net[idx]+=HistoryDealGetDouble(tk,DEAL_PROFIT)+HistoryDealGetDouble(tk,DEAL_SWAP)
               +HistoryDealGetDouble(tk,DEAL_COMMISSION)+HistoryDealGetDouble(tk,DEAL_FEE);
      ENUM_DEAL_ENTRY en=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk,DEAL_ENTRY);
      if(en==DEAL_ENTRY_OUT || en==DEAL_ENTRY_INOUT || en==DEAL_ENTRY_OUT_BY)
      {
         if(!closed[idx]){ int n=ArraySize(order); ArrayResize(order,n+1); order[n]=idx; }
         closed[idx]=true;
         lastOut[idx]=(datetime)HistoryDealGetInteger(tk,DEAL_TIME);
      }
   }
   int losses=0; ulong newestPos=0; datetime newestOut=0;
   for(int j=ArraySize(order)-1;j>=0;j--)
   {
      int idx=order[j];
      if(newestPos==0){ newestPos=ids[idx]; newestOut=lastOut[idx]; }
      if(net[idx]<0.0) losses++;
      else if(net[idx]>0.0) break;
   }
   if(losses>=InpMaxConsecutiveLosses && newestPos!=lastBreakerPosId)
   {
      lastBreakerPosId=newestPos;
      cooldownUntil=newestOut+InpCooldownMinutes*60;
      SaveState();
      PrintFormat("V25 CIRCUIT BREAKER: %d consecutive net losses. Paused until %s",
                  losses,TimeToString(cooldownUntil,TIME_DATE|TIME_MINUTES));
      return now<cooldownUntil;
   }
   return false;
}

//--- Position management -------------------------------------------------
void ManageOpenPositions()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol()!=_Symbol || posInfo.Magic()!=InpMagicNumber) continue;

      datetime now=TimeCurrent();
      long heldMin=(long)((now-posInfo.Time())/60);
      bool timeExit=heldMin>=InpMaxHoldBars;
      bool fridayExit=IsFridayFlatten(now);
      if(!timeExit && !fridayExit) continue;

      ulong ms=GetTickCount64();
      if(ms-lastCloseTryMs<2000) continue;   // throttle close retries
      lastCloseTryMs=ms;
      if(trade.PositionClose(posInfo.Ticket(),InpDeviationPts))
         PrintFormat("V25 EXIT %s Ticket=%I64u held_min=%I64d retcode=%u",
                     fridayExit?"FRIDAY_FLATTEN":"TIME",posInfo.Ticket(),heldMin,trade.ResultRetcode());
      else
         PrintFormat("V25 EXIT FAILED Ticket=%I64u retcode=%u (%s) - will retry",
                     posInfo.Ticket(),trade.ResultRetcode(),trade.ResultRetcodeDescription());
   }
}

bool HasOpenPosition()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol()==_Symbol && posInfo.Magic()==InpMagicNumber) return true;
   }
   return false;
}

// On netting accounts a foreign position on the same symbol would be merged with ours.
bool HasForeignPositionOnNetting()
{
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return false;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol()==_Symbol && posInfo.Magic()!=InpMagicNumber) return true;
   }
   return false;
}

bool CheckMargin(ENUM_ORDER_TYPE type,double volume,double price)
{
   double req=0.0;
   if(!OrderCalcMargin(type,_Symbol,volume,price,req))
   { Print("V25 OrderCalcMargin failed. Error: ",GetLastError()); Reject(RJ_MARGIN); return false; }
   if(req>AccountInfoDouble(ACCOUNT_MARGIN_FREE)*0.70)
   {
      PrintFormat("V25 MARGIN GATE: required %.2f > 70%% of free %.2f",req,AccountInfoDouble(ACCOUNT_MARGIN_FREE));
      Reject(RJ_MARGIN); return false;
   }
   double lvl=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(InpMinMarginLevelPct>0.0 && AccountInfoDouble(ACCOUNT_MARGIN)>0.0 && lvl<InpMinMarginLevelPct)
   { Reject(RJ_MARGINLEVEL); return false; }
   return true;
}

//--- Volume sizing by planned cash loss ---------------------------------
double NormalizeVolume(double v)
{
   double step=symInfo.LotsStep(), mn=symInfo.LotsMin(), mx=symInfo.LotsMax();
   if(step<=0.0) step=0.01;
   v=MathFloor(v/step+1e-9)*step;
   v=MathMin(v,mx);
   if(v<mn-1e-12) return 0.0;
   return NormalizeDouble(v,2);
}

double SizedVolume(ENUM_ORDER_TYPE type,double price,double sl)
{
   double vol=NormalizeVolume(InpLotSize);
   if(vol<=0.0) return 0.0;
   if(!InpEnableRiskSizing) return vol;
   double pl=0.0;
   if(!OrderCalcProfit(type,_Symbol,1.0,price,sl,pl) || pl==0.0)
   { Print("V25 OrderCalcProfit failed. Error: ",GetLastError()); return 0.0; }
   double lossPerLot=MathAbs(pl);
   double maxLoss=AccountInfoDouble(ACCOUNT_EQUITY)*InpMaxRiskPct/100.0;
   double fit=maxLoss/lossPerLot;
   if(fit<vol) vol=NormalizeVolume(fit);
   return vol;
}

//--- Order sending with retry and post-fill SL/TP re-anchoring -----------
bool RetryableRetcode(uint rc)
{
   return rc==TRADE_RETCODE_REQUOTE || rc==TRADE_RETCODE_PRICE_CHANGED || rc==TRADE_RETCODE_PRICE_OFF
       || rc==TRADE_RETCODE_TOO_MANY_REQUESTS
       || rc==TRADE_RETCODE_CONNECTION || rc==TRADE_RETCODE_TIMEOUT || rc==TRADE_RETCODE_LOCKED;
}

void ComputeLevels(bool buy,double price,double slDist,double tpDist,double tick,double &sl,double &tp)
{
   if(buy)
   {
      sl=InpEnableHardSL?NormalizeDouble(MathFloor((price-slDist)/tick)*tick,_Digits):0.0;
      tp=NormalizeDouble(MathCeil((price+tpDist)/tick)*tick,_Digits);
   }
   else
   {
      sl=InpEnableHardSL?NormalizeDouble(MathCeil((price+slDist)/tick)*tick,_Digits):0.0;
      tp=NormalizeDouble(MathFloor((price-tpDist)/tick)*tick,_Digits);
   }
}

void ReanchorToFill(bool buy,double slDist,double tpDist,double tick)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol()!=_Symbol || posInfo.Magic()!=InpMagicNumber) continue;
      double sl,tp;
      ComputeLevels(buy,posInfo.PriceOpen(),slDist,tpDist,tick,sl,tp);
      if(MathAbs(sl-posInfo.StopLoss())>=tick || MathAbs(tp-posInfo.TakeProfit())>=tick)
      {
         if(!trade.PositionModify(posInfo.Ticket(),sl,tp))
            PrintFormat("V25 REANCHOR FAILED Ticket=%I64u retcode=%u (%s)",posInfo.Ticket(),
                        trade.ResultRetcode(),trade.ResultRetcodeDescription());
      }
      return;
   }
}

bool OpenTrade(bool buy,double atr,long spreadPts)
{
   double point=symInfo.Point(), tick=symInfo.TickSize();
   if(tick<=0.0) tick=point;
   double slDist=MathMax(InpStopLossATRMul*atr,InpMinSLPoints*point);
   // Respect broker stops/freeze level plus current spread
   double minDist=(double)MathMax(symInfo.StopsLevel(),symInfo.FreezeLevel())*point+spreadPts*point;
   if(slDist<minDist) slDist=minDist;
   double tpDist=slDist*InpTakeProfitRRMul;
   if(tpDist<minDist){ Reject(RJ_STOPS); return false; }
   ENUM_ORDER_TYPE type=buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;

   for(int attempt=1;attempt<=MathMax(1,InpMaxRetries);attempt++)
   {
      // A timed-out/connection-lost request may still have filled: never send a second order then.
      if(attempt>1 && HasOpenPosition())
      {
         Print("V25 RETRY ABORTED: position already open after uncertain retcode");
         ordersOK++;
         ReanchorToFill(buy,slDist,tpDist,tick);
         return true;
      }
      symInfo.RefreshRates();
      double price=buy?symInfo.Ask():symInfo.Bid();
      double sl,tp;
      ComputeLevels(buy,price,slDist,tpDist,tick,sl,tp);

      double vol=SizedVolume(type,price,InpEnableHardSL?sl:(buy?price-slDist:price+slDist));
      if(vol<=0.0){ Reject(RJ_RISK); return false; }
      if(InpEnableMarginGuard && !CheckMargin(type,vol,price)) return false;

      PrintFormat("V25 %s attempt=%d price=%.2f SL=%.2f TP=%.2f vol=%.2f slDist=%.2f spread=%I64d",
                  buy?"BUY":"SELL",attempt,price,sl,tp,vol,slDist,spreadPts);
      bool ok=buy?trade.Buy(vol,_Symbol,price,sl,tp,"AegisPredator V25 Buy")
                 :trade.Sell(vol,_Symbol,price,sl,tp,"AegisPredator V25 Sell");
      uint rc=trade.ResultRetcode();
      if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_DONE_PARTIAL))
      {
         ordersOK++;
         PrintFormat("V25 ORDER OK Side=%s Retcode=%u Order=%I64u Deal=%I64u fill=%.2f",
                     buy?"BUY":"SELL",rc,trade.ResultOrder(),trade.ResultDeal(),trade.ResultPrice());
         ReanchorToFill(buy,slDist,tpDist,tick);
         V25Status("ORDER_EXECUTED");
         return true;
      }
      PrintFormat("V25 ORDER FAILED attempt=%d retcode=%u (%s)",attempt,rc,trade.ResultRetcodeDescription());
      if(!RetryableRetcode(rc)) break;
      Sleep(InpRetryDelayMs);
   }
   Reject(RJ_ORDER);
   return false;
}

//+------------------------------------------------------------------+
int OnInit()
{
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
   { Print("V25 BLOCKED: demo accounts only"); return INIT_FAILED; }
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1)
   { Print("V25 BLOCKED: requires XAUUSD M1"); return INIT_PARAMETERS_INCORRECT; }
   if(InpATRPeriod<1 || InpStopLossATRMul<=0 || InpTakeProfitRRMul<=0 || InpMinSLPoints<1
      || InpMaxHoldBars<1 || InpLotSize<=0 || InpMaxConsecutiveLosses<1 || InpCooldownMinutes<1
      || InpMaxRiskPct<=0 || InpMaxRiskPct>100 || InpDailyLossPct<=0 || InpDailyLossPct>100
      || InpFridayNoEntryHour<0 || InpFridayFlattenHour>23 || InpMaxRetries<1 || InpMaxSpreadPts<1)
      return INIT_PARAMETERS_INCORRECT;
   if(InpTargetAccount>0 && (ulong)AccountInfoInteger(ACCOUNT_LOGIN)!=InpTargetAccount)
   {
      PrintFormat("V25 BLOCKED: account mismatch. Running on %I64d, required %I64u",
                  AccountInfoInteger(ACCOUNT_LOGIN),InpTargetAccount);
      return INIT_FAILED;
   }
   if(!symInfo.Name(_Symbol)){ Print("V25: symbol info init failed"); return INIT_FAILED; }
   symInfo.Refresh();
   double step=symInfo.LotsStep();
   if(InpLotSize<symInfo.LotsMin() || InpLotSize>symInfo.LotsMax()
      || (step>0 && MathAbs(InpLotSize/step-MathRound(InpLotSize/step))>1e-6))
   {
      PrintFormat("V25 BLOCKED: InpLotSize %.4f invalid (min %.2f max %.2f step %.2f)",
                  InpLotSize,symInfo.LotsMin(),symInfo.LotsMax(),step);
      return INIT_PARAMETERS_INCORRECT;
   }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(InpDeviationPts);
   trade.SetTypeFillingBySymbol(_Symbol);

   gvPrefix=StringFormat("EXPD2_%I64d_%I64u_",AccountInfoInteger(ACCOUNT_LOGIN),InpMagicNumber);
   LoadState();
   ZeroMemory(rejects);

   atrHandle=iATR(_Symbol,PERIOD_M1,InpATRPeriod);
   if(atrHandle==INVALID_HANDLE){ Print("V25: ATR handle failed. Error: ",GetLastError()); return INIT_FAILED; }
   if(!InitV25Signal()){ ReleaseAll(); Print("V25 BLOCKED: indicator initialization failed"); return INIT_FAILED; }
   if(!EventSetTimer(300)){ ReleaseAll(); Print("V25 BLOCKED: heartbeat initialization failed"); return INIT_FAILED; }

   PrintFormat("V25 INIT margin_mode=%d lot=%.2f riskCap=%.1f%% dayHalt=%.1f%% breaker=%d/%dm friday=%d rollover=%d",
               (int)AccountInfoInteger(ACCOUNT_MARGIN_MODE),InpLotSize,InpMaxRiskPct,InpDailyLossPct,
               InpMaxConsecutiveLosses,InpCooldownMinutes,(int)InpEnableFridayGuard,(int)InpEnableRolloverBlock);
   V25Status("INITIALIZED_WAIT_NEXT_BAR");
   LogV25Health();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("V25 DEINIT reason=%d Signals=%I64d Orders=%I64d Rejects: %s",reason,signalsSeen,ordersOK,RejectSummary());
   ReleaseAll();
   Comment("");
}

void OnTick()
{
   ManageOpenPositions();

   datetime currentBarTime=iTime(_Symbol,PERIOD_M1,0);
   if(currentBarTime<=0 || currentBarTime==lastBarTime) return;
   datetime prevBar=lastBarTime;
   lastBarTime=currentBarTime;
   if(prevBar==0) return;                       // wait for first completed bar after attach

   if(HasOpenPosition()){ V25Status("MANAGING_POSITION"); return; }

   if(IsCircuitBreakerActive()){ Reject(RJ_BREAKER); V25Status("CIRCUIT_BREAKER_PAUSE"); return; }
   if(IsDayHalted()){ V25Status("DAY_HALT"); return; }
   datetime now=TimeCurrent();
   if(IsFridayNoEntry(now)){ Reject(RJ_FRIDAY); return; }
   if(IsRolloverWindow(now)){ Reject(RJ_ROLLOVER); return; }
   if(HasForeignPositionOnNetting()){ Reject(RJ_FOREIGNPOS); return; }

   symInfo.Refresh();
   long spread=symInfo.Spread();
   if(InpEnableSpreadGuard && spread>InpMaxSpreadPts){ Reject(RJ_SPREAD); return; }

   double a[];
   ArraySetAsSeries(a,true);
   if(CopyBuffer(atrHandle,0,1,1,a)<1 || a[0]<=0){ Reject(RJ_ATR); return; }
   double atr=a[0];

   int signal=ProposedSignal(atr);
   if(signal==0){ Reject(RJ_NOSIGNAL); V25Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }
   signalsSeen++;
   V25Status(signal==1?"BUY_CANDIDATE":"SELL_CANDIDATE");
   OpenTrade(signal==1,atr,spread);
}

//--- V24 signal, unchanged (parity-tested byte-for-byte) -----------------
bool ReadClosed(int handle,int shift,double &value)
{
   double a[];
   if(CopyBuffer(handle,0,shift,1,a)!=1 || !MathIsValidNumber(a[0])) return false;
   value=a[0];return true;
}

int bbH=INVALID_HANDLE, adxH=INVALID_HANDLE;
int ProposedSignal(double atr)
{
   if(bbH==INVALID_HANDLE) bbH=iBands(_Symbol,PERIOD_M1,InpBBPeriod,0,InpBBDev,PRICE_CLOSE);
   if(adxH==INVALID_HANDLE) adxH=iADX(_Symbol,PERIOD_M5,14);
   if(bbH==INVALID_HANDLE || adxH==INVALID_HANDLE) return 0;
   double up,lo,adx;
   if(!ReadBuf(bbH,1,1,up) || !ReadBuf(bbH,2,1,lo) || !ReadBuf(adxH,0,1,adx)) return 0;
   if(adx>=InpADXMax) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1) return 0;
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote)) return 0;
   if(quote.ask-quote.bid>0.1*atr) return 0;
   if(r[0].low<lo && r[0].close>lo && r[0].close>r[0].open) return 1;
   if(r[0].high>up && r[0].close<up && r[0].close<r[0].open) return -1;
   return 0;
}
bool ReadBuf(int handle,int buf,int shift,double &value)
{
   double a[];
   if(CopyBuffer(handle,buf,shift,1,a)!=1 || !MathIsValidNumber(a[0])) return false;
   value=a[0];return true;
}
