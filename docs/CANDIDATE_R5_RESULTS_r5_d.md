# R5 fresh-control results, 2026-10-08

Status: completed historical research. No qualified V25 and no deployment.

## Evidence and protocol

Evidence root: `reports/v25_research_20261008_postupdate/`. Manifest: `r5_d_complete.json`. Full entry-level attribution: `r5_d_attribution.json`.

Use XAUUSD M1 MetaQuotes-Demo native real ticks, December2025 through September2026. Updated terminal/tester build6246, $10,000 structural deposit, leverage1:200, fixed0.01lot, 200ms execution delay. All four development cells share SL1.5ATR, TP1R, BEoff and maximum60 completed M1 bars. P0/P1 are the frozen displacement presets. A0 disables and A1 enables completed M1 EMA9/20 direction alignment. No new exit grid or schedule rule was introduced.

The isolated connection account's $70 and1:500 do not change these tester inputs. This is not an XM live-account estimate.

Production V24 and R5 mode0 reproduced 15,072 ordered native order/deal report rows over ten months. Both fresh R4 controls exactly reproduced the respective R5 A0 development economics. The analyzer independently reconciled eight accepted environments: production, mode0, four development cells and two R4 controls. Runtime/cache provenance is exact, including six-month subsets of the full ten-month reference. Actual R5 MQL behavioral fixtures passed27 checks.

Old-runtime update-handoff evidence remains unaccepted. Old controls and their hashes were not rewritten. The original historical windows have been inspected before and are not genuinely unseen OOS.

## Six-month development

Window: `[2025-12-01, 2026-06-01)`. Frozen pass requires net>0, PF>=1.20 and at least150 positions per cell.

| Cell | Closed positions | Net USD | PF | Pass |
| --- | ---: | ---: | ---: | --- |
| P0 A0 | 351 | 54.85 | 1.0630 | No |
| P0 A1 | 132 | 11.68 | 1.0358 | No |
| P1 A0 | 156 | 98.82 | 1.2759 | Yes |
| P1 A1 | 54 | 4.04 | 1.0264 | No |

## Validation and ten-month diagnostic

P1 A0 was the only eligible development cell. June–July validation earned $36.02, PF1.7633, from28 positions. It fails the frozen40-position floor. No validation-qualified selection lock or confirmation-qualified release exists.

The development-selected descriptive ten-month replay was not promoted into a qualified winner:

- 202 positions, win rate52.48%, net-$2.68, PF0.9955, native equity DD1.64%.
- Seven positive months, three negative months. September net-$150.17.
- Fixed-trade additional-cost sensitivities: $0.20 per position produces-$43.08, $0.50 produces-$103.68. Spread already appears in executable fills and is not subtracted twice.
- These values exactly reproduce the earlier R4 result under the fresh controls. This recovery did not create new profitability.

## Why M1 alignment did not improve this sample

Both A1 replays retained exact subsets of A0 entries. Retained entries had unchanged economics, and A1 added no unmatched positions.

| Preset | Identical retained positions | Excluded positions | Excluded net USD | A1 net change |
| --- | ---: | ---: | ---: | ---: |
| P0 | 132 | 219 | 43.17 | -43.17 |
| P1 | 54 | 102 | 94.78 | -94.78 |

Therefore this particular completed-M1 alignment rule removed a net-profitable subset instead of curing bad entries. It does not establish that every excluded trade was good or that EMA conflict causes profit. It falsifies improvement by this rule on this sample, not every possible directional or regime filter.

An exhaustion/reclaim entry can occur before the slower M1 EMA20 has turned. An opposite EMA9/20 relationship is not by itself proof of a mistaken BUY/SELL. This is a mechanism hypothesis, distinct from the measured paired-trade result. Do not invert orders merely because the short-term EMA relationship differs.

The known worst September short retained in the ten-month ledger lost $141.74 after a gap and extreme executable Ask movement while Bid fell. That is not proof of a uniformly wrong SELL direction, independent feed corruption, or a verified historical session schedule. Do not delete it, cap its realized loss synthetically, or hardcode its date/hour to improve results.

## Decision

R5 C0 research fails qualification. C1 remains `UNRUN_SCHEDULE_UNVERIFIED`. Continue the separately preregistered R6 signal families without lowering sample floors, changing exits after results, or claiming these historical periods are prospective evidence. V24, VM accounts and V21 collectors remain untouched by this batch.
