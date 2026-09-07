//+------------------------------------------------------------------+
//|                                              TrailingSafety.mqh  |
//|               QuantumTitan v9+++ Singularity Architecture         |
//|               Module 2: Dynamic Trailing & Reversal Safety        |
//|               Beating Benchmark: 3Commas TTP & Trailing Buy       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Trailing State Tracking Struct per Position
struct PositionTrailingState
{
   ulong    ticket;
   long     positionType;
   double   openPrice;
   double   peakPrice;           // Highest price reached for BUY, Lowest for SELL
   double   currentSL;
   double   currentTP;
   bool     breakEvenSecured;
   bool     trailingActive;
   datetime openTime;
};

//--- Trailing Buy / Safety Order Monitoring Struct
struct TrailingSafetyState
{
   bool     isActive;
   long     orderType;           // POSITION_TYPE_BUY or POSITION_TYPE_SELL
   double   targetTriggerPrice;  // Price level where safety order armed
   double   extremePrice;        // Lowest price reached during drop (for BUY)
   double   reversalBouncePoints;// Required bounce from bottom
   datetime armedTime;
   int      safetyOrderIndex;    // 1st, 2nd, 3rd safety order
   double   suggestedLot;
};

//+------------------------------------------------------------------+
//| Class CTrailingSafetyEngine                                      |
//+------------------------------------------------------------------+
class CTrailingSafetyEngine
{
private:
   CTrade               m_trade;
   CPositionInfo        m_position;
   CSymbolInfo          m_symbolInfo;
   string               m_symbol;
   ulong                m_magic;

   // Trailing Parameters
   double               m_beTriggerR;       // Breakeven trigger in R-multiple (e.g. 0.4R)
   double               m_trailTriggerR;    // Trailing trigger in R-multiple (e.g. 1.2R)
   double               m_atrMultiplier;    // ATR multiplier for trailing step (e.g. 0.5 - 0.75)
   bool                 m_useAdaptiveTTP;   // 3Commas Trailing Take Profit Adaptive Mode
   int                  m_safetyTimeoutSec; // Trailing safety order expiration in seconds (default 4 hours)

   // Active Trailing Positions Cache (Max 32 concurrent positions)
   PositionTrailingState m_positions[32];
   int                  m_positionCount;

   // Trailing Buy / Safety Order Manager
   TrailingSafetyState  m_safetyState;

   // Internal Helpers
   int                  FindPositionIndex(ulong ticket);
   void                 PruneClosedPositions();

public:
                        CTrailingSafetyEngine();
                       ~CTrailingSafetyEngine();

   bool                 Init(string symbol, ulong magic, double beR = 0.4, double trailR = 1.2, double atrMult = 0.6);
   
   // Core Execution Logic
   void                 UpdateTrailing(double currentAtr);
   
   // 3Commas Trailing Buy / Reversal Logic
   void                 ArmTrailingSafetyOrder(long posType, double triggerPrice, double bouncePoints, int safetyIndex, double lot);
   bool                 CheckTrailingSafetyTrigger(double currentBid, double currentAsk, double &execLot);
   void                 CancelTrailingSafety();

