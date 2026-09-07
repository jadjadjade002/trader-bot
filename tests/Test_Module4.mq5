//+------------------------------------------------------------------+
//|                                                Test_Module4.mq5  |
//|         Adversarial Test Rig for Module 4 Risk Guardian          |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "1.00"

#include "..\Include\QuantumTitan\RiskGuardian.mqh"

CRiskGuardian g_risk;

int OnInit()
{
   if(!g_risk.Init(_Symbol, 770700, 8.0, 30.0, 12, 3, 45.0, true, 30, 30))
   {
      Print("Init failed!");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnTick()
{
   RiskTelemetry rTelem;
   bool canTrade = g_risk.ValidateExecution(rTelem);
   PrintFormat("CanTrade: %s, DailyDD: %.2f%%, Reason: %s",
      (canTrade ? "YES" : "NO"), rTelem.currentDrawdownPct, rTelem.rejectReason);
}
