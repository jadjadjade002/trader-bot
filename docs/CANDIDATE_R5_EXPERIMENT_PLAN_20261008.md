# R5 research plan derived from winner attribution

Status: PRE-IMPLEMENTATION. Not V25. No new native strategy replay, compiled EA or deployment yet. Baseline V24 and accepted R1/R2/R3/R4 artifacts remain frozen.

## Activation amendment, 2026-10-07 19:15 UTC

The status above records the original preregistration. The latest user authorized bounded research iterations and deployment only after V25 qualification. Activate the four C0 cells now. All four C1 cells remain `UNRUN_SCHEDULE_UNVERIFIED`. No VM action is authorized by a failed or merely descriptive result.

Final tester source: `research/ResearchCandidate_R5.mq5`, SHA256 `98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494`. Freeze the newly compiled binary before launch. Native fixture contract is exactly 27 checks. Evidence destination is `reports/v25_research_20261008/`. Preserve the previous evidence root.

In addition to production V24 mode0 parity, both A0 development cells must reconcile native metrics and ordered order/deal economics against their accepted R4 controls before selection. A failed reconciliation aborts the batch.

Instrumentation does not move signal evaluation ahead of held-position or breaker gates. Those opportunities are censored and explicitly labeled, with unavailable features blank. Evaluated rows log actual closed signal OHLC, body/ATR, close location from low, M1/M5 EMA values, ATR, the exact R2 pre-reclaim displacement `r[1].close-r[6].close`, sampled Bid/Ask and intended SL/TP geometry. Session fields are `n/a` for C0. Logged intended prices do not replace actual native fills. Legacy zero-filled breakout features are excluded from the R5 CSV schema. Therefore the earlier request for every pre-gate signal opportunity is not fulfilled by this instrumentation and must not be claimed.

Native attempt update: MetaEditor compiled the frozen source with 0 errors and 0 warnings, producing EX5 SHA256 `842722988E75991E79996EC0C969B8115ABF18EBFFD5C1E9AD49F217B7F2A320`. The first baseline attempt `r5_a_baseline` then stopped before EA initialization because the local tester could not use its saved demo account. No accepted R5 result or native fixture pass exists. Preserve the unaccepted attempt. This is `TESTER_ACCOUNT_UNAVAILABLE`, not a zero-trade profit result. Resume instructions are in `docs/V25_RESEARCH_RESUME_20261008.md`.

## Fresh-control amendment, 2026-10-08

The user created a separate local research demo. Read-only terminal verification confirmed the intended research data directory, MetaQuotes-Demo demo mode, USD70 equity/balance, 1:500 account leverage, and no positions or pending orders. Saved authorization exists in the research terminal. No password extraction, VM mutation, or production account change occurred.

Before any new R5 native outcome, the resumed runner rejected reuse of the previously accepted production V24 control. Signature comparison showed only `tick_cache` differed: all ten month files retained their recorded byte sizes but their complete SHA256 values changed. This does not prove equal quote data, header-only changes, or the cause of the rewrite. Do not edit the old hashes or accepted records, restore guessed cache contents, or ignore the drift.

Explicit fresh-control mode will rerun production V24 and both A0 R4 development controls under the current cache and explicit confirmed local demo login. New prefix: `r5_c`. Evidence root: `reports/v25_research_20261008/`. New production control: `r5_c_production_v24`. New R4 controls: `r5_c_r4_control_p0` and `r5_c_r4_control_p1`. Record `control_policy=fresh_same_cache` and exact control mapping. Existing legacy-control mode and records remain available but may not be silently used when current signatures differ.

Fresh V24 must match R5 mode0 ordered native economics. Both fresh R4 controls must match their respective R5 A0 development cells before selection. Validate source/binary, SET, started/accepted signatures, native completion/fixtures, HTML/deal/balance reconciliation, runtime, and current tick-cache provenance. Cross-run cache/runtime drift still invalidates comparisons. The attribution analyzer must use the explicit control policy to resolve only the known legacy or same-batch roots, not arbitrary paths from the manifest.

The 1:500 connection account does not change the frozen native tester's 1:200 leverage. Development, validation, confirmation, sample floors, top-three R5 shortlist, exits, costs, and risk gates remain unchanged. The requested USD70/1:500 operating condition requires a separate appropriately declared test before deployment, not relabeling the existing USD70/1:200 stress test.

This is a provenance recovery amendment, not a newly profitable result or permission to deploy an unqualified bot. Preserve `r5_a` setup failure and the pre-launch `r5_b` signature rejection. Native MQL behavioral fixtures and R5 profits remain unverified until accepted fresh runs exist.

