# V25: forensic decision before another deployment

Date: 2026-09-28. Scope: XAUUSD M1 demo research. Status: **candidate built, not a proven profitable strategy, not deployed**.

## Executive decision

Do not splice all prior indicators into a larger score. That would obscure which change helped, amplify data-mining, and leave the old payoff defect untouched. Preserve one frozen, causal signal family as a benchmark: V16.59/R4 EMA 6/24 state transition. Build V25 as an execution/risk-hardened derivative, not a claim that R4 already has an edge. Use V21 data to *reject* weak hypotheses and quantify friction. Keep V22 swing, V23 breakout, and the V21 whipsaw veto separate until independently validated.

The V25 artifact is `QuantumTitan_v25_EvidenceFirst.mq5`. It is demo-only, XAUUSD M1, hedging-mode-only, and `InpEnableTrading=false` by default. No VM, existing EA, or account is changed by this work.

## Evidence hierarchy

1. Broker deal history with prices, profit, commissions, position identity, and execution timestamp is strongest for actual PnL. Account balance alone is not an EA attribution.
2. Native MT5 real-tick tests with frozen inputs are useful but still may differ from live execution, spread, stop slippage, and broker contract settings.
3. V21 forward collector M1 bars are valuable for regime, spread and *falsification*. They do not contain full intrabar bid/ask paths, cannot prove exact stop ordering, and come from a different demo server/account than some XM goals.
4. Python OHLC proxy and parameter search are exploratory. No validation label may be called untouched after repeated inspection/tuning.
5. A compile or unit-test PASS proves mechanics, not expectancy.

## Old failures, separated by cause

| Line | Observed evidence | Root cause | V25 response |
|---|---|---|---|
| V16 Velocity M1 | 256 matched exits, 189 positive (73.83%), estimated gross +$17.93 but peak-to-trough giveback -$24.14; 99 TP, 90 BE, 67 initial SL | Many small positives coexist with large full stops. 67 stops at about -$2.60 consume 99 TP and 90 tiny BE gains. Early legacy magic overlap with Apex also contaminates some events. | Do not optimize for win rate. Unique magic, no BE lock, account-wide same-symbol exposure veto, explicit net-deal logging. |
| V16.1 | One-day real-tick comparison: 121 trades -$46.43 original versus 98 trades -$25.45 V16.1 | Larger TP/slower BE reduced damage but did not create a profitable signal. | No blind TP extension or assumption that slower BE guarantees profit. |
| V16.3/16.55 | V16.3 real-tick 151 trades -$71.80; V16.55 42 trades -$15.43 | More “precision” filters did not survive execution costs. | Freeze simple signal. Test whole strategy out of sample, not component aesthetics. |
| V16.56 live demo | 12 trades: 4 wins +$1.57, 8 losses -$22.25, net -$20.68, PF .071. 11/12 entries WICK_PULLBACK. Winners' MFE about +$1.56 to +$1.88; realized only +$0.34 to +$0.50. | Entry quality and payoff policy both failed. BE lock shrank winners while all losers hit full SL. | Remove automatic near-entry lock. Broker hard SL remains mandatory. Reject raw wick/FVG as default entry. |
| V16.58 ablations | No lock improved 11-trade smoke net from -$11.11 to -$0.12; every tested entry variant failed validation, including EMA-reclaim/KER (+$23.26 development, -$3.66 validation). | Exit fix alone is insufficient; apparent development gain overfit. | No parameter selected solely from development or small sample. |
| V16.59 R4 | MT5 real ticks: development 22 trades +$7.92 PF1.66; validation 21 trades -$5.13 PF.78 and 28.23% equity DD; confirmation 10 trades +$2.81 PF1.49. Aggregate 53 +$5.60 PF1.14. | Best surviving *lead*, but independent validation failed. Nominal EA had no hard stop by default. | Keep signal fixed to avoid a new search; add hard stop, dollar-risk and daily-loss veto. Treat resulting trades as a **new** strategy requiring new tests. |
| V21 whipsaw veto | 16,417 valid bars, 16 broker sessions, 907 eligible probes. Vetoed whipsaw 18.60% versus kept 20.69%, separation **-2.09 pp**. Coverage 61.6%, beyond 10–40% gate. | Filter rejects too broadly and does not preferentially remove whipsaws. 907 < preregistered 1000, 3 < 4 weekly blocks, yet observed direction is wrong. | Do not put V21 veto in V25. More sessions cannot retroactively make current failed gates a PASS. |
| V23 claimed breakout | Report claims 92 trades +$102.34/PF1.60 on earlier snapshot. Re-run of its generic research module gives candidate-2 75 dev +$23.37 and 55 validation +$7.08, not report's numbers. EA defaults invert signals and disable spread guard. | Research report and shipped EA are not demonstrably the same frozen policy. Original generic simulator skipped SL/TP on the entry candle. Strategy selection/reporting used the inspected dataset. | Reject PF1.60 as verified. Rebuild exact executable-policy test and real-tick validation before considering V23. |
| V22 swing | Stronger contextual filters and risk controls exist, but no comparable, independent account-level PnL evidence in the inspected material. | Architecture quality is not profit proof; different timeframe/holding regime. | Keep separate. Do not combine V22 signals with M1 R4 without a preregistered ablation. |

