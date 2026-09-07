//+------------------------------------------------------------------+
//|                                                AlphaScoring.mqh  |
//|               QuantumTitan v13.00 Singularity Architecture       |
//|               Module 1: Institutional Macro Brain & Confluence   |
//|               Top-Down Narrative, Premium/Discount, FVG, Sweeps  |
//|               Beating Benchmark: Cryptohopper Strategy Designer  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "13.00"

//--- Market Regime Enumeration
enum ENUM_MARKET_REGIME
{
   REGIME_UNKNOWN          = 0,
   REGIME_TREND_BULL       = 1, // Strong Uptrend (ADX > 25, EMA20 > EMA50 > EMA200)
   REGIME_TREND_BEAR       = 2, // Strong Downtrend (ADX > 25, EMA20 < EMA50 < EMA200)
   REGIME_CHOP_RANGE       = 3, // Low Volatility / Consolidation (ADX < 20, Squeeze ON)
   REGIME_VOLATILITY_SHOCK = 4  // Extreme Volatility / News Spike (ATR > 2.2x Normal)
};

//--- Signal Type Enumeration
enum ENUM_ALPHA_SIGNAL
{
   ALPHA_SIGNAL_NONE = 0,
   ALPHA_SIGNAL_BUY  = 1,
   ALPHA_SIGNAL_SELL = 2
};

//--- Institutional Macro Valuation Zone (The 50% Rule)
enum ENUM_MACRO_ZONE
{
   ZONE_EQUILIBRIUM = 0, // Fair Value (48% - 52%)
   ZONE_DISCOUNT    = 1, // Cheap (<48%): Institutional Buy Zone, SELL Blocked
   ZONE_PREMIUM     = 2  // Expensive (>52%): Institutional Sell Zone, BUY Blocked
};

//--- Score Breakdown Struct for Telemetry & HUD
struct AlphaScoreTelemetry
{
   ENUM_MARKET_REGIME regime;
   ENUM_MACRO_ZONE    macroZone;
   string             macroZoneName;
   double             zonePct;          // 0.0% (lowest low) to 100.0% (highest high)
   string             dailyBias;        // "BULLISH", "BEARISH", "NEUTRAL"
   string             killzone;         // "LONDON KZ", "NEW YORK KZ", "OFF-HOURS"
   bool               liquiditySweptBuy;
   bool               liquiditySweptSell;
   bool               fvgMitigatedBuy;
   bool               fvgMitigatedSell;
   int                totalScoreBuy;
   int                totalScoreSell;
   int                trendScore;       // Max 25
   int                zoneScore;        // Max 20
   int                structureScore;   // Max 20 (Liquidity Sweep & SMC)
   int                fvgSqueezeScore;  // Max 15 (FVG Imbalance & Squeeze)
   int                rsiScore;         // Max 10
   int                killzoneScore;    // Max 10
   double             adxValue;
   double             atrValue;
   double             atrBaseline;
   double             rsiValue;
   bool               squeezeActive;
   string             regimeName;
};

//+------------------------------------------------------------------+
//| Class CAlphaScoringEngine                                        |
//+------------------------------------------------------------------+
class CAlphaScoringEngine
{
private:
   string             m_symbol;
   ENUM_TIMEFRAMES    m_timeframe;
   ENUM_TIMEFRAMES    m_htfTimeframe;

   // Indicator Handles
   int                m_handleEMA20;
   int                m_handleEMA50;
   int                m_handleEMA200;
   int                m_handleADX;
   int                m_handleATR;
   int                m_handleRSI;
   int                m_handleBB;

   // Parameters
   int                m_scoreThreshold; // Minimum score to trigger signal (Default 75)
   int                m_adxTrendLevel;   // ADX Level for trending (Default 25)
   int                m_adxChopLevel;    // ADX Level for chop (Default 20)
   double             m_shockMultiplier; // ATR shock threshold (Default 2.2)

   // Telemetry Cache
   AlphaScoreTelemetry m_telemetry;

