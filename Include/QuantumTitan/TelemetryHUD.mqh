//+------------------------------------------------------------------+
//|                                                 TelemetryHUD.mqh |
//|               QuantumTitan v9+++ Singularity Architecture         |
//|               Module 5: Real-time Visual Matrix HUD & Alerts     |
//|               Institutional On-Chart Telemetry & Notifications   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "9.00"

#define QT_HUD_PREFIX "QT9_HUD_"

//+------------------------------------------------------------------+
//| Class CTelemetryHUD                                              |
//+------------------------------------------------------------------+
class CTelemetryHUD
{
private:
   string         m_symbol;
   bool           m_enabled;
   bool           m_sendPush;
   bool           m_sendPop;
   datetime       m_lastAlertTime;

   // Internal Drawing Helpers
   void           CreateLabel(string name, int x, int y, string text, color clr, int fontSize = 9, string font = "Trebuchet MS");
   void           CreateCard(string name, int x, int y, int width, int height, color bgColor, color borderColor);

public:
                  CTelemetryHUD();
                 ~CTelemetryHUD();

   bool           Init(string symbol, bool enabled = true, bool sendPush = true, bool sendPop = true);
   void           Deinit();

   // Core Rendering
   void           RenderHUD(string regimeStr, int buyScore, int sellScore,
                            int buyOrders, double buyLots, int sellOrders, double sellLots,
                            double floatingPnl, double dailyHWM, double dailyDDPct,
                            double freeMarginPct, string newsStatus, bool isTradingPermitted,
                            string statusReason);

   // Visual Trade Markers
   void           DrawOrderBlock(string name, datetime t1, double p1, datetime t2, double p2, color boxColor);
   void           DrawTradeArrow(string name, datetime t, double p, bool isBuy);

   // Alerts
   void           DispatchAlert(string title, string message, bool isUrgent = false);
};

//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CTelemetryHUD::CTelemetryHUD()
   : m_symbol(""),
     m_enabled(true),
     m_sendPush(true),
     m_sendPop(true),
     m_lastAlertTime(0)
{
}

//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CTelemetryHUD::~CTelemetryHUD()
{
   Deinit();
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
bool CTelemetryHUD::Init(string symbol, bool enabled, bool sendPush, bool sendPop)
{
   m_symbol = (symbol == "") ? _Symbol : symbol;
   m_enabled = enabled;
   m_sendPush = sendPush;
   m_sendPop = sendPop;

   Deinit();
   return true;
}

//+------------------------------------------------------------------+
//| Clean Chart Objects                                              |
//+------------------------------------------------------------------+
void CTelemetryHUD::Deinit()
{
   ObjectsDeleteAll(0, QT_HUD_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Create UI Label                                                  |
//+------------------------------------------------------------------+
void CTelemetryHUD::CreateLabel(string name, int x, int y, string text, color clr, int fontSize, string font)
{
   string objName = QT_HUD_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, objName, OBJPROP_HIDDEN, true);
   }
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetString(0, objName, OBJPROP_FONT, font);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
}

//+------------------------------------------------------------------+
//| Create HUD Card Background                                       |
//+------------------------------------------------------------------+
void CTelemetryHUD::CreateCard(string name, int x, int y, int width, int height, color bgColor, color borderColor)
{
   string objName = QT_HUD_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, objName, OBJPROP_XSIZE, width);
      ObjectSetInteger(0, objName, OBJPROP_YSIZE, height);
      ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bgColor);
      ObjectSetInteger(0, objName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, borderColor);
      ObjectSetInteger(0, objName, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, objName, OBJPROP_BACK, false);
      ObjectSetInteger(0, objName, OBJPROP_HIDDEN, true);
   }
}

