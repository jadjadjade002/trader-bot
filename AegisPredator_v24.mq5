//+------------------------------------------------------------------+
//|                                          AegisPredator_v24.mq5   |
//|                                  Copyright 2026, Quant Architect |
//|       Aegis Predator V23 - Institutional Liquidity Engine        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Quant Architect"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "24.00"
#property description "V24 demo research: closed M5 trend, M1 pullback/reclaim, TP2R, BE off. Historical net remains negative."
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
void OnTick()
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
      { V24Status("MANAGING_POSITION"); return; }

   // Check Circuit Breaker (Guard 7)
   if(IsCircuitBreakerActive())
      { V24Status("CIRCUIT_BREAKER_PAUSE"); return; }

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

   signal=ProposedSignal(atr);
   if(signal == 0)
      { V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }
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

      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_BUY, InpLotSize, ask)) return;

      PrintFormat("AegisPredator V23 BUY SIGNAL: Ask=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (2.0R) Spread=%d",
                  ask, sl, InpEnableHardSL, slDistance, tp, currentSpread);
      
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

      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_SELL, InpLotSize, bid)) return;

      PrintFormat("AegisPredator V23 SELL SIGNAL: Bid=%.2f SL=%.2f (HardSL=%d dist=%.2f) TP=%.2f (2.0R) Spread=%d",
                  bid, sl, InpEnableHardSL, slDistance, tp, currentSpread);

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