   // Internal Institutional Calculation Helpers
   void               CalculateEquilibriumZone(double &zonePct, ENUM_MACRO_ZONE &zone, string &zoneStr);
   void               DetectMacroLiquiditySweep(bool &sweptBuy, bool &sweptSell);
   void               DetectFairValueGap(bool &fvgBuy, bool &fvgSell);
   void               GetDailyBias(string &biasStr);
   void               GetSessionKillzone(string &kzStr, int &kzPts);
   bool               CalculateSqueeze(bool &sqzOn, double &sqzMomentum);
   bool               DetectSMCSweep(bool &bullSweep, bool &bearSweep, double &obTop, double &obBottom);

public:
                      CAlphaScoringEngine();
                     ~CAlphaScoringEngine();

   bool               Init(string symbol, ENUM_TIMEFRAMES tf, ENUM_TIMEFRAMES htf = PERIOD_H1);
   void               Deinit();

   // Core Evaluation
   ENUM_ALPHA_SIGNAL  EvaluateSignals(AlphaScoreTelemetry &telemetryOut);
   ENUM_MARKET_REGIME DetectRegime();
   
   // Accessors
   AlphaScoreTelemetry GetTelemetry() const { return m_telemetry; }
   string             GetRegimeString(ENUM_MARKET_REGIME regime);
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CAlphaScoringEngine::CAlphaScoringEngine()
   : m_symbol(""),
     m_timeframe(PERIOD_CURRENT),
     m_htfTimeframe(PERIOD_H1),
     m_handleEMA20(INVALID_HANDLE),
     m_handleEMA50(INVALID_HANDLE),
     m_handleEMA200(INVALID_HANDLE),
     m_handleADX(INVALID_HANDLE),
     m_handleATR(INVALID_HANDLE),
     m_handleRSI(INVALID_HANDLE),
     m_handleBB(INVALID_HANDLE),
     m_scoreThreshold(75),
     m_adxTrendLevel(25),
     m_adxChopLevel(20),
     m_shockMultiplier(2.2)
{
   ZeroMemory(m_telemetry);
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CAlphaScoringEngine::~CAlphaScoringEngine()
{
   Deinit();
}

//+------------------------------------------------------------------+
//| Deinitialization & Clean Handle Release                          |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::Deinit()
{
   if(m_handleEMA20 != INVALID_HANDLE)  { IndicatorRelease(m_handleEMA20);  m_handleEMA20 = INVALID_HANDLE; }
   if(m_handleEMA50 != INVALID_HANDLE)  { IndicatorRelease(m_handleEMA50);  m_handleEMA50 = INVALID_HANDLE; }
   if(m_handleEMA200 != INVALID_HANDLE) { IndicatorRelease(m_handleEMA200); m_handleEMA200 = INVALID_HANDLE; }
   if(m_handleADX != INVALID_HANDLE)    { IndicatorRelease(m_handleADX);    m_handleADX = INVALID_HANDLE; }
   if(m_handleATR != INVALID_HANDLE)    { IndicatorRelease(m_handleATR);    m_handleATR = INVALID_HANDLE; }
   if(m_handleRSI != INVALID_HANDLE)    { IndicatorRelease(m_handleRSI);    m_handleRSI = INVALID_HANDLE; }
   if(m_handleBB != INVALID_HANDLE)     { IndicatorRelease(m_handleBB);     m_handleBB = INVALID_HANDLE; }
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
bool CAlphaScoringEngine::Init(string symbol, ENUM_TIMEFRAMES tf, ENUM_TIMEFRAMES htf)
{
   Deinit();
   m_symbol = (symbol == "") ? _Symbol : symbol;
   m_timeframe = (tf == PERIOD_CURRENT) ? _Period : tf;
   m_htfTimeframe = htf;

   // 1. HTF Trend EMAs
   m_handleEMA20  = iMA(m_symbol, m_htfTimeframe, 20, 0, MODE_EMA, PRICE_CLOSE);
   m_handleEMA50  = iMA(m_symbol, m_htfTimeframe, 50, 0, MODE_EMA, PRICE_CLOSE);
   m_handleEMA200 = iMA(m_symbol, m_htfTimeframe, 200, 0, MODE_EMA, PRICE_CLOSE);

   // 2. ADX for Market Regime (Trend vs Chop)
   m_handleADX    = iADX(m_symbol, m_timeframe, 14);

   // 3. ATR for Volatility Shock & Dynamic Spacing
   m_handleATR    = iATR(m_symbol, m_timeframe, 14);

   // 4. RSI for Exhaustion & Anti-Chop
   m_handleRSI    = iRSI(m_symbol, m_timeframe, 14, PRICE_CLOSE);

   // 5. Bollinger Bands for LazyBear Squeeze Detection
   m_handleBB     = iBands(m_symbol, m_timeframe, 20, 0, 2.0, PRICE_CLOSE);

   if(m_handleEMA20 == INVALID_HANDLE || m_handleEMA50 == INVALID_HANDLE || m_handleEMA200 == INVALID_HANDLE ||
      m_handleADX == INVALID_HANDLE || m_handleATR == INVALID_HANDLE || m_handleRSI == INVALID_HANDLE ||
      m_handleBB == INVALID_HANDLE)
   {
      PrintFormat("[AlphaScoring] ERROR: Failed to create indicator handles for %s. Error: %d", m_symbol, GetLastError());
      return false;
   }

   AlphaScoreTelemetry initTelem;
   EvaluateSignals(initTelem);

   PrintFormat("[AlphaScoring] Institutional Macro Brain initialized for %s (TF: %d, HTF: %d)", m_symbol, m_timeframe, m_htfTimeframe);
   return true;
}

//+------------------------------------------------------------------+
//| 1. Institutional Equilibrium & Valuation Zone (The 50% Rule)     |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::CalculateEquilibriumZone(double &zonePct, ENUM_MACRO_ZONE &zone, string &zoneStr)
{
   zonePct = 50.0;
   zone = ZONE_EQUILIBRIUM;
   zoneStr = "EQUILIBRIUM (50.0%)";

   MqlRates htfRates[];
   ArraySetAsSeries(htfRates, true);
   int copied = CopyRates(m_symbol, m_htfTimeframe, 0, 48, htfRates);
   if(copied < 20) return;

   double macroHigh = htfRates[0].high;
   double macroLow  = htfRates[0].low;
   for(int i = 1; i < copied; i++)
   {
      if(htfRates[i].high > macroHigh) macroHigh = htfRates[i].high;
      if(htfRates[i].low  < macroLow)  macroLow  = htfRates[i].low;
   }

   double currentBid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double range = macroHigh - macroLow;
   if(range > 0)
   {
      zonePct = ((currentBid - macroLow) / range) * 100.0;
   }

   if(zonePct < 48.0)
   {
      zone = ZONE_DISCOUNT;
      zoneStr = StringFormat("DISCOUNT (%.1f%%) [BUY ONLY]", zonePct);
   }
   else if(zonePct > 52.0)
   {
      zone = ZONE_PREMIUM;
      zoneStr = StringFormat("PREMIUM (%.1f%%) [SELL ONLY]", zonePct);
   }
   else
   {
      zone = ZONE_EQUILIBRIUM;
      zoneStr = StringFormat("EQUILIBRIUM (%.1f%%) [FAIR]", zonePct);
   }
}

//+------------------------------------------------------------------+
//| 2. Institutional Liquidity Sweep Engine (PDH / PDL / Swings)     |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectMacroLiquiditySweep(bool &sweptBuy, bool &sweptSell)
{
   sweptBuy = false;
   sweptSell = false;

   // Check Previous Day High / Low (PDH / PDL)
   MqlRates d1Rates[];
   ArraySetAsSeries(d1Rates, true);
   if(CopyRates(m_symbol, PERIOD_D1, 1, 1, d1Rates) > 0)
   {
      double pdh = d1Rates[0].high;
      double pdl = d1Rates[0].low;

      MqlRates curRates[];
      ArraySetAsSeries(curRates, true);
      if(CopyRates(m_symbol, m_timeframe, 0, 5, curRates) >= 5)
      {
         // Bearish Liquidity Sweep (Turtle Soup over PDH):
         // Price spiked above PDH but recent completed candle closed back below PDH!
         if((curRates[0].high > pdh || curRates[1].high > pdh) && curRates[0].close < pdh)
         {
            sweptSell = true;
         }

         // Bullish Liquidity Sweep (Turtle Soup under PDL):
         // Price spiked below PDL but recent completed candle closed back above PDL!
         if((curRates[0].low < pdl || curRates[1].low < pdl) && curRates[0].close > pdl)
         {
            sweptBuy = true;
         }
      }
   }

   // Local Swing High / Low Sweep (Last 15 bars)
   MqlRates localRates[];
   ArraySetAsSeries(localRates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 15, localRates) >= 15)
   {
      double swingHigh = localRates[2].high;
      double swingLow  = localRates[2].low;
      for(int i = 3; i < 15; i++)
      {
         if(localRates[i].high > swingHigh) swingHigh = localRates[i].high;
         if(localRates[i].low  < swingLow)  swingLow  = localRates[i].low;
      }

      // Bar 1 swept swing high and rejected
      if(localRates[0].high > swingHigh && localRates[0].close < swingHigh && localRates[0].close < localRates[0].open)
      {
         sweptSell = true;
      }
      // Bar 1 swept swing low and rejected
      if(localRates[0].low < swingLow && localRates[0].close > swingLow && localRates[0].close > localRates[0].open)
      {
         sweptBuy = true;
      }
   }
}

//+------------------------------------------------------------------+
//| 3. Fair Value Gap (FVG / Imbalance) Detection                     |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectFairValueGap(bool &fvgBuy, bool &fvgSell)
{
   fvgBuy = false;
   fvgSell = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 5, rates) < 5) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   // Bullish FVG (Gap up: Bar 3 High is lower than Bar 1 Low)
   if(rates[3].high < rates[1].low)
   {
      double fvgTop    = rates[1].low;
      double fvgBottom = rates[3].high;
      // Current price is rebalancing inside or bouncing off the FVG
      if(bid >= fvgBottom && bid <= fvgTop)
      {
         fvgBuy = true;
      }
   }

