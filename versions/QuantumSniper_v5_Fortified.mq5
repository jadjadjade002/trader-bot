//+------------------------------------------------------------------+
//|                                    QuantumSniper_v5_Fortified.mq5|
//|        v5.0 Fortified: All 14 Vulnerabilities Patched            |
//|        H1 Trend Filter + Strict Scoring + LinReg Fix + Safety    |
//+------------------------------------------------------------------+
#property copyright "QuantumSniper Fortified v5.0"
#property link      "https://www.mql5.com"
#property version   "5.00"
#property description "v5.0: H1 Trend Filter, Fixed LinReg, Strict AND Logic, Max Trades/Day, Losing Streak Guard, Extended Cooldown"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== 1. ACCOUNT SAFETY & DEMO GUARD ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 550500;     // Magic Number (v5 unique: 550500)
input double   InpMaxSpreadPoints      = 50.0;       // Max Spread Allowed (Points)
input double   InpMaxDailyLossPct      = 10.0;       // Daily Drawdown Auto-Kill Switch (%)
input int      InpMaxTradesPerDay      = 15;         // Max Trades Per Day (FIX #4)
input int      InpMaxLosingStreak      = 3;          // Max Consecutive Losses Before Pause (FIX #4)

input group "=== 2. HIGHER TIMEFRAME TREND FILTER (FIX #3) ==="
input bool     InpUseHTFFilter         = true;       // Require H1 Trend Alignment
input ENUM_TIMEFRAMES InpHTF_Period    = PERIOD_H1;  // Higher Timeframe
input int      InpHTF_EMA_Fast         = 20;         // HTF Fast EMA
input int      InpHTF_EMA_Slow         = 50;         // HTF Slow EMA

input group "=== 3. LAZYBEAR SQUEEZE MOMENTUM ENGINE ==="
input bool     InpUseSqueezeFilter     = true;       // Require Squeeze Release to Fire
input int      InpBBLength             = 20;         // Bollinger Bands Length
input double   InpBBMult               = 2.0;        // Bollinger Bands Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Length
input double   InpKCMult               = 1.5;        // Keltner Channel Multiplier

input group "=== 4. LUXALGO SMART MONEY CONCEPTS (SMC) ==="
input bool     InpUseOrderBlocks       = true;       // Filter entries with Institutional Order Blocks
input int      InpSMC_Lookback         = 30;         // Order Block Scan Lookback (Bars) — was 15 (FIX #6)
input int      InpSweepBars            = 3;          // Liquidity Sweep Window (Bars)
input double   InpOB_BodyRatio         = 0.6;        // OB Displacement Body Ratio (was 0.8) (FIX #6)

input group "=== 5. RISK & UT BOT TRAILING MANAGEMENT ==="
input double   InpFixedLot             = 0.01;       // Fixed Lot Size (0.01 for $50)
input double   InpRiskRewardRatio      = 1.8;        // Target Risk:Reward Ratio
input double   InpBreakEvenTriggerR    = 0.8;        // Fast Break-Even Trigger (at 0.8R Profit)
input bool     InpUseTrailingStop      = true;       // Enable UT Bot Dynamic Trailing Stop
input double   InpTrailingTriggerR     = 1.2;        // Activate Trailing at 1.2R Profit
input int      InpCooldownBars         = 3;          // Cooldown Period After Exit (Bars) — was 1 (FIX #11)

//--- GLOBAL OBJECTS & HANDLES ---
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

int            h_atr;
int            h_htf_emaFast;       // FIX #3: H1 trend filter
int            h_htf_emaSlow;       // FIX #3: H1 trend filter
datetime       m_lastBarTime;
double         m_startingDailyEquity;
datetime       m_currentDay;

// FIX #4: Trade counting & streak tracking
int            g_dailyTradeCount = 0;
int            g_losingStreak    = 0;
datetime       g_tradeCountDay   = 0;

// FIX #7: Store initial risk per position (by ticket)
double         g_initialRisk     = 0;
ulong          g_trackedTicket   = 0;

// Cooldown Tracker
datetime       g_lastExitTime = 0;
bool           g_wasInPosition = false;