## Runtime-update recovery amendment, 2026-10-08

The `r5_c_production_v24` parent process exited during automatic MT5 LiveUpdate. The updater relaunched its configured child, which subsequently completed and exited. Both terminal and tester binary SHA256 values changed from the frozen runtime. This run remains unaccepted even though its native HTML report exists. Preserve the original started signature, failure record, runtime freeze and subsequent child artifacts. Do not adopt the child result under its parent's old-runtime signature.

Before any new accepted outcome, declare a new evidence root `reports/v25_research_20261008_postupdate/` and prefix `r5_d`. Freeze the updated runtime there, then rerun the complete fresh V24 and R4 controls and the same four R5 cells. The experiment definitions and all selection/release thresholds remain unchanged. A new lab process-identity guard must refuse another launch while any lab terminal, tester, or targeted updater is active. Never disable LiveUpdate or kill unrelated processes as a workaround.

## Rationale

R4 preset1, SL1.5ATR, TP1R has exact 156-entry pairing with TP2R over six development months. Shortening the actual target improves net by $91.21 and turns 32 SL outcomes into TP. The historical ten-month diagnostic still returns -$2.68.

Two unproven mechanisms merit controlled tests: M1/M5 direction conflict at entry and exposure across quote or trading-session gaps. Neither is established as a profitable fix.

R1 TP1R loses in all tested cells. Do not generalize exhaustion's target to continuation or choose another target using later-month PnL.

## Eight fixed configurations

Factor P: existing R2/R4 displacement preset0/1, respectively 1.25ATR/1.75ATR.
Factor A: completed M1 EMA9/20 alignment off/on.
Factor C: pre-session-close entry blocking plus flattening off/on.

| Config | Preset | M1 alignment | Closure policy |
| --- | ---: | --- | --- |
| R5-P0-A0-C0 | 0 | Off | Off |
| R5-P0-A1-C0 | 0 | On | Off |
| R5-P0-A0-C1 | 0 | Off | On |
| R5-P0-A1-C1 | 0 | On | On |
| R5-P1-A0-C0 | 1 | Off | Off |
| R5-P1-A1-C0 | 1 | On | Off |
| R5-P1-A0-C1 | 1 | Off | On |
| R5-P1-A1-C1 | 1 | On | On |

No additional TP/SL grid. Fix SL1.5ATR with the original minimum150points, TP1R, max hold60 completed M1 bars, BEoff, 0.01lot, MetaQuotes-Demo XAUUSD M1, structural deposit $10,000, leverage1:200, real ticks and 200ms delay. Preserve hard SL, margin gate, magic and circuit breaker. No grid, martingale, inversion or live-account changes.

C deliberately combines entry blocking and flattening. The matrix separates C from alignment A, not the two components inside C. If C helps, separate its components in a later preregistered ablation. Changed policies may alter occupancy, available signals and breaker state. Include all new and unmatched positions in native totals.

## Activation and schedule prerequisite

Do not launch C1 until schedule and clock inputs have a documented historical applicability basis. Current session metadata and recurring sample gaps are not independent proof of historical market schedules.

Before C1 native tests:

1. Record broker/tester clock semantics. Do not convert broker clock to UTC without verified offset.
2. Export weekday symbol trade/quote sessions with index and clock source. Handle midnight crossings, multiple intraday sessions, 24-hour sessions and weekend transitions.
3. Reconcile September1/2 actual source ticks around the known event. Minute samples are not all raw quotes. Preserve the extreme Ask and every deal.
4. Record historical schedule changes, holidays and DST evidence. Otherwise mark historical applicability unresolved. The API has no historical-date argument.
5. Freeze one lead interval in the implementation manifest before new results. No buffer sweep. A proposed 10 elapsed minutes is an assumption for review, not an optimal value or a setting locked by this document.
6. If schedule applicability cannot be established, mark C1 UNRUN_SCHEDULE_UNVERIFIED. Do not hardcode22:50 or replace unavailable arms with zero-profit results. A0/A1 with C0 can be researched separately, but the factorial remains incomplete.

These hypotheses arose after inspecting history. Freezing now prevents further result-driven tuning. It does not erase historical contamination.

## Source contract and controls

