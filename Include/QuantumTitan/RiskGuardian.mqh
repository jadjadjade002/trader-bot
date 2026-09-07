//+------------------------------------------------------------------+
//|                                                 RiskGuardian.mqh |
//|               QuantumTitan v12.00 Singularity Architecture       |
//|               Module 4: Institutional Capital & Risk Guardian    |
//|               High-Water Mark Drawdown, News Shield, Breakers    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "12.00"

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
   double            m_maxAccountLots;      // Max total open lots on account (Default 0.02)

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
   string            m_gvHwm;
   string            m_gvDay;
   string            m_gvCB;

   // Cached Daily Stats (Eliminates O(N) HistorySelect tick churn)
   datetime          m_lastStatsCheckTime;
   int               m_cachedTradeCount;
   int               m_cachedConsecutiveLosses;

   // Internal Helpers
   void              CheckNewDay();
   int               CalculateTodayStats(int &consecutiveLosses);
   bool              IsInNewsWindow(string &eventName);

public:
                     CRiskGuardian();
                    ~CRiskGuardian();

   bool              Init(string symbol, ulong magic, double maxDDPct = 8.0, double hardFloor = 30.0,
                          int maxTrades = 12, int maxLosses = 3, double maxSpread = 45.0,
                          bool useNews = true, int newsBefore = 30, int newsAfter = 30,
                          double maxAccountLots = 0.20);

   // Core Assessment
   bool              ValidateExecution(RiskTelemetry &telemetryOut);
   bool              CheckEmergencyFloor();
   void              CloseAllPositions(string reason = "Emergency Shutdown");
   void              InvalidateStatsCache() { m_lastStatsCheckTime = 0; }

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
     m_cachedNewsEvent(""),
     m_lastStatsCheckTime(0),
     m_cachedTradeCount(0),
     m_cachedConsecutiveLosses(0)
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
                         bool useNews, int newsBefore, int newsAfter,
                         double maxAccountLots)
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
   m_maxAccountLots = maxAccountLots;

   m_trade.SetExpertMagicNumber(m_magic);

   // Dynamic Filling Mode Resolution
   uint filling = (uint)SymbolInfoInteger(m_symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

   // Initialize Daily Equity & HWM with Cross-Asset Isolated GlobalVariables
   m_currentDay = iTime(m_symbol, PERIOD_D1, 0);
   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   string safeSymbol = m_symbol;
   StringReplace(safeSymbol, "/", "_");
   StringReplace(safeSymbol, ".", "_");
   m_gvHwm = StringFormat("QT_%I64u_%s_HWM", m_magic, safeSymbol);
   m_gvDay = StringFormat("QT_%I64u_%s_DAY", m_magic, safeSymbol);
   m_gvCB  = StringFormat("QT_%I64u_%s_CB", m_magic, safeSymbol);

   if(GlobalVariableCheck(m_gvDay) && (datetime)GlobalVariableGet(m_gvDay) == m_currentDay)
   {
      m_dailyHighWaterMark = GlobalVariableGet(m_gvHwm);
      m_circuitBreakerTripped = (GlobalVariableGet(m_gvCB) > 0.5);
      PrintFormat("[RiskGuardian] RESTORED PERSISTENT STATE (%s): HWM=$%.2f, CircuitBreaker=%s",
         m_symbol, m_dailyHighWaterMark, m_circuitBreakerTripped ? "TRIPPED" : "OFF");
   }
   else
   {
      m_dailyHighWaterMark = m_startingDailyEquity;
      m_circuitBreakerTripped = false;
      GlobalVariableSet(m_gvDay, (double)m_currentDay);
      GlobalVariableSet(m_gvHwm, m_dailyHighWaterMark);
      GlobalVariableSet(m_gvCB, 0.0);
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

   if(today != m_currentDay && today > 0)
   {
      m_currentDay = today;
      m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      m_dailyHighWaterMark = m_startingDailyEquity;
      m_circuitBreakerTripped = false;
      GlobalVariableSet(m_gvDay, (double)m_currentDay);
      GlobalVariableSet(m_gvHwm, m_dailyHighWaterMark);
      GlobalVariableSet(m_gvCB, 0.0);
      PrintFormat("[RiskGuardian] NEW TRADING DAY DETECTED (%s). Reset HWM: $%.2f", m_symbol, m_dailyHighWaterMark);
   }

   // Continuously track peak equity and persist
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > m_dailyHighWaterMark)
   {
      m_dailyHighWaterMark = currentEquity;
      GlobalVariableSet(m_gvHwm, m_dailyHighWaterMark);
   }
}

