//+------------------------------------------------------------------+
//|                              QuantumTitan_v22_1_Precision.mq5     |
//|        v22.10 Precision Multi-Timeframe Swing Titan              |
//|      Multi-Agent Autonomous Trading System: Top 1% Standard      |
//|      Supported Timeframes: M5, M15, M30, H1, H4, D1              |
//|      High-Conviction Triple-Screen Gating (Score >= 80/100)      |
//|      ATR Dynamic Swing Stops (1:2 - 1:3 R:R) & Chandelier Trail  |
//|      Dedicated 0.02 Lot Execution & Isolated Magic Routing       |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumTitan Institutional Quant Framework v22.10 Precision"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "22.10"
#property description "v22.10 Precision: strict pullback/rejection, directional DI, account-wide XAU mutex and cash risk caps"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//+------------------------------------------------------------------+
//| ENUMS & DEFINITIONS                                              |
//+------------------------------------------------------------------+
enum ENUM_SWING_SETUP_TYPE
{
   SETUP_NONE = 0,
   SETUP_TREND_PULLBACK = 1,
   SETUP_STRUCTURE_BREAK = 2,
   SETUP_LIQUIDITY_REVERSAL = 3
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== 1. ACCOUNT SECURITY & POSITION SIZING ==="
input bool     InpDemoOnly             = true;          // Lock EA to DEMO Accounts Only
input ulong    InpTargetAccount        = 112468807;     // Authorized Target Demo Account (0 = Any Demo)
input ulong    InpBaseMagicNumber      = 992200;        // Base Magic Number (Auto-offsets by timeframe)
input double   InpBaseLotSize          = 0.01;          // Base Lot Size (Initial 0.01 Lots)
input double   InpScaledLotSize        = 0.02;          // Scaled Lot Size (0.02 Lots when Equity >= Threshold)
input double   InpEquityScaleThreshold = 120.0;         // Equity Threshold ($) to scale lot to 0.02
input bool     InpLogOrdersToCsv       = true;          // Record all orders & spreads to CSV
input double   InpMaxSpreadPoints      = 52.0;          // Max Allowed Spread (Points: V21 95th Percentile)
input ulong    InpMaxSlippagePoints    = 25;            // Max Allowed Slippage / Deviation (Points)

input group "=== 2. MULTI-TIMEFRAME CONFLUENCE & GATING ==="
input int      InpMinConfidenceScore   = 80;            // Min Conviction Score to Enter (0-100)
input int      InpMacroFastEma         = 50;            // Macro Trend Fast EMA (HTF)
input int      InpMacroSlowEma         = 200;           // Macro Trend Slow EMA (HTF)
input int      InpStructureFastEma     = 20;            // Structure Pullback Fast EMA
input int      InpStructureSlowEma     = 50;            // Structure Pullback Slow EMA
input int      InpRsiPeriod            = 14;            // RSI Period
input int      InpAdxPeriod            = 14;            // ADX Trend Strength Period
input double   InpMinAdxStrength       = 20.0;          // Minimum ADX Threshold for Trending State
input double   InpWickRatioThreshold   = 0.35;          // Min Rejection Wick Ratio (Calibrated from V21 Forward Data)
input double   InpMaxChaseAtr           = 0.35;          // Max close distance beyond structure value zone

input group "=== 3. SWING TARGETS & RISK MANAGEMENT ==="
input int      InpAtrPeriod            = 14;            // ATR Period for Volatility Measurement
input double   InpAtrStopMultiplier    = 1.8;           // Stop Loss Distance (ATR Multiplier)
input double   InpRewardRiskRatio      = 2.2;           // Take Profit Target (R:R Ratio, e.g. 2.2R)
input bool     InpEnableBreakeven      = true;          // Enable Automatic Breakeven Protection
input double   InpBreakevenTriggerR    = 1.0;           // Breakeven Activation at +1.0R Profit
input double   InpBreakevenLockPoints  = 25.0;          // Profit Points Locked at Breakeven
input bool     InpEnableChandelier     = true;          // Enable ATR Chandelier Trailing Stop
input double   InpChandelierTriggerR   = 1.5;           // Activate Trailing Stop at +1.5R Profit
input double   InpChandelierAtrMult    = 1.5;           // Trailing Distance (ATR Multiplier)
input int      InpCooldownBars         = 2;             // Cooldown Bars after Position Exit
input double   InpMaxStopPoints        = 350.0;          // Reject volatility shock stops
input double   InpMaxRiskMoney         = 1.50;           // Hard cash loss ceiling at requested lot

input group "=== 4. RISK GUARDIAN CIRCUIT BREAKERS ==="
input bool     InpEnableRiskGuardian   = true;          // Account-wide daily equity circuit breaker
input double   InpMaxDailyDrawdownPct  = 5.0;           // Daily Drawdown Auto-Halt Circuit Breaker (%)
input double   InpMaxDailyLossMoney    = 3.50;           // Shared account daily cash-loss ceiling
input bool     InpAccountWideXauMutex  = true;           // Never add XAU exposure across TF/magic
input bool     InpFridayLockout        = false;         // Block New Entries after Friday 20:00 (Gap Guard)
input int      InpFridayCutoffHour     = 20;            // Friday Entry Cutoff Hour (Server Time)

input group "=== 5. VISUAL HUD ==="
input bool     InpEnableHUD            = true;          // Render Real-Time On-Chart Swing HUD

//+------------------------------------------------------------------+
//| GLOBAL STATE & OBJECTS                                           |
//+------------------------------------------------------------------+
CTrade         g_trade;
CPositionInfo  g_position;
CSymbolInfo    g_symbolInfo;

ulong          g_activeMagic           = 0;
ENUM_TIMEFRAMES g_structureTF          = PERIOD_CURRENT;
ENUM_TIMEFRAMES g_macroTF              = PERIOD_CURRENT;

// Indicator Handles
int            g_handleMacroFastEma    = INVALID_HANDLE;
int            g_handleMacroSlowEma    = INVALID_HANDLE;
int            g_handleStructFastEma   = INVALID_HANDLE;
int            g_handleStructSlowEma   = INVALID_HANDLE;
int            g_handleChartFastEma    = INVALID_HANDLE;
int            g_handleChartSlowEma    = INVALID_HANDLE;
int            g_handleRsi             = INVALID_HANDLE;
int            g_handleAdx             = INVALID_HANDLE;
int            g_handleAtr             = INVALID_HANDLE;

datetime       g_lastBarTime           = 0;
datetime       g_lastExitTime          = 0;
bool           g_hadActivePosition     = false;
double         g_dayInitialEquity      = 0.0;
int            g_lastCheckedDay        = -1;
int            g_cachedBuyScore        = 0;
int            g_cachedSellScore       = 0;
string         g_lastExecutedSetupKey  = "";
string         g_entryMutexKey         = "QT_V221_XAU_ENTRY_MUTEX";

//+------------------------------------------------------------------+
//| Resolve Multi-Timeframe Hierarchy Based on Chart TF              |
//+------------------------------------------------------------------+
void ResolveTimeframeHierarchy(ENUM_TIMEFRAMES currentTF,
                               ENUM_TIMEFRAMES &outStructureTF,
                               ENUM_TIMEFRAMES &outMacroTF)
{
   switch(currentTF)
   {
      case PERIOD_M5:
         outStructureTF = PERIOD_M30;
         outMacroTF     = PERIOD_H4;
         break;
      case PERIOD_M15:
         outStructureTF = PERIOD_H1;
         outMacroTF     = PERIOD_H4;
         break;
      case PERIOD_M30:
         outStructureTF = PERIOD_H1;
         outMacroTF     = PERIOD_D1;
         break;
      case PERIOD_H1:
         outStructureTF = PERIOD_H4;
         outMacroTF     = PERIOD_D1;
         break;
      case PERIOD_H4:
         outStructureTF = PERIOD_D1;
         outMacroTF     = PERIOD_W1;
         break;
      case PERIOD_D1:
         outStructureTF = PERIOD_W1;
         outMacroTF     = PERIOD_MN1;
         break;
      default:
         outStructureTF = PERIOD_H1;
         outMacroTF     = PERIOD_D1;
         break;
   }
}

//+------------------------------------------------------------------+
//| Resolve Execution Filling Mode Dynamically                       |
//+------------------------------------------------------------------+
void ResolveFillingMode()
{
   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);
}

