# v20 and first data-research validation

## Decision

Version 20 and the first data-derived signal family both failed their frozen development gates. Neither is eligible for holdout testing, EA implementation, or deployment. Version 16 on the VM remains unchanged.

## v20 exhaustion branch

The single development run produced 127 completed trades, 50 net-cost wins, a 39.37% win rate, USD -42.99 net profit, profit factor 0.546, and 85.98% relative equity drawdown. It passed runtime safety only and failed the trade-count, profitability, profit-factor, and drawdown gates. The v20 branch is terminated.

## Reusable local research pipeline

The no-trade exporter compiled with zero errors and zero warnings and produced 19,799 completed XAUUSD M1 bars inside the requested 2026-08-03 to 2026-08-22 development interval. The isolated MT5 run used real ticks, 200 ms execution delay, and local agents only. The pipeline records source, binary, and CSV hashes and rejects stale builds, duplicate or unordered timestamps, invalid OHLC values, and bars outside the requested interval.

The analyzer uses only Python's standard library. It calculates causal Wilder ATR(14), reports market gaps without filling them, and separates the data chronologically into 70% selection and 30% validation with a three-bar embargo. All eight focused tests pass.

## Frozen impulse-continuation family

The only tested family enters at the next bar's open after a completed candle whose body is at least 0.75, 1.00, or 1.25 ATR and whose close is in the outer 20% of its range. It exits after three bars and applies a spread-adjusted return proxy. Threshold selection used only the first 70% of the development data. The last 30% was evaluated once for the selected 1.00 ATR threshold.

The selected threshold produced 259 training outcomes, USD 39.61 proxy net, and profit factor 1.190 in selection. It then produced 121 validation outcomes, USD -26.50 proxy net, profit factor 0.797, 61.36% drawdown proxy, and 97.2% concentration in its largest positive day. It failed every validation quality gate despite having enough observations.

## Conclusion

The impulse-continuation family is abandoned without tuning or reuse of the validation segment. No v21 EA will be created from it. The exported dataset and pipeline remain reusable for a future, materially different, preregistered hypothesis.
