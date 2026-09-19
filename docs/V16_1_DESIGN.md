# QuantumTitan V16.1 M1 Architecture & Design Specification

**Status**: Candidate Implemented & Verified  
**Author**: Chief Engineer / Quant Architecture Team  
**Date**: 2026-09-11  
**Target Symbol**: XAUUSD  
**Timeframe**: M1  
**Architecture Base**: `QuantumTitan_v16_Velocity.mq5` (M1 Fast Scalper)  

---

## 1. Executive Summary & Objective

`QuantumTitan_v16_1_M1` is a dedicated single-position high-confidence scalper designed for XAUUSD M1. It evolves directly from the battle-tested `Velocity M1` core, preserving its high responsiveness while eliminating the failure modes and statistical vulnerabilities identified during live observation on account `112334471`.

### Key Improvements over V16 Baseline
1. **Multi-Gate Confidence Scoring**: Trades execute only when a composite multi-gate confidence score meets or exceeds 70/100 points.
2. **Expanded Take Profit (1:1 R:R)**: TP is expanded from 180 points ($1.80) to 260 points ($2.60), balancing risk/reward with the 260-point SL.
3. **Slower, Safer Breakeven**: Activation threshold is widened from 85 points ($0.85) to 130 points ($1.30, 0.5R), with a 20-point lock ($0.20), preventing trades from being choked by normal market fluctuation.
4. **Noise & Volatility Gate**: Requires M1 ATR(14) $\ge$ 80 points ($0.80), rejecting flat/dead sessions.
5. **Strict Spread Gate**: Spread ceiling tightened from 60 points to 35 points.
6. **Anti-Whipsaw Cooldown**: Extended from 1 bar to 3 M1 bars (180 seconds) after position closure.
7. **Transparent Audit Logging**: `OnTradeTransaction` explicitly logs realized Net PnL, profit, swap, and commission.
8. **Isolation & Safety**: Locked to DEMO mode; dedicated magic number `991612` with auto-collision override.

---

## 2. V16 Empirical Failure Analysis

The empirical review of `deploy/v16_20260910_mql5.log` and the V16 source code revealed five distinct failure modes:

| Failure Mode | Observed Behavior in V16 | Root Cause | V16.1 Design Resolution |
| :--- | :--- | :--- | :--- |
| **1. Sub-1.0 R:R Ratio** | TP = 180 pts, SL = 260 pts ($R = 0.692$). | Low reward target created high break-even winrate requirement (>59.1% before spread). Spread (30-45 pts) consumed 25% of gross profit. | TP expanded to **260 pts** ($R = 1.0$). Reward matches risk, requiring only 50% baseline winrate. |
| **2. Premature Breakeven Choke** | 12 out of 13 trades triggered BE within 1.5 hours; many stopped at +15 pts. | 85 points ($0.85) is smaller than the typical Gold M1 candle range ($1.00-$2.50). Normal minor retests closed trades prematurely. | BE Trigger moved to **130 pts** ($1.30 / 0.5R$) with **20 pts** lock buffer. Provides breathing room for trend expansion. |
| **3. Chop Whipsaw Re-entry** | Repeated scalp opens shortly after exit in consolidation regimes. | Cooldown was only 1 M1 bar (60s). Allowed immediate re-entry into the same range. | Cooldown widened to **3 M1 bars** (180s) plus ATR noise floor filter ($\ge 80$ pts). |
| **4. Modify Race Conditions** | Log Line 28: `CTrade::OrderSend: modify position ... [position closed]`. | Fast tick arrivals caused position modify requests to reach broker after position was already stopped out. | Pre-check position validity, check broker `STOPS_LEVEL`, and gracefully capture modify results without warnings. |
| **5. Log PnL Opacity** | Velocity close logs only printed `Deal #... closed; cooldown started` without dollar values. | No query to history deals for realized net profit. | Implemented explicit deal profit extraction in `OnTradeTransaction` logging dollar net PnL. |

---

## 3. Comparison Specification: V16 vs V16.1

```text
Parameter                V16 Velocity Baseline     V16.1 M1 Candidate        Design Impact
----------------------------------------------------------------------------------------------------
Timeframe                M1                        M1                        Identical execution speed
Magic Number             991602                    991612                    Strict isolation from Apex/Velocity
Order Architecture       Single Position           Single Position           No grid, no martingale, no averaging
Base Lot                 0.01                      0.01                      Strict micro-risk preservation
Take Profit              180.0 pts ($1.80)         260.0 pts ($2.60)         +44.4% reward expansion (1.0R)
Stop Loss                260.0 pts ($2.60)         260.0 pts ($2.60)         Risk boundary maintained
Expected R (TP/SL)       0.69 R                    1.00 R                    Mathematically balanced R:R
Breakeven Trigger        85.0 pts ($0.85)          130.0 pts ($1.30)         +52.9% wider breathing room
Breakeven Lock           15.0 pts ($0.15)          20.0 pts ($0.20)          Covers commission + minor slippage
Max Allowed Spread       60.0 pts ($0.60)          35.0 pts ($0.35)          Blocks execution during wide spreads
Post-Exit Cooldown       1 M1 bar (60s)            3 M1 bars (180s)          Triple anti-whipsaw delay
Min ATR Floor            None                      80.0 pts ($0.80)          Rejects flat/dead market noise
Confidence Threshold     Single indicator check    Multi-gate score >= 70    Strict multi-confluence requirement
Audit Logging            Ticket number only        Explicit Net PnL ($)      Full transparency in expert log
Demo Guard               Yes (InpDemoOnly)         Yes (InpDemoOnly)         Hard block against live account
```