//+------------------------------------------------------------------+
//| Initialize Indicators and Timeframe Handles                      |
//+------------------------------------------------------------------+
bool InitIndicators()
{
   // Macro Trend Handles
   g_handleMacroFastEma  = iMA(_Symbol, g_macroTF, InpMacroFastEma, 0, MODE_EMA, PRICE_CLOSE);
   g_handleMacroSlowEma  = iMA(_Symbol, g_macroTF, InpMacroSlowEma, 0, MODE_EMA, PRICE_CLOSE);

   // Structure Handles
   g_handleStructFastEma = iMA(_Symbol, g_structureTF, InpStructureFastEma, 0, MODE_EMA, PRICE_CLOSE);
   g_handleStructSlowEma = iMA(_Symbol, g_structureTF, InpStructureSlowEma, 0, MODE_EMA, PRICE_CLOSE);

   // Current Chart Handles
   g_handleChartFastEma  = iMA(_Symbol, _Period, InpStructureFastEma, 0, MODE_EMA, PRICE_CLOSE);
   g_handleChartSlowEma  = iMA(_Symbol, _Period, InpStructureSlowEma, 0, MODE_EMA, PRICE_CLOSE);
   g_handleRsi           = iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE);
   g_handleAdx           = iADX(_Symbol, _Period, InpAdxPeriod);
   g_handleAtr           = iATR(_Symbol, _Period, InpAtrPeriod);

   if(g_handleMacroFastEma == INVALID_HANDLE || g_handleMacroSlowEma == INVALID_HANDLE ||
      g_handleStructFastEma == INVALID_HANDLE || g_handleStructSlowEma == INVALID_HANDLE ||
      g_handleChartFastEma == INVALID_HANDLE || g_handleChartSlowEma == INVALID_HANDLE ||
      g_handleRsi == INVALID_HANDLE || g_handleAdx == INVALID_HANDLE || g_handleAtr == INVALID_HANDLE)
   {
      PrintFormat("[V22 Swing INIT ERROR] Failed to create one or more indicator handles!");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Release Indicator Handles                                        |
//+------------------------------------------------------------------+
void ReleaseIndicators()
{
   if(g_handleMacroFastEma  != INVALID_HANDLE) { IndicatorRelease(g_handleMacroFastEma);  g_handleMacroFastEma = INVALID_HANDLE; }
   if(g_handleMacroSlowEma  != INVALID_HANDLE) { IndicatorRelease(g_handleMacroSlowEma);  g_handleMacroSlowEma = INVALID_HANDLE; }
   if(g_handleStructFastEma != INVALID_HANDLE) { IndicatorRelease(g_handleStructFastEma); g_handleStructFastEma = INVALID_HANDLE; }
   if(g_handleStructSlowEma != INVALID_HANDLE) { IndicatorRelease(g_handleStructSlowEma); g_handleStructSlowEma = INVALID_HANDLE; }
   if(g_handleChartFastEma  != INVALID_HANDLE) { IndicatorRelease(g_handleChartFastEma);  g_handleChartFastEma = INVALID_HANDLE; }
   if(g_handleChartSlowEma  != INVALID_HANDLE) { IndicatorRelease(g_handleChartSlowEma);  g_handleChartSlowEma = INVALID_HANDLE; }
   if(g_handleRsi           != INVALID_HANDLE) { IndicatorRelease(g_handleRsi);           g_handleRsi = INVALID_HANDLE; }
   if(g_handleAdx           != INVALID_HANDLE) { IndicatorRelease(g_handleAdx);           g_handleAdx = INVALID_HANDLE; }
   if(g_handleAtr           != INVALID_HANDLE) { IndicatorRelease(g_handleAtr);           g_handleAtr = INVALID_HANDLE; }
}

//+------------------------------------------------------------------+
//| Compute Current Dynamic Lot Size Based on Account Equity         |
//+------------------------------------------------------------------+
double ComputeCurrentLotSize()
{
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity >= InpEquityScaleThreshold)
      return InpScaledLotSize;
   return InpBaseLotSize;
}