   // Bearish FVG (Gap down: Bar 3 Low is higher than Bar 1 High)
   if(rates[3].low > rates[1].high)
   {
      double fvgTop    = rates[3].low;
      double fvgBottom = rates[1].high;
      // Current price is rebalancing inside or bouncing off the FVG
      if(ask >= fvgBottom && ask <= fvgTop)
      {
         fvgSell = true;
      }
   }
}

//+------------------------------------------------------------------+
//| 4. Top-Down Daily Bias (D1 Macro Context)                        |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::GetDailyBias(string &biasStr)
{
   biasStr = "NEUTRAL";
   MqlRates d1[];
   ArraySetAsSeries(d1, true);
   if(CopyRates(m_symbol, PERIOD_D1, 0, 2, d1) < 2) return;

   double currentPrice = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double dailyOpen = d1[0].open;
   double prevClose = d1[1].close;

   if(currentPrice > dailyOpen && currentPrice > prevClose)
      biasStr = "BULLISH EXPANSION";
   else if(currentPrice < dailyOpen && currentPrice < prevClose)
      biasStr = "BEARISH EXPANSION";
   else
      biasStr = "CONSOLIDATION";
}

//+------------------------------------------------------------------+
//| 5. Time & Price Session Killzones                                |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::GetSessionKillzone(string &kzStr, int &kzPts)
{
   datetime srvTime = TimeTradeServer();
   MqlDateTime dt;
   TimeToStruct(srvTime, dt);
   int hour = dt.hour;

   // London Killzone (approx 07:00 - 11:00 Server Time)
   if(hour >= 7 && hour < 11)
   {
      kzStr = "LONDON KILLZONE";
      kzPts = 10;
   }
   // New York Killzone (approx 12:00 - 17:00 Server Time)
   else if(hour >= 12 && hour < 17)
   {
      kzStr = "NEW YORK KILLZONE";
      kzPts = 10;
   }
   // Asian / Off-Hours
   else
   {
      kzStr = "OFF-HOURS";
      kzPts = 0;
   }
}

