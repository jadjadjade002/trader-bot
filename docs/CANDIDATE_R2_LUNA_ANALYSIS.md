# R2 accepted development readout

Scope: all ten accepted R2 development runs, Dec 1, 2025–May 31, 2026. Family labels follow `research/run_candidate_r2.py:FAMILIES`. Complete development list contains exactly these ten mode/preset pairs; all ten are marked ineligible. No validation, confirmation, or full-candidate result used.

Each record reports 100% real ticks, verified cache hashes, and no terminal cache-read warnings. PF = net profit factor. Cost column applies hypothetical extra $0.20 per completed position; it is diagnostic accounting stress, not a qualification or selection gate.

| Family / mode | Preset | Run | Net | Net PF | Positions | Net / pos. | Net after $0.20 / pos. |
|---|---:|---|---:|---:|---:|---:|---:|
| deeper_pullback / 1 | 0 | `r2_a_dev_1_0` | +$81.88 | 1.0122 | 1,812 | +$0.0452 | -$280.52 |
| deeper_pullback / 1 | 1 | `r2_a_dev_1_1` | +$173.91 | 1.0264 | 1,776 | +$0.0979 | -$181.29 |
| compression / 2 | 0 | `r2_a_dev_2_0` | -$208.46 | 0.9084 | 562 | -$0.3709 | -$320.86 |
| compression / 2 | 1 | `r2_a_dev_2_1` | -$73.63 | 0.9646 | 526 | -$0.1400 | -$178.83 |
| range_reversal / 3 | 0 | `r2_a_dev_3_0` | -$86.97 | 0.6794 | 75 | -$1.1596 | -$101.97 |
| range_reversal / 3 | 1 | `r2_a_dev_3_1` | -$66.91 | 0.6858 | 57 | -$1.1739 | -$78.31 |
| break_retest / 4 | 0 | `r2_a_dev_4_0` | -$3.56 | 0.9836 | 59 | -$0.0603 | -$15.36 |
| break_retest / 4 | 1 | `r2_a_dev_4_1` | +$13.15 | 1.0656 | 56 | +$0.2348 | +$1.95 |
| exhaustion / 5 | 0 | `r2_a_dev_5_0` | +$41.97 | 1.0369 | 339 | +$0.1238 | -$25.83 |
| exhaustion / 5 | 1 | `r2_a_dev_5_1` | +$7.61 | 1.0142 | 156 | +$0.0488 | -$23.59 |

## Qualification

Protocol requires each configuration to have net > 0, net PF ≥ 1.20, and at least 150 closed positions. None qualifies. Five of ten show positive net, but best PF is only 1.0656. Both range_reversal runs and both break_retest runs also miss the 150-position minimum (57–75 and 56–59 positions). The sample gate applies per candidate; combined counts across runs cannot substitute.

Both deeper_pullback presets clear net and position count, but PF remains 1.0122–1.0264. Both compression presets lose net. Exhaustion has enough positions in both presets, but PF remains 1.0142–1.0369. Its positive raw nets turn negative under the hypothetical $0.20 stress. Break_retest preset1 stays only +$1.95 under that stress and still fails position count and PF. Stress is not part of the frozen gate.

## Direction and shared exits

BUY-side net is negative in all ten runs. SELL-side net is positive in deeper_pullback, break_retest, and exhaustion; both sides are negative in compression and range_reversal. These side totals are descriptive aggregates. They do not prove a direction bug: exit-code totals have the same broad pattern across families, while accepted summaries lack side-by-exit cross-tabs and no controlled replay isolates direction from entry selection.

Across all ten records, exit code 4 contributes losses (3,662 positions, combined net -$20,191.51); exit code 5 contributes gains (1,679 positions, +$19,988.05); code 3 is smaller (77 positions, +$82.45). Treat codes as identifiers only; this note assigns no semantic label. Shared exit-code economics cannot identify which direction caused the losses.

## Evidence boundary

Native development evidence covers these ten six-month runs only. No market-regime or direction-by-exit attribution is present in the accepted summaries. Root separately documented 25 passing actual MQL native fixtures; source-contract checks are separate and are not native MQL tests. No regime, direction defect, candidate selection, release, or deployment conclusion follows from these results.