- Create a new tester-only research source. Do not modify accepted sources or production V24.
- Preserve completed-bar predicates. Exact V24 baseline mode remains an independent parity control.
- R5-P0-A0-C0 must reconcile to accepted R4-P0-SL1.5-TP1 native orders, deals and economics on a common slice. R5-P1-A0-C0 must reconcile to R4-P1-SL1.5-TP1. Logging alone must not perturb either control.
- Fail initialization outside native tester. No account identifiers, credentials or external requests.
- Validate finite EMA, ATR, Bid and Ask, positive prices and Bid<=Ask. Entry filters use completed bars only, never future returns or active-bar features.
- A1 uses shift1 M1 EMA9/20. Buy requires EMA9>EMA20, Sell requires EMA9<EMA20. Equality or missing data rejects entry. This may also reject profitable early reversals.
- C1 derives its endpoint from an applicable schedule, not the known loser's hour. Block entries inside the frozen elapsed-time lead. Flatten while executable quotes still exist. Check ticks plus a bounded timer, verify retcodes and reconcile actual closes. No callback guarantees execution during a no-quote interval.
- Schedule lookup failure blocks new C1 entries and preserves normal management of existing positions. Log failed flatten attempts, bounded retries and carried exposure. Do not claim tail risk eliminated.
- Correct misleading legacy labels only in the new research source. Log actual input and executed SL/TP/R rather than a hardcoded2R label.

## Required diagnostics

For each signal opportunity before execution gates, record:

- broker bar time, tick milliseconds, side, mode and preset
- closed M1 EMA9/20, closed M5 EMA20/50 and historical EMA20 used for slope
- ATR, displacement/ATR, close location and initial SL/TP geometry
- actual Bid, Ask, spread, applicable session ID, endpoint and time-to-close
- A/C predicates, held-position and breaker state, order attempt, retcode and entry deal

For each completed position, record entry/exit milliseconds, side, volume, actual risk, profit, commission, swap, fee, net, final exit reason, duration in completed bars and elapsed seconds, closure attempts and known gap exposure. Sampled MFE/MAE timestamps must not precede entry-deal milliseconds. Samples are not complete first-hit paths.

Report all eight configs, native count/net/PF/equity DD, average win/loss, decisive and all-position win rates, monthly/side/exit tables, cost sensitivity, paired and unmatched entries, changed gates, missed opportunities and newly opened positions. Do not treat removed old losses as predicted improvement. Keep the worst trade in every relevant total.

## Selection and release gates

Keep the original historical qualification gates and the existing separate economic robustness screen:

- Development [2025-12-01,2026-06-01): net>0, PF>=1.20, positions>=150. Keep at most three qualified configs from this family, ordered by lower native DD, higher net, then stable config ID.
- Validation [2026-06-01,2026-08-01): net>0, PF>=1.20, positions>=40. Lock one candidate by validation DD/net/config ID before historical confirmation. No reselection after failed confirmation.
- Confirmation [2026-08-01,2026-10-01): net>0, PF>=1.10, positions>=40.
- Whole ten months: net>0, PF>=1.15, at least7/10 positive months, higher net than V24 and native equity DD<=V24.

For a qualified candidate only, run an independent $70 native replay without redeposit, requiring positive net and no broker stopout. Run separate 500ms native stress, requiring positive net and PF>=1.10. Hypothetical extra $0.20 per completed position must remain positive. Report $0.50 sensitivity too. Accounting cost stress is not spread simulation. MetaQuotes results do not establish XM readiness.

Prospective evidence begins after recorded source/binary/settings/selection lock and the next future broker session. Inspected October trades or collector rows are not unseen. If N remains too low, collect additional frozen future data. Do not lower thresholds or reoptimize until something passes.

## Falsification and stopping conditions

- A fails if it only reduces count without positive net expectancy or removes more useful winners than losses. Failed sample floors cannot be overridden.
- C fails if total native expectancy or DD worsens after flattening and missed winners, or gap exposure persists without explanation. Preventing one known loss is insufficient.
- P1 is not automatically better than P0. Select using frozen criteria, not the label stricter.
- Setup, parity, history, source or runtime drift invalidates a run. Retain failures. Never count invalid runs as zero-PnL successes.
- No qualification means no V25 and no VM replacement. State new native-test and deployment status separately from this plan.

## References

- docs/CANDIDATE_WINNER_ANALYSIS_20261008.md
- docs/V25_RESEARCH_PROTOCOL_20261007.md
- research/candidate_release_evidence.py
- docs/CANDIDATE_R4_GAP_DIAGNOSTIC.md
- reports/v25_research_20261007/r4_a_complete.json
- [MQL5 SymbolInfoSessionTrade](https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade)
