//+------------------------------------------------------------------+
//|                                                Test_Module5.mq5  |
//|         Adversarial Test Rig for Module 5 Telemetry HUD          |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "1.00"

#include "..\Include\QuantumTitan\TelemetryHUD.mqh"

CTelemetryHUD g_hud;

int OnInit()
{
   if(!g_hud.Init(_Symbol, true, false, false))
   {
      Print("Init failed!");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   g_hud.Deinit();
}

void OnTick()
{
   g_hud.RenderHUD("TREND BULL [Institutional]", 85, 20, 2, 0.02, 0, 0.0, 15.50, 100000, 0.0, 99.8, "CLEAR", true, "OPERATIONAL");
}