//+------------------------------------------------------------------+
//| Render Real-Time Visual Matrix HUD                               |
//+------------------------------------------------------------------+
void CTelemetryHUD::RenderHUD(string regimeStr, int buyScore, int sellScore,
                             int buyOrders, double buyLots, int sellOrders, double sellLots,
                             double floatingPnl, double dailyHWM, double dailyDDPct,
                             double freeMarginPct, string newsStatus, bool isTradingPermitted,
                             string statusReason)
{
   if(!m_enabled) return;

   int startX = 20;
   int startY = 30;
   int cardW  = 360;
   int cardH  = 220;

   // 1. Draw Master Card Background
   CreateCard("BG", startX, startY, cardW, cardH, C'20,24,35', C'45,55,75');

   // 2. Header
   CreateLabel("HDR", startX + 15, startY + 12, "⚡ QUANTUMTITAN v9+++ SINGULARITY", clrCyan, 10, "Trebuchet MS");
   
   // Status Pill
   string statusBadge = isTradingPermitted ? "🟢 ACTIVE [OPERATIONAL]" : "🔴 PAUSED [" + statusReason + "]";
   color statusColor = isTradingPermitted ? clrLimeGreen : clrCrimson;
   CreateLabel("STATUS", startX + 15, startY + 34, statusBadge, statusColor, 9, "Consolas");

   // 3. Market Regime
   color regimeClr = clrDeepSkyBlue;
   if(StringFind(regimeStr, "BULL") >= 0) regimeClr = clrLime;
   else if(StringFind(regimeStr, "BEAR") >= 0) regimeClr = clrTomato;
   else if(StringFind(regimeStr, "SHOCK") >= 0) regimeClr = clrMagenta;
   else regimeClr = clrGold;

   CreateLabel("REGIME", startX + 15, startY + 58, "Market Regime: " + regimeStr, regimeClr, 9, "Trebuchet MS");

   // 4. Alpha Confluence Scores
   string scoreStr = StringFormat("Alpha Score: BUY %d/100 | SELL %d/100 (Min 75)", buyScore, sellScore);
   CreateLabel("SCORE", startX + 15, startY + 80, scoreStr, clrWhiteSmoke, 9, "Consolas");

   // 5. Active Basket Exposure
   string posStr = StringFormat("Open Basket: BUY %d (%.2f L) | SELL %d (%.2f L)",
      buyOrders, buyLots, sellOrders, sellLots);
   CreateLabel("EXPOSURE", startX + 15, startY + 102, posStr, clrSilver, 9, "Consolas");

   // 6. Floating & High-Water Mark PnL
   color pnlClr = (floatingPnl >= 0) ? clrLimeGreen : clrOrangeRed;
   string pnlStr = StringFormat("Floating PnL: %s$%.2f | Daily DD: %.1f%% (HWM: $%.0f)",
      (floatingPnl >= 0 ? "+" : ""), floatingPnl, dailyDDPct, dailyHWM);
   CreateLabel("PNL", startX + 15, startY + 124, pnlStr, pnlClr, 9, "Consolas");

   // 7. Dynamic Cash Reserve Buffer
   color marginClr = (freeMarginPct >= 60.0) ? clrMediumSpringGreen : clrDarkOrange;
   string marginStr = StringFormat("Cash Buffer: Free Margin %.1f%% %s",
      freeMarginPct, (freeMarginPct >= 60.0 ? "[SECURE]" : "[RESERVE LOCK]"));
   CreateLabel("MARGIN", startX + 15, startY + 146, marginStr, marginClr, 9, "Consolas");

   // 8. Economic News Shield
   string newsStr = (newsStatus == "" || newsStatus == "CLEAR") ? "News Shield: CLEAR (No Red News)" : "News Shield: " + newsStatus;
   color newsClr = (newsStatus == "" || newsStatus == "CLEAR") ? clrLightSkyBlue : clrYellow;
   CreateLabel("NEWS", startX + 15, startY + 168, newsStr, newsClr, 9, "Trebuchet MS");

   // 9. Institutional Signature
   CreateLabel("FOOTER", startX + 15, startY + 192, "Institutional Quant Multi-Agent Framework v9.00", C'120,135,160', 8, "Trebuchet MS");

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Draw SMC Order Block Box                                         |
//+------------------------------------------------------------------+
void CTelemetryHUD::DrawOrderBlock(string name, datetime t1, double p1, datetime t2, double p2, color boxColor)
{
   if(!m_enabled) return;
   string objName = QT_HUD_PREFIX + "OB_" + name;
   ObjectDelete(0, objName);
   if(ObjectCreate(0, objName, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
   {
      ObjectSetInteger(0, objName, OBJPROP_COLOR, boxColor);
      ObjectSetInteger(0, objName, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, objName, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, objName, OBJPROP_FILL, true);
      ObjectSetInteger(0, objName, OBJPROP_BACK, true);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
}

//+------------------------------------------------------------------+
//| Draw Trade Execution Arrow                                       |
//+------------------------------------------------------------------+
void CTelemetryHUD::DrawTradeArrow(string name, datetime t, double p, bool isBuy)
{
   if(!m_enabled) return;
   string objName = QT_HUD_PREFIX + "ARROW_" + name;
   ObjectDelete(0, objName);
   if(ObjectCreate(0, objName, OBJ_ARROW, 0, t, p))
   {
      ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, isBuy ? 233 : 234);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, isBuy ? clrDeepSkyBlue : clrOrangeRed);
      ObjectSetInteger(0, objName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, objName, OBJPROP_BACK, false);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
}

//+------------------------------------------------------------------+
//| Multi-Channel Alert Dispatcher                                   |
//+------------------------------------------------------------------+
void CTelemetryHUD::DispatchAlert(string title, string message, bool isUrgent)
{
   datetime now = TimeCurrent();
   // Rate limit: 5 seconds between non-urgent alerts
   if(!isUrgent && (now - m_lastAlertTime < 5)) return;
   m_lastAlertTime = now;

   string fullMessage = StringFormat("[QuantumTitan v9] %s: %s", title, message);

   if(m_sendPop)
   {
      Alert(fullMessage);
   }

   if(m_sendPush)
   {
      SendNotification(fullMessage);
   }
}
