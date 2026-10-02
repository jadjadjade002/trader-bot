//+------------------------------------------------------------------+
//|                           QuantumTitan_v16_58_EvidenceLab.mq5    |
//|          v16.58 Evidence Lab                                    |
//|      Multi-Agent Autonomous Trading System: Top 1% Standard      |
//|      Trend-Locked SMC Sweeps, Anti-Revenge Cooldown,             |
//|      Volatility Shock Ceiling, Dynamic ATR Targets               |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumTitan Institutional Quant Framework v16.58 Evidence Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "16.58"
#property description "v16.58: causal entry/exit experiments with frozen per-position risk"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== 1. ACCOUNT SECURITY & EXECUTION ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpTargetAccount        = 0;          // Authorized Target Demo Account (0 = Any Demo)
input ulong    InpMagicNumber          = 991658;     // Dedicated Evidence Lab ID
input double   InpMaxSpreadPoints      = 45.0;       // Evidence-based tighter execution-cost ceiling

input group "=== 2. MQL5 NATIVE ECONOMIC NEWS INTELLIGENCE ==="
input bool     InpUseNewsFilter        = false;      // Enable MQL5 Calendar API News Filter (false = DISABLED)
input int      InpNewsBufferMinsBefore = 0;          // Pause entries N mins before High-Impact News
input int      InpNewsBufferMinsAfter  = 0;          // Resume entries N mins after High-Impact News

input group "=== 3. SMART MONEY CONCEPTS (TREND-LOCKED SMC) ==="
input bool     InpEnableLiquiditySweep = true;       // Detect Institutional Liquidity Sweep (Turtle Soup)
input int      InpSweepLookbackBars    = 30;         // Lookback bars for Swing High/Low Liquidity Pool
input bool     InpEnableFVG            = true;       // Detect Fair Value Gap (Imbalance Mitigation)
input double   InpWickRatioThreshold   = 0.30;       // Min Rejection Wick Ratio (30% Wick Required)
input bool     InpStrictTrendSweepLock = true;       // Lock SMC Sweeps strictly to M5 Trend Direction

input group "=== 4. MULTI-TIMEFRAME TREND & RETEST (M1 + M5) ==="
input int      InpFastEmaPeriod        = 14;         // M1 Fast EMA Period (Pullback Zone)
input int      InpSlowEmaPeriod        = 50;         // M1 Slow EMA Period (Intraday Baseline Trend)
input int      InpM5FastEmaPeriod      = 20;         // HTF M5 Fast EMA Period
input int      InpM5SlowEmaPeriod      = 50;         // HTF M5 Slow EMA Period
input double   InpMaxDistanceEmaPoints = 40.0;       // Max Distance to Fast EMA for Entry (Points)

input group "=== 5. LAZYBEAR SQUEEZE MOMENTUM ==="
input int      InpBBLength             = 20;         // Bollinger Bands Period
input double   InpBBMult               = 2.0;        // Bollinger Bands StdDev Multiplier
input int      InpKCLength             = 20;         // Keltner Channel Period
input double   InpKCMult               = 1.5;        // Keltner Channel ATR Multiplier

input group "=== 6. DYNAMIC VOLATILITY REGIME & ATR TARGETS ==="
input bool     InpUseDynamicAtr        = true;       // Adaptive ATR Volatility Scaling (vs Static Points)
input double   InpAtrSlMult            = 1.5;        // Stop Loss (ATR Multiplier)
input double   InpAtrTpMult            = 2.0;        // Preserve v16.55 TP behavior
input double   InpMaxStopLossPoints    = 150.0;      // Hard per-trade loss-distance ceiling (~$1.50 at 0.01 lot XAU)
input double   InpAtrBeTriggerMult     = 0.8;        // Preserve v16.55 first protection trigger
input double   InpAtrBeLockMult        = 0.2;        // Preserve v16.55 first protection lock
input double   InpMinBeTriggerPts      = 75.0;
input double   InpMaxBeTriggerPts      = 150.0;
input double   InpMinBeLockPts         = 20.0;
input double   InpMaxBeLockPts         = 50.0;
input bool     InpEnableStagedProfitLock = false;    // Experimental; baseline-equivalent exit by default
input double   InpStage2TriggerAtr     = 1.20;       // Strong move: advance lock materially
input double   InpStage2LockAtr        = 0.55;
input double   InpStage3TriggerAtr     = 1.65;       // Exceptional move: protect roughly 1R
input double   InpStage3LockAtr        = 1.00;
input double   InpMinAtrPoints         = 50.0;       // Dead Market Filter (Min ATR Points: $0.50)
input double   InpMaxAllowedAtrPoints  = 650.0;      // Extreme Volatility Shock Ceiling (Max ATR Points: $6.50)
input double   InpTakeProfitPoints     = 220.0;      // Preserve v16.55 fallback TP
input double   InpStopLossPoints       = 180.0;      // Fallback Static Stop Loss (Points: -$1.80)
input double   InpBreakevenTriggerPts  = 75.0;
input double   InpBreakevenLockPts     = 20.0;
input int      InpCooldownBars         = 5;          // Full M1 bars to wait after position closes
input int      InpLossStreakPauseMins  = 60;         // Anti-Revenge Pause after 2 consecutive losses

input group "=== 6B. CAUSAL EXIT POLICY ==="
input int      InpExitPolicy           = 1;          // 0=legacy, 1=1R delayed lock, 2=1R peak trail, 3=no lock
input double   InpDelayedLockTriggerR  = 1.00;       // Arm only after one full initial-risk unit
input double   InpDelayedLockR         = 0.10;       // Preserve 0.10R after trigger
input double   InpPeakTrailTriggerR    = 1.00;       // Start peak trail after this MFE
input double   InpPeakTrailDistanceR   = 0.75;       // Trail distance behind best price

input group "=== 6C. CAUSAL ENTRY POLICY ==="
input int      InpPullbackEvidenceMode = 1;          // 0=OR, 1=wick, 2=AND, 3=reclaim+KER, 4=breakout retest
input double   InpMinSignalBodyRatio   = 0.20;       // Reject doji/weak signal candles
input double   InpMinM5EmaSepPoints    = 20.0;       // Reject flat M5 trend
input bool     InpRequireMomentumAccel = false;      // Optional slope acceleration confirmation
input double   InpMinEfficiencyRatio   = 0.25;       // Directional efficiency floor for mode 3
input int      InpBreakoutLookback     = 12;         // Prior completed bars defining breakout level
input int      InpBreakoutRetestBars   = 5;          // Maximum M1 bars allowed for retest

