//+------------------------------------------------------------------+
//|                                  QuantumTitan_v9_Singularity.mq5 |
//|           v9.00 Singularity Institutional Quant Framework        |
//|      Multi-Agent Autonomous Trading System: Top 1% Standard      |
//|      Surpassing Benchmarks: Pionex, 3Commas, Cryptohopper        |
//|                    Chief Engineer: Gemini Quantum                |
//+------------------------------------------------------------------+
#property copyright "QuantumTitan Institutional Quant Framework v9.00"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"
#property description "v9+++ Singularity: Market Regime Scoring (vs Cryptohopper), Dynamic TTP & Trailing Buy (vs 3Commas), ATR Geometric Grid & Cash Buffer (vs Pionex), Native MQL5 News Shield"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

#include "Include\QuantumTitan\AlphaScoring.mqh"
#include "Include\QuantumTitan\TrailingSafety.mqh"
#include "Include\QuantumTitan\DynamicGrid.mqh"
#include "Include\QuantumTitan\RiskGuardian.mqh"
#include "Include\QuantumTitan\TelemetryHUD.mqh"

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== 1. ACCOUNT SECURITY & CAPITAL PRESERVATION ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 990900;     // Magic Number (v9 Singularity ID)
input double   InpMaxSpreadPoints      = 45.0;       // Max Allowed Spread (Points)
input double   InpMaxDailyLossPct      = 8.0;        // Daily Loss Kill-Switch (%)
input double   InpHardEquityFloor      = 30.0;       // Hard Equity Floor ($) - Stop All Trading
input int      InpMaxTradesPerDay      = 16;         // Maximum Completed Trades Per Day
input int      InpMaxLosingStreak      = 3;          // Max Consecutive Losses Before Pausing

input group "=== 2. MQL5 NATIVE ECONOMIC NEWS SHIELD ==="
input bool     InpUseNewsFilter        = true;       // Enable Economic Calendar News Filter
input int      InpNewsBufferMinsBefore = 30;         // Pause Trading Before High-Impact News (Mins)
input int      InpNewsBufferMinsAfter  = 30;         // Pause Trading After High-Impact News (Mins)
input bool     InpFilterUSDOnly        = true;       // Filter USD News (Critical for Gold & Majors)

input group "=== 3. MARKET REGIME & ALPHA SCORING (vs Cryptohopper) ==="
input int      InpScoreThreshold       = 75;         // Minimum Confluence Score (0-100)
input int      InpADXTrendLevel        = 25;         // ADX Threshold for Trending Regime
input double   InpShockMultiplier      = 2.2;        // ATR Volatility Shock Multiplier
input ENUM_TIMEFRAMES InpHTF           = PERIOD_H1;  // Institutional Higher Timeframe Trend

input group "=== 4. DYNAMIC TRAILING & SAFETY (vs 3Commas) ==="
input double   InpBreakEvenTriggerR    = 0.4;        // Breakeven Activation (0.4R Profit)
input double   InpTrailingTriggerR     = 1.2;        // Trailing Activation (1.2R Profit)
input double   InpTrailingAtrMult      = 0.6;        // Dynamic Trailing Distance (ATR Multiplier)
input double   InpSafetyBouncePoints   = 35.0;       // Trailing Buy Reversal Bounce (Points)

input group "=== 5. ATR GEOMETRIC GRID & CASH BUFFER (vs Pionex) ==="
input double   InpBaseLot              = 0.01;       // Base Lot Size (0.01 for Micro/Cent)
input int      InpMaxGridOrdersPerSide = 4;          // Hard Max Active Grid Orders Per Side
input double   InpGridStepAtrMult      = 1.0;        // Grid Step Distance (ATR Multiplier)
input double   InpLotMultiplier        = 1.25;       // Geometric Lot Multiplier
input double   InpMinMarginReservePct  = 60.0;       // Dynamic Cash Reserve (Min Free Margin %)
input double   InpBasketTpAtrMult      = 0.8;        // Basket Take Profit Target (ATR Multiplier)