//+------------------------------------------------------------------+
//| Detect Current Market Regime                                     |
//+------------------------------------------------------------------+
ENUM_MARKET_REGIME CAlphaScoringEngine::DetectRegime()
{
   if(m_handleADX == INVALID_HANDLE || m_handleATR == INVALID_HANDLE)
   {
      m_telemetry.regime = REGIME_UNKNOWN;
      m_telemetry.regimeName = "CALIBRATING";
      return REGIME_UNKNOWN;
   }

   if(!SeriesInfoInteger(m_symbol, m_timeframe, SERIES_SYNCHRONIZED) ||
      !SeriesInfoInteger(m_symbol, m_htfTimeframe, SERIES_SYNCHRONIZED))
   {
      m_telemetry.regime = REGIME_UNKNOWN;
      m_telemetry.regimeName = "SYNCING";
      return REGIME_UNKNOWN;
   }

   datetime bar0 = iTime(m_symbol, m_timeframe, 0);
   if(bar0 <= 0)
   {
      m_telemetry.regime = REGIME_UNKNOWN;
      m_telemetry.regimeName = "AWAITING_BAR";
      return REGIME_UNKNOWN;
   }

   double adxBuf[1];
   if(CopyBuffer(m_handleADX, 0, 1, 1, adxBuf) <= 0) return REGIME_UNKNOWN;
   double adxVal = adxBuf[0];

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(m_handleATR, 0, 1, 10, atrBuf) < 10) return REGIME_UNKNOWN;
   double currentAtr = atrBuf[0];
   double avgAtr = 0;
   for(int i = 0; i < 10; i++) avgAtr += atrBuf[i];
   avgAtr /= 10.0;

   m_telemetry.adxValue = adxVal;
   m_telemetry.atrValue = currentAtr;
   m_telemetry.atrBaseline = avgAtr;

   // 1. Live Candle Volatility Shock
   MqlRates liveBar[1];
   if(CopyRates(m_symbol, m_timeframe, 0, 1, liveBar) > 0)
   {
      double liveCandleRange = liveBar[0].high - liveBar[0].low;
      if(avgAtr > 0 && (liveCandleRange / avgAtr) >= m_shockMultiplier)
      {
         m_telemetry.regime = REGIME_VOLATILITY_SHOCK;
         m_telemetry.regimeName = "REALTIME_SHOCK";
         return REGIME_VOLATILITY_SHOCK;
      }
   }

   // 2. Completed Bar Volatility Shock
   if(avgAtr > 0 && (currentAtr / avgAtr) >= m_shockMultiplier)
   {
      m_telemetry.regime = REGIME_VOLATILITY_SHOCK;
      m_telemetry.regimeName = "VOLATILITY_SHOCK";
      return REGIME_VOLATILITY_SHOCK;
   }

   // 3. Check Trend vs Chop based on ADX & HTF EMAs
   double ema20[1], ema50[1], ema200[1];
   if(CopyBuffer(m_handleEMA20, 0, 1, 1, ema20) > 0 &&
      CopyBuffer(m_handleEMA50, 0, 1, 1, ema50) > 0 &&
      CopyBuffer(m_handleEMA200, 0, 1, 1, ema200) > 0)
   {
      if(adxVal >= m_adxTrendLevel)
      {
         if(ema20[0] > ema50[0] && ema50[0] >= ema200[0])
         {
            m_telemetry.regime = REGIME_TREND_BULL;
            m_telemetry.regimeName = "TREND_BULL";
            return REGIME_TREND_BULL;
         }
         else if(ema20[0] < ema50[0] && ema50[0] <= ema200[0])
         {
            m_telemetry.regime = REGIME_TREND_BEAR;
            m_telemetry.regimeName = "TREND_BEAR";
            return REGIME_TREND_BEAR;
         }
      }
   }

   m_telemetry.regime = REGIME_CHOP_RANGE;
   m_telemetry.regimeName = "CHOP_RANGE";
   return REGIME_CHOP_RANGE;
}

