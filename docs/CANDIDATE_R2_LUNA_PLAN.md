# Candidate R2 signal plan

Date: 2026-10-07  
Role: signal research design only. No implementation or backtest outcomes used.

## Scope and frozen conditions

Mode 0 remains exact V24. R1 already covers one-bar continuation, stronger V24 reclaim, and close beyond the previous ten-bar extreme. R2 modes are fixed: 0 exact V24, 1 R2-A, 2 R2-B, 3 R2-C, 4 R2-D, 5 R2-E. R2 candidates below test other mechanisms, not cosmetic variants of R1. Each family has exactly two entry presets; test 10 family/preset configurations total, with no per-family exit grid.

For every R2 rule, evaluate once on the first tick of a new M1 bar, using only completed candles (shift >= 1). Candle `s1` means latest completed M1 bar; `s2...` are older. Compute ATR14 from completed M1 bars. Any missing/non-finite input, nonpositive ATR, invalid OHLC bounds or volume, noncontiguous required history, stale `s1` timestamp, bad quote, or existing entry gate failure means no signal. R2 candles must be contiguous 60-second bars; family predicates reject `s1` range > 2 ATR. BUY and SELL are exact sign mirrors. Entry quote gates stay the existing V24 limits: spread <= 0.10 M1 ATR; absolute quote midpoint minus `s1.close` <= 0.50 M1 ATR.

All price distances below are multiples of M1 ATR14 unless otherwise stated. Freeze exits and risk at V24 values: SL 1.5 ATR, TP 2R, 60 M1-bar maximum hold, BE off, 0.01 lot, 150-point minimum SL, hard broker SL, margin gate, one position at a time, and existing four-loss/90-minute circuit breaker. No exit grid, trailing stop, sizing, or per-family exit changes. Reject harness settings that change these values.

## Candidate families

Every family uses only two presets at most. Thresholds are frozen below before implementation. Parameter count means variable axes, not derived calculations.

### R2-A: M5 trend pullback to EMA20

Distinct question: does a deeper pullback to the slower M1 mean offer better location than V24's EMA9 touch?

- Regime: closed M5 EMA20 > EMA50 and EMA20 > EMA20 from five completed M5 bars earlier for BUY; exact inverse for SELL. EMA separation >= 0.10 * closed M5 ATR14. Closed M1 EMA9 must be on the trend side of EMA20.
- Setup and trigger: `s1` overlaps EMA20 (BUY: low <= EMA20 and high >= EMA20), has trend-colored close (BUY: close > open), and closes at least `b * ATR` beyond EMA20 (BUY: close >= EMA20 + b*ATR). SELL mirrors all inequalities.
- Chase guard: absolute `s1.close - EMA9` <= 0.75 * ATR; standard midpoint chase gate also applies.
- Bounded axis: reclaim buffer `b ∈ {0.00, 0.10}`. One axis, two configs.
- Preset mapping: `InpEntryStrength=0` selects `b=0.00`; `1` selects `b=0.10`.
- Main false positives: persistent breakdown through EMA20 mistaken for pullback; signal bar already extended relative to EMA9; trend change within slow M5 filter lag.

### R2-B: Volatility compression then directional expansion

Distinct question: can a quiet, directional coil resolve into continuation without requiring a ten-bar breakout predicate?

- Regime: same closed M5 trend and alignment gates as R2-A.
- Compression: on `s2..s4`, each full M1 range <= 0.80 * its own completed ATR14; combined high-low envelope <= 1.50 * ATR14 at `s2`.
- Trigger: `s1` closes in trend direction beyond the `s2..s4` envelope by at least `b * ATR14(s1)`. Favorable close location >= 0.70 (BUY `(close-low)/(high-low)`; SELL `(high-close)/(high-low)`). Reject zero range and range > 2.0 * ATR.
- Bounded axis: envelope break buffer `b ∈ {0.00, 0.05}`. One axis, two configs. Compression thresholds fixed, not optimized.
- Preset mapping: `InpEntryStrength=0` selects `b=0.00`; `1` selects `b=0.05`.
- Main false positives: low-activity feed periods, spread widening on expansion, one-bar news spikes, and apparent coil caused by missing bars. Missing/irregular bars must fail closed.

### R2-C: Failed-range-break reversal

Distinct question: do failed excursions outside a mature local range produce a symmetric reversal entry?

- Regime: range-only. Over prior 20 completed M1 bars `s2..s21`, range width must be 2.0..6.0 * current ATR14. Closed M5 EMA20 slope over five bars must have absolute value <= 0.10 * M5 ATR14, and absolute EMA20-EMA50 separation <= 0.20 * M5 ATR14. These are regime definitions, not tuned axes.
- Setup/trigger: BUY if `s2` low swept below prior range low from `s3..s22` by 0.05..0.50 * ATR, and `s1` closes back above that prior range low, with bullish body and favorable close location >= 0.60. SELL mirrors at range high. Signal bar range <= 2.0 * ATR. Entry is at next-bar executable quote subject to standard chase/cost gate.
- Bounded axis: sweep minimum `w ∈ {0.05, 0.15} ATR`; maximum remains 0.50 ATR. One axis, two configs.
- Preset mapping: `InpEntryStrength=0` selects `w=0.05`; `1` selects `w=0.15`; equality at both minimum and maximum sweep depth is accepted.
- Main false positives: genuine range-to-trend transition, shallow quote noise around range edge, event gaps, and false range classification during slow trends. Record outcomes by subsequent M5 trend transition and entry direction.

### R2-D: Trend pullback then break-retest

Distinct question: after a confirmed local level break, does a retest/rejection entry improve on R1's immediate close-through entry?

