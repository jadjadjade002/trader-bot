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
   bool     tradingPermitted;
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

   // Initialize Daily Equity & HWM
   m_currentDay = iTime(m_symbol, PERIOD_D1, 0);
   m_startingDailyEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_dailyHighWaterMark = m_startingDailyEquity;
   m_circuitBreakerTripped = false;

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
      PrintFormat("[RiskGuardian] NEW TRADING DAY DETECTED. Reset HWM: $%.2f", m_dailyHighWaterMark);
   }

   // Continuously track peak equity
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > m_dailyHighWaterMark)
   {
      m_dailyHighWaterMark = currentEquity;
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

   datetime serverTime = TimeTradeServer();
   if(serverTime - m_lastNewsCheckTime < 30 && m_lastNewsCheckTime > 0)
   {
      eventName = m_cachedNewsEvent;
      return m_cachedNewsResult;
   }

   datetime timeFrom = serverTime - (m_newsBufferAfterMins * 60);
   datetime timeTo   = serverTime + (m_newsBufferBeforeMins * 60);

   MqlCalendarValue values[];
   string currencyFilter = m_filterUSDOnly ? "USD" : NULL;

   int count = CalendarValueHistory(values, timeFrom, timeTo, NULL, currencyFilter);
   if(count <= 0)
   {
      m_lastNewsCheckTime = serverTime;
      m_cachedNewsResult = false;
      m_cachedNewsEvent = "";
      return false;
   }

   for(int i = 0; i < count; i++)
   {
      MqlCalendarEvent event;
      if(CalendarEventById(values[i].event_id, event))
      {
         if(event.importance == CALENDAR_IMPORTANCE_HIGH)
         {
            eventName = event.name + " [HIGH IMPACT]";
            m_lastNewsCheckTime = serverTime;
            m_cachedNewsResult = true;
            m_cachedNewsEvent = eventName;
            return true;
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

   // Compute Drawdown from High-Water Mark
   double ddPct = 0.0;
   if(m_dailyHighWaterMark > 0)
   {
      ddPct = ((m_dailyHighWaterMark - currentEquity) / m_dailyHighWaterMark) * 100.0;
   }
   telemetryOut.currentDrawdownPct = ddPct;

   // 1. TRIPWIRE: Hard Equity Floor ($30.00)
   if(currentEquity < m_hardEquityFloor)
   {
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("CRITICAL: Equity $%.2f hit Hard Floor $%.2f", currentEquity, m_hardEquityFloor);
      PrintFormat("[RiskGuardian] %s", telemetryOut.rejectReason);
      CloseAllPositions("Hard Floor Breached");
      return false;
   }

   // 2. TRIPWIRE: Daily High-Water Mark Drawdown Circuit Breaker (8.0%)
   if(ddPct >= m_maxDailyLossPct)
   {
      m_circuitBreakerTripped = true;
      telemetryOut.circuitBreakerTripped = true;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("CIRCUIT BREAKER: Daily DD %.2f%% exceeded limit %.1f%%", ddPct, m_maxDailyLossPct);
      return false;
   }

   telemetryOut.circuitBreakerTripped = m_circuitBreakerTripped;
   if(m_circuitBreakerTripped)
   {
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = "CIRCUIT BREAKER: Locked until next trading day";
      return false;
   }

   // 3. TRIPWIRE: Economic Calendar News Lockout
   string newsName = "";
   if(IsInNewsWindow(newsName))
   {
      telemetryOut.inNewsLockout = true;
      telemetryOut.newsEventName = newsName;
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("NEWS SHIELD: %s Lockout Active (+/-%d min)", newsName, m_newsBufferBeforeMins);
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
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("DAILY CAP: %d trades reached (Max: %d)", completedTrades, m_maxTradesPerDay);
      return false;
   }

   if(streak >= m_maxLosingStreak)
   {
      telemetryOut.tradingPermitted = false;
      telemetryOut.rejectReason = StringFormat("STREAK PAUSE: %d consecutive losses", streak);
      return false;
   }

   telemetryOut.tradingPermitted = true;
   telemetryOut.rejectReason = "CLEAR";
   return true;
}

//+------------------------------------------------------------------+
//| Close All Positions on Emergency                                 |
//+------------------------------------------------------------------+
void CRiskGuardian::CloseAllPositions(string reason)
{
   PrintFormat("[RiskGuardian] EMERGENCY CLOSE TRIGGERED: %s", reason);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(m_position.Symbol() == m_symbol && m_position.Magic() == m_magic)
      {
         m_trade.PositionClose(m_position.Ticket());
      }
   }
}
