//+------------------------------------------------------------------+
//|                                                Test_Module1.mq5  |
//|               Adversarial Test Rig for Module 1 Alpha Scoring    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Institutional Quant Lab"
#property link      "https://github.com/jadjadjade002/trader-bot"
#property version   "1.00"

#include "..\Include\QuantumTitan\AlphaScoring.mqh"

CAlphaScoringEngine g_alpha;

int OnInit()
{
   if(!g_alpha.Init(_Symbol, PERIOD_CURRENT, PERIOD_H1))
   {
      Print("Init failed!");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   g_alpha.Deinit();
}

void OnTick()
{
   AlphaScoreTelemetry telemetry;
   ENUM_ALPHA_SIGNAL sig = g_alpha.EvaluateSignals(telemetry);
   if(sig != ALPHA_SIGNAL_NONE)
   {
      PrintFormat("Signal: %s, BuyScore: %d, SellScore: %d, Regime: %s",
         (sig == ALPHA_SIGNAL_BUY ? "BUY" : "SELL"),
         telemetry.totalScoreBuy,
         telemetry.totalScoreSell,
         telemetry.regimeName);
   }
}
