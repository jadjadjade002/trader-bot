//+------------------------------------------------------------------+
//|                                     QuantumTitan_v16_1_M1.mq5    |
//|          v16.10 M1 High-Confidence Scalper Framework             |
//|      Multi-Agent Autonomous Trading System: Top 1% Standard      |
//|      Dedicated Ultra-Fast M1 Scalper with Confidence Scoring,    |
//|      Expanded TP (1:1 R:R), Slower Breakeven, and Noise Filters  |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumTitan Institutional Quant Framework v16.10 M1"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "16.10"
#property description "v16.10 M1 High-Confidence Scalper: Multi-Gate Confidence Scoring, Squeeze Momentum, EMA14/50 Retest, +260pt TP, 130pt Slower BE"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== 1. ACCOUNT SECURITY & EXECUTION ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 991612;     // Dedicated V16.1 ID (Isolates from Apex 991601 & Velocity 991602)
input double   InpMaxSpreadPoints      = 35.0;       // Max Allowed Spread (Points - Strict Gold Scalp Filter)
input double   InpBaseLot              = 0.01;       // Base Lot Size (Strict 0.01 for Micro Risk)

input group "=== 2. M1 TARGETS & TRADE MANAGEMENT (Expanded TP & Slower BE) ==="
input double   InpTakeProfitPoints     = 260.0;      // Expanded Take Profit (Points: +$2.60 on 0.01 lot, 1.0R)
input double   InpStopLossPoints       = 260.0;      // Stop Loss (Points: -$2.60 on 0.01 lot, 1.0R baseline)
input double   InpBreakevenTriggerPts  = 130.0;      // Slower Breakeven Activation (Points: +$1.30 / 0.5R)
input double   InpBreakevenLockPts     = 20.0;       // Breakeven Lock Buffer (Points: +$0.20 net profit lock)
input int      InpCooldownBars         = 3;          // M1 bars to wait after any position closes (Anti-whipsaw)

input group "=== 3. CONFIDENCE & NOISE GATES ==="
input int      InpMinConfidenceScore   = 70;         // Minimum Multi-Gate Confidence Score (0-100)
input double   InpMinAtrPoints         = 80.0;       // Min M1 ATR Noise Floor (Points: $0.80 minimum bar movement)
input int      InpFastEmaPeriod        = 14;         // Fast EMA Period (Pullback / Retest Zone)
input int      InpSlowEmaPeriod        = 50;         // Slow EMA Period (Intraday Baseline Trend)
input double   InpWickRatioThreshold   = 0.25;       // Min Rejection Wick Ratio (Wick / Candle Range)

input group "=== 4. LAZYBEAR SQUEEZE MOMENTUM ==="
input int      InpBBLength             = 20;         // Bollinger Bands Period
input double   InpBBMult               = 2.0;        // Bollinger Bands StdDev Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Period
input double   InpKCMult               = 1.5;        // Keltner Channel ATR Multiplier

input group "=== 5. VISUAL MATRIX HUD ==="
input bool     InpEnableHUD            = true;       // Render Real-Time On-Chart HUD

//+------------------------------------------------------------------+
//| GLOBAL INSTANCES & STATE                                         |
//+------------------------------------------------------------------+
CTrade         g_trade;
CPositionInfo  g_position;
CSymbolInfo    g_symbolInfo;

int            g_handleEmaFast = INVALID_HANDLE;
int            g_handleEmaSlow = INVALID_HANDLE;
int            g_handleBands   = INVALID_HANDLE;
int            g_handleAtrKC   = INVALID_HANDLE;
int            g_handleAtr14   = INVALID_HANDLE;
int            g_handleRsi     = INVALID_HANDLE;

