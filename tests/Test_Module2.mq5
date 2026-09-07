//+------------------------------------------------------------------+
//|                                                Test_Module2.mq5  |
//|         Adversarial Test Rig for Module 2 Trailing Safety        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "1.00"

#include "..\Include\QuantumTitan\TrailingSafety.mqh"

CTrailingSafetyEngine g_trailing;

int OnInit()
{
   if(!g_trailing.Init(_Symbol, 770700, 0.4, 1.2, 0.6))
   {
      Print("Init failed!");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnTick()
{
   double atrDummy = 100 * _Point;
   g_trailing.UpdateTrailing(atrDummy);
}