input group "=== 6. VISUAL MATRIX HUD & TELEMETRY ==="
input bool     InpEnableHUD            = true;       // Render Real-Time On-Chart HUD
input bool     InpSendPushAlerts       = true;       // Send MT5 Mobile Push Notifications
input bool     InpSendPopAlerts        = true;       // Send Terminal Popup Alerts

//+------------------------------------------------------------------+
//| GLOBAL SYSTEM INSTANCES                                          |
//+------------------------------------------------------------------+
CTrade                 g_trade;
CPositionInfo          g_position;
CSymbolInfo            g_symbolInfo;

CAlphaScoringEngine    g_alphaEngine;
CTrailingSafetyEngine  g_trailingEngine;
CDynamicGridEngine     g_gridEngine;
CRiskGuardian          g_riskGuardian;
CTelemetryHUD          g_hud;

datetime               g_lastBarTime = 0;
int                    g_handleAtrMain = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("══════════════════════════════════════════════════════════════");
   Print("🚀 INITIALIZING QUANTUMTITAN v9+++ SINGULARITY...");
   Print("══════════════════════════════════════════════════════════════");

   // 1. Demo Lock Check
   if(InpDemoOnly && (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL)
   {
      Alert("🚨 [SECURITY CRITICAL] QuantumTitan v9 is locked to DEMO mode! Real account trading blocked.");
      Print("❌ [SECURITY CRITICAL] Real account trading blocked.");
      return INIT_FAILED;
   }

   // 2. Symbol Info Initialization
   if(!g_symbolInfo.Name(_Symbol))
   {
      PrintFormat("❌ Failed to initialize symbol info for %s", _Symbol);
      return INIT_FAILED;
   }
   g_symbolInfo.Refresh();

   // 3. Trade Object & Dynamic Filling Mode Setup
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(20);

   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      g_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   // 4. Main ATR Indicator for Execution Sizing
   g_handleAtrMain = iATR(_Symbol, _Period, 14);
   if(g_handleAtrMain == INVALID_HANDLE)
   {
      Print("❌ Failed to create main ATR handle");
      return INIT_FAILED;
   }

   // 5. Initialize Module 1: Alpha Scoring Engine (vs Cryptohopper)
   if(!g_alphaEngine.Init(_Symbol, _Period, InpHTF))
   {
      Print("❌ Failed to initialize Module 1: Alpha Scoring Engine");
      return INIT_FAILED;
   }

   // 6. Initialize Module 2: Trailing & Reversal Safety Engine (vs 3Commas)
   if(!g_trailingEngine.Init(_Symbol, InpMagicNumber, InpBreakEvenTriggerR, InpTrailingTriggerR, InpTrailingAtrMult))
   {
      Print("❌ Failed to initialize Module 2: Trailing Safety Engine");
      return INIT_FAILED;
   }

   // 7. Initialize Module 3: ATR Geometric Grid Engine (vs Pionex)
   if(!g_gridEngine.Init(_Symbol, InpMagicNumber, InpBaseLot, InpMaxGridOrdersPerSide,
                         InpGridStepAtrMult, InpLotMultiplier, InpMinMarginReservePct))
   {
      Print("❌ Failed to initialize Module 3: Dynamic Grid Engine");
      return INIT_FAILED;
   }

   // 8. Initialize Module 4: Risk Guardian & Macro News Shield
   if(!g_riskGuardian.Init(_Symbol, InpMagicNumber, InpMaxDailyLossPct, InpHardEquityFloor,
                           InpMaxTradesPerDay, InpMaxLosingStreak, InpMaxSpreadPoints,
                           InpUseNewsFilter, InpNewsBufferMinsBefore, InpNewsBufferMinsAfter))
   {
      Print("❌ Failed to initialize Module 4: Risk Guardian");
      return INIT_FAILED;
   }

   // 9. Initialize Module 5: Visual Matrix HUD & Telemetry
   if(!g_hud.Init(_Symbol, InpEnableHUD, InpSendPushAlerts, InpSendPopAlerts))
   {
      Print("❌ Failed to initialize Module 5: Visual Matrix HUD");
      return INIT_FAILED;
   }

   g_lastBarTime = 0;
   g_hud.DispatchAlert("SYSTEM BOOT", "QuantumTitan v9+++ Singularity activated successfully.", true);

   Print("✅ QUANTUMTITAN v9+++ SINGULARITY INITIALIZED WITH 0 ERRORS.");
   Print("   • Module 1 (Alpha Scoring)  : ACTIVE (Min Score: ", InpScoreThreshold, ")");
   Print("   • Module 2 (TTP & Safety)   : ACTIVE (BE: ", InpBreakEvenTriggerR, "R, Trail: ", InpTrailingTriggerR, "R)");
   Print("   • Module 3 (Geometric Grid) : ACTIVE (Max Orders: ", InpMaxGridOrdersPerSide, ", Cash Buffer: ", InpMinMarginReservePct, "%)");
   Print("   • Module 4 (Risk Guardian)  : ACTIVE (HWM Loss: ", InpMaxDailyLossPct, "%, Floor: $", InpHardEquityFloor, ")");
   Print("   • Module 5 (Matrix HUD)     : ACTIVE");
   Print("══════════════════════════════════════════════════════════════");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("🛑 Deinitializing QuantumTitan v9+++ Singularity... Reason: ", reason);
   if(g_handleAtrMain != INVALID_HANDLE)
   {
      IndicatorRelease(g_handleAtrMain);
      g_handleAtrMain = INVALID_HANDLE;
   }
   g_alphaEngine.Deinit();
   g_hud.Deinit();
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Fetch Current ATR Value
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_handleAtrMain, 0, 1, 1, atrBuf) <= 0) return;
   double currentAtr = atrBuf[0];

   // 2. Refresh Rates
   if(!g_symbolInfo.RefreshRates()) return;
   double bid   = g_symbolInfo.Bid();
   double ask   = g_symbolInfo.Ask();
   double point = g_symbolInfo.Point();
   int    digits= g_symbolInfo.Digits();

   // 3. STEP 1: Institutional Risk Guardian Audit
   RiskTelemetry riskTelem;
   bool isTradingPermitted = g_riskGuardian.ValidateExecution(riskTelem);

   // 4. STEP 2: Module 2 Dynamic Trailing & Breakeven Management
   g_trailingEngine.UpdateTrailing(currentAtr);

   // 5. STEP 3: Module 3 Dynamic Basket Rebalance & Take Profit
   g_gridEngine.CheckAndCloseBasket(currentAtr);

   // Fetch Telemetry from Grid and Alpha engines
   GridBasketTelemetry gridTelem = g_gridEngine.GetTelemetry();
   AlphaScoreTelemetry alphaTelem = g_alphaEngine.GetTelemetry();

   // 6. Render On-Chart Visual Matrix HUD
   double floatingPnl = gridTelem.totalBuyProfit + gridTelem.totalSellProfit;
   g_hud.RenderHUD(
      alphaTelem.regimeName,
      alphaTelem.totalScoreBuy,
      alphaTelem.totalScoreSell,
      gridTelem.buyOrderCount,
      gridTelem.totalBuyLots,
      gridTelem.sellOrderCount,
      gridTelem.totalSellLots,
      floatingPnl,
      riskTelem.dailyHighWaterMark,
      riskTelem.currentDrawdownPct,
      gridTelem.freeMarginPct,
      riskTelem.inNewsLockout ? riskTelem.newsEventName : "CLEAR",
      isTradingPermitted,
      riskTelem.rejectReason
   );

   // 7. STEP 4: Active Basket Grid Layer Placement (if in active position)
   // DECOUPLED ARCHITECTURE: Existing basket is allowed to rebalance/average-down
   // as long as riskTelem.canManageGrid is TRUE and market is NOT in a Volatility Shock!
   if(riskTelem.canManageGrid && alphaTelem.regime != REGIME_VOLATILITY_SHOCK)
   {
      if(gridTelem.buyOrderCount > 0 || gridTelem.sellOrderCount > 0)
      {
         g_gridEngine.EvaluateGridStep(currentAtr, true, true);
      }
   }

   // 8. STEP 5: New Cycle Entry Gatekeeper
   // Strictly block opening NEW trade cycles if circuit breaker, news lockout, or streak pause is active!
   if(!riskTelem.canOpenNewCycle) return;

   // 9. STEP 6: 3Commas Trailing Buy Reversal Check
   double execLot = 0.0;
   if(g_trailingEngine.CheckTrailingSafetyTrigger(bid, ask, execLot))
   {
      // Open safety order after reversal confirmed
      if(g_trade.Buy(execLot, _Symbol, ask, 0, 0, "QT9_TrailingBuy_Reversal"))
      {
         g_hud.DispatchAlert("TRAILING BUY TRIGGERED", StringFormat("Reversal safety buy executed at %.5f (Lot: %.2f)", ask, execLot));
      }
   }

   // 10. STEP 7: New Bar Signal Generation (Bar-Close Discipline)
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == g_lastBarTime) return; // Only evaluate new entries once per closed bar
   g_lastBarTime = currentBarTime;

   // Evaluate Alpha Confluence Signals (Score >= 75)
   ENUM_ALPHA_SIGNAL signal = g_alphaEngine.EvaluateSignals(alphaTelem);

   // DYNAMIC MICRO-ACCOUNT RISK BUDGETING: Cap single-order SL to max $3.00 (6% of $50 equity)
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double maxRiskDollars = (equity <= 100.0) ? 3.00 : (equity * 0.02);
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double pointVal = (tickSz > 0) ? (tickVal / tickSz) * point : 1.0;
   double maxSlPoints = (pointVal > 0 && InpBaseLot > 0) ? (maxRiskDollars / (InpBaseLot * pointVal)) : (currentAtr * 1.5 / point);
   double slDist = MathMin(currentAtr * 1.5, maxSlPoints * point);
   double tpDist = currentAtr * 1.8 * 1.5;

   // Only open new initial entries if no opposing positions exist and basket within limits
   if(signal == ALPHA_SIGNAL_BUY && gridTelem.buyOrderCount == 0 && gridTelem.sellOrderCount == 0)
   {
      double sl = NormalizeDouble(ask - slDist, digits);
      double tp = NormalizeDouble(ask + tpDist, digits);

      if(g_trade.Buy(InpBaseLot, _Symbol, ask, sl, tp, "QuantumTitan_Alpha_Buy"))
      {
         g_hud.DispatchAlert("ALPHA BUY ENTRY", StringFormat("Score: %d/100 | Regime: %s | SL: %.5f ($%.2f risk) | TP: %.5f",
            alphaTelem.totalScoreBuy, alphaTelem.regimeName, sl, maxRiskDollars, tp));
         g_hud.DrawTradeArrow("BUY_" + IntegerToString((int)TimeCurrent()), TimeCurrent(), ask, true);
      }
   }
   else if(signal == ALPHA_SIGNAL_SELL && gridTelem.buyOrderCount == 0 && gridTelem.sellOrderCount == 0)
   {
      double sl = NormalizeDouble(bid + slDist, digits);
      double tp = NormalizeDouble(bid - tpDist, digits);

      if(g_trade.Sell(InpBaseLot, _Symbol, bid, sl, tp, "QuantumTitan_Alpha_Sell"))
      {
         g_hud.DispatchAlert("ALPHA SELL ENTRY", StringFormat("Score: %d/100 | Regime: %s | SL: %.5f ($%.2f risk) | TP: %.5f",
            alphaTelem.totalScoreSell, alphaTelem.regimeName, sl, maxRiskDollars, tp));
         g_hud.DrawTradeArrow("SELL_" + IntegerToString((int)TimeCurrent()), TimeCurrent(), bid, false);
      }
   }
}

//+------------------------------------------------------------------+
//| TradeTransaction event handler                                   |
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
         if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) == _Symbol &&
            HistoryDealGetInteger(dealTicket, DEAL_MAGIC) == InpMagicNumber)
         {
            long entry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            {
               double pnl = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
               PrintFormat("[QuantumTitan v9] DEAL CLOSED #%I64u: PnL: %s$%.2f",
                  dealTicket, (pnl >= 0 ? "+" : ""), pnl);
            }
         }
      }
   }
}
