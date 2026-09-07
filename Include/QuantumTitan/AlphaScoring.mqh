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
   string             dailyBias;        // "BULLISH EXPANSION", "BEARISH EXPANSION", "CONSOLIDATION"
   string             killzone;         // "LONDON KILLZONE", "NEW YORK KILLZONE", "OFF-HOURS"
   
   // Institutional SMC & Price Action Telemetry
   bool               liquiditySweptBuy;
   bool               liquiditySweptSell;
   bool               fvgMitigatedBuy;
   bool               fvgMitigatedSell;
   bool               nestledObBuy;
   bool               nestledObSell;
   bool               hiddenBaseBuy;
   bool               hiddenBaseSell;
   bool               wickClearedBuy;
   bool               wickClearedSell;
   bool               htfWickFillBuy;
   bool               htfWickFillSell;
   bool               failedPaTrapBuy;
   bool               failedPaTrapSell;
   bool               bosConfirmedBuy;
   bool               bosConfirmedBear;
   bool               chochConfirmedBuy;
   bool               chochConfirmedBear;
   bool               idmSweptBuy;
   bool               idmSweptSell;
   bool               vbcConfirmedBuy;
   bool               vbcConfirmedSell;
   bool               srFlipBuy;
   bool               srFlipSell;
   bool               candleAbsorbBuy;
   bool               candleAbsorbSell;

   int                totalScoreBuy;
   int                totalScoreSell;
   int                trendScore;       // Max 20
   int                zoneScore;        // Max 15 (Equilibrium & Fibo 61.8%)
   int                obBaseScore;      // Max 15 (Nestled OB & Hidden Base)
   int                fvgScore;         // Max 15 (Stateful FVG & CE 50%)
   int                sweepIdmScore;    // Max 15 (Liquidity Sweeps & IDM Purge)
   int                wickScore;        // Max 10 (Wick Clearance & HTF Wick-Fill)
   int                vbcSrScore;       // Max 5  (VBC >600 pts & S/R Flip)
   int                killzoneScore;    // Max 5  (Peak Session Confluence)
   
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
   int                m_handleEMA14;
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
   void               DetectNestledOrderBlock(bool &obBuy, bool &obSell, double &obTop, double &obBottom);
   void               DetectStatefulFVG(bool &fvgBuy, bool &fvgSell, double &cePrice);
   void               DetectHiddenBaseFibo(bool &baseBuy, bool &baseSell, double &fiboLevel);
   void               DetectCandleAbsorption(bool &bullAbsorb, bool &bearAbsorb);
   void               DetectWickClearance(bool &buyWickCleared, bool &sellWickCleared);
   void               DetectHTFWickFill(bool &wickFillBuy, bool &wickFillSell, double &fillTarget);
   void               DetectFailedPATrap(bool &trapBuy, bool &trapSell);
   void               DetectMarketStructureShift(bool &bosBull, bool &bosBear, bool &chochBull, bool &chochBear);
   void               DetectInducementSweep(bool &idmSweptBuy, bool &idmSweptSell);
   void               DetectVolumeBreakConfirm(bool &vbcBuy, bool &vbcSell, double minRangePoints);
   void               DetectSRFlip(bool &srFlipBuy, bool &srFlipSell);
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
     m_handleEMA14(INVALID_HANDLE),
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
   if(m_handleEMA14 != INVALID_HANDLE)  { IndicatorRelease(m_handleEMA14);  m_handleEMA14 = INVALID_HANDLE; }
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

   // 1. Momentum & Trend EMAs
   m_handleEMA14  = iMA(m_symbol, m_timeframe, 14, 0, MODE_EMA, PRICE_CLOSE);
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

   if(m_handleEMA14 == INVALID_HANDLE || m_handleEMA20 == INVALID_HANDLE || 
      m_handleEMA50 == INVALID_HANDLE || m_handleEMA200 == INVALID_HANDLE ||
      m_handleADX == INVALID_HANDLE || m_handleATR == INVALID_HANDLE || 
      m_handleRSI == INVALID_HANDLE || m_handleBB == INVALID_HANDLE)
   {
      PrintFormat("[AlphaScoring] ERROR: Failed to create indicator handles for %s. Error: %d", m_symbol, GetLastError());
      return false;
   }

   AlphaScoreTelemetry initTelem;
   EvaluateSignals(initTelem);

   PrintFormat("[AlphaScoring] Institutional Macro Brain v14 initialized for %s (TF: %d, HTF: %d)", m_symbol, m_timeframe, m_htfTimeframe);
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

