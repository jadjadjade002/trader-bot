---
name: mql5-quant-architect
description: Comprehensive institutional MQL5 architecture and quantitative Expert Advisor engineering guide. Covers multi-timeframe synchronization, event handlers (OnInit, OnTick, OnTimer, OnTradeTransaction), safe trade execution, dynamic filling mode resolution, indicator handle lifecycle management, and zero-error compilation patterns.
---

# MQL5 Quant Architect Skill

## Core Principles of Institutional MQL5 Engineering

### 1. Dynamic Filling Mode Resolution
Never hardcode ORDER_FILLING_FOK. Broker execution modes differ across accounts:
`cpp
uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
if((filling & SYMBOL_FILLING_FOK) != 0) m_trade.SetTypeFilling(ORDER_FILLING_FOK);
else if((filling & SYMBOL_FILLING_IOC) != 0) m_trade.SetTypeFilling(ORDER_FILLING_IOC);
else m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
`

### 2. Stops Level & Freeze Level Safety
Always validate that SL/TP distances conform to broker minimums:
`cpp
long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
double minStopDist = MathMax((double)stopLevel, 30.0) * _Point;
`

### 3. Handle Lifecycle Management
Always release indicator handles in OnDeinit to prevent memory leaks in terminal:
`cpp
void OnDeinit(const int reason)
{
   IndicatorRelease(h_indicator);
   Comment("");
}
`

### 4. Zero-Lag Tick Optimization
Only calculate heavy multi-bar regression, multi-candle loops, and pattern scans on **New Candle Events**, while running SL trailing and risk circuit breakers on **Every Tick**.
