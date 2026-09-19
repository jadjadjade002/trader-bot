# R3 preregistration: session-VWAP statistical fade

R3 is a session-distribution mean-reversion family frozen before exporting or inspecting its research period. It uses XAUUSD M1 from 2025-12-08 through 2026-03-29 broker time. December 8 through January 4 is warm-up and audit context only. April 6 onward and all existing result files are excluded.

## Causal statistics and signal

The session runs from 18:00 to 02:00 broker time, with bars after midnight assigned to the preceding session date. From the complete 18:00 bar through each signal bar, calculate tick-volume-weighted typical-price VWAP and weighted population standard deviation. Every intervening M1 bar must exist. Require at least 30 session bars, positive total tick volume, and positive standard deviation. The z-score is `(close - VWAP) / sigma`.

Deceleration means the absolute latest close change is no greater than the median of the latest 20 absolute one-minute close changes. All 21 required closes must be consecutive and the median must be positive.

A long signal requires `z <= -Z`, `close[t] < close[t-3]`, and deceleration. A short signal mirrors these conditions. There is no candle confirmation, sweep, reclaim, breakout, ATR impulse, or trend filter.

The variants are loose `Z=1.25`, nominal `Z=1.50`, and strict `Z=1.75`. Nominal is fixed. Loose and strict are robustness vetoes and cannot be promoted.

## Execution proxy

Enter at the next consecutive M1 open from 18:30 through 01:56 with entry spread no greater than 40 points. Exit at the close of the third complete M1 bar after entry. Opportunities cannot overlap and all signal-to-exit bars must be consecutive. Longs pay entry spread and shorts pay exit spread. Stress results charge 1.5 times the observed spread.

## Walk-forward protocol

- Train January 5–February 1, validate February 2–15.
- Train January 19–February 15, validate February 16–March 1.
- Train February 2–March 1, validate March 2–15.
- Train February 16–March 15, validate March 16–29.

Training outcomes must finish before each validation boundary. Validation begins after a three-M1-bar embargo. All variants run on training first. A fold with fewer than 35 nominal training trades does not expose validation.

## Gates and stopping

All four training guards, at least 70 aggregate nominal validation trades, at least 10 nominal trades per validation fold, positive aggregate expectancy, profit factor at least 1.10, drawdown no greater than 20% from USD 50 proxy equity, at least three profitable folds, positive-day concentration no greater than 50%, positive nominal expectancy at 1.5 times spread, and positive loose and strict aggregate expectancy must all pass.

Any failure abandons R3. Results cannot justify inversion, parameter changes, robustness promotion, added filters, date changes, exit changes, or weaker gates.
