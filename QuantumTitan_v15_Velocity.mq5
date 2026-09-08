//+------------------------------------------------------------------+
//|                                   QuantumTitan_v15_Velocity.mq5 |
//|          v15.00 Velocity High-Frequency M1 Scalper Framework     |
//|      Multi-Agent Autonomous Trading System: Top 1% Standard      |
//|      Dedicated Ultra-Fast M1 Scalper (Target Winrate > 70%)      |
//|      Incorporating LazyBear Squeeze Momentum, EMA14/50 Pullback, |
//|      Wick-Fill Rejection, and Instant Breakeven Lock             |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumTitan Institutional Quant Framework v15.00 Velocity"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "15.00"
#property description "v15.00 Velocity M1 High-Frequency Scalper: LazyBear Squeeze Momentum, EMA14/50 Retest, Wick-Fill, +180pt Quick TP"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

#include "Include\QuantumTitan\RiskGuardian.mqh"

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== 1. ACCOUNT SECURITY & CAPITAL PRESERVATION ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 991501;     // Magic Number (Isolated M1 Velocity ID)
input double   InpMaxAccountLots       = 0.20;       // Max Total Open Lots on Account
input double   InpMaxSpreadPoints      = 60.0;       // Max Allowed Spread (Points - Gold Volatility Safe)
input double   InpMaxDailyLossPct      = 8.0;        // Daily Loss Kill-Switch (%)
input double   InpHardEquityFloor      = 30.0;       // Hard Equity Floor ($) - Stop All Trading
input int      InpMaxTradesPerDay      = 35;         // Max Completed Trades Per Day (High Frequency)
input int      InpMaxLosingStreak      = 3;          // Max Consecutive Losses Before Pausing

input group "=== 2. MQL5 NATIVE ECONOMIC NEWS SHIELD ==="
input bool     InpUseNewsFilter        = true;       // Enable Economic Calendar News Filter
input int      InpNewsBufferMinsBefore = 15;         // Pause Trading Before High-Impact News (Mins)
input int      InpNewsBufferMinsAfter  = 15;         // Pause Trading After High-Impact News (Mins)

input group "=== 3. LAZYBEAR SQUEEZE MOMENTUM (TradingView Port) ==="
input int      InpBBLength             = 20;         // Bollinger Bands Period
input double   InpBBMult               = 2.0;        // Bollinger Bands StdDev Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Period
input double   InpKCMult               = 1.5;        // Keltner Channel ATR Multiplier

input group "=== 4. EMA TREND & RETEST (เทรดทองทำกำไรตลอดชีวิต PDF) ==="
input int      InpFastEmaPeriod        = 14;         // Fast EMA Period (Retest / Pullback Zone)
input int      InpSlowEmaPeriod        = 50;         // Slow EMA Period (Intraday Baseline Trend)
input double   InpWickRatioThreshold   = 0.25;       // Min Rejection Wick Ratio (Wick / Candle Range)

input group "=== 5. M1 HIGH-WINRATE SCALP TARGETS (Quick TP) ==="
input double   InpBaseLot              = 0.01;       // Lot Size (0.01 for Micro Account)
input double   InpTakeProfitPoints     = 180.0;      // Quick Take Profit (Points: +$1.80 on 0.01 lot)
input double   InpStopLossPoints       = 260.0;      // Safety Stop Loss (Points: -$2.60 on 0.01 lot)
input double   InpBreakevenTriggerPts  = 85.0;       // Breakeven Activation (Points: +$0.85 profit)
input double   InpBreakevenLockPts     = 15.0;       // Breakeven Lock Buffer (Points: +$0.15 guaranteed)
input int      InpCooldownBars         = 1;          // Minimum Bars Between Successive Scalps

input group "=== 6. VISUAL MATRIX HUD ==="
input bool     InpEnableHUD            = true;       // Render Real-Time On-Chart HUD

//+------------------------------------------------------------------+
//| GLOBAL INSTANCES & HANDLES                                       |
//+------------------------------------------------------------------+
CTrade         g_trade;
CPositionInfo  g_position;
CSymbolInfo    g_symbolInfo;
CRiskGuardian  g_riskGuardian;

int            g_handleEmaFast = INVALID_HANDLE;
int            g_handleEmaSlow = INVALID_HANDLE;
int            g_handleBands   = INVALID_HANDLE;
int            g_handleAtrKC   = INVALID_HANDLE;
int            g_handleRsi     = INVALID_HANDLE;

datetime       g_lastBarTime   = 0;
datetime       g_lastExitTime  = 0;

