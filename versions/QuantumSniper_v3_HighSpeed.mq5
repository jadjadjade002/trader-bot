//+------------------------------------------------------------------+
//|                                     QuantumSniper_v3_HighSpeed.mq5|
//|                     High-Speed Dynamic Scalper Pro 3.6 (Cooldown) |
//|                                      https://www.mql5.com        |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Scalper"
#property link      "https://www.mql5.com"
#property version   "3.60"
#property description "Version 3.6: High-Speed Scalper with Post-Trade Cooldown & Anti-Churn Guard (Pre-TradingView Indicators)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== 1. ACCOUNT SAFETY & DEMO GUARD ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 777888;     // Magic Number (Bot ID)
input double   InpMaxSpreadPoints      = 50.0;       // Max Spread Allowed (Points)
input double   InpMaxDailyLossPct      = 10.0;       // Daily Drawdown Auto-Kill Switch (%)

input group "=== 2. HIGH-SPEED SCALPING ENGINE ==="
input int      InpTargetScore          = 45;         // Fast-Trigger Target Score (45% = High Speed)
input int      InpCooldownBars         = 1;          // Cooldown Period After Exit (Bars)
input int      InpSweepLookback        = 2;          // Rapid Liquidity Lookback (Bars)

input group "=== 3. RISK & POSITION MANAGEMENT ($50 Capital) ==="
input double   InpFixedLot             = 0.01;       // Fixed Lot Size (0.01 for $50)
input double   InpRiskRewardRatio      = 1.5;        // Rapid Profit Target (1:1.5 R:R)
input double   InpSL_ATR_Multiplier    = 1.2;        // SL Buffer Multiplier
input double   InpBreakEvenTriggerR    = 0.8;        // Fast Break-Even Trigger (at 0.8R Profit)
input bool     InpUseTrailingStop      = true;       // Enable Dynamic Trailing Stop
input double   InpTrailingTriggerR     = 1.2;        // Activate Trailing at 1.2R Profit

//--- GLOBAL OBJECTS & HANDLES ---
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

int            h_fastEMA;
int            h_mediumEMA;
int            h_rsi;
int            h_atr;

datetime       m_lastBarTime;
double         m_startingDailyEquity;
datetime       m_currentDay;

// Cooldown Tracker
datetime       g_lastExitTime = 0;
bool           g_wasInPosition = false;

// Live Diagnostics
int            g_liveBuyScore = 0;
int            g_liveSellScore = 0;
int            g_displayScore = 0;
string         g_scoreBreakdown = "";
string         g_lastSignalReason = "High-Speed Hunter Ready";

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

   h_fastEMA   = iMA(_Symbol, _Period, 9, 0, MODE_EMA, PRICE_CLOSE);
   h_mediumEMA = iMA(_Symbol, _Period, 21, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi       = iRSI(_Symbol, _Period, 7, PRICE_CLOSE);
   h_atr       = iATR(_Symbol, _Period, 14);

   if(h_fastEMA == INVALID_HANDLE || h_mediumEMA == INVALID_HANDLE ||
      h_rsi == INVALID_HANDLE || h_atr == INVALID_HANDLE)
   {
      Print("❌ Failed to initialize indicator handles");
      return(INIT_FAILED);
   }

   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_currentDay = iTime(_Symbol, PERIOD_D1, 0);
   m_lastBarTime = 0;
   g_wasInPosition = HasOpenPosition();

   Print("⚡ QuantumSniper v3.6 High-Speed Initialized on ", _Symbol, " (TF: ", EnumToString(_Period), ")");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_fastEMA);
   IndicatorRelease(h_mediumEMA);
   IndicatorRelease(h_rsi);
   IndicatorRelease(h_atr);
   Comment("");
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

   // 3. Manage Open Trades
   ManageOpenPositionsSafe();

   // 4. Track Position Exits for Cooldown Guard
   bool currentlyInTrade = HasOpenPosition();
   if(g_wasInPosition && !currentlyInTrade)
   {
      g_lastExitTime = TimeCurrent();
      Print("⏳ Trade closed. Cooldown activated for ", InpCooldownBars, " bar(s).");
   }
   g_wasInPosition = currentlyInTrade;

   // 5. Calculate Live Scores
   CalculateLiveScores();

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

   // 10. Execute Trade
   CheckAndExecuteTrade();

   m_lastBarTime = currentBarTime;
}

