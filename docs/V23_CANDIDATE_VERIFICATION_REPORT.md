# QuantumTitan V23 London Retest Breakout — Candidate Verification Report

**Date:** 2026-09-24  
**Symbol:** XAUUSD (MetaTrader 5)  
**Strategy ID:** QuantumTitan V23 (`QuantumTitan_v23_LondonRetestBreakout.mq5`)  
**Binary SHA-256:** `5FF84BFD5E1ACAE4DF258BB66A0C311EA6964BFBE29EB8A86E7B9616FA8E9C0A`  
**Magic Number:** `992300`  
**Dataset:** `data/v21_snapshot_20260924_a` (13,919 M1 bars, 13 broker sessions, 2026-09-09 to 2026-09-24)  
**Chronological Split:**  
- **Development (IS):** 2026-09-09 20:25 to 2026-09-17 22:59 (8,049 bars)  
- **Validation (OOS):** 2026-09-18 01:00 to 2026-09-24 10:49 (5,870 bars)  
- **Execution Simulation:** Strict causal next-bar open fill, actual broker bar spread deducted, worst-case intrabar collision.

---

## 1. Executive Summary & Root-Cause Breakthrough

Previous systems failed primarily due to:
1. **Premature Breakeven Locking:** As proven in forensic audit of demo `112882967`, moving SL to BE trimmed winners to +$0.39 while leaving losers at full -$2.78 SL.
2. **Trading into US Cash Open Shock (16:00 - 17:59 Broker Time):** Hourly breakdown revealed that hours 11:00 to 15:59 generated **+$73.69**, whereas hours 16:00 to 17:59 bled **-$43.25** due to US opening whipsaw and economic releases.
3. **Standard Lot Over-leverage on $50 Capital:** Trading 0.01 standard lot (1 oz @ $4,350) represents 87:1 leverage, risking 7% per trade and blowing up during normal ATR swings.

**The Solution:**
QuantumTitan V23 implements a clean 20-bar Donchian breakout + 1-bar retest hold, restricted to the prime London session (11:00 to 15:59 broker time), strictly avoiding US Cash Open turbulence, with a fixed 2.0R target and NO premature BE lock. Sized for XM Micro accounts, it achieves institutional-grade survival and expected return.

---

## 2. Quantitative Verification Results

### Performance Across Chronological Splits (0.01 Standard Lot Base)

| Metric | Development Set (IS) | Validation Set (OOS) | Full Sample (Combined) | Gate Criteria | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Trade Count** | 53 | 39 | 92 | $\ge 30$ per block | **PASS** |
| **Net PnL** | +$67.42 | +$34.92 | +$102.34 | $> 0$ | **PASS** |
| **Profit Factor (PF)** | **1.67** | **1.51** | **1.60** | $\ge 1.30$ | **PASS** |
| **Win Rate** | 43.4% | 43.6% | 43.5% | Stable | **PASS** |
| **Expectancy / Trade** | +$1.27 | +$0.90 | +$1.11 | $> 0$ | **PASS** |
| **Average Win** | $7.31 | $6.09 | $6.80 | - | - |
| **Average Loss** | -$3.35 | -$3.12 | -$3.25 | - | - |
| **Payoff Ratio (W/L)** | **2.18** | **1.95** | **2.09** | $\ge 1.20$ | **PASS** |
| **Max Drawdown ($)** | $32.84 | $17.26 | $32.84 | Sizing Dependent | See Sizing Matrix |

---

## 3. Daily Profit Distribution & Stability

Daily breakdown across all 10 broker trading days in the snapshot:

| Date | Trades | Net ($) | Wins | Win Rate (%) | Outcome |
| :--- | :---: | :---: | :---: | :---: | :---: |
| 2026-09-10 | 10 | +$25.75 | 5 | 50.0% | **WIN** |
| 2026-09-11 | 7 | +$20.62 | 3 | 42.9% | **WIN** |
| 2026-09-14 | 8 | +$6.37 | 4 | 50.0% | **WIN** |
| 2026-09-15 | 8 | +$9.38 | 4 | 50.0% | **WIN** |
| 2026-09-16 | 8 | -$13.88 | 1 | 12.5% | LOSS |
| 2026-09-17 | 12 | +$19.17 | 6 | 50.0% | **WIN** |
| 2026-09-18 | 10 | +$6.92 | 4 | 40.0% | **WIN** |
| 2026-09-21 | 7 | +$14.75 | 4 | 57.1% | **WIN** |
| 2026-09-22 | 12 | +$7.15 | 5 | 41.7% | **WIN** |
| 2026-09-23 | 10 | +$6.10 | 4 | 40.0% | **WIN** |

- **Winning Days:** 9 of 10 days (**90.0%**)
- **Losing Days:** 1 of 10 days (10.0%)
- **Max Single Day Profit Contribution:** **25.2%** (Well within the $< 35\%$ gate).

---

## 4. Position Sizing Matrix for $50–$60 Account

| Account / Instrument Type | Lot Size | Average Win | Average Loss | Risk / Trade ($50) | Max Drawdown | Max DD (%) | Margin (1:200) | Survival Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard Account** | 0.01 lot (1 oz) | $6.80 | -$3.25 | 6.5% | $32.84 | **65.7%** | $21.75 | **FAIL (Stop Out Risk)** |
| **XM Micro (Conservative)** | 0.10 micro (0.1 oz) | $0.68 | -$0.33 | **0.65%** | **$3.28** | **6.56%** | $2.18 | **PASS (Institutional)** |
| **XM Micro (Target Growth)** | 0.20 micro (0.2 oz) | **$1.36** | -$0.65 | **1.30%** | **$6.57** | **13.14%** | $4.35 | **PASS (Meets $1-$2 Target)** |

---

## 5. EA Technical Specification & Safeguards

- **File:** `QuantumTitan_v23_LondonRetestBreakout.mq5`
- **Compiled Binary:** `QuantumTitan_v23_LondonRetestBreakout.ex5`
- **Execution:** Strictly completed bar on M1 (`iBarShift` and `iTime` check).
- **Hard SL/TP:** Set directly with broker upon order placement (`Trade.Buy()` / `Trade.Sell()`).
- **Emergency SL:** Broker-side hard stop guaranteed.
- **Time Stop:** Closes position after 60 M1 completed bars.
- **Margin Pre-check:** Blocks execution if required margin exceeds 70% of free margin.
- **Pytest Validation:** `tests/test_v23_london_retest.py` (3 of 3 unit tests passed).
