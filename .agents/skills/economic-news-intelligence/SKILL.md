---
name: economic-news-intelligence
description: Macroeconomic calendar event filtering and news shock management for MT5/MQL5. Covers native MQL5 CalendarValueHistory API, event importance levels, pre/post news lockout windows, USD macro catalysts (NFP, CPI, FOMC, Fed speeches), and emergency news flatten protocols.
---

# Economic News Intelligence Skill

## Macro Calendar Filter Architecture in MQL5

### 1. Native CalendarValueHistory API
MetaTrader 5 provides a built-in Economic Calendar feed synchronized with trade server time.

`cpp
bool IsInHighImpactNewsWindow(string &newsEventName, int bufferMinsBefore=30, int bufferMinsAfter=30, string currency="USD")
{
   datetime serverTime = TimeTradeServer();
   datetime timeFrom = serverTime - (bufferMinsAfter * 60);
   datetime timeTo   = serverTime + (bufferMinsBefore * 60);

   MqlCalendarValue values[];
   int count = CalendarValueHistory(values, timeFrom, timeTo, NULL, currency);
   if(count <= 0) return false;

   for(int i = 0; i < count; i++)
   {
      MqlCalendarEvent event;
      if(CalendarEventById(values[i].event_id, event))
      {
         if(event.importance == CALENDAR_IMPORTANCE_HIGH)
         {
            newsEventName = event.name + " [High Impact]";
            return true;
         }
      }
   }
   return false;
}
`

### 2. Best Practices for Gold (XAUUSD)
- Gold prices react violently to US Macro data (CPI, Non-Farm Payrolls, FOMC rate decisions, PPI, Retail Sales).
- Always prioritize **USD** news filtering.
- Recommended lockout buffer: 30 minutes before news release to 30 minutes after news release.