void CAlphaScoringEngine::DetectFairValueGap(bool &fvgBuy, bool &fvgSell)
{
   double cePrice = 0.0;
   DetectStatefulFVG(fvgBuy, fvgSell, cePrice);
}

//+------------------------------------------------------------------+
//| 3.1 Nestled Order Block (NOB) Detection (PDF 1, Pages 1, 3, 4)   |
//| Solitary candle nestled before displacement                      |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectNestledOrderBlock(bool &obBuy, bool &obSell, double &obTop, double &obBottom)
{
   obBuy = false;
   obSell = false;
   obTop = 0.0;
   obBottom = 0.0;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 15, rates) < 15) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   for(int i = 3; i <= 10; i++)
   {
      // Nestled Demand OB (Buy)
      if(!obBuy && rates[i].close < rates[i].open)
      {
         bool isDisplacement = (rates[i-1].close > rates[i-1].open) && 
                               (rates[i-2].close > rates[i-2].open) &&
                               (rates[i-2].close > rates[i].high);
         if(isDisplacement)
         {
            double zoneTop = rates[i].high;
            double zoneBtm = rates[i].low;
            if(bid >= zoneBtm && bid <= (zoneTop + (zoneTop - zoneBtm) * 0.35))
            {
               obBuy = true;
               obTop = zoneTop;
               obBottom = zoneBtm;
            }
         }
      }

      // Nestled Supply OB (Sell)
      if(!obSell && rates[i].close > rates[i].open)
      {
         bool isDisplacement = (rates[i-1].close < rates[i-1].open) && 
                               (rates[i-2].close < rates[i-2].open) &&
                               (rates[i-2].close < rates[i].low);
         if(isDisplacement)
         {
            double zoneTop = rates[i].high;
            double zoneBtm = rates[i].low;
            if(ask <= zoneTop && ask >= (zoneBtm - (zoneTop - zoneBtm) * 0.35))
            {
               obSell = true;
               obTop = zoneTop;
               obBottom = zoneBtm;
            }
         }
      }
      if(obBuy && obSell) break;
   }
}

//+------------------------------------------------------------------+
//| 3.2 Stateful FVG & Consequent Encroachment (CE 50%) (PDF 1, P. 5)|
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectStatefulFVG(bool &fvgBuy, bool &fvgSell, double &cePrice)
{
   fvgBuy = false;
   fvgSell = false;
   cePrice = 0.0;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 10, rates) < 10) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   for(int i = 1; i <= 6; i++)
   {
      // Bullish FVG
      if(!fvgBuy && rates[i+2].high < rates[i].low)
      {
         double fvgTop = rates[i].low;
         double fvgBtm = rates[i+2].high;
         double ce     = (fvgTop + fvgBtm) * 0.5;
         if(bid >= fvgBtm && bid <= fvgTop)
         {
            fvgBuy = true;
            cePrice = ce;
         }
      }

      // Bearish FVG
      if(!fvgSell && rates[i+2].low > rates[i].high)
      {
         double fvgTop = rates[i+2].low;
         double fvgBtm = rates[i].high;
         double ce     = (fvgTop + fvgBtm) * 0.5;
         if(ask >= fvgBtm && ask <= fvgTop)
         {
            fvgSell = true;
            cePrice = ce;
         }
      }
      if(fvgBuy && fvgSell) break;
   }
}

