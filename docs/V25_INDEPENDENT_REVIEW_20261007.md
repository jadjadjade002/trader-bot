# V25 independent review, 2026-10-07

Scope: local read-only inspection of V24, native evidence and V23 harness. No VM, accounts, keys, credentials, native tester or external agent communication. This document is an audit, not evidence that V25 has passed.

## Verified baseline

- `AegisPredator_v24.mq5:487-501`: baseline already follows completed M5 EMA20/EMA50 trend and five-bar EMA20 slope, then completed M1 EMA9 reclaim aligned with EMA20. Buy and Sell mirror one another. A rising current M1 candle does not establish completed M5 bullish trend. A simple inversion is not the missing V24 feature.
- `AegisPredator_v24.mq5:116-120`: FadeBreakouts must be false, XAUUSD M1, demo only. `:405` replaces the old Donchian recognition result with ProposedSignal. Old Donchian calculations remain availability prerequisites, not active direction selection.
- `AegisPredator_v24.mq5:496`: spread <= 0.1 M1 ATR and midpoint displacement <= 0.5 ATR from completed candle close. A later run should retain a reason ledger to distinguish no signal from blocked execution.
- `research/build_v24.py:generate`: packaging starts from hash-frozen V23, copies tested ProposedSignal, ReadClosed and ReleaseExperiment, preserving breaker and position-management bodies.
- `research/verify_v24_native.py:12-36`: production V24 replay compared ordered economic rows after comment-version normalization, nine metrics and cache hashes.
- `reports/v23_tuning_20261006/v24_demo_20261006_v24_parity.json`: passed five-month parity. 1,476 positions, net -165.23 USD, 58,118,739 ticks, 143,336 bars, 100% real ticks. This is negative historical evidence, not a profitable baseline.
- Frozen V24 source SHA256: `5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E`.
- Frozen V24 EX5 SHA256: `5A11086D05F7AA5C4E0B3D806B58BFF446BE08CC0EC8A48944A7681D42A539AF`.

## Ten-month interval and contamination

Requested latest ten complete months: `[2025-12-01, 2026-10-01)`. End exclusive. October is incomplete on client date 2026-10-07. Do not silently substitute a shorter interval or include partial October and call it ten complete months.

At initial inspection local tick folder `.mt5-v23-tuning.local/bases/MetaQuotes-Demo/ticks/XAUUSD` contained 202605 through 202610 only. During subsequent acquisition, files 202512 through 202604 appeared. All ten requested monthly cache files now exist. Real-tick observed coverage remains unverified until native evidence audit. File presence/size alone cannot establish quality or daily continuity.

The May-Sep2026 interval was already inspected, optimized and used to select V24. Therefore Jun-Jul validation and Aug-Sep confirmation are historical reused evaluation windows. They cannot honestly be untouched out-of-sample evidence, even if a V25 config is frozen before this new run.

Recommended honest policy:

1. Freeze signal families, bounded grid, selection rule, cost assumptions, dates and rejection criteria before V25 native runs.
2. Development Dec2025-May2026, reused historical validation Jun-Jul2026, reused historical confirmation Aug-Sep2026. Report each label explicitly. Full ten-month aggregate is descriptive historical robustness, not a separate independent confirmation.
3. Evaluate chronological rolling folds without fitting on future folds. Example initial train Dec-Feb, test Mar, expand train through Mar, test Apr, then continue. Reused months remain contaminated at research-design level. Label walk-forward as retrospective temporal robustness, not untouched data.
4. Set boundaries for closed positions/forward labels so a training outcome cannot use prices after its training cutoff. Embargo a full maximum holding/label horizon at boundaries for label-based analysis. Native EA resets/forced end exits and warmup must be disclosed separately from continuous full-period performance.
5. Reserve data after strategy/config freeze for true prospective confirmation. October data already examined cannot be retroactively called unseen. Choose a future start after freeze and do not use its results for selection. Failed confirmation permits a new candidate only with a new future confirmation window.
6. Maintain complete trial ledger, including failed and abandoned configs. Best net alone after hundreds of trials is selection bias. No indefinite grid expansion until an attractive PnL appears.

## Harness blockers to resolve before acceptance