---

## 4. Multi-Gate Confidence Scoring Algorithm

The entry decision is governed by an objective 100-point scoring model evaluated exclusively on the closed candle (`Bar 1`):

$$\text{ConfidenceScore} = G_{\text{trend}} + G_{\text{retest}} + G_{\text{pa}} + G_{\text{vol}} + G_{\text{rsi}}$$

An order is triggered only when $\text{ConfidenceScore} \ge \text{InpMinConfidenceScore}$ (default: 70).

### Gate 1: Trend Alignment (+25 Points)
- **BUY**: $\text{EMA}_{14} > \text{EMA}_{50}$ AND $\text{Close}[1] > \text{EMA}_{50}$.
- **SELL**: $\text{EMA}_{14} < \text{EMA}_{50}$ AND $\text{Close}[1] < \text{EMA}_{50}$.
- *Rationale*: Guarantees trade alignment with both short-term momentum and baseline intraday trend.

### Gate 2: Quantified Pullback & Retest (+25 Points)
- **Tolerance**: $\Delta_{\text{tol}} = \max(15.0 \text{ pts}, 0.25 \times \text{ATR}_{14})$.
- **BUY**: $\text{Low}[1] \le \text{EMA}_{14} + \Delta_{\text{tol}}$.
- **SELL**: $\text{High}[1] \ge \text{EMA}_{14} - \Delta_{\text{tol}}$.
- *Rationale*: Eliminates chasing moves in mid-air; ensures trade enters during a legitimate retest zone.

### Gate 3: Price Action Rejection (+20 Points)
- **BUY**: Lower Wick Ratio $\ge 25\%$ of candle range OR Bullish Close ($\text{Close}[1] > \text{Open}[1]$).
- **SELL**: Upper Wick Ratio $\ge 25\%$ of candle range OR Bearish Close ($\text{Close}[1] < \text{Open}[1]$).
- *Rationale*: Confirms buying/selling pressure off the EMA dynamic support/resistance.

### Gate 4: Volatility & Squeeze Momentum (+15 Points)
- **BUY**: LazyBear Squeeze Momentum $> -0.02$ OR Squeeze Breakout active.
- **SELL**: LazyBear Squeeze Momentum $< 0.02$ OR Squeeze Breakout active.
- *Rationale*: Prevents counter-momentum trades during strong adverse expansions.

### Gate 5: RSI Regime Filter (+15 Points)
- **BUY**: $45.0 \le \text{RSI}(14) \le 65.0$.
- **SELL**: $35.0 \le \text{RSI}(14) \le 55.0$.
- *Rationale*: Filters out overextended exhaustion peaks (avoids buying at RSI > 70 or selling at RSI < 30).

---

## 5. Execution & Safety Protocols

1. **Pre-Tick Gate Sequence**:
   ```mermaid
   graph TD
       A[New Tick] --> B{Active Scalp?}
       B -- Yes --> C[Manage Position / Breakeven]
       B -- No --> D{Cooldown Active?}
       D -- Yes --> Z[Exit]
       D -- No --> E{Spread <= 35 pts?}
       E -- No --> Z
       E -- Yes --> F{ATR >= 80 pts?}
       F -- No --> Z
       F -- Yes --> G{New M1 Bar?}
       G -- No --> Z
       G -- Yes --> H[Evaluate Multi-Gate Score]
       H --> I{Score >= 70?}
       I -- No --> Z
       I -- Yes --> J{Free Margin >= $50?}
       J -- No --> Z
       J -- Yes --> K[Execute 0.01 Lot Scalp with SL & TP]
   ```
2. **Breakeven Modification Protocol**:
   - Compares distance between target SL and current market price against broker `SYMBOL_TRADE_STOPS_LEVEL`.
   - Modifies position only once per breakeven event.
   - Logs full confirmation and handles broker error codes gracefully.
3. **Transparent Audit Logging**:
   - In `OnTradeTransaction`:
     ```mql5
     double netPnl = profit + comm + swap;
     PrintFormat("🎯 [V16.1 M1 Audit] Deal #%I64u CLOSED | Net PnL: $%+.2f (Profit: $%.2f, Comm: $%.2f, Swap: $%.2f)", ...);
     ```

---

## 6. Architecture Boundary & Prohibitions

- **No Apex Modules**: Does not import or depend on `AlphaScoring.mqh`, `DynamicGrid.mqh`, or `TrailingSafety.mqh`.
- **No Grid or Recovery**: Strictly 1 position at any time.
- **No Martinagle**: Lot size fixed at `InpBaseLot` (0.01).
- **Single Magic Number**: Operates under `InpMagicNumber` (default `991612`), completely isolated from `991602` (Velocity) and `991605` (Apex).
