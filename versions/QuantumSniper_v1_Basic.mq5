//+------------------------------------------------------------------+
//|                                             QuantumSniper_EA.mq5 |
//|                                  Copyright 2026, Institutional EA|
//|                                      https://www.mql5.com        |
//+------------------------------------------------------------------+
#property copyright "Institutional Scalper"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property description "High-Precision Liquidity Sweep & Momentum Scalper"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== 1. ACCOUNT SAFETY & DEMO GUARD ==="
input bool     InpDemoOnly             = true;       // Lock EA to DEMO Account Only
input ulong    InpMagicNumber          = 777888;     // Magic Number (Bot ID)
input double   InpMaxSpreadPoints      = 35;         // Max Spread Allowed (Points)
input double   InpMaxDailyLossPct      = 10.0;       // Daily Drawdown Auto-Kill Switch (%)

input group "=== 2. RISK & LOT MANAGEMENT ($50 Capital) ==="
input double   InpFixedLot             = 0.01;       // Fixed Lot Size (Recommended: 0.01 for $50)
input bool     InpUseDynamicLot        = false;      // Use Dynamic Risk % instead of Fixed Lot
input double   InpRiskPercent          = 3.0;        // Risk % per Trade (if Dynamic is true)

input group "=== 3. STRATEGY PARAMETERS ==="
input int      InpSwingBars            = 5;          // Swing Lookback Bars for Liquidity Sweep
input int      InpFastEMA              = 9;          // Fast Momentum EMA
input int      InpMediumEMA            = 21;         // Medium Trend EMA
input int      InpBaselineEMA          = 200;        // Long-term Regime Filter EMA
input int      InpRSIPeriod            = 7;          // Fast RSI Period
input int      InpATRPeriod            = 14;         // ATR Volatility Period

input group "=== 4. TAKE PROFIT, SL & TRAILING ==="
input double   InpRiskRewardRatio      = 2.0;        // Risk to Reward Ratio (1:2)
input double   InpBreakEvenTriggerR    = 1.0;        // Move SL to Entry at 1.0R Profit
input bool     InpUseTrailingStop      = true;       // Enable Dynamic Trailing Stop
input double   InpTrailingTriggerR     = 1.5;        // Activate Trailing at 1.5R Profit

//--- GLOBAL OBJECTS & HANDLES ---
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

int            h_emaFast, h_emaMedium, h_emaBaseline;
int            h_rsi;
int            h_atr;

datetime       m_lastBarTime;
double         m_startingDailyEquity;
datetime       m_currentDay;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // 1. Check Demo Guard
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Alert("❌ CRITICAL ERROR: This EA is locked for DEMO testing only!");
      Print("EA Stopped: Attempted to run on a Non-Demo account.");
      return(INIT_FAILED);
   }

   // 2. Initialize Symbol & Trade class
   if(!m_symbol.Name(_Symbol))
   {
      Print("Error initializing SymbolInfo");
      return(INIT_FAILED);
   }
   m_symbol.Refresh();

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(10);
   m_trade.SetTypeFillingBySymbol(_Symbol);

   // 3. Initialize Indicators
   h_emaFast     = iMA(_Symbol, _Period, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   h_emaMedium   = iMA(_Symbol, _Period, InpMediumEMA, 0, MODE_EMA, PRICE_CLOSE);
   h_emaBaseline = iMA(_Symbol, _Period, InpBaselineEMA, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi         = iRSI(_Symbol, _Period, InpRSIPeriod, PRICE_CLOSE);
   h_atr         = iATR(_Symbol, _Period, InpATRPeriod);

   if(h_emaFast == INVALID_HANDLE || h_emaMedium == INVALID_HANDLE || 
      h_emaBaseline == INVALID_HANDLE || h_rsi == INVALID_HANDLE || h_atr == INVALID_HANDLE)
   {
      Print("Error creating indicator handles");
      return(INIT_FAILED);
   }

   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_currentDay = iTime(_Symbol, PERIOD_D1, 0);
   m_lastBarTime = 0;

   Print("✅ QuantumSniper EA Initialized Successfully on ", _Symbol);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_emaFast);
   IndicatorRelease(h_emaMedium);
   IndicatorRelease(h_emaBaseline);
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
   
   // 1. Update Daily Equity Tracker for Daily Drawdown Guard
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != m_currentDay)
   {
      m_currentDay = today;
      m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   }

   // 2. Check Daily Kill-Switch
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDrawdownPct = ((m_startingDailyEquity - currentEquity) / m_startingDailyEquity) * 100.0;
   
   // 3. Manage Open Positions (Break-Even & Trailing Stop on every tick)
   ManageOpenPositions();

   // 4. Update HUD On-Screen Dashboard
   UpdateHUD(dailyDrawdownPct);

   if(dailyDrawdownPct >= InpMaxDailyLossPct)
   {
      Comment("\n🚨 DAILY KILL-SWITCH ACTIVE: Max daily drawdown reached (", DoubleToString(dailyDrawdownPct, 1), "%). Trading locked today.");
      return;
   }

   // 5. Check if it's a new candle
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == m_lastBarTime) return; // Only scan for new entries once per candle
   m_lastBarTime = currentBarTime;

   // 6. Check Spread Protection
   double currentSpread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxSpreadPoints)
   {
      Print("Entry skipped: Spread too high (", currentSpread, " > ", InpMaxSpreadPoints, ")");
      return;
   }

   // 7. Check if there is already an open position by this EA
   if(HasOpenPosition()) return;

   // 8. Evaluate Trade Entry Logic
   CheckForEntry();
}