| Finding | Verified location | Required correction for V25 |
|---|---|---|
| Ordered parity drops Dec2025 economic rows | `research/finalize_v23_tuning.py:60`, `research/analyze_v23_backtest.py:164` | Match valid native date format across all years. Include first Dec trades in regression fixture. Reject empty ordered sequences for a traded run. |
| Cache manifest covers only May-Sep2026 | `research/finalize_v23_tuning.py:48-55` | Manifest all requested months, runtime binaries, symbol specification and source/config hashes. Reject missing months rather than silently using old manifest. |
| Boundary-only coverage can hide a missing middle month | `research/run_v23_tuning.py:78-85,227-239` | Require observed per-month/day tick coverage, native quality and tick anomaly logs for each accepted pass. Boundary tolerance needs trading-calendar explanation. |
| Production/original branch does not inspect exported first/last ticks | `research/run_v23_tuning.py:246-247` | Verify actual native period and observed dates, not requested INI alone. |
| Runner stores count of cash events but does not validate their types/value in core acceptance | `research/run_v23_tuning.py:260`; stricter check in `finalize_v23_tuning.py:69-70` | Every acceptance requires exactly supported initial deposit, no unexplained cash adjustment. |
| Optimizer frames need native XML reconciliation | `research/finalize_v23_tuning.py:19-42` | Preserve exact passID/config/trade/net/DD matching. Do not rank stale CSV frames or use native rounded PF to replace fee-aware PF. |
| Broker reference differs from deployment target | `research/run_v23_tuning.py:154-166` | MetaQuotes-Demo, leverage1:200 and 200ms are research reference assumptions. State actual demo leverage separately. XM execution profitability not established. |
| Original inherited breaker has known limitations | `AegisPredator_v24.mq5:273-299` | HistorySelect failure returns false and streak uses DEAL_PROFIT only. Preserve for signal comparison and disclose. No unrequested breaker repair. |

## Economic acceptance

`research/analyze_v23_backtest.py:44-76` already groups complete trades by position ID and sums entry/exit profit + commission + swap + fee. It rejects concurrent/add-on entries, orphan exits, side/volume mismatches, reversals/out-by and open residual positions. These limitations match the one-position EA, but must not be silently relaxed if V25 introduces a different trade topology.

For every finalist:

- Independent parser/native reconciliation: net, position count, gross and fees, final balance, forced-end exits and cash events. Distinguish position counts from deal counts.
- Monthly report including zero-trade months, direction counts, gross-before-charges average, all charges, net expectancy, net PF, win rate, native equity DD, maximum loss streak and execution rejection reasons.
- Count trades by net-after-cost sign. Unknown PnL must not be treated as zero. No-loss PF is undefined/infinite category, not a made-up large finite score.
- Full ten-month continuous replay, plus frozen validation slices. Slice resets and forced exits alter economic paths and breaker state, so do not add slice results and claim equality with continuous replay.
- Structural-capital fixed lot0.01 run and target-capital run separately. Margin-blocked days, exhausted account and broker stopout are different outcomes. Actual small account cannot inherit structural-capital total PnL predictions.
- Cost sensitivity: disclose actual native spread/commission/swap, then stress round-trip incremental costs and fixed delay. Post-hoc fee subtraction is a fixed-trade stress test, not a new spread simulation because wider spread changes signals, stops and fills.
- Regime sensitivity: classify only with features known at signal time. Do not classify an entry as trend/range using the future outcome. Disclose long/short, hour, volatility, trend/chop, monthly concentration, and worst month.
- Multiple-testing uncertainty: use session/day blocks rather than treating correlated positions as independent. A positive ten-month maximum without stability or confirmation is not proof of repeatable profit.

## Baseline parity contract

V25 mode0 must reproduce frozen V24 economic sequence under identical runtime, symbol specs/ticks, dates, deposit, leverage, delay200ms, lot0.01, magic992300, hard SL, SL1.5ATR/TP2R/min150points, maxhold60, margin guard and unchanged breaker4losses/90min. Session/fixed spread guards disabled, Fade=false, BE off. Copy all inputs, not a remembered subset.

Only explicit comment/version labels and passive status telemetry may differ during parity normalization. Do not normalize direction, entry/exit times, size, prices, stops, fill/rejection reasons or fee values. Preserve floating-point evaluation order in mode0. Prove baseline parity before accepting any V25 candidate score.

## Current independent status

V24 packaging evidence verified by local inspection. Ten-month history and V25 economic superiority NOT verified. No profitability or deployment approval granted by this review.

### Builder review received

`research/build_v25.py` and `research/v25_signal_extension.mqh` inspected. Mode0 calls the original ProposedSignal directly. Generated breaker, position management, margin check and ProposedSignal match frozen V24 function bodies. Candidate modes use completed M1/M5 features, direction aligned with closed M5 trend, no BE or lot escalation. This is structural review only. Native ordered baseline parity is still required.

Two instrumentation findings sent to orchestrator for correction:

