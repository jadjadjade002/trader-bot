//+------------------------------------------------------------------+
//|                                     AegisPredator_v26_lab.mq5    |
//|                                  Copyright 2026, Quant Architect |
//|   Aegis Predator V26 Lab - Parametric V25 copy with research inputs|
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "26.00"
#property description "V26 Lab research: Parametric copy of V25. Defaults reproduce V25 baseline trades exactly. Adds parametric signals, geometry, filters, exits, risk scaling, and confluence score / sniper hold."
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Inputs -----------------------------------------------------------
input group "=== Execution Gates ==="
input bool     InpEnableSpreadGuard       = true;     // Absolute max spread gate
input int      InpMaxSpreadPts            = 60;       // Max spread (points); MetaQuotes-Demo median ~32, p90 ~50
input bool     InpEnableMarginGuard       = true;     // Margin pre-check
input double   InpMinMarginLevelPct       = 300.0;    // Min margin level % to open while a position exists (0 = off)
input bool     InpEnableHardSL            = true;     // Broker-side hard SL
input int      InpMaxHoldBars             = 60;       // Time exit (minutes of wall-clock holding)

input group "=== Signal Parameters (V25 parametric) ==="
input int      InpATRPeriod               = 14;       // M1 ATR period
input double   InpTrendStrengthMul        = 0.1;      // Min M5 EMA gap in M5 ATR units
input double   InpSignalSpreadMul         = 0.1;      // Max spread in M1 ATR units for entry
input int      InpM1FastEMA               = 9;        // M1 entry fast EMA period
input int      InpM1SlowEMA               = 20;       // M1 entry slow EMA period
input int      InpM5FastEMA               = 20;       // M5 trend fast EMA period
input int      InpM5SlowEMA               = 50;       // M5 trend slow EMA period
input int      InpSlopeBars               = 6;        // M5 slope lookback bars

input group "=== Geometry & Stops ==="
input double   InpStopLossATRMul          = 1.5;      // SL = max(mul*ATR, MinSL)
input double   InpTakeProfitRRMul         = 2.0;      // TP = SL * RR (when InpTpMode=0)
input int      InpMinSLPoints             = 150;      // Minimum SL (points)
input int      InpTpMode                  = 0;        // 0=RR multiple, 1=fixed price distance
input double   InpTpFixed                 = 1.5;      // Fixed TP distance in price units (when InpTpMode=1)
input double   InpSlFixedUSD              = 0.0;      // 0=off; if >0 SL distance fixed in price units instead of ATR
input double   InpLotSize                 = 0.01;     // Base trade volume
input ulong    InpMagicNumber             = 992600;   // Magic (default 992600)
input ulong    InpTargetAccount           = 0;        // 0 = any demo account

input group "=== Filters (Research) ==="
input int      InpHourStart               = 0;        // Start broker hour (0/24 = off)
input int      InpHourEnd                 = 24;       // End broker hour (0/24 = off)
input int      InpAtrFilterMode           = 0;        // 0=off, 1=M1 ATR > median(100), 2=M1 ATR < median(100)
input double   InpAdxMin                  = 0.0;      // 0=off; Min M5 ADX(14)
input bool     InpRequireM15Trend         = false;    // Require M15 EMA20/50 alignment
input bool     InpRequireH1Trend          = false;    // Require H1 EMA20/50 alignment
input double   InpSpikeAtrMul             = 0.0;      // 0=off; skip if any of last 5 bars range > mul*ATR
input int      InpCooldownAfterCloseMin   = 0;        // Cooldown minutes after position close (0=off)

input group "=== Exits (Research) ==="
input double   InpBreakevenAtR            = 0.0;      // 0=off; move SL to entry+spread when profit >= R*initial risk
input double   InpTrailAfterR             = 0.0;      // 0=off; start ATR trail when profit >= R*initial risk
input double   InpTrailAtrMul             = 1.0;      // ATR multiplier for trailing stop
input bool     InpEmaCrossExit            = false;    // Close when M1 EMA fast crosses slow against position
input int      InpTimeStopMin             = 0;        // 0=off; close if not at target after minutes
input double   InpTimeStopMinR            = 0.5;      // Target profit in R for TimeStopMin
input double   InpChandelierAtrMul        = 0.0;      // 0=off; trailing stop from highest/lowest close since entry
input int      InpCloseHour               = -1;       // -1=off; close all positions at/after this broker hour

input group "=== Risk & Sizing ==="
input bool     InpEnableRiskSizing        = true;     // Skip/shrink trade if planned SL loss > cap
input double   InpMaxRiskPct              = 5.0;      // Planned loss cap % of equity
input bool     InpEnableDayHalt           = true;     // Halt for rest of server day after daily loss
input double   InpDailyLossPct            = 8.0;      // Daily loss limit % of day-start equity
input double   InpEquityFloor             = 0.0;      // Halt below this equity (0 = off)
input int      InpMaxTradesPerDay         = 0;        // 0=off; max entries per server day
input double   InpLotAfterWinMul          = 1.0;      // Lot multiplier after a winning trade (1.0 = neutral)
input double   InpLotMaxMul               = 1.0;      // Max allowed lot multiplier cap (1.0 = cap at InpLotSize)
input double   InpDdScaleBelowPct         = 0.0;      // 0=off; reduce size if equity DD from peak >= pct
input double   InpDdScaleMul              = 0.5;      // Lot multiplier when in DD scale regime

