---
name: quant-risk-guardian
description: Institutional quantitative risk management and capital preservation protocols for trading bots. Covers High-Water Mark equity drawdown tracking, hard equity circuit breakers, ATR volatility position sizing, losing streak pauses, and session-based exposure controls.
---

# Quant Risk Guardian Skill

## Capital Preservation & Execution Gating

### 1. Circuit Breakers (Tripwires)
1. **Daily Drawdown Auto-Kill Switch:** Measure decline from starting equity of the day. Lock out further trades if daily drawdown hits threshold (e.g. 8-10%).
2. **Hard Equity Floor:** If total account equity falls below a critical safety floor (e.g. \.00 on a \ account), permanently halt all EA operations to guarantee capital survival.
3. **Losing Streak Circuit Breaker:** Track consecutive losses from deal history. If losing streak reaches 3 consecutive stops, engage mandatory cool-down to prevent tilt.
4. **Max Trades Per Day:** Cap total executions (e.g. 12-15 trades/day) to prevent overtrading during choppy sideways days.

### 2. Session & Weekend Gap Guards
- **London & New York Sessions (13:00 - 23:00 Server Time):** High liquidity and genuine institutional directional momentum.
- **Friday Night Lockout:** Never initiate new positions after Friday 20:00 server time to avoid unpredictable weekend gaps on Monday market open.
