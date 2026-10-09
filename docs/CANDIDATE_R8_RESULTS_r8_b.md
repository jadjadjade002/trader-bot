# R8 results — `r8_b`

Status: research only. No treatment passed development; validation did not run. `qualified=false`, `promotion=false`; no V25 qualification or deployment. Offline attribution completed on 2026-10-08 and saved to `r8_b_attribution.json`. Preserve all accepted runs, losses, and the earlier `r8_a` failure unchanged.

## Controls and run integrity

The completed record is [`r8_b_complete.json`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/r8_b_complete.json). It records exact V24 mode-0 parity (`passed=true`) and exact R1 continuation off/off parity (`passed=true`). The fresh R1 reporting control was `r8_b_r1_control_retry1`; off/off R8 control was `r8_b_control_k0_e0`. Both report 1,797 trades, net `$808.43`, PF `1.0896`. This is an accepted six-month development control, not a ten-month off/off counterfactual.

R8 mode-0 baseline reports net `$130.00`, matching the V24 reference. The post-test export repair captured the native terminal close on the R1 control; its accepted result records verified native end-close accounting. The analyzer must still independently recheck accepted signatures, settings, runtime/cache, HTML, all deal exports, balances, and parity. No aggregate result below is an independent offline attribution verdict.

## Fixed development arms

All use P2 / SL `2.0 ATR` / TP `3R`; unchanged trading gates and native costs. Frozen floors: `N>=150`, net `>0`, PF `>=1.20`.

| Arm | Factor | N | Net | PF | Native equity DD | Extra `$0.20` stress | Extra `$0.50` stress | Dev gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `k0_e1` | Extension `<=1 ATR` | 1,328 | `$381.19` | 1.0555 | 4.85% | `$115.59` | `-$282.81` | Fail: PF |
| `k1_e0` | ER10 `>=0.30` | 1,435 | `$319.08` | 1.0424 | 5.81% | `$32.08` | `-$398.42` | Fail: PF |
| `k1_e1` | Both factors | 645 | `-$229.04` | 0.9342 | 5.02% | `-$358.04` | `-$551.54` | Fail: net and PF |

No treatment met the development PF floor, so none went to validation. Do not infer that removed trades were “saved losses”; the three arms also change trade count and later occupancy.

## Development-only descriptive replay

With no validation-qualified arm, the runner selected `k0_e1` from development outcomes for descriptive ten-month replay only. [`r8_b_descriptive10m/accepted.json`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_descriptive10m/accepted.json) reports N `1,837`, net `$131.17`, PF `1.0145`, native equity DD `5.81%`, extra `$0.20` stress `-$236.23`, extra `$0.50` stress `-$787.33`. The result has 552 wins and 1,285 losses.

Monthly net in the completed record: Dec `-$31.40`; Jan `+$226.50`; Feb `-$126.60`; Mar `+$543.11`; Apr `-$23.41`; May `-$207.01`; Jun `-$34.97`; Jul `-$87.85`; Aug `-$104.93`; Sep `-$22.27`. Thus **2 positive and 8 negative months** (not 4/6). The ten-month net is `$1.17` above V24’s `$130.00`, but PF is below the frozen `1.15` ten-month floor, DD exceeds V24’s reported `5.71%`, and the additional `$0.20` cost stress is negative. This is not a qualifying candidate.

R8 has no same-config ten-month off/off R1 control. The accepted off/off comparison covers development only. Therefore the descriptive full-period difference cannot be attributed to the R8 factor as a full-period causal effect. Keep the realized historical result and every loss; do not delete outliers or select a new arm from confirmation-like data.

## Primary evidence

- [`r8_b_complete.json`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/r8_b_complete.json): matrix, frozen eligibility flags, selected descriptive branch, final qualification/promotion flags, full-period monthly totals.
- [`r8_b_descriptive10m.htm`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_descriptive10m/r8_b_descriptive10m.htm) and [`r8_b_descriptive10m_deals.csv`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_descriptive10m/r8_b_descriptive10m_deals.csv): native report and exported deal ledger.
- Accepted treatment records: [`k0_e1`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_dev_k0_e1/accepted.json), [`k1_e0`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_dev_k1_e0/accepted.json), [`k1_e1`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_dev_k1_e1/accepted.json).
- Controls: [`r8_b_baseline`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_baseline/accepted.json), [`r8_b_control_k0_e0`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_control_k0_e0/accepted.json), [`r8_b_r1_control_retry1`](D:/project/trader-bot/reports/v25_research_20261008_postupdate/runs/r8_b_r1_control_retry1/accepted.json).

## Completed read-only attribution, 2026-10-08

Command `python -m research.analyze_candidate_r8` completed successfully. Its
report label is `ATTRIBUTION_ONLY_NOT_RELEASE_QUALIFICATION`. It rechecked pinned
accepted/started signatures, settings, source/binary/runtime/cache identity,
native HTML, deal economics, native end-close accounting, final balances, and
all exact raw/signal entry joins. No EA source or accepted native run was changed.

Against the off/off development control, extension-only net changed by -$427.24,
ER-only by -$489.35, and both by -$1,037.47. Exact paired entries were 743, 865 and
237 respectively, with $0 paired economic change in each arm. Remaining total
deltas reconcile to unmatched entry/occupancy changes, not better exits on the
same positions. Thus these factors did not improve the observed development
payoff. Unmatched control winners are descriptive, not inferred saved losses.

The combined-factor audit reconstructed one ER10 threshold observation from 11
contiguous raw closes. Full-precision value was below 0.30 but its CSV rounded to
0.3000000000. The actual rejection is preserved, not overridden by epsilon.
Clock checks retained observed same-decision-bar feature sampling delays instead
of inventing a strict guessed millisecond cutoff. This fixes analysis precision,
not trading behavior.

There is still no same-config full-period off/off control for causal ten-month
factor attribution. No profitability, unseen OOS validation, V25 release, or
deployment follows from this completed attribution.
