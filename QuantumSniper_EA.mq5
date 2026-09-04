//+------------------------------------------------------------------+
//|                                             QuantumSniper_EA.mq5 |
//|        TradingView Hall of Fame Hybrid: LuxAlgo SMC + LazyBear SQZ |
//|                                      https://www.mql5.com        |
//+------------------------------------------------------------------+
#property copyright "TradingView Quant Hybrid"
#property link      "https://www.mql5.com"
#property version   "4.00"
#property description "Elite Hybrid EA: LuxAlgo Smart Money Concepts (Order Blocks) + LazyBear Squeeze Momentum + UT Bot Trailing"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== 1. ACCOUNT SAFETY & DEMO GUARD ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 777888;     // Magic Number (Bot ID)
input double   InpMaxSpreadPoints      = 50.0;       // Max Spread Allowed (Points)
input double   InpMaxDailyLossPct      = 10.0;       // Daily Drawdown Auto-Kill Switch (%)

input group "=== 2. LAZYBEAR SQUEEZE MOMENTUM ENGINE ==="
input bool     InpUseSqueezeFilter     = true;       // Require Squeeze Release to Fire
input int      InpBBLength             = 20;         // Bollinger Bands Length
input double   InpBBMult               = 2.0;        // Bollinger Bands Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Length
input double   InpKCMult               = 1.5;        // Keltner Channel Multiplier

input group "=== 3. LUXALGO SMART MONEY CONCEPTS (SMC) ==="
input bool     InpUseOrderBlocks       = true;       // Filter entries with Institutional Order Blocks
input int      InpSMC_Lookback         = 15;         // Order Block Scan Lookback (Bars)
input int      InpSweepBars            = 3;          // Liquidity Sweep Window (Bars)

input group "=== 4. RISK & UT BOT TRAILING MANAGEMENT ==="
input double   InpFixedLot             = 0.01;       // Fixed Lot Size (0.01 for $50)
input double   InpRiskRewardRatio      = 1.8;        // Target Risk:Reward Ratio
input double   InpBreakEvenTriggerR    = 0.8;        // Fast Break-Even Trigger (at 0.8R Profit)
input bool     InpUseTrailingStop      = true;       // Enable UT Bot Dynamic Trailing Stop
input double   InpTrailingTriggerR     = 1.2;        // Activate Trailing at 1.2R Profit
input int      InpCooldownBars         = 1;          // Cooldown Period After Exit (Bars)

//--- GLOBAL OBJECTS & HANDLES ---
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

int            h_atr;
datetime       m_lastBarTime;
double         m_startingDailyEquity;
datetime       m_currentDay;

// Cooldown Tracker
datetime       g_lastExitTime = 0;
bool           g_wasInPosition = false;

// Squeeze & SMC Diagnostics
string         g_sqzStateStr = "NEUTRAL";
string         g_momColorStr = "NEUTRAL";
string         g_smcStateStr = "SCANNING";
double         g_lastSqzVal = 0.0;
bool           g_isSqzFired = false;
string         g_lastSignalReason = "TradingView Hybrid Engine Ready";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Alert("❌ CRITICAL: EA is configured for DEMO testing only!");
      return(INIT_FAILED);
   }

   if(!m_symbol.Name(_Symbol)) return(INIT_FAILED);
   m_symbol.Refresh();

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(15);

   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0) m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0) m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   h_atr = iATR(_Symbol, _Period, 14);
   if(h_atr == INVALID_HANDLE) return(INIT_FAILED);

   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_currentDay = iTime(_Symbol, PERIOD_D1, 0);
   m_lastBarTime = 0;
   g_wasInPosition = HasOpenPosition();

   Print("⚡ QuantumSniper TV Hybrid 4.0 Initialized on ", _Symbol, " (TF: ", EnumToString(_Period), ")");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr);
   Comment("");
}

//+------------------------------------------------------------------+
//| Linear Regression calculation (Exact LazyBear Pine Script match) |
//+------------------------------------------------------------------+
double CalculateLinReg(const double &arr[], int length)
{
   if(length <= 1) return 0;
   double sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
   for(int i = 0; i < length; i++)
   {
      double x = i;
      double y = arr[i]; // arr[0] is current bar, arr[1] is bar-1
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumXX += x * x;
   }
   double denominator = (length * sumXX - sumX * sumX);
   if(denominator == 0) return arr[0];
   double slope = (length * sumXY - sumX * sumY) / denominator;
   double intercept = (sumY - slope * sumX) / length;
   return intercept; // Value at x = 0
}

