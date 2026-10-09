# Candidate R1 independent verification — 2026-10-07

## Scope and status

Read-only audit of `research/run_v25_native.py`, `tests/test_candidate_r1_runner.py`, `docs/V25_INDEPENDENT_REVIEW_20261007.md`, and available `r1_b` progress evidence. No VM, account, credentials, terminal launch, or native tester operation performed here.

**Status: baseline parity and continuation development optimizer evidence independently reconciled; candidate profitability not established.** The visible `r1_b_progress.json` contains a complete baseline and parity result. No finalist, confirmation, or full candidate result was inspected here. Main rerun remains necessary before a candidate conclusion.

### Continuation optimizer retry evidence

Read-only reconciliation of `.mt5-v23-tuning.local/MQL5/Files/r1_b_dev_continuation_retry1_{optimization,coverage}.csv` against `.mt5-v23-tuning.local/reports/r1_b_dev_continuation_retry1.xml` passed:

- 36 unique optimizer frames; each frame matched native XML pass ID, SL/TP/strength inputs, net, trade count, and equity DD.
- 216 coverage rows: all 36 passes × six complete months, Dec 2025 through May 2026. Every frame's `observed_ticks` equals its monthly callback sum.
- Retry journal records `optimization finished, total passes 36` and 36/36 local tasks, 0 remote, 0 cloud. Twelve local Core agents are recorded as started/authorized. Thus native completion is supported despite the runner's original check requiring the standalone-run phrase `automatic testing finished`.
- Stored `.set` files are identical after excluding `InpRunTag`; retry did not change optimizer settings.

This verifies the development optimizer evidence only. It does not prove intramonth gap-free callback coverage, candidate selection, confirmation, or profit.

### Final R1 outcome audit

`r1_b_complete.json` now contains all three accepted development grids. I independently re-ran optimizer CSV/coverage/XML checks for continuation, reclaim, and breakout: each has 36 unique frames, 216 coverage rows (36 × six months), 36/36 native XML reconciliations, and zero per-frame callback-total mismatches. Across all 108 frames, the highest development net is $808.41 in continuation at SL 2.0 ATR / TP 3R / strength 2. There are zero validation candidates; the frozen runner reports `qualified=false`, `promotion=false`, and `genuinely_unseen_oos=false`.

The runner's separate development-only descriptive replay selected that maximum for context and correctly labels it failed/unvalidated. I independently parsed its stored native report and deals: 2,490 positions, one expected $10,000 initial cash event, net $547.26, fee-aware PF 1.0457, final balance $10,547.26, native equity DD 6.16%. Its fixed extra-cost stress is +$49.26 at $0.20/position but -$697.74 at $0.50/position. This is a positive hindsight replay after selecting the maximum from the same development data; it is not candidate validation, unseen OOS, or proof of repeatable profit.

The stored frozen V24 versus mode0 parity also independently recomputes as passed for 15,072 ordered native rows including 2025. Baseline remains +$130 on 3,768 trades with net PF 1.0096. Final R1 evidence therefore supports the conclusion “no candidate passed the prescribed selection/validation screen”; no finalist confirmation/full locked evaluation occurred.

## Findings

### Blocking: `qualified` omits robustness cost gates

`run_all()` computes `qualified` from confirmation and ten-month native net/PF/trade thresholds, positive-month count, net above baseline, and equity drawdown no worse than baseline. The runner separately computes fixed extra-cost stresses of $0.20 and $0.50 per trade, and separately runs a 500 ms delay case, but neither result affects `qualified`.

This matters materially at the recorded baseline scale. `r1_b_progress.json` shows +$130.00 over 3,768 trades, fee-aware net PF 1.0096. Its fixed-cost stress is -$623.60 at $0.20/trade and -$1,754.00 at $0.50/trade. Those figures are not a changed-spread simulation, but they show that a small cost increase overwhelms the reference result. A passing runner boolean therefore cannot stand alone as proof of robust profit; any conclusion must show the 500 ms outcome and cost stress explicitly and describe the stress as post-hoc fixed-cost arithmetic.

### Data and provenance claims

- Baseline native report records 100% real ticks, 132,841,964 raw native ticks, and 286,859 bars for 2025-12-01 through 2026-10-01.
- Accepted monthly EA callback observations sum to 132,829,154, 12,810 fewer than raw ticks. The artifact explicitly calls these callbacks, reports skipped callbacks, and sets `interior_gap_free_proven=false`. This is appropriately bounded evidence; it does not prove every intramonth trading day was covered.
- Baseline parity records 15,072 ordered native rows and `includes_2025=true`; native metrics include profit, gross profit/loss, trades, ticks, bars, history quality, and equity/balance drawdown. This proves the recorded V24-vs-mode0 historical replay match, not candidate profitability.
- The review correctly marks May-Sep 2026 as previously inspected/reused. Jun-Jul validation and Aug-Sep confirmation cannot be called untouched out-of-sample evidence. The runner also hard-codes `genuinely_unseen_oos=false` and `promotion=false`.
- Runner validates frozen V24 source/binary, candidate source/binary, runtime hashes, monthly cache hashes before/after, generated input signature, optimizer grid, and XML pass/config/economics/DD. Its lease coordinates cooperating invocations of this runner; it does not establish that unrelated MT5 processes are absent or cap optimizer worker resource use.

## Acceptance recommendation

Do not present any future `qualified=true` as evidence of release readiness. Report it as the runner's historical screen only. Proposed minimum economic gate for any profit claim: positive net after the $0.20/trade fixed stress; 500 ms run positive net and net PF at least 1.1; $70 account run positive net with no stopout. These are necessary screens, not proof by themselves. Also require independently reconciled full-run economics and genuine prospective confirmation after the strategy/config freeze. Keep existing reused months labeled retrospective. Current artifacts do not provide profit proof.

### Separate release-evidence screen review

`research/candidate_release_evidence.py` keeps these economic conditions separate from frozen historical qualification and fails closed on absent/nonfinite values. It requires the $0.20 full-run stress, positive 500 ms net with PF >= 1.10, and positive $70 account net with explicit `native_stopout is False`. It also keeps `promotion=false`, `genuinely_unseen_oos=false`, and prospective confirmation `NOT_ESTABLISHED`, even if all numeric conditions pass. The accompanying screen document correctly treats the $0.50 stress as disclosure only and warns that fixed-cost arithmetic is not a changed-spread simulation.

This screen is necessary but still not sufficient for a profit claim: independent full-artifact review and actual prospective evidence remain outstanding.

## Test artifact

`tests/test_candidate_r1_luna_review.py` records the key qualification gap and baseline evidence as regression-style audit checks. It does not launch MetaTrader or test trade profitability.