bool IsXauSymbol(string symbol)
{
   StringToUpper(symbol);
   return (StringFind(symbol, "XAUUSD") >= 0);
}

bool HasAccountWideXauExposure()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket) &&
         IsXauSymbol(PositionGetString(POSITION_SYMBOL)))
         return true;
   }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && IsXauSymbol(OrderGetString(ORDER_SYMBOL)))
         return true;
   }
   return false;
}

bool AcquireEntryMutex()
{
   if(!InpAccountWideXauMutex) return true;
   GlobalVariableTemp(g_entryMutexKey);
   double owner = (double)(ChartID() + 1);
   return GlobalVariableSetOnCondition(g_entryMutexKey, owner, 0.0);
}

void ReleaseEntryMutex()
{
   if(!InpAccountWideXauMutex) return;
   double owner = (double)(ChartID() + 1);
   if(GlobalVariableCheck(g_entryMutexKey) && GlobalVariableGet(g_entryMutexKey) == owner)
      GlobalVariableSet(g_entryMutexKey, 0.0);
}

bool IsRiskMoneyAllowed(ENUM_ORDER_TYPE orderType, double lot, double entryPrice, double slPrice,
                        double &outRiskMoney)
{
   double projected = 0.0;
   if(!OrderCalcProfit(orderType, _Symbol, lot, entryPrice, slPrice, projected))
      return false;
   outRiskMoney = MathAbs(projected);
   return (outRiskMoney > 0.0 && outRiskMoney <= InpMaxRiskMoney);
}

string BuildSetupKey(ENUM_ORDER_TYPE orderType)
{
   // Canonical H4 episode shared by M5/M15/H1 instances.
   datetime macroBar = iTime(_Symbol, PERIOD_H4, 1);
   return StringFormat("%s|%d|%I64d", _Symbol, (int)orderType, (long)macroBar);
}

string SetupGlobalKey(string setupKey)
{
   uint hash = 2166136261;
   for(int i = 0; i < StringLen(setupKey); i++)
      hash = (hash ^ (uint)StringGetCharacter(setupKey, i)) * 16777619;
   return StringFormat("QT_V221_SETUP_%u", hash);
}

bool WasSetupConsumed(string setupKey)
{
   return (setupKey == g_lastExecutedSetupKey || GlobalVariableCheck(SetupGlobalKey(setupKey)));
}

void MarkSetupConsumed(string setupKey)
{
   g_lastExecutedSetupKey = setupKey;
   GlobalVariableSet(SetupGlobalKey(setupKey), (double)TimeCurrent());
}

bool TradeRetcodeAccepted()
{
   uint rc = g_trade.ResultRetcode();
   return (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL ||
           rc == TRADE_RETCODE_PLACED);
}