input group "=== Confluence Score & Sniper Hold ==="
input int      InpMinScore                = 0;        // 0=off; skip entries below this confluence score (0-5)
input bool     InpSniperHold              = false;    // Enable sniper hold and chandelier trail for high scores
input int      InpSniperScore             = 5;        // Min score required to trigger sniper parameters
input double   InpSniperRR                = 4.0;      // TP RR multiple for sniper trades
input int      InpSniperHoldMin           = 240;      // Max hold bars (minutes) for sniper trades

input group "=== Circuit Breaker (net of costs, persistent) ==="
input bool     InpEnableCircuitBreaker    = true;
input int      InpMaxConsecutiveLosses    = 4;
input int      InpCooldownMinutes         = 90;

input group "=== Calendar Guards ==="
input bool     InpEnableFridayGuard       = true;     // No new entries / flatten on Friday
input int      InpFridayNoEntryHour       = 21;       // Broker hour: stop new entries
input int      InpFridayFlattenHour       = 22;       // Broker hour: close positions
input bool     InpEnableRolloverBlock     = true;     // No entries around server midnight
input int      InpRolloverBeforeMin       = 10;       // Minutes before midnight
input int      InpRolloverAfterMin        = 10;       // Minutes after midnight

input group "=== Order Handling ==="
input int      InpMaxRetries              = 3;
input int      InpRetryDelayMs            = 300;
input int      InpDeviationPts            = 20;

//--- Reject ledger ----------------------------------------------------
enum RejectReason
{
   RJ_BREAKER=0, RJ_DAYHALT, RJ_FLOOR, RJ_FRIDAY, RJ_ROLLOVER, RJ_SPREAD, RJ_ATR,
   RJ_NOSIGNAL, RJ_STOPS, RJ_RISK, RJ_MARGIN, RJ_MARGINLEVEL, RJ_FOREIGNPOS, RJ_ORDER,
   RJ_HOUR, RJ_ATR_FILTER, RJ_ADX, RJ_M15, RJ_H1, RJ_SPIKE, RJ_COOLDOWN_CLOSE, RJ_MAXTRADES, RJ_MINSCORE,
   RJ_COUNT
};

string RJ_NAMES[RJ_COUNT]={
   "breaker","day_halt","equity_floor","friday","rollover","spread","atr",
   "no_signal","stops_level","risk_cap","margin","margin_level","foreign_pos","order_fail",
   "hour","atr_filter","adx","m15_trend","h1_trend","spike","cooldown_close","max_trades","min_score"
};

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
string         gvPrefix = "";
string         v26State = "STARTING";

int trendFast = INVALID_HANDLE, trendSlow = INVALID_HANDLE, trendATR = INVALID_HANDLE;
int entryFast = INVALID_HANDLE, entrySlow = INVALID_HANDLE;
int m15Fast   = INVALID_HANDLE, m15Slow   = INVALID_HANDLE;
int h1Fast    = INVALID_HANDLE, h1Slow    = INVALID_HANDLE;
int adxHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
void Reject(RejectReason r){ rejects[r]++; }

void ReleaseAll()
{
   if(atrHandle!=INVALID_HANDLE) { IndicatorRelease(atrHandle); atrHandle=INVALID_HANDLE; }
   if(trendFast!=INVALID_HANDLE) { IndicatorRelease(trendFast); trendFast=INVALID_HANDLE; }
   if(trendSlow!=INVALID_HANDLE) { IndicatorRelease(trendSlow); trendSlow=INVALID_HANDLE; }
   if(trendATR!=INVALID_HANDLE)  { IndicatorRelease(trendATR);  trendATR=INVALID_HANDLE;  }
   if(entryFast!=INVALID_HANDLE) { IndicatorRelease(entryFast); entryFast=INVALID_HANDLE; }
   if(entrySlow!=INVALID_HANDLE) { IndicatorRelease(entrySlow); entrySlow=INVALID_HANDLE; }
   if(m15Fast!=INVALID_HANDLE)   { IndicatorRelease(m15Fast);   m15Fast=INVALID_HANDLE;   }
   if(m15Slow!=INVALID_HANDLE)   { IndicatorRelease(m15Slow);   m15Slow=INVALID_HANDLE;   }
   if(h1Fast!=INVALID_HANDLE)    { IndicatorRelease(h1Fast);    h1Fast=INVALID_HANDLE;    }
   if(h1Slow!=INVALID_HANDLE)    { IndicatorRelease(h1Slow);    h1Slow=INVALID_HANDLE;    }
   if(adxHandle!=INVALID_HANDLE) { IndicatorRelease(adxHandle); adxHandle=INVALID_HANDLE; }
}