//+------------------------------------------------------------------+
//| LazyBear Squeeze Momentum Calculator                             |
//+------------------------------------------------------------------+
void CalculateSqueezeMomentum(bool &sqzOn, bool &sqzOff, double &val, double &valPrev, string &momColor)
{
   int totalNeeded = InpBBLength + InpKCLength + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, totalNeeded, rates) < totalNeeded) return;

   // 1. Calculate Bollinger Bands (20, 2.0)
   double smaBB = 0;
   for(int i = 0; i < InpBBLength; i++) smaBB += rates[i].close;
   smaBB /= InpBBLength;

   double variance = 0;
   for(int i = 0; i < InpBBLength; i++) variance += MathPow(rates[i].close - smaBB, 2);
   double stdevBB = MathSqrt(variance / InpBBLength);

   double upperBB = smaBB + (InpBBMult * stdevBB);
   double lowerBB = smaBB - (InpBBMult * stdevBB);

   // 2. Calculate Keltner Channel (20, 1.5)
   double smaKC = 0;
   for(int i = 0; i < InpKCLength; i++) smaKC += rates[i].close;
   smaKC /= InpKCLength;

   double sumTR = 0;
   for(int i = 0; i < InpKCLength; i++)
   {
      double tr = MathMax(rates[i].high - rates[i].low, 
                  MathMax(MathAbs(rates[i].high - rates[i+1].close), MathAbs(rates[i].low - rates[i+1].close)));
      sumTR += tr;
   }
   double rangema = sumTR / InpKCLength;

   double upperKC = smaKC + (rangema * InpKCMult);
   double lowerKC = smaKC - (rangema * InpKCMult);

   // Squeeze Status
   sqzOn  = (lowerBB > lowerKC) && (upperBB < upperKC);
   sqzOff = (lowerBB < lowerKC) && (upperBB > upperKC);

   // 3. Calculate Linear Regression Momentum `val` for Bar 0 and Bar 1
   double diffArr0[25], diffArr1[25];
   for(int j = 0; j < InpKCLength; j++)
   {
      // Find highest high & lowest low in 20 bars starting from j
      double hh0 = rates[j].high, ll0 = rates[j].low;
      double sumClose0 = 0;
      for(int k = 0; k < InpKCLength; k++)
      {
         if(rates[j + k].high > hh0) hh0 = rates[j + k].high;
         if(rates[j + k].low < ll0)  ll0 = rates[j + k].low;
         sumClose0 += rates[j + k].close;
      }
      double midLine0 = ((hh0 + ll0) / 2.0 + (sumClose0 / InpKCLength)) / 2.0;
      diffArr0[j] = rates[j].close - midLine0;
   }

   for(int j = 0; j < InpKCLength; j++)
   {
      double hh1 = rates[j+1].high, ll1 = rates[j+1].low;
      double sumClose1 = 0;
      for(int k = 0; k < InpKCLength; k++)
      {
         if(rates[j + 1 + k].high > hh1) hh1 = rates[j + 1 + k].high;
         if(rates[j + 1 + k].low < ll1)  ll1 = rates[j + 1 + k].low;
         sumClose1 += rates[j + 1 + k].close;
      }
      double midLine1 = ((hh1 + ll1) / 2.0 + (sumClose1 / InpKCLength)) / 2.0;
      diffArr1[j] = rates[j+1].close - midLine1;
   }

   val     = CalculateLinReg(diffArr0, InpKCLength);
   valPrev = CalculateLinReg(diffArr1, InpKCLength);

   // Color Scheme
   if(val > 0)
   {
      momColor = (val > valPrev) ? "LIME (Bull Explosion) 🟢" : "DARK GREEN (Bull Weakening) 🍏";
   }
   else
   {
      momColor = (val < valPrev) ? "BRIGHT RED (Bear Plunge) 🔴" : "MAROON (Bear Weakening) 🥀";
   }
}