datetime       g_lastBarTime   = 0;
ulong          g_v161Magic     = 0;
datetime       g_lastExitTime  = 0;
bool           g_hadActivePosition = false;

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
   double bbMiddle[2], bbUpper[2], bbLower[2];
   if(CopyBuffer(g_handleBands, BASE_LINE, 0, 2, bbMiddle) < 2 ||
      CopyBuffer(g_handleBands, UPPER_BAND, 0, 2, bbUpper) < 2 ||
      CopyBuffer(g_handleBands, LOWER_BAND, 0, 2, bbLower) < 2)
      return false;

   double atrKC[2];
   if(CopyBuffer(g_handleAtrKC, 0, 0, 2, atrKC) < 2) return false;

   double kcUpper = bbMiddle[0] + (InpKCMult * atrKC[0]);
   double kcLower = bbMiddle[0] - (InpKCMult * atrKC[0]);

   state.isSqueezeOn = (bbUpper[0] < kcUpper && bbLower[0] > kcLower);
   
   double prevKcUpper = bbMiddle[1] + (InpKCMult * atrKC[1]);
   double prevKcLower = bbMiddle[1] - (InpKCMult * atrKC[1]);
   bool prevSqueezeOn = (bbUpper[1] < prevKcUpper && bbLower[1] > prevKcLower);
   state.isBreakout  = (prevSqueezeOn && !state.isSqueezeOn);

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
//| Manage Active Position (Slower Breakeven Lock & Protection)      |
//+------------------------------------------------------------------+
void ManagePosition(long posType, double openPrice, double currentSl, ulong ticket)
{
   double point  = g_symbolInfo.Point();
   double bid    = g_symbolInfo.Bid();
   double ask    = g_symbolInfo.Ask();
   int    digits = g_symbolInfo.Digits();

   if(point <= 0) return;
   if(ticket == 0 || !PositionSelectByTicket(ticket)) return;

   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minStopDist = (double)stopsLevel * point;

   if(posType == POSITION_TYPE_BUY)
   {
      double profitPoints = (bid - openPrice) / point;
      if(profitPoints >= InpBreakevenTriggerPts)
      {
         double targetSl = NormalizeDouble(openPrice + (InpBreakevenLockPts * point), digits);
         if((bid - targetSl) >= minStopDist && (currentSl < targetSl || currentSl == 0.0))
         {
            if(PositionSelectByTicket(ticket))
            {
               if(g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit()))
               {
                  PrintFormat("⚡ [V16.1 M1] BUY BREAKEVEN LOCKED: Profit %.1f pts (Trigger %.0f pts) -> SL set to %.5f",
                              profitPoints, InpBreakevenTriggerPts, targetSl);
               }
               else
               {
                  PrintFormat("⚠️ [V16.1 M1] BUY BREAKEVEN MODIFY REJECTED: RetCode=%u (%s)",
                              g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
   else if(posType == POSITION_TYPE_SELL)
   {
      double profitPoints = (openPrice - ask) / point;
      if(profitPoints >= InpBreakevenTriggerPts)
      {
         double targetSl = NormalizeDouble(openPrice - (InpBreakevenLockPts * point), digits);
         if((targetSl - ask) >= minStopDist && (currentSl > targetSl || currentSl == 0.0))
         {
            if(PositionSelectByTicket(ticket))
            {
               if(g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit()))
               {
                  PrintFormat("⚡ [V16.1 M1] SELL BREAKEVEN LOCKED: Profit %.1f pts (Trigger %.0f pts) -> SL set to %.5f",
                              profitPoints, InpBreakevenTriggerPts, targetSl);
               }
               else
               {
                  PrintFormat("⚠️ [V16.1 M1] SELL BREAKEVEN MODIFY REJECTED: RetCode=%u (%s)",
                              g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Post-Exit Cooldown Protection                                    |
//+------------------------------------------------------------------+
bool IsPostExitCooldownActive()
{
   if(g_lastExitTime <= 0 || InpCooldownBars <= 0) return false;

   int barSeconds = PeriodSeconds(PERIOD_M1);
   if(barSeconds <= 0) barSeconds = 60;
   return (TimeCurrent() - g_lastExitTime) < (barSeconds * InpCooldownBars);
}

//+------------------------------------------------------------------+
//| Render On-Chart HUD                                              |
//+------------------------------------------------------------------+
void RenderHUD(const SqueezeState &sqz, double fastEma, double slowEma, double atrPoints, double spreadPts, int activeTrades, double pnl, int lastScore)
{
   if(!InpEnableHUD) return;

   string prefix = "QT16_1_M1_";
   string lines[9];

   string sqzText = sqz.isSqueezeOn ? "COMPRESSED [SQUEEZE ON]" : (sqz.isBreakout ? "BREAKOUT EXPLOSION" : "EXPANDING");
   color  sqzClr  = sqz.isSqueezeOn ? clrDarkOrange : (sqz.isBreakout ? clrCyan : clrGold);

   string momText = (sqz.momentum > 0) ? StringFormat("BULLISH (+%.4f)", sqz.momentum) : StringFormat("BEARISH (%.4f)", sqz.momentum);
   color  momClr  = (sqz.momentum > 0) ? clrMediumSpringGreen : clrCrimson;

   string trendText = (fastEma > slowEma) ? "BULLISH (EMA14 > EMA50)" : "BEARISH (EMA14 < EMA50)";
   color  trendClr  = (fastEma > slowEma) ? clrMediumSpringGreen : clrCrimson;

   lines[0] = ">> QUANTUM TITAN v16.10 M1 [HIGH-CONFIDENCE SCALPER] <<";
   lines[1] = StringFormat("Account Mode  : DEMO ONLY | Equity: $%.2f", AccountInfoDouble(ACCOUNT_EQUITY));
   lines[2] = StringFormat("Confidence    : %d / 100 (Threshold: %d) | Spread: %.1f pts (Max: %.1f)", lastScore, InpMinConfidenceScore, spreadPts, InpMaxSpreadPoints);
   lines[3] = StringFormat("Squeeze State : %s", sqzText);
   lines[4] = StringFormat("Momentum (LB) : %s", momText);
   lines[5] = StringFormat("Trend (EMA)   : %s | M1 ATR: %.1f pts (Floor: %.1f)", trendText, atrPoints, InpMinAtrPoints);
   lines[6] = StringFormat("Active Scalp  : %d trade(s) | Floating: %+.2f", activeTrades, pnl);
   lines[7] = StringFormat("Targets       : TP: +%.0f pts ($%.2f) | SL: -%.0f pts | BE Trigger: +%.0f pts", InpTakeProfitPoints, InpTakeProfitPoints * 0.01, InpStopLossPoints, InpBreakevenTriggerPts);
   lines[8] = StringFormat("Cooldown      : %d bars | Magic ID: %I64u", InpCooldownBars, g_v161Magic);

   int startX = 20;
   int startY = 20;
   int lineHeight = 16;

   for(int i = 0; i < 9; i++)
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
      color txtClr = (i == 0) ? clrCyan : (i == 2 ? clrYellow : (i == 3 ? sqzClr : (i == 4 ? momClr : (i == 5 ? trendClr : clrWhiteSmoke))));
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
      Alert("🚨 [SECURITY CRITICAL] QuantumTitan v16.1 M1 is locked to DEMO mode! Real execution blocked.");
      return INIT_FAILED;
   }

   if(!g_symbolInfo.Name(_Symbol)) return INIT_FAILED;
   g_symbolInfo.Refresh();

   g_v161Magic = InpMagicNumber;
   if(g_v161Magic == 991601 || g_v161Magic == 991602 || g_v161Magic == 991600)
   {
      g_v161Magic = 991612;
      PrintFormat("[V16.1 Safety] Magic collision detected (%I64u overridden to 991612 for isolation).", InpMagicNumber);
   }

   g_trade.SetExpertMagicNumber(g_v161Magic);
   g_trade.SetDeviationInPoints(20);

   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   g_handleEmaFast = iMA(_Symbol, PERIOD_M1, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleEmaSlow = iMA(_Symbol, PERIOD_M1, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleBands   = iBands(_Symbol, PERIOD_M1, InpBBLength, 0, InpBBMult, PRICE_CLOSE);
   g_handleAtrKC   = iATR(_Symbol, PERIOD_M1, InpKCLength);
   g_handleAtr14   = iATR(_Symbol, PERIOD_M1, 14);
   g_handleRsi     = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

   if(g_handleEmaFast == INVALID_HANDLE || g_handleEmaSlow == INVALID_HANDLE ||
      g_handleBands == INVALID_HANDLE   || g_handleAtrKC == INVALID_HANDLE   ||
      g_handleAtr14 == INVALID_HANDLE   || g_handleRsi == INVALID_HANDLE)
   {
      Print("❌ Failed to create indicator handles for QuantumTitan v16.1 M1");
      return INIT_FAILED;
   }

   ChartIndicatorAdd(0, 0, g_handleEmaFast);
   ChartIndicatorAdd(0, 0, g_handleEmaSlow);
   ChartIndicatorAdd(0, 0, g_handleBands);

   PrintFormat("⚡ QuantumTitan v16.10 M1 Initialized on %s M1 (Magic: %I64u | TP: +%.0f pts | BE: +%.0f pts)",
               _Symbol, g_v161Magic, InpTakeProfitPoints, InpBreakevenTriggerPts);
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
   IndicatorRelease(g_handleAtr14);
   IndicatorRelease(g_handleRsi);

   ObjectsDeleteAll(0, "QT16_1_M1_");
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
   if(point <= 0.0) return;

   double openPrice = 0.0, currentSl = 0.0, currentPnl = 0.0;
   long posType = -1;
   ulong activeTicket = 0;
   int activeTrades = GetActivePositionCount(g_v161Magic, openPrice, currentSl, currentPnl, posType, activeTicket);

   if(activeTrades > 0)
   {
      g_hadActivePosition = true;
      ManagePosition(posType, openPrice, currentSl, activeTicket);
   }
   else if(g_hadActivePosition)
   {
      g_hadActivePosition = false;
      g_lastExitTime = TimeCurrent();
      PrintFormat("[V16.1 Safety] Scalp position closed; %d bar(s) anti-whipsaw cooldown active.", InpCooldownBars);
   }

   double fastEma[2], slowEma[2], rsiVal[2], atr14Val[2];
   if(CopyBuffer(g_handleEmaFast, 0, 0, 2, fastEma) < 2) return;
   if(CopyBuffer(g_handleEmaSlow, 0, 0, 2, slowEma) < 2) return;
   if(CopyBuffer(g_handleRsi,     0, 0, 2, rsiVal) < 2) return;
   if(CopyBuffer(g_handleAtr14,   0, 0, 2, atr14Val) < 2) return;

   double currentSpread = (ask - bid) / point;
   double currentAtrPts = atr14Val[0] / point;

   SqueezeState sqz;
   CalculateSqueezeMomentum(sqz);

   static int s_lastConfidenceScore = 0;
   RenderHUD(sqz, fastEma[0], slowEma[0], currentAtrPts, currentSpread, activeTrades, currentPnl, s_lastConfidenceScore);

   if(activeTrades > 0) return;
   if(IsPostExitCooldownActive()) return;
   if(currentSpread > InpMaxSpreadPoints) return;
   if(currentAtrPts < InpMinAtrPoints) return;

   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime <= 0 || currentBarTime == g_lastBarTime) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 3, rates) < 3) return;

   MqlRates completedBar = rates[0];
   double barRange = completedBar.high - completedBar.low;
   if(barRange <= 0.0) return;

   double lowerWick = MathMin(completedBar.open, completedBar.close) - completedBar.low;
   double upperWick = completedBar.high - MathMax(completedBar.open, completedBar.close);
   double lowerWickRatio = lowerWick / barRange;
   double upperWickRatio = upperWick / barRange;

   double retestTolPoints = MathMax(15.0, 0.25 * currentAtrPts);
   double retestTolPrice  = retestTolPoints * point;

   bool signalBuy  = false;
   bool signalSell = false;
   int buyScore    = 0;
   int sellScore   = 0;

   // BUY CONFIDENCE SCORING (100 Points Total)
   if(fastEma[0] > slowEma[0] && completedBar.close > slowEma[0])
   {
      buyScore += 20; // Gate 1: Trend Alignment

      if(completedBar.low <= fastEma[0] + retestTolPrice)
         buyScore += 20; // Gate 2: Retest Zone

      if(lowerWickRatio >= InpWickRatioThreshold)
         buyScore += 20; // Gate 3: Lower Wick Rejection

      if(completedBar.close > completedBar.open)
         buyScore += 15; // Gate 4: Bullish Candle Close

      if(sqz.isMomentumBullish || sqz.isBreakout)
         buyScore += 15; // Gate 5: Expanding Momentum

      if(rsiVal[0] >= 45.0 && rsiVal[0] <= 65.0)
         buyScore += 10; // Gate 6: RSI Regime

      if(buyScore >= InpMinConfidenceScore)
         signalBuy = true;
   }

   // SELL CONFIDENCE SCORING (100 Points Total)
   if(fastEma[0] < slowEma[0] && completedBar.close < slowEma[0])
   {
      sellScore += 20; // Gate 1: Trend Alignment

      if(completedBar.high >= fastEma[0] - retestTolPrice)
         sellScore += 20; // Gate 2: Retest Zone

      if(upperWickRatio >= InpWickRatioThreshold)
         sellScore += 20; // Gate 3: Upper Wick Rejection

      if(completedBar.close < completedBar.open)
         sellScore += 15; // Gate 4: Bearish Candle Close

      if(sqz.isMomentumBearish || sqz.isBreakout)
         sellScore += 15; // Gate 5: Expanding Momentum

      if(rsiVal[0] >= 35.0 && rsiVal[0] <= 55.0)
         sellScore += 10; // Gate 6: RSI Regime

      if(sellScore >= InpMinConfidenceScore)
         signalSell = true;
   }

   s_lastConfidenceScore = MathMax(buyScore, sellScore);

   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(freeMargin < 15.0) // Safe margin buffer ($5 required for 0.01 at 1:500)
   {
      PrintFormat("⚠️ [V16.1 M1] Insufficient Free Margin ($%.2f) to open 0.01 scalp.", freeMargin);
      g_lastBarTime = currentBarTime;
      return;
   }

   const double strictLot = InpBaseLot;
   if(signalBuy)
   {
      double sl = NormalizeDouble(ask - (InpStopLossPoints * point), digits);
      double tp = NormalizeDouble(ask + (InpTakeProfitPoints * point), digits);

      if(g_trade.Buy(strictLot, _Symbol, ask, sl, tp, "QT16_1_Buy"))
      {
         g_hadActivePosition = true;
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [V16.1 M1] BUY SCALP OPENED @ %.5f | Score: %d/100 | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts) | Lot: %.2f | Spread: %.1f pts",
                     ask, buyScore, sl, InpStopLossPoints, tp, InpTakeProfitPoints, strictLot, currentSpread);
      }
      else
      {
         PrintFormat("❌ [V16.1 M1] BUY ORDER FAILED: RetCode=%u (%s)", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
   else if(signalSell)
   {
      double sl = NormalizeDouble(bid + (InpStopLossPoints * point), digits);
      double tp = NormalizeDouble(bid - (InpTakeProfitPoints * point), digits);

      if(g_trade.Sell(strictLot, _Symbol, bid, sl, tp, "QT16_1_Sell"))
      {
         g_hadActivePosition = true;
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [V16.1 M1] SELL SCALP OPENED @ %.5f | Score: %d/100 | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts) | Lot: %.2f | Spread: %.1f pts",
                     bid, sellScore, sl, InpStopLossPoints, tp, InpTakeProfitPoints, strictLot, currentSpread);
      }
      else
      {
         PrintFormat("❌ [V16.1 M1] SELL ORDER FAILED: RetCode=%u (%s)", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }

   g_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//| Transparent Audit: Explicit Realized Deal PnL in Log             |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != g_v161Magic) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
   {
      g_lastExitTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      g_hadActivePosition = false;

      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      double comm   = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
      double swap   = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
      double netPnl = profit + comm + swap;

      PrintFormat("🎯 [V16.1 M1 Audit] Deal #%I64u CLOSED | Net PnL: $%+.2f (Profit: $%.2f, Comm: $%.2f, Swap: $%.2f) | Cooldown started.",
                  trans.deal, netPnl, profit, comm, swap);
   }
}
//+------------------------------------------------------------------+
