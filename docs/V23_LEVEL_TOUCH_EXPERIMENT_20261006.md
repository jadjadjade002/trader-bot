# V23 signal-only experiment, 2026-10-06

Scope: isolated MT5 Strategy Tester. Do not change the deployed V23, breaker, SL/TP, lot, margin rule, live terminal, or accounts.

## Evidence before this experiment

The existing May–September 2026 native real-tick comparison gave original fade 2,987 trades / -$1,342.34, momentum 2,705 / -$1,221.67, and close-back fade 1,436 / -$464.50 at $10,000 starting balance, fixed 0.01 lot. These are retrospective results, not a fresh holdout. A low-spread slice of the original fade remained negative. Merely reversing direction or removing trades has not established a positive edge.

From completed-position net PnL, original fade had 909 wins averaging +$6.45 and 2,078 losses averaging -$3.47. Its observed 30.43% win rate is below the **34.96%** break-even rate implied by those realized average payouts. Momentum and close-back also fell below their respective realized break-even rates (33.73% and 34.13%). Thus the **signal plus unchanged exits** lacks a positive edge in these samples. This alone does not isolate whether entry, exit, or their interaction is causal.

## Single new signal hypothesis

Original V23 calls a retest if the candle stays within 0.5 ATR of the broken level, even if it never touches that level, then fades a breakout. This experiment instead requires a *true level touch and reclaim* on a **completed** M1 retest candle, then trades **with** the breakout:

- Buy: breakout candle closes above Donchian high H. Next completed candle low is in [H - 0.5 ATR, H], closes above H, and closes above its open.
- Sell: breakout candle closes below Donchian low L. Next completed candle high is in [L, L + 0.5 ATR], closes below L, and closes below its open.

Entry remains at the next bar's actual first eligible tick. No forming-bar OHLC or future prices. All non-signal inputs and trading/risk code inherited from frozen V23. Build source is SHA-256-guarded and fails if frozen benchmark source changes. Candidate is tester-only and cannot initialize on a live chart.

## Evaluation rule fixed before run

Run exact same May–September native real-tick interval and costs at $10,000 and $70, with 200 ms delay. First require compilation and data/runtime integrity. Compare against original fade and momentum, including monthly net, net profit factor, trades, drawdown, and capital halt. Research threshold: positive net after all costs, PF > 1.10, at least 100 completed trades, at least four of five months positive at $10,000, and positive net without capital halt at $70. Failure of any threshold rejects this candidate.

Even passing is **not deployment clearance**. This date range has been inspected repeatedly. Evidence for promotion requires future untouched broker-time forward data or an independently reserved period, with the same rule unchanged. Do not parameter-sweep this candidate after seeing results.

## Result, 2026-10-06: rejected

`V23_LevelTouchBenchmark.mq5` compiled with **0 errors, 0 warnings**, but the isolated native tester could not start. Terminal log says `Accounts deleted due security reason` and `tester not started because the account is not specified`. No native PnL for this candidate exists. Do not substitute the following screen for a completed backtest.

The first-tick historical bid/ask screen (`research/screen_v23_leveltouch.py`) used the frozen `fade_10000_raw.csv` snapshots. It applied the exact closed-bar predicate, entered at the next bar's first observed ask/bid, marked at the first quote exactly 5/15/60 calendar minutes later, and rejected windows with missing M1 rows. This includes entry/exit spread but **omits** execution delay, order rejection, SL/TP, fees, and trading-state path dependence. Units are signed XAUUSD price delta, **not account dollars**.

| Mark horizon | Matched signals | Positive | Mean price delta | Months positive |
|---|---:|---:|---:|---:|
| 5 minutes | 2,499 | 41.58% | -0.502 | 0/5 |
| 15 minutes | 2,478 | 45.36% | -0.271 | 1/5 |
| 60 minutes | 2,385 | 46.92% | -0.352 | 2/5 |

The 5-minute screen is negative in **every** May–September month, before the omitted execution costs. The experiment therefore fails the first directional screen. Do not deploy or tune around this failure. Leave the V23 live source/config and breaker untouched. October V21 collector data remains uninspected as a possible future forward check for a separately specified signal; three available October bar files do not by themselves establish an edge.