input group "=== 7. RISK GUARDIAN & CIRCUIT BREAKERS ==="
input bool     InpEnableRiskGuardian   = true;       // Mandatory daily equity circuit breaker
input double   InpMaxDailyDrawdownPct  = 5.0;        // Daily Drawdown Auto-Halt Circuit Breaker (%)
input double   InpMaxDailyLossCash     = 3.0;        // Persistent realized-loss halt across EA restarts
input int      InpMaxTradesPerDay      = 4;          // Prevent M1 overtrading
input int      InpMaxLosingTradesDay   = 2;          // Stop for broker day after two losing exits
input bool     InpRequireFvgAndWick    = true;       // Retest requires both imbalance and rejection evidence
input bool     InpFridayLockout        = false;      // Block New Entries after Friday Cutoff (false = DISABLED)
input int      InpFridayCutoffHour     = 20;         // Friday Entry Cutoff Hour (Server Time)
input bool     InpDailyRolloverLock    = true;       // Flatten before metals break and block gap exposure
input int      InpRolloverFlatHour     = 22;
input int      InpRolloverFlatMinute   = 30;
input int      InpRolloverResumeHour   = 1;
input int      InpRolloverResumeMinute = 15;

input group "=== 8. VISUAL MATRIX HUD ==="
input bool     InpEnableHUD            = true;       // Render Real-Time On-Chart HUD

//+------------------------------------------------------------------+
//| GLOBAL INSTANCES & HANDLES                                       |
//+------------------------------------------------------------------+
CTrade         g_trade;
CPositionInfo  g_position;
CSymbolInfo    g_symbolInfo;

int            g_handleEmaFast   = INVALID_HANDLE;
int            g_handleEmaSlow   = INVALID_HANDLE;
int            g_handleM5EmaFast = INVALID_HANDLE;
int            g_handleM5EmaSlow = INVALID_HANDLE;
int            g_handleBands     = INVALID_HANDLE;
int            g_handleAtrKC     = INVALID_HANDLE;
int            g_handleRsi       = INVALID_HANDLE;

datetime       g_lastBarTime     = 0;
ulong          g_velocityMagic   = 0;
datetime       g_lastExitTime    = 0;
bool           g_hadActivePosition = false;
double         g_dayInitialEquity = 0.0;
int            g_lastCheckedDay   = -1;

int            g_consecutiveLosses = 0;
datetime       g_lastLossStreakTime = 0;
ulong          g_managedTicket      = 0;
double         g_entryRiskPts       = 0.0;
double         g_peakFavorablePrice = 0.0;
int            g_breakoutDirection  = 0;
double         g_breakoutLevel      = 0.0;
datetime       g_breakoutArmedAt    = 0;

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
   if(CopyBuffer(g_handleBands, BASE_LINE, 1, 2, bbMiddle) < 2 ||
      CopyBuffer(g_handleBands, UPPER_BAND, 1, 2, bbUpper) < 2 ||
      CopyBuffer(g_handleBands, LOWER_BAND, 1, 2, bbLower) < 2)
      return false;

   double atrKC[2];
   if(CopyBuffer(g_handleAtrKC, 0, 1, 2, atrKC) < 2) return false;

   double kcUpper = bbMiddle[1] + (InpKCMult * atrKC[1]);
   double kcLower = bbMiddle[1] - (InpKCMult * atrKC[1]);

   state.isSqueezeOn = (bbUpper[1] < kcUpper && bbLower[1] > kcLower);
   
   double prevKcUpper = bbMiddle[0] + (InpKCMult * atrKC[0]);
   double prevKcLower = bbMiddle[0] - (InpKCMult * atrKC[0]);
   bool prevSqueezeOn = (bbUpper[0] < prevKcUpper && bbLower[0] > prevKcLower);
   state.isBreakout  = (prevSqueezeOn && !state.isSqueezeOn);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 21, rates) < 21)
      return false;

   // Two comparable regression slopes built only from completed bars.
   // The old implementation compared a slope with a raw price deviation and
   // included the still-forming bar. That made the momentum gate inconsistent.
   double currentClose[20];
   double previousClose[20];
   for(int k = 0; k < 20; k++)
   {
      currentClose[k]  = rates[k].close;
      previousClose[k] = rates[k + 1].close;
   }

   state.momentum     = LinRegSlope(currentClose, 20);
   state.prevMomentum = LinRegSlope(previousClose, 20);

   state.isMomentumBullish = (state.momentum > 0 && state.momentum >= state.prevMomentum);
   state.isMomentumBearish = (state.momentum < 0 && state.momentum <= state.prevMomentum);

   return true;
}

//+------------------------------------------------------------------+
//| Check Native MQL5 Economic Calendar for High-Impact USD News     |
//+------------------------------------------------------------------+
bool IsInHighImpactNews(string &outEventName)
{
   if(!InpUseNewsFilter) return false;

   datetime serverTime = TimeTradeServer();
   if(serverTime <= 0) serverTime = TimeCurrent();

   static datetime lastNewsCheckTime = 0;
   static bool     cachedNewsResult  = false;
   static string   cachedNewsEvent   = "";

   if(serverTime - lastNewsCheckTime < 30 && lastNewsCheckTime > 0)
   {
      outEventName = cachedNewsEvent;
      return cachedNewsResult;
   }

   datetime timeFrom = serverTime - (InpNewsBufferMinsAfter * 60);
   datetime timeTo   = serverTime + (InpNewsBufferMinsBefore * 60);

   MqlCalendarValue values[];
   int count = CalendarValueHistory(values, timeFrom, timeTo, NULL, "USD");
   if(count > 0)
   {
      for(int i = 0; i < count; i++)
      {
         MqlCalendarEvent event;
         if(CalendarEventById(values[i].event_id, event))
         {
            if(event.importance == CALENDAR_IMPORTANCE_HIGH)
            {
               outEventName = StringFormat("[USD] %s", event.name);
               lastNewsCheckTime = serverTime;
               cachedNewsResult  = true;
               cachedNewsEvent   = outEventName;
               return true;
            }
         }
      }
   }

   lastNewsCheckTime = serverTime;
   cachedNewsResult  = false;
   cachedNewsEvent   = "";
   return false;
}