- Mode0 records `candidateTrend=0` and generic `v24_exact_signal` even when no signal. Baseline direction/regime/rejection explanations cannot be inferred from this ledger alone. Post-execution diagnostics may explain it without changing original economic evaluation.
- `diagnosticFile` is not explicitly flushed/closed before export, unlike rawFile. Relying on automatic cleanup is weaker than an explicit export-completeness contract.

`research/v25_preflight.py` inspected. Its existing native original branch plus ten TKC files is an acquisition bootstrap, NOT observed per-month coverage validation. The script correctly discloses that file existence is not proof. Its `preflight=True` output must not become a ten-month acceptance claim.

Independent checks: `python -m unittest tests.test_v25_independent_review -v`, 9/9 passed. Tests cover frozen source, copied signal/management invariants and fee-aware accounting. They do not execute or simulate MT5. Separate new native runner review pending arrival.

### New runner first review

`research/run_v25_native.py` inspected before candidate search. Good protections: independent frozen V24 production replay, native sequence supports2025, ten-month cache manifests before/after, full36-pass grid assertions, per-pass monthly observations, XML/config/net/trade/DD reconciliation, strict initial deposit accounting, chronological development/validation selection, saved finalist lock, no reselect after final, no release/deployment.

Findings sent for correction before search:

1. **Blocking false rejection**: standalone coverage summed EA callbacks compared to native raw `Ticks`. Prior native proposed reference has 58,115,284 callbacks versus 58,118,739 native ticks. Callback sampling differs under execution delays. Reconcile coverage sum to exported `observed_ticks`, require positive callbacks <= native ticks and retain native real-tick/journal/cache evidence. Do not pretend callbacks represent every raw tick.
2. Coverage identifiers use `int(finite(...))`, silently accepting fractional pass/month IDs. Require integral IDs before conversion.
3. XML TP index accepts negative indexing in Python unless explicitly range checked. Native XML input -1 must fail, not map to TP3R.
4. Monthly positive counts and edge timestamps do not prove interior trading-day completeness. Disclose observed coverage versus gap-free data. Strict continuity requires daily/session audit.
5. Runner currently launches without lab ownership lock/process guard. `UseLocal=1` does not bound optimizer agent concurrency or memory consumption. Do not claim one agent solely because bootstrap warmed one local agent. Orchestrator must ensure isolated ownership and practical resource limits.
6. Candidate source/binary hashes currently recorded before launch, not rechecked at acceptance. Add end-of-run invariant or ensure immutable candidate files through complete batch.

Three new unit regressions added: all native2025 rows retained, exact Dec2025-Sep2026 month list, fractional monthly identifiers rejected. Execution attempt was blocked before Python startup by `MXC launcher: CreateProcessSecurityEnvironment failed (HRESULT = 0x80070020)` twice. This is environment failure, not a claim of passing or failing test logic. Latest suite contains12 tests, prior9 were verified passing.

Research artifact naming restriction acknowledged: `ResearchCandidate_R1`, property24.90, not a V25 release until profitable evidence. Internal v25 project filenames do not grant profitability or promotion.

### Corrected runner review and verified tests

Rechecked revised runner before corrected native batch:

- Callback sum now reconciles to exported `observed_ticks`; observed callbacks cannot exceed native raw ticks. Coverage explicitly reports callback metric and `interior_gap_free_proven=false`.
- `strict_int` rejects fractional/negative identifiers and constrains TP/strength indices.
- Research source/binary hashes rechecked before accepting run, plus V24/runtime/cache hashes.
- CLI uses OS byte-range lab lease, released automatically on process termination. This prevents concurrent cooperating candidate batches, not unrelated old runners. Native optimizer agent count still needs resource-aware orchestration and must not be inferred from the single warmed agent.
- Baseline trend diagnostic now computed after economic execution. Diagnostic file explicitly closed in exports and deinit.
- Artifact output `research/ResearchCandidate_R1.mq5`, version24.90. No V25 production release.
- Added mocked regression with three eligible survivors and failing final: selects one, records lock before confirmation, evaluates confirmation exactly once, never reselects, `qualified=false`, `promotion=false`.

Final pre-batch independent tests: `python -m unittest tests.test_v25_independent_review -v`, **13/13 passed**, 0.060s. Sandbox startup problem bypassed through approved local-test execution. No native tester, VM or account operated by independent verifier.

Scope of acceptance: ready for bounded native research execution, not profitable evidence. Final native artifacts remain to be audited. Monthly presence/edge checks are not daily interior continuity proof. Historical reused confirmation is not genuine unseen OOS.