   // Getters & Status
   bool                 IsSafetyArmed() const { return m_safetyState.isActive; }
   int                  GetTrackedPositionCount() const { return m_positionCount; }
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CTrailingSafetyEngine::CTrailingSafetyEngine()
   : m_symbol(""),
     m_magic(0),
     m_beTriggerR(0.4),
     m_trailTriggerR(1.2),
     m_atrMultiplier(0.6),
     m_useAdaptiveTTP(true),
     m_safetyTimeoutSec(14400),
     m_positionCount(0)
{
   ZeroMemory(m_positions);
   ZeroMemory(m_safetyState);
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CTrailingSafetyEngine::~CTrailingSafetyEngine()
{
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
bool CTrailingSafetyEngine::Init(string symbol, ulong magic, double beR, double trailR, double atrMult)
{
   m_symbol = (symbol == "") ? _Symbol : symbol;
   m_magic = magic;
   m_beTriggerR = beR;
   m_trailTriggerR = trailR;
   m_atrMultiplier = atrMult;
   m_safetyTimeoutSec = 14400; // 4 Hours expiration

   if(!m_symbolInfo.Name(m_symbol))
   {
      PrintFormat("[TrailingSafety] ERROR: Cannot initialize symbol %s", m_symbol);
      return false;
   }

   m_trade.SetExpertMagicNumber(m_magic);
   m_trade.SetDeviationInPoints(20);

   PrintFormat("[TrailingSafety] Initialized for %s (Magic: %d, BE: %.1fR, Trail: %.1fR, ATRMult: %.2f)",
      m_symbol, m_magic, m_beTriggerR, m_trailTriggerR, m_atrMultiplier);
   return true;
}

//+------------------------------------------------------------------+
//| Find Position Index in Cache                                     |
//+------------------------------------------------------------------+
int CTrailingSafetyEngine::FindPositionIndex(ulong ticket)
{
   for(int i = 0; i < m_positionCount; i++)
   {
      if(m_positions[i].ticket == ticket) return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Prune Closed Positions from Cache                                |
//+------------------------------------------------------------------+
void CTrailingSafetyEngine::PruneClosedPositions()
{
   int validCount = 0;
   PositionTrailingState temp[32];

   for(int i = 0; i < m_positionCount; i++)
   {
      if(m_position.SelectByTicket(m_positions[i].ticket))
      {
         temp[validCount++] = m_positions[i];
      }
   }

   m_positionCount = validCount;
   for(int i = 0; i < 32; i++)
   {
      if(i < validCount) m_positions[i] = temp[i];
      else ZeroMemory(m_positions[i]);
   }
}

//+------------------------------------------------------------------+
//| Core Trailing & Breakeven Engine (3Commas TTP Adaptive)          |
//+------------------------------------------------------------------+
void CTrailingSafetyEngine::UpdateTrailing(double currentAtr)
{
   if(!m_symbolInfo.RefreshRates()) return;
   PruneClosedPositions();

   double point = m_symbolInfo.Point();
   int digits   = m_symbolInfo.Digits();
   double bid   = m_symbolInfo.Bid();
   double ask   = m_symbolInfo.Ask();

   if(currentAtr <= 0) currentAtr = 100 * point;

   double trailingStep = currentAtr * m_atrMultiplier;

   long stopLevel   = SymbolInfoInteger(m_symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevel = SymbolInfoInteger(m_symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double minDistance = MathMax(stopLevel, freezeLevel) * point + (2 * point);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;

      ulong ticket     = m_position.Ticket();
      long  type       = m_position.PositionType();
      double openPrice = m_position.PriceOpen();
      double currentSL = m_position.StopLoss();
      double currentTP = m_position.TakeProfit();

      // Register or retrieve from cache
      int idx = FindPositionIndex(ticket);
      if(idx < 0)
      {
         if(m_positionCount < 32)
         {
            idx = m_positionCount++;
            m_positions[idx].ticket = ticket;
            m_positions[idx].positionType = type;
            m_positions[idx].openPrice = openPrice;
            m_positions[idx].peakPrice = (type == POSITION_TYPE_BUY) ? bid : ask;
            m_positions[idx].currentSL = currentSL;
            m_positions[idx].currentTP = currentTP;
            m_positions[idx].breakEvenSecured = false;
            m_positions[idx].trailingActive = false;
            m_positions[idx].openTime = (datetime)m_position.Time();
         }
         else continue; // Cache full
      }

      // Compute initial risk distance R (Distance from Open to initial SL)
      double riskDistance = 0.0;
      if(currentSL > 0) riskDistance = MathAbs(openPrice - currentSL);
      if(riskDistance <= 0) riskDistance = currentAtr * 1.5; // Default fallback to 1.5 ATR

      // Update Peak Price (Highest high for BUY, Lowest low for SELL)
      if(type == POSITION_TYPE_BUY)
      {
         if(bid > m_positions[idx].peakPrice) m_positions[idx].peakPrice = bid;
         double profitDistance = bid - openPrice;

         // 1. Breakeven Security (at 0.4R)
         if(!m_positions[idx].breakEvenSecured && profitDistance >= (riskDistance * m_beTriggerR))
         {
            double beSL = NormalizeDouble(openPrice + (2 * point), digits);
            if(beSL > currentSL && (bid - beSL) >= minDistance)
            {
               if(m_trade.PositionModify(ticket, beSL, currentTP))
               {
                  m_positions[idx].breakEvenSecured = true;
                  m_positions[idx].currentSL = beSL;
                  PrintFormat("[TrailingSafety] Ticket #%I64u: Breakeven LOCKED at %.5f (+%.1fR)", ticket, beSL, m_beTriggerR);
               }
            }
         }

         // 2. Dynamic Trailing Take Profit (TTP) - Surpassing 3Commas
         if(profitDistance >= (riskDistance * m_trailTriggerR))
         {
            m_positions[idx].trailingActive = true;
            // Trail behind peak price by dynamic ATR distance
            double targetSL = NormalizeDouble(m_positions[idx].peakPrice - trailingStep, digits);
            
            // Ensure targetSL is above open price, strictly higher than existing SL, and outside stop level
            if(targetSL > openPrice && targetSL > currentSL + (5 * point) && (bid - targetSL) >= minDistance)
            {
               if(m_trade.PositionModify(ticket, targetSL, currentTP))
               {
                  m_positions[idx].currentSL = targetSL;
                  PrintFormat("[TrailingSafety] Ticket #%I64u: TTP Dynamic Trail SL raised to %.5f (Peak: %.5f)",
                     ticket, targetSL, m_positions[idx].peakPrice);
               }
            }
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         if(ask < m_positions[idx].peakPrice || m_positions[idx].peakPrice == 0) m_positions[idx].peakPrice = ask;
         double profitDistance = openPrice - ask;

         // 1. Breakeven Security (at 0.4R)
         if(!m_positions[idx].breakEvenSecured && profitDistance >= (riskDistance * m_beTriggerR))
         {
            double beSL = NormalizeDouble(openPrice - (2 * point), digits);
            if((currentSL == 0 || beSL < currentSL) && (beSL - ask) >= minDistance)
            {
               if(m_trade.PositionModify(ticket, beSL, currentTP))
               {
                  m_positions[idx].breakEvenSecured = true;
                  m_positions[idx].currentSL = beSL;
                  PrintFormat("[TrailingSafety] Ticket #%I64u: Breakeven LOCKED at %.5f (+%.1fR)", ticket, beSL, m_beTriggerR);
               }
            }
         }

         // 2. Dynamic Trailing Take Profit (TTP) - Surpassing 3Commas
         if(profitDistance >= (riskDistance * m_trailTriggerR))
         {
            m_positions[idx].trailingActive = true;
            // Trail above peak price by dynamic ATR distance
            double targetSL = NormalizeDouble(m_positions[idx].peakPrice + trailingStep, digits);
            
            // Ensure targetSL is below open price, strictly lower than existing SL, and outside stop level
            if(targetSL < openPrice && (currentSL == 0 || targetSL < currentSL - (5 * point)) && (targetSL - ask) >= minDistance)
            {
               if(m_trade.PositionModify(ticket, targetSL, currentTP))
               {
                  m_positions[idx].currentSL = targetSL;
                  PrintFormat("[TrailingSafety] Ticket #%I64u: TTP Dynamic Trail SL lowered to %.5f (Peak: %.5f)",
                     ticket, targetSL, m_positions[idx].peakPrice);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Arm Trailing Buy / Reversal Safety Order (3Commas Benchmark)     |
//+------------------------------------------------------------------+
void CTrailingSafetyEngine::ArmTrailingSafetyOrder(long posType, double triggerPrice, double bouncePoints, int safetyIndex, double lot)
{
   m_safetyState.isActive = true;
   m_safetyState.orderType = posType;
   m_safetyState.targetTriggerPrice = triggerPrice;
   m_safetyState.extremePrice = triggerPrice;
   m_safetyState.reversalBouncePoints = bouncePoints;
   m_safetyState.armedTime = TimeCurrent();
   m_safetyState.safetyOrderIndex = safetyIndex;
   m_safetyState.suggestedLot = lot;

   PrintFormat("[TrailingSafety] ARMED Trailing Safety #%d (%s) at Trigger: %.5f, BounceReq: %.1f pts, Lot: %.2f",
      safetyIndex, (posType == POSITION_TYPE_BUY ? "BUY" : "SELL"), triggerPrice, bouncePoints, lot);
}

//+------------------------------------------------------------------+
//| Check Trailing Safety Reversal Trigger (No Falling Knife)        |
//+------------------------------------------------------------------+
bool CTrailingSafetyEngine::CheckTrailingSafetyTrigger(double currentBid, double currentAsk, double &execLot)
{
   if(!m_safetyState.isActive) return false;

   // Expiration check
   if(m_safetyTimeoutSec > 0 && (TimeCurrent() - m_safetyState.armedTime) > m_safetyTimeoutSec)
   {
      PrintFormat("[TrailingSafety] Safety order #%d EXPIRED after %d seconds.",
         m_safetyState.safetyOrderIndex, m_safetyTimeoutSec);
      m_safetyState.isActive = false;
      return false;
   }

   double point = m_symbolInfo.Point();
   execLot = m_safetyState.suggestedLot;

   if(m_safetyState.orderType == POSITION_TYPE_BUY)
   {
      // Track lowest dip
      if(currentAsk < m_safetyState.extremePrice)
      {
         m_safetyState.extremePrice = currentAsk;
      }

      // Reversal confirmation: price bounced from lowest dip by required bounce points
      double bounce = (currentAsk - m_safetyState.extremePrice) / point;
      if(bounce >= m_safetyState.reversalBouncePoints)
      {
         PrintFormat("[TrailingSafety] TRAILING BUY TRIGGERED: Extreme: %.5f, CurrentAsk: %.5f, Bounce: %.1f pts",
            m_safetyState.extremePrice, currentAsk, bounce);
         m_safetyState.isActive = false; // Disarm after trigger
         return true;
      }
   }
   else if(m_safetyState.orderType == POSITION_TYPE_SELL)
   {
      // Track highest peak
      if(currentBid > m_safetyState.extremePrice)
      {
         m_safetyState.extremePrice = currentBid;
      }

      // Reversal confirmation: price bounced down from peak by required bounce points
      double bounce = (m_safetyState.extremePrice - currentBid) / point;
      if(bounce >= m_safetyState.reversalBouncePoints)
      {
         PrintFormat("[TrailingSafety] TRAILING SELL TRIGGERED: Extreme: %.5f, CurrentBid: %.5f, Bounce: %.1f pts",
            m_safetyState.extremePrice, currentBid, bounce);
         m_safetyState.isActive = false; // Disarm after trigger
         return true;
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Cancel Trailing Safety Order                                     |
//+------------------------------------------------------------------+
void CTrailingSafetyEngine::CancelTrailingSafety()
{
   if(m_safetyState.isActive)
   {
      PrintFormat("[TrailingSafety] Trailing Safety #%d Cancelled/Disarmed.", m_safetyState.safetyOrderIndex);
      m_safetyState.isActive = false;
   }
}
