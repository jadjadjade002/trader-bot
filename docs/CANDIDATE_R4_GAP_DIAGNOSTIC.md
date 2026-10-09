# R4 position 388: session-gap diagnostic

## Finding

Position 388 was a 0.01-lot XAUUSD sell opened **2026-09-01 22:53:00.238** at 4327.48. It closed **2026-09-02 01:00:00.037** at 4469.17, with exit comment `sl 4331.60`, P/L -141.69 and swap -0.05. These are epoch-millisecond values rendered using the broker/tester clock label; UTC offset is not verified. MT5 journal shows same broker/tester date and minute. Planned stop was 4331.60, 4.12 price units from entry. The stop-price overshoot at exit was 137.57 (33.4 planned price-risk units); realized loss was about 34.4R.

This was a stop-loss-triggered exit at an extreme ask on the first post-gap observation. Raw ask equals reported fill, so there is no evidence here of additional execution slippage after that quote. Evidence does not establish false feed or news cause.

## Event trace

Accepted artifacts identify XAUUSD, tick size 0.01, contract size 100, minimum volume 0.01. The source hash in `accepted.json` matches `research/ResearchCandidate_R4.mq5`: `AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320`.

At 22:53, raw export records bid/ask 4327.55/4327.81, sell signal, order attempt, retcode 10009, ticket 388. Deal entry was 4327.48. Journal records SL 4331.60 and TP 4323.50. Last pre-gap raw minute sample: 22:59:00.078, bid/ask 4324.39/4324.78 (bar label 22:59). Next raw sample: 01:00:00.037, bid/ask 4320.26/4469.17. For a short, ask is close side and equals reported exit fill. Raw spread there is 148.91. We have minute samples, not a tick-by-tick record of the interval.

`market_probe_minute_daily.csv` reports 1,320 M1 bars on each date: Sep 1 first 01:00:00.269, last 22:59:59.994; Sep 2 first 01:00:00.037, last 22:59:59.972. This supports a recurring two-hour gap in observed M1 coverage, not tick-by-tick proof of closure. The exported session table's 00:00–23:00 schedule is current metadata, not historical schedule proof; verify broker's historical applicable schedule before relying on it. Probe gap CSV has header only; minute-issues flags other dates, not Sep 1–2.

Journal caveat: event lines carry stale `AegisPredator V23` label and print `(2.0R)` after TP 4323.50. Accepted R4 input override sets TP RR to 1.0. Trust the literal SL/TP prices, accepted config, and deal/fill; do not interpret the stale label or printed 2.0R as the actual run configuration.

## Holding time

Wall-clock hold was 2h 07m (127 minutes). There were six completed post-entry M1 bars before the coverage gap (22:54–22:59), not 60 completed M1 bars before the 01:00 stop fill. If “60 bars” means another timeframe, define it explicitly. Count completed bars from bar timestamps, not elapsed wall time, and define gap behavior.

## Context, with loss retained

The month-by-month 167.86 September drawdown (1.653%) is a callback-sample estimate, not authoritative accepted-coverage DD. Prior monthly estimates ranged 5.86–47.14, March highest before September. The accepted run's authoritative overall native DD is 1.64%; this report does not attribute the difference to one cause. The -141.69 trade remains in all performance totals; do not remove it as an outlier or select strategy from adjusted results.

## Hypothesis and next test

Leading hypothesis: a short entered shortly before a scheduled daily closure remained exposed through the observed M1 coverage gap; the stop triggered on the next available quote and filled at the extreme ask. Alternative: reopening quote is tester/history artifact. Current evidence cannot distinguish these.

Next test: **broker-session-end pre-close guard**, using symbol session schedule in broker time and validating historical applicability. Before broker close, block fresh entries inside a minimum bar/time buffer and proactively flatten existing positions before the no-quote interval. Entry and spread guards alone cannot protect a held position if broker closes first and EA receives no callback until reopening. Test every session across accepted period. Compare trade count, drawdown, expectancy, gap-loss count, missed winners; use chronological held-out periods. Do not tune one clock hour. Reconcile raw bid/ask against native source tick quotes before concluding feed error.

## Sources

- `reports/v25_research_20261007/runs/r4_a_descriptive10m/accepted.json`
- Same run: deals, raw, signals, paths, coverage, spec CSVs; bounded event search in `journal_4.txt` and `journal_6.txt`
- `reports/v23_backtest_20261004/runs/market_probe_minute/market_probe_minute_daily.csv`, `market_probe_minute_sessions.csv`, `market_probe_minute_gaps.csv`, `market_probe_minute_minute_issues.csv`