- Regime: same closed M5 trend and M1 EMA9/20 alignment as R2-A.
- State machine: a trend-aligned close through the highest high / lowest low of the prior ten completed bars (`s2..s11`), with close at least 0.05 ATR beyond level, arms a setup for exactly the next three M1 bars. A new bar may signal only if `s1` touches the broken level within 0.15 ATR, closes back on the breakout side by at least `b*ATR`, has trend-colored body, and closes no farther than 0.75 ATR from EMA9. Cancel if any completed close crosses back through the level by >0.15 ATR, trend regime invalidates, or three-bar expiry passes. One arm; reject a repeat arm if level differs by no more than one symbol point from last arm.
- Bounded axis: close-back buffer `b ∈ {0.00, 0.05}`. One axis, two configs. Retest tolerance, arm age and invalidation fixed.
- Preset mapping: `InpEntryStrength=0` selects `b=0.00`; `1` selects `b=0.05`.
- Arm state advances on every new completed M1 bar before position/breaker/cost gates, so a blocked signal cannot extend the three-bar expiry. Arm cancels at three completed bars, if M5 trend or M1 EMA alignment fails, if close crosses back through level by >0.15 ATR, or if contiguous-history checks fail. A level within one symbol point of last armed level cannot re-arm; trend-direction change or history gap resets dedup state. State transitions use completed OHLC only; quote cost gate remains mandatory.
- Main false positives: repeated level touches counted as separate signals, stale arms, intrabar ordering ambiguity, and retest candle that technically touches only by spread.

### R2-E: Trend exhaustion snapback

Distinct question: can a locally overextended move reverse in the direction of the higher-timeframe trend after a failed push?

- Regime: same closed M5 trend, but M1 EMA9/20 may be temporarily crossed during the pullback; M5 direction remains mandatory.
- Setup/trigger: over prior five completed bars ending at `s2`, signed displacement from close five bars before to `s2.close` must be >= 1.25 ATR in the direction opposite the M5 trend. `s2` or `s3` must make a 10-bar extreme in that countertrend direction. `s1` then closes back across EMA9 in the M5 trend direction, has trend-colored body, and favorable close location >= 0.70. Entry-side distance from EMA9 <= 0.25 ATR to avoid chasing the snapback. SELL mirrors BUY.
- Bounded axis: countertrend displacement threshold `x ∈ {1.25, 1.75} ATR`. One axis, two configs. Extreme window and confirmation fixed.
- Preset mapping: `InpEntryStrength=0` selects `x=1.25`; `1` selects `x=1.75`.
- Main false positives: orderly countertrend transition rather than exhaustion, one-bar reversal against a still-accelerating move, and ATR jump reducing normalized displacement. Attribute by subsequent M5 trend flip and adverse excursion.

## Recommended order and bounded test plan

1. R2-A first: simplest extension of current trend family; tests pullback depth with two configs.
2. R2-D next: clear two-stage hypothesis and useful comparison against R1 breakout; implementation needs explicit arm state and reset tests.
3. R2-B: tests compression and expansion with compact predicates.
4. R2-C: distinct range regime and reversal; lower prior because range classification can be fragile.
5. R2-E: lower prior due rare setup and possible trend reversal ambiguity.

Cap initial R2 at these 10 signal configurations plus exact V24 parity mode. No Cartesian products between families, axes, strength presets or exits. Do not optimize threshold grids after viewing results. Keep SL=1.5 ATR, TP=2R, lot=0.01, hold cap=60, BE off, breaker, margin and hard SL frozen across modes. Compare R2 with Mode0 and the already predeclared R1 modes using identical dates, broker ticks, spread, 200 ms delay, deposit, leverage, and gate settings.

Candidate selection follows `V25_RESEARCH_PROTOCOL_20261007.md`: development only `[2025-12-01,2026-06-01)`, validation `[2026-06-01,2026-08-01)`, historical confirmation `[2026-08-01,2026-10-01)`. May-September was already seen and is contaminated for fresh holdout claims. No full-result selection. Preserve per-month coverage and native tick provenance. If a family lacks adequate trades or fails its predeclared gates, report failure; do not add neighboring parameter values.

## False-positive and implementation checks

Before any economic comparison, test rule behavior with hand-authored OHLC fixtures and full native logs:

- Sign symmetry: reflect OHLC around a constant price and invert M5 trend; candidate direction must invert, trigger bars and normalized distances must match.
- Closed-bar causality: alter bar 0 and later prices while holding completed history fixed; candidate signal must not change. Verify exact use of shifts and no indicator's current-bar value.
- Boundary checks: values exactly on each threshold, one tick inside/outside, zero-range bars, gaps, negative/non-finite ATR, and insufficient history.
- Frequency and diagnostics: signals / 10,000 eligible bars by month, long/short count, rejection reason, overlap with R1/V24, and concentration around session changes and large-range candles.
- Cost gate: spread just below/equal/above 0.10 ATR; quote midpoint distance just below/equal/above 0.50 ATR. No cost-gate bypass in range or stateful modes.
- R2-D state tests: exact three-bar expiry, cancellation on close through level, no duplicate arm, trend loss cancellation, restart/reset behavior, and one-position rule.
- R2-C regime tests: boundary width, flat-slope threshold equality, sweep depth boundaries, range break that does not close back in, and trend-transition false positive attribution.
- These local checks are source-contract checks and hand-authored edge-fixture coverage only. They do not run or compile MQL and do not establish EA runtime behavior. Native integrity is still required before economic comparison: Mode0 ordered order/deal parity to frozen V24; same 0.01 lot, SL/TP calculation, hard SL, margin gate, one position, breaker and 60-bar exit. Preserve raw logs and reconcile deals by position ID including profit, commission, swap and fee.

All outputs are research findings only. Positive backtest results do not promise profit, do not justify live/VM deployment, and do not support introducing V25 identity into the deployed artifact before evidence review.
