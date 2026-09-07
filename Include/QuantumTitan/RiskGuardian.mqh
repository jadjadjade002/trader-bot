//+------------------------------------------------------------------+
//|                                                 RiskGuardian.mqh |
//|               QuantumTitan v9+++ Singularity Architecture         |
//|               Module 4: Institutional Capital & Risk Guardian    |
//|               High-Water Mark Drawdown, News Shield, Breakers    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Risk Telemetry Data Struct
struct RiskTelemetry
{
   double   startingEquity;
   double   dailyHighWaterMark;
   double   currentEquity;
   double   currentDrawdownPct;
   bool     circuitBreakerTripped;
   bool     inNewsLockout;
   string   newsEventName;
   int      completedTradesToday;
   int      consecutiveLosses;
   bool     canOpenNewCycle;       // Allowed to open new trade cycles
   bool     canManageGrid;         // Allowed to manage active grid layers
   bool     tradingPermitted;      // Overall status
   string   rejectReason;
};

//+------------------------------------------------------------------+
//| Class CRiskGuardian                                              |
//+------------------------------------------------------------------+
class CRiskGuardian
{
private:
   CTrade            m_trade;
   CPositionInfo     m_position;
   string            m_symbol;
   ulong             m_magic;

   // Capital Protection Limits
   double            m_maxDailyLossPct;     // Daily DD limit % from HWM (Default 8.0%)
   double            m_hardEquityFloor;     // Emergency Floor $ (Default 30.0)
   int               m_maxTradesPerDay;     // Daily completed trade cap (Default 12)
   int               m_maxLosingStreak;     // Pause after N consecutive losses (Default 3)
   double            m_maxSpreadPoints;     // Max allowed spread (Default 45.0)

   // News Filter Parameters
   bool              m_useNewsFilter;       // Economic calendar filter
   int               m_newsBufferBeforeMins;// Pre-news pause (Default 30 mins)
   int               m_newsBufferAfterMins; // Post-news pause (Default 30 mins)
   bool              m_filterUSDOnly;

   // Daily State Variables
   datetime          m_currentDay;
   double            m_startingDailyEquity;
   double            m_dailyHighWaterMark;
   bool              m_circuitBreakerTripped;
   datetime          m_lastNewsCheckTime;
   bool              m_cachedNewsResult;
   string            m_cachedNewsEvent;

   // Internal Helpers
   void              CheckNewDay();
   int               CalculateTodayStats(int &consecutiveLosses);
   bool              IsInNewsWindow(string &eventName);

public:
                     CRiskGuardian();
                    ~CRiskGuardian();

   bool              Init(string symbol, ulong magic, double maxDDPct = 8.0, double hardFloor = 30.0,
                          int maxTrades = 12, int maxLosses = 3, double maxSpread = 45.0,
                          bool useNews = true, int newsBefore = 30, int newsAfter = 30);

   // Core Assessment
   bool              ValidateExecution(RiskTelemetry &telemetryOut);
   bool              CheckEmergencyFloor();
   void              CloseAllPositions(string reason = "Emergency Shutdown");