//+------------------------------------------------------------------+
//| 3.3 Hidden Base & Fibonacci Matrix (PDF 1, Page 5, 6, 13, 14)    |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectHiddenBaseFibo(bool &baseBuy, bool &baseSell, double &fiboLevel)
{
   baseBuy = false;
   baseSell = false;
   fiboLevel = 0.0;

   MqlRates htfRates[];
   ArraySetAsSeries(htfRates, true);
   if(CopyRates(m_symbol, m_htfTimeframe, 0, 30, htfRates) < 30) return;

   double macroHigh = htfRates[0].high;
   double macroLow  = htfRates[0].low;
   int highIdx = 0, lowIdx = 0;
   for(int i = 1; i < 30; i++)
   {
      if(htfRates[i].high > macroHigh) { macroHigh = htfRates[i].high; highIdx = i; }
      if(htfRates[i].low  < macroLow)  { macroLow  = htfRates[i].low;  lowIdx  = i; }
   }

   double range = macroHigh - macroLow;
   if(range <= 0) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   if(lowIdx > highIdx) // Uptrend leg
   {
      double fibo50 = macroHigh - 0.500 * range;
      double fibo61 = macroHigh - 0.618 * range;
      if(bid >= fibo61 && bid <= (fibo50 + 0.10 * range))
      {
         for(int k = 1; k < 15; k++)
         {
            double kRange = htfRates[k].high - htfRates[k].low;
            double kBody  = MathAbs(htfRates[k].close - htfRates[k].open);
            if(kRange > 0 && (kBody / kRange) < 0.35)
            {
               if(MathAbs(htfRates[k].close - fibo50) <= (0.15 * range))
               {
                  baseBuy = true;
                  fiboLevel = 61.8;
                  break;
               }
            }
         }
      }
   }
   else if(highIdx > lowIdx) // Downtrend leg
   {
      double fibo50 = macroLow + 0.500 * range;
      double fibo61 = macroLow + 0.618 * range;
      if(ask <= fibo61 && ask >= (fibo50 - 0.10 * range))
      {
         for(int k = 1; k < 15; k++)
         {
            double kRange = htfRates[k].high - htfRates[k].low;
            double kBody  = MathAbs(htfRates[k].close - htfRates[k].open);
            if(kRange > 0 && (kBody / kRange) < 0.35)
            {
               if(MathAbs(htfRates[k].close - fibo50) <= (0.15 * range))
               {
                  baseSell = true;
                  fiboLevel = 61.8;
                  break;
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| 3.4 Continuous Candlestick Trend Absorption (PDF 1, Page 10, 11) |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectCandleAbsorption(bool &bullAbsorb, bool &bearAbsorb)
{
   bullAbsorb = false;
   bearAbsorb = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 4, rates) < 4) return;

   // Bullish Absorption
   if(rates[2].close > rates[2].open &&
      rates[1].close < rates[1].open &&
      rates[0].close > rates[0].open &&
      rates[0].close >= rates[1].high)
   {
      bullAbsorb = true;
   }

   // Bearish Absorption
   if(rates[2].close < rates[2].open &&
      rates[1].close > rates[1].open &&
      rates[0].close < rates[0].open &&
      rates[0].close <= rates[1].low)
   {
      bearAbsorb = true;
   }
}

//+------------------------------------------------------------------+
//| 3.5 Wick Clearance ("การเคลียร์ไส้") (PDF 1, Page 11, 12)         |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectWickClearance(bool &buyWickCleared, bool &sellWickCleared)
{
   buyWickCleared = false;
   sellWickCleared = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 4, rates) < 4) return;

   double b1Range = rates[1].high - rates[1].low;
   if(rates[2].close > rates[2].open && rates[1].low < rates[2].low && b1Range > 0)
   {
      if((rates[1].close - rates[1].low) / b1Range >= 0.50)
      {
         buyWickCleared = true;
      }
   }

   if(rates[2].close < rates[2].open && rates[1].high > rates[2].high && b1Range > 0)
   {
      if((rates[1].high - rates[1].close) / b1Range >= 0.50)
      {
         sellWickCleared = true;
      }
   }
}

//+------------------------------------------------------------------+
//| 3.6 HTF Wick-Fill Zone (PDF 2, Page 4, 8, 12, 13)                |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectHTFWickFill(bool &wickFillBuy, bool &wickFillSell, double &fillTarget)
{
   wickFillBuy = false;
   wickFillSell = false;
   fillTarget = 0.0;

   MqlRates htfRates[];
   ArraySetAsSeries(htfRates, true);
   if(CopyRates(m_symbol, m_htfTimeframe, 0, 6, htfRates) < 6) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   for(int i = 1; i <= 2; i++)
   {
      double r = htfRates[i].high - htfRates[i].low;
      if(r <= 0) continue;

      double upperWick = htfRates[i].high - MathMax(htfRates[i].open, htfRates[i].close);
      double lowerWick = MathMin(htfRates[i].open, htfRates[i].close) - htfRates[i].low;

      if(!wickFillBuy && upperWick >= (r * 0.45))
      {
         if(bid >= MathMax(htfRates[i].open, htfRates[i].close) && bid < htfRates[i].high)
         {
            wickFillBuy = true;
            fillTarget = htfRates[i].high;
         }
      }

      if(!wickFillSell && lowerWick >= (r * 0.45))
      {
         if(ask <= MathMin(htfRates[i].open, htfRates[i].close) && ask > htfRates[i].low)
         {
            wickFillSell = true;
            fillTarget = htfRates[i].low;
         }
      }
      if(wickFillBuy && wickFillSell) break;
   }
}

//+------------------------------------------------------------------+
//| 3.7 Price Action Trap / Failed PA Reversal (PDF 1, Page 16-18)   |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectFailedPATrap(bool &trapBuy, bool &trapSell)
{
   trapBuy = false;
   trapSell = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 4, rates) < 4) return;

   // Failed Bullish PA -> Sell Trap
   if(rates[2].close > rates[2].open && rates[1].close < rates[1].open &&
      rates[1].close < rates[2].low && rates[1].open >= rates[2].close)
   {
      trapSell = true;
   }

   // Failed Bearish PA -> Buy Trap
   if(rates[2].close < rates[2].open && rates[1].close > rates[1].open &&
      rates[1].close > rates[2].high && rates[1].open <= rates[2].close)
   {
      trapBuy = true;
   }
}

