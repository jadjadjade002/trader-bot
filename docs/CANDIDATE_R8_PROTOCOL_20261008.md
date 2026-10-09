# R8 continuation-quality factorial

Locked before R8 generation, compile or outcomes. Research only, not V25.

## Rationale and limits

R7 target screen ended without qualification. P1/TP0.6R descriptive ten months:202 positions, net$73.61, PF1.2128, WR64.36%, DD0.34%, six positive months. Validation28 positions falls below40 and whole-period net below V24$130.00. Closer targets improved frequency of winning trades, not enough release evidence. No further target sweep in R8.

R1 continuation P2/SL2/TP3 had1,797 development positions and net$808.41 but PF1.0896. Its descriptive ten-month PF1.0457 and cost fragility motivate testing measurable continuation quality, not claiming false breakouts are the proven cause. This starting config was selected from an earlier development maximum. R8 is post-selection mechanism research using inspected historical data, not independent validation. Preserve gates and every loss.

## Frozen parent and controls

Parent `research/ResearchCandidate_R1.mq5`, SHA256 `0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2`.

Keep parent closed M1/M5 trend and continuation direction, preset2 body/close/buffer, fixed SL2ATR/TP3R, minimum150points, hold60 completed M1 bars, BEoff, fixed0.01lot, hardSL/margin/breaker unchanged. No buy-only/sell-only selection, stacking, inversion or grid. Existing V24 mode0 parity remains P0/SL1.5/TP2, separate from continuation controls.

Prefix `r8_a`, same approved `reports/v25_research_20261008_postupdate` root, build6246 and complete monthly cache records equal to `r5_d_baseline`. Reuse exact accepted V24 production from this root. Obtain a fresh accepted R1 P2/SL2/TP3 development control using current runtime/cache, then demand exact ordered native economics from R8 both-factors-off. Old-cache R1 aggregates motivate the hypothesis but cannot be substituted for a same-cache control. Controls precede new outcomes.

## Exactly three new treatments plus one control

| ID | ER factor | Extension factor |
| --- | --- | --- |
| k0_e0 | Off, exact R1 control | Off |
| k1_e0 | ER10>=0.30 | Off |
| k0_e1 | Off | Extension<=1.00ATR |
| k1_e1 | ER10>=0.30 | Extension<=1.00ATR |

`ER10 = abs(close[1]-close[11]) / sum(abs(close[i]-close[i+1]), i=1..10)`. Eleven observed completed M1 bars in series order, strictly descending positive timestamps and positive finite closes. These are ten observed bar transitions, not necessarily ten wall-clock minutes. Do not impose exact60-second adjacency or a new session-gap filter. Gap-spanning observations may affect ER and must be reported. Flat denominator, malformed or missing ER context rejects ER-on signals with an explicit availability reason. ER-off performs no ER lookback and must preserve original behavior.

`Extension = abs(close[1]-EMA9[1]) / ATR14[1]`. Closed shift1 only, positive finite ATR and prices, equality1.00 passes, symmetric sides. Extension-off does not impose this filter. ER and extension tests are inclusive at their thresholds. Original quote/spread/chase gates remain. No future label, active-bar value, MFE/MAE or realized PnL enters predicates.

KER hypothesis: low directed movement relative to traveled price distance may identify noisy continuation entries. Extension hypothesis: distance from the short-term mean may identify late entries. Both can reject profitable trends. Their causal value is unknown until native replay. Do not call an excluded trade a saved loss without full replay and changed-occupancy accounting.

## Environment, gates and sequence

XAUUSD M1 MetaQuotes-Demo Model4 real ticks,200 ms, structural$10,000, leverage1:200, local connection113802049. This is not performance of the newly created$70/1:500 account or brokerXM.

After V24 mode0 and exact R1 off/off control parity, run all three new development treatments on `[2025-12-01,2026-06-01)`. Fixed gates: net>0, PF>=1.20, N>=150. Keep control result and every treatment outcome, do not count reused control as a novel strategy.

Every treatment survivor goes to validation `[2026-06-01,2026-08-01)`, requiring net>0/PF>=1.20/N>=40. Lock one by lowest validation native DD, highest net, stableID. No reselection after confirmation. Confirmation `[2026-08-01,2026-10-01)` requires net>0/PF>=1.10/N>=40. Ten-month net>0/PF>=1.15/N>=150, >=7 positive months, net>V24 and DD<=V24. Extra$0.20 fixed-trade accounting stress must stay positive,500 ms native PF>=1.10 and net>0,$70 native net>0/no stopout. Report$0.50 sensitivity. Requested1:500 conditions need a separate declared test if a candidate qualifies.

If none qualifies on validation, choose one descriptive ten-month treatment using development net/DD/stableID only. No qualified selection, no deployment or V25 name from that replay. No threshold fitting, reduced floors or pooled trade counts.

## Evidence and safety

Both-off calls the parent signal unchanged, without feature reads. Native MQL fixtures must test ER trend/chop/flat/short/malformed/order validity, exact thresholds, extension mirror/equality, and factor-off behavior. Native report count/net/coverage, source/binary/SET/runtime/cache must reconcile. Diagnostic fields explicitly mark ER/extension availability and source bar times, with blank unavailable values, not fake zeroes. No clocks converted to UTC without evidence. Quote/session gaps and censored held/breaker signals reported, not discarded from economic totals.

For all treatments, compare actual raw ResultDeal -> native opening ticket -> position. Pair exact executed entries, report matched outcomes and all new/unmatched trades, occupancy, missed winners, economic costs and worst loss. Genuine prospective proof is still unestablished. C1 session closure remains `UNRUN_SCHEDULE_UNVERIFIED`, not replaced by hardcoded known-gap hours.

Independent Luna logical review found the bounded factorial defensible under these caveats. That review is not final-source review or native validation. No VM, existing charts/accounts, collectors, credentials or Git mutations in this experiment.

## Final pre-run build

Generated source SHA256 `AC9D5D89A5E92E60815A5870D5E1A9636DBD452E00DEDD38967021AC845D6C74`, binary SHA256 `004B55DA23E7769F7EFC56526EF9066F41D70BD7C44953246803E8192C14B0AB`. Main compiled0 errors/0 warnings,1026 ms. Actual native fixture requirement27, not merely Python equivalents. Diagnostics distinguish decision bar shift0 from closed signal bar shift1.

Independent Luna reviewer directly verified final files/hashes, validator, off/off wrapper and native backend guard. Focused45 Python tests passed. Main affected suite270 passed plus143 subtests. Reviewer did not compile or run native. These checks authorize bounded research execution, not profitability or release.

## Export-only recovery amendment, before treatment outcomes

`r8_a` stopped at incomplete R1 control export, before any of the three treatments. Preserve its accepted baseline and failed control, never reuse those signatures with changed sources. New prefix `r8_b` uses the same fixed treatments and gates, not another strategy search. Native end-close lies after the last quote, so only `OnTester`'s post-test deals query upper bound changes to `D'3000.12.31 23:59:59'`. Online history windows and immutable R1 parent remain unchanged. Dedicated reporting control is generated from the pinned parent with only version/description and the identical post-test query repair. Native completeness must prove the missing close is captured, otherwise abort. Full recovery evidence and exact build hashes are recorded in `docs/CANDIDATE_R8_EXPORT_RECOVERY_20261008.md`.

New R8 source SHA256 `03CD489C2C51BDA9F87CA88AA231FFF25206071BFFDBA73ACDDCFD1597431974`. Reporting-control source SHA256 `961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B`. Both hashes enforced by runner before native launch. No treatment result has been inspected under this amendment.