   // Getters
   RiskTelemetry     GetTelemetry();
   bool              IsCircuitBreakerActive() const { return m_circuitBreakerTripped; }
   double            GetDailyHWM() const { return m_dailyHighWaterMark; }
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CRiskGuardian::CRiskGuardian()
   : m_symbol(""),
     m_magic(0),
     m_maxDailyLossPct(8.0),
     m_hardEquityFloor(30.0),
     m_maxTradesPerDay(12),
     m_maxLosingStreak(3),
     m_maxSpreadPoints(45.0),
     m_useNewsFilter(true),
     m_newsBufferBeforeMins(30),
     m_newsBufferAfterMins(30),
     m_filterUSDOnly(true),
     m_currentDay(0),
     m_startingDailyEquity(0.0),
     m_dailyHighWaterMark(0.0),
     m_circuitBreakerTripped(false),
     m_lastNewsCheckTime(0),
     m_cachedNewsResult(false),
     m_cachedNewsEvent("")
{
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CRiskGuardian::~CRiskGuardian()
{
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
bool CRiskGuardian::Init(string symbol, ulong magic, double maxDDPct, double hardFloor,
                         int maxTrades, int maxLosses, double maxSpread,
                         bool useNews, int newsBefore, int newsAfter)
{
   m_symbol = (symbol == "") ? _Symbol : symbol;
   m_magic = magic;
   m_maxDailyLossPct = maxDDPct;
   m_hardEquityFloor = hardFloor;
   m_maxTradesPerDay = maxTrades;
   m_maxLosingStreak = maxLosses;
   m_maxSpreadPoints = maxSpread;
   m_useNewsFilter = useNews;
   m_newsBufferBeforeMins = newsBefore;
   m_newsBufferAfterMins = newsAfter;

   m_trade.SetExpertMagicNumber(m_magic);

   // Dynamic Filling Mode Resolution
   uint filling = (uint)SymbolInfoInteger(m_symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   // Initialize Daily Equity & HWM with GlobalVariable Persistence
   m_currentDay = iTime(m_symbol, PERIOD_D1, 0);
   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   string gvHwm = StringFormat("QT_%I64u_HWM", m_magic);
   string gvDay = StringFormat("QT_%I64u_DAY", m_magic);
   string gvCB  = StringFormat("QT_%I64u_CB", m_magic);

   if(GlobalVariableCheck(gvDay) && (datetime)GlobalVariableGet(gvDay) == m_currentDay)
   {
      m_dailyHighWaterMark = GlobalVariableGet(gvHwm);
      m_circuitBreakerTripped = (GlobalVariableGet(gvCB) > 0.5);
      PrintFormat("[RiskGuardian] RESTORED PERSISTENT STATE: HWM=$%.2f, CircuitBreaker=%s",
         m_dailyHighWaterMark, m_circuitBreakerTripped ? "TRIPPED" : "OFF");
   }
   else
   {
      m_dailyHighWaterMark = m_startingDailyEquity;
      m_circuitBreakerTripped = false;
      GlobalVariableSet(gvDay, (double)m_currentDay);
      GlobalVariableSet(gvHwm, m_dailyHighWaterMark);
      GlobalVariableSet(gvCB, 0.0);
   }

   PrintFormat("[RiskGuardian] Initialized for %s (DailyMaxDD: %.1f%%, HardFloor: $%.2f, MaxLossStreak: %d)",
      m_symbol, m_maxDailyLossPct, m_hardEquityFloor, m_maxLosingStreak);
   return true;
}

//+------------------------------------------------------------------+
//| Check and Reset Stats for a New Trading Day                      |
//+------------------------------------------------------------------+
void CRiskGuardian::CheckNewDay()
{
   datetime today = iTime(m_symbol, PERIOD_D1, 0);
   string gvHwm = StringFormat("QT_%I64u_HWM", m_magic);
   string gvDay = StringFormat("QT_%I64u_DAY", m_magic);
   string gvCB  = StringFormat("QT_%I64u_CB", m_magic);

   if(today != m_currentDay && today > 0)
   {
      m_currentDay = today;
      m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      m_dailyHighWaterMark = m_startingDailyEquity;
      m_circuitBreakerTripped = false;
      GlobalVariableSet(gvDay, (double)m_currentDay);
      GlobalVariableSet(gvHwm, m_dailyHighWaterMark);
      GlobalVariableSet(gvCB, 0.0);
      PrintFormat("[RiskGuardian] NEW TRADING DAY DETECTED. Reset HWM: $%.2f", m_dailyHighWaterMark);
   }

   // Continuously track peak equity and persist
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > m_dailyHighWaterMark)
   {
      m_dailyHighWaterMark = currentEquity;
      GlobalVariableSet(gvHwm, m_dailyHighWaterMark);
   }
}

//+------------------------------------------------------------------+
//| Calculate Closed Trades & Consecutive Losses Today               |
//+------------------------------------------------------------------+
int CRiskGuardian::CalculateTodayStats(int &consecutiveLosses)
{
   consecutiveLosses = 0;
   int tradeCount = 0;

   datetime startOfDay = iTime(m_symbol, PERIOD_D1, 0);
   if(!HistorySelect(startOfDay, TimeCurrent())) return 0;

   int totalDeals = HistoryDealsTotal();
   int streak = 0;

   // Process deals chronologically to count trades and streak
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != m_symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != m_magic) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
      {
         tradeCount++;
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         if(profit < -0.0001) streak++;
         else if(profit > 0.0001) streak = 0; // Win resets streak
      }
   }

   consecutiveLosses = streak;
   return tradeCount;
}

//+------------------------------------------------------------------+
//| Native MQL5 Economic Calendar High-Impact News Window            |
//+------------------------------------------------------------------+
bool CRiskGuardian::IsInNewsWindow(string &eventName)
{
   if(!m_useNewsFilter) return false;

   // 1. REAL-TIME MICROSTRUCTURE SPREAD SURGE CHECK (ZERO CACHE - EVALUATED EVERY TICK)
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   double currentSpread = (point > 0) ? (ask - bid) / point : 0;
   if(currentSpread >= (m_maxSpreadPoints * 0.70))
   {
      eventName = StringFormat("PROXY: Spread Surge %.1f pts (Real-Time Microstructure)", currentSpread);
      return true;
   }

   // 2. CALENDAR-BASED NEWS QUERY (Cached for 30 seconds)
   datetime serverTime = TimeTradeServer();
   if(serverTime - m_lastNewsCheckTime < 30 && m_lastNewsCheckTime > 0)
   {
      eventName = m_cachedNewsEvent;
      return m_cachedNewsResult;
   }

   datetime timeFrom = serverTime - (m_newsBufferAfterMins * 60);
   datetime timeTo   = serverTime + (m_newsBufferBeforeMins * 60);

   // Extract relevant currencies for this asset (Base, Profit, and USD)
   string currs[3];
   int currCount = 0;
   string baseCurr = SymbolInfoString(m_symbol, SYMBOL_CURRENCY_BASE);
   string profitCurr = SymbolInfoString(m_symbol, SYMBOL_CURRENCY_PROFIT);

   if(baseCurr != "") { currs[currCount++] = baseCurr; }
   if(profitCurr != "" && profitCurr != baseCurr) { currs[currCount++] = profitCurr; }
   if(baseCurr != "USD" && profitCurr != "USD") { currs[currCount++] = "USD"; }

   for(int c = 0; c < currCount; c++)
   {
      MqlCalendarValue values[];
      int count = CalendarValueHistory(values, timeFrom, timeTo, NULL, currs[c]);
      if(count <= 0) continue;

      for(int i = 0; i < count; i++)
      {
         MqlCalendarEvent event;
         if(CalendarEventById(values[i].event_id, event))
         {
            if(event.importance == CALENDAR_IMPORTANCE_HIGH)
            {
               eventName = StringFormat("[%s] %s [HIGH IMPACT]", currs[c], event.name);
               m_lastNewsCheckTime = serverTime;
               m_cachedNewsResult = true;
               m_cachedNewsEvent = eventName;
               return true;
            }
         }
      }
   }

   m_lastNewsCheckTime = serverTime;
   m_cachedNewsResult = false;
   m_cachedNewsEvent = "";
   return false;
}

//+------------------------------------------------------------------+
//| Validate Trade Execution against All Institutional Tripwires     |
//+------------------------------------------------------------------+
bool CRiskGuardian::ValidateExecution(RiskTelemetry &telemetryOut)
{
   CheckNewDay();

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   telemetryOut.startingEquity       = m_startingDailyEquity;
   telemetryOut.dailyHighWaterMark   = m_dailyHighWaterMark;
   telemetryOut.currentEquity        = currentEquity;

   // Default permissions
   telemetryOut.canOpenNewCycle  = true;
   telemetryOut.canManageGrid    = true;
   telemetryOut.tradingPermitted = true;
   telemetryOut.rejectReason     = "CLEAR";

   // Compute Drawdown from High-Water Mark
   double ddPct = 0.0;
   if(m_dailyHighWaterMark > 0)
   {
      ddPct = ((m_dailyHighWaterMark - currentEquity) / m_dailyHighWaterMark) * 100.0;
   }
   telemetryOut.currentDrawdownPct = ddPct;

   // 1. TRIPWIRE: Hard Equity Floor ($30.00) - ULTIMATE CAPITAL PRESERVATION BREAKER
   if(currentEquity < m_hardEquityFloor)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.canManageGrid    = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("CRITICAL: Equity $%.2f hit Hard Floor $%.2f", currentEquity, m_hardEquityFloor);
      PrintFormat("[RiskGuardian] %s - EMERGENCY LIQUIDATION TRIGGERED", telemetryOut.rejectReason);
      CloseAllPositions("Hard Floor Breached");
      return false;
   }

