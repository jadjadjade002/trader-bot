# R4 preregistration: M1 EMA state transition

R4 is the final historical family search. It trades only a new fast/slow EMA state transition and excludes breakout levels, sweeps, impulses, higher-timeframe pullbacks, VWAP, and statistical fades. The research source is 2025-08-11 through 2025-11-30 broker time. August 11 through September 7 is warm-up only. December 8 onward and all existing result files are excluded.

## Signal

Completed M1 closes form conventionally seeded recursive EMAs and Wilder ATR(14). Every signal requires the latest 120 M1 bars to be consecutive. `ATRmed120` is the median of the 120 causal ATR values and `vol_ratio = ATR14 / ATRmed120`.

Nominal uses EMA 6/24. Long requires EMA6 to cross strictly above EMA24 after being at or below it on the prior bar. Short is mirrored. Require `0.50 <= vol_ratio <= 1.50`, close no farther than `0.35 ATR` from the slow EMA, and bar range no greater than `1.50 ATR`. A rejected crossover cannot enter late.

Robustness-only pairs are EMA 5/20 and 8/32. They may veto nominal but cannot replace it.

## Execution proxy

Enter at the next consecutive M1 open from 18:00 through 01:56 with spread at most 40 points. Exit at the third completed M1 close. Outcomes cannot overlap and signal through exit must be consecutive. Longs pay entry spread and shorts pay exit spread. Stress charges twice the observed spread.

## Walk-forward folds

- Train September 8–October 5, validate October 6–19.
- Train September 22–October 19, validate October 20–November 2.
- Train October 6–November 2, validate November 3–16.
- Train October 20–November 16, validate November 17–30.

Training outcomes must finish before each boundary and validation begins after a three-M1-bar embargo. Nominal requires 35 training trades per fold before that fold's validation can be opened.

## Strong gates

Nominal requires all training guards, at least 70 validation trades and 10 per fold, every fold profitable, aggregate PF at least 1.20, drawdown at most 15%, positive-day concentration at most 35%, positive expectancy at twice spread, and daily-net t-statistic at least 2.50 using at least 20 days. Both robustness pairs require at least 50 trades, positive expectancy, PF at least 1.10, and three profitable folds.

Any failure abandons R4. If it fails, historical strategy-family searching stops. The project moves to execution diagnostics and genuinely future untouched data rather than another historical hypothesis.
