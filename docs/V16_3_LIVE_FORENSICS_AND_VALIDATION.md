# V16 Live Forensics and V16.3 Validation

Date: 2026-09-13  
Decision: **V16.3 DEPLOYMENT BLOCKED**

## Scope and safety

- Account `112334471` treated as protected, read-only baseline.
- Account `112468807` not modified and received no EA deployment.
- V21 Research terminal inspected and CSV files copied read-only.
- No VM restart, chart change, account login, Git commit, or Git push performed.

## Reconstructed V16 Velocity outcome

Source: UTF-16 MT5 terminal and Expert logs copied from the VM. Terminal deals were restricted to the exact account prefix for `112334471`. Velocity events were matched by timestamp, side, and price with one active trade at a time.

| Metric | Result |
|---|---:|
| Matched closed trades | 256 |
| Positive estimated exits | 189 |
| Negative estimated exits | 67 |
| Positive-exit rate | 73.83% |
| Estimated gross XAUUSD price PnL | +$17.93 |
| TP exits | 99 |
| Break-even lock exits | 90 |
| Initial stop exits | 67 |
| Peak cumulative gross estimate | +$24.29 |
| Peak-to-trough giveback | -$24.14 |

The estimate excludes commission, swap, and any broker-side adjustment. It is not an account statement.

### Exit contribution

| Exit class | Estimated gross contribution |
|---|---:|
| TP | +$178.37 |
| Break-even lock | +$13.50 |
| Initial stop | -$173.94 |

Main finding: V16 did not fail because break-even existed. Break-even protected many trades. The damaging asymmetry was that one full `-$2.60` stop erased about 1.44 average TP exits or about 17 small break-even wins. On 2026-09-10 the bot still had about 70.6% positive exits but finished the day negative.

## Historical isolation defect

Early V16 logs show Apex M1 and Velocity both using magic `991601`. Later logs explicitly show Velocity overriding legacy magic to `991602` to isolate Apex positions. Early results can therefore include cross-management contamination. New candidates must use a unique magic and must never manage positions belonging to another module.

## V16.3 candidate

Files:

- `QuantumTitan_v16_3_Precision.mq5`
- `QuantumTitan_v16_3_Precision.ex5`
- `tests/test_v16_3_precision.py`

Engineering changes include completed-bar buffers, fail-closed indicator reads, independent slope values, per-ticket entry state, verified stop modification results, symbol/tick/stops-level checks, same-terminal entry locking, explicit deal-cost logging, account allowlist `112468807`, and unique magic `991613`. Grid and martingale logic are absent.

Compilation result: 0 errors, 0 warnings.

## Recent real-tick backtests

Test window: 2026-09-08 through 2026-09-12, XAUUSD M1.

| Candidate | Trades | Win rate | Net profit | Profit factor | Max balance DD |
|---|---:|---:|---:|---:|---:|
| V16.3 precision defaults | 151 | 50.33% | -$71.80 | 0.59 | 72.48% |
| V16.3 with original management values | 117 | 50.43% | -$72.31 | unavailable | unavailable |
| Current V16.55 binary | 42 | 61.90% | -$15.43 | 0.60 | 18.29% |

Result: all tested candidates fail the deployment gate. Delaying break-even and increasing TP did not preserve the observed live edge.

## Why OHLC counterfactual is insufficient

`research/v16_m1_counterfactual.py` tested the observed entries against V21 M1 OHLC. Exact exit-class reproduction was only 49 of 146 trades, or 33.56%. A one-minute candle does not reveal whether TP, break-even activation, or SL happened first inside the minute. Its decision is therefore:

`INCONCLUSIVE_OHLC_CANNOT_REPRODUCE_LIVE_EXITS`

M1 OHLC scenario results must not be used to select production thresholds.

## V21 acquisition status

- Valid bars: 2,784
- Sessions: 3 of 15
- Malformed rows: 0
- Invalid OHLC rows: 0
- Duplicate rows: 0
- Write errors: 0
- Current weekend state: `MARKET_IDLE`
- Acquisition gate: `COLLECTING`
- Deployment gate: `BLOCKED`

The row target is complete. Session diversity is not complete. `research/v21_progress_report.py` now separates current weekend liveness from the latest healthy data-quality heartbeat, avoiding a false lag failure.

## Required next evidence

Before changing TP, SL, or break-even again, collect tick-path evidence containing per-trade MFE, MAE, spread distribution, and first-passage ordering for candidate thresholds. Then use chronological train, validation, and holdout windows. Promotion requires positive expectancy after XM spread and execution costs, acceptable drawdown, stability across sessions, and no dependence on one profitable day.

## Final decision

- Preserve account `112334471` unchanged.
- Do not deploy V16.3 to `112468807`.
- Continue V21 passive collection.
- Read-only tick-path collector built, independently audited, compiled, tested, and deployed on V21 Research account `5055724796`.
- Wait for market ticks before validating the first 15-bar output rows.

## Tick-path collector deployment

Team review found eight material data-integrity defects. All were fixed before the market produced any collector rows:

1. A tick from the next bar could leak past the 15-bar horizon.
2. Missing-bar records were incorrectly labelled `COMPLETE`.
3. Disconnect state was never observed.
4. Rollover was checked only at entry rather than through the full horizon.
5. Previous slope used a disjoint ten-bar window instead of a one-bar shift.
6. Spread P95 used only the first 256 ticks and was time-biased.
7. Buy and sell excursions used the wrong entry quote side and omitted initial spread.
8. First-touch summaries could not reconstruct a break-even lock recross after activation.

Final evidence:

- `QuantumTitan_V16_TickPathCollector.mq5`
- `QuantumTitan_V16_TickPathCollector.ex5`
- Schema/collector version `2` / `16.31`
- Binary SHA-256 `094e1c21774e72d2237417ba4d661ed7b8ade5dbc344215caaf769a126897d0d`
- MetaEditor: 0 errors, 0 warnings
- Collector tests: 16 of 16 passed
- Full Python suite: 158 of 158 passed
- V21 Research restarted only during market idle
- New V21 Research PID: `212634`
- Journal confirmed account `5055724796`
- Journal confirmed both ForwardCollector and TickPathCollector loaded successfully on separate XAUUSD M1 charts
- Existing V16, V16.1, and V17 terminal processes remained running

## Collector 16.32 redeployment, 2026-09-14

- Scope: V21 Research only, demo account `5055724796`.
- Protected accounts `112334471` and `112468807`: not restarted or modified.
- Fixed exact-point floating comparison and invalid quality-flag concatenation.
- Schema remains `2`; collector version is `16.32`.
- Binary SHA-256: `448d097b474992c3d7477224c7ee2e127db70801ef9dbb8f565e49528bc3e49c`.
- Previous `16.31` EX5 retained as `QuantumTitan_V16_TickPathCollector.ex5.bak_16_31` on the research terminal.
- V21 Research restarted only. New terminal PID: `218054`.
- Journal confirmation: both `QuantumTitan_ForwardCollector` and `QuantumTitan_V16_TickPathCollector` loaded successfully on XAUUSD M1.
- Local validation after the change: MetaEditor 0 errors / 0 warnings; Python suite 179 passed.