//+------------------------------------------------------------------+
//| LuxAlgo Smart Money Concepts (Order Block & Liquidity Grab)      |
//+------------------------------------------------------------------+
void DetectLuxAlgoSMC(bool &bullishOB, bool &bearishOB, bool &sweptLow, bool &sweptHigh)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, InpSMC_Lookback + 5, rates) < InpSMC_Lookback + 5) return;

   // 1. Liquidity Sweep
   double swingHigh = rates[InpSweepBars + 1].high;
   double swingLow  = rates[InpSweepBars + 1].low;
   for(int i = InpSweepBars + 2; i <= InpSweepBars + 5; i++)
   {
      if(rates[i].high > swingHigh) swingHigh = rates[i].high;
      if(rates[i].low < swingLow)   swingLow  = rates[i].low;
   }

   sweptLow = false; sweptHigh = false;
   for(int i = 1; i <= InpSweepBars; i++)
   {
      if(rates[i].low <= swingLow)   sweptLow = true;
      if(rates[i].high >= swingHigh) sweptHigh = true;
   }

   // 2. Bullish & Bearish Order Block (OB) Detection
   // Bullish OB: Prior down-candle followed by a strong aggressive up-displacement
   bullishOB = false;
   bearishOB = false;
   for(int i = 2; i <= 6; i++)
   {
      // Strong Bullish Displacement: candle body is large and broke highs
      if(rates[i-1].close > rates[i-1].open && (rates[i-1].close - rates[i-1].open) > (rates[i].high - rates[i].low) * 0.8)
      {
         if(rates[i].close < rates[i].open) // Down candle prior to displacement (Demand Zone)
         {
            if(rates[0].low <= rates[i].high && rates[0].close >= rates[i].low)
               bullishOB = true; // Price currently tapping into Bullish Order Block!
         }
      }
      // Strong Bearish Displacement: candle body is large and broke lows
      if(rates[i-1].close < rates[i-1].open && (rates[i-1].open - rates[i-1].close) > (rates[i].high - rates[i].low) * 0.8)
      {
         if(rates[i].close > rates[i].open) // Up candle prior to displacement (Supply Zone)
         {
            if(rates[0].high >= rates[i].low && rates[0].close <= rates[i].high)
               bearishOB = true; // Price currently tapping into Bearish Order Block!
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   m_symbol.RefreshRates();

   // 1. Daily Equity Reset
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != m_currentDay)
   {
      m_currentDay = today;
      m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   }

   // 2. Daily Loss Limit Check
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDD = ((m_startingDailyEquity - currentEquity) / m_startingDailyEquity) * 100.0;

   // 3. UT Bot Safe Position Management
   ManageOpenPositionsSafe();

   // 4. Track Exits for Cooldown Guard
   bool currentlyInTrade = HasOpenPosition();
   if(g_wasInPosition && !currentlyInTrade)
   {
      g_lastExitTime = TimeCurrent();
      Print("⏳ Trade closed. Cooldown activated for ", InpCooldownBars, " bar(s).");
   }
   g_wasInPosition = currentlyInTrade;

   // 5. Run Squeeze Momentum & SMC Calculations on every tick
   bool sqzOn = false, sqzOff = false;
   double sqzVal = 0, sqzValPrev = 0;
   string momColor = "";
   CalculateSqueezeMomentum(sqzOn, sqzOff, sqzVal, sqzValPrev, momColor);

   g_lastSqzVal = sqzVal;
   g_sqzStateStr = sqzOn ? "🟡 SQZ ON (Coiling Energy)" : (sqzOff ? "🚀 SQZ FIRED (Explosion)" : "⚪ NO SQUEEZE");
   g_momColorStr = momColor;
   g_isSqzFired = sqzOff;

   bool bullishOB = false, bearishOB = false, sweptLow = false, sweptHigh = false;
   DetectLuxAlgoSMC(bullishOB, bearishOB, sweptLow, sweptHigh);
   g_smcStateStr = bullishOB ? "BULLISH OB 📦" : (bearishOB ? "BEARISH OB 📦" : (sweptLow ? "SWEEP LOW 🪤" : (sweptHigh ? "SWEEP HIGH 🪤" : "STRUCTURE SCAN 🔍")));

   // 6. Update HUD Dashboard
   UpdateQuantHUD(dailyDD);

   if(dailyDD >= InpMaxDailyLossPct)
   {
      Comment("\n🚨 DAILY KILL-SWITCH TRIGGERED: Loss ", DoubleToString(dailyDD, 1), "%. Trading locked.");
      return;
   }

   // 7. Check New Candle Event
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == m_lastBarTime) return;

   // 8. Check Spread Protection
   double currentSpread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxSpreadPoints)
   {
      g_lastSignalReason = "Spread too high (" + DoubleToString(currentSpread, 0) + " pts)";
      return;
   }

   // 9. Max 1 Position Guard
   if(HasOpenPosition()) return;

   // 10. Execute Hybrid Strategy
   CheckAndExecuteHybridTrade(sqzOn, sqzOff, sqzVal, sqzValPrev, bullishOB, bearishOB, sweptLow, sweptHigh);

   m_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//| Execute Hybrid Trade (LuxAlgo SMC + LazyBear Squeeze)            |
