//+------------------------------------------------------------------+
//|                                                  DynamicGrid.mqh |
//|               QuantumTitan v10 Singularity Architecture          |
//|               Module 3: ATR Geometric Grid & Dynamic Rebalancer  |
//|               Beating Benchmark: Pionex Infinity Grid            |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "10.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Grid Order Data Structure
struct GridOrderInfo
{
   ulong    ticket;
   long     type;
   double   lots;
   double   openPrice;
   double   profit;
   datetime openTime;
};

//--- Grid Basket Telemetry
struct GridBasketTelemetry
{
   int      buyOrderCount;
   int      sellOrderCount;
   double   totalBuyLots;
   double   totalSellLots;
   double   avgBuyPrice;
   double   avgSellPrice;
   double   totalBuyProfit;
   double   totalSellProfit;
   double   freeMarginPct;
   bool     marginReserveLocked;
   double   currentGridStep;
};

//+------------------------------------------------------------------+
//| Class CDynamicGridEngine                                         |
//+------------------------------------------------------------------+
class CDynamicGridEngine
{
private:
   CTrade               m_trade;
   CPositionInfo        m_position;
   CSymbolInfo          m_symbolInfo;
   string               m_symbol;
   ulong                m_magic;

   // Grid Sizing & Spacing Parameters
   double               m_baseLot;              // Base lot size (e.g. 0.01)
   int                  m_maxOrdersPerSide;     // Maximum active grid orders (Default 4)
   double               m_stepAtrMultiplier;    // Multiplier for ATR step (Default 1.0)
   double               m_lotMultiplier;        // Geometric lot multiplier (Default 1.25)
   double               m_minMarginReservePct;  // Minimum Free Margin % to allow new orders (Default 60.0%)
   double               m_basketTpAtrMult;      // Target ATR profit for basket close (Default 0.8)

   // Pending Grid Layer Anchors (prevents geometric grid distortion on execution retries)
   bool                 m_pendingBuyActive;
   double               m_pendingBuyAnchorPrice;
   int                  m_pendingBuyLayerIndex;
   bool                 m_pendingSellActive;
   double               m_pendingSellAnchorPrice;
   int                  m_pendingSellLayerIndex;

   // Telemetry Cache
   GridBasketTelemetry  m_telemetry;

   // Internal Helpers
   void                 ScanBasket(GridOrderInfo &buyOrders[], int &buyCount, GridOrderInfo &sellOrders[], int &sellCount);
   double               NormalizeLot(double lot);
   double               CalculateGridLot(int orderIndex);

public:
                        CDynamicGridEngine();
                       ~CDynamicGridEngine();

   bool                 Init(string symbol, ulong magic, double baseLot = 0.01, int maxOrders = 4,
                             double stepAtrMult = 1.0, double lotMult = 1.25, double minMarginPct = 60.0);

   // Core Evaluation & Execution
   bool                 EvaluateGridStep(double currentAtr, bool allowBuy, bool allowSell);
   bool                 CheckAndCloseBasket(double currentAtr);
   bool                 CloseAllGridOrders(long filterType = -1);
   void                 SyncBasketTakeProfit(long filterType, double targetTp);