//+------------------------------------------------------------------+
//| Fast Confluence Score Calculation                                |
//+------------------------------------------------------------------+
void CalculateLiveScores()
{
   double fastEMA[2], medEMA[2], rsi[3];
   if(CopyBuffer(h_fastEMA, 0, 0, 2, fastEMA) < 2) return;
   if(CopyBuffer(h_mediumEMA, 0, 0, 2, medEMA) < 2) return;
   if(CopyBuffer(h_rsi, 0, 0, 3, rsi) < 3) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, 20, rates) < 20) return;

   double swingHigh = rates[InpSweepLookback + 1].high;
   double swingLow  = rates[InpSweepLookback + 1].low;
   for(int i = InpSweepLookback + 2; i <= InpSweepLookback + 5; i++)
   {
      if(rates[i].high > swingHigh) swingHigh = rates[i].high;
      if(rates[i].low < swingLow)   swingLow  = rates[i].low;
   }

   bool sweptLow = false, sweptHigh = false;
   for(int i = 1; i <= InpSweepLookback; i++)
   {
      if(rates[i].low <= swingLow)   sweptLow = true;
      if(rates[i].high >= swingHigh) sweptHigh = true;
   }

   bool bullMom = (rates[0].close >= fastEMA[0]) || (fastEMA[0] >= medEMA[0]);
   bool bearMom = (rates[0].close <= fastEMA[0]) || (fastEMA[0] <= medEMA[0]);

   bool rsiBull = (rsi[0] >= 38.0 && rsi[0] <= 72.0);
   bool rsiBear = (rsi[0] <= 62.0 && rsi[0] >= 28.0);

   bool bullCandle = (rates[0].close >= rates[0].open) || (rates[1].close > rates[1].open);
   bool bearCandle = (rates[0].close <= rates[0].open) || (rates[1].close < rates[1].open);

   g_liveBuyScore = 0;
   if(sweptLow)    g_liveBuyScore += 25;
   if(bullMom)     g_liveBuyScore += 25;
   if(rsiBull)     g_liveBuyScore += 25;
   if(bullCandle)  g_liveBuyScore += 25;

   g_liveSellScore = 0;
   if(sweptHigh)   g_liveSellScore += 25;
   if(bearMom)     g_liveSellScore += 25;
   if(rsiBear)     g_liveSellScore += 25;
   if(bearCandle)  g_liveSellScore += 25;

   if(g_liveBuyScore >= g_liveSellScore)
   {
      g_displayScore = g_liveBuyScore;
      g_scoreBreakdown = "BUY [Swp:" + (sweptLow?"25":"0") + " Mom:" + (bullMom?"25":"0") + " RSI:" + (rsiBull?"25":"0") + " Bar:" + (bullCandle?"25":"0") + "]";
   }
   else
   {
      g_displayScore = g_liveSellScore;
      g_scoreBreakdown = "SELL [Swp:" + (sweptHigh?"25":"0") + " Mom:" + (bearMom?"25":"0") + " RSI:" + (rsiBear?"25":"0") + " Bar:" + (bearCandle?"25":"0") + "]";
   }
}

//+------------------------------------------------------------------+
//| Execute Fast Trade with Cooldown Filter                          |
//+------------------------------------------------------------------+
void CheckAndExecuteTrade()
{
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

   double safeBuffer = atr[0] * InpSL_ATR_Multiplier;
   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minStopDist = MathMax((double)stopLevel * _Point, 25 * _Point);
   if(safeBuffer < minStopDist) safeBuffer = minStopDist;

   // BUY TRIGGER
   if(g_liveBuyScore >= InpTargetScore && (rates[1].close >= rates[1].open || rates[0].close >= rates[0].open))
   {
      double entryPrice = m_symbol.Ask();
      double sl = entryPrice - safeBuffer;
      double riskPoints = entryPrice - sl;
      if(riskPoints <= 0) return;

      double tp = entryPrice + (riskPoints * InpRiskRewardRatio);
      m_trade.Buy(InpFixedLot, _Symbol, entryPrice, sl, tp, "FastScalp BUY (" + IntegerToString(g_liveBuyScore) + "%)");
      g_lastSignalReason = "🚀 BUY Executed (Score: " + IntegerToString(g_liveBuyScore) + "%)";
      Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
      return;
   }

   // SELL TRIGGER
   if(g_liveSellScore >= InpTargetScore && (rates[1].close <= rates[1].open || rates[0].close <= rates[0].open))
   {
      double entryPrice = m_symbol.Bid();
      double sl = entryPrice + safeBuffer;
      double riskPoints = sl - entryPrice;
      if(riskPoints <= 0) return;

      double tp = entryPrice - (riskPoints * InpRiskRewardRatio);
      m_trade.Sell(InpFixedLot, _Symbol, entryPrice, sl, tp, "FastScalp SELL (" + IntegerToString(g_liveSellScore) + "%)");
      g_lastSignalReason = "🔻 SELL Executed (Score: " + IntegerToString(g_liveSellScore) + "%)";
      Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
      return;
   }

   g_lastSignalReason = "Scanning Fast Setup (Score: " + IntegerToString(g_displayScore) + "% / Target: " + IntegerToString(InpTargetScore) + "%)";
}

//+------------------------------------------------------------------+
//| Safe Position Management                                         |
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

      // 1. Break-Even Check
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
   hud += "  ⚡ QUANTUM SNIPER v3.6 HIGH-SPEED ⚡\n";
   hud += "===========================================\n";
   hud += " Mode           : HIGH-SPEED (" + EnumToString(_Period) + ")\n";
   hud += " Target Score   : >= " + IntegerToString(InpTargetScore) + "% (Current: " + IntegerToString(g_displayScore) + "%)\n";
   hud += " Capital Equity : $" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
   hud += " Spread Check   : " + IntegerToString((long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)) + " pts\n";
   hud += " Breakdown      : " + g_scoreBreakdown + "\n";
   hud += " Status         : " + g_lastSignalReason + "\n";
   hud += " Active Trades  : " + (HasOpenPosition() ? "IN TRADE 🟢" : "READY / HUNTING ⚡") + "\n";
   hud += "===========================================";
   Comment(hud);
}