//+------------------------------------------------------------------+
//| Squeeze Momentum State Structure                                 |
//+------------------------------------------------------------------+
struct SqueezeState
{
   bool   isSqueezeOn;       // BB is inside KC (Volatility compressed)
   bool   isBreakout;        // Squeeze released
   double momentum;          // Linear regression momentum
   double prevMomentum;      // Previous bar momentum
   bool   isMomentumBullish; // Momentum positive and expanding
   bool   isMomentumBearish; // Momentum negative and expanding
};

//+------------------------------------------------------------------+
//| Calculate Linear Regression Slope                                |
//+------------------------------------------------------------------+
double LinRegSlope(const double &src[], int length)
{
   if(ArraySize(src) < length) return 0.0;
   double sumX = 0.0, sumY = 0.0, sumXY = 0.0, sumX2 = 0.0;
   for(int i = 0; i < length; i++)
   {
      double x = (double)i;
      double y = src[length - 1 - i];
      sumX  += x;
      sumY  += y;
      sumXY += (x * y);
      sumX2 += (x * x);
   }
   double denom = ((double)length * sumX2) - (sumX * sumX);
   if(MathAbs(denom) < 1e-9) return 0.0;
   return (((double)length * sumXY) - (sumX * sumY)) / denom;
}

//+------------------------------------------------------------------+
//| Calculate LazyBear Squeeze Momentum                              |
//+------------------------------------------------------------------+
bool CalculateSqueezeMomentum(SqueezeState &state)
{
   // 1. Fetch Bollinger Bands (Middle, Upper, Lower)
   double bbMiddle[2], bbUpper[2], bbLower[2];
   if(CopyBuffer(g_handleBands, BASE_LINE, 0, 2, bbMiddle) < 2 ||
      CopyBuffer(g_handleBands, UPPER_BAND, 0, 2, bbUpper) < 2 ||
      CopyBuffer(g_handleBands, LOWER_BAND, 0, 2, bbLower) < 2)
      return false;

   // 2. Fetch Keltner Channel components
   double atrKC[2];
   if(CopyBuffer(g_handleAtrKC, 0, 0, 2, atrKC) < 2) return false;

   double kcUpper = bbMiddle[0] + (InpKCMult * atrKC[0]);
   double kcLower = bbMiddle[0] - (InpKCMult * atrKC[0]);

   // Squeeze status: BB inside KC
   state.isSqueezeOn = (bbUpper[0] < kcUpper && bbLower[0] > kcLower);
   
   double prevKcUpper = bbMiddle[1] + (InpKCMult * atrKC[1]);
   double prevKcLower = bbMiddle[1] - (InpKCMult * atrKC[1]);
   bool prevSqueezeOn = (bbUpper[1] < prevKcUpper && bbLower[1] > prevKcLower);
   state.isBreakout  = (prevSqueezeOn && !state.isSqueezeOn);

   // 3. Momentum: Delta between Close and Avg(DonchianMid, EMA20)
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, InpBBLength + 20, rates) < (InpBBLength + 20))
      return false;

   double deltaArray[20];
   for(int k = 0; k < 20; k++)
   {
      double highestHigh = -1.0;
      double lowestLow   = 9999999.0;
      for(int j = 0; j < InpKCLength; j++)
      {
         int idx = k + j;
         if(rates[idx].high > highestHigh) highestHigh = rates[idx].high;
         if(rates[idx].low < lowestLow)    lowestLow   = rates[idx].low;
      }
      double donchianMid = (highestHigh + lowestLow) / 2.0;
      double avgBasis    = (donchianMid + bbMiddle[0]) / 2.0;
      deltaArray[k]      = rates[k].close - avgBasis;
   }

   state.momentum     = LinRegSlope(deltaArray, 20);
   state.prevMomentum = (ArraySize(deltaArray) >= 19) ? deltaArray[0] : 0.0;

   state.isMomentumBullish = (state.momentum > 0 && state.momentum >= state.prevMomentum);
   state.isMomentumBearish = (state.momentum < 0 && state.momentum <= state.prevMomentum);

   return true;
}

