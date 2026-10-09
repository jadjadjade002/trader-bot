# V24-based research: 140 configurations, no qualified V25

2026-10-07. Local native MT5 research only. Production VM, V21 collector, accounts and Git history unchanged by this research round.

## Outcome

Eleven distinct entry-rule families, not 140 independent strategies: R1 has three families × 36 exit/entry presets, R2 five families × two presets, R3 three families × two presets. R4 reuses the exact R2 exhaustion family across 16 exit settings. Total: 108 + 10 + 6 + 16 = 140 development configurations. Luna agents performed implementation/attribution and independent verification. Orchestrator owned native execution, reviewed their work and closed the discovered validator and diagnostic-parser gaps.

| Round | Development configs | Development qualifiers | Validation qualifiers | Status |
| --- | ---: | ---: | ---: | --- |
| R1 | 108 | 0 | 0 | PF below frozen threshold |
| R2 | 10 | 0 | 0 | Weak PF or too few positions |
| R3 | 6 | 0 | 0 | Only 1–33 development positions per row |
| R4 | 16 | 2 | 0 | Both positive validations have 28 positions, below 40 |

Development net>0/PF>=1.20/N>=150; validation net>0/PF>=1.20/N>=40. These are screening floors, not guarantees or a formal power calculation. Do not lower them after viewing results. May–September history was reused, so no historical slice here is genuinely unseen OOS.

## Ten-month context

Each candidate below was selected by development results alone and rejected by the qualification path. These are diagnostic replays, not a full-sample winner competition. Dates: 2025-12-01 through 2026-10-01 exclusive, broker clock. Structural deposit $10,000, fixed 0.01 lot, 1:200, native real ticks, 200ms execution delay. Not a forecast for $70 or XM.

| Artifact | Positions | Net USD | Net PF | Equity DD % | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Frozen V24 | 3,768 | 130.00 | 1.0096 | 5.71 | Thin baseline, extra $0.20/position turns net negative |
| R1 continuation | 2,490 | 547.26 | 1.0457 | 6.16 | Positive but unqualified and worse DD than V24 |
| R2 deeper pullback | 2,434 | 185.09 | 1.0215 | 5.49 | Thin expectancy, unqualified |
| R3 efficient flag | 4 | 24.85 | 6.1237 | 0.06 | High PF with only four positions, inadequate evidence/activity |
| R4 exhaustion / TP1R | 202 | -2.68 | 0.9955 | 1.64 | 52.48% wins, seven positive months, full-period net negative |

The R4 development maximum uses preset1, SL1.5ATR, TP1R, hold60 completed M1 bars, BE off. Development +$98.82/PF1.2759/156 positions; June–July +$36.02/PF1.7633/28 positions. The other development qualifier TP0.75R gives +$77.27/PF1.2524/156; validation +$21.26/PF1.4834/28. Neither became a locked finalist. No confirmation, $70 replay or 500ms qualification run was launched. Rejected descriptive R4 extra-cost stress: -$43.08 at $0.20 and -$103.68 at $0.50 per position. Accounting stress is not a changed-spread simulation.

## Main failure evidence

1. Most tested entries have weak or unstable net expectancy, not a verified inverted BUY/SELL bug. V24 already follows closed M5 trend and closed M1 reclaim. Mode0 native parity is exact, including 15,072 ordered report rows from both 2025 and 2026.
2. More selective R3 entries hardly trade. A large PF does not establish superiority when based on three/four trades.
3. Shortening TP improved R4 development and validation samples but did not protect the full-period result. September net is -$150.17; the worst native position accounts for -$141.69.
4. That position sold at 4327.48 on 2026-09-01 22:53:00.238, initial SL4331.60, planned distance4.12. Native SL exit filled at4469.17 on 2026-09-02 01:00:00.037. Overshoot beyond SL is137.57, about34.4 times planned price risk in total loss. Last pre-gap sampled quote was Bid4324.39/Ask4324.78; the next sampled quote was Bid4320.26/Ask4469.17, spread148.91. The Bid fell rather than rising through the short's stop; the extreme Ask equals its actual closing price. A hard SL is a trigger, not evidence that this simulated fill was capped at the requested price. No separate execution slippage beyond that observed Ask or false-feed cause is established. Do not delete the trade or label it a proven bad feed without independent quote evidence.
5. Hold60 counts M1 bars via `iBarShift`, not 60 elapsed minutes. A market pause need not create M1 bars; wall-clock expiry alone cannot execute a close when no quote is available. Investigate closure carry risk separately from entry direction.
6. Historical log text includes legacy V23 names and a hard-coded `2.0R` label even when actual input TPR=1.00. Native inputs, order prices and artifact hashes establish actual behavior. Repair such diagnostic labels in a future artifact, not in frozen accepted source.

## Next bounded hypothesis

First reconcile the oversized fill against adjacent quote/bar exports and session metadata. Then preregister a separate closure-risk experiment: use broker session-end metadata to block fresh entries and flatten held positions before the known close, with a fixed lead interval defined before new runs. Do not select an hour by removing the September loser. Current session metadata is not proof of historical schedules; that limit must remain explicit. Maintain signal, lot, ATR, TP/SL and breaker unchanged in the paired control. Execute native replay, including all losses and new occupancy paths. An unchanged-source sample with one loss subtracted is not a valid strategy backtest.

An entry-only spread check cannot protect an already open position when the broker triggers its stop before the EA's next callback. The prospective experiment must address carrying exposure into the pause, not just rejecting the reopening quote. Native probe daily endpoints corroborate observed 22:59:59.994 to01:00:00.037 absence across this boundary; that remains evidence about these exports, not a verified historical schedule or independent market-feed truth. See `docs/CANDIDATE_R4_GAP_DIAGNOSTIC.md`.

Even a positive new replay requires the original sample/robustness gates and prospective frozen evidence before a release claim. No release named V25, no VM replacement.

## Verification and limits

- R4 compile: 0 errors, 0 warnings. Source SHA256 `AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320`; EX5 `1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9`.
- R4 native fixtures: 25 checks per initialization. All 16 development records and both validations independently reconciled. Both fixed-exit R4 controls match corresponding R2 ordered reports and exported deal/diagnostic hashes.
- Native real-tick reports, monthly edges and cache/runtime hashes verified. Callback telemetry is not every raw tick; interior gap-free history is not independently proven.
- Candidate-focused Python tests: 73 passed. Additional V24/V25 current-source subset: 42 passed. Static and mocked tests do not prove profitability.
- Global legacy suite remains red: recorded 313-test run had 38 failures and 7 errors. Missing/archived root-level EA paths explain a verified cluster, not every failure. See regression scope report. Do not claim the entire repository passes.
- Sampled MFE/MAE is not a counterfactual alternate-exit engine. Some MAE quote timestamps precede entry deal time by 200ms; disclosed in the diagnostic. Exact native deal accounting remains authoritative.

## Evidence files

- `docs/CANDIDATE_R1_RESULTS_r1_b.md`
- `docs/CANDIDATE_R2_RESULTS_r2_a.md`
- `docs/CANDIDATE_R3_RESULTS_r3_a.md`
- `docs/CANDIDATE_R4_RESULTS_r4_a.md`
- `docs/CANDIDATE_R4_LUNA_VERIFICATION.md`
- `docs/CANDIDATE_R2_EXHAUSTION_DIAGNOSTIC.md`
- `docs/CANDIDATE_R4_GAP_DIAGNOSTIC.md`
- `docs/CANDIDATE_REGRESSION_SCOPE_20261007.md`
- `reports/v25_research_20261007/r4_a_complete.json` and retained native run folders.
