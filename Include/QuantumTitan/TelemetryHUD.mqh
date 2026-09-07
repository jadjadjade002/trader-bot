//+------------------------------------------------------------------+
//|                                                 TelemetryHUD.mqh |
//|               QuantumTitan v12.00 Singularity Architecture       |
//|               Module 5: Real-time Visual Matrix HUD & Alerts     |
//|               Institutional On-Chart Telemetry & Notifications   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "12.00"

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

   int startX = 15;
   int startY = 88;
   int cardW  = 315;
   int cardH  = 265;

   // 1. Draw Master Card Background (TradingView Slate Dark #131722 with subtle border)
   CreateCard("BG", startX, startY, cardW, cardH, C'19,23,34', C'40,48,64');

   // 2. Header
   string tfStr = EnumToString(_Period);
   StringReplace(tfStr, "PERIOD_", "");
   string hdrStr = StringFormat("✦ QUANTUM TITAN v12.00 [%s] ✦", tfStr);
   CreateLabel("HDR", startX + 12, startY + 8, hdrStr, clrWhiteSmoke, 9, "Consolas");
   CreateLabel("SEP1", startX + 12, startY + 22, "--------------------------------------------------", C'48,56,74', 8, "Consolas");

   // Section 1: Account Security & News
   string accMode = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO (Safe)" : "REAL (Live)";
   string accStr  = StringFormat("Account Mode   : %s ($%.2f)", accMode, AccountInfoDouble(ACCOUNT_EQUITY));
   CreateLabel("ACC", startX + 12, startY + 36, accStr, C'175,185,200', 8, "Consolas");

   string newsStr = (newsStatus == "" || newsStatus == "CLEAR") ? "News Calendar  : CLEAR 🟢" : "News Calendar  : " + newsStatus;
   color newsClr = (newsStatus == "" || newsStatus == "CLEAR") ? clrMediumSpringGreen : clrYellow;
   CreateLabel("NEWS", startX + 12, startY + 50, newsStr, newsClr, 8, "Consolas");

   long currentSpread = SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
   string spreadStr = StringFormat("Spread Check   : %d pts", currentSpread);
   color spreadClr = (currentSpread <= 35) ? clrMediumSpringGreen : ((currentSpread <= 45) ? clrGold : clrOrangeRed);
   CreateLabel("SPREAD", startX + 12, startY + 64, spreadStr, spreadClr, 8, "Consolas");

   CreateLabel("SEP2", startX + 12, startY + 77, "--------------------------------------------------", C'48,56,74', 8, "Consolas");

   // Section 2: Quant Engines & Signals
   color regimeClr = clrDeepSkyBlue;
   if(StringFind(regimeStr, "BULL") >= 0) regimeClr = C'38,166,154';
   else if(StringFind(regimeStr, "BEAR") >= 0) regimeClr = C'239,83,80';
   else if(StringFind(regimeStr, "SHOCK") >= 0) regimeClr = clrMagenta;
   else regimeClr = clrGold;

   CreateLabel("REGIME", startX + 12, startY + 90, "H1 Trend Bias  : " + regimeStr, regimeClr, 8, "Consolas");

   string scoreStr = StringFormat("Alpha Score    : BUY %d/100 | SELL %d/100", buyScore, sellScore);
   CreateLabel("SCORE", startX + 12, startY + 104, scoreStr, C'200,210,225', 8, "Consolas");

   string posStr = StringFormat("Active Basket  : BUY %d (%.2f L) | SELL %d (%.2f L)",
      buyOrders, buyLots, sellOrders, sellLots);
   CreateLabel("EXPOSURE", startX + 12, startY + 118, posStr, C'165,175,190', 8, "Consolas");

   color pnlClr = (floatingPnl >= 0) ? C'38,166,154' : C'239,83,80';
   string pnlStr = StringFormat("Floating PnL   : %s$%.2f | DD: %.1f%% (HWM: $%.0f)",
      (floatingPnl >= 0 ? "+" : ""), floatingPnl, dailyDDPct, dailyHWM);
   CreateLabel("PNL", startX + 12, startY + 132, pnlStr, pnlClr, 8, "Consolas");

   color marginClr = (freeMarginPct >= 60.0) ? C'38,166,154' : clrDarkOrange;
   string marginStr = StringFormat("Cash Buffer    : Free Margin %.1f%% %s",
      freeMarginPct, (freeMarginPct >= 60.0 ? "[SECURE]" : "[LOCK]"));
   CreateLabel("MARGIN", startX + 12, startY + 146, marginStr, marginClr, 8, "Consolas");

   CreateLabel("SEP3", startX + 12, startY + 159, "--------------------------------------------------", C'48,56,74', 8, "Consolas");

   // Section 3: Status & Execution
   string statusBadge = isTradingPermitted ? "🟢 HUNTING SETUP 🎯" : "🔴 PAUSED [" + statusReason + "]";
   color statusColor = isTradingPermitted ? C'38,166,154' : C'239,83,80';
   CreateLabel("STATUS", startX + 12, startY + 172, "Status         : " + statusBadge, statusColor, 8, "Consolas");

   string activeStr = (buyOrders > 0 || sellOrders > 0) ? "Active Trades  : IN POSITION 🟢" : "Active Trades  : SCANNING MARKET ⚡";
   CreateLabel("ACTIVE", startX + 12, startY + 186, activeStr, C'175,185,200', 8, "Consolas");

   CreateLabel("SEP4", startX + 12, startY + 200, "--------------------------------------------------", C'48,56,74', 8, "Consolas");

   // Footer
   CreateLabel("FOOTER", startX + 12, startY + 214, "Institutional Quant Matrix v12.00", C'110,125,145', 8, "Consolas");

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

   string fullMessage = StringFormat("[QuantumTitan v10.10] %s: %s", title, message);

   if(m_sendPop)
   {
      Alert(fullMessage);
   }

   if(m_sendPush)
   {
      SendNotification(fullMessage);
   }
}