//+------------------------------------------------------------------+
//| 3.8 Market Structure Shift (BOS & CHoCH) (PDF 1, Page 6, 7, 8, 9)|
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectMarketStructureShift(bool &bosBull, bool &bosBear, bool &chochBull, bool &chochBear)
{
   bosBull = false;
   bosBear = false;
   chochBull = false;
   chochBear = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 1, 20, rates) < 20) return;

   double highestHigh = rates[3].high;
   double lowestLow   = rates[3].low;
   int hhIdx = 3, llIdx = 3;

   for(int i = 4; i < 18; i++)
   {
      if(rates[i].high > highestHigh) { highestHigh = rates[i].high; hhIdx = i; }
      if(rates[i].low  < lowestLow)   { lowestLow   = rates[i].low;  llIdx = i; }
   }

   if(rates[0].close > highestHigh && rates[0].open <= highestHigh)
   {
      bosBull = true;
      if(llIdx < hhIdx) chochBull = true;
   }

   if(rates[0].close < lowestLow && rates[0].open >= lowestLow)
   {
      bosBear = true;
      if(hhIdx < llIdx) chochBear = true;
   }
}

//+------------------------------------------------------------------+
//| 3.9 Inducement (IDM) Liquidity Sweeper (PDF 1, Page 22, 23, 24)  |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectInducementSweep(bool &idmSweptBuy, bool &idmSweptSell)
{
   idmSweptBuy = false;
   idmSweptSell = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 10, rates) < 10) return;

   double idmLow = rates[4].low;
   double idmHigh = rates[4].high;

   if(rates[1].low < idmLow && rates[0].close > idmLow)
   {
      idmSweptBuy = true;
   }

   if(rates[1].high > idmHigh && rates[0].close < idmHigh)
   {
      idmSweptSell = true;
   }
}

