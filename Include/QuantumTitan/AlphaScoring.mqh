//+------------------------------------------------------------------+
//|                                                AlphaScoring.mqh  |
//|               QuantumTitan v9+++ Singularity Architecture         |
//|               Module 1: Market Regime & Confluence Scoring       |
//|               Beating Benchmark: Cryptohopper Strategy Designer  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"

//--- Market Regime Enumeration
enum ENUM_MARKET_REGIME
{
   REGIME_UNKNOWN          = 0,
   REGIME_TREND_BULL       = 1, // Strong Uptrend (ADX > 25, EMA20 > EMA50 > EMA200)
   REGIME_TREND_BEAR       = 2, // Strong Downtrend (ADX > 25, EMA20 < EMA50 < EMA200)
   REGIME_CHOP_RANGE       = 3, // Low Volatility / Consolidation (ADX < 20, Squeeze ON)
   REGIME_VOLATILITY_SHOCK = 4  // Extreme Volatility / News Spike (ATR > 2.5x Normal)
};

//--- Signal Type Enumeration
enum ENUM_ALPHA_SIGNAL
{
   ALPHA_SIGNAL_NONE = 0,
   ALPHA_SIGNAL_BUY  = 1,
   ALPHA_SIGNAL_SELL = 2
};

//--- Score Breakdown Struct for Telemetry & HUD
struct AlphaScoreTelemetry
{
   ENUM_MARKET_REGIME regime;
   int                totalScoreBuy;
   int                totalScoreSell;
   int                trendScore;      // Max 30
   int                smcScore;        // Max 25
   int                squeezeScore;    // Max 25
   int                rsiScore;        // Max 20
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

   // Internal Calculation Helpers
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

   // 1. HTF Trend EMAs (H1)
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

   PrintFormat("[AlphaScoring] Initialized successfully for %s (TF: %d, HTF: %d)", m_symbol, m_timeframe, m_htfTimeframe);
   return true;
}