bool InitV26Signal()
{
   trendFast = iMA(_Symbol, PERIOD_M5, InpM5FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   trendSlow = iMA(_Symbol, PERIOD_M5, InpM5SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   trendATR  = iATR(_Symbol, PERIOD_M5, 14);
   entryFast = iMA(_Symbol, PERIOD_M1, InpM1FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   entrySlow = iMA(_Symbol, PERIOD_M1, InpM1SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   m15Fast   = iMA(_Symbol, PERIOD_M15, 20, 0, MODE_EMA, PRICE_CLOSE);
   m15Slow   = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   h1Fast    = iMA(_Symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
   h1Slow    = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   adxHandle = iADX(_Symbol, PERIOD_M5, 14);

   return trendFast!=INVALID_HANDLE && trendSlow!=INVALID_HANDLE && trendATR!=INVALID_HANDLE
       && entryFast!=INVALID_HANDLE && entrySlow!=INVALID_HANDLE
       && m15Fast!=INVALID_HANDLE && m15Slow!=INVALID_HANDLE
       && h1Fast!=INVALID_HANDLE && h1Slow!=INVALID_HANDLE
       && adxHandle!=INVALID_HANDLE;
}

void V26Status(string state)
{
   v26State=state;
   Comment("AEGIS V26 LAB | DEMO RESEARCH | XAUUSD M1\nState: ",state,
           "\nAccount: ",AccountInfoInteger(ACCOUNT_LOGIN)," Magic: ",InpMagicNumber);
}

string RejectSummary()
{
   string s="";
   for(int i=0;i<RJ_COUNT;i++) s+=StringFormat("%s=%I64d ",RJ_NAMES[i],rejects[i]);
   return s;
}

void LogV26Health()
{
   PrintFormat("V26 HEALTH Account=%I64d Connected=%d Positions=%d State=%s Balance=%.2f Equity=%.2f FreeMargin=%.2f Signals=%I64d Orders=%I64d Rejects: %s",
      AccountInfoInteger(ACCOUNT_LOGIN),(int)TerminalInfoInteger(TERMINAL_CONNECTED),PositionsTotal(),v26State,
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoDouble(ACCOUNT_MARGIN_FREE),
      signalsSeen,ordersOK,RejectSummary());
}

void OnTimer(){ LogV26Health(); }

//--- Persistent state ---------------------------------------------------
string GV(string name){ return gvPrefix+name; }
string PosGV(ulong ticket, string tag){ return StringFormat("%sP_%I64u_%s", gvPrefix, ticket, tag); }

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

void DeletePositionState(ulong ticket)
{
   GlobalVariableDel(PosGV(ticket, "IRISK"));
   GlobalVariableDel(PosGV(ticket, "TIME"));
   GlobalVariableDel(PosGV(ticket, "HICLOSE"));
   GlobalVariableDel(PosGV(ticket, "LOCLOSE"));
   GlobalVariableDel(PosGV(ticket, "SNIPER"));
}

void SaveNewPositionState(ulong ticket, double openPrice, double slDist, bool isSniper)
{
   GlobalVariableSet(PosGV(ticket, "IRISK"), slDist);
   GlobalVariableSet(PosGV(ticket, "TIME"), (double)(long)TimeCurrent());
   GlobalVariableSet(PosGV(ticket, "HICLOSE"), openPrice);
   GlobalVariableSet(PosGV(ticket, "LOCLOSE"), openPrice);
   GlobalVariableSet(PosGV(ticket, "SNIPER"), isSniper ? 1.0 : 0.0);
   GlobalVariableSet(GV("ACTIVE_TICKET"), (double)ticket);
}

//--- Calendar & Time helpers --------------------------------------------
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
      Print("V26 BREAKER: HistorySelect failed, blocking entries (fail-closed)");
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
      PrintFormat("V26 CIRCUIT BREAKER: %d consecutive net losses. Paused until %s",
                  losses,TimeToString(cooldownUntil,TIME_DATE|TIME_MINUTES));
      return now<cooldownUntil;
   }
   return false;
}

//--- Deal history inspection helpers ------------------------------------
double GetLastClosedDealProfit()
{
   datetime now = TimeCurrent();
   if(!HistorySelect(now - 86400 * 7, now + 60)) return 0.0;
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if((ulong)HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      ENUM_DEAL_ENTRY en = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(en == DEAL_ENTRY_OUT || en == DEAL_ENTRY_INOUT || en == DEAL_ENTRY_OUT_BY)
      {
         return HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP)
              + HistoryDealGetDouble(tk, DEAL_COMMISSION) + HistoryDealGetDouble(tk, DEAL_FEE);
      }
   }
   return 0.0;
}

datetime GetLastClosedDealTime()
{
   datetime lastTime = 0;
   if(GlobalVariableCheck(GV("LASTCLOSETIME")))
      lastTime = (datetime)(long)GlobalVariableGet(GV("LASTCLOSETIME"));

   datetime now = TimeCurrent();
   if(HistorySelect(now - 86400 * 7, now + 60))
   {
      int total = HistoryDealsTotal();
      for(int i = total - 1; i >= 0; i--)
      {
         ulong tk = HistoryDealGetTicket(i);
         if(tk == 0) continue;
         if((ulong)HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
         if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
         ENUM_DEAL_ENTRY en = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk, DEAL_ENTRY);
         if(en == DEAL_ENTRY_OUT || en == DEAL_ENTRY_INOUT || en == DEAL_ENTRY_OUT_BY)
         {
            datetime dt = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
            if(dt > lastTime) lastTime = dt;
            break;
         }
      }
   }
   return lastTime;
}

int GetTodayTradesCount()
{
   datetime now = TimeCurrent();
   datetime dayStart = (now / 86400) * 86400;
   if(!HistorySelect(dayStart, now + 60)) return 0;
   int cnt = 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if((ulong)HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      ENUM_DEAL_ENTRY en = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(en == DEAL_ENTRY_IN) cnt++;
   }
   return cnt;
}

//--- Position management -------------------------------------------------
bool ReadClosed(int handle, int shift, double &value)
{
   double a[];
   if(CopyBuffer(handle, 0, shift, 1, a) != 1 || !MathIsValidNumber(a[0])) return false;
   value = a[0]; return true;
}

void ManageOpenPositions()
{
   symInfo.Refresh();
   symInfo.RefreshRates();
   double point = symInfo.Point();
   double tick = symInfo.TickSize();
   if(tick <= 0.0) tick = point;
   double stopsLvl = (double)symInfo.StopsLevel() * point;

   MqlRates r1[]; ArraySetAsSeries(r1, true);
   bool hasR1 = (CopyRates(_Symbol, PERIOD_M1, 1, 1, r1) == 1);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol() != _Symbol || posInfo.Magic() != InpMagicNumber) continue;

      ulong ticket = posInfo.Ticket();
      bool buy = (posInfo.PositionType() == POSITION_TYPE_BUY);
      double op = posInfo.PriceOpen();
      double curSL = posInfo.StopLoss();
      double curTP = posInfo.TakeProfit();
      datetime openTime = posInfo.Time();

      // Retrieve or reconstruct position state
      double initialRisk = 0.0;
      datetime entryTime = openTime;
      double highClose = op;
      double lowClose = op;
      bool isSniper = false;

      if(GlobalVariableCheck(PosGV(ticket, "IRISK")))
      {
         initialRisk = GlobalVariableGet(PosGV(ticket, "IRISK"));
         entryTime = (datetime)(long)GlobalVariableGet(PosGV(ticket, "TIME"));
         highClose = GlobalVariableGet(PosGV(ticket, "HICLOSE"));
         lowClose = GlobalVariableGet(PosGV(ticket, "LOCLOSE"));
         isSniper = (GlobalVariableGet(PosGV(ticket, "SNIPER")) > 0.5);
      }
      else
      {
         initialRisk = (curSL > 0.0) ? MathAbs(op - curSL) : InpStopLossATRMul * point * 100;
         entryTime = openTime;
         highClose = op;
         lowClose = op;
         isSniper = (StringFind(posInfo.Comment(), "Sniper") >= 0);

         MqlRates pbars[];
         int nb = CopyRates(_Symbol, PERIOD_M1, entryTime, TimeCurrent(), pbars);
         for(int k = 0; k < nb; k++)
         {
            if(pbars[k].close > highClose) highClose = pbars[k].close;
            if(pbars[k].close < lowClose)  lowClose  = pbars[k].close;
         }
         GlobalVariableSet(PosGV(ticket, "IRISK"), initialRisk);
         GlobalVariableSet(PosGV(ticket, "TIME"), (double)(long)entryTime);
         GlobalVariableSet(PosGV(ticket, "HICLOSE"), highClose);
         GlobalVariableSet(PosGV(ticket, "LOCLOSE"), lowClose);
         GlobalVariableSet(PosGV(ticket, "SNIPER"), isSniper ? 1.0 : 0.0);
         GlobalVariableSet(GV("ACTIVE_TICKET"), (double)ticket);
      }

      // Update highest/lowest close from closed bar 1
      if(hasR1 && r1[0].time >= entryTime)
      {
         if(r1[0].close > highClose)
         {
            highClose = r1[0].close;
            GlobalVariableSet(PosGV(ticket, "HICLOSE"), highClose);
         }
         if(r1[0].close < lowClose)
         {
            lowClose = r1[0].close;
            GlobalVariableSet(PosGV(ticket, "LOCLOSE"), lowClose);
         }
      }

      datetime now = TimeCurrent();
      long heldMin = (long)((now - entryTime) / 60);
      double curPx = buy ? symInfo.Bid() : symInfo.Ask();
      double profitDist = buy ? (curPx - op) : (op - curPx);

      // 1. Breakeven: InpBreakevenAtR (0 off)
      if(InpBreakevenAtR > 0.0 && curSL > 0.0 && initialRisk > 0.0)
      {
         bool alreadyBE = buy ? (curSL >= op) : (curSL <= op);
         if(!alreadyBE && profitDist >= InpBreakevenAtR * initialRisk)
         {
            double spr = (symInfo.Ask() - symInfo.Bid());
            double nsl = buy ? NormalizeDouble(MathCeil((op + spr) / tick) * tick, _Digits)
                             : NormalizeDouble(MathFloor((op - spr) / tick) * tick, _Digits);
            bool okDist = buy ? (curPx - nsl > stopsLvl) : (nsl - curPx > stopsLvl);
            if(okDist)
            {
               if((buy && nsl > curSL) || (!buy && (curSL == 0.0 || nsl < curSL)))
               {
                  if(trade.PositionModify(ticket, nsl, curTP))
                     curSL = nsl;
               }
            }
         }
      }

      // 2. Trailing stop: InpTrailAfterR (0 off)
      if(InpTrailAfterR > 0.0 && initialRisk > 0.0 && profitDist >= InpTrailAfterR * initialRisk)
      {
         double a[]; ArraySetAsSeries(a, true);
         if(CopyBuffer(atrHandle, 0, 1, 1, a) == 1 && a[0] > 0)
         {
            double trailDist = InpTrailAtrMul * a[0];
            double nsl = buy ? NormalizeDouble(MathFloor((curPx - trailDist) / tick) * tick, _Digits)
                             : NormalizeDouble(MathCeil((curPx + trailDist) / tick) * tick, _Digits);
            bool okDist = buy ? (curPx - nsl > stopsLvl) : (nsl - curPx > stopsLvl);
            if(okDist)
            {
               if((buy && nsl > curSL + tick) || (!buy && (curSL > 0.0 && nsl < curSL - tick)))
               {
                  if(trade.PositionModify(ticket, nsl, curTP))
                     curSL = nsl;
               }
            }
         }
      }

      // 3. Chandelier trailing stop: InpChandelierAtrMul (0 off) OR (isSniper && InpSniperHold)
      double chandMul = InpChandelierAtrMul;
      if(chandMul <= 0.0 && isSniper && InpSniperHold) chandMul = 3.0;
      if(chandMul > 0.0)
      {
         double a[]; ArraySetAsSeries(a, true);
         if(CopyBuffer(atrHandle, 0, 1, 1, a) == 1 && a[0] > 0)
         {
            double nsl = buy ? NormalizeDouble(MathFloor((highClose - chandMul * a[0]) / tick) * tick, _Digits)
                             : NormalizeDouble(MathCeil((lowClose + chandMul * a[0]) / tick) * tick, _Digits);
            bool okDist = buy ? (curPx - nsl > stopsLvl) : (nsl - curPx > stopsLvl);
            if(okDist)
            {
               if((buy && nsl > curSL + tick) || (!buy && (curSL > 0.0 && nsl < curSL - tick)))
               {
                  if(trade.PositionModify(ticket, nsl, curTP))
                     curSL = nsl;
               }
            }
         }
      }

      // --- Exit checks ---
      int maxHold = (isSniper && InpSniperHold) ? InpSniperHoldMin : InpMaxHoldBars;
      bool timeExit = heldMin >= maxHold;
      bool fridayExit = IsFridayFlatten(now);
      bool closeHourExit = (InpCloseHour >= 0 && now > 0);
      if(closeHourExit)
      {
         MqlDateTime dt; TimeToStruct(now, dt);
         closeHourExit = (dt.hour >= InpCloseHour);
      }

      bool emaCrossExit = false;
      if(InpEmaCrossExit)
      {
         double ef = 0, es = 0;
         if(ReadClosed(entryFast, 1, ef) && ReadClosed(entrySlow, 1, es))
         {
            if((buy && ef < es) || (!buy && ef > es)) emaCrossExit = true;
         }
      }

      bool timeStopExit = false;
      if(InpTimeStopMin > 0 && heldMin >= InpTimeStopMin && initialRisk > 0.0)
      {
         if(profitDist < InpTimeStopMinR * initialRisk) timeStopExit = true;
      }

      bool shouldClose = timeExit || fridayExit || closeHourExit || emaCrossExit || timeStopExit;
      if(!shouldClose) continue;

      ulong ms = GetTickCount64();
      if(ms - lastCloseTryMs < 2000) continue; // throttle close retries
      lastCloseTryMs = ms;

      string reasonStr = "TIME";
      if(fridayExit) reasonStr = "FRIDAY_FLATTEN";
      else if(closeHourExit) reasonStr = "CLOSE_HOUR";
      else if(emaCrossExit) reasonStr = "EMA_CROSS";
      else if(timeStopExit) reasonStr = "TIME_STOP";
      else if(isSniper && InpSniperHold) reasonStr = "SNIPER_TIME";

      if(trade.PositionClose(ticket, InpDeviationPts))
      {
         PrintFormat("V26 EXIT %s Ticket=%I64u held_min=%I64d retcode=%u",
                     reasonStr, ticket, heldMin, trade.ResultRetcode());
         DeletePositionState(ticket);
         GlobalVariableDel(GV("ACTIVE_TICKET"));
         GlobalVariableSet(GV("LASTCLOSETIME"), (double)(long)now);
      }
      else
      {
         PrintFormat("V26 EXIT FAILED Ticket=%I64u retcode=%u (%s) - will retry",
                     ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
      }
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
   { Print("V26 OrderCalcMargin failed. Error: ",GetLastError()); Reject(RJ_MARGIN); return false; }
   if(req>AccountInfoDouble(ACCOUNT_MARGIN_FREE)*0.70)
   {
      PrintFormat("V26 MARGIN GATE: required %.2f > 70%% of free %.2f",req,AccountInfoDouble(ACCOUNT_MARGIN_FREE));
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
   double baseLot = InpLotSize;

   if(InpLotAfterWinMul != 1.0)
   {
      double lastProfit = GetLastClosedDealProfit();
      if(lastProfit > 0.0) baseLot *= InpLotAfterWinMul;
   }

   if(InpLotMaxMul > 0.0)
   {
      baseLot = MathMin(baseLot, InpLotSize * InpLotMaxMul);
   }

   if(InpDdScaleBelowPct > 0.0)
   {
      double peakEq = GlobalVariableCheck(GV("PEAK_EQ")) ? GlobalVariableGet(GV("PEAK_EQ")) : 0.0;
      double curEq = AccountInfoDouble(ACCOUNT_EQUITY);
      if(curEq > peakEq) { peakEq = curEq; GlobalVariableSet(GV("PEAK_EQ"), peakEq); }
      double ddPct = (peakEq > 0.0) ? (peakEq - curEq) / peakEq * 100.0 : 0.0;
      if(ddPct >= InpDdScaleBelowPct)
      {
         baseLot *= InpDdScaleMul;
      }
   }

   double vol=NormalizeVolume(baseLot);
   if(vol<=0.0) return 0.0;
   if(!InpEnableRiskSizing) return vol;

   double pl=0.0;
   if(!OrderCalcProfit(type,_Symbol,1.0,price,sl,pl) || pl==0.0)
   { Print("V26 OrderCalcProfit failed. Error: ",GetLastError()); return 0.0; }
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
            PrintFormat("V26 REANCHOR FAILED Ticket=%I64u retcode=%u (%s)",posInfo.Ticket(),
                        trade.ResultRetcode(),trade.ResultRetcodeDescription());
      }
      return;
   }
}

bool OpenTrade(bool buy, double atr, long spreadPts, int score, bool isSniper)
{
   double point=symInfo.Point(), tick=symInfo.TickSize();
   if(tick<=0.0) tick=point;

   double slDist;
   if(InpSlFixedUSD > 0.0)
      slDist = MathMax(InpSlFixedUSD, InpMinSLPoints * point);
   else
      slDist = MathMax(InpStopLossATRMul * atr, InpMinSLPoints * point);

   // Respect broker stops/freeze level plus current spread
   double minDist=(double)MathMax(symInfo.StopsLevel(),symInfo.FreezeLevel())*point+spreadPts*point;
   if(slDist<minDist) slDist=minDist;

   double tpDist;
   if(isSniper && InpSniperHold)
      tpDist = slDist * InpSniperRR;
   else if(InpTpMode == 1)
      tpDist = InpTpFixed;
   else
      tpDist = slDist * InpTakeProfitRRMul;

   if(tpDist<minDist){ Reject(RJ_STOPS); return false; }
   ENUM_ORDER_TYPE type=buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;

   for(int attempt=1;attempt<=MathMax(1,InpMaxRetries);attempt++)
   {
      // A timed-out/connection-lost request may still have filled: never send a second order then.
      if(attempt>1 && HasOpenPosition())
      {
         Print("V26 RETRY ABORTED: position already open after uncertain retcode");
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

      PrintFormat("V26 %s attempt=%d price=%.2f SL=%.2f TP=%.2f vol=%.2f slDist=%.2f spread=%I64d score=%d%s",
                  buy?"BUY":"SELL",attempt,price,sl,tp,vol,slDist,spreadPts,score,isSniper?" [SNIPER]":"");

      string comment = StringFormat("AegisPredator V26 %s%s", buy ? "Buy" : "Sell", isSniper ? " [SNIPER]" : "");
      bool ok=buy?trade.Buy(vol,_Symbol,price,sl,tp,comment)
                 :trade.Sell(vol,_Symbol,price,sl,tp,comment);
      uint rc=trade.ResultRetcode();
      if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_DONE_PARTIAL))
      {
         ordersOK++;
         PrintFormat("V26 ORDER OK Side=%s Retcode=%u Order=%I64u Deal=%I64u fill=%.2f score=%d%s",
                     buy?"BUY":"SELL",rc,trade.ResultOrder(),trade.ResultDeal(),trade.ResultPrice(),score,isSniper?" [SNIPER]":"");
         ReanchorToFill(buy,slDist,tpDist,tick);

         for(int k=PositionsTotal()-1;k>=0;k--)
         {
            if(!posInfo.SelectByIndex(k)) continue;
            if(posInfo.Symbol()==_Symbol && posInfo.Magic()==InpMagicNumber)
            {
               SaveNewPositionState(posInfo.Ticket(), posInfo.PriceOpen(), slDist, isSniper);
               break;
            }
         }

         V26Status("ORDER_EXECUTED");
         return true;
      }
      PrintFormat("V26 ORDER FAILED attempt=%d retcode=%u (%s)",attempt,rc,trade.ResultRetcodeDescription());
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
   { Print("V26 BLOCKED: demo accounts only"); return INIT_FAILED; }
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1)
   { Print("V26 BLOCKED: requires XAUUSD M1"); return INIT_PARAMETERS_INCORRECT; }

   if(InpATRPeriod<1 || InpStopLossATRMul<=0 || InpTakeProfitRRMul<=0 || InpMinSLPoints<1
      || InpMaxHoldBars<1 || InpLotSize<=0 || InpMaxConsecutiveLosses<1 || InpCooldownMinutes<1
      || InpMaxRiskPct<=0 || InpMaxRiskPct>100 || InpDailyLossPct<=0 || InpDailyLossPct>100
      || InpFridayNoEntryHour<0 || InpFridayFlattenHour>23 || InpMaxRetries<1 || InpMaxSpreadPts<1
      || InpM1FastEMA<1 || InpM1SlowEMA<1 || InpM5FastEMA<1 || InpM5SlowEMA<1 || InpSlopeBars<1
      || InpHourStart<0 || InpHourStart>24 || InpHourEnd<0 || InpHourEnd>24)
      return INIT_PARAMETERS_INCORRECT;

   if(InpTargetAccount>0 && (ulong)AccountInfoInteger(ACCOUNT_LOGIN)!=InpTargetAccount)
   {
      PrintFormat("V26 BLOCKED: account mismatch. Running on %I64d, required %I64u",
                  AccountInfoInteger(ACCOUNT_LOGIN),InpTargetAccount);
      return INIT_FAILED;
   }
   if(!symInfo.Name(_Symbol)){ Print("V26: symbol info init failed"); return INIT_FAILED; }
   symInfo.Refresh();
   double step=symInfo.LotsStep();
   if(InpLotSize<symInfo.LotsMin() || InpLotSize>symInfo.LotsMax()
      || (step>0 && MathAbs(InpLotSize/step-MathRound(InpLotSize/step))>1e-6))
   {
      PrintFormat("V26 BLOCKED: InpLotSize %.4f invalid (min %.2f max %.2f step %.2f)",
                  InpLotSize,symInfo.LotsMin(),symInfo.LotsMax(),step);
      return INIT_PARAMETERS_INCORRECT;
   }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(InpDeviationPts);
   trade.SetTypeFillingBySymbol(_Symbol);

   gvPrefix=StringFormat("AV26_%I64d_%I64u_",AccountInfoInteger(ACCOUNT_LOGIN),InpMagicNumber);
   LoadState();
   ZeroMemory(rejects);

   atrHandle=iATR(_Symbol,PERIOD_M1,InpATRPeriod);
   if(atrHandle==INVALID_HANDLE){ Print("V26: ATR handle failed. Error: ",GetLastError()); return INIT_FAILED; }
   if(!InitV26Signal()){ ReleaseAll(); Print("V26 BLOCKED: indicator initialization failed"); return INIT_FAILED; }
   if(!EventSetTimer(300)){ ReleaseAll(); Print("V26 BLOCKED: heartbeat initialization failed"); return INIT_FAILED; }

   PrintFormat("V26 INIT margin_mode=%d lot=%.2f riskCap=%.1f%% dayHalt=%.1f%% breaker=%d/%dm friday=%d rollover=%d magic=%I64u",
               (int)AccountInfoInteger(ACCOUNT_MARGIN_MODE),InpLotSize,InpMaxRiskPct,InpDailyLossPct,
               InpMaxConsecutiveLosses,InpCooldownMinutes,(int)InpEnableFridayGuard,(int)InpEnableRolloverBlock,InpMagicNumber);
   V26Status("INITIALIZED_WAIT_NEXT_BAR");
   LogV26Health();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("V26 DEINIT reason=%d Signals=%I64d Orders=%I64d Rejects: %s",reason,signalsSeen,ordersOK,RejectSummary());
   ReleaseAll();
   Comment("");
}