   // 2. TRIPWIRE: Daily High-Water Mark Drawdown Circuit Breaker (8.0%)
   // SOFT BREAKER: Stop new cycle entries for the day, BUT allow active basket to rebalance and exit!
   if(ddPct >= m_maxDailyLossPct || m_circuitBreakerTripped)
   {
      m_circuitBreakerTripped = true;
      string gvCB = StringFormat("QT_%I64u_CB", m_magic);
      GlobalVariableSet(gvCB, 1.0);
      telemetryOut.circuitBreakerTripped = true;
      telemetryOut.canOpenNewCycle       = false; // Blocks Module 1 initial entries
      telemetryOut.canManageGrid         = true;  // Allows Module 3 active basket rebalance!
      telemetryOut.tradingPermitted      = false;
      telemetryOut.rejectReason = StringFormat("CIRCUIT BREAKER: Daily DD %.2f%% reached (New entries locked, grid active)", ddPct);
   }

   // 3. TRIPWIRE: Economic Calendar News Lockout
   string newsName = "";
   if(IsInNewsWindow(newsName))
   {
      telemetryOut.inNewsLockout    = true;
      telemetryOut.newsEventName    = newsName;
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.canManageGrid    = false; // Freeze grid expansion during news surge
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason     = StringFormat("NEWS SHIELD: %s Lockout Active", newsName);
      return false;
   }
   telemetryOut.inNewsLockout = false;
   telemetryOut.newsEventName = "";