//+------------------------------------------------------------------+
//| Calculate Squeeze Momentum & State                               |
//+------------------------------------------------------------------+
bool CAlphaScoringEngine::CalculateSqueeze(bool &sqzOn, double &sqzMomentum)
{
   sqzOn = false;
   sqzMomentum = 0.0;
   if(m_handleBB == INVALID_HANDLE || m_handleATR == INVALID_HANDLE) return false;

   double bbUpper[1], bbLower[1], bbMid[1];
   if(CopyBuffer(m_handleBB, BASE_LINE, 1, 1, bbMid) <= 0 ||
      CopyBuffer(m_handleBB, UPPER_BAND, 1, 1, bbUpper) <= 0 ||
      CopyBuffer(m_handleBB, LOWER_BAND, 1, 1, bbLower) <= 0)
      return false;

   double atrBuf[1];
   if(CopyBuffer(m_handleATR, 0, 1, 1, atrBuf) <= 0) return false;

   double kcUps = bbMid[0] + 1.5 * atrBuf[0];
   double kcLows = bbMid[0] - 1.5 * atrBuf[0];

   sqzOn = (bbUpper[0] < kcUps && bbLower[0] > kcLows);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 20, rates) < 20) return false;

   double highestHigh = rates[0].high;
   double lowestLow = rates[0].low;
   for(int i = 1; i < 20; i++)
   {
      if(rates[i].high > highestHigh) highestHigh = rates[i].high;
      if(rates[i].low < lowestLow) lowestLow = rates[i].low;
   }
   double donchianMid = (highestHigh + lowestLow) / 2.0;
   sqzMomentum = rates[0].close - ((donchianMid + bbMid[0]) / 2.0);

   m_telemetry.squeezeActive = sqzOn;
   return true;
}

