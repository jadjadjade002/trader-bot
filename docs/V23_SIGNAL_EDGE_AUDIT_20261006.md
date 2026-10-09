# V23 signal edge audit, 2026-10-06

Scope: research only. No changes to `AegisPredator_v23.mq5`, circuit breaker, live terminal, accounts or VM. No deployment claim.

## What was tested

`research/audit_v23_signal_markouts.py` reads the 143,336 all-bar snapshots in `reports/v23_backtest_20261004/runs/fade_10000/fade_10000_raw.csv`, 2026-05-01 through 2026-09-30 broker time. It uses **all raw candidate signals before holding-position/breaker gates**, rather than only trades that happened to execute. For every signal, entry is the first observed new-bar bid/ask; exit is the first observed bid/ask exactly 5, 15 or 60 minutes later. A missing intervening minute invalidates that window. Buy pays ask then exits bid; sell enters bid then exits ask. Reported price deltas are XAUUSD quote units, **not account dollars**. The difference between midquote and bid/ask markout estimates quoted entry/exit spread drag.

This is a descriptive signal screen, **not** a native trade backtest. It omits execution delay, slippage beyond the observed quote, fees, SL/TP, position occupancy and breaker path. Multiple horizons and variants on previously inspected May–September data are exploratory. Day-block bootstrap intervals are descriptive, not a multiple-testing-adjusted proof.

Cross-run check: repeating the audit on `momentum_10000_raw.csv` and `closeback_10000_raw.csv` produced the same 143,336 bar count, candidate counts, and all three 15-minute mean markouts to the reported precision. These are separate EA-run ledgers but the same underlying historical market period, **not independent validation**.

## Primary diagnosis at 15 minutes

| Raw signal | Matched | Mean midquote move | Mean quoted spread drag | Mean after quoted spread | 95% day-block bootstrap mean interval |
|---|---:|---:|---:|---:|---:|
| Original fade | 7,881 | +0.040 | 0.277 | **-0.236** | [-0.463, +0.008] |
| Original momentum (reverse direction) | 7,881 | -0.040 | 0.277 | **-0.317** | [-0.560, -0.085] |
| Close-back fade | 1,938 | +0.112 | 0.275 | **-0.163** | [-0.458, +0.141] |

At 5 and 60 minutes, mean after-spread markouts were also negative for all three variants. Original fade at 5 minutes: midquote +0.160, spread drag 0.278, after-spread -0.118. Close-back at 5 minutes: +0.078, 0.275, -0.198. These figures answer the Buy/Sell question more directly than the breaker: reversing all original directions makes the 15-minute raw outcome **worse**, not better. The fade direction has a small positive midquote drift on this historical sample, but less than the quoted spread drag. That is **not evidence of deployable alpha**.

Native strategy results on the same historical interval reinforce the concern: original fade 2,987 positions / -$1,342.34; momentum 2,705 / -$1,221.67; close-back fade 1,436 / -$464.50 (`reports/v23_backtest_20261004/comparison.json`). Those totals include the strategy's actual SL/TP/time exit and path dependence. They do not isolate signal direction alone.

## Decision

