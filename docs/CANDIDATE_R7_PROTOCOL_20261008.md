# R7 low-target experiment

Locked before R7 generation, compilation, or native outcomes. Research only, not V25.

## Evidence and hypothesis

R4 P1 development used 156 entries. TP1 realized $98.82, PF1.2759. TP2 realized $7.61, PF1.0142. Paired TP2 to TP1 outcomes include 32 SL-to-TP changes, offset by smaller gains on existing winners. R5 reproduced TP1, but its descriptive ten-month result was -$2.68. R6 F1 produced $21.70 across ten months on only 53 trades and failed acquisition/consistency gates. None qualifies.

Hypothesis: the unchanged exhaustion/reclaim entry may have more short-lived favorable movement than its existing targets capture. Test nearer targets, accepting smaller wins and requiring stronger win frequency after actual execution costs. A higher win rate alone is not improvement.

## Exactly four new cells

| Stable ID | InpEntryStrength | InpStopLossATRMul | InpTakeProfitRRMul |
| --- | --- | --- | --- |
| p0_tp0p5 | 0 | 1.5 | 0.5 |
| p0_tp0p6 | 0 | 1.5 | 0.6 |
| p1_tp0p5 | 1 | 1.5 | 0.5 |
| p1_tp0p6 | 1 | 1.5 | 0.6 |

Use tester-only mode5. Source parent `research/ResearchCandidate_R4.mq5`, SHA256 `AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320`. Entry predicates, guards, one-position occupancy, breaker, minimum stop, hold policy and sizing unchanged. No M1-alignment filter, BE, inversion, stacking, grid or martingale. Do not change thresholds after outcomes.

R is the inherited nominal stop distance: `max(1.5 * closed ATR14, 150 * point)`, before separate outward tick rounding and the 200 ms fill delay. Actual rounded/fill risk may differ. Do not silently redefine R using actual filled risk. R4 lines 1063-1104 establish this geometry.

Native actual fixtures: inherited 25 plus six named R7 target assertions =31. Mode0 must reproduce V24 economics exactly with SL1.5/TP2. Separate mode5 TP1 P0/P1 controls must reproduce the accepted R4 controls before any new-cell execution. TP1/TP2 are controls, not extra screened cells.

## Final pre-run build and review

Generated source SHA256 `1EEED145819D57B6F4D85CE1D13A7AF4DF5DC3E0FCBEB885EDE2B624DED2B38C`, binary SHA256 `CCAA1D266B2306348CAFE40FCDA12209DA812CADD8EE170F5359AE8D9A4E778E`. Main compiled with0 errors/0 warnings,1129 ms. Source mode5 rejects TP2, while mode0 retains strict TP2. Generic `ConfiguredR` journal text replaces inherited hardcoded2R labels without changing execution arguments.

Independent Luna reviewer read final source and runner, verified both hashes and ran40 focused generator/runner/adapter tests. Reviewer did not compile or launch native tests. Main affected suite:213 passed plus143 subtests. This pre-run review validates bounded execution, not profitable strategy results.

## Frozen environment and provenance

Prefix `r7_a`, evidence root `reports/v25_research_20261008_postupdate/`. Build6246 runtime and per-month real tick cache hashes must match accepted `r5_d_baseline`. Reuse only explicit root-approved controls `r5_d_production_v24`, `r5_d_r4_control_p0`, `r5_d_r4_control_p1`. Full signature validation required. Preserve all attempts, never accept update/relaunch as strategy completion.

XAUUSD M1, MetaQuotes-Demo native Model4 real ticks, 0.01 lot, 200 ms delay, structural $10,000, tester leverage1:200. Local connection113802049 is Demo $70/leverage500, but this is not the tester deposit/leverage. No VM change. The requested $70/1:500 deployment geometry requires its own later test and cannot be inferred from a $70/1:200 stress.

## Gates and sequence

1. Exact baseline and both TP1 controls, same runtime/cache, 31 actual fixtures.
2. Run all four development cells on `[2025-12-01, 2026-06-01)`. Each needs net>0, net PF>=1.20, >=150 closed positions.
3. Send every development survivor to validation `[2026-06-01, 2026-08-01)`. Each needs net>0, PF>=1.20, >=40 positions. No top-three cap.
4. Select one validation survivor by lowest native equity DD, then highest net, then stable ID. Save immutable selection lock before confirmation. No reselection after failure.
5. Confirmation `[2026-08-01, 2026-10-01)` needs net>0, PF>=1.10, >=40 positions.
6. Locked whole ten-month result needs net>0, PF>=1.15, >=150 positions, >=7 positive months, net above V24 and equity DD no worse than V24.
7. Require positive net under extra $0.20 per-position fixed-trade accounting stress, positive 500 ms native replay with PF>=1.10, positive $70 native replay with no stopout. Report extra $0.50 sensitivity without turning it into a post-outcome gate.

If no validation-qualified cell, keep every outcome and run one descriptive full-period replay, chosen using development only. It is not confirmation, not a qualified selection and never a release. Do not lower gates, pool sample counts, remove losses, or select using descriptive full-period profit.

## Interpretation and handoff

Report native net/PF/WR/count/DD, monthly and side breakdown, actual exit reasons, fixed-trade cost sensitivities and worst trade. When pairing exits, match actual opening deal/position via exported ResultDeal and native history, not estimated minute equality. Count unmatched entries and occupancy/breaker changes. Low TP requires approximately 66.7% gross wins at 0.5R or 62.5% at 0.6R before costs for ideal fixed-risk binary outcomes. Actual unequal risks, rounded prices, time exits, swap and gaps invalidate treating those as actual break-even estimates.

All historical windows were inspected in earlier work. They are not genuinely unseen OOS. Any prospective confirmation starts only after immutable source/binary/settings/selection lock. No V25 name or deployment until qualification, independent review and fresh target verification. No guaranteed future profit.