   // 4. TRIPWIRE: Max Spread Check
   double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
   double currentSpread = (point > 0) ? (ask - bid) / point : 0;
   if(currentSpread > m_maxSpreadPoints)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.canManageGrid    = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("SPREAD EXCESSIVE: %.1f pts (Max: %.1f)", currentSpread, m_maxSpreadPoints);
      return false;
   }

   // 5. TRIPWIRE: Daily Trade Count & Losing Streak
   int streak = 0;
   int completedTrades = CalculateTodayStats(streak);
   telemetryOut.completedTradesToday = completedTrades;
   telemetryOut.consecutiveLosses = streak;

   if(completedTrades >= m_maxTradesPerDay)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("DAILY CAP: %d trades reached (Max: %d)", completedTrades, m_maxTradesPerDay);
   }

   if(streak >= m_maxLosingStreak)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("STREAK PAUSE: %d consecutive losses", streak);
   }

   return telemetryOut.tradingPermitted;
}

//+------------------------------------------------------------------+
//| Close All Positions on Emergency with Slippage & Filling Guard   |
//+------------------------------------------------------------------+
void CRiskGuardian::CloseAllPositions(string reason)
{
   PrintFormat("[RiskGuardian] EMERGENCY CLOSE TRIGGERED: %s", reason);

   // Adaptive execution to guarantee fill in illiquid or emergency states
   uint filling = (uint)SymbolInfoInteger(m_symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   m_trade.SetDeviationInPoints(50); // Increased deviation buffer for emergency close

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() == m_symbol && m_position.Magic() == m_magic)
      {
         m_trade.PositionClose(m_position.Ticket());
      }
   }
}