//+------------------------------------------------------------------+
//| Calculate Closed Trades & Consecutive Losses Today               |
//+------------------------------------------------------------------+
int CRiskGuardian::CalculateTodayStats(int &consecutiveLosses)
{
   datetime now = TimeCurrent();
   // Cache stats for 5 seconds to eliminate O(N) HistorySelect database churn on every tick
   if(now - m_lastStatsCheckTime < 5 && m_lastStatsCheckTime > 0)
   {
      consecutiveLosses = m_cachedConsecutiveLosses;
      return m_cachedTradeCount;
   }

   m_lastStatsCheckTime = now;
   consecutiveLosses = 0;
   int tradeCount = 0;

   datetime startOfDay = iTime(m_symbol, PERIOD_D1, 0);
   if(!HistorySelect(startOfDay, now))
   {
      consecutiveLosses = m_cachedConsecutiveLosses;
      return m_cachedTradeCount;
   }

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
         double swap   = HistoryDealGetDouble(ticket, DEAL_SWAP);
         double comm   = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double fee    = HistoryDealGetDouble(ticket, DEAL_FEE);
         double netPnl = profit + swap + comm + fee;
         if(netPnl < -0.0001) streak++;
         else if(netPnl > 0.0001) streak = 0; // Net win resets streak
      }
   }

   m_cachedTradeCount = tradeCount;
   m_cachedConsecutiveLosses = streak;
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
   if(currentSpread >= m_maxSpreadPoints)
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
      GlobalVariableSet(m_gvCB, 1.0);
      telemetryOut.circuitBreakerTripped = true;
      telemetryOut.canOpenNewCycle       = false; // Blocks Module 1 initial entries
      telemetryOut.canManageGrid         = true;  // Allows Module 3 active basket rebalance!
      telemetryOut.tradingPermitted      = false;
      telemetryOut.rejectReason = StringFormat("CIRCUIT BREAKER: Daily DD %.2f%% reached (New entries locked, grid active)", ddPct);
   }

   // 3. TRIPWIRE: Midnight Swap Rollover Blackout (23:55 to 00:05 Broker Server Time)
   datetime srvTime = TimeTradeServer();
   MqlDateTime srvDt;
   TimeToStruct(srvTime, srvDt);

   bool isMidnightRollover = (srvDt.hour == 23 && srvDt.min >= 55) || (srvDt.hour == 0 && srvDt.min < 5);
   if(isMidnightRollover)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.canManageGrid    = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("ROLLOVER BLACKOUT: Midnight swap transition (%02d:%02d)", srvDt.hour, srvDt.min);
      return false;
   }

   // 4. TRIPWIRE: Friday Afternoon Leverage Reduction & Weekend Margin Shock Guard
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double freeMargin  = AccountInfoDouble(ACCOUNT_MARGIN_FREE);

   // Institutional brokers reduce leverage (e.g. 1:500 -> 1:100) on Friday afternoon (5x margin jump)
   if(srvDt.day_of_week == 5 && srvDt.hour >= 18)
   {
      telemetryOut.canOpenNewCycle = false;
      telemetryOut.canManageGrid   = false; // Freeze grid expansion before weekend close

      if(marginLevel > 0.0 && marginLevel < 350.0)
      {
         telemetryOut.tradingPermitted = false;
         telemetryOut.rejectReason = StringFormat("FRIDAY LEVERAGE GUARD: Margin Level %.1f%% below 350%% safety buffer. Preemptive liquidation.", marginLevel);
         PrintFormat("[RiskGuardian] %s", telemetryOut.rejectReason);
         CloseAllPositions("Friday Leverage Reduction Preemptive Cut");
         return false;
      }
   }

   // 5. TRIPWIRE: Dynamic Margin Level Protection (Continuous Across All Sessions)
   if(marginLevel > 0.0 && marginLevel < 180.0)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.canManageGrid    = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("MARGIN DEFICIT: Margin level %.1f%% below 180%% safety buffer", marginLevel);
      PrintFormat("[RiskGuardian] %s - Executing defensive liquidation", telemetryOut.rejectReason);
      CloseAllPositions("Emergency Margin Preservation");
      return false;
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

   // 7. TRIPWIRE: Portfolio Multi-Chart Exposure Cap (Account-Wide Volume Check)
   double totalOpenLots = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() == m_symbol)
            totalOpenLots += m_position.Volume();
      }
   }
   if(totalOpenLots >= m_maxAccountLots)
   {
      telemetryOut.canOpenNewCycle  = false;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("PORTFOLIO CAP: %.2f lots active (Max: %.2f)", totalOpenLots, m_maxAccountLots);
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

   const int maxRetries = 3;
   for(int attempt = 1; attempt <= maxRetries; attempt++)
   {
      int remaining = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(!m_position.SelectByIndex(i)) continue;
         if(m_position.Symbol() == m_symbol && m_position.Magic() == m_magic)
         {
            if(!m_trade.PositionClose(m_position.Ticket()))
            {
               remaining++;
               PrintFormat("[RiskGuardian] Attempt %d: Failed to close #%I64u (Retcode: %u). Retrying...",
                  attempt, m_position.Ticket(), m_trade.ResultRetcode());
            }
         }
      }

      if(remaining == 0) break;
      if(attempt < maxRetries) Sleep(100);
   }
}