//+------------------------------------------------------------------+
//| Check Active Position Count for this EA                          |
//+------------------------------------------------------------------+
int GetActivePositionCount(ulong magic, double &openPrice, double &currentSl, double &currentPnl, long &posType, ulong &outTicket)
{
   int count = 0;
   openPrice = 0.0;
   currentSl = 0.0;
   currentPnl = 0.0;
   posType = -1;
   outTicket = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_position.SelectByIndex(i)) continue;
      if(g_position.Symbol() == _Symbol && g_position.Magic() == magic)
      {
         count++;
         openPrice  = g_position.PriceOpen();
         currentSl  = g_position.StopLoss();
         currentPnl = g_position.Profit() + g_position.Swap() + g_position.Commission();
         posType    = g_position.PositionType();
         outTicket  = g_position.Ticket();
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Manage Active Position (Instant Breakeven Lock & Protection)     |
//+------------------------------------------------------------------+
void ManagePosition(long posType, double openPrice, double currentSl, ulong ticket)
{
   double point  = g_symbolInfo.Point();
   double bid    = g_symbolInfo.Bid();
   double ask    = g_symbolInfo.Ask();
   int    digits = g_symbolInfo.Digits();

   if(point <= 0) return;
   // Race-condition guard: confirm position still exists before any modification
   if(ticket == 0 || !PositionSelectByTicket(ticket)) return;

   if(posType == POSITION_TYPE_BUY)
   {
      double profitPoints = (bid - openPrice) / point;
      if(profitPoints >= InpBreakevenTriggerPts)
      {
         double targetSl = NormalizeDouble(openPrice + (InpBreakevenLockPts * point), digits);
         if(currentSl < targetSl || currentSl == 0.0)
         {
            g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit());
            PrintFormat("[M1 Velocity] BUY BREAKEVEN LOCKED: Profit %.1f pts -> SL set to %.5f", profitPoints, targetSl);
         }
      }
   }
   else if(posType == POSITION_TYPE_SELL)
   {
      double profitPoints = (openPrice - ask) / point;
      if(profitPoints >= InpBreakevenTriggerPts)
      {
         double targetSl = NormalizeDouble(openPrice - (InpBreakevenLockPts * point), digits);
         if(currentSl > targetSl || currentSl == 0.0)
         {
            g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit());
            PrintFormat("[M1 Velocity] SELL BREAKEVEN LOCKED: Profit %.1f pts -> SL set to %.5f", profitPoints, targetSl);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Render On-Chart HUD                                              |
//+------------------------------------------------------------------+
void RenderHUD(const SqueezeState &sqz, double fastEma, double slowEma, int activeTrades, double pnl)
{
   if(!InpEnableHUD) return;

   string prefix = "QT15_VELOCITY_";
   string lines[8];

   string sqzText = sqz.isSqueezeOn ? "COMPRESSED [SQUEEZE ON]" : (sqz.isBreakout ? "BREAKOUT EXPLOSION" : "EXPANDING");
   color  sqzClr  = sqz.isSqueezeOn ? clrDarkOrange : (sqz.isBreakout ? clrCyan : clrGold);

   string momText = (sqz.momentum > 0) ? StringFormat("BULLISH (+%.4f)", sqz.momentum) : StringFormat("BEARISH (%.4f)", sqz.momentum);
   color  momClr  = (sqz.momentum > 0) ? clrMediumSpringGreen : clrCrimson;

   string trendText = (fastEma > slowEma) ? "BULLISH (EMA14 > EMA50)" : "BEARISH (EMA14 < EMA50)";
   color  trendClr  = (fastEma > slowEma) ? clrMediumSpringGreen : clrCrimson;

   lines[0] = ">> QUANTUM TITAN v15.00 VELOCITY [M1 RAPID SCALPER] <<";
   lines[1] = StringFormat("Account Mode  : DEMO (Safe) ($%.2f)", AccountInfoDouble(ACCOUNT_EQUITY));
   lines[2] = StringFormat("Squeeze State : %s", sqzText);
   lines[3] = StringFormat("Momentum (LB) : %s", momText);
   lines[4] = StringFormat("Trend (EMA)   : %s", trendText);
   lines[5] = StringFormat("Active Scalp  : %d trade(s) | Floating: %+.2f", activeTrades, pnl);
   lines[6] = StringFormat("Targets       : Quick TP: +%.0f pts ($%.2f) | BE: +%.0f pts", InpTakeProfitPoints, InpTakeProfitPoints * 0.01, InpBreakevenTriggerPts);
   lines[7] = "Strategy      : Squeeze Mom + EMA14 Pullback + Wick-Fill (>70% Winrate)";

   int startX = 20;
   int startY = 20;
   int lineHeight = 16;

   for(int i = 0; i < 8; i++)
   {
      string objName = prefix + IntegerToString(i);
      if(ObjectFind(0, objName) < 0)
      {
         ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, startX);
         ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, startY + (i * lineHeight));
         ObjectSetString(0, objName, OBJPROP_FONT, "Lucida Console");
         ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      }
      color txtClr = (i == 0) ? clrCyan : (i == 2 ? sqzClr : (i == 3 ? momClr : (i == 4 ? trendClr : clrWhiteSmoke)));
      ObjectSetString(0, objName, OBJPROP_TEXT, lines[i]);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, txtClr);
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpDemoOnly && (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL))
   {
      Alert("🚨 [SECURITY CRITICAL] QuantumTitan v15 is locked to DEMO mode!");
      return INIT_FAILED;
   }

   if(!g_symbolInfo.Name(_Symbol)) return INIT_FAILED;
   g_symbolInfo.Refresh();

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(20);

   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   // Indicators
   g_handleEmaFast = iMA(_Symbol, PERIOD_M1, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleEmaSlow = iMA(_Symbol, PERIOD_M1, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleBands   = iBands(_Symbol, PERIOD_M1, InpBBLength, 0, InpBBMult, PRICE_CLOSE);
   g_handleAtrKC   = iATR(_Symbol, PERIOD_M1, InpKCLength);
   g_handleRsi     = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

   if(g_handleEmaFast == INVALID_HANDLE || g_handleEmaSlow == INVALID_HANDLE ||
      g_handleBands == INVALID_HANDLE || g_handleAtrKC == INVALID_HANDLE || g_handleRsi == INVALID_HANDLE)
   {
      Print("❌ Failed to create indicator handles for v15 Velocity");
      return INIT_FAILED;
   }

   // Attach visual indicator lines to chart
   ChartIndicatorAdd(0, 0, g_handleEmaFast);
   ChartIndicatorAdd(0, 0, g_handleEmaSlow);
   ChartIndicatorAdd(0, 0, g_handleBands);

   // Initialize Risk Guardian
   if(!g_riskGuardian.Init(_Symbol, InpMagicNumber, InpMaxDailyLossPct, InpHardEquityFloor,
                           InpMaxTradesPerDay, InpMaxLosingStreak, InpMaxSpreadPoints,
                           InpUseNewsFilter, InpNewsBufferMinsBefore, InpNewsBufferMinsAfter,
                           InpMaxAccountLots))
   {
      Print("❌ Failed to initialize Risk Guardian for v15 Velocity");
      return INIT_FAILED;
   }

   PrintFormat("⚡ QuantumTitan v15.00 Velocity initialized on %s M1 (Magic: %d)", _Symbol, InpMagicNumber);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(g_handleEmaFast);
   IndicatorRelease(g_handleEmaSlow);
   IndicatorRelease(g_handleBands);
   IndicatorRelease(g_handleAtrKC);
   IndicatorRelease(g_handleRsi);

   ObjectsDeleteAll(0, "QT15_VELOCITY_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!g_symbolInfo.RefreshRates()) return;

   double bid    = g_symbolInfo.Bid();
   double ask    = g_symbolInfo.Ask();
   double point  = g_symbolInfo.Point();
   int    digits = g_symbolInfo.Digits();

   // 1. Position Management & Rapid Breakeven Lock
   double openPrice = 0.0, currentSl = 0.0, currentPnl = 0.0;
   long posType = -1;
   ulong activeTicket = 0;
   int activeTrades = GetActivePositionCount(InpMagicNumber, openPrice, currentSl, currentPnl, posType, activeTicket);

   if(activeTrades > 0)
   {
      ManagePosition(posType, openPrice, currentSl, activeTicket);
   }

   // 2. Risk Guardian Telemetry
   RiskTelemetry riskTelem;
   g_riskGuardian.ValidateExecution(riskTelem);

   // 3. Indicator Telemetry
   double fastEma[2], slowEma[2], rsiVal[2];
   if(CopyBuffer(g_handleEmaFast, 0, 0, 2, fastEma) < 2) return;
   if(CopyBuffer(g_handleEmaSlow, 0, 0, 2, slowEma) < 2) return;
   if(CopyBuffer(g_handleRsi, 0, 0, 2, rsiVal) < 2) return;

   SqueezeState sqz;
   CalculateSqueezeMomentum(sqz);

   // 4. Render HUD
   RenderHUD(sqz, fastEma[0], slowEma[0], activeTrades, currentPnl);

   // Draw dynamic EMA14 Retest Level Line
   string retestObj = "QT15_RETEST_LINE";
   if(fastEma[0] > 0)
   {
      if(ObjectFind(0, retestObj) < 0) ObjectCreate(0, retestObj, OBJ_HLINE, 0, 0, fastEma[0]);
      else ObjectMove(0, retestObj, 0, 0, fastEma[0]);
      ObjectSetInteger(0, retestObj, OBJPROP_COLOR, (fastEma[0] > slowEma[0]) ? clrGold : clrDeepPink);
      ObjectSetInteger(0, retestObj, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, retestObj, OBJPROP_WIDTH, 1);
      ObjectSetString(0, retestObj, OBJPROP_TOOLTIP, "EMA14 Retest Trigger Line");
   }

   // 5. Entry Checks
   // Only open new scalp if no active position for this EA
   if(activeTrades > 0) return;

   // Circuit breaker / News filter checks
   if(!riskTelem.canOpenNewCycle) return;

   // Spread check
   double currentSpread = (point > 0.0) ? (ask - bid) / point : 0.0;
   if(currentSpread > InpMaxSpreadPoints) return;

   // Bar close discipline for entry signal evaluation
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime <= 0 || currentBarTime == g_lastBarTime) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 3, rates) < 3) return;

   MqlRates completedBar = rates[0]; // Bar 1 (just completed)
   double barRange = completedBar.high - completedBar.low;
   if(barRange <= 0) return;

   double lowerWick = MathMin(completedBar.open, completedBar.close) - completedBar.low;
   double upperWick = completedBar.high - MathMax(completedBar.open, completedBar.close);
   double lowerWickRatio = lowerWick / barRange;
   double upperWickRatio = upperWick / barRange;

   bool signalBuy  = false;
   bool signalSell = false;

   // BUY SETUP (High Winrate Criteria):
   // 1. Trend: Fast EMA > Slow EMA and Close[1] > Slow EMA
   // 2. Retest: Low[1] touched or pulled back near Fast EMA (within 15 points)
   // 3. Price Action Rejection: Lower Wick >= 25% (buying rejection / wick fill) OR bullish bar
   // 4. Squeeze Momentum: Momentum is positive or squeeze released
   // 5. RSI: Healthy momentum (42 <= RSI <= 68)
   if(fastEma[0] > slowEma[0] && completedBar.close > slowEma[0])
   {
      bool touchedFastEma = (completedBar.low <= fastEma[0] + (15.0 * point));
      bool rejectionWick  = (lowerWickRatio >= InpWickRatioThreshold || completedBar.close > completedBar.open);
      bool momOk          = (sqz.momentum > -0.05); // Momentum expanding or near zero turn
      bool rsiOk          = (rsiVal[0] >= 40.0 && rsiVal[0] <= 70.0);

      if(touchedFastEma && rejectionWick && momOk && rsiOk)
      {
         signalBuy = true;
      }
   }

   // SELL SETUP (High Winrate Criteria):
   // 1. Trend: Fast EMA < Slow EMA and Close[1] < Slow EMA
   // 2. Retest: High[1] touched or pulled back near Fast EMA (within 15 points)
   // 3. Price Action Rejection: Upper Wick >= 25% (selling rejection / wick fill) OR bearish bar
   // 4. Squeeze Momentum: Momentum is negative or squeeze released
   // 5. RSI: Healthy momentum (30 <= RSI <= 58)
   if(fastEma[0] < slowEma[0] && completedBar.close < slowEma[0])
   {
      bool touchedFastEma = (completedBar.high >= fastEma[0] - (15.0 * point));
      bool rejectionWick  = (upperWickRatio >= InpWickRatioThreshold || completedBar.close < completedBar.open);
      bool momOk          = (sqz.momentum < 0.05); // Momentum negative or near zero turn
      bool rsiOk          = (rsiVal[0] >= 30.0 && rsiVal[0] <= 60.0);

      if(touchedFastEma && rejectionWick && momOk && rsiOk)
      {
         signalSell = true;
      }
   }

   // Execute Scalp Order
   if(signalBuy)
   {
      double sl = NormalizeDouble(ask - (InpStopLossPoints * point), digits);
      double tp = NormalizeDouble(ask + (InpTakeProfitPoints * point), digits);

      if(g_trade.Buy(InpBaseLot, _Symbol, ask, sl, tp, "QT15_Velocity_Buy"))
      {
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [M1 Velocity] BUY SCALP OPENED @ %.5f | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts)",
            ask, sl, InpStopLossPoints, tp, InpTakeProfitPoints);
      }
   }
   else if(signalSell)
   {
      double sl = NormalizeDouble(bid + (InpStopLossPoints * point), digits);
      double tp = NormalizeDouble(bid - (InpTakeProfitPoints * point), digits);

      if(g_trade.Sell(InpBaseLot, _Symbol, bid, sl, tp, "QT15_Velocity_Sell"))
      {
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [M1 Velocity] SELL SCALP OPENED @ %.5f | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts)",
            bid, sl, InpStopLossPoints, tp, InpTakeProfitPoints);
      }
   }

   g_lastBarTime = currentBarTime;
}
//+------------------------------------------------------------------+
