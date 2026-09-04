//+------------------------------------------------------------------+
//|                                QuantumSniper_v6_Institutional.mq5|
//|            v6.0 Institutional Master Edition                     |
//|      MQL5 Economic News Filter + H1 Trend + SMC + SQZ + Safety   |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumSniper Institutional v6.0"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "6.00"
#property description "v6.0: Native MQL5 News Calendar Engine, Session Filter, Strict SMC & SQZ Confluence, Stepped Trailing, Auto Chart Visualizer"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== 1. ACCOUNT SECURITY & CAPITAL PRESERVATION ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 660600;     // Magic Number (v6 Institutional ID)
input double   InpMaxSpreadPoints      = 45.0;       // Max Allowed Spread (Points)
input double   InpMaxDailyLossPct      = 8.0;        // Daily Loss Kill-Switch (%)
input double   InpHardEquityFloor      = 30.0;       // Hard Equity Floor ($) - Stop All Trading
input int      InpMaxTradesPerDay      = 12;         // Maximum Completed Trades Per Day
input int      InpMaxLosingStreak      = 3;          // Max Consecutive Losses Before Pausing

input group "=== 2. MQL5 NATIVE ECONOMIC NEWS FILTER ==="
input bool     InpUseNewsFilter        = true;       // Enable Economic Calendar News Filter
input int      InpNewsBufferMinsBefore = 30;         // Pause Trading Before High-Impact News (Mins)
input int      InpNewsBufferMinsAfter  = 30;         // Pause Trading After High-Impact News (Mins)
input bool     InpFilterUSDOnly        = true;       // Filter USD News (Critical for Gold XAUUSD)

input group "=== 3. TRADING SESSION & TIME FILTER ==="
input bool     InpUseSessionFilter     = true;       // Enable Active Trading Hours Filter
input int      InpTradeHourStart       = 13;         // Start Hour (Server Time, ~London Open)
input int      InpTradeHourEnd         = 23;         // End Hour (Server Time, ~NY Close)
input bool     InpCloseFridayNight     = true;       // Avoid Weekend Gaps (No new trades late Friday)

input group "=== 4. HIGHER TIMEFRAME TREND FILTER (H1) ==="
input bool     InpUseHTFFilter         = true;       // Require H1 Trend Alignment
input ENUM_TIMEFRAMES InpHTF_Period    = PERIOD_H1;  // Higher Timeframe
input int      InpHTF_EMA_Fast         = 20;         // HTF Fast EMA Period
input int      InpHTF_EMA_Slow         = 50;         // HTF Slow EMA Period

input group "=== 5. LAZYBEAR SQUEEZE MOMENTUM ENGINE ==="
input bool     InpUseSqueezeFilter     = true;       // Require Squeeze Release (sqzOff)
input int      InpBBLength             = 20;         // Bollinger Bands Length
input double   InpBBMult               = 2.0;        // Bollinger Bands Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Length
input double   InpKCMult               = 1.5;        // Keltner Channel Multiplier

input group "=== 6. LUXALGO SMART MONEY CONCEPTS (SMC) ==="
input bool     InpUseOrderBlocks       = true;       // Institutional Order Block Requirement
input int      InpSMC_Lookback         = 30;         // Order Block Scan Window (Bars)
input int      InpSweepBars            = 3;          // Liquidity Sweep Window (Bars)
input double   InpOB_BodyRatio         = 0.6;        // Displacement Body-to-Range Ratio

input group "=== 7. EXECUTION, RISK & TRAILING MANAGEMENT ==="
input double   InpFixedLot             = 0.01;       // Lot Size (0.01 Recommended for  Port)
input double   InpRiskRewardRatio      = 1.8;        // Target Risk:Reward Ratio
input double   InpBreakEvenTriggerR    = 0.8;        // Break-Even Activation at 0.8R Profit
input bool     InpUseTrailingStop      = true;       // Enable Dynamic Stepped Trailing Stop
input double   InpTrailingTriggerR     = 1.2;        // Trailing Activation at 1.2R Profit
input int      InpCooldownBars         = 3;          // Post-Trade Cooldown (Bars)

//--- GLOBAL OBJECTS & HANDLES ---
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

int            h_atr;
int            h_htf_emaFast;
int            h_htf_emaSlow;

datetime       m_lastBarTime;
double         m_startingDailyEquity;
datetime       m_currentDay;