//+------------------------------------------------------------------+
//| Core Entry Logic (Liquidity Sweep + Momentum)                    |
//+------------------------------------------------------------------+
void CheckForEntry()
{
   // Copy indicator values (Bar 1 = closed bar)
   double emaFast[2], emaMedium[2], emaBaseline[2], rsi[3], atr[2];
   if(CopyBuffer(h_emaFast, 0, 1, 2, emaFast) < 2) return;
   if(CopyBuffer(h_emaMedium, 0, 1, 2, emaMedium) < 2) return;
   if(CopyBuffer(h_emaBaseline, 0, 1, 2, emaBaseline) < 2) return;
   if(CopyBuffer(h_rsi, 0, 1, 3, rsi) < 3) return;
   if(CopyBuffer(h_atr, 0, 1, 2, atr) < 2) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, InpSwingBars + 5, rates) < InpSwingBars + 5) return;

   // Find Previous Swing High and Low (Liquidity levels)
   double swingHigh = rates[2].high;
   double swingLow  = rates[2].low;
   for(int i = 3; i <= InpSwingBars + 2; i++)
   {
      if(rates[i].high > swingHigh) swingHigh = rates[i].high;
      if(rates[i].low < swingLow)   swingLow  = rates[i].low;
   }

   bool isBullishEngulfing = (rates[1].close > rates[1].open) && (rates[1].close > rates[2].high);
   bool isBearishEngulfing = (rates[1].close < rates[1].open) && (rates[1].close < rates[2].low);

   double lotSize = CalculateLotSize(atr[0]);

   // --- BULLISH SETUP ---
   // 1. Baseline Trend Filter: Price above 200 EMA
   // 2. Liquidity Grab: Candle 1 swept below swingLow
   // 3. Reversal confirmation: Bullish Engulfing closed above 9 EMA
   // 4. RSI momentum recovery: RSI crossed above 35 from oversold
   if(rates[1].close > emaBaseline[0] && rates[1].low < swingLow && isBullishEngulfing && 
      rates[1].close > emaFast[0] && rsi[0] > 35.0 && rsi[1] <= 35.0)
   {
      double entryPrice = m_symbol.Ask();
      double sl = rates[1].low - (atr[0] * 0.5);
      double riskPoints = entryPrice - sl;
      if(riskPoints <= 0) return;

      double tp = entryPrice + (riskPoints * InpRiskRewardRatio);

      m_trade.Buy(lotSize, _Symbol, entryPrice, sl, tp, "Quantum Buy Sweep");
      Print("🚀 BUY Executed at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
   }

   // --- BEARISH SETUP ---
   // 1. Baseline Trend Filter: Price below 200 EMA
   // 2. Liquidity Grab: Candle 1 swept above swingHigh
   // 3. Reversal confirmation: Bearish Engulfing closed below 9 EMA
   // 4. RSI momentum drop: RSI crossed below 65 from overbought
   if(rates[1].close < emaBaseline[0] && rates[1].high > swingHigh && isBearishEngulfing && 
      rates[1].close < emaFast[0] && rsi[0] < 65.0 && rsi[1] >= 65.0)
   {
      double entryPrice = m_symbol.Bid();
      double sl = rates[1].high + (atr[0] * 0.5);
      double riskPoints = sl - entryPrice;
      if(riskPoints <= 0) return;

      double tp = entryPrice - (riskPoints * InpRiskRewardRatio);

      m_trade.Sell(lotSize, _Symbol, entryPrice, sl, tp, "Quantum Sell Sweep");
      Print("🔻 SELL Executed at ", entryPrice, " | SL: ", sl, " | TP: ", tp);
   }
}