   // Telemetry
   GridBasketTelemetry  GetTelemetry() const { return m_telemetry; }
   bool                 IsMarginLocked() const { return m_telemetry.marginReserveLocked; }
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CDynamicGridEngine::CDynamicGridEngine()
   : m_symbol(""),
     m_magic(0),
     m_baseLot(0.01),
     m_maxOrdersPerSide(4),
     m_stepAtrMultiplier(1.0),
     m_lotMultiplier(1.25),
     m_minMarginReservePct(60.0),
     m_basketTpAtrMult(0.8),
     m_pendingBuyActive(false),
     m_pendingBuyAnchorPrice(0.0),
     m_pendingBuyLayerIndex(0),
     m_pendingSellActive(false),
     m_pendingSellAnchorPrice(0.0),
     m_pendingSellLayerIndex(0)
{
   ZeroMemory(m_telemetry);
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CDynamicGridEngine::~CDynamicGridEngine()
{
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
bool CDynamicGridEngine::Init(string symbol, ulong magic, double baseLot, int maxOrders,
                             double stepAtrMult, double lotMult, double minMarginPct)
{
   m_symbol = (symbol == "") ? _Symbol : symbol;
   m_magic = magic;
   m_baseLot = baseLot;
   m_maxOrdersPerSide = maxOrders;
   m_stepAtrMultiplier = stepAtrMult;
   m_lotMultiplier = lotMult;
   m_minMarginReservePct = minMarginPct;
   m_pendingBuyActive = false;
   m_pendingBuyAnchorPrice = 0.0;
   m_pendingBuyLayerIndex = 0;
   m_pendingSellActive = false;
   m_pendingSellAnchorPrice = 0.0;
   m_pendingSellLayerIndex = 0;

   if(!m_symbolInfo.Name(m_symbol))
   {
      PrintFormat("[DynamicGrid] ERROR: Cannot initialize symbol %s", m_symbol);
      return false;
   }

   m_trade.SetExpertMagicNumber(m_magic);
   m_trade.SetDeviationInPoints(20);

   // Dynamic Filling Mode Resolution
   uint filling = (uint)SymbolInfoInteger(m_symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   PrintFormat("[DynamicGrid] Initialized for %s (Magic: %d, MaxOrders: %d, ATRStep: %.2f, MinMargin: %.1f%%)",
      m_symbol, m_magic, m_maxOrdersPerSide, m_stepAtrMultiplier, m_minMarginReservePct);
   return true;
}

//+------------------------------------------------------------------+
//| Scan Active Basket of Grid Orders                                |
//+------------------------------------------------------------------+
void CDynamicGridEngine::ScanBasket(GridOrderInfo &buyOrders[], int &buyCount, GridOrderInfo &sellOrders[], int &sellCount)
{
   buyCount = 0;
   sellCount = 0;
   ArrayResize(buyOrders, 16);
   ArrayResize(sellOrders, 16);

   double totalBuyVol = 0, totalSellVol = 0;
   double sumBuyPriceVol = 0, sumSellPriceVol = 0;
   double totalBuyPnl = 0, totalSellPnl = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;

      ulong  ticket = m_position.Ticket();
      long   type   = m_position.PositionType();
      double volume = m_position.Volume();
      double price  = m_position.PriceOpen();
      double profit = m_position.Profit() + m_position.Swap();

      if(type == POSITION_TYPE_BUY)
      {
         if(buyCount < 16)
         {
            buyOrders[buyCount].ticket = ticket;
            buyOrders[buyCount].type = type;
            buyOrders[buyCount].lots = volume;
            buyOrders[buyCount].openPrice = price;
            buyOrders[buyCount].profit = profit;
            buyOrders[buyCount].openTime = (datetime)m_position.Time();
            buyCount++;
         }
         totalBuyVol += volume;
         sumBuyPriceVol += (price * volume);
         totalBuyPnl += profit;
      }
      else if(type == POSITION_TYPE_SELL)
      {
         if(sellCount < 16)
         {
            sellOrders[sellCount].ticket = ticket;
            sellOrders[sellCount].type = type;
            sellOrders[sellCount].lots = volume;
            sellOrders[sellCount].openPrice = price;
            sellOrders[sellCount].profit = profit;
            sellOrders[sellCount].openTime = (datetime)m_position.Time();
            sellCount++;
         }
         totalSellVol += volume;
         sumSellPriceVol += (price * volume);
         totalSellPnl += profit;
      }
   }

   // Update Telemetry
   m_telemetry.buyOrderCount   = buyCount;
   m_telemetry.sellOrderCount  = sellCount;
   m_telemetry.totalBuyLots    = totalBuyVol;
   m_telemetry.totalSellLots   = totalSellVol;
   m_telemetry.totalBuyProfit  = totalBuyPnl;
   m_telemetry.totalSellProfit = totalSellPnl;
   m_telemetry.avgBuyPrice     = (totalBuyVol > 0) ? (sumBuyPriceVol / totalBuyVol) : 0.0;
   m_telemetry.avgSellPrice    = (totalSellVol > 0) ? (sumSellPriceVol / totalSellVol) : 0.0;

   // Check Dynamic Cash Reserve
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   m_telemetry.freeMarginPct = (equity > 0) ? ((freeMargin / equity) * 100.0) : 100.0;
   m_telemetry.marginReserveLocked = (m_telemetry.freeMarginPct < m_minMarginReservePct);
}

//+------------------------------------------------------------------+
//| Institutional Lot Size Normalizer                                |
//+------------------------------------------------------------------+
double CDynamicGridEngine::NormalizeLot(double lot)
{
   double step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
   
   if(step > 0)
      lot = MathFloor((lot / step) + 1e-7) * step;
      
   int lotDigits = 2;
   if(step >= 1.0) lotDigits = 0;
   else if(step >= 0.1) lotDigits = 1;
   
   lot = NormalizeDouble(lot, lotDigits);
   return MathMax(minLot, MathMin(maxLot, lot));
}

//+------------------------------------------------------------------+
//| Calculate Next Grid Lot Size with Strict Step Normalization      |
//+------------------------------------------------------------------+
double CDynamicGridEngine::CalculateGridLot(int orderIndex)
{
   double step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   if(minLot <= 0) minLot = 0.01;

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   // MICRO ACCOUNT (<$100) MANDATORY PROTECTION:
   // On small accounts ($50), any lot escalation causes fatal margin lockout (exhausting the 60% reserve)
   // and turns normal market breathing into catastrophic drawdown.
   // All grid layers are strictly locked to minLot (0.01 flat) to guarantee free margin > 70%.
   if(currentEquity <= 100.0)
   {
      return NormalizeLot(minLot);
   }

   // Standard Account: Geometric with Arithmetic Fallback
   double rawLot = m_baseLot * MathPow(m_lotMultiplier, orderIndex);
   double lot = MathRound(rawLot / step) * step;

   if(orderIndex >= 1 && lot <= m_baseLot)
   {
      lot = m_baseLot + (step * orderIndex);
   }

   return NormalizeLot(lot);
}

//+------------------------------------------------------------------+
//| Evaluate Dynamic Grid Step & Place Next Layer                    |
//+------------------------------------------------------------------+
bool CDynamicGridEngine::EvaluateGridStep(double currentAtr, bool allowBuy, bool allowSell)
{
   if(!m_symbolInfo.RefreshRates()) return false;

   GridOrderInfo buyOrders[];
   GridOrderInfo sellOrders[];
   int buyCount = 0, sellCount = 0;
   ScanBasket(buyOrders, buyCount, sellOrders, sellCount);

   // Margin Circuit Lock: If Free Margin < 60%, strictly forbid opening new grid orders
   if(m_telemetry.marginReserveLocked)
   {
      return false;
   }

   double point = m_symbolInfo.Point();
   double bid   = m_symbolInfo.Bid();
   double ask   = m_symbolInfo.Ask();

   // Spread Guard: Never add grid layers when spread is excessive (> 25 points)
   double spreadPts = (point > 0.0) ? (ask - bid) / point : 0.0;
   if(spreadPts > 25.0) return false;

   double midPrice = (bid + ask) / 2.0;

   if(currentAtr <= 0) currentAtr = 100 * (point > 0.0 ? point : 0.0001);
   double gridStepDist = currentAtr * m_stepAtrMultiplier;
   m_telemetry.currentGridStep = gridStepDist;

   // Micro Account Safety: On equity <= $100, clamp max grid layers to 2 orders per side
   int effectiveMaxOrders = m_maxOrdersPerSide;
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity <= 100.0)
   {
      effectiveMaxOrders = MathMin(m_maxOrdersPerSide, 2);
   }

   // Reconcile pending anchors if basket count changed externally
   if(m_pendingBuyActive && (buyCount == 0 || buyCount >= effectiveMaxOrders || buyCount + 1 != m_pendingBuyLayerIndex))
   {
      m_pendingBuyActive = false;
      m_pendingBuyAnchorPrice = 0.0;
   }
   if(m_pendingSellActive && (sellCount == 0 || sellCount >= effectiveMaxOrders || sellCount + 1 != m_pendingSellLayerIndex))
   {
      m_pendingSellActive = false;
      m_pendingSellAnchorPrice = 0.0;
   }

   // 1. Evaluate BUY Grid (Normalized to Mid-Price and Anchored against Execution Drift)
   if(allowBuy && buyCount > 0 && buyCount < effectiveMaxOrders)
   {
      // Find lowest buy price
      double lowestBuy = buyOrders[0].openPrice;
      for(int i = 1; i < buyCount; i++)
      {
         if(buyOrders[i].openPrice < lowestBuy) lowestBuy = buyOrders[i].openPrice;
      }

      double targetAnchor = lowestBuy - gridStepDist;
      bool triggerLayer = false;

      if(m_pendingBuyActive && m_pendingBuyLayerIndex == buyCount + 1)
      {
         // Pending anchor exists: trigger if market is at or below anchor level
         if(midPrice <= m_pendingBuyAnchorPrice && (m_pendingBuyAnchorPrice - midPrice) <= 2.0 * gridStepDist)
            triggerLayer = true;
         else if((m_pendingBuyAnchorPrice - midPrice) > 2.0 * gridStepDist)
         {
            m_pendingBuyAnchorPrice = targetAnchor;
            triggerLayer = true;
         }
      }
      else if((lowestBuy - midPrice) >= gridStepDist)
      {
         m_pendingBuyActive = true;
         m_pendingBuyAnchorPrice = targetAnchor;
         m_pendingBuyLayerIndex = buyCount + 1;
         triggerLayer = true;
      }

      if(triggerLayer)
      {
         double nextLot = CalculateGridLot(buyCount);

         // PREDICTIVE MARGIN SIMULATION: Verify post-trade free margin >= m_minMarginReservePct
         double simulatedMargin = 0.0;
         if(OrderCalcMargin(ORDER_TYPE_BUY, m_symbol, nextLot, ask, simulatedMargin))
         {
            double equity = AccountInfoDouble(ACCOUNT_EQUITY);
            if(equity <= 0.0) return false;
            double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
            double projectedFreeMarginPct = ((freeMargin - simulatedMargin) / equity) * 100.0;

            if(projectedFreeMarginPct < m_minMarginReservePct)
            {
               PrintFormat("[DynamicGrid] PREDICTIVE MARGIN DEFICIT: Adding BUY %.2f lot requires $%.2f margin. Projected Free Margin: %.1f%% < %.1f%%. Layer blocked.",
                  nextLot, simulatedMargin, projectedFreeMarginPct, m_minMarginReservePct);
               return false;
            }
         }

         PrintFormat("[DynamicGrid] Executing BUY Grid #%d at Mid: %.5f (Anchor: %.5f, Lowest: %.5f, Lot: %.2f)",
            buyCount + 1, midPrice, m_pendingBuyAnchorPrice, lowestBuy, nextLot);

         // Institutional 3-Attempt Immediate Retry Loop
         for(int attempt = 1; attempt <= 3; attempt++)
         {
            ask = m_symbolInfo.Ask();
            if(m_trade.Buy(nextLot, m_symbol, ask, 0, 0, "QuantumTitan_Grid_Buy"))
            {
               m_pendingBuyActive = false;
               m_pendingBuyAnchorPrice = 0.0;
               return true;
            }
            uint retcode = m_trade.ResultRetcode();
            if(retcode == 10009 || retcode == 10008 || retcode == 10018)
            {
               PrintFormat("[DynamicGrid] Order returned retcode %d (%s). Aborting immediate retry to prevent duplicate ghost orders.",
                  retcode, m_trade.ResultComment());
               break;
            }
            Sleep(50);
            m_symbolInfo.RefreshRates();
         }
         PrintFormat("[DynamicGrid] WARNING: BUY Grid #%d failed 3 immediate attempts. Anchor retained at %.5f for next tick.",
            buyCount + 1, m_pendingBuyAnchorPrice);
      }
   }

   // 2. Evaluate SELL Grid (Normalized to Mid-Price and Anchored against Execution Drift)
   if(allowSell && sellCount > 0 && sellCount < effectiveMaxOrders)
   {
      // Find highest sell price
      double highestSell = sellOrders[0].openPrice;
      for(int i = 1; i < sellCount; i++)
      {
         if(sellOrders[i].openPrice > highestSell) highestSell = sellOrders[i].openPrice;
      }

      double targetAnchor = highestSell + gridStepDist;
      bool triggerLayer = false;

      if(m_pendingSellActive && m_pendingSellLayerIndex == sellCount + 1)
      {
         // Pending anchor exists: trigger if market is at or above anchor level
         if(midPrice >= m_pendingSellAnchorPrice && (midPrice - m_pendingSellAnchorPrice) <= 2.0 * gridStepDist)
            triggerLayer = true;
         else if((midPrice - m_pendingSellAnchorPrice) > 2.0 * gridStepDist)
         {
            m_pendingSellAnchorPrice = targetAnchor;
            triggerLayer = true;
         }
      }
      else if((midPrice - highestSell) >= gridStepDist)
      {
         m_pendingSellActive = true;
         m_pendingSellAnchorPrice = targetAnchor;
         m_pendingSellLayerIndex = sellCount + 1;
         triggerLayer = true;
      }

      if(triggerLayer)
      {
         double nextLot = CalculateGridLot(sellCount);

         // PREDICTIVE MARGIN SIMULATION: Verify post-trade free margin >= m_minMarginReservePct
         double simulatedMargin = 0.0;
         if(OrderCalcMargin(ORDER_TYPE_SELL, m_symbol, nextLot, bid, simulatedMargin))
         {
            double equity = AccountInfoDouble(ACCOUNT_EQUITY);
            if(equity <= 0.0) return false;
            double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
            double projectedFreeMarginPct = ((freeMargin - simulatedMargin) / equity) * 100.0;

            if(projectedFreeMarginPct < m_minMarginReservePct)
            {
               PrintFormat("[DynamicGrid] PREDICTIVE MARGIN DEFICIT: Adding SELL %.2f lot requires $%.2f margin. Projected Free Margin: %.1f%% < %.1f%%. Layer blocked.",
                  nextLot, simulatedMargin, projectedFreeMarginPct, m_minMarginReservePct);
               return false;
            }
         }

         PrintFormat("[DynamicGrid] Executing SELL Grid #%d at Mid: %.5f (Anchor: %.5f, Highest: %.5f, Lot: %.2f)",
            sellCount + 1, midPrice, m_pendingSellAnchorPrice, highestSell, nextLot);

         // Institutional 3-Attempt Immediate Retry Loop
         for(int attempt = 1; attempt <= 3; attempt++)
         {
            bid = m_symbolInfo.Bid();
            if(m_trade.Sell(nextLot, m_symbol, bid, 0, 0, "QuantumTitan_Grid_Sell"))
            {
               m_pendingSellActive = false;
               m_pendingSellAnchorPrice = 0.0;
               return true;
            }
            uint retcode = m_trade.ResultRetcode();
            if(retcode == 10009 || retcode == 10008 || retcode == 10018)
            {
               PrintFormat("[DynamicGrid] Order returned retcode %d (%s). Aborting immediate retry to prevent duplicate ghost orders.",
                  retcode, m_trade.ResultComment());
               break;
            }
            Sleep(50);
            m_symbolInfo.RefreshRates();
         }
         PrintFormat("[DynamicGrid] WARNING: SELL Grid #%d failed 3 immediate attempts. Anchor retained at %.5f for next tick.",
            sellCount + 1, m_pendingSellAnchorPrice);
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Dynamic Basket Take Profit (Pionex Infinity Dynamic Close)       |
//+------------------------------------------------------------------+
bool CDynamicGridEngine::CheckAndCloseBasket(double currentAtr)
{
   if(!m_symbolInfo.RefreshRates()) return false;

   GridOrderInfo buyOrders[];
   GridOrderInfo sellOrders[];
   int buyCount = 0, sellCount = 0;
   ScanBasket(buyOrders, buyCount, sellOrders, sellCount);

   double point = m_symbolInfo.Point();
   double bid   = m_symbolInfo.Bid();
   double ask   = m_symbolInfo.Ask();

   if(currentAtr <= 0) currentAtr = 100 * point;
   double targetProfitDist = currentAtr * m_basketTpAtrMult;

   bool closedAny = false;

   // 1. Check BUY Basket
   if(buyCount >= 2 && m_telemetry.avgBuyPrice > 0)
   {
      int digits = m_symbolInfo.Digits();
      double targetTp = NormalizeDouble(m_telemetry.avgBuyPrice + targetProfitDist, digits);
      
      // Proactively synchronize all basket order TakeProfits to hard limit on broker book (Zero Latency Execution)
      SyncBasketTakeProfit(POSITION_TYPE_BUY, targetTp);

      // Target: Bid has crossed above average buy price by targetProfitDist
      if((bid - m_telemetry.avgBuyPrice) >= targetProfitDist && m_telemetry.totalBuyProfit > 0)
      {
         PrintFormat("[DynamicGrid] BASKET REBALANCE: Closing %d BUY orders at +$%.2f profit (AvgPrice: %.5f, Bid: %.5f)",
            buyCount, m_telemetry.totalBuyProfit, m_telemetry.avgBuyPrice, bid);
         CloseAllGridOrders(POSITION_TYPE_BUY);
         closedAny = true;
      }
   }

   // 2. Check SELL Basket
   if(sellCount >= 2 && m_telemetry.avgSellPrice > 0)
   {
      int digits = m_symbolInfo.Digits();
      double targetTp = NormalizeDouble(m_telemetry.avgSellPrice - targetProfitDist, digits);

      // Proactively synchronize all basket order TakeProfits to hard limit on broker book (Zero Latency Execution)
      SyncBasketTakeProfit(POSITION_TYPE_SELL, targetTp);

      // Target: Ask has dropped below average sell price by targetProfitDist
      if((m_telemetry.avgSellPrice - ask) >= targetProfitDist && m_telemetry.totalSellProfit > 0)
      {
         PrintFormat("[DynamicGrid] BASKET REBALANCE: Closing %d SELL orders at +$%.2f profit (AvgPrice: %.5f, Ask: %.5f)",
            sellCount, m_telemetry.totalSellProfit, m_telemetry.avgSellPrice, ask);
         CloseAllGridOrders(POSITION_TYPE_SELL);
         closedAny = true;
      }
   }

   // 3. Emergency Protection on Micro Accounts (Equity <= $100)
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity <= 100.0)
   {
      // Single order protection: prevent lone position bleeding out (Max $3.00 loss = 6% risk)
      if(buyCount == 1 && m_telemetry.totalBuyProfit <= -3.00)
      {
         PrintFormat("[DynamicGrid] EMERGENCY DEFENSIVE CUT: 1 BUY order hit -$%.2f risk cap", MathAbs(m_telemetry.totalBuyProfit));
         CloseAllGridOrders(POSITION_TYPE_BUY);
         closedAny = true;
      }
      if(sellCount == 1 && m_telemetry.totalSellProfit <= -3.00)
      {
         PrintFormat("[DynamicGrid] EMERGENCY DEFENSIVE CUT: 1 SELL order hit -$%.2f risk cap", MathAbs(m_telemetry.totalSellProfit));
         CloseAllGridOrders(POSITION_TYPE_SELL);
         closedAny = true;
      }

      // Basket protection (Max $10.00 loss = 20% risk)
      if(buyCount >= 2 && m_telemetry.totalBuyProfit <= -10.0)
      {
         PrintFormat("[DynamicGrid] EMERGENCY BASKET CUT: Closing %d BUY orders at -$%.2f loss to protect capital",
            buyCount, MathAbs(m_telemetry.totalBuyProfit));
         CloseAllGridOrders(POSITION_TYPE_BUY);
         closedAny = true;
      }
      if(sellCount >= 2 && m_telemetry.totalSellProfit <= -10.0)
      {
         PrintFormat("[DynamicGrid] EMERGENCY BASKET CUT: Closing %d SELL orders at -$%.2f loss to protect capital",
            sellCount, MathAbs(m_telemetry.totalSellProfit));
         CloseAllGridOrders(POSITION_TYPE_SELL);
         closedAny = true;
      }
   }

   return closedAny;
}

//+------------------------------------------------------------------+
//| Close All Grid Orders in Basket                                  |
//+------------------------------------------------------------------+
bool CDynamicGridEngine::CloseAllGridOrders(long filterType)
{
   bool allClosed = true;
   const int maxRetries = 3;

   for(int attempt = 1; attempt <= maxRetries; attempt++)
   {
      int remaining = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(!m_position.SelectByIndex(i)) continue;
         if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;

         long posType = m_position.PositionType();
         if(filterType == -1 || posType == filterType)
         {
            if(!m_trade.PositionClose(m_position.Ticket()))
            {
               remaining++;
               PrintFormat("[DynamicGrid] Attempt %d: Failed to close #%I64u (Retcode: %u). Retrying...",
                  attempt, m_position.Ticket(), m_trade.ResultRetcode());
            }
         }
      }

      if(remaining == 0)
      {
         allClosed = true;
         break;
      }
      else
      {
         allClosed = false;
         if(attempt < maxRetries)
         {
            Sleep(100);
            m_symbolInfo.RefreshRates();
         }
      }
   }

   return allClosed;
}

//+------------------------------------------------------------------+
//| Synchronize All Basket Orders to a Unified Hard TakeProfit Price |
//+------------------------------------------------------------------+
void CDynamicGridEngine::SyncBasketTakeProfit(long filterType, double targetTp)
{
   if(targetTp <= 0.0) return;
   double point = m_symbolInfo.Point();
   if(point <= 0.0) point = 0.0001;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;
      if(m_position.PositionType() != filterType) continue;

      double curTp = m_position.TakeProfit();
      if(MathAbs(curTp - targetTp) > (2.0 * point))
      {
         m_trade.PositionModify(m_position.Ticket(), m_position.StopLoss(), targetTp);
      }
   }
}