// Daily Trade & Streak Tracking
int            g_dailyTradeCount = 0;
int            g_losingStreak    = 0;
datetime       g_tradeCountDay   = 0;

// Stored Original Risk per position
double         g_initialRisk     = 0;
ulong          g_trackedTicket   = 0;

// Cooldown Tracker
datetime       g_lastExitTime    = 0;
bool           g_wasInPosition   = false;

// Real-Time Engine Diagnostics
string         g_sqzStateStr     = "NEUTRAL";
string         g_momColorStr     = "NEUTRAL";
string         g_smcStateStr     = "SCANNING";
string         g_htfBias         = "UNKNOWN";
string         g_newsStatusStr   = "CALENDAR CLEAR 🟢";
string         g_lastSignalReason= "v6.0 Institutional Engine Ready";
double         g_lastSqzVal      = 0.0;
bool           g_isSqzFired      = false;

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

   Print("⚡ QuantumSniper v6.0 INSTITUTIONAL Initialized on ", _Symbol, " (", EnumToString(_Period), ")");
   Print("   News Calendar Filter : ", InpUseNewsFilter ? "ACTIVE (USD High-Impact)" : "OFF");
   Print("   Session Filter       : ", InpUseSessionFilter ? (IntegerToString(InpTradeHourStart)+":00 - "+IntegerToString(InpTradeHourEnd)+":00") : "24/7");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr);
   IndicatorRelease(h_htf_emaFast);
   IndicatorRelease(h_htf_emaSlow);
   Comment("");
}