//+------------------------------------------------------------------+
//| Log Order and Spread Telemetry to CSV File                       |
//+------------------------------------------------------------------+
void LogOrderJournal(ulong ticket,
                     string actionType,
                     double lot,
                     double price,
                     double sl,
                     double tp,
                     double spreadPoints,
                     double netPnl,
                     string comment)
{
   if(!InpLogOrdersToCsv) return;
   string filename = "v22_swing_orders.csv";
   for(int attempt = 0; attempt < 5; attempt++)
   {
      bool exists = FileIsExist(filename);
      int handle = FileOpen(filename, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
      if(handle != INVALID_HANDLE)
      {
         FileSeek(handle, 0, SEEK_END);
         if(!exists || FileSize(handle) == 0)
         {
            FileWriteString(handle, "Time,Ticket,Magic,Symbol,Timeframe,Action,Lot,Price,SL,TP,SpreadPoints,NetPnL,Equity,Comment\n");
         }
         string line = StringFormat("%s,%I64u,%I64u,%s,%s,%s,%.2f,%.2f,%.2f,%.2f,%.1f,%.2f,%.2f,%s\n",
                                    TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
                                    ticket,
                                    g_activeMagic,
                                    _Symbol,
                                    EnumToString(_Period),
                                    actionType,
                                    lot,
                                    price,
                                    sl,
                                    tp,
                                    spreadPoints,
                                    netPnl,
                                    AccountInfoDouble(ACCOUNT_EQUITY),
                                    comment);
         FileWriteString(handle, line);
         FileClose(handle);
         break;
      }
      Sleep(20);
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
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // 1. Account Security Gate
   if(InpDemoOnly && !MQLInfoInteger(MQL_TESTER))
   {
      long acctType = AccountInfoInteger(ACCOUNT_TRADE_MODE);
      if(acctType != ACCOUNT_TRADE_MODE_DEMO)
      {
         Alert("CRITICAL ERROR: QuantumTitan v22 Swing is locked to DEMO accounts only!");
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
   }

   // 2. Minimum Timeframe Filter (Enforce M5 and higher)
   if(_Period < PERIOD_M5)
   {
      Alert(StringFormat("CRITICAL ERROR: QuantumTitan v22 Swing is locked to M5 and higher! Current TF: %s", EnumToString(_Period)));
      PrintFormat("[V22 INIT REJECT] Timeframe %s is below minimum allowed M5!", EnumToString(_Period));
      return INIT_FAILED;
   }

   // 3. Compute Unique Magic Number per Timeframe
   g_activeMagic = InpBaseMagicNumber + (ulong)_Period;

   // 4. Initialize Symbol & Trade Instances
   if(!g_symbolInfo.Name(_Symbol))
   {
      PrintFormat("[V22 INIT ERROR] Symbol %s not found!", _Symbol);
      return INIT_FAILED;
   }
   g_symbolInfo.RefreshRates();

   g_trade.SetExpertMagicNumber(g_activeMagic);
   g_trade.SetDeviationInPoints(InpMaxSlippagePoints);
   ResolveFillingMode();

   // 4. Resolve Timeframe Hierarchy
   ResolveTimeframeHierarchy(_Period, g_structureTF, g_macroTF);

   // 5. Initialize Indicators
   if(!InitIndicators())
   {
      return INIT_FAILED;
   }

   // 6. Initialize Risk Tracking (Accurate Day Baseline)
   g_dayInitialEquity = ComputeDayStartingEquity();
   MqlDateTime dt;
   TimeCurrent(dt);
   g_lastCheckedDay = dt.day;

   // 7. Initialize Cached Conviction Scores for HUD
   double initSl = 0.0, initTp = 0.0;
   string initReason = "";
   g_cachedBuyScore  = EvaluateConviction(ORDER_TYPE_BUY, initSl, initTp, initReason);
   g_cachedSellScore = EvaluateConviction(ORDER_TYPE_SELL, initSl, initTp, initReason);

   PrintFormat("=== QuantumTitan v22 Swing Initialized on %s %s ===", _Symbol, EnumToString(_Period));
   PrintFormat("    Magic: %I64u | Base Lot: %.2f | Scaled Lot: %.2f (>= $%.1f) | Structure TF: %s | Macro TF: %s",
               g_activeMagic, InpBaseLotSize, InpScaledLotSize, InpEquityScaleThreshold, EnumToString(g_structureTF), EnumToString(g_macroTF));
   PrintFormat("    Score Gate: >= %d/100 | ATR Mult: %.2f | Target R:R: 1:%.2f",
               InpMinConfidenceScore, InpAtrStopMultiplier, InpRewardRiskRatio);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ReleaseIndicators();
   if(InpEnableHUD)
   {
      Comment("");
   }
   PrintFormat("=== QuantumTitan v22 Swing Deinitialized (Reason: %d) ===", reason);
}

//+------------------------------------------------------------------+
//| Check if Today's Drawdown Exceeds Circuit Breaker Floor          |
//+------------------------------------------------------------------+
bool IsDailyLossBreakerTripped()
{
   if(!InpEnableRiskGuardian) return false;

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
      double lossMoney = g_dayInitialEquity - currentEquity;
      if(InpMaxDailyLossMoney > 0.0 && lossMoney >= InpMaxDailyLossMoney)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Weekend Gap Filter (Friday Lockout)                              |
//+------------------------------------------------------------------+
bool IsFridayLockout()
{
   if(!InpFridayLockout) return false;
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day_of_week == 5 && dt.hour >= InpFridayCutoffHour)
   {
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Multi-Gate Conviction Evaluation                                 |
//+------------------------------------------------------------------+
int EvaluateConviction(ENUM_ORDER_TYPE orderType,
                       double &outSlPoints,
                       double &outTpPoints,
                       string &outReason)
{
   int score = 0;
   outReason = "";

   // Copy recent closed execution rates (rates[1] = newest completed bar, rates[0] = prior bar)
   MqlRates rates[2];
   if(CopyRates(_Symbol, _Period, 1, 2, rates) < 2)
   {
      outReason = "ERR_RATES_COPY";
      return 0;
   }

   // --- Gate 1: Macro Trend Alignment (30 pts) ---
   double macroFast[2], macroSlow[2], macroClose[2];
   if(CopyBuffer(g_handleMacroFastEma, 0, 1, 2, macroFast) < 2 ||
      CopyBuffer(g_handleMacroSlowEma, 0, 1, 2, macroSlow) < 2 ||
      CopyClose(_Symbol, g_macroTF, 1, 2, macroClose) < 2)
   {
      outReason = "ERR_MACRO_COPY";
      return 0;
   }

   bool macroBull = (macroFast[1] > macroSlow[1]) && (macroClose[1] > macroFast[1]);
   bool macroBear = (macroFast[1] < macroSlow[1]) && (macroClose[1] < macroFast[1]);

   if(orderType == ORDER_TYPE_BUY && macroBull)
   {
      score += 30;
      outReason += "[MacroBull+30]";
   }
   else if(orderType == ORDER_TYPE_SELL && macroBear)
   {
      score += 30;
      outReason += "[MacroBear+30]";
   }
   else
   {
      outReason = "REJECT_MACRO_MISALIGNMENT";
      return 0;
   }

   // --- Gate 2: Structure Value Zone Pullback (25 pts) ---
   double structFast[2], structSlow[2], structHigh[2], structLow[2], structClose[2];
   if(CopyBuffer(g_handleStructFastEma, 0, 1, 2, structFast) < 2 ||
      CopyBuffer(g_handleStructSlowEma, 0, 1, 2, structSlow) < 2 ||
      CopyHigh(_Symbol, g_structureTF, 1, 2, structHigh) < 2 ||
      CopyLow(_Symbol, g_structureTF, 1, 2, structLow) < 2 ||
      CopyClose(_Symbol, g_structureTF, 1, 2, structClose) < 2)
   {
      outReason = "ERR_STRUCT_COPY";
      return 0;
   }

   double zoneUpper = MathMax(structFast[1], structSlow[1]);
   double zoneLower = MathMin(structFast[1], structSlow[1]);

   if(orderType == ORDER_TYPE_BUY)
   {
      double lowerWick = MathMin(rates[1].open, rates[1].close) - rates[1].low;
      double barRange = MathMax(rates[1].high - rates[1].low, _Point);
      bool strictDip = structFast[1] > structSlow[1] &&
                       rates[1].low <= zoneUpper && rates[1].high >= zoneLower &&
                       rates[1].close > zoneUpper && rates[1].close > rates[1].open &&
                       (lowerWick / barRange) >= InpWickRatioThreshold;
      if(!strictDip) { outReason = "REJECT_STRICT_PULLBACK"; return 0; }
      score += 25;
      outReason += "[StrictValueZoneDip+25]";
   }
   else if(orderType == ORDER_TYPE_SELL)
   {
      double upperWick = rates[1].high - MathMax(rates[1].open, rates[1].close);
      double barRange = MathMax(rates[1].high - rates[1].low, _Point);
      bool strictRally = structFast[1] < structSlow[1] &&
                         rates[1].high >= zoneLower && rates[1].low <= zoneUpper &&
                         rates[1].close < zoneLower && rates[1].close < rates[1].open &&
                         (upperWick / barRange) >= InpWickRatioThreshold;
      if(!strictRally) { outReason = "REJECT_STRICT_PULLBACK"; return 0; }
      score += 25;
      outReason += "[StrictValueZoneRally+25]";
   }

   // --- Gate 3: Momentum Recovery & Trend Strength (25 pts) ---
   double rsiVal[3];
   double adxMain[2], adxPlusDI[2], adxMinusDI[2];

   if(CopyBuffer(g_handleRsi, 0, 1, 3, rsiVal) < 3 ||
      CopyBuffer(g_handleAdx, 0, 1, 2, adxMain) < 2 ||
      CopyBuffer(g_handleAdx, 1, 1, 2, adxPlusDI) < 2 ||
      CopyBuffer(g_handleAdx, 2, 1, 2, adxMinusDI) < 2)
   {
      outReason = "ERR_MOMENTUM_COPY";
      return 0;
   }

   // For static arrays copied with start_pos=1:
   // rsiVal[2] is Bar 1 (newest completed), rsiVal[1] is Bar 2, rsiVal[0] is Bar 3
   // adxMain[1] is Bar 1, adxMain[0] is Bar 2
   bool directionalAdx = adxMain[1] >= InpMinAdxStrength &&
      ((orderType == ORDER_TYPE_BUY && adxPlusDI[1] > adxMinusDI[1]) ||
       (orderType == ORDER_TYPE_SELL && adxMinusDI[1] > adxPlusDI[1]));
   if(!directionalAdx) { outReason = "REJECT_DIRECTIONAL_ADX"; return 0; }
   score += 10;
   outReason += "[DirectionalAdx+10]";
   if(adxMain[1] >= 28.0) { score += 5; outReason += "[AdxExpansion+5]"; }

   if(orderType == ORDER_TYPE_BUY)
   {
      // Bar 1 (rsiVal[2]) in pullback zone and curling up from Bar 2 (rsiVal[1])
      if(rsiVal[2] >= 38.0 && rsiVal[2] <= 58.0 && rsiVal[2] > rsiVal[1])
      {
         score += 10;
         outReason += "[RsiBullPivot+10]";
      }
      else if(rsiVal[2] > 58.0 && rsiVal[2] < 72.0 && adxPlusDI[1] > adxMinusDI[1])
      {
         score += 8;
         outReason += "[RsiBullPush+8]";
      }
   }
   else if(orderType == ORDER_TYPE_SELL)
   {
      // Bar 1 (rsiVal[2]) in pullback zone and curling down from Bar 2 (rsiVal[1])
      if(rsiVal[2] <= 62.0 && rsiVal[2] >= 42.0 && rsiVal[2] < rsiVal[1])
      {
         score += 10;
         outReason += "[RsiBearPivot+10]";
      }
      else if(rsiVal[2] < 42.0 && rsiVal[2] > 28.0 && adxMinusDI[1] > adxPlusDI[1])
      {
         score += 8;
         outReason += "[RsiBearPush+8]";
      }
   }

   // Institutional Peak Liquidity Window (Server Hours 08:00 - 21:00 derived from V21 volume analysis)
   MqlDateTime barTime;
   TimeToStruct(rates[1].time, barTime);
   if(barTime.hour >= 8 && barTime.hour <= 21)
   {
      score += 5;
      outReason += "[V21LiquiditySession+5]";
   }

   // Gate 4 is mandatory: strict pullback above already proved same-bar rejection.
   score += 20;
   outReason += "[MandatoryRejection+20]";

   // --- Calculate Dynamic ATR Stops ---
   double atrBuf[1];
   if(CopyBuffer(g_handleAtr, 0, 1, 1, atrBuf) < 1 || atrBuf[0] <= 0.0)
   {
      outReason = "ERR_ATR_COPY";
      return 0;
   }

   double atrPoints = atrBuf[0] / _Point;
   outSlPoints = MathMax(atrPoints * InpAtrStopMultiplier, 50.0);
   outTpPoints = outSlPoints * InpRewardRiskRatio;

   double chaseDistance = (orderType == ORDER_TYPE_BUY)
      ? MathMax(0.0, rates[1].close - zoneUpper)
      : MathMax(0.0, zoneLower - rates[1].close);
   if(chaseDistance > atrBuf[0] * InpMaxChaseAtr)
   {
      outReason = "REJECT_CHASE_DISTANCE";
      return 0;
   }

   long minStopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(outSlPoints < (double)minStopLevel) outSlPoints = (double)minStopLevel + 10.0;
   outTpPoints = outSlPoints * InpRewardRiskRatio;
   if(outTpPoints < (double)minStopLevel) outTpPoints = (double)minStopLevel + 20.0;

   return score;
}

//+------------------------------------------------------------------+
//| Manage Active Position (Breakeven & Chandelier Trailing)        |
//+------------------------------------------------------------------+
void ManageActivePositions()
{
   if(!g_position.SelectByMagic(_Symbol, g_activeMagic))
   {
      return;
   }

   ENUM_POSITION_TYPE posType = g_position.PositionType();
   double openPrice  = g_position.PriceOpen();
   double currentSL  = g_position.StopLoss();
   double currentTP  = g_position.TakeProfit();
   double currentPrice = (posType == POSITION_TYPE_BUY) ? g_symbolInfo.Bid() : g_symbolInfo.Ask();

   double atrBuf[1];
   if(CopyBuffer(g_handleAtr, 0, 0, 1, atrBuf) < 1 || atrBuf[0] <= 0.0) return;
   double atrDist = atrBuf[0] * InpChandelierAtrMult;

   if(posType == POSITION_TYPE_BUY)
   {
      double profitPoints = (currentPrice - openPrice) / _Point;
      double initialRiskPts = 0.0;
      if(currentTP > 0.0 && InpRewardRiskRatio > 0.0)
         initialRiskPts = (MathAbs(openPrice - currentTP) / _Point) / InpRewardRiskRatio;
      if(initialRiskPts <= 0.0)
      {
         if(currentSL > 0.0 && currentSL < openPrice) initialRiskPts = (openPrice - currentSL) / _Point;
         else initialRiskPts = atrBuf[0] * InpAtrStopMultiplier / _Point;
      }

      // 1. Breakeven Lock
      if(InpEnableBreakeven && profitPoints >= (initialRiskPts * InpBreakevenTriggerR))
      {
         double bePrice = NormalizeDouble(openPrice + (InpBreakevenLockPoints * _Point), _Digits);
         if(currentSL < bePrice)
         {
            g_trade.PositionModify(g_position.Ticket(), bePrice, currentTP);
            PrintFormat("[V22 SWING BE] BUY #%I64u Breakeven Locked at %.2f (+%.1f pts)",
                        g_position.Ticket(), bePrice, InpBreakevenLockPoints);
         }
      }

      // 2. Chandelier Trailing
      if(InpEnableChandelier && profitPoints >= (initialRiskPts * InpChandelierTriggerR))
      {
         double trailPrice = NormalizeDouble(currentPrice - atrDist, _Digits);
         double minTrailStep = MathMax(30.0 * _Point, atrBuf[0] * 0.15);
         if(trailPrice > (currentSL + minTrailStep) && trailPrice > (openPrice + (InpBreakevenLockPoints * _Point)))
         {
            g_trade.PositionModify(g_position.Ticket(), trailPrice, currentTP);
         }
      }
   }
   else if(posType == POSITION_TYPE_SELL)
   {
      double profitPoints = (openPrice - currentPrice) / _Point;
      double initialRiskPts = 0.0;
      if(currentTP > 0.0 && InpRewardRiskRatio > 0.0)
         initialRiskPts = (MathAbs(openPrice - currentTP) / _Point) / InpRewardRiskRatio;
      if(initialRiskPts <= 0.0)
      {
         if(currentSL > openPrice) initialRiskPts = (currentSL - openPrice) / _Point;
         else initialRiskPts = atrBuf[0] * InpAtrStopMultiplier / _Point;
      }

      // 1. Breakeven Lock
      if(InpEnableBreakeven && profitPoints >= (initialRiskPts * InpBreakevenTriggerR))
      {
         double bePrice = NormalizeDouble(openPrice - (InpBreakevenLockPoints * _Point), _Digits);
         if(currentSL > bePrice || currentSL == 0.0)
         {
            g_trade.PositionModify(g_position.Ticket(), bePrice, currentTP);
            PrintFormat("[V22 SWING BE] SELL #%I64u Breakeven Locked at %.2f (+%.1f pts)",
                        g_position.Ticket(), bePrice, InpBreakevenLockPoints);
         }
      }

      // 2. Chandelier Trailing
      if(InpEnableChandelier && profitPoints >= (initialRiskPts * InpChandelierTriggerR))
      {
         double trailPrice = NormalizeDouble(currentPrice + atrDist, _Digits);
         double minTrailStep = MathMax(30.0 * _Point, atrBuf[0] * 0.15);
         if(((currentSL - trailPrice) > minTrailStep || currentSL == 0.0) && trailPrice < (openPrice - (InpBreakevenLockPoints * _Point)))
         {
            g_trade.PositionModify(g_position.Ticket(), trailPrice, currentTP);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Render Real-Time On-Chart HUD                                    |
//+------------------------------------------------------------------+
void RenderHUD(int buyScore, int sellScore, double spread)
{
   if(!InpEnableHUD) return;

   bool isPosActive = g_position.SelectByMagic(_Symbol, g_activeMagic);
   string posStr = isPosActive ? StringFormat("ACTIVE %s #%I64u | Open: %.2f | SL: %.2f | TP: %.2f",
                                              (g_position.PositionType() == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                                              g_position.Ticket(), g_position.PriceOpen(),
                                              g_position.StopLoss(), g_position.TakeProfit())
                               : "FLAT (Waiting for Swing Signal)";

   double currentLot = ComputeCurrentLotSize();
   string hud = StringFormat(
      "====================================================\n"
      " QuantumTitan v22.00 Swing Titan | %s %s\n"
      " Magic: %I64u | Lot: %.2f (Base: %.2f | Scaled: %.2f @ >= $%.0f)\n"
      " Equity: $%.2f | Structure TF: %s | Macro TF: %s\n"
      "----------------------------------------------------\n"
      " Status: %s\n"
      " Live Spread: %.1f pts (Max: %.1f)\n"
      " BUY Conviction:  %d/100 (Threshold: %d)\n"
      " SELL Conviction: %d/100 (Threshold: %d)\n"
      " Circuit Breaker: %s | Friday Lockout: %s\n"
      "====================================================",
      _Symbol, EnumToString(_Period),
      g_activeMagic, currentLot, InpBaseLotSize, InpScaledLotSize, InpEquityScaleThreshold,
      AccountInfoDouble(ACCOUNT_EQUITY), EnumToString(g_structureTF), EnumToString(g_macroTF),
      posStr,
      spread, InpMaxSpreadPoints,
      buyScore, InpMinConfidenceScore,
      sellScore, InpMinConfidenceScore,
      (IsDailyLossBreakerTripped() ? "TRIPPED (HALT)" : "OK (NORMAL)"),
      (IsFridayLockout() ? "LOCKED" : "ACTIVE")
   );
   Comment(hud);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   g_symbolInfo.RefreshRates();

   // 1. Tick-Level Trailing Stop & Breakeven Management
   ManageActivePositions();

   // 2. Track Position Close for Cooldown Calculation
   bool hasPos = g_position.SelectByMagic(_Symbol, g_activeMagic);
   if(g_hadActivePosition && !hasPos)
   {
      g_lastExitTime = TimeCurrent();
   }
   g_hadActivePosition = hasPos;

   // 3. New Bar Check (Execute heavy scans only on Closed Candle)
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   bool isNewBar = (currentBarTime != g_lastBarTime);

   // 4. Spread Check
   double currentSpread = (g_symbolInfo.Ask() - g_symbolInfo.Bid()) / _Point;

   // 5. Render HUD with cached conviction scores (Zero CPU overhead on micro-ticks)
   RenderHUD(g_cachedBuyScore, g_cachedSellScore, currentSpread);

   if(!isNewBar) return;
   g_lastBarTime = currentBarTime;

   // 6. Compute Conviction Scores on Closed Bar
   double buySlPoints = 0.0, buyTpPoints = 0.0;
   string buyReason = "";
   int buyScore = EvaluateConviction(ORDER_TYPE_BUY, buySlPoints, buyTpPoints, buyReason);

   double sellSlPoints = 0.0, sellTpPoints = 0.0;
   string sellReason = "";
   int sellScore = EvaluateConviction(ORDER_TYPE_SELL, sellSlPoints, sellTpPoints, sellReason);

   g_cachedBuyScore  = buyScore;
   g_cachedSellScore = sellScore;
   RenderHUD(g_cachedBuyScore, g_cachedSellScore, currentSpread);

   // 7. Execution Safety Gates
   if(hasPos) return; // Only 1 active swing position per timeframe chart
   if(IsDailyLossBreakerTripped())
   {
      PrintFormat("[V22 SWING HALT] Daily loss circuit breaker tripped! No new trades allowed today.");
      return;
   }
   if(IsFridayLockout())
   {
      PrintFormat("[V22 SWING LOCK] Friday evening lockout active. No new trades ahead of weekend.");
      return;
   }
   if(currentSpread > InpMaxSpreadPoints)
   {
      PrintFormat("[V22 SPREAD FILTER] Spread %.1f exceeds max allowed %.1f. Entry blocked.",
                  currentSpread, InpMaxSpreadPoints);
      return;
   }
   if(InpAccountWideXauMutex && HasAccountWideXauExposure())
   {
      Print("[V22.1 MUTEX] Existing account-wide XAU exposure. Entry blocked.");
      return;
   }

   // 8. Cooldown Check
   if(g_lastExitTime > 0)
   {
      int elapsedBars = (int)((TimeCurrent() - g_lastExitTime) / PeriodSeconds(_Period));
      if(elapsedBars < InpCooldownBars)
      {
         PrintFormat("[V22 COOLDOWN] Exit cooling down: %d/%d bars elapsed.", elapsedBars, InpCooldownBars);
         return;
      }
   }

   // 9. Evaluate Trade Entry with Spread-Compensated SL/TP
   double entryLot = ComputeCurrentLotSize();
   if(buyScore >= InpMinConfidenceScore)
   {
      double ask = g_symbolInfo.Ask();
      double bid = g_symbolInfo.Bid();
      // BUY closes at Bid: Anchor SL and TP to Bid for true distance
      double sl = NormalizeDouble(bid - (buySlPoints * _Point), _Digits);
      double tp = NormalizeDouble(bid + (buyTpPoints * _Point), _Digits);
      if(buySlPoints > InpMaxStopPoints)
      {
         PrintFormat("[V22.1 STOP CAP] BUY stop %.1f > %.1f points. Entry blocked.", buySlPoints, InpMaxStopPoints);
         return;
      }
      string setupKey = BuildSetupKey(ORDER_TYPE_BUY);
      if(WasSetupConsumed(setupKey)) { Print("[V22.1 SETUP] BUY setup already consumed."); return; }
      if(!AcquireEntryMutex()) { Print("[V22.1 MUTEX] Entry lock busy."); return; }
      if(HasAccountWideXauExposure() || IsDailyLossBreakerTripped()) { ReleaseEntryMutex(); return; }
      double riskMoney = 0.0;
      if(!IsRiskMoneyAllowed(ORDER_TYPE_BUY, entryLot, ask, sl, riskMoney))
      {
         PrintFormat("[V22.1 RISK CAP] BUY projected loss $%.2f > $%.2f or calculation failed.", riskMoney, InpMaxRiskMoney);
         ReleaseEntryMutex();
         return;
      }

      PrintFormat("[V22 SWING BUY SIGNAL] Score: %d/100 | SL: %.2f (-%.1f pts) | TP: %.2f (+%.1f pts) | Reason: %s",
                  buyScore, sl, buySlPoints, tp, buyTpPoints, buyReason);

      bool sent = g_trade.Buy(entryLot, _Symbol, ask, sl, tp, "QuantumTitan_v22_1_Precision");
      if(sent && TradeRetcodeAccepted())
      {
         MarkSetupConsumed(setupKey);
         ulong orderTicket = g_trade.ResultOrder();
         PrintFormat("[V22 SWING EXECUTED] BUY %.2f %s @ %.2f Done. Order: %I64u | Spread: %.1f pts | Equity: $%.2f",
                     entryLot, _Symbol, ask, orderTicket, currentSpread, AccountInfoDouble(ACCOUNT_EQUITY));
         LogOrderJournal(orderTicket, "BUY_OPEN", entryLot, ask, sl, tp, currentSpread, 0.0, buyReason);
      }
      else
      {
         PrintFormat("[V22 EXECUTION FAILED] RetCode: %u | Msg: %s",
                     g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
      ReleaseEntryMutex();
   }
   else if(sellScore >= InpMinConfidenceScore)
   {
      double bid = g_symbolInfo.Bid();
      double ask = g_symbolInfo.Ask();
      // SELL closes at Ask: Anchor SL and TP to Ask for true distance
      double sl = NormalizeDouble(ask + (sellSlPoints * _Point), _Digits);
      double tp = NormalizeDouble(ask - (sellTpPoints * _Point), _Digits);
      if(sellSlPoints > InpMaxStopPoints)
      {
         PrintFormat("[V22.1 STOP CAP] SELL stop %.1f > %.1f points. Entry blocked.", sellSlPoints, InpMaxStopPoints);
         return;
      }
      string setupKey = BuildSetupKey(ORDER_TYPE_SELL);
      if(WasSetupConsumed(setupKey)) { Print("[V22.1 SETUP] SELL setup already consumed."); return; }
      if(!AcquireEntryMutex()) { Print("[V22.1 MUTEX] Entry lock busy."); return; }
      if(HasAccountWideXauExposure() || IsDailyLossBreakerTripped()) { ReleaseEntryMutex(); return; }
      double riskMoney = 0.0;
      if(!IsRiskMoneyAllowed(ORDER_TYPE_SELL, entryLot, bid, sl, riskMoney))
      {
         PrintFormat("[V22.1 RISK CAP] SELL projected loss $%.2f > $%.2f or calculation failed.", riskMoney, InpMaxRiskMoney);
         ReleaseEntryMutex();
         return;
      }

      PrintFormat("[V22 SWING SELL SIGNAL] Score: %d/100 | SL: %.2f (-%.1f pts) | TP: %.2f (+%.1f pts) | Reason: %s",
                  sellScore, sl, sellSlPoints, tp, sellTpPoints, sellReason);

      bool sent = g_trade.Sell(entryLot, _Symbol, bid, sl, tp, "QuantumTitan_v22_1_Precision");
      if(sent && TradeRetcodeAccepted())
      {
         MarkSetupConsumed(setupKey);
         ulong orderTicket = g_trade.ResultOrder();
         PrintFormat("[V22 SWING EXECUTED] SELL %.2f %s @ %.2f Done. Order: %I64u | Spread: %.1f pts | Equity: $%.2f",
                     entryLot, _Symbol, bid, orderTicket, currentSpread, AccountInfoDouble(ACCOUNT_EQUITY));
         LogOrderJournal(orderTicket, "SELL_OPEN", entryLot, bid, sl, tp, currentSpread, 0.0, sellReason);
      }
      else
      {
         PrintFormat("[V22 EXECUTION FAILED] RetCode: %u | Msg: %s",
                     g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
      ReleaseEntryMutex();
   }
}

//+------------------------------------------------------------------+
//| Trade Transaction Event for Transparent Audit Logging            |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      ulong dealTicket = trans.deal;
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
      {
         ulong dealMagic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         if(dealMagic == g_activeMagic)
         {
            ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
               double comm   = HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
               double swap   = HistoryDealGetDouble(dealTicket, DEAL_SWAP);
               double netPnl = profit + comm + swap;
               double exitSpread = (g_symbolInfo.Ask() - g_symbolInfo.Bid()) / _Point;

               PrintFormat("[V22 SWING AUDIT] Deal #%I64u CLOSED | Net PnL: $%.2f (Profit: $%.2f, Comm: $%.2f, Swap: $%.2f) | Spread: %.1f pts | TF: %s",
                           dealTicket, netPnl, profit, comm, swap, exitSpread, EnumToString(_Period));

               LogOrderJournal(dealTicket, "DEAL_CLOSE",
                               HistoryDealGetDouble(dealTicket, DEAL_VOLUME),
                               HistoryDealGetDouble(dealTicket, DEAL_PRICE),
                               0.0, 0.0, exitSpread, netPnl, "EXIT_CLOSED");
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