//+------------------------------------------------------------------+
//| Detect LuxAlgo SMC Liquidity Sweep & Order Block Displacement   |
//+------------------------------------------------------------------+
bool CAlphaScoringEngine::DetectSMCSweep(bool &bullSweep, bool &bearSweep, double &obTop, double &obBottom)
{
   bullSweep = false;
   bearSweep = false;
   obTop = 0.0;
   obBottom = 0.0;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 10, rates) < 10) return false;

   double barRange = rates[0].high - rates[0].low;
   double barBody = MathAbs(rates[0].close - rates[0].open);
   if(barRange <= 0) return false;

   double bodyRatio = barBody / barRange;

   double prevHigh = rates[1].high;
   double prevLow  = rates[1].low;
   for(int i = 2; i <= 5; i++)
   {
      if(rates[i].high > prevHigh) prevHigh = rates[i].high;
      if(rates[i].low  < prevLow)  prevLow  = rates[i].low;
   }

   if(rates[0].low < prevLow && rates[0].close > rates[0].open && bodyRatio >= 0.55)
   {
      bullSweep = true;
      obBottom = rates[0].low;
      obTop = rates[0].open;
   }

   if(rates[0].high > prevHigh && rates[0].close < rates[0].open && bodyRatio >= 0.55)
   {
      bearSweep = true;
      obTop = rates[0].high;
      obBottom = rates[0].open;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Evaluate Institutional Macro Brain & Confluence Signals          |
//+------------------------------------------------------------------+
ENUM_ALPHA_SIGNAL CAlphaScoringEngine::EvaluateSignals(AlphaScoreTelemetry &telemetryOut)
{
   m_telemetry.totalScoreBuy = 0;
   m_telemetry.totalScoreSell = 0;
   m_telemetry.trendScore = 0;
   m_telemetry.zoneScore = 0;
   m_telemetry.structureScore = 0;
   m_telemetry.fvgSqueezeScore = 0;
   m_telemetry.rsiScore = 0;
   m_telemetry.killzoneScore = 0;

   ENUM_MARKET_REGIME regime = DetectRegime();

   // 1. Calculate Institutional Valuation Zone (50% Equilibrium Rule)
   double zonePct = 50.0;
   ENUM_MACRO_ZONE macroZone = ZONE_EQUILIBRIUM;
   string zoneStr = "";
   CalculateEquilibriumZone(zonePct, macroZone, zoneStr);
   m_telemetry.macroZone     = macroZone;
   m_telemetry.macroZoneName = zoneStr;
   m_telemetry.zonePct       = zonePct;

   // 2. Detect Liquidity Sweeps (Macro PDH/PDL + Local Swings)
   bool sweptBuy = false, sweptSell = false;
   DetectMacroLiquiditySweep(sweptBuy, sweptSell);
   m_telemetry.liquiditySweptBuy  = sweptBuy;
   m_telemetry.liquiditySweptSell = sweptSell;

   // 3. Detect Fair Value Gaps (FVG)
   bool fvgBuy = false, fvgSell = false;
   DetectFairValueGap(fvgBuy, fvgSell);
   m_telemetry.fvgMitigatedBuy  = fvgBuy;
   m_telemetry.fvgMitigatedSell = fvgSell;

   // 4. Daily Bias & Session Killzone
   string dailyBias = "";
   GetDailyBias(dailyBias);
   m_telemetry.dailyBias = dailyBias;

   string kzStr = "";
   int kzPts = 0;
   GetSessionKillzone(kzStr, kzPts);
   m_telemetry.killzone      = kzStr;
   m_telemetry.killzoneScore = kzPts;

   // Component 1: Higher Timeframe Trend Bias (Max 25 Points)
   double htfEma20[1], htfEma50[1], htfEma200[1];
   if(CopyBuffer(m_handleEMA20, 0, 1, 1, htfEma20) > 0 &&
      CopyBuffer(m_handleEMA50, 0, 1, 1, htfEma50) > 0 &&
      CopyBuffer(m_handleEMA200, 0, 1, 1, htfEma200) > 0)
   {
      if(htfEma20[0] > htfEma50[0])
      {
         int pts = 15;
         if(htfEma50[0] > htfEma200[0]) pts += 10; // 25 pts
         m_telemetry.totalScoreBuy += pts;
         m_telemetry.trendScore = pts;
      }
      else if(htfEma20[0] < htfEma50[0])
      {
         int pts = 15;
         if(htfEma50[0] < htfEma200[0]) pts += 10; // 25 pts
         m_telemetry.totalScoreSell += pts;
         m_telemetry.trendScore = pts;
      }
   }

   // Component 2: Institutional Valuation Zone (Max 20 Points)
   // Elite Rule: Reward buying in Discount (<50%) and selling in Premium (>50%)
   if(macroZone == ZONE_DISCOUNT)
   {
      m_telemetry.totalScoreBuy += 20;
      m_telemetry.zoneScore = 20;
   }
   else if(macroZone == ZONE_PREMIUM)
   {
      m_telemetry.totalScoreSell += 20;
      m_telemetry.zoneScore = 20;
   }
   else // Equilibrium
   {
      m_telemetry.totalScoreBuy += 10;
      m_telemetry.totalScoreSell += 10;
      m_telemetry.zoneScore = 10;
   }

   // Component 3: Market Structure & Liquidity Sweeps (Max 20 Points)
   bool bullSweep = false, bearSweep = false;
   double obTop = 0, obBottom = 0;
   DetectSMCSweep(bullSweep, bearSweep, obTop, obBottom);

   if(sweptBuy || bullSweep)
   {
      int pts = sweptBuy ? 20 : 15;
      m_telemetry.totalScoreBuy += pts;
      m_telemetry.structureScore = pts;
   }
   if(sweptSell || bearSweep)
   {
      int pts = sweptSell ? 20 : 15;
      m_telemetry.totalScoreSell += pts;
      if(m_telemetry.structureScore < pts) m_telemetry.structureScore = pts;
   }

   // Component 4: Fair Value Gap Imbalance & Squeeze Momentum (Max 15 Points)
   bool sqzOn = false;
   double sqzMom = 0.0;
   CalculateSqueeze(sqzOn, sqzMom);

   if(fvgBuy || (!sqzOn && sqzMom > 0))
   {
      int pts = (fvgBuy && !sqzOn) ? 15 : 10;
      m_telemetry.totalScoreBuy += pts;
      m_telemetry.fvgSqueezeScore = pts;
   }
   if(fvgSell || (!sqzOn && sqzMom < 0))
   {
      int pts = (fvgSell && !sqzOn) ? 15 : 10;
      m_telemetry.totalScoreSell += pts;
      if(m_telemetry.fvgSqueezeScore < pts) m_telemetry.fvgSqueezeScore = pts;
   }

   // Component 5: Multi-Timeframe RSI Volatility & Exhaustion (Max 10 Points)
   double rsiBuf[1];
   if(CopyBuffer(m_handleRSI, 0, 1, 1, rsiBuf) > 0)
   {
      double rsiVal = rsiBuf[0];
      m_telemetry.rsiValue = rsiVal;

      if(rsiVal >= 35.0 && rsiVal <= 58.0)
      {
         m_telemetry.totalScoreBuy += 10;
         m_telemetry.rsiScore = 10;
      }
      if(rsiVal >= 42.0 && rsiVal <= 65.0)
      {
         m_telemetry.totalScoreSell += 10;
         m_telemetry.rsiScore = 10;
      }
   }

   // Component 6: Session Killzone Confluence (Max 10 Points)
   m_telemetry.totalScoreBuy  += kzPts;
   m_telemetry.totalScoreSell += kzPts;

   // =================================================================
   // CRITICAL PRO-TRADER GATEKEEPERS (THE 50% EQUILIBRIUM RULE)
   // =================================================================
   // Elite Rule 1: NEVER BUY IN PREMIUM (Above 50% of Macro Range)!
   if(macroZone == ZONE_PREMIUM)
   {
      m_telemetry.totalScoreBuy = 0; // Strictly zero out BUY score in expensive zone!
   }

   // Elite Rule 2: NEVER SELL IN DISCOUNT (Below 50% of Macro Range)!
   if(macroZone == ZONE_DISCOUNT)
   {
      m_telemetry.totalScoreSell = 0; // Strictly zero out SELL score in cheap zone!
   }

   telemetryOut = m_telemetry;

   // Final Confluence Threshold (75/100) + Strict Regime & Valuation Alignment
   if(m_telemetry.totalScoreBuy >= m_scoreThreshold && m_telemetry.totalScoreBuy > m_telemetry.totalScoreSell && regime == REGIME_TREND_BULL)
   {
      return ALPHA_SIGNAL_BUY;
   }
   else if(m_telemetry.totalScoreSell >= m_scoreThreshold && m_telemetry.totalScoreSell > m_telemetry.totalScoreBuy && regime == REGIME_TREND_BEAR)
   {
      return ALPHA_SIGNAL_SELL;
   }

   return ALPHA_SIGNAL_NONE;
}

//+------------------------------------------------------------------+
//| Helper to convert regime to string                               |
//+------------------------------------------------------------------+
string CAlphaScoringEngine::GetRegimeString(ENUM_MARKET_REGIME regime)
{
   switch(regime)
   {
      case REGIME_TREND_BULL:       return "TREND BULL [Institutional]";
      case REGIME_TREND_BEAR:       return "TREND BEAR [Institutional]";
      case REGIME_CHOP_RANGE:       return "CHOP RANGE [Mean-Reversion]";
      case REGIME_VOLATILITY_SHOCK: return "VOLATILITY SHOCK [CIRCUIT LOCK]";
      default:                      return "CALIBRATING";
   }
}
