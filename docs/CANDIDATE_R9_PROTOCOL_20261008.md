# R9 single hold-horizon contrast

Status: independently reviewed and approved for this bounded historical experiment. Implementation preparation only, no R9 native outcome yet. No V25 qualification, selection, or deployment approval.

## Question and evidence

Test one change only: for the frozen R1 mode-1 continuation setup, compare `InpMaxHoldBars=90` with the unchanged 60-bar control under the existing `iBarShift` M1-bar-distance implementation. Keep P2 (`InpEntryStrength=2`), SL `2.0 ATR`, TP `3.0R`, and all signal predicates fixed. No ER/extension filters or thresholds, TP/SL sweep, break-even, circuit-breaker, sizing, or other entry/exit changes.

Rationale is a question, not a conclusion. In accepted same-cache development control `reports/v25_research_20261008_postupdate/runs/r8_b_control_k0_e0/accepted.json`, strict accepted-result/report/deal/accounting checks passed, including verified native terminal close. Its 1,797 positions reconcile to 1,797 unique path records with finite positive initial risk. Exit-reason totals: time exit 247 / +$1,504.64, stop 1,211 / -$8,860.98, target 338 / +$8,164.75, and one terminal liquidation / +$0.02.

In this control, time-exit positions had median sampled MFE `2.002R`, with median time-to-sampled-MFE `36.7` minutes; 201 of 247 closed positive. Target is `3R`. An additional 30 bars might let some continuation positions reach target, but could also surrender open gains and occupy the single-position slot longer. This is the sole rationale for testing 90 bars against 60.

The same path export shows stop-exit median sampled MFE `0.433R`; 548/1,211 reached at least `0.5R`, 292/1,211 at least `1R`, and 145/1,211 at least `1.5R`. These observations do not support a break-even rule or another entry filter. R8 already tests entry-quality factors, do not duplicate that factorial here. At approval, overall R8 attribution remains blocked by a rounded ER threshold value in a treatment. R9 rationale relies only on independently reconciled R1 and off/off controls, not treatment attribution.

`ObservePath` samples bid for buys and ask for sells during EA callbacks (`research/ResearchCandidate_R8.mq5:518-538`). MFE is not an exact intratick path or a counterfactual trade result. Its elapsed wall-clock age can cross market gaps. Do not convert sampled MFE into claimed saved losses or hypothetical PnL.

## Frozen implementation boundary

Use the pinned R1 continuation logic and its existing `InpMaxHoldBars` mechanism. Mode 1 treatment sets only `InpMaxHoldBars=90`; mode 1 control remains 60. Mode 0 parity must retain 60 and exact V24 economics. Preserve P2, SL2/TP3, fixed 0.01 lot, one-position occupancy, hard stop, margin guard, breaker (four consecutive losses / 90-minute cooldown), closed-bar signal timing, session/spread settings, and all other inputs. The time exit remains based on `iBarShift` M1 bars, not elapsed minutes (`research/ResearchCandidate_R1.mq5:547-560`).

Keep parent `research/ResearchCandidate_R1.mq5` immutable at SHA256 `0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2`. The already-reviewed post-test history-export upper-bound repair may be applied only as a reporting revision, outside online handlers and trade logic. It must not change online `HistorySelect` windows or execution. Validate inclusion of any native terminal close after the final observed quote using raw ledger, native HTML, journal, and balance; preserve original deal rows. If reporting repair cannot be proven isolated, abort.

Implementation reuses the already compiled, unchanged reporting clone `research/ResearchControl_R1_R8.mq5` and binary. Source SHA256 `961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B`, binary SHA256 `2F59FC1F06CDAFF468F137ACF650C4198CE4BDB68CC6962551CFEBDBC46535CE`. No new EA source or compile is required. An explicit `r9_hold=True` backend profile permits only hold60/90 with P2/SL2/TP3, and is recorded in new signatures. Old R8 profile and accepted signatures remain unchanged.

## Controls, environment, and run sequence

Use only approved root `reports/v25_research_20261008_postupdate`, current MT5 build 6246, and complete per-month real-tick cache identical to `r5_d_baseline`. Freeze and reconcile runtime, cache manifests, source, binary, SET, INI, and signatures for every run. Do not follow paths supplied by evidence manifests outside this fixed root.

Before any treatment outcome:

1. Verify the frozen V24 production baseline and exact mode-0 parity at P0 / SL1.5 / TP2 / hold60, comparing ordered native economics. Reuse accepted `r8_b_baseline` only if its complete signature, current runtime and all-month cache still match.
2. Verify fresh same-runtime/cache mode-1 off/off control P2 / SL2 / TP3 / hold60 against the accepted R1 control `r8_b_r1_control_retry1`, including ordered native economics and terminal-close accounting. Keep control and treatment exports distinct.
3. Only after both controls pass, run the single mode-1 treatment P2 / SL2 / TP3 / hold90.

Require same model, symbol, real ticks, 200 ms delay, structural $10,000 deposit, leverage 1:200, fixed 0.01 lot, and all-month cache identity. Any runtime/cache drift, parity mismatch, incomplete export, or accounting mismatch stops the batch before interpretation. The post-test history query repair is reporting-only; it does not authorize changes to the immutable R1 parent.

Frozen windows: development `2025.12.01` to `2026.06.01`, validation `2026.06.01` to `2026.08.01`, confirmation `2026.08.01` to `2026.10.01`, full `2025.12.01` to `2026.10.01`. Development must pass before validation. Validation must pass before a durable source/binary/configuration lock and confirmation. Lock timestamp must precede confirmation start. No post-outcome edits or reselection.

Paired hold60/90 mechanism inference is limited to development, where both arms run on identical dates. Any later hold90 replay evaluates candidate gates only. No full-period hold-effect estimate is claimed without a matched full-period hold60 control. `iBarShift` distance, elapsed wall time and sampled path age are different quantities, report them with explicit labels.

## Frozen gates and interpretation

Do not lower or reinterpret existing floors. The 90-bar development treatment must meet net > 0, PF >= 1.20, and at least 150 closed positions. If it proceeds, validation requires net > 0, PF >= 1.20, and at least 40 positions. Confirmation requires net > 0, PF >= 1.10, and at least 40 positions. Full ten-month robustness requires net > 0, PF >= 1.15, at least 150 positions, at least 7/10 positive months, net above V24, and equity drawdown no higher than V24. Preserve cost/operational screens: positive net under the hypothetical additional $0.20 per-position accounting stress, positive 500 ms native replay with PF >= 1.10, and positive $70 replay with no stopout. Report $0.50 sensitivity; it is not an additional gate.

Report both arms in full: all paired and unmatched entries, changes in entry count/occupancy/breaker state, actual exit reasons, monthly and side results, native net/PF/drawdown, worst trade, cost stress, and terminal liquidation. Pair by native opening deal/position identity, not approximate minute matching. Do not drop losses, infer saved stopouts from MFE, or claim improvement from time-exit-to-target transitions unless those transitions occurred in actual native treatment results.

All development, validation, confirmation, and ten-month dates here are already inspected historical data. Even if every historical gate passes, label result retrospective and post-selection; it is not genuinely unseen OOS or prospective confirmation. Only a new, separately locked future sample can establish prospective evidence. No outcome guarantees profit or authorizes V25 naming/deployment.