//+------------------------------------------------------------------+
void CheckAndExecuteHybridTrade(bool sqzOn, bool sqzOff, double sqzVal, double sqzValPrev,
                               bool bullishOB, bool bearishOB, bool sweptLow, bool sweptHigh)
{
   // Cooldown check
   int cooldownSeconds = InpCooldownBars * PeriodSeconds(_Period);
   if(TimeCurrent() - g_lastExitTime < cooldownSeconds)
   {
      int remaining = (int)(cooldownSeconds - (TimeCurrent() - g_lastExitTime));
      g_lastSignalReason = "⏳ Cooldown Active (" + IntegerToString(remaining) + "s remaining)";
      return;
   }

   double atr[2];
   if(CopyBuffer(h_atr, 0, 1, 2, atr) < 2) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, 5, rates) < 5) return;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double safeBuffer = atr[0] * 1.3;
   double minStopDist = MathMax((double)stopLevel * _Point, 25 * _Point);
   if(safeBuffer < minStopDist) safeBuffer = minStopDist;

   // --- BUY TRIGGER ---
   // 1. LazyBear: Momentum is positive and accelerating (Lime Green: val > 0 && val > valPrev)
   // 2. Squeeze: Not coiling (sqzOff == true)
   // 3. LuxAlgo SMC: Price tapped Bullish Order Block OR swept liquidity low
   // 4. Candle: Bullish confirmation
   bool sqzBuySignal = (sqzVal > 0 && sqzVal > sqzValPrev) && (!InpUseSqueezeFilter || sqzOff);
   bool smcBuySignal = (!InpUseOrderBlocks || bullishOB || sweptLow);
   bool candleBuy    = (rates[1].close >= rates[1].open || rates[0].close >= rates[0].open);

   if(sqzBuySignal && smcBuySignal && candleBuy)
   {
      double entryPrice = m_symbol.Ask();
      double sl = entryPrice - safeBuffer;
      double riskPoints = entryPrice - sl;
      if(riskPoints <= 0) return;

      double tp = entryPrice + (riskPoints * InpRiskRewardRatio);
      m_trade.Buy(InpFixedLot, _Symbol, entryPrice, sl, tp, "Hybrid BUY [SMC+SQZ]");
      g_lastSignalReason = "🚀 BUY Executed (LuxAlgo SMC + LazyBear Squeeze)";
      Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
      return;
   }

   // --- SELL TRIGGER ---
   // 1. LazyBear: Momentum is negative and expanding (Bright Red: val < 0 && val < valPrev)
   // 2. Squeeze: Not coiling (sqzOff == true)
   // 3. LuxAlgo SMC: Price tapped Bearish Order Block OR swept liquidity high
   // 4. Candle: Bearish confirmation
   bool sqzSellSignal = (sqzVal < 0 && sqzVal < sqzValPrev) && (!InpUseSqueezeFilter || sqzOff);
   bool smcSellSignal = (!InpUseOrderBlocks || bearishOB || sweptHigh);
   bool candleSell    = (rates[1].close <= rates[1].open || rates[0].close <= rates[0].open);

   if(sqzSellSignal && smcSellSignal && candleSell)
   {
      double entryPrice = m_symbol.Bid();
      double sl = entryPrice + safeBuffer;
      double riskPoints = sl - entryPrice;
      if(riskPoints <= 0) return;

      double tp = entryPrice - (riskPoints * InpRiskRewardRatio);
      m_trade.Sell(InpFixedLot, _Symbol, entryPrice, sl, tp, "Hybrid SELL [SMC+SQZ]");
      g_lastSignalReason = "🔻 SELL Executed (LuxAlgo SMC + LazyBear Squeeze)";
      Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
      return;
   }

   g_lastSignalReason = "Scanning Fusion Setup (SQZ: " + (sqzOff?"OFF":"ON") + " | SMC: " + g_smcStateStr + ")";
}