//+------------------------------------------------------------------+
//| MQL5 Native Economic Calendar News Filter                        |
//+------------------------------------------------------------------+
bool IsInHighImpactNewsWindow(string &newsEventName)
{
   if(!InpUseNewsFilter) return false;

   datetime serverTime = TimeTradeServer();
   datetime timeFrom = serverTime - (InpNewsBufferMinsAfter * 60);
   datetime timeTo   = serverTime + (InpNewsBufferMinsBefore * 60);

   MqlCalendarValue values[];
   string currencyFilter = InpFilterUSDOnly ? "USD" : NULL;

   int count = CalendarValueHistory(values, timeFrom, timeTo, NULL, currencyFilter);
   if(count <= 0) return false;

   for(int i = 0; i < count; i++)
   {
      MqlCalendarEvent event;
      if(CalendarEventById(values[i].event_id, event))
      {
         if(event.importance == CALENDAR_IMPORTANCE_HIGH)
         {
            newsEventName = event.name + " [High Impact]";
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Trading Session & Weekend Gap Filter                             |
//+------------------------------------------------------------------+
bool IsAllowedTradingTime()
{
   MqlDateTime dt;
   TimeTradeServer(dt);

   // Avoid weekend holding (No new orders after Friday 20:00 server time)
   if(InpCloseFridayNight && dt.day_of_week == 5 && dt.hour >= 20)
   {
      g_lastSignalReason = "🛑 Friday Evening Weekend Guard Active";
      return false;
   }

   if(!InpUseSessionFilter) return true;

   if(dt.hour < InpTradeHourStart || dt.hour >= InpTradeHourEnd)
   {
      g_lastSignalReason = "⏳ Off-Session (" + IntegerToString(dt.hour) + ":00 outside " +
                           IntegerToString(InpTradeHourStart) + "-" + IntegerToString(InpTradeHourEnd) + ")";
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Linear Regression Momentum (Fitted value at Current Bar)         |
//+------------------------------------------------------------------+
double CalculateLinReg(const double &arr[], int length)
{
   if(length <= 1) return 0;
   double sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
   for(int i = 0; i < length; i++)
   {
      double x = (double)i;
      double y = arr[i];
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumXX += x * x;
   }
   double denominator = (length * sumXX - sumX * sumX);
   if(denominator == 0) return arr[0];
   double slope = (length * sumXY - sumX * sumY) / denominator;
   double intercept = (sumY - slope * sumX) / length;
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

   // 1. Bollinger Bands (20, 2.0)
   double smaBB = 0;
   for(int i = 0; i < InpBBLength; i++) smaBB += rates[i].close;
   smaBB /= InpBBLength;

   double variance = 0;
   for(int i = 0; i < InpBBLength; i++) variance += MathPow(rates[i].close - smaBB, 2);
   double stdevBB = MathSqrt(variance / InpBBLength);

   double upperBB = smaBB + (InpBBMult * stdevBB);
   double lowerBB = smaBB - (InpBBMult * stdevBB);

   // 2. Keltner Channel (20, 1.5)
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

   sqzOn  = (lowerBB > lowerKC) && (upperBB < upperKC);
   sqzOff = (lowerBB < lowerKC) && (upperBB > upperKC);

   // 3. Linear Regression Momentum
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

   if(val > 0)
      momColor = (val > valPrev) ? "LIME (Bull Explosion) 🟢" : "DARK GREEN (Bull Weakening) 🍏";
   else
      momColor = (val < valPrev) ? "BRIGHT RED (Bear Plunge) 🔴" : "MAROON (Bear Weakening) 🥀";
}

//+------------------------------------------------------------------+
//| LuxAlgo SMC (Order Block + Liquidity Sweep)                      |
//+------------------------------------------------------------------+
void DetectLuxAlgoSMC(bool &bullishOB, bool &bearishOB, bool &sweptLow, bool &sweptHigh)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, InpSMC_Lookback + 5, rates) < InpSMC_Lookback + 5) return;

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

   bullishOB = false;
   bearishOB = false;
   int scanLimit = MathMin(InpSMC_Lookback, ArraySize(rates) - 2);

   for(int i = 2; i <= scanLimit; i++)
   {
      double candleRange = rates[i].high - rates[i].low;
      if(candleRange <= 0) continue;

      if(rates[i-1].close > rates[i-1].open && (rates[i-1].close - rates[i-1].open) > candleRange * InpOB_BodyRatio)
      {
         if(rates[i].close < rates[i].open)
         {
            if(rates[0].low <= rates[i].high && rates[0].close >= rates[i].low)
               bullishOB = true;
         }
      }

      if(rates[i-1].close < rates[i-1].open && (rates[i-1].open - rates[i-1].close) > candleRange * InpOB_BodyRatio)
      {
         if(rates[i].close > rates[i].open)
         {
            if(rates[0].high >= rates[i].low && rates[0].close <= rates[i].high)
               bearishOB = true;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Higher Timeframe Trend Bias (H1 EMA 20/50)                       |
//+------------------------------------------------------------------+
int GetHTFBias()
{
   if(!InpUseHTFFilter) return 0;

   double htfFast[2], htfSlow[2];
   if(CopyBuffer(h_htf_emaFast, 0, 0, 2, htfFast) < 2) return 0;
   if(CopyBuffer(h_htf_emaSlow, 0, 0, 2, htfSlow) < 2) return 0;

   double currentPrice = m_symbol.Bid();

   if(htfFast[0] > htfSlow[0] && currentPrice > htfFast[0])
   {
      g_htfBias = "BULLISH ↑ (H1 EMA20 > EMA50)";
      return 1;
   }
   else if(htfFast[0] < htfSlow[0] && currentPrice < htfFast[0])
   {
      g_htfBias = "BEARISH ↓ (H1 EMA20 < EMA50)";
      return -1;
   }
   else
   {
      g_htfBias = "RANGING ↔ (No Clear H1 Trend)";
      return 0;
   }
}

//+------------------------------------------------------------------+
//| Update Daily Trade Statistics & Losing Streak                    |
//+------------------------------------------------------------------+
void UpdateDailyTradeStats()
{
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != g_tradeCountDay)
   {
      g_tradeCountDay = today;
      g_dailyTradeCount = 0;
      g_losingStreak = 0;
   }

   HistorySelect(today, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   g_dailyTradeCount = 0;
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
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) +
                         HistoryDealGetDouble(ticket, DEAL_COMMISSION) +
                         HistoryDealGetDouble(ticket, DEAL_SWAP);

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

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDD = ((m_startingDailyEquity - currentEquity) / m_startingDailyEquity) * 100.0;

   // Hard Equity Floor Protection
   if(currentEquity < InpHardEquityFloor)
   {
      Comment("\n🚨 CRITICAL HARD EQUITY FLOOR HIT ($", DoubleToString(currentEquity, 2), " < $", DoubleToString(InpHardEquityFloor, 2), "). All Trading Halted.");
      return;
   }

   // 2. Safe Open Position Management
   ManageOpenPositionsSafe();

   // 3. Cooldown Tracker
   bool currentlyInTrade = HasOpenPosition();
   if(g_wasInPosition && !currentlyInTrade)
   {
      g_lastExitTime = TimeCurrent();
      Print("⏳ Trade closed. Cooldown activated for ", InpCooldownBars, " bar(s).");
   }
   g_wasInPosition = currentlyInTrade;

   // 4. Update Daily Trade Stats
   UpdateDailyTradeStats();

   // 5. Check Economic Calendar News Status
   string newsEventName = "";
   bool inNewsWindow = IsInHighImpactNewsWindow(newsEventName);
   if(inNewsWindow)
      g_newsStatusStr = "🛑 HIGH-IMPACT NEWS: " + newsEventName;
   else
      g_newsStatusStr = "CLEAR 🟢 (No News Barrier)";

   // 6. Update HUD Dashboard
   UpdateQuantHUD(dailyDD);

   if(dailyDD >= InpMaxDailyLossPct)
   {
      Comment("\n🚨 DAILY KILL-SWITCH TRIGGERED: Loss ", DoubleToString(dailyDD, 1), "%. Trading locked for the day.");
      return;
   }

   // 7. Check New Candle Event
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == m_lastBarTime) return;

   // 8. Spread Protection
   double currentSpread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxSpreadPoints)
   {
      g_lastSignalReason = "Spread too high (" + DoubleToString(currentSpread, 0) + " pts)";
      m_lastBarTime = currentBarTime;
      return;
   }

   // 9. Max 1 Position Guard
   if(HasOpenPosition())
   {
      m_lastBarTime = currentBarTime;
      return;
   }

   // 10. News Window Guard
   if(inNewsWindow)
   {
      g_lastSignalReason = "🚫 News Lockout: " + newsEventName;
      m_lastBarTime = currentBarTime;
      return;
   }

   // 11. Active Trading Session Guard
   if(!IsAllowedTradingTime())
   {
      m_lastBarTime = currentBarTime;
      return;
   }

   // 12. Calculate Signals on New Bar
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

   // 13. Execute Trade
   CheckAndExecuteInstitutionalTrade(sqzOn, sqzOff, sqzVal, sqzValPrev, bullishOB, bearishOB, sweptLow, sweptHigh, inNewsWindow);

   m_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
void CheckAndExecuteInstitutionalTrade(bool sqzOn, bool sqzOff, double sqzVal, double sqzValPrev,
                                       bool bullishOB, bool bearishOB, bool sweptLow, bool sweptHigh,
                                       bool inNewsWindow)
{
   int cooldownSeconds = InpCooldownBars * PeriodSeconds(_Period);
   if(TimeCurrent() - g_lastExitTime < cooldownSeconds)
   {
      int remaining = (int)(cooldownSeconds - (TimeCurrent() - g_lastExitTime));
      g_lastSignalReason = "⏳ Cooldown Active (" + IntegerToString(remaining) + "s remaining)";
      return;
   }

   if(g_dailyTradeCount >= InpMaxTradesPerDay)
   {
      g_lastSignalReason = "🚫 Max Daily Trades Reached (" + IntegerToString(g_dailyTradeCount) + "/" + IntegerToString(InpMaxTradesPerDay) + ")";
      return;
   }

   if(g_losingStreak >= InpMaxLosingStreak)
   {
      g_lastSignalReason = "🛑 Losing Streak Circuit Breaker (" + IntegerToString(g_losingStreak) + " losses)";
      return;
   }

   int htfBias = GetHTFBias();

   double atr[1];
   if(CopyBuffer(h_atr, 0, 0, 1, atr) < 1) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, 5, rates) < 5) return;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double safeBuffer = atr[0] * 1.3;
   double minStopDist = MathMax((double)stopLevel * _Point, 25 * _Point);
   if(safeBuffer < minStopDist) safeBuffer = minStopDist;

   bool sqzBull = (sqzVal > 0 && sqzVal > sqzValPrev);
   bool sqzBear = (sqzVal < 0 && sqzVal < sqzValPrev);
   bool sqzReady = (!InpUseSqueezeFilter || sqzOff);

   bool smcBuyReady  = InpUseOrderBlocks ? (bullishOB && sweptLow) : true;
   bool smcSellReady = InpUseOrderBlocks ? (bearishOB && sweptHigh) : true;

   bool candleBuy  = (rates[1].close > rates[1].open) && (rates[0].close >= rates[0].open);
   bool candleSell = (rates[1].close < rates[1].open) && (rates[0].close <= rates[0].open);

   bool buySignal  = sqzBull && sqzReady && smcBuyReady && candleBuy;
   bool sellSignal = sqzBear && sqzReady && smcSellReady && candleSell;

   if(buySignal && sellSignal)
   {
      g_lastSignalReason = "⚠️ Dual Conflict (BUY+SELL) - Stood Down";
      return;
   }

   if(buySignal && htfBias == -1)
   {
      g_lastSignalReason = "🚫 BUY Rejected (H1 is BEARISH)";
      return;
   }
   if(sellSignal && htfBias == 1)
   {
      g_lastSignalReason = "🚫 SELL Rejected (H1 is BULLISH)";
      return;
   }
   if(InpUseHTFFilter && htfBias == 0)
   {
      g_lastSignalReason = "🚫 Choppy H1 Market - Standing By";
      return;
   }

   // --- BUY EXECUTION ---
   if(buySignal)
   {
      double entryPrice = m_symbol.Ask();
      double sl = entryPrice - safeBuffer;
      double riskPoints = entryPrice - sl;
      if(riskPoints <= 0) return;

      double tp = entryPrice + (riskPoints * InpRiskRewardRatio);

      if(m_trade.Buy(InpFixedLot, _Symbol, entryPrice, sl, tp, "v6 BUY [News+SMC+SQZ]"))
      {
         if(m_trade.ResultRetcode() == TRADE_RETCODE_DONE || m_trade.ResultRetcode() == TRADE_RETCODE_PLACED)
         {
            g_lastSignalReason = "🚀 BUY Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
         }
      }
      return;
   }

   // --- SELL EXECUTION ---
   if(sellSignal)
   {
      double entryPrice = m_symbol.Bid();
      double sl = entryPrice + safeBuffer;
      double riskPoints = sl - entryPrice;
      if(riskPoints <= 0) return;

      double tp = entryPrice - (riskPoints * InpRiskRewardRatio);

      if(m_trade.Sell(InpFixedLot, _Symbol, entryPrice, sl, tp, "v6 SELL [News+SMC+SQZ]"))
      {
         if(m_trade.ResultRetcode() == TRADE_RETCODE_DONE || m_trade.ResultRetcode() == TRADE_RETCODE_PLACED)
         {
            g_lastSignalReason = "🔻 SELL Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
         }
      }
      return;
   }

   g_lastSignalReason = "Hunting [News:" + (inNewsWindow?"BLOCKED":"CLEAR") + " | SQZ:" + (sqzOff?"OFF":"ON") + " | SMC:" + g_smcStateStr + "]";
}

//+------------------------------------------------------------------+
//| Position Management (Break-Even & Stepped Trailing)              |
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

      double initialRisk = (g_trackedTicket == m_position.Ticket() && g_initialRisk > 0) ? g_initialRisk : MathAbs(openPrice - currentSL);
      if(initialRisk <= 0) continue;

      if(m_position.PositionType() == POSITION_TYPE_BUY)
      {
         double profitPoints = currentPrice - openPrice;

         // 1. Break-Even
         if(profitPoints >= initialRisk * InpBreakEvenTriggerR && currentSL < openPrice)
         {
            double beBuffer = MathMax(minStopDist, m_symbol.Spread() * _Point * 2);
            double newSL = openPrice + beBuffer;
            if(currentPrice - newSL > minStopDist)
            {
               m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
               Print("🛡️ BUY SL moved to Break-Even+Buffer");
            }
         }

         // 2. Trailing Stop
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

         // 1. Break-Even
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

         // 2. Trailing Stop
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
//| Helpers & Cockpit HUD                                            |
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
   hud += "  ⚡ QUANTUM SNIPER v6.0 INSTITUTIONAL ⚡\n";
   hud += "===========================================\n";
   hud += " Account Mode   : " + accMode + " ($" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ")\n";
   hud += " News Calendar  : " + g_newsStatusStr + "\n";
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
   hud += " Active Trades  : " + (HasOpenPosition() ? "IN POSITION 🟢" : "HUNTING SETUP 🎯") + "\n";
   hud += "===========================================";
   Comment(hud);
}


