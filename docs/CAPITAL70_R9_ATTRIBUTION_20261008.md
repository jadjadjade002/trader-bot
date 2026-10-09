# R9 capital-70 native attribution

Status: completed historical demo research, failed frozen gates. No V25 qualification, independent release approval, or deployment. All dollars below are MT5 Strategy Tester account-currency results, not live-money losses. Runs used USD70, 1:500, XAUUSD M1, MetaQuotes-Demo 100%-real-tick history, 200ms execution delay, fixed 0.01 lot. Source, binary, runtime and cache identities are recorded in each accepted signature under `reports/v25_research_20261008_capital70/runs/`.

## Outcome

`reports/v25_research_20261008_capital70/r9_70_a_complete.json` records `qualified=false`, `promotion=false`, no validation, no selection lock, and no confirmation/full qualification stage. Both development arms failed before validation:

| Run | Window | Positions | Net | PF | Equity DD | Final balance | Stopout |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| V24 production and exact mode-0 baseline | Dec 2025–Sep 2026 | 98 | -$59.37 | 0.7654 | 88.11% | $10.63 | No |
| Hold60 continuation | Dec 2025–May 2026 | 56 | -$59.30 | 0.7253 | 89.51% | $10.70 | No |
| Hold90 continuation | Dec 2025–May 2026 | 58 | -$64.71 | 0.7180 | 94.81% | $5.29 | No |

Production and mode-0 baseline exact native parity passed (`r9_70_a_progress.json`, `parity.passed=true`). Full descriptive hold60 and hold90 replays were allowed after both development arms failed; they reproduced the same 56 and 58 positions respectively, with the same PnL. They add no new trades after December and do not rescue the gates.

## Loss, margin blocks, inactivity

Mode-0 accepted baseline closes reconcile independently from its deals export to native HTML and final balance: 98 entries + 98 closes, net -$59.37, final balance $10.63. All 98 positions opened and closed in December 2025. Exit comments / deal reasons reconcile to 68 stop losses (-$253.08), 27 take-profits (+$189.24), and 3 expert-coded one-hour closes (+$4.47). No stopout deal or stopout message appears. Sides: 47 buys, 17 wins, +$2.54; 51 sells, 13 wins, -$61.91. The longest losing streak was 12. The largest losing position was -$9.29, matching the native report.

The mode-0 raw ledger records 98 accepted order attempts, then first `margin_block` on 2025-12-11 01:10:00 with no order attempt/retcode/deal. Matching journal text states required margin $8.46 exceeded the 70%-of-free-margin budget ($7.44 from $10.63 free margin). Last raw margin block was 2026-09-30 18:26:00; journal says $8.31 exceeded the same $7.44 budget. The raw gate-count total is 14,299: December 959, then January–September 1,720 / 2,173 / 2,389 / 1,805 / 1,581 / 2,082 / 737 / 421 / 432. Journals `journal_7.txt` and `journal_10.txt` mirror these events; counts above use the raw CSV once, not duplicated journal totals.

Both continuation arms also had all fills in December; January–May had zero closed positions despite continuing history and candidate margin blocks. Hold60 first margin block: 2025-12-10 20:40, required $8.38 versus 70% budget $7.49 from $10.70 free margin. Hold90 first margin block: 2025-12-11 02:10, required $8.48 versus 70% budget $3.70 from $5.29 free margin. Across their full descriptive runs, raw `margin_block` counts were 9,052 (hold60) and 9,045 (hold90); last recorded event for both was 2026-09-30 18:26. Neither arm had stopout. These data support a concrete mechanism: the fixed margin guard rejected eligible entries after account equity had been depleted, leaving later months without fills. They do not show what rejected trades would have earned.

Hold60 development: 40 SL losses net -$207.36, 9 TP wins +$129.22, 7 time exits +$18.84. Hold90: 43 SL losses -$224.12, 10 TP wins +$139.06, 5 time exits +$20.35. Hold60 side totals were 24 buys/+ $20.91 and 32 sells/- $80.21; hold90 totals were 26 buys/+ $13.90 and 32 sells/- $78.61. Small, all-December samples; do not select a side or infer a general directional edge.

In the descriptive full-window pairing, 53 opening identities matched by open timestamp, side, volume and price. Their realized net delta was +$7.05 for hold90; 3 unmatched hold60 positions netted +$6.06 and 5 unmatched hold90 positions -$6.40. Matched exit transitions: 38 SL→SL, 8 TP→TP, 5 time→time, 1 time→SL, 1 time→TP. Overall hold90 still ended $5.41 worse than hold60, with 2 more positions and 5.30 percentage-points higher equity drawdown. This is descriptive paired accounting on already inspected history, not independent validation or prospective evidence; occupancy makes unmatched positions path-dependent.

## Evidence and interpretation limits

- Production HTML: `runs/r9_70_a_production/r9_70_a_production.htm`; accepted signature/result: `runs/r9_70_a_production/accepted.json`.
- Exact mode-0 export: `runs/r9_70_a_baseline/accepted.json`, `r9_70_a_baseline.htm`, `r9_70_a_baseline_deals.csv`, `r9_70_a_baseline_raw.csv`, `r9_70_a_baseline_spec.csv`, and journals. Hold-arm exports are in corresponding `r9_70_a_dev_hold60`, `r9_70_a_dev_hold90`, `r9_70_a_descriptive_hold60`, and `r9_70_a_descriptive_hold90` folders.
- Completed gates and null confirmation: `reports/v25_research_20261008_capital70/r9_70_a_complete.json`.
- Validation used the runner's accepted-report/SET/INI/deal/cash reconciliation and independent `parse_verified_native_deals`; no special native end-of-test close was needed (`native_end_close_audit.verified=false`, no whitelisted tickets). This means no close was missing, not an accounting exception.
- Baseline extra-cost accounting stress at +$0.20/position was -$78.97; hold60 -$70.50; hold90 -$76.31. These are hypothetical fixed-position cost sensitivities, not replayed spreads or additional realized native losses. The actual native fills already reflect Bid/Ask.
- This result does not establish that 1:500 caused the trading loss: leverage affects margin capacity, while the observed results include the specific $70 capital, fixed lot, strategy, margin rule and historical path. Do not convert earlier $10,000 runs to $70 or derive planned stop dollars from unreliable tick-value fields.

The actionable finding is operational, not a V25 signal discovery: USD70 with fixed 0.01 lot and this stop/margin policy depleted to roughly $5–11 before year-end and then blocked trades, without broker stopout. Current risk-clone proposal must use broker-native account-currency risk calculations and preserve rejected events; it cannot assume smaller margin blocks imply a profitable strategy. No further signal/exit tuning is supported by this batch. Any follow-up remains separately preregistered historical research; the inspected months are not unseen OOS.