Sources inside this repository: `docs/V16_3_LIVE_FORENSICS_AND_VALIDATION.md`, `docs/V16_58_EVIDENCE_REPORT.md`, `reports/v1659_*.json`, `data/v21_check_20260928_124506/decision.json`, `docs/V23_CANDIDATE_VERIFICATION_REPORT.md`, and EA sources. The V16 historical estimates are not broker account statements.

## V21 friction audit, independent reproduction

Run: `python research/v25_forensics.py data/v21_check_20260928_124506`.

- Collected period: 2026-09-09 20:25 to 2026-09-28 08:43 broker time; 16,417 M1 bars, 92 non-OK flags, 22 time gaps.
- Observed **open** spread: median 32 points, p90 50, p99 68, 74.2% over 25 points. This is a MetaQuotes-Demo collector, not verified XM contract pricing. It still falsifies any claim that a 25-point filter is a harmless default on this stream.
- Conservative V23-like proxy with default inverted signal and spread guard disabled: 149 trades, -$114.77, PF .686, 26.2% wins. 19 positions touched an exit on the entry candle, which the old simulator did not inspect. Earlier snapshot alone: 132 trades, -$99.87.
- Inverted + 25-point **observed open-spread** guard: 56 trades, -$12.12, PF .896. Non-inverted + same guard: 50 trades, -$0.48, PF .995. Under 2× entry/exit-spread stress with the same observed-spread gate: 57 trades, -$45.77, PF .66.
- These proxies are *diagnostic*, not executable PnL: ask intrabar high/low absent, spread at stop unknown, commission/slippage not modeled, contract assumptions may differ. The large discrepancy against V23's report demands a native MT5 real-tick audit, not a declaration of a precise alternative profit number.

## V25 design, fixed before tester result

Signal is identical in concept to nominal R4: closed M1 EMA6/EMA24 cross, ATR14/120-bar median regime 0.5–1.5, close within 0.35 ATR of EMA24, signal candle range at most 1.5 ATR, entry during broker 18:00–01:56 with spread at most 40 points. Three completed M1 bars is the planned time exit. No BE, no trailing, no grid, no martingale, no signal inversion. Signals are logged even when vetoed.

Execution changes:

1. Mandatory broker-side stop at 2 ATR, tick-size rounded, broker stop-level checked. **Gap/slippage can still exceed it.**
2. `OrderCalcProfit` estimates stop loss in actual account currency; reject if above 3% of current equity. This is a veto, not a promise of exact fill or a stop-size squeeze. If 0.01 lot is too large, **skip the trade**.
3. Account-wide same-symbol exposure veto, even when another EA uses another magic. V25 closes only its own magic, so no cross-management.
4. Daily equity loss veto at 5% of reconstructed broker-day-start balance; at most four V25 entries per broker day. History unavailable fails closed. Deposits or manual balance operations require separate handling before live use.
5. Fresh Bid/Ask tick, positive spread and hard spread limit; margin precheck. Account must be demo, hedging mode, XAUUSD M1.
6. Default `InpEnableTrading=false`. Separate `InpTargetAccount` may bind exact demo account when later authorized. No VM deployment in this research step.
7. Distinct rejection and deal logs support a causal funnel: signal → session → exposure → quote/spread → daily limits → stop/risk → margin → order retcode → realized net. Future threshold changes must identify which funnel stage they alter.

This is deliberately *not* a high-frequency 10–20 order promise. Previous high-count systems lost money. If the 3% cap blocks most signals on a $60 standard account, reducing the hard stop to force trades would repeat the old error. Use a verified smaller contract or accept fewer trades.

## Native MT5 real-tick verdict, frozen V25 inputs

Local isolated MT5 tester; XAUUSD M1, MetaQuotes-Demo history, 0.01 standard lot, 1:500, 200 ms execution delay. V25 binary and set/config hashes are recorded in `.mt5-v17.local/reports/v25_*.metadata.json`. This is **not XM**, and these dates were already used during earlier V16.59 research, so neither validation nor confirmation is a new untouched sample for the broader project.

| Capital/window | Trades | Wins | Net | PF | Max equity DD | Readout |
|---|---:|---:|---:|---:|---:|---|
| $60, development Aug 03–21 | 0 | 0 | $0.00 | n/a | 0 | 80 signals: 49 session veto, 6 spread veto, 25 risk veto. All post-session/post-spread signals exceeded $1.80 risk cap. |
| $60, validation Aug 24–Sep 08 | 1 | 0 | -$0.93 | 0 | $0.93 / 1.55% | Not enough trades to estimate an edge; the capital/lot mismatch persists. |
| $200, development Aug 03–21 | 21 | 14 | +$7.75 | 1.64 | $9.73 / 4.57% | Interesting but development only. |
| $200, validation Aug 24–Sep 08 | 16 | 5 | **-$0.25** | **0.98** | $10.79 / 5.38% | **Fails positive-net and PF gates.** |
| $200, confirmation Sep 09–18 | 10 | 5 | +$2.81 | 1.49 | $3.54 / 1.76% | Too few trades, already inspected period. |