//+------------------------------------------------------------------+
//| 3.10 Volume Break Confirm (VBC >600 pts) (PDF 2, Page 14, 15)    |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectVolumeBreakConfirm(bool &vbcBuy, bool &vbcSell, double minRangePoints = 600.0)
{
   vbcBuy = false;
   vbcSell = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 5, rates) < 5) return;

   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   if(point <= 0) return;

   for(int i = 1; i <= 2; i++)
   {
      double r = (rates[i].high - rates[i].low) / point;
      double b = MathAbs(rates[i].close - rates[i].open) / point;
      if(r >= minRangePoints && (b / r) >= 0.65)
      {
         if(rates[i].close > rates[i].open)
         {
            if(rates[0].low <= rates[i].close && rates[0].close >= rates[i].open)
            {
               vbcBuy = true;
            }
         }
         else if(rates[i].close < rates[i].open)
         {
            if(rates[0].high >= rates[i].close && rates[0].close <= rates[i].open)
            {
               vbcSell = true;
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| 3.11 S/R Flip True Breakout (PDF 2, Page 3, 5, 6)                |
//+------------------------------------------------------------------+
void CAlphaScoringEngine::DetectSRFlip(bool &srFlipBuy, bool &srFlipSell)
{
   srFlipBuy = false;
   srFlipSell = false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(m_symbol, m_timeframe, 0, 15, rates) < 15) return;

   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);

   double resLevel = rates[5].high;
   double supLevel = rates[5].low;
   for(int i = 6; i < 15; i++)
   {
      if(rates[i].high > resLevel) resLevel = rates[i].high;
      if(rates[i].low  < supLevel) supLevel = rates[i].low;
   }

   if(rates[2].close > resLevel && rates[1].low <= resLevel && bid >= resLevel)
   {
      srFlipBuy = true;
   }

   if(rates[2].close < supLevel && rates[1].high >= supLevel && ask <= supLevel)
   {
      srFlipSell = true;
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
   m_telemetry.totalScoreBuy  = 0;
   m_telemetry.totalScoreSell = 0;
   m_telemetry.trendScore     = 0;
   m_telemetry.zoneScore      = 0;
   m_telemetry.obBaseScore    = 0;
   m_telemetry.fvgScore       = 0;
   m_telemetry.sweepIdmScore  = 0;
   m_telemetry.wickScore      = 0;
   m_telemetry.vbcSrScore     = 0;
   m_telemetry.killzoneScore  = 0;

   ENUM_MARKET_REGIME regime = DetectRegime();

   // 1. Calculate Institutional Valuation Zone (50% Equilibrium Rule)
   double zonePct = 50.0;
   ENUM_MACRO_ZONE macroZone = ZONE_EQUILIBRIUM;
   string zoneStr = "";
   CalculateEquilibriumZone(zonePct, macroZone, zoneStr);
   m_telemetry.macroZone     = macroZone;
   m_telemetry.macroZoneName = zoneStr;
   m_telemetry.zonePct       = zonePct;

   // 2. Detect Macro Sweeps & Inducement (IDM) & Failed PA Trap
   bool sweptBuy = false, sweptSell = false;
   DetectMacroLiquiditySweep(sweptBuy, sweptSell);
   m_telemetry.liquiditySweptBuy  = sweptBuy;
   m_telemetry.liquiditySweptSell = sweptSell;

   bool idmBuy = false, idmSell = false;
   DetectInducementSweep(idmBuy, idmSell);
   m_telemetry.idmSweptBuy  = idmBuy;
   m_telemetry.idmSweptSell = idmSell;

   bool failedPaBuy = false, failedPaSell = false;
   DetectFailedPATrap(failedPaBuy, failedPaSell);
   m_telemetry.failedPaTrapBuy  = failedPaBuy;
   m_telemetry.failedPaTrapSell = failedPaSell;

   // 3. Detect Nestled Order Block (แท่งโดดๆ) & Hidden Base Fibo
   bool nestledBuy = false, nestledSell = false;
   double obTop = 0.0, obBottom = 0.0;
   DetectNestledOrderBlock(nestledBuy, nestledSell, obTop, obBottom);
   m_telemetry.nestledObBuy  = nestledBuy;
   m_telemetry.nestledObSell = nestledSell;

   bool hiddenBaseBuy = false, hiddenBaseSell = false;
   double baseFibo = 0.0;
   DetectHiddenBaseFibo(hiddenBaseBuy, hiddenBaseSell, baseFibo);
   m_telemetry.hiddenBaseBuy  = hiddenBaseBuy;
   m_telemetry.hiddenBaseSell = hiddenBaseSell;

   // 4. Detect Stateful FVG & Consequent Encroachment (CE 50%)
   bool fvgStateBuy = false, fvgStateSell = false;
   double ceLevel = 0.0;
   DetectStatefulFVG(fvgStateBuy, fvgStateSell, ceLevel);
   m_telemetry.fvgMitigatedBuy  = fvgStateBuy;
   m_telemetry.fvgMitigatedSell = fvgStateSell;

   // 5. Candle Absorption & Wick Clearance & HTF Wick-Fill
   bool absorbBuy = false, absorbSell = false;
   DetectCandleAbsorption(absorbBuy, absorbSell);
   m_telemetry.candleAbsorbBuy  = absorbBuy;
   m_telemetry.candleAbsorbSell = absorbSell;

   bool wickClearBuy = false, wickClearSell = false;
   DetectWickClearance(wickClearBuy, wickClearSell);
   m_telemetry.wickClearedBuy  = wickClearBuy;
   m_telemetry.wickClearedSell = wickClearSell;

   bool htfWickBuy = false, htfWickSell = false;
   double wickMedian = 0.0;
   DetectHTFWickFill(htfWickBuy, htfWickSell, wickMedian);
   m_telemetry.htfWickFillBuy  = htfWickBuy;
   m_telemetry.htfWickFillSell = htfWickSell;

   // 6. Market Structure Shift (BOS / CHoCH)
   bool bosBuy = false, chochBuy = false, bosBear = false, chochBear = false;
   DetectMarketStructureShift(bosBuy, chochBuy, bosBear, chochBear);
   m_telemetry.bosConfirmedBuy    = bosBuy;
   m_telemetry.chochConfirmedBuy  = chochBuy;
   m_telemetry.bosConfirmedBear   = bosBear;
   m_telemetry.chochConfirmedBear = chochBear;

   // 7. Volume Break Confirm (VBC > 600 pts) & S/R Flip
   bool vbcBuy = false, vbcSell = false;
   DetectVolumeBreakConfirm(vbcBuy, vbcSell);
   m_telemetry.vbcConfirmedBuy  = vbcBuy;
   m_telemetry.vbcConfirmedSell = vbcSell;

   bool srFlipBuy = false, srFlipSell = false;
   DetectSRFlip(srFlipBuy, srFlipSell);
   m_telemetry.srFlipBuy  = srFlipBuy;
   m_telemetry.srFlipSell = srFlipSell;

   // 8. Daily Bias & Session Killzone
   string dailyBias = "";
   GetDailyBias(dailyBias);
   m_telemetry.dailyBias = dailyBias;

   string kzStr = "";
   int kzPts = 0;
   GetSessionKillzone(kzStr, kzPts);
   m_telemetry.killzone      = kzStr;
   int finalKzPts = (kzPts > 0) ? 5 : 0;
   m_telemetry.killzoneScore = finalKzPts;

   // =================================================================
   // 8 CONFLUENCE FACTOR SCORING ENGINE (100 TOTAL POINTS)
   // =================================================================
   
   // Factor 1: Higher Timeframe Trend & EMA Alignment (Max 20 Points)
   double htfEma20[1], htfEma50[1], htfEma200[1];
   int trendBuyPts = 0, trendSellPts = 0;
   if(CopyBuffer(m_handleEMA20, 0, 1, 1, htfEma20) > 0 &&
      CopyBuffer(m_handleEMA50, 0, 1, 1, htfEma50) > 0 &&
      CopyBuffer(m_handleEMA200, 0, 1, 1, htfEma200) > 0)
   {
      if(htfEma20[0] > htfEma50[0])
      {
         trendBuyPts = 12;
         if(htfEma50[0] > htfEma200[0]) trendBuyPts += 8; // 20 pts
      }
      else if(htfEma20[0] < htfEma50[0])
      {
         trendSellPts = 12;
         if(htfEma50[0] < htfEma200[0]) trendSellPts += 8; // 20 pts
      }
   }
   m_telemetry.trendScore = MathMax(trendBuyPts, trendSellPts);
   m_telemetry.totalScoreBuy  += trendBuyPts;
   m_telemetry.totalScoreSell += trendSellPts;

   // Factor 2: Institutional Valuation Zone (Max 15 Points)
   int zoneBuyPts = 0, zoneSellPts = 0;
   if(macroZone == ZONE_DISCOUNT)
   {
      zoneBuyPts = 15;
   }
   else if(macroZone == ZONE_PREMIUM)
   {
      zoneSellPts = 15;
   }
   else // Equilibrium
   {
      zoneBuyPts  = 8;
      zoneSellPts = 8;
   }
   m_telemetry.zoneScore = MathMax(zoneBuyPts, zoneSellPts);
   m_telemetry.totalScoreBuy  += zoneBuyPts;
   m_telemetry.totalScoreSell += zoneSellPts;

   // Factor 3: Nestled Order Block & Hidden Base (Max 15 Points)
   int obBaseBuyPts = 0, obBaseSellPts = 0;
   if(nestledBuy)     obBaseBuyPts += 10;
   if(hiddenBaseBuy)  obBaseBuyPts += 5;
   if(nestledSell)    obBaseSellPts += 10;
   if(hiddenBaseSell) obBaseSellPts += 5;
   obBaseBuyPts  = MathMin(obBaseBuyPts, 15);
   obBaseSellPts = MathMin(obBaseSellPts, 15);
   m_telemetry.obBaseScore = MathMax(obBaseBuyPts, obBaseSellPts);
   m_telemetry.totalScoreBuy  += obBaseBuyPts;
   m_telemetry.totalScoreSell += obBaseSellPts;

   // Factor 4: Stateful FVG & Consequent Encroachment (Max 15 Points)
   int fvgBuyPts = 0, fvgSellPts = 0;
   if(fvgStateBuy)  fvgBuyPts  = 15;
   if(fvgStateSell) fvgSellPts = 15;
   m_telemetry.fvgScore = MathMax(fvgBuyPts, fvgSellPts);
   m_telemetry.totalScoreBuy  += fvgBuyPts;
   m_telemetry.totalScoreSell += fvgSellPts;

   // Factor 5: Liquidity Sweeps, IDM Purge & Failed PA Trap (Max 15 Points)
   int sweepBuyPts = 0, sweepSellPts = 0;
   if(sweptBuy)    sweepBuyPts += 8;
   if(idmBuy)      sweepBuyPts += 4;
   if(failedPaBuy) sweepBuyPts += 3;
   if(sweptSell)   sweepSellPts += 8;
   if(idmSell)     sweepSellPts += 4;
   if(failedPaSell)sweepSellPts += 3;
   sweepBuyPts  = MathMin(sweepBuyPts, 15);
   sweepSellPts = MathMin(sweepSellPts, 15);
   m_telemetry.sweepIdmScore = MathMax(sweepBuyPts, sweepSellPts);
   m_telemetry.totalScoreBuy  += sweepBuyPts;
   m_telemetry.totalScoreSell += sweepSellPts;

   // Factor 6: Wick Clearance, Candle Absorption & HTF Wick-Fill (Max 10 Points)
   int wickBuyPts = 0, wickSellPts = 0;
   if(wickClearBuy) wickBuyPts += 4;
   if(absorbBuy)    wickBuyPts += 3;
   if(htfWickBuy)   wickBuyPts += 3;
   if(wickClearSell) wickSellPts += 4;
   if(absorbSell)   wickSellPts += 3;
   if(htfWickSell)  wickSellPts += 3;
   wickBuyPts  = MathMin(wickBuyPts, 10);
   wickSellPts = MathMin(wickSellPts, 10);
   m_telemetry.wickScore = MathMax(wickBuyPts, wickSellPts);
   m_telemetry.totalScoreBuy  += wickBuyPts;
   m_telemetry.totalScoreSell += wickSellPts;

   // Factor 7: VBC Displacement (>600 pts) & S/R Flip (Max 5 Points)
   int vbcSrBuyPts = 0, vbcSrSellPts = 0;
   if(vbcBuy || srFlipBuy)    vbcSrBuyPts = 5;
   if(vbcSell || srFlipSell)  vbcSrSellPts = 5;
   m_telemetry.vbcSrScore = MathMax(vbcSrBuyPts, vbcSrSellPts);
   m_telemetry.totalScoreBuy  += vbcSrBuyPts;
   m_telemetry.totalScoreSell += vbcSrSellPts;

   // Factor 8: Session Killzone Confluence (Max 5 Points)
   m_telemetry.totalScoreBuy  += finalKzPts;
   m_telemetry.totalScoreSell += finalKzPts;

   // =================================================================
   // CRITICAL PRO-TRADER GATEKEEPERS (THE 50% EQUILIBRIUM RULE)
   // =================================================================
   // Inviolable Rule 1: NEVER BUY IN PREMIUM (Above 52% of Macro Range)!
   if(macroZone == ZONE_PREMIUM)
   {
      m_telemetry.totalScoreBuy = 0; // Strictly zero out BUY score in expensive zone!
   }

   // Inviolable Rule 2: NEVER SELL IN DISCOUNT (Below 48% of Macro Range)!
   if(macroZone == ZONE_DISCOUNT)
   {
      m_telemetry.totalScoreSell = 0; // Strictly zero out SELL score in cheap zone!
   }

   // Optional RSI Volatility Telemetry
   double rsiBuf[1];
   if(CopyBuffer(m_handleRSI, 0, 1, 1, rsiBuf) > 0)
   {
      m_telemetry.rsiValue = rsiBuf[0];
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