// Squeeze & SMC Diagnostics
string         g_sqzStateStr = "NEUTRAL";
string         g_momColorStr = "NEUTRAL";
string         g_smcStateStr = "SCANNING";
double         g_lastSqzVal = 0.0;
bool           g_isSqzFired = false;
string         g_lastSignalReason = "v5.0 Fortified Engine Ready";
string         g_htfBias = "UNKNOWN";

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

   // FIX #3: Higher Timeframe EMA handles
   h_htf_emaFast = iMA(_Symbol, InpHTF_Period, InpHTF_EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   h_htf_emaSlow = iMA(_Symbol, InpHTF_Period, InpHTF_EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   if(h_htf_emaFast == INVALID_HANDLE || h_htf_emaSlow == INVALID_HANDLE)
   {
      Print("❌ Failed to initialize HTF EMA handles");
      return(INIT_FAILED);
   }

   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_currentDay = iTime(_Symbol, PERIOD_D1, 0);
   m_lastBarTime = 0;
   g_wasInPosition = HasOpenPosition();
   g_tradeCountDay = m_currentDay;

   Print("⚡ QuantumSniper v5.0 FORTIFIED Initialized on ", _Symbol, " (TF: ", EnumToString(_Period), ")");
   Print("   HTF Filter: ", InpUseHTFFilter ? "ON ("+EnumToString(InpHTF_Period)+")" : "OFF");
   Print("   Max Trades/Day: ", InpMaxTradesPerDay, " | Max Losing Streak: ", InpMaxLosingStreak);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr);
   IndicatorRelease(h_htf_emaFast);
   IndicatorRelease(h_htf_emaSlow);
   Comment("");
}

//+------------------------------------------------------------------+
//| FIX #5: Linear Regression — returns fitted value at CURRENT bar  |
//+------------------------------------------------------------------+
double CalculateLinReg(const double &arr[], int length)
{
   if(length <= 1) return 0;
   double sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
   for(int i = 0; i < length; i++)
   {
      double x = (double)i;
      double y = arr[i]; // arr[0] is current bar
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumXX += x * x;
   }
   double denominator = (length * sumXX - sumX * sumX);
   if(denominator == 0) return arr[0];
   double slope = (length * sumXY - sumX * sumY) / denominator;
   double intercept = (sumY - slope * sumX) / length;
   // FIX #5: Pine Script linreg returns the fitted value at the LAST point (x = length-1)
   // NOT the intercept (x = 0). This was causing delayed momentum signals.
   return intercept + slope * (length - 1);
}

