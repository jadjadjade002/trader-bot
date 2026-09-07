//+------------------------------------------------------------------+
//|                                                  DynamicGrid.mqh |
//|               QuantumTitan v9+++ Singularity Architecture         |
//|               Module 3: ATR Geometric Grid & Dynamic Rebalancer  |
//|               Beating Benchmark: Pionex Infinity Grid            |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"

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

   // Telemetry Cache
   GridBasketTelemetry  m_telemetry;

   // Internal Helpers
   void                 ScanBasket(GridOrderInfo &buyOrders[], int &buyCount, GridOrderInfo &sellOrders[], int &sellCount);
   double               NormalizeLot(double lot);

public:
                        CDynamicGridEngine();
                       ~CDynamicGridEngine();

   bool                 Init(string symbol, ulong magic, double baseLot = 0.01, int maxOrders = 4,
                             double stepAtrMult = 1.0, double lotMult = 1.25, double minMarginPct = 60.0);

   // Core Evaluation & Execution
   bool                 EvaluateGridStep(double currentAtr, bool allowBuy, bool allowSell);
   bool                 CheckAndCloseBasket(double currentAtr);
   void                 CloseAllGridOrders(long filterType = -1);

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
     m_basketTpAtrMult(0.8)
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
      lot = MathFloor(lot / step) * step;
      
   int lotDigits = 2;
   if(step >= 1.0) lotDigits = 0;
   else if(step >= 0.1) lotDigits = 1;
   
   lot = NormalizeDouble(lot, lotDigits);
   return MathMax(minLot, MathMin(maxLot, lot));
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

   if(currentAtr <= 0) currentAtr = 100 * point;
   double gridStepDist = currentAtr * m_stepAtrMultiplier;
   m_telemetry.currentGridStep = gridStepDist;

   // 1. Evaluate BUY Grid
   if(allowBuy && buyCount > 0 && buyCount < m_maxOrdersPerSide)
   {
      // Find lowest buy price
      double lowestBuy = buyOrders[0].openPrice;
      for(int i = 1; i < buyCount; i++)
      {
         if(buyOrders[i].openPrice < lowestBuy) lowestBuy = buyOrders[i].openPrice;
      }

      // Check if price dropped by at least gridStepDist from lowest buy
      if((lowestBuy - ask) >= gridStepDist)
      {
         // Calculate next geometric lot size normalized
         double nextLot = NormalizeLot(m_baseLot * MathPow(m_lotMultiplier, buyCount));

         PrintFormat("[DynamicGrid] Placing BUY Grid #%d at Ask: %.5f (Lowest: %.5f, Dist: %.1f pts, Lot: %.2f)",
            buyCount + 1, ask, lowestBuy, (lowestBuy - ask) / point, nextLot);

         if(m_trade.Buy(nextLot, m_symbol, ask, 0, 0, "QuantumTitan_Grid_Buy"))
         {
            return true;
         }
      }
   }

   // 2. Evaluate SELL Grid
   if(allowSell && sellCount > 0 && sellCount < m_maxOrdersPerSide)
   {
      // Find highest sell price
      double highestSell = sellOrders[0].openPrice;
      for(int i = 1; i < sellCount; i++)
      {
         if(sellOrders[i].openPrice > highestSell) highestSell = sellOrders[i].openPrice;
      }

      // Check if price rose by at least gridStepDist from highest sell
      if((bid - highestSell) >= gridStepDist)
      {
         // Calculate next geometric lot size normalized
         double nextLot = NormalizeLot(m_baseLot * MathPow(m_lotMultiplier, sellCount));

         PrintFormat("[DynamicGrid] Placing SELL Grid #%d at Bid: %.5f (Highest: %.5f, Dist: %.1f pts, Lot: %.2f)",
            sellCount + 1, bid, highestSell, (bid - highestSell) / point, nextLot);

         if(m_trade.Sell(nextLot, m_symbol, bid, 0, 0, "QuantumTitan_Grid_Sell"))
         {
            return true;
         }
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
      // Target: Ask has dropped below average sell price by targetProfitDist
      if((m_telemetry.avgSellPrice - ask) >= targetProfitDist && m_telemetry.totalSellProfit > 0)
      {
         PrintFormat("[DynamicGrid] BASKET REBALANCE: Closing %d SELL orders at +$%.2f profit (AvgPrice: %.5f, Ask: %.5f)",
            sellCount, m_telemetry.totalSellProfit, m_telemetry.avgSellPrice, ask);
         CloseAllGridOrders(POSITION_TYPE_SELL);
         closedAny = true;
      }
   }

   return closedAny;
}

//+------------------------------------------------------------------+
//| Close All Grid Orders in Basket                                  |
//+------------------------------------------------------------------+
void CDynamicGridEngine::CloseAllGridOrders(long filterType)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;

      long posType = m_position.PositionType();
      if(filterType == -1 || posType == filterType)
      {
         m_trade.PositionClose(m_position.Ticket());
      }
   }
}
