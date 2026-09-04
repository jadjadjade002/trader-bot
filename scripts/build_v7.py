import os

source_path = r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\QuantumSniper_v6_Institutional.mq5"
with open(source_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update Header & Version to v7.0
code = code.replace("QuantumSniper_v6_Institutional.mq5", "QuantumSniper_v7_Apex.mq5")
code = code.replace("v6.0 Institutional Master Edition", "v7.0 Institutional Apex Edition")
code = code.replace('"6.00"', '"7.00"')
code = code.replace("InpMagicNumber          = 660600;", "InpMagicNumber          = 770700;")

# 2. Add Visual SMC inputs and Telemetry inputs
visual_and_alerts_inputs = """
input group "=== 4. VISUAL SMC CHART ENGINE ==="
input bool     InpDrawOrderBlocks      = true;       // Draw Order Block Rectangles on Chart
input color    InpDemandOB_Color       = clrLightGreen;// Bullish Demand Zone Color
input color    InpSupplyOB_Color       = clrLightPink; // Bearish Supply Zone Color
input bool     InpDrawTradeArrows      = true;       // Draw Buy/Sell Entry Arrows on Chart

input group "=== 5. TELEMETRY AND MULTI-CHANNEL ALERTS ==="
input bool     InpSendPushAlerts       = true;       // Send MT5 Mobile Push Notifications
input bool     InpSendPopAlerts        = true;       // Send Terminal Audio/Popup Alerts
input bool     InpSendNewsAlerts       = true;       // Alert on High-Impact News Lockout
"""

target_group = 'input group "=== 4. HIGHER TIMEFRAME TREND FILTER (H1) ==="'
code = code.replace(target_group, visual_and_alerts_inputs + "\n" + target_group)

# 3. Add Object prefix definition and Visual helpers
helper_funcs = """
#define OBJ_PREFIX "QS_APEX_"

void CleanVisualObjects()
{
   ObjectsDeleteAll(0, OBJ_PREFIX);
}

void DrawOrderBlockBox(string name, datetime t1, double p1, datetime t2, double p2, color boxColor)
{
   if(!InpDrawOrderBlocks) return;
   string objName = OBJ_PREFIX + name;
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

void DrawTradeMarker(string name, datetime t, double p, bool isBuy)
{
   if(!InpDrawTradeArrows) return;
   string objName = OBJ_PREFIX + "TRADE_" + name;
   int arrowCode = isBuy ? 233 : 234;
   color arrowColor = isBuy ? clrDeepSkyBlue : clrOrangeRed;
   ObjectDelete(0, objName);
   if(ObjectCreate(0, objName, OBJ_ARROW, 0, t, p))
   {
      ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, arrowCode);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, arrowColor);
      ObjectSetInteger(0, objName, OBJPROP_WIDTH, 2);
   }
}

void SendQuantAlert(string title, string msg)
{
   string fullMsg = "⚡ [QuantumSniper Apex 7.0]\\n" + title + "\\n" + msg;
   if(InpSendPopAlerts) Alert(fullMsg);
   if(InpSendPushAlerts) SendNotification(fullMsg);
   Print("📢 QUANT ALERT: ", title, " | ", msg);
}
"""

code = code.replace("//--- GLOBAL OBJECTS & HANDLES ---", helper_funcs + "\n//--- GLOBAL OBJECTS & HANDLES ---")

# 4. CleanVisualObjects on Init and Deinit
code = code.replace("g_tradeCountDay = m_currentDay;", "g_tradeCountDay = m_currentDay;\n   CleanVisualObjects();")
code = code.replace('Comment("");', 'CleanVisualObjects();\n   Comment("");')

# 5. Connect DrawOrderBlockBox into DetectLuxAlgoSMC
bull_ob_trigger = "bullishOB = true;"
bull_ob_replace = """bullishOB = true;
               DrawOrderBlockBox("DEMAND_OB", rates[i].time, rates[i].high, rates[0].time + PeriodSeconds()*10, rates[i].low, InpDemandOB_Color);"""
code = code.replace(bull_ob_trigger, bull_ob_replace)

bear_ob_trigger = "bearishOB = true;"
bear_ob_replace = """bearishOB = true;
               DrawOrderBlockBox("SUPPLY_OB", rates[i].time, rates[i].high, rates[0].time + PeriodSeconds()*10, rates[i].low, InpSupplyOB_Color);"""
code = code.replace(bear_ob_trigger, bear_ob_replace)

# 6. Connect DrawTradeMarker and Alerts
buy_block_old = """g_lastSignalReason = "🚀 BUY Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);"""

buy_block_new = """g_lastSignalReason = "🚀 BUY Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            DrawTradeMarker("BUY_" + IntegerToString(TimeCurrent()), TimeCurrent(), entryPrice, true);
            string alertBuy = "Symbol: " + _Symbol + "\\nType: BUY 🟢\\nEntry: " + DoubleToString(entryPrice, _Digits) +
                              "\\nSL: " + DoubleToString(sl, _Digits) + "\\nTP: " + DoubleToString(tp, _Digits) +
                              "\\nR:R: 1:" + DoubleToString(InpRiskRewardRatio, 1);
            SendQuantAlert("🚀 TRADE OPENED [BUY]", alertBuy);
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);"""
code = code.replace(buy_block_old, buy_block_new)

sell_block_old = """g_lastSignalReason = "🔻 SELL Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);"""

sell_block_new = """g_lastSignalReason = "🔻 SELL Executed (H1:" + g_htfBias + ")";
            g_initialRisk = riskPoints;
            g_trackedTicket = m_trade.ResultOrder();
            DrawTradeMarker("SELL_" + IntegerToString(TimeCurrent()), TimeCurrent(), entryPrice, false);
            string alertSell = "Symbol: " + _Symbol + "\\nType: SELL 🔴\\nEntry: " + DoubleToString(entryPrice, _Digits) +
                               "\\nSL: " + DoubleToString(sl, _Digits) + "\\nTP: " + DoubleToString(tp, _Digits) +
                               "\\nR:R: 1:" + DoubleToString(InpRiskRewardRatio, 1);
            SendQuantAlert("🔻 TRADE OPENED [SELL]", alertSell);
            Print(g_lastSignalReason, " at ", entryPrice, " | SL: ", sl, " | TP: ", tp);"""
code = code.replace(sell_block_old, sell_block_new)

# 7. Update HUD Title
code = code.replace("⚡ QUANTUM SNIPER v6.0 INSTITUTIONAL ⚡", "⚡ QUANTUM SNIPER v7.0 APEX EDITION ⚡")

# 8. Save as QuantumSniper_v7_Apex.mq5
target_path = r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\QuantumSniper_v7_Apex.mq5"
with open(target_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Saved cleanly! Length:", len(code))