//+------------------------------------------------------------------+
//| LazyBear Squeeze Momentum Calculator                             |
//+------------------------------------------------------------------+
void CalculateSqueezeMomentum(bool &sqzOn, bool &sqzOff, double &val, double &valPrev, string &momColor)
{
   int totalNeeded = MathMax(InpBBLength, InpKCLength) * 2 + 5;
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

   // 3. Calculate Linear Regression Momentum for Bar 0 and Bar 1
   double diffArr0[], diffArr1[];
   ArrayResize(diffArr0, InpKCLength);
   ArrayResize(diffArr1, InpKCLength);
   
   for(int j = 0; j < InpKCLength; j++)
   {
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
//| FIX #6: LuxAlgo SMC — Extended lookback + relaxed body ratio     |
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

   // 2. FIX #6: Extended Order Block scan (2 to InpSMC_Lookback) with relaxed ratio
   bullishOB = false;
   bearishOB = false;
   int scanLimit = MathMin(InpSMC_Lookback, ArraySize(rates) - 2);
   
   for(int i = 2; i <= scanLimit; i++)
   {
      double candleRange = rates[i].high - rates[i].low;
      if(candleRange <= 0) continue;
      
      // Strong Bullish Displacement
      if(rates[i-1].close > rates[i-1].open && (rates[i-1].close - rates[i-1].open) > candleRange * InpOB_BodyRatio)
      {
         if(rates[i].close < rates[i].open) // Down candle = Demand Zone
         {
            if(rates[0].low <= rates[i].high && rates[0].close >= rates[i].low)
               bullishOB = true;
         }
      }
      // Strong Bearish Displacement
      if(rates[i-1].close < rates[i-1].open && (rates[i-1].open - rates[i-1].close) > candleRange * InpOB_BodyRatio)
      {
         if(rates[i].close > rates[i].open) // Up candle = Supply Zone
         {
            if(rates[0].high >= rates[i].low && rates[0].close <= rates[i].high)
               bearishOB = true;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| FIX #3: Higher Timeframe Trend Filter                            |
//+------------------------------------------------------------------+
int GetHTFBias()
{
   if(!InpUseHTFFilter) return 0; // 0 = no filter (allow both)
   
   double htfFast[2], htfSlow[2];
   if(CopyBuffer(h_htf_emaFast, 0, 0, 2, htfFast) < 2) return 0;
   if(CopyBuffer(h_htf_emaSlow, 0, 0, 2, htfSlow) < 2) return 0;
   
   // Get current price relative to HTF EMAs
   double currentPrice = m_symbol.Bid();
   
   if(htfFast[0] > htfSlow[0] && currentPrice > htfFast[0])
   {
      g_htfBias = "BULLISH ↑ (H1 EMA" + IntegerToString(InpHTF_EMA_Fast) + " > EMA" + IntegerToString(InpHTF_EMA_Slow) + ")";
      return 1;  // Only BUY allowed
   }
   else if(htfFast[0] < htfSlow[0] && currentPrice < htfFast[0])
   {
      g_htfBias = "BEARISH ↓ (H1 EMA" + IntegerToString(InpHTF_EMA_Fast) + " < EMA" + IntegerToString(InpHTF_EMA_Slow) + ")";
      return -1; // Only SELL allowed
   }
   else
   {
      g_htfBias = "RANGING ↔ (No Clear H1 Trend)";
      return 0;  // Block both — no trade in choppy H1
   }
}

//+------------------------------------------------------------------+
//| FIX #4: Count today's trades from history                        |
//+------------------------------------------------------------------+
void UpdateDailyTradeStats()
{
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   
   // Reset on new day
   if(today != g_tradeCountDay)
   {
      g_tradeCountDay = today;
      g_dailyTradeCount = 0;
      g_losingStreak = 0;
   }
   
   // Count from deal history
   datetime dayStart = today;
   datetime now = TimeCurrent();
   HistorySelect(dayStart, now);
   
   int totalDeals = HistoryDealsTotal();
   g_dailyTradeCount = 0;
   g_losingStreak = 0;
   int tempStreak = 0;
   
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagicNumber) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      
      long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(dealEntry == DEAL_ENTRY_OUT || dealEntry == DEAL_ENTRY_INOUT)
      {
         g_dailyTradeCount++;
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_COMMISSION) + HistoryDealGetDouble(ticket, DEAL_SWAP);
         
         if(profit < 0)
            tempStreak++;
         else
            tempStreak = 0;
      }
   }
   g_losingStreak = tempStreak;
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

   // 5. FIX #4: Update trade stats
   UpdateDailyTradeStats();

   // 6. Update HUD (before new bar check so dashboard always shows)
   UpdateQuantHUD(dailyDD);

   if(dailyDD >= InpMaxDailyLossPct)
   {
      Comment("\n🚨 DAILY KILL-SWITCH TRIGGERED: Loss ", DoubleToString(dailyDD, 1), "%. Trading locked.");
      return;
   }

   // 7. Check New Candle Event
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == m_lastBarTime) return;

   // 8. Check Spread Protection — FIX #9: update m_lastBarTime even on spread reject
   double currentSpread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxSpreadPoints)
   {
      g_lastSignalReason = "Spread too high (" + DoubleToString(currentSpread, 0) + " pts)";
      m_lastBarTime = currentBarTime; // FIX #9: Don't retry this bar
      return;
   }

   // 9. Max 1 Position Guard
   if(HasOpenPosition())
   {
      m_lastBarTime = currentBarTime;
      return;
   }

   // 10. FIX #14: Calculate Squeeze & SMC ONLY on new bar (not every tick)
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

   // 11. Execute Hybrid Strategy
   CheckAndExecuteHybridTrade(sqzOn, sqzOff, sqzVal, sqzValPrev, bullishOB, bearishOB, sweptLow, sweptHigh);

   m_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//| Execute Hybrid Trade — ALL FIXES APPLIED                         |
//+------------------------------------------------------------------+
void CheckAndExecuteHybridTrade(bool sqzOn, bool sqzOff, double sqzVal, double sqzValPrev,
                               bool bullishOB, bool bearishOB, bool sweptLow, bool sweptHigh)
{
   // Cooldown check (FIX #11: now 3 bars default)
   int cooldownSeconds = InpCooldownBars * PeriodSeconds(_Period);
   if(TimeCurrent() - g_lastExitTime < cooldownSeconds)
   {
      int remaining = (int)(cooldownSeconds - (TimeCurrent() - g_lastExitTime));
      g_lastSignalReason = "⏳ Cooldown Active (" + IntegerToString(remaining) + "s remaining)";
      return;
   }

   // FIX #4: Max trades per day check
   if(g_dailyTradeCount >= InpMaxTradesPerDay)
   {
      g_lastSignalReason = "🚫 Max Trades/Day Reached (" + IntegerToString(g_dailyTradeCount) + "/" + IntegerToString(InpMaxTradesPerDay) + ")";
      return;
   }

   // FIX #4: Losing streak check
   if(g_losingStreak >= InpMaxLosingStreak)
   {
      g_lastSignalReason = "🛑 Losing Streak Pause (" + IntegerToString(g_losingStreak) + " losses in a row)";
      return;
   }

   // FIX #3: Higher Timeframe bias
   int htfBias = GetHTFBias();

   // FIX #12: ATR from bar 0 (not bar 1)
   double atr[1];
   if(CopyBuffer(h_atr, 0, 0, 1, atr) < 1) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, 5, rates) < 5) return;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double safeBuffer = atr[0] * 1.3;
   double minStopDist = MathMax((double)stopLevel * _Point, 25 * _Point);
   if(safeBuffer < minStopDist) safeBuffer = minStopDist;

   // --- Compute signals ---
   // FIX #1, #2, #10: Use AND logic, make BUY/SELL mutually exclusive
   
   // Squeeze signal (momentum direction)
   bool sqzBull = (sqzVal > 0 && sqzVal > sqzValPrev);
   bool sqzBear = (sqzVal < 0 && sqzVal < sqzValPrev);
   
   // Squeeze release required
   bool sqzReady = (!InpUseSqueezeFilter || sqzOff);
   
   // FIX #10: SMC must have BOTH OB AND Sweep (not OR)
   bool smcBuyReady  = false;
   bool smcSellReady = false;
   if(!InpUseOrderBlocks)
   {
      smcBuyReady = true;
      smcSellReady = true;
   }
   else
   {
      smcBuyReady  = (bullishOB && sweptLow);   // Must have BOTH OB + Sweep
      smcSellReady = (bearishOB && sweptHigh);   // Must have BOTH OB + Sweep
   }
   
   // FIX #1: Candle confirmation — AND logic (both current AND previous must confirm)
   bool candleBuy  = (rates[1].close > rates[1].open) && (rates[0].close >= rates[0].open);
   bool candleSell = (rates[1].close < rates[1].open) && (rates[0].close <= rates[0].open);

   // Build final signals
   bool buySignal  = sqzBull && sqzReady && smcBuyReady && candleBuy;
   bool sellSignal = sqzBear && sqzReady && smcSellReady && candleSell;
   
   // FIX #2: If both signal, pick the stronger one (or block both)
   if(buySignal && sellSignal)
   {
      // Both fired — ambiguous market, skip
      g_lastSignalReason = "⚠️ BUY+SELL Conflict — Market Ambiguous, Skipping";
      Print(g_lastSignalReason);
      return;
   }

   // FIX #3: Apply HTF bias filter
   if(buySignal && htfBias == -1)
   {
      g_lastSignalReason = "🚫 BUY Blocked (H1 Trend = BEARISH)";
      return;
   }
   if(sellSignal && htfBias == 1)
   {
      g_lastSignalReason = "🚫 SELL Blocked (H1 Trend = BULLISH)";
      return;
   }
   // If htfBias == 0 (ranging) and InpUseHTFFilter is true → block all trades
   if(InpUseHTFFilter && htfBias == 0)
   {
      g_lastSignalReason = "🚫 No Clear H1 Trend — Standing Down";
      return;
   }

   // --- BUY TRIGGER ---
   if(buySignal)
   {
      double entryPrice = m_symbol.Ask();
      double sl = entryPrice - safeBuffer;
      double riskPoints = entryPrice - sl;
      if(riskPoints <= 0) return;

      double tp = entryPrice + (riskPoints * InpRiskRewardRatio);
      
      if(m_trade.Buy(InpFixedLot, _Symbol, entryPrice, sl, tp, "v5 BUY [SMC+SQZ+H1]"))
      {
         // FIX #13: Check trade result
         if(m_trade.ResultRetcode() == TRADE_RETCODE_DONE || m_trade.ResultRetcode() == TRADE_RETCODE_PLACED)
         {
            g_lastSignalReason = "🚀 BUY Executed (H1:" + g_htfBias + ")";
            // FIX #7: Store initial risk for this trade
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
         }
         else
         {
            Print("❌ BUY Failed: retcode=", m_trade.ResultRetcode(), " comment=", m_trade.ResultComment());
         }
      }
      return;
   }

   // --- SELL TRIGGER ---
   if(sellSignal)
   {
      double entryPrice = m_symbol.Bid();
      double sl = entryPrice + safeBuffer;
      double riskPoints = sl - entryPrice;
      if(riskPoints <= 0) return;

      double tp = entryPrice - (riskPoints * InpRiskRewardRatio);
      
      if(m_trade.Sell(InpFixedLot, _Symbol, entryPrice, sl, tp, "v5 SELL [SMC+SQZ+H1]"))
      {
         // FIX #13: Check trade result
         if(m_trade.ResultRetcode() == TRADE_RETCODE_DONE || m_trade.ResultRetcode() == TRADE_RETCODE_PLACED)
         {
            g_lastSignalReason = "🔻 SELL Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
         }
         else
         {
            Print("❌ SELL Failed: retcode=", m_trade.ResultRetcode(), " comment=", m_trade.ResultComment());
         }
      }
      return;
   }

   g_lastSignalReason = "Scanning Fusion (SQZ:" + (sqzOff?"OFF":"ON") + " SMC:" + g_smcStateStr + " H1:" + g_htfBias + ")";
}