1. Do **not** flip all Buy/Sell signals. Tested momentum path and raw markouts both remain negative.
2. Do **not** promote close-back or level-touch. Close-back is less negative but not profitable; level-touch already failed its separate historical directional screen (`docs/V23_LEVEL_TOUCH_EXPERIMENT_20261006.md`).
3. Do **not** modify the breaker in this signal-only task. Breaker changes might cap later losses but cannot create positive entry expectancy.
4. Do **not** fit a spread/session/ATR/volume threshold to these May–September results and call it proven. Such a threshold would be exploratory and need a new untouched test. Selection from repeatedly inspected backtests risks overfitting ([Bailey et al., original paper](https://escholarship.org/uc/item/4w1110bb)).

## Prospective test, not yet runnable end-to-end

- Reserved broker-server interval: **[2026-10-07 00:00, 2026-12-02 00:00)**. Exclude October 1-6. Primary existing hypothesis: close-back fade, unchanged. Original fade and momentum are diagnostics, not choices to optimize after viewing the window.
- Primary *signal* endpoint: 15-minute first-quote bid/ask markout for every quality-valid raw candidate, with day-block interval. Require positive mean and a lower 95% bound above zero before claiming directional evidence. The 5/60-minute horizons are secondary, not selection knobs.
- Separate *tradable-strategy* endpoint: native real-tick net PnL after all charges, net PF > 1.20, >=300 completed positions, full data/accounting audit, and acceptable drawdown. Passing these screens still needs broker-specific forward execution validation. If fewer than 300 positions, label underpowered; do not extend the primary window after viewing outcomes.
- The V21 collector has OHLC and first-tick bid/ask. `research/audit_v23_v21_forward.py` reconstructs the frozen V23 Donchian/ATR and signal using only closed bars. On the September 9-28 local V21 snapshot, **14,749 quality-eligible bars matched native raw timestamps; all 14,749 signal classifications matched**, including 910 original and 203 close-back candidates. Donchian max absolute difference was 0, ATR mean absolute difference was 0.000005666, max 0.005714. First-quote bid/ask matched on 14,722/14,749 bars (99.81694%). Within the diagnostic subset whose entry-bar flag later became `OK`, quotes matched on 14,703/14,705 bars (99.9864%); two asks differed by 0.07 and 0.04 quote units. This validates signal reconstruction on that overlapping sample, **not** future fills or perfect quote parity. The adapter rejects gaps and non-`OK` historical lookback bars. It does **not** gate the entry signal using entry-bar flags, because those flags are finalized later and would leak future information. Quote anomalies and candidate coverage must remain visible in future reports.
- The isolated local MT5 tester currently lacks its demo account, so a new native run is blocked. **Do not relabel a collector-only markout as native PnL.** The MT5 real-tick tester can substitute generated ticks where tick and minute data disagree, so inspect quality logs as well as headline history quality ([MQL5 testing reference](https://www.mql5.com/en/docs/runtime/testing)).

SHA-256 before the reserved window: live source `C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0`; frozen benchmark source `F60340E10AC59EC6E300068A44946424D33BA382A2C640E94AB97B9DC41C0183`; markout auditor `9E5F6CD22B8125B38DD0183DF22890D04AF6AAC0B743401601242A0088C308A6`; V21 adapter `B007E3136193BC7B9F0F377AB1F52A05EA727F929B0A0C257753A0487D367113`. Signal adapter parity is demonstrated on the overlap. Native tester access and future collector health/coverage remain unverified, so this is a **partial protocol freeze**, not a claim that the future run is operationally ready.

## Additional structural signal test

The reversal-confirmation hypothesis was specified before execution in `docs/V23_REVERSAL_CONFIRMATION_PROTOCOL_20261006.md`. It requires the close-back candle to move in the intended fade direction, rather than fading a still-continuing candle. The 15-minute result was 1,937 matched signals, mean midquote +0.111941, quoted spread drag 0.274574, after-spread mean -0.162633, day-block 95% interval [-0.458411, +0.141257], and only one of five months positive. It failed the predeclared advancement rule.

Overlap check: all 1,961 raw candidate entries were already close-back candidates with the same trade direction; the old close-back set had 1,963. The extra candle-direction condition removed only two entries (0.102%). It supplied almost no new information. This is a useful negative result: changing the candle-direction wording alone does not repair this entry model. Both 5- and 60-minute outcomes were negative too. No reversal-confirmation native EA was created or deployed.

Validation: 11 focused tests passed for spread arithmetic, direction, calendar gaps, closed-bar isolation, ATR reconstruction, window boundaries and the new signal predicates. The live V23 source SHA-256 remained unchanged. Exact candidate results and reproduction command are in the protocol document.