//+------------------------------------------------------------------+
//| Position Management (Break-Even & Trailing Stop)                 |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Magic() != InpMagicNumber || m_position.Symbol() != _Symbol) continue;

      double openPrice = m_position.PriceOpen();
      double currentSL  = m_position.StopLoss();
      double currentTP  = m_position.TakeProfit();
      double currentPrice = (m_position.PositionType() == POSITION_TYPE_BUY) ? m_symbol.Bid() : m_symbol.Ask();
      
      double initialRisk = MathAbs(openPrice - currentSL);
      if(initialRisk == 0) continue;

      // 1. Break-Even Check (Triggered at 1.0R)
      if(m_position.PositionType() == POSITION_TYPE_BUY)
      {
         double profitPoints = currentPrice - openPrice;
         if(profitPoints >= initialRisk * InpBreakEvenTriggerR && currentSL < openPrice)
         {
            double newSL = openPrice + (10 * _Point); // Entry + 1 pip profit buffer
            m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
            Print("🛡️ BUY SL moved to Break-Even");
         }

         // 2. Trailing Stop Check (Triggered at 1.5R)
         if(InpUseTrailingStop && profitPoints >= initialRisk * InpTrailingTriggerR)
         {
            double trailingSL = currentPrice - (initialRisk * 0.8);
            if(trailingSL > currentSL)
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
            double newSL = openPrice - (10 * _Point);
            m_trade.PositionModify(m_position.Ticket(), newSL, currentTP);
            Print("🛡️ SELL SL moved to Break-Even");
         }

         // 2. Trailing Stop Check (Triggered at 1.5R)
         if(InpUseTrailingStop && profitPoints >= initialRisk * InpTrailingTriggerR)
         {
            double trailingSL = currentPrice + (initialRisk * 0.8);
            if(trailingSL < currentSL || currentSL == 0)
            {
               m_trade.PositionModify(m_position.Ticket(), trailingSL, currentTP);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helpers & Calculations                                           |
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

double CalculateLotSize(double atrVal)
{
   if(!InpUseDynamicLot) return InpFixedLot;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (InpRiskPercent / 100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0 || tickSize <= 0) return InpFixedLot;

   double riskPoints = (atrVal * 1.5) / _Point;
   double calculatedLot = (riskAmount / (riskPoints * tickValue));
   
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   calculatedLot = MathFloor(calculatedLot / lotStep) * lotStep;
   if(calculatedLot < minLot) calculatedLot = minLot;
   if(calculatedLot > maxLot) calculatedLot = maxLot;

   return calculatedLot;
}

void UpdateHUD(double dailyDD)
{
   string accMode = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO (Safe)" : "REAL (Live)";
   string hud = "====================================\n";
   hud += "  ⚡ QUANTUM SNIPER SCALPER EA ⚡\n";
   hud += "====================================\n";
   hud += " Account Mode  : " + accMode + "\n";
   hud += " Equity        : $" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
   hud += " Balance       : $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n";
   hud += " Daily Drawdown: " + DoubleToString(dailyDD, 2) + "% / " + DoubleToString(InpMaxDailyLossPct, 1) + "%\n";
   hud += " Current Spread: " + IntegerToString((long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)) + " pts\n";
   hud += " Active Trades : " + (HasOpenPosition() ? "IN TRADE 🟢" : "SCANNING... 🔍") + "\n";
   hud += "====================================";
   Comment(hud);
}