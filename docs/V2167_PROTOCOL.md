# QuantumTitan V21.67: corrected Velocity execution candidate

Status: experimental implementation. Performance target is unverified. This is
a separate candidate, not a promotion of the V21 whipsaw observation study.

## User objective and decisions fixed before testing

The objective is 10 to 20 completed positions per overnight session, at least
80% wins after costs, and positive net profit. Until a different sleep window
is agreed, use the project's existing 18:00 to 02:00 broker-time window. This
is not a claim about the user's local timezone or a guarantee per night.

Build one candidate from the v16 Velocity mechanism with corrected bar clocks
and execution accounting. Do not optimize thresholds or select a profitable
historical variant. Preserve all v16, v17 and V21 Collector files and running
accounts. No RiskGuardian dependency, grid, averaging or lot scaling.

## Frozen strategy

- XAUUSD M1. Fixed 0.01 lot and magic 992167.
- Read completed bars only. EMA14, EMA50 and RSI14 use shift 1. Read 40
  consecutive completed M1 bars. Invalid or unavailable values skip the bar.
- For each historical bar, delta is its close minus the average of its own
  Donchian20 midpoint and its own SMA20 close. Momentum is the chronological
  linear regression slope of 20 deltas. Previous momentum uses the preceding
  20 deltas. This is a slope-based corrected Velocity model, not a claim of
  exact equivalence to TradingView's regression-endpoint indicator.
- Long: fast EMA > slow EMA, completed close > slow EMA, low <= fast EMA +
  15 points, lower wick / range >= 0.25 OR bullish candle, momentum > -0.05,
  and RSI in [40,70]. Short mirrors the comparisons, with momentum < 0.05
  and RSI in [30,60]. Equal EMA values and zero-range bars give no signal.
- Evaluate once on the first tick of a new M1 bar, no older than 10 seconds.
  Missing inputs, rejected quotes and failed submissions consume that bar.
- Entry from 18:00 through 01:49. Maximum hold 10 minutes and session exit
  at the first executable quote at or after 02:00. These are new explicit
  holding policies, not properties of the old Velocity bot.
- Maximum spread 60 points. SL 260 points, TP 180 points. Breakeven trigger
  85 points with a 15-point price lock. No micro-trailing. A price lock does
  not guarantee a net win after fees, gaps and slippage.
- Market execution uses a 20-point deviation request, which is not a broker
  guarantee. After a fill, attached SL/TP prices must still match the submitted
  protection. Up to 20 points plus one tick of adverse fill movement is accepted
  (maximum initial risk 280 points plus rounding, minimum remaining target 160
  points minus rounding); worse or unreconciled protection triggers a retried
  safety exit rather than moving the SL or TP.
- Cooldown 60 seconds after a complete exit, restored from account history.
- Broker tick-size rounding and minimum stop distances apply. Reject invalid
  volume, margin or protection. Never enlarge an invalid stop to force entry.
- One gold exposure, including pending orders, on a dedicated account. An
  uncertain submission blocks another entry until an entry deal is reconciled.
- Outside Strategy Tester, order sending defaults off and requires an exact
  separate demo login. Accounts 112334471 and 5055724796 are prohibited. A
  change of account after initialization disables all trade actions.

## Engineering validation fixed before outcomes

Compile with zero errors and warnings. Native MQL tests check the pure signal,
bar continuity, rolling momentum, mirrored cases, clock boundaries and rounding.
Python tests check outcome accounting and fail-closed qualification.

Use an isolated local `.mt5-v2167.local` terminal. First run the already exposed
2026-08-03 to 2026-08-04 interval as an execution smoke test. If runtime checks
pass, run 2026-08-03 to 2026-08-22 once, with a USD 50 deposit, 1:500 leverage,
real ticks and 200 ms delay. A 500 ms run is a separately reported execution
stress check, never a parameter-selection opportunity. These are exposed
engineering checks, not untouched holdout evidence, even if profitable.

Record source, dependency, protocol, binary and input hashes. Report closed
positions including entry/exit commissions and swap. Reject unrecognized deal
formats or unreconciled net PnL rather than claiming fee coverage. Show forced
test-end exits and positions carried past 02:00. Zero-trade weekday sessions
remain in denominators. Native equity drawdown includes floating losses.

## Prospective qualification

Before a future demo experiment begins, record its separate account, broker,
source/binary/settings hashes and the next 40 scheduled weekday overnight
sessions. Their start must be after the freeze and their outcomes must not
have been examined during development. The existing V21 Collector study is
unchanged and is not a substitute for execution evidence. No future account
or start date has been selected by this document.

The candidate must have at least 400 completed positions over those 40
scheduled sessions, mean frequency 10 to 20, net win rate >=80%, and at least
32 sessions meeting frequency, win rate and positive net together. Additional
research quality hurdles, not promises from the user, are net profit >=USD 40,
net-cost profit factor >=1.20, maximum equity drawdown <=20%, at least six of
eight chronological five-session blocks profitable, and positive expectancy
after an extra half-spread cost stress. Record missing data and outages. Do
not drop sessions or delay the fixed end until the statistics improve.

Report uncertainty by session. A trade-level Wilson interval is only a
diagnostic because correlated scalps are not independent. A favorable
historical result cannot authorize deployment. Failure or insufficient
evidence is reported explicitly. A change of strategy requires a new freeze.

## Technical references

MT5 documents the distinction between request acceptance and trade execution
at https://www.mql5.com/en/docs/trading/ordersend and tester tick/delay settings
at https://www.metatrader5.com/en/terminal/help/algotrading/testing.
