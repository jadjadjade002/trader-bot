# R2 preregistration: trend pullback continuation

This exploratory protocol was frozen before exporting or inspecting its research period. It uses XAUUSD M1 bars from 2026-04-06 through 2026-07-26 broker time. April 6 through May 3 is indicator warm-up only. August 3 onward and previous result files are excluded.

## Causal signal

Raw M1 bars are aggregated into complete, gap-free broker-clock M5 and M15 buckets. A higher-timeframe bucket becomes usable only after its last M1 constituent closes. M15 EMA values use an arithmetic seed followed by the standard recursive EMA. M15 ATR(14) uses Wilder smoothing and a mean true-range seed.

For a long trend, the latest completed M15 close must be above EMA20, EMA20 must be above EMA50, EMA20 must exceed its value two completed M15 bars earlier, and `(EMA20 - EMA50) / ATR14` must be at least `S`. A short trend mirrors every comparison.

A long M5 pullback requires the minimum low of the two latest completed M5 bars to touch or cross EMA20 while remaining above EMA50, followed by the latest M5 close at or above EMA20. A short pullback is the exact mirror.

A long M1 reacceleration bar must close above its open and strictly above the highs of the prior two M1 bars, with its close in the upper 30% of its range. A short signal is mirrored. Zero-range or nonconsecutive bars are invalid.

## Frozen variants and execution proxy

Only the M15 normalized separation varies: loose `S=0.05`, nominal `S=0.10`, and strict `S=0.15`. Nominal is fixed as the candidate. Loose and strict are robustness vetoes and cannot replace it.

Entry is the next consecutive M1 open between 18:00 and 01:56 broker time with spread at most 40 points. Exit is the close of the third complete M1 bar after entry. Opportunities cannot overlap and any missing minute from signal through exit invalidates the opportunity. Longs pay entry spread and shorts pay exit spread. Returns are a research proxy using 0.01 XAU lot as one-ounce exposure, not an execution backtest.

## Walk-forward protocol

Four fixed folds use four training weeks followed by two validation weeks:

- Train May 4–May 31, validate June 1–June 14.
- Train May 18–June 14, validate June 15–June 28.
- Train June 1–June 28, validate June 29–July 12.
- Train June 15–July 12, validate July 13–July 26.

Every boundary has a three-M1-bar purge. All three variants are evaluated on training first. If nominal has fewer than 35 training trades in any fold, the protocol terminates without opening that fold's validation. There is no fitted parameter or winner selection.

## Advancement gates

The four nominal validation streams are concatenated chronologically. Every gate must pass:

- At least 140 aggregate validation trades.
- Positive net expectancy after observed spread.
- Profit factor at least 1.10.
- Relative drawdown no greater than 20% from USD 50 starting proxy equity.
- At least three of four validation folds profitable.
- No positive day contributes more than 50% of all positive-day profit.
- Expectancy remains positive with charged spreads multiplied by 1.5.
- Loose and strict variants both retain positive aggregate validation expectancy.

Run the protocol once. Any failure abandons R2. Results may not justify inversion, session changes, formula changes, sensitivity selection, exit changes, date changes, or weaker gates. A later attempt requires a materially different mechanism and a previously unused pre-August-3 interval.