//--- V24 signal, parametric inputs (default identical to V24/V25) -------
int ProposedSignal(double atr)
{
   double fast,slow,past,m5atr,e9,e20;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,InpSlopeBars,past) || !ReadClosed(trendATR,1,m5atr)
      || !ReadClosed(entryFast,1,e9) || !ReadClosed(entrySlow,1,e20) || m5atr<=0) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1) return 0;
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote)) return 0;
   if(quote.ask-quote.bid>InpSignalSpreadMul*atr || MathAbs((quote.ask+quote.bid)/2-r[0].close)>0.5*atr) return 0;
   if(fast>slow && fast>past && fast-slow>=InpTrendStrengthMul*m5atr && e9>e20
      && r[0].low<=e9 && r[0].close>e9 && r[0].close>r[0].open) return 1;
   if(fast<slow && fast<past && slow-fast>=InpTrendStrengthMul*m5atr && e9<e20
      && r[0].high>=e9 && r[0].close<e9 && r[0].close<r[0].open) return -1;
   return 0;
}

void OnTick()
{
   ManageOpenPositions();

   datetime currentBarTime=iTime(_Symbol,PERIOD_M1,0);
   if(currentBarTime<=0 || currentBarTime==lastBarTime) return;
   datetime prevBar=lastBarTime;
   lastBarTime=currentBarTime;
   if(prevBar==0) return;                       // wait for first completed bar after attach

   // Clean up state if active position closed via SL/TP
   if(!HasOpenPosition() && GlobalVariableCheck(GV("ACTIVE_TICKET")))
   {
      ulong actTk = (ulong)GlobalVariableGet(GV("ACTIVE_TICKET"));
      DeletePositionState(actTk);
      GlobalVariableDel(GV("ACTIVE_TICKET"));
      GlobalVariableSet(GV("LASTCLOSETIME"), (double)(long)TimeCurrent());
   }

   if(HasOpenPosition()){ V26Status("MANAGING_POSITION"); return; }

   if(IsCircuitBreakerActive()){ Reject(RJ_BREAKER); V26Status("CIRCUIT_BREAKER_PAUSE"); return; }
   if(IsDayHalted()){ V26Status("DAY_HALT"); return; }
   datetime now=TimeCurrent();
   if(IsFridayNoEntry(now)){ Reject(RJ_FRIDAY); return; }
   if(IsRolloverWindow(now)){ Reject(RJ_ROLLOVER); return; }
   if(HasForeignPositionOnNetting()){ Reject(RJ_FOREIGNPOS); return; }

   // Filter: Broker hour window (0/24 = off)
   if(InpHourStart!=0 || InpHourEnd!=24)
   {
      MqlDateTime dt; TimeToStruct(now, dt);
      bool inWindow = (InpHourStart < InpHourEnd)
                    ? (dt.hour >= InpHourStart && dt.hour < InpHourEnd)
                    : (dt.hour >= InpHourStart || dt.hour < InpHourEnd);
      if(!inWindow){ Reject(RJ_HOUR); return; }
   }

   // Filter: CloseHour block
   if(InpCloseHour >= 0)
   {
      MqlDateTime dt; TimeToStruct(now, dt);
      if(dt.hour >= InpCloseHour){ Reject(RJ_HOUR); return; }
   }

   // Filter: Cooldown after position close
   if(InpCooldownAfterCloseMin > 0)
   {
      datetime lastClose = GetLastClosedDealTime();
      if(lastClose > 0 && now < lastClose + InpCooldownAfterCloseMin * 60)
      { Reject(RJ_COOLDOWN_CLOSE); return; }
   }

   // Filter: Max trades per day
   if(InpMaxTradesPerDay > 0)
   {
      if(GetTodayTradesCount() >= InpMaxTradesPerDay)
      { Reject(RJ_MAXTRADES); return; }
   }

   symInfo.Refresh();
   long spread=symInfo.Spread();
   if(InpEnableSpreadGuard && spread>InpMaxSpreadPts){ Reject(RJ_SPREAD); return; }

   double a[];
   ArraySetAsSeries(a,true);
   if(CopyBuffer(atrHandle,0,1,1,a)<1 || a[0]<=0){ Reject(RJ_ATR); return; }
   double atr=a[0];

   // Median of last 100 closed bars of M1 ATR
   double atrMedian = 0.0;
   bool hasMedian = false;
   double hAtr[]; ArraySetAsSeries(hAtr, true);
   if(CopyBuffer(atrHandle, 0, 1, 100, hAtr) == 100)
   {
      ArraySort(hAtr);
      atrMedian = 0.5 * (hAtr[49] + hAtr[50]);
      hasMedian = true;
   }
   else if(InpAtrFilterMode != 0)
   {
      Reject(RJ_ATR); return; // fail-closed if filter required
   }

   // Filter: InpAtrFilterMode (0 off, 1 > median, 2 < median)
   if(InpAtrFilterMode == 1 && hasMedian && atr <= atrMedian){ Reject(RJ_ATR_FILTER); return; }
   if(InpAtrFilterMode == 2 && hasMedian && atr >= atrMedian){ Reject(RJ_ATR_FILTER); return; }

   // Filter: InpSpikeAtrMul (0 off; skip if any of last 5 bars range > mul*ATR)
   if(InpSpikeAtrMul > 0.0)
   {
      MqlRates sp[]; ArraySetAsSeries(sp, true);
      if(CopyRates(_Symbol, PERIOD_M1, 1, 5, sp) != 5){ Reject(RJ_SPIKE); return; }
      bool spike = false;
      for(int s = 0; s < 5; s++)
      {
         if(sp[s].high - sp[s].low > InpSpikeAtrMul * atr){ spike = true; break; }
      }
      if(spike){ Reject(RJ_SPIKE); return; }
   }

   // Filter: InpAdxMin (0 off; M5 ADX14)
   double adxVal = 0.0;
   bool hasAdx = ReadClosed(adxHandle, 1, adxVal);
   if(!hasAdx && InpAdxMin > 0.0){ Reject(RJ_ADX); return; }
   if(InpAdxMin > 0.0 && adxVal < InpAdxMin){ Reject(RJ_ADX); return; }

   int signal=ProposedSignal(atr);
   if(signal==0){ Reject(RJ_NOSIGNAL); V26Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }

   // Filter: M15 Trend alignment
   double m15F = 0.0, m15S = 0.0;
   bool hasM15 = ReadClosed(m15Fast, 1, m15F) && ReadClosed(m15Slow, 1, m15S);
   if(InpRequireM15Trend)
   {
      if(!hasM15){ Reject(RJ_M15); return; }
      if((signal == 1 && m15F <= m15S) || (signal == -1 && m15F >= m15S)){ Reject(RJ_M15); return; }
   }

   // Filter: H1 Trend alignment
   double h1F = 0.0, h1S = 0.0;
   bool hasH1 = ReadClosed(h1Fast, 1, h1F) && ReadClosed(h1Slow, 1, h1S);
   if(InpRequireH1Trend)
   {
      if(!hasH1){ Reject(RJ_H1); return; }
      if((signal == 1 && h1F <= h1S) || (signal == -1 && h1F >= h1S)){ Reject(RJ_H1); return; }
   }

   // Confluence Score calculation (0-5)
   // 1. M5 trend strong (>=0.3*M5ATR)
   // 2. M15 EMA20>50 agreement
   // 3. H1 agreement
   // 4. ADX > 25
   // 5. ATR above median
   double m5F = 0.0, m5S = 0.0, m5Atr = 0.0;
   bool hasM5 = ReadClosed(trendFast, 1, m5F) && ReadClosed(trendSlow, 1, m5S) && ReadClosed(trendATR, 1, m5Atr);

   int score = 0;
   if(hasM5 && m5Atr > 0.0)
   {
      if(signal == 1 && (m5F - m5S >= 0.3 * m5Atr)) score++;
      if(signal == -1 && (m5S - m5F >= 0.3 * m5Atr)) score++;
   }
   if(hasM15)
   {
      if(signal == 1 && m15F > m15S) score++;
      if(signal == -1 && m15F < m15S) score++;
   }
   if(hasH1)
   {
      if(signal == 1 && h1F > h1S) score++;
      if(signal == -1 && h1F < h1S) score++;
   }
   if(hasAdx && adxVal > 25.0) score++;
   if(hasMedian && atr > atrMedian) score++;

   // Filter: InpMinScore (0 off)
   if(InpMinScore > 0 && score < InpMinScore)
   {
      Reject(RJ_MINSCORE);
      return;
   }

   bool isSniper = InpSniperHold && (score >= InpSniperScore);

   signalsSeen++;
   V26Status(signal==1?"BUY_CANDIDATE":"SELL_CANDIDATE");
   OpenTrade(signal==1, atr, spread, score, isSniper);
}
//+------------------------------------------------------------------+