//+------------------------------------------------------------------+
//| Detect Institutional Liquidity Sweep (Turtle Soup Pattern)       |
//+------------------------------------------------------------------+
bool DetectLiquiditySweep(const MqlRates &rates[], int totalBars, bool &outIsSweepBuy, bool &outIsSweepSell)
{
   outIsSweepBuy  = false;
   outIsSweepSell = false;
   if(!InpEnableLiquiditySweep || totalBars < InpSweepLookbackBars + 2) return false;

   double swingHigh = -1.0;
   double swingLow  = 9999999.0;
   for(int i = 1; i <= InpSweepLookbackBars; i++)
   {
      if(rates[i].high > swingHigh) swingHigh = rates[i].high;
      if(rates[i].low < swingLow)   swingLow  = rates[i].low;
   }

   double bar1Range = rates[0].high - rates[0].low;
   if(bar1Range <= 0) return false;

   double lowerWick = MathMin(rates[0].open, rates[0].close) - rates[0].low;
   double upperWick = rates[0].high - MathMax(rates[0].open, rates[0].close);

   // Bullish Liquidity Sweep: Price swept below swing low, rejected and closed back above
   if(rates[0].low < swingLow && rates[0].close > swingLow && (lowerWick / bar1Range) >= InpWickRatioThreshold)
   {
      outIsSweepBuy = true;
      return true;
   }

   // Bearish Liquidity Sweep: Price swept above swing high, rejected and closed back below
   if(rates[0].high > swingHigh && rates[0].close < swingHigh && (upperWick / bar1Range) >= InpWickRatioThreshold)
   {
      outIsSweepSell = true;
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Detect Fair Value Gap (Imbalance Confluence)                     |
//+------------------------------------------------------------------+
bool DetectFVG(const MqlRates &rates[], int totalBars, bool &outBullishFvg, bool &outBearishFvg)
{
   outBullishFvg = false;
   outBearishFvg = false;
   if(!InpEnableFVG || totalBars < 4) return false;

   // Bullish FVG: Bar 1 Low > Bar 3 High
   if(rates[0].low > rates[2].high)
   {
      outBullishFvg = true;
   }

   // Bearish FVG: Bar 1 High < Bar 3 Low
   if(rates[0].high < rates[2].low)
   {
      outBearishFvg = true;
   }

   return (outBullishFvg || outBearishFvg);
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
//| Manage Active Position (Delayed Dynamic Profit Lock)             |
//+------------------------------------------------------------------+
void ManagePosition(long posType, double openPrice, double currentSl, ulong ticket,
                    double beTriggerPts, double beLockPts,
                    double stage2TriggerPts, double stage2LockPts,
                    double stage3TriggerPts, double stage3LockPts)
{
   double point  = g_symbolInfo.Point();
   double bid    = g_symbolInfo.Bid();
   double ask    = g_symbolInfo.Ask();
   int    digits = g_symbolInfo.Digits();

   if(point <= 0) return;
   if(ticket == 0 || !PositionSelectByTicket(ticket)) return;

   if(g_managedTicket != ticket)
   {
      g_managedTicket = ticket;
      g_entryRiskPts = MathAbs(openPrice - currentSl) / point;
      g_peakFavorablePrice = openPrice;
   }
   if(g_entryRiskPts <= 0.0) return;

   if(posType == POSITION_TYPE_BUY)
   {
      if(bid > g_peakFavorablePrice) g_peakFavorablePrice = bid;
      double profitPoints = (bid - openPrice) / point;
      double desiredLockPts = 0.0;
      int stage = 0;
      if(InpExitPolicy == 0)
      {
         if(InpEnableStagedProfitLock && profitPoints >= stage3TriggerPts) { desiredLockPts = stage3LockPts; stage = 3; }
         else if(InpEnableStagedProfitLock && profitPoints >= stage2TriggerPts) { desiredLockPts = stage2LockPts; stage = 2; }
         else if(profitPoints >= beTriggerPts) { desiredLockPts = beLockPts; stage = 1; }
      }
      else if(InpExitPolicy == 1 && profitPoints >= InpDelayedLockTriggerR * g_entryRiskPts)
      {
         desiredLockPts = InpDelayedLockR * g_entryRiskPts;
         stage = 1;
      }
      else if(InpExitPolicy == 2 && profitPoints >= InpPeakTrailTriggerR * g_entryRiskPts)
      {
         double peakLockPts = (g_peakFavorablePrice - openPrice) / point - InpPeakTrailDistanceR * g_entryRiskPts;
         desiredLockPts = MathMax(InpDelayedLockR * g_entryRiskPts, peakLockPts);
         stage = 2;
      }
      if(stage > 0)
      {
         double targetSl = NormalizeDouble(openPrice + (desiredLockPts * point), digits);
         if(currentSl < targetSl || currentSl == 0.0)
         {
            if(g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit()))
               PrintFormat("[M1 ProfitRunner] BUY STAGE %d LOCK: Profit %.1f pts -> SL %.5f (+%.1f pts)", stage, profitPoints, targetSl, desiredLockPts);
         }
      }
   }
   else if(posType == POSITION_TYPE_SELL)
   {
      if(g_peakFavorablePrice <= 0.0 || ask < g_peakFavorablePrice) g_peakFavorablePrice = ask;
      double profitPoints = (openPrice - ask) / point;
      double desiredLockPts = 0.0;
      int stage = 0;
      if(InpExitPolicy == 0)
      {
         if(InpEnableStagedProfitLock && profitPoints >= stage3TriggerPts) { desiredLockPts = stage3LockPts; stage = 3; }
         else if(InpEnableStagedProfitLock && profitPoints >= stage2TriggerPts) { desiredLockPts = stage2LockPts; stage = 2; }
         else if(profitPoints >= beTriggerPts) { desiredLockPts = beLockPts; stage = 1; }
      }
      else if(InpExitPolicy == 1 && profitPoints >= InpDelayedLockTriggerR * g_entryRiskPts)
      {
         desiredLockPts = InpDelayedLockR * g_entryRiskPts;
         stage = 1;
      }
      else if(InpExitPolicy == 2 && profitPoints >= InpPeakTrailTriggerR * g_entryRiskPts)
      {
         double peakLockPts = (openPrice - g_peakFavorablePrice) / point - InpPeakTrailDistanceR * g_entryRiskPts;
         desiredLockPts = MathMax(InpDelayedLockR * g_entryRiskPts, peakLockPts);
         stage = 2;
      }
      if(stage > 0)
      {
         double targetSl = NormalizeDouble(openPrice - (desiredLockPts * point), digits);
         if(currentSl > targetSl || currentSl == 0.0)
         {
            if(g_trade.PositionModify(ticket, targetSl, g_position.TakeProfit()))
               PrintFormat("[M1 ProfitRunner] SELL STAGE %d LOCK: Profit %.1f pts -> SL %.5f (+%.1f pts)", stage, profitPoints, targetSl, desiredLockPts);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Do not re-enter immediately after a trade close                  |
//+------------------------------------------------------------------+
bool IsPostExitCooldownActive()
{
   if(g_lastExitTime <= 0 || InpCooldownBars <= 0) return false;

   int barSeconds = PeriodSeconds(PERIOD_M1);
   if(barSeconds <= 0) barSeconds = 60;
   return (TimeCurrent() - g_lastExitTime) < (barSeconds * InpCooldownBars);
}

//+------------------------------------------------------------------+
//| Check Anti-Revenge Loss Streak Cooldown                          |
//+------------------------------------------------------------------+
bool IsLossStreakCooldownActive()
{
   if(g_consecutiveLosses < 2 || InpLossStreakPauseMins <= 0) return false;

   int cooldownSeconds = InpLossStreakPauseMins * 60;
   if(TimeCurrent() - g_lastLossStreakTime < cooldownSeconds)
   {
      return true;
   }
   else
   {
      g_consecutiveLosses = 0; // Cooldown expired, reset streak counter
      return false;
   }
}

//+------------------------------------------------------------------+
//| Compute True Starting Equity of Current Trading Day               |
//+------------------------------------------------------------------+
double ComputeDayStartingEquity()
{
   datetime todayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(todayStart <= 0) return AccountInfoDouble(ACCOUNT_EQUITY);

   if(!HistorySelect(todayStart, TimeCurrent()))
      return AccountInfoDouble(ACCOUNT_EQUITY);

   double todayRealized = 0.0;
   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            todayRealized += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            todayRealized += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            todayRealized += HistoryDealGetDouble(ticket, DEAL_SWAP);
         }
      }
   }
   double startEquity = AccountInfoDouble(ACCOUNT_BALANCE) - todayRealized;
   return MathMax(startEquity, 10.0);
}

//+------------------------------------------------------------------+
//| Rebuild account-wide XAU safety state from broker history.       |
//| This survives EA/terminal restarts and cannot be reset by reload.|
//+------------------------------------------------------------------+
bool GetTodaySafetyStats(int &entries, int &losingExits, double &realizedNet)
{
   entries = 0;
   losingExits = 0;
   realizedNet = 0.0;

   datetime todayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(todayStart <= 0 || !HistorySelect(todayStart, TimeCurrent())) return false;

   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      // Deliberately account-wide for this symbol.  A version or magic change
      // must never erase losses already realized earlier in the broker day.

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN) entries++;
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
      {
         double net = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                    + HistoryDealGetDouble(ticket, DEAL_COMMISSION)
                    + HistoryDealGetDouble(ticket, DEAL_SWAP)
                    + HistoryDealGetDouble(ticket, DEAL_FEE);
         realizedNet += net;
         if(net < -0.01) losingExits++;
      }
   }
   return true;
}

bool IsPersistentDailySafetyHalt()
{
   int entries = 0, losingExits = 0;
   double realizedNet = 0.0;
   if(!GetTodaySafetyStats(entries, losingExits, realizedNet))
   {
      Print("[V16.57 SAFETY] Cannot reconstruct today's broker history. Entries fail closed.");
      return true;
   }

   bool halt = false;
   if(InpMaxDailyLossCash > 0.0 && realizedNet <= -InpMaxDailyLossCash) halt = true;
   if(InpMaxTradesPerDay > 0 && entries >= InpMaxTradesPerDay) halt = true;
   if(InpMaxLosingTradesDay > 0 && losingExits >= InpMaxLosingTradesDay) halt = true;

   if(halt)
   {
      static datetime lastPrint = 0;
      if(TimeCurrent() - lastPrint >= 300)
      {
         PrintFormat("[V16.57 DAILY HALT] entries=%d/%d | losses=%d/%d | realized=$%.2f | cash floor=-$%.2f",
                     entries, InpMaxTradesPerDay, losingExits, InpMaxLosingTradesDay,
                     realizedNet, InpMaxDailyLossCash);
         lastPrint = TimeCurrent();
      }
   }
   return halt;
}

//+------------------------------------------------------------------+
//| Check if Today's Drawdown Exceeds Circuit Breaker Floor          |
//+------------------------------------------------------------------+
bool IsDailyLossBreakerTripped()
{
   if(!InpEnableRiskGuardian || InpMaxDailyDrawdownPct <= 0.0) return false;

   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_lastCheckedDay || g_dayInitialEquity <= 0.0)
   {
      g_dayInitialEquity = ComputeDayStartingEquity();
      g_lastCheckedDay = dt.day;
   }

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_dayInitialEquity > 0.0)
   {
      double lossPct = ((g_dayInitialEquity - currentEquity) / g_dayInitialEquity) * 100.0;
      if(lossPct >= InpMaxDailyDrawdownPct)
      {
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Weekend Gap Filter (Friday Lockout)                              |
//+------------------------------------------------------------------+
bool IsFridayLockoutActive()
{
   if(!InpFridayLockout) return false;
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.day_of_week == 5 && dt.hour >= InpFridayCutoffHour);
}

//+------------------------------------------------------------------+
//| Daily metals rollover gap guard (broker server time)             |
//+------------------------------------------------------------------+
bool IsDailyRolloverLockout()
{
   if(!InpDailyRolloverLock) return false;
   MqlDateTime dt;
   TimeCurrent(dt);
   int nowMinutes = dt.hour * 60 + dt.min;
   int flatMinutes = InpRolloverFlatHour * 60 + InpRolloverFlatMinute;
   int resumeMinutes = InpRolloverResumeHour * 60 + InpRolloverResumeMinute;
   if(flatMinutes > resumeMinutes)
      return (nowMinutes >= flatMinutes || nowMinutes < resumeMinutes);
   return (nowMinutes >= flatMinutes && nowMinutes < resumeMinutes);
}

//+------------------------------------------------------------------+
//| Render On-Chart HUD                                              |
//+------------------------------------------------------------------+
void RenderHUD(const SqueezeState &sqz, double fastEma, double slowEma, double m5Fast, double m5Slow,
               string newsStatus, string smcStatus, double curAtrPts, double dynTp, double dynSl,
               int activeTrades, double pnl)
{
   if(!InpEnableHUD) return;

   string prefix = "QT1657_SAFETY_";
   string lines[8];

   string sqzText = sqz.isSqueezeOn ? "COMPRESSED [SQUEEZE ON]" : (sqz.isBreakout ? "BREAKOUT EXPLOSION" : "EXPANDING");
   color  sqzClr  = sqz.isSqueezeOn ? clrDarkOrange : (sqz.isBreakout ? clrCyan : clrGold);

   string momText = (sqz.momentum > 0) ? StringFormat("BULL (+%.4f)", sqz.momentum) : StringFormat("BEAR (%.4f)", sqz.momentum);
   color  momClr  = (sqz.momentum > 0) ? clrMediumSpringGreen : clrCrimson;

   string trendM1Text = (fastEma > slowEma) ? "M1 BULL" : "M1 BEAR";
   string trendM5Text = (m5Fast > m5Slow) ? "M5 BULL" : "M5 BEAR";
   bool   trendAligned = ((fastEma > slowEma) == (m5Fast > m5Slow));
   string trendText   = StringFormat("%s | %s [%s]", trendM1Text, trendM5Text, trendAligned ? "ALIGNED" : "CONFLICT");
   color  trendClr    = trendAligned ? ((fastEma > slowEma) ? clrMediumSpringGreen : clrCrimson) : clrDarkOrange;

   string pauseStatus = IsLossStreakCooldownActive() ? StringFormat("PAUSED (Anti-Revenge %d mins)", InpLossStreakPauseMins) : "ACTIVE";
   color  statusClr   = IsLossStreakCooldownActive() ? clrCrimson : clrCyan;

   lines[0] = StringFormat(">> QUANTUM TITAN v16.57 [SAFETY HOTFIX] - %s <<", pauseStatus);
   lines[1] = StringFormat("Account : DEMO ($%.2f) | Losses Streak: %d | News: %s", AccountInfoDouble(ACCOUNT_EQUITY), g_consecutiveLosses, newsStatus);
   lines[2] = StringFormat("Squeeze : %s | Mom: %s", sqzText, momText);
   lines[3] = StringFormat("Trend   : %s", trendText);
   lines[4] = StringFormat("SMC Footprint : %s (M5 Trend-Locked)", smcStatus);
   lines[5] = StringFormat("Regime  : ATR: %.1f pts | Dynamic Targets: TP +%.0f pts | SL -%.0f pts", curAtrPts, dynTp, dynSl);
   lines[6] = StringFormat("Active  : %d trade(s) | Floating: %+.2f USD", activeTrades, pnl);
   lines[7] = "Strategy: Trend-Locked Liquidity Sweeps + Anti-Revenge Choke + Dynamic ATR";

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
      color txtClr = (i == 0) ? statusClr : (i == 2 ? sqzClr : (i == 3 ? trendClr : (i == 4 ? clrGold : clrWhiteSmoke)));
      ObjectSetString(0, objName, OBJPROP_TEXT, lines[i]);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, txtClr);
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpAtrSlMult <= 0.0 || InpAtrTpMult <= 0.0 ||
      InpAtrBeTriggerMult <= 0.0 || InpAtrBeLockMult < 0.0 ||
      InpMinBeTriggerPts <= 0.0 || InpMaxBeTriggerPts < InpMinBeTriggerPts ||
      InpMinBeLockPts < 0.0 || InpMaxBeLockPts < InpMinBeLockPts ||
      InpMaxBeLockPts >= InpMinBeTriggerPts ||
      InpStage2TriggerAtr <= InpAtrBeTriggerMult || InpStage2LockAtr <= InpAtrBeLockMult ||
      InpStage3TriggerAtr <= InpStage2TriggerAtr || InpStage3LockAtr <= InpStage2LockAtr ||
      InpStage2LockAtr >= InpStage2TriggerAtr || InpStage3LockAtr >= InpStage3TriggerAtr ||
      InpRolloverFlatHour < 0 || InpRolloverFlatHour > 23 ||
      InpRolloverResumeHour < 0 || InpRolloverResumeHour > 23 ||
      InpRolloverFlatMinute < 0 || InpRolloverFlatMinute > 59 ||
      InpRolloverResumeMinute < 0 || InpRolloverResumeMinute > 59 ||
      InpBreakevenLockPts >= InpBreakevenTriggerPts ||
      InpMaxStopLossPoints <= 0.0 || InpMaxDailyLossCash <= 0.0 ||
      InpMaxTradesPerDay <= 0 || InpMaxLosingTradesDay <= 0)
   {
      Print("V16.57 invalid safety or exit-policy parameters.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(InpDemoOnly && (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL))
   {
      Alert("🚨 [SECURITY CRITICAL] QuantumTitan v16 is locked to DEMO mode!");
      return INIT_FAILED;
   }

   if(InpTargetAccount > 0)
   {
      ulong currentLogin = (ulong)AccountInfoInteger(ACCOUNT_LOGIN);
      if(currentLogin != InpTargetAccount)
      {
         Alert(StringFormat("CRITICAL SECURITY: Unauthorized account %I64u! Required: %I64u", currentLogin, InpTargetAccount));
         return INIT_FAILED;
      }
   }

   g_dayInitialEquity = ComputeDayStartingEquity();
   MqlDateTime dtInit;
   TimeCurrent(dtInit);
   g_lastCheckedDay = dtInit.day;

   if(!g_symbolInfo.Name(_Symbol)) return INIT_FAILED;
   g_symbolInfo.Refresh();

   g_velocityMagic = InpMagicNumber;
   if(g_velocityMagic == 991601)
   {
      g_velocityMagic = 991602;
      Print("[Velocity Safety] Legacy magic 991601 overridden to 991602 to isolate Apex M1 positions.");
   }

   g_trade.SetExpertMagicNumber(g_velocityMagic);
   g_trade.SetDeviationInPoints(20);

   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   // Indicators
   g_handleEmaFast   = iMA(_Symbol, PERIOD_M1, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleEmaSlow   = iMA(_Symbol, PERIOD_M1, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleM5EmaFast = iMA(_Symbol, PERIOD_M5, InpM5FastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleM5EmaSlow = iMA(_Symbol, PERIOD_M5, InpM5SlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleBands     = iBands(_Symbol, PERIOD_M1, InpBBLength, 0, InpBBMult, PRICE_CLOSE);
   g_handleAtrKC     = iATR(_Symbol, PERIOD_M1, InpKCLength);
   g_handleRsi       = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);

   if(g_handleEmaFast == INVALID_HANDLE || g_handleEmaSlow == INVALID_HANDLE ||
      g_handleM5EmaFast == INVALID_HANDLE || g_handleM5EmaSlow == INVALID_HANDLE ||
      g_handleBands == INVALID_HANDLE || g_handleAtrKC == INVALID_HANDLE || g_handleRsi == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles for v16.57 Safety Hotfix");
      return INIT_FAILED;
   }

   ChartIndicatorAdd(0, 0, g_handleEmaFast);
   ChartIndicatorAdd(0, 0, g_handleEmaSlow);
   ChartIndicatorAdd(0, 0, g_handleBands);

   PrintFormat("QuantumTitan v16.57 Safety Hotfix initialized on %s M1 (Magic: %I64u)", _Symbol, g_velocityMagic);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(g_handleEmaFast);
   IndicatorRelease(g_handleEmaSlow);
   IndicatorRelease(g_handleM5EmaFast);
   IndicatorRelease(g_handleM5EmaSlow);
   IndicatorRelease(g_handleBands);
   IndicatorRelease(g_handleAtrKC);
   IndicatorRelease(g_handleRsi);

   ObjectsDeleteAll(0, "QT1657_SAFETY_");
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

   // 1. Dynamic ATR Volatility Engine
   double atrKC[2];
   if(CopyBuffer(g_handleAtrKC, 0, 0, 2, atrKC) < 2) return;
   double currentAtrPts = (point > 0.0) ? atrKC[0] / point : 100.0;

   double dynamicSlPts        = InpStopLossPoints;
   double dynamicTpPts        = InpTakeProfitPoints;
   double dynamicBeTriggerPts = InpBreakevenTriggerPts;
   double dynamicBeLockPts    = InpBreakevenLockPts;
   double stage2TriggerPts     = 180.0;
   double stage2LockPts        = 80.0;
   double stage3TriggerPts     = 250.0;
   double stage3LockPts        = 150.0;

   if(InpUseDynamicAtr)
   {
      dynamicSlPts        = MathMax(100.0, MathMin(InpMaxStopLossPoints, InpAtrSlMult * currentAtrPts));
      dynamicTpPts        = MathMax(240.0, MathMin(600.0, InpAtrTpMult * currentAtrPts));
      dynamicBeTriggerPts = MathMax(InpMinBeTriggerPts, MathMin(InpMaxBeTriggerPts, InpAtrBeTriggerMult * currentAtrPts));
      dynamicBeLockPts    = MathMax(InpMinBeLockPts, MathMin(InpMaxBeLockPts, InpAtrBeLockMult * currentAtrPts));
      stage2TriggerPts     = MathMax(140.0, MathMin(300.0, InpStage2TriggerAtr * currentAtrPts));
      stage2LockPts        = MathMax(50.0,  MathMin(140.0, InpStage2LockAtr * currentAtrPts));
      stage3TriggerPts     = MathMax(220.0, MathMin(450.0, InpStage3TriggerAtr * currentAtrPts));
      stage3LockPts        = MathMax(100.0, MathMin(250.0, InpStage3LockAtr * currentAtrPts));
   }

   // 2. Position Management & Delayed Dynamic Profit Lock
   double openPrice = 0.0, currentSl = 0.0, currentPnl = 0.0;
   long posType = -1;
   ulong activeTicket = 0;
   int activeTrades = GetActivePositionCount(g_velocityMagic, openPrice, currentSl, currentPnl, posType, activeTicket);

   if(activeTrades > 0)
   {
      g_hadActivePosition = true;
      if(IsDailyRolloverLockout())
      {
         if(g_trade.PositionClose(activeTicket))
            PrintFormat("[ProfitRunner Rollover Guard] Position #%I64u closed before daily metals break.", activeTicket);
         return;
      }
      ManagePosition(posType, openPrice, currentSl, activeTicket,
                     dynamicBeTriggerPts, dynamicBeLockPts,
                     stage2TriggerPts, stage2LockPts,
                     stage3TriggerPts, stage3LockPts);
   }
   else if(g_hadActivePosition)
   {
      g_hadActivePosition = false;
      g_managedTicket = 0;
      g_entryRiskPts = 0.0;
      g_peakFavorablePrice = 0.0;
      g_lastExitTime = TimeCurrent();
      PrintFormat("[Velocity Safety] Position closed; entry cooldown started for %d M1 bar(s).", InpCooldownBars);
   }

   // 3. Indicator Telemetry (M1 + HTF M5)
   double fastEma[2], slowEma[2], rsiVal[2];
   if(CopyBuffer(g_handleEmaFast, 0, 0, 2, fastEma) < 2) return;
   if(CopyBuffer(g_handleEmaSlow, 0, 0, 2, slowEma) < 2) return;
   if(CopyBuffer(g_handleRsi, 0, 0, 2, rsiVal) < 2) return;

   double m5FastEma[2], m5SlowEma[2];
   if(CopyBuffer(g_handleM5EmaFast, 0, 0, 2, m5FastEma) < 2) return;
   if(CopyBuffer(g_handleM5EmaSlow, 0, 0, 2, m5SlowEma) < 2) return;

   SqueezeState sqz;
   if(!CalculateSqueezeMomentum(sqz)) return;

   // 4. MQL5 Economic Calendar News Filter
   string newsEvent = "";
   bool inNewsWindow = IsInHighImpactNews(newsEvent);
   string newsStatus = !InpUseNewsFilter ? "OFF (ชนข่าว)" : (inNewsWindow ? StringFormat("LOCKOUT (%s)", newsEvent) : "CLEAR (Trade Allowed)");

   // 5. SMC Scan for HUD
   string smcStatus = "Scanning...";
   int ratesNeeded = MathMax(35, InpSweepLookbackBars + 5);
   MqlRates ratesScan[];
   ArraySetAsSeries(ratesScan, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, ratesNeeded, ratesScan) >= ratesNeeded)
   {
      bool swBuy = false, swSell = false, fvgB = false, fvgS = false;
      DetectLiquiditySweep(ratesScan, ratesNeeded, swBuy, swSell);
      DetectFVG(ratesScan, ratesNeeded, fvgB, fvgS);
      string swText  = swBuy ? "SWEEP BUY" : (swSell ? "SWEEP SELL" : "None");
      string fvgText = fvgB ? "BULL FVG" : (fvgS ? "BEAR FVG" : "None");
      smcStatus = StringFormat("Sweep: %s | FVG: %s", swText, fvgText);
   }

   // 6. Render HUD
   RenderHUD(sqz, fastEma[0], slowEma[0], m5FastEma[0], m5SlowEma[0],
             newsStatus, smcStatus, currentAtrPts, dynamicTpPts, dynamicSlPts,
             activeTrades, currentPnl);

   // Draw dynamic EMA14 Retest Level Line
   string retestObj = "QT16_RETEST_LINE";
   if(fastEma[0] > 0)
   {
      if(ObjectFind(0, retestObj) < 0) ObjectCreate(0, retestObj, OBJ_HLINE, 0, 0, fastEma[0]);
      else ObjectMove(0, retestObj, 0, 0, fastEma[0]);
      ObjectSetInteger(0, retestObj, OBJPROP_COLOR, (fastEma[0] > slowEma[0]) ? clrGold : clrDeepPink);
      ObjectSetInteger(0, retestObj, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, retestObj, OBJPROP_WIDTH, 1);
      ObjectSetString(0, retestObj, OBJPROP_TOOLTIP, "EMA14 Retest Trigger Line");
   }

   // 7. Entry Checks
   if(IsDailyLossBreakerTripped()) return;
   if(IsPersistentDailySafetyHalt()) return;
   if(IsFridayLockoutActive()) return;
   if(IsDailyRolloverLockout()) return;
   if(activeTrades > 0) return;
   if(IsPostExitCooldownActive()) return;

   // Anti-Revenge Loss Streak Cooldown (Pause 15 mins after 2 consecutive losses)
   if(IsLossStreakCooldownActive())
   {
      static datetime lastStreakPrint = 0;
      if(TimeCurrent() - lastStreakPrint > 300)
      {
         PrintFormat("[Velocity Anti-Revenge] Loss streak cooldown active (%d mins). Waiting for market stabilization.", InpLossStreakPauseMins);
         lastStreakPrint = TimeCurrent();
      }
      return;
   }

   // News Shock Entry Lockout (if enabled)
   if(inNewsWindow) return;

   // Volatility Regime Dead Market Check
   if(currentAtrPts < InpMinAtrPoints) return;

   // Volatility Shock Ceiling Check (Avoid trading inside explosive $8-$12 news candles)
   if(currentAtrPts > InpMaxAllowedAtrPoints)
   {
      static datetime lastAtrPrint = 0;
      if(TimeCurrent() - lastAtrPrint > 300)
      {
         PrintFormat("[Velocity Volatility Guard] ATR %.1f pts exceeds ceiling %.1f pts! Entry paused.", currentAtrPts, InpMaxAllowedAtrPoints);
         lastAtrPrint = TimeCurrent();
      }
      return;
   }

   // Spread check
   double currentSpread = (point > 0.0) ? (ask - bid) / point : 0.0;
   if(currentSpread > InpMaxSpreadPoints) return;

   // Bar close discipline for entry signal evaluation
   datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBarTime <= 0 || currentBarTime == g_lastBarTime) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, ratesNeeded, rates) < ratesNeeded) return;

   MqlRates completedBar = rates[0]; // Bar 1 (just completed)
   double barRange = completedBar.high - completedBar.low;
   if(barRange <= 0) return;

   double lowerWick = MathMin(completedBar.open, completedBar.close) - completedBar.low;
   double upperWick = completedBar.high - MathMax(completedBar.open, completedBar.close);
   double lowerWickRatio = lowerWick / barRange;
   double upperWickRatio = upperWick / barRange;
   double bodyRatio = MathAbs(completedBar.close - completedBar.open) / barRange;
   double pathLength = 0.0;
   for(int er = 0; er < 20; er++)
      pathLength += MathAbs(rates[er].close - rates[er + 1].close);
   double efficiencyRatio = (pathLength > 0.0)
      ? MathAbs(rates[0].close - rates[20].close) / pathLength : 0.0;
   bool efficientBull = (efficiencyRatio >= InpMinEfficiencyRatio && rates[0].close > rates[20].close);
   bool efficientBear = (efficiencyRatio >= InpMinEfficiencyRatio && rates[0].close < rates[20].close);

   // SMC Footprint Detection
   bool isSweepBuy = false, isSweepSell = false;
   DetectLiquiditySweep(rates, ratesNeeded, isSweepBuy, isSweepSell);

   bool hasBullFvg = false, hasBearFvg = false;
   DetectFVG(rates, ratesNeeded, hasBullFvg, hasBearFvg);

   bool signalBuy  = false;
   bool signalSell = false;
   string entryReason = "";

   bool m5Bullish = (m5FastEma[0] > m5SlowEma[0]);
   bool m5Bearish = (m5FastEma[0] < m5SlowEma[0]);
   double m5SeparationPts = MathAbs(m5FastEma[0] - m5SlowEma[0]) / point;
   bool m5TrendStrongEnough = (m5SeparationPts >= InpMinM5EmaSepPoints);

   // BUY SETUP 1: Trend-Locked Smart Money Liquidity Sweep (Strict Trend Direction)
   // Only BUY sweeps if M5 is Bullish and M1 price is above slow EMA baseline!
   bool sweepBuyTrendOk = !InpStrictTrendSweepLock ||
      (m5Bullish && completedBar.close > slowEma[0] &&
       (InpPullbackEvidenceMode != 3 || (efficientBull && completedBar.close >= fastEma[0])));
   if(InpPullbackEvidenceMode != 4 && isSweepBuy && sweepBuyTrendOk && (rsiVal[0] >= 35.0 && rsiVal[0] <= 55.0))
   {
      signalBuy = true;
      entryReason = "SMC_SWEEP_BUY";
   }
   // BUY SETUP 2: Trend Retest + Value Zone + FVG / Wick Confluence
   else if(InpPullbackEvidenceMode != 4 && m5Bullish && m5TrendStrongEnough && fastEma[0] > slowEma[0] && completedBar.close > slowEma[0])
   {
      bool touchedFastEma  = (completedBar.low <= fastEma[0] + (15.0 * point));
      bool withinValueZone = (MathAbs(completedBar.close - fastEma[0]) <= (InpMaxDistanceEmaPoints * point));
      bool rejectionWick   = (lowerWickRatio >= InpWickRatioThreshold && completedBar.close >= (completedBar.open - 5.0 * point));
      bool momOk           = (sqz.momentum > 0.0 && (!InpRequireMomentumAccel || sqz.isMomentumBullish));
      bool rsiOk           = (rsiVal[0] >= 42.0 && rsiVal[0] <= 58.0);

      bool evidenceOk = (InpPullbackEvidenceMode == 2) ? (rejectionWick && hasBullFvg) :
                        (InpPullbackEvidenceMode == 1) ? rejectionWick : (rejectionWick || hasBullFvg);
      bool qualityOk = (InpPullbackEvidenceMode != 3) ||
         (efficientBull && completedBar.close >= fastEma[0]);
      if(touchedFastEma && withinValueZone && evidenceOk && momOk && rsiOk &&
         qualityOk && bodyRatio >= InpMinSignalBodyRatio && completedBar.close > completedBar.open)
      {
         signalBuy = true;
         entryReason = hasBullFvg ? "FVG_PULLBACK_BUY" : "WICK_PULLBACK_BUY";
      }
   }

   // SELL SETUP 1: Trend-Locked Smart Money Liquidity Sweep (Strict Trend Direction)
   // Only SELL sweeps if M5 is Bearish and M1 price is below slow EMA baseline!
   bool sweepSellTrendOk = !InpStrictTrendSweepLock ||
      (m5Bearish && completedBar.close < slowEma[0] &&
       (InpPullbackEvidenceMode != 3 || (efficientBear && completedBar.close <= fastEma[0])));
   if(InpPullbackEvidenceMode != 4 && isSweepSell && sweepSellTrendOk && (rsiVal[0] >= 45.0 && rsiVal[0] <= 65.0))
   {
      signalSell = true;
      entryReason = "SMC_SWEEP_SELL";
   }
   // SELL SETUP 2: Trend Retest + Value Zone + FVG / Wick Confluence
   else if(InpPullbackEvidenceMode != 4 && m5Bearish && m5TrendStrongEnough && fastEma[0] < slowEma[0] && completedBar.close < slowEma[0])
   {
      bool touchedFastEma  = (completedBar.high >= fastEma[0] - (15.0 * point));
      bool withinValueZone = (MathAbs(completedBar.close - fastEma[0]) <= (InpMaxDistanceEmaPoints * point));
      bool rejectionWick   = (upperWickRatio >= InpWickRatioThreshold && completedBar.close <= (completedBar.open + 5.0 * point));
      bool momOk           = (sqz.momentum < 0.0 && (!InpRequireMomentumAccel || sqz.isMomentumBearish));
      bool rsiOk           = (rsiVal[0] >= 42.0 && rsiVal[0] <= 58.0);

      bool evidenceOk = (InpPullbackEvidenceMode == 2) ? (rejectionWick && hasBearFvg) :
                        (InpPullbackEvidenceMode == 1) ? rejectionWick : (rejectionWick || hasBearFvg);
      bool qualityOk = (InpPullbackEvidenceMode != 3) ||
         (efficientBear && completedBar.close <= fastEma[0]);
      if(touchedFastEma && withinValueZone && evidenceOk && momOk && rsiOk &&
         qualityOk && bodyRatio >= InpMinSignalBodyRatio && completedBar.close < completedBar.open)
      {
         signalSell = true;
         entryReason = hasBearFvg ? "FVG_PULLBACK_SELL" : "WICK_PULLBACK_SELL";
      }
   }

   // Mode 4 separates impulse detection from entry. Arm on a completed-bar
   // breakout, then enter only after a later completed bar retests and reclaims
   // the level. This prevents buying/selling the first expansion spike.
   if(InpPullbackEvidenceMode == 4)
   {
      int ageSeconds = (g_breakoutArmedAt > 0) ? (int)(currentBarTime - g_breakoutArmedAt) : 0;
      if(g_breakoutDirection != 0 && ageSeconds > InpBreakoutRetestBars * 60)
      {
         g_breakoutDirection = 0;
         g_breakoutLevel = 0.0;
         g_breakoutArmedAt = 0;
      }

      if(g_breakoutDirection == 1)
      {
         bool retest = completedBar.low <= g_breakoutLevel + 15.0 * point &&
                       completedBar.low >= g_breakoutLevel - 50.0 * point;
         if(retest && completedBar.close > g_breakoutLevel && completedBar.close > completedBar.open &&
            bodyRatio >= InpMinSignalBodyRatio && sqz.momentum > 0.0 && m5Bullish)
         {
            signalBuy = true;
            entryReason = "BREAKOUT_RETEST_BUY";
            g_breakoutDirection = 0;
         }
      }
      else if(g_breakoutDirection == -1)
      {
         bool retest = completedBar.high >= g_breakoutLevel - 15.0 * point &&
                       completedBar.high <= g_breakoutLevel + 50.0 * point;
         if(retest && completedBar.close < g_breakoutLevel && completedBar.close < completedBar.open &&
            bodyRatio >= InpMinSignalBodyRatio && sqz.momentum < 0.0 && m5Bearish)
         {
            signalSell = true;
            entryReason = "BREAKOUT_RETEST_SELL";
            g_breakoutDirection = 0;
         }
      }

      if(!signalBuy && !signalSell && g_breakoutDirection == 0)
      {
         double priorHigh = rates[1].high;
         double priorLow = rates[1].low;
         int lookback = MathMin(InpBreakoutLookback, ArraySize(rates) - 1);
         for(int br = 2; br <= lookback; br++)
         {
            if(rates[br].high > priorHigh) priorHigh = rates[br].high;
            if(rates[br].low < priorLow) priorLow = rates[br].low;
         }
         if(m5Bullish && m5TrendStrongEnough && completedBar.close > priorHigh &&
            completedBar.close > completedBar.open && bodyRatio >= 0.30 && sqz.momentum > 0.0)
         {
            g_breakoutDirection = 1;
            g_breakoutLevel = priorHigh;
            g_breakoutArmedAt = currentBarTime;
         }
         else if(m5Bearish && m5TrendStrongEnough && completedBar.close < priorLow &&
                 completedBar.close < completedBar.open && bodyRatio >= 0.30 && sqz.momentum < 0.0)
         {
            g_breakoutDirection = -1;
            g_breakoutLevel = priorLow;
            g_breakoutArmedAt = currentBarTime;
         }
      }
   }

   // Execute Scalp Order (Strict 0.01 Lot Guaranteed)
   const double strictLot = 0.01;
   if(signalBuy)
   {
      double sl = NormalizeDouble(ask - (dynamicSlPts * point), digits);
      double tp = NormalizeDouble(ask + (dynamicTpPts * point), digits);

      if(g_trade.Buy(strictLot, _Symbol, ask, sl, tp, entryReason))
      {
         g_hadActivePosition = true;
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [M1 Velocity] BUY (%s) @ %.5f | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts) | ATR: %.1f pts | Lot: %.2f",
            entryReason, ask, sl, dynamicSlPts, tp, dynamicTpPts, currentAtrPts, strictLot);
      }
   }
   else if(signalSell)
   {
      double sl = NormalizeDouble(bid + (dynamicSlPts * point), digits);
      double tp = NormalizeDouble(bid - (dynamicTpPts * point), digits);

      if(g_trade.Sell(strictLot, _Symbol, bid, sl, tp, entryReason))
      {
         g_hadActivePosition = true;
         g_lastBarTime = currentBarTime;
         PrintFormat("⚡ [M1 Velocity] SELL (%s) @ %.5f | SL: %.5f (-%.0f pts) | TP: %.5f (+%.0f pts) | ATR: %.1f pts | Lot: %.2f",
            entryReason, bid, sl, dynamicSlPts, tp, dynamicTpPts, currentAtrPts, strictLot);
      }
   }

   g_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//| Deal Tracker & Anti-Revenge Loss Streak Manager                  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != g_velocityMagic) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
   {
      g_lastExitTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      g_hadActivePosition = false;

      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      double swap   = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
      double comm   = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
      double netPnl = profit + swap + comm;

      if(netPnl < -0.01)
      {
         g_consecutiveLosses++;
         PrintFormat("[Velocity Safety] Deal #%I64u closed with LOSS ($%.2f). Streak: %d", trans.deal, netPnl, g_consecutiveLosses);
         if(g_consecutiveLosses >= 2)
         {
            g_lastLossStreakTime = g_lastExitTime;
            PrintFormat("🚨 [Velocity Anti-Revenge] 2 Consecutive Losses! Pausing new entries for %d minutes.", InpLossStreakPauseMins);
         }
      }
      else
      {
         g_consecutiveLosses = 0;
         PrintFormat("✅ [Velocity Safety] Deal #%I64u closed with WIN ($%.2f). Loss streak reset.", trans.deal, netPnl);
      }
   }
}
//+------------------------------------------------------------------+