//+------------------------------------------------------------------+
//| UT Bot Safe Position Management (Break-Even & Dynamic Trailing)  |
//+------------------------------------------------------------------+
void ManageOpenPositionsSafe()
{
   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minStopDist = MathMax((double)stopLevel, 30.0) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Magic() != InpMagicNumber || m_position.Symbol() != _Symbol) continue;

      double openPrice   = m_position.PriceOpen();
      double currentSL   = m_position.StopLoss();
      double currentTP   = m_position.TakeProfit();
      double currentPrice= (m_position.PositionType() == POSITION_TYPE_BUY) ? m_symbol.Bid() : m_symbol.Ask();

      double initialRisk = MathAbs(openPrice - currentSL);
      if(initialRisk <= 0) continue;

      // 1. Break-Even Check (UT Bot Fast Guard)
      if(m_position.PositionType() == POSITION_TYPE_BUY)
      {
         double profitPoints = currentPrice - openPrice;
         if(profitPoints >= initialRisk * InpBreakEvenTriggerR && currentSL < openPrice)
         {
            double newSL = openPrice + minStopDist;
            if(currentPrice - newSL > minStopDist)
            {
               m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
               Print("🛡️ BUY SL moved to Break-Even");
            }
         }

         // 2. Trailing Stop Check
         if(InpUseTrailingStop && profitPoints >= initialRisk * InpTrailingTriggerR)
         {
            double trailingSL = currentPrice - (initialRisk * 0.7);
            if(trailingSL > currentSL && (currentPrice - trailingSL > minStopDist))
            {
               m_trade.PositionModify(m_position.Ticket(), trailingSL, currentTP);
            }
         }
      }
      else if(m_position.PositionType() == POSITION_TYPE_SELL)
      {
         double profitPoints = openPrice - currentPrice;
         if(profitPoints >= initialRisk * InpBreakEvenTriggerR && (currentSL > openPrice || currentSL == 0))
         {
            double newSL = openPrice - minStopDist;
            if(newSL - currentPrice > minStopDist)
            {
               m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
               Print("🛡️ SELL SL moved to Break-Even");
            }
         }

         // 2. Trailing Stop Check
         if(InpUseTrailingStop && profitPoints >= initialRisk * InpTrailingTriggerR)
         {
            double trailingSL = currentPrice + (initialRisk * 0.7);
            if((trailingSL < currentSL || currentSL == 0) && (trailingSL - currentPrice > minStopDist))
            {
               m_trade.PositionModify(m_position.Ticket(), trailingSL, currentTP);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
            return true;
      }
   }
   return false;
}

void UpdateQuantHUD(double dailyDD)
{
   string accMode = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO (Safe)" : "REAL (Live)";
   string hud = "===========================================\n";
   hud += "  ⚡ TV HYBRID 4.0: LUXALGO SMC + LAZYBEAR ⚡\n";
   hud += "===========================================\n";
   hud += " Account Mode   : " + accMode + " ($" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ")\n";
   hud += " Spread Check   : " + IntegerToString((long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)) + " pts\n";
   hud += "-------------------------------------------\n";
   hud += " LazyBear SQZ   : " + g_sqzStateStr + "\n";
   hud += " SQZ Momentum   : " + g_momColorStr + "\n";
   hud += " LuxAlgo SMC    : " + g_smcStateStr + "\n";
   hud += " Status         : " + g_lastSignalReason + "\n";
   hud += " Active Trades  : " + (HasOpenPosition() ? "IN TRADE 🟢" : "READY / HUNTING 🎯") + "\n";
   hud += "===========================================";
   Comment(hud);
}