//+------------------------------------------------------------------+
//| FIX #7: UT Bot Safe Position Management — uses stored initialRisk|
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

      // FIX #7: Use stored initial risk if available, otherwise calculate from SL
      double initialRisk;
      if(g_trackedTicket == m_position.Ticket() && g_initialRisk > 0)
         initialRisk = g_initialRisk;  // Use the ORIGINAL risk, not current SL distance
      else
         initialRisk = MathAbs(openPrice - currentSL);
      
      if(initialRisk <= 0) continue;

      // 1. Break-Even Check
      if(m_position.PositionType() == POSITION_TYPE_BUY)
      {
         double profitPoints = currentPrice - openPrice;
         if(profitPoints >= initialRisk * InpBreakEvenTriggerR && currentSL < openPrice)
         {
            // FIX #7: Break-Even at openPrice + small buffer (not minStopDist)
            double beBuffer = MathMax(minStopDist, m_symbol.Spread() * _Point * 2);
            double newSL = openPrice + beBuffer;
            if(currentPrice - newSL > minStopDist)
            {
               m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
               Print("🛡️ BUY SL moved to Break-Even+Buffer");
            }
         }

         // 2. Trailing Stop Check — uses stored initialRisk
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
            double beBuffer = MathMax(minStopDist, m_symbol.Spread() * _Point * 2);
            double newSL = openPrice - beBuffer;
            if(newSL - currentPrice > minStopDist)
            {
               m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
               Print("🛡️ SELL SL moved to Break-Even+Buffer");
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
   hud += "  ⚡ QUANTUM SNIPER v5.0 FORTIFIED ⚡\n";
   hud += "===========================================\n";
   hud += " Account Mode   : " + accMode + " ($" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ")\n";
   hud += " Spread Check   : " + IntegerToString((long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)) + " pts\n";
   hud += "-------------------------------------------\n";
   hud += " H1 Trend Bias  : " + g_htfBias + "\n";
   hud += " LazyBear SQZ   : " + g_sqzStateStr + "\n";
   hud += " SQZ Momentum   : " + g_momColorStr + "\n";
   hud += " LuxAlgo SMC    : " + g_smcStateStr + "\n";
   hud += "-------------------------------------------\n";
   hud += " Trades Today   : " + IntegerToString(g_dailyTradeCount) + "/" + IntegerToString(InpMaxTradesPerDay) + "\n";
   hud += " Losing Streak  : " + IntegerToString(g_losingStreak) + "/" + IntegerToString(InpMaxLosingStreak) + "\n";
   hud += " Daily DD       : " + DoubleToString(dailyDD, 1) + "% / " + DoubleToString(InpMaxDailyLossPct, 0) + "%\n";
   hud += " Status         : " + g_lastSignalReason + "\n";
   hud += " Active Trades  : " + (HasOpenPosition() ? "IN TRADE 🟢" : "READY / HUNTING 🎯") + "\n";
   hud += "===========================================";
   Comment(hud);
}
