//+------------------------------------------------------------------+
//|                                                Test_Module3.mq5  |
//|           Adversarial Test Rig for Module 3 Dynamic Grid         |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "1.00"

#include "..\Include\QuantumTitan\DynamicGrid.mqh"

CDynamicGridEngine g_grid;

int OnInit()
{
   if(!g_grid.Init(_Symbol, 770700, 0.01, 4, 1.0, 1.25, 60.0))
   {
      Print("Init failed!");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnTick()
{
   double atrDummy = 100 * _Point;
   g_grid.CheckAndCloseBasket(atrDummy);
   g_grid.EvaluateGridStep(atrDummy, true, true);
}