The risk controls prevent forced oversized entries on $60; they **do not** turn the R4 signal into a reliably profitable edge. Do not loosen the 3% cap to manufacture activity. The $200 tests show the signal is regime-sensitive and validation remains negative. In validation, **one +$10.29 trade supplied 76.8% of all gross winning dollars**; without it the 16-trade net would have been -$10.54. Confirmation's largest win supplied 38.6% of gross winning dollars. V25 is a useful hardened research baseline, not a deployable winner.

## Promotion gates, in order

1. Clean compile and focused mechanics tests.
2. Native MT5 real-tick test with frozen V25 parameters and correct binary/settings hashes, identical development and validation windows as V16.59. If terminal cannot synchronize to server, mark **unverified**, never substitute bar proxy as proof.
3. Holdout not inspected during design, at least 30 trades per independent block, positive net after costs, PF >= 1.30 per block, equity drawdown <= 15%, no single day supplying >35% of gains. These are review criteria, not statistical guarantees.
4. Spread/delay stress, zero-trade and rejected-signal accounting, account/contract-spec parity. Compare V25 versus V16.59 using equal period, account type, initial capital, and execution mode.
5. Only after that, explicit account and deployment authorization. Keep existing EA/profile untouched until rollback path and open-position ownership are verified.

## Unresolved limits

No backtest or 16-session collector sample can guarantee a positive edge. V21 is 16 broker sessions, not 16 independent market regimes. Reusing these dates for idea selection makes them development data. The next genuinely untouched forward period is the final check. Per-trade $1–$2 target with $60 and 3% risk may not be compatible with broker minimum lot and realistic spreads; V25 prioritizes bounded loss over forced trade count.

## Build and test provenance

- MetaEditor compiled `QuantumTitan_v25_EvidenceFirst.mq5` with **0 errors, 0 warnings** (`v25_compile.log`).
- Five native tester reports and their source/binary/settings/config SHA-256 metadata live under `.mt5-v17.local/reports/v25_*`; all metadata source/binary hashes match the final local EA artifacts.
- `python -m unittest tests.test_v25_forensics -v`: 3/3 passed, including entry-candle SL and unchanged sample under spread stress.
- Full `unittest discover` ran 209 tests: 208 executed without failure, one V23 test module could not import because bundled Python lacks `pytest`. This is a test-environment dependency gap, **not** a full-suite PASS. No existing V23 test or environment was altered to hide it.
- No MT5 terminal on the VM, chart, account, open position, collector, or Git history was changed.

## Follow-up started 2026-09-28: smaller contract and truly prospective test

- VM terminal logs inspected read-only: all currently identifiable accounts use **MetaQuotes-Demo**. No XM terminal/account is available to measure XM XAUUSD lot contract, minimum volume or stop economics. Do not project MetaQuotes contract values onto XM.
- Compiled `V25_ContractProbe.mq5` (0 errors, 0 warnings). It is a read-only MQL5 script for an eventual XM demo terminal. It prints broker/server, contract size, minimum and step volume, tick size/value, closed M1 ATR, plus `OrderCalcProfit` stop-loss and `OrderCalcMargin` for minimum and candidate lots. It never sends an order. It has **not** been run on XM.
- Source and binary are frozen for the next prospective MetaQuotes-Demo evaluation at broker time **2026-09-28 12:10:00**. `research/v25_forward_gate.py` requires matching SHA-256, refuses any pre-freeze trade, and demands at least 30 trades over 10 trading days, positive net, PF >=1.30, DD <=15%, and no single winner over 35% of gross winning dollars. Even a pass yields `REVIEWABLE_NOT_DEPLOY_APPROVED`, never automatic deployment.
- The old Aug/Sep validation report was fed to this gate and correctly returned `BLOCKED_OR_INCOMPLETE` with `REUSED_PRE_FREEZE_TRADE`, negative net, PF .98 and 76.8% winning-dollar concentration. Seven focused V25 tests pass.
- V21 collector remained healthy at 2026-09-28 12:14 broker heartbeat; last observed completed bar at 12:17. These first post-freeze minutes are not enough to evaluate strategy expectancy.

**Action needed for the $60 XM question:** connect a separate XM demo terminal/account and run the read-only contract probe there. Its exact XAUUSD symbol specification, not generic “micro” marketing labels, determines whether a smaller lot can preserve a two-ATR stop under the 3% ($1.80) risk cap. Any XM port would also need broker-session and spread calibration, then a separately frozen backtest and forward period.