//+------------------------------------------------------------------+
//| Detect Current Market Regime                                     |
//+------------------------------------------------------------------+
ENUM_MARKET_REGIME CAlphaScoringEngine::DetectRegime()
{
   if(m_handleADX == INVALID_HANDLE || m_handleATR == INVALID_HANDLE) return REGIME_UNKNOWN;

   double adxBuf[1];
   if(CopyBuffer(m_handleADX, 0, 1, 1, adxBuf) <= 0) return REGIME_UNKNOWN;
   double adxVal = adxBuf[0];

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(m_handleATR, 0, 1, 10, atrBuf) < 10) return REGIME_UNKNOWN;
   double currentAtr = atrBuf[0]; // Bar 1 (most recent completed bar)
   double avgAtr = 0;
   for(int i = 0; i < 10; i++) avgAtr += atrBuf[i];
   avgAtr /= 10.0;

   m_telemetry.adxValue = adxVal;
   m_telemetry.atrValue = currentAtr;
   m_telemetry.atrBaseline = avgAtr;

   // 1. Check for Real-Time Live Candle Volatility Shock (Bar 0 - Zero Lag)
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

   // 2. Check for Completed Bar Volatility Shock (Bar 1)
   if(avgAtr > 0 && (currentAtr / avgAtr) >= m_shockMultiplier)
   {
      m_telemetry.regime = REGIME_VOLATILITY_SHOCK;
      m_telemetry.regimeName = "VOLATILITY_SHOCK";
      return REGIME_VOLATILITY_SHOCK;
   }

   // 2. Check Trend vs Chop based on ADX & HTF EMAs
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

   // 3. If ADX < Chop level or in transition
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

   // Keltner Channels (20 SMA +/- 1.5 * ATR)
   double kcUps = bbMid[0] + 1.5 * atrBuf[0];
   double kcLows = bbMid[0] - 1.5 * atrBuf[0];

   // Squeeze ON: Bollinger Bands inside Keltner Channels (Volatility contraction)
   if(bbUpper[0] < kcUps && bbLower[0] > kcLows)
   {
      sqzOn = true;
   }
   else
   {
      sqzOn = false; // Squeeze Release (Explosion ready)
   }

   // Momentum: Close vs average of (Highest High + Lowest Low)/2 + SMA
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
   double delta = rates[0].close - ((donchianMid + bbMid[0]) / 2.0);
   sqzMomentum = delta;

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

   // Bar 1 is the displacement candle
   double barRange = rates[0].high - rates[0].low;
   double barBody = MathAbs(rates[0].close - rates[0].open);
   if(barRange <= 0) return false;

   double bodyRatio = barBody / barRange;

   // Check liquidity sweep over previous 5 bars
   double prevHigh = rates[1].high;
   double prevLow  = rates[1].low;
   for(int i = 2; i <= 5; i++)
   {
      if(rates[i].high > prevHigh) prevHigh = rates[i].high;
      if(rates[i].low  < prevLow)  prevLow  = rates[i].low;
   }

   // Bullish Sweep: Price dipped below prevLow but closed bullish with strong displacement
   if(rates[0].low < prevLow && rates[0].close > rates[0].open && bodyRatio >= 0.55)
   {
      bullSweep = true;
      obBottom = rates[0].low;
      obTop = rates[0].open;
   }

   // Bearish Sweep: Price spiked above prevHigh but closed bearish with strong displacement
   if(rates[0].high > prevHigh && rates[0].close < rates[0].open && bodyRatio >= 0.55)
   {
      bearSweep = true;
      obTop = rates[0].high;
      obBottom = rates[0].open;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Evaluate 100-Point Confluence Scoring System                     |
//+------------------------------------------------------------------+
ENUM_ALPHA_SIGNAL CAlphaScoringEngine::EvaluateSignals(AlphaScoreTelemetry &telemetryOut)
{
   // Reset scores
   m_telemetry.totalScoreBuy = 0;
   m_telemetry.totalScoreSell = 0;
   m_telemetry.trendScore = 0;
   m_telemetry.smcScore = 0;
   m_telemetry.squeezeScore = 0;
   m_telemetry.rsiScore = 0;

   ENUM_MARKET_REGIME regime = DetectRegime();

   // CRITICAL GATE 1: Circuit breaker on Volatility Shock
   if(regime == REGIME_VOLATILITY_SHOCK)
   {
      telemetryOut = m_telemetry;
      return ALPHA_SIGNAL_NONE; // Absolute pause during black swan / shock
   }

   // Component 1: Higher Timeframe Trend Bias (Max 30 Points)
   double htfEma20[1], htfEma50[1], htfEma200[1];
   if(CopyBuffer(m_handleEMA20, 0, 1, 1, htfEma20) > 0 &&
      CopyBuffer(m_handleEMA50, 0, 1, 1, htfEma50) > 0 &&
      CopyBuffer(m_handleEMA200, 0, 1, 1, htfEma200) > 0)
   {
      if(htfEma20[0] > htfEma50[0])
      {
         int pts = 20;
         if(htfEma50[0] > htfEma200[0]) pts += 10; // Full bull alignment (30 pts)
         m_telemetry.totalScoreBuy += pts;
         m_telemetry.trendScore = pts;
      }
      else if(htfEma20[0] < htfEma50[0])
      {
         int pts = 20;
         if(htfEma50[0] < htfEma200[0]) pts += 10; // Full bear alignment (30 pts)
         m_telemetry.totalScoreSell += pts;
         m_telemetry.trendScore = pts;
      }
   }

   // Component 2: LuxAlgo SMC Order Block Sweep (Max 25 Points)
   bool bullSweep = false, bearSweep = false;
   double obTop = 0, obBottom = 0;
   if(DetectSMCSweep(bullSweep, bearSweep, obTop, obBottom))
   {
      if(bullSweep)
      {
         m_telemetry.totalScoreBuy += 25;
         m_telemetry.smcScore = 25;
      }
      else if(bearSweep)
      {
         m_telemetry.totalScoreSell += 25;
         m_telemetry.smcScore = 25;
      }
   }

   // Component 3: LazyBear Squeeze Momentum Release (Max 25 Points)
   bool sqzOn = false;
   double sqzMom = 0.0;
   if(CalculateSqueeze(sqzOn, sqzMom))
   {
      if(!sqzOn) // Squeeze is released (Momentum explosion)
      {
         if(sqzMom > 0)
         {
            m_telemetry.totalScoreBuy += 25;
            m_telemetry.squeezeScore = 25;
         }
         else if(sqzMom < 0)
         {
            m_telemetry.totalScoreSell += 25;
            m_telemetry.squeezeScore = 25;
         }
      }
      else
      {
         // Inside squeeze - award partial points if momentum is clearly directional
         if(sqzMom > 0) m_telemetry.totalScoreBuy += 10;
         else if(sqzMom < 0) m_telemetry.totalScoreSell += 10;
         m_telemetry.squeezeScore = 10;
      }
   }

   // Component 4: Multi-Timeframe RSI Volatility & Exhaustion (Max 20 Points)
   double rsiBuf[1];
   if(CopyBuffer(m_handleRSI, 0, 1, 1, rsiBuf) > 0)
   {
      double rsiVal = rsiBuf[0];
      m_telemetry.rsiValue = rsiVal;

      // Buy condition: RSI healthy pull-back (35 - 58), not overbought (>65)
      if(rsiVal >= 35.0 && rsiVal <= 58.0)
      {
         m_telemetry.totalScoreBuy += 20;
         m_telemetry.rsiScore = 20;
      }
      else if(rsiVal > 58.0 && rsiVal <= 65.0)
      {
         m_telemetry.totalScoreBuy += 10;
         m_telemetry.rsiScore = 10;
      }

      // Sell condition: RSI healthy rally (42 - 65), not oversold (<35)
      if(rsiVal >= 42.0 && rsiVal <= 65.0)
      {
         m_telemetry.totalScoreSell += 20;
         if(m_telemetry.rsiScore < 20) m_telemetry.rsiScore = 20;
      }
      else if(rsiVal >= 35.0 && rsiVal < 42.0)
      {
         m_telemetry.totalScoreSell += 10;
         if(m_telemetry.rsiScore < 10) m_telemetry.rsiScore = 10;
      }
   }

   telemetryOut = m_telemetry;

   // Final Signal Decision based on 75-point Confluence Threshold
   if(m_telemetry.totalScoreBuy >= m_scoreThreshold && m_telemetry.totalScoreBuy > m_telemetry.totalScoreSell)
   {
      return ALPHA_SIGNAL_BUY;
   }
   else if(m_telemetry.totalScoreSell >= m_scoreThreshold && m_telemetry.totalScoreSell > m_telemetry.totalScoreBuy)
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
