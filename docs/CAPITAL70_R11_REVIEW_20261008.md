# R11 source review — 2026-10-08

Scope: read-only review of `ResearchCandidate_R11.mq5` against the R11 signal
design and pending-state contract. No compile or native execution performed.

## Re-review after held-state fix

The prior held-at-start issue is fixed in source hash
`F19DDB56768BD1E02F05DA4FA859F3E428561CECB006FD103967EC072184D246`.
`OnTick` captures start-of-callback occupancy and passes it to
`R11PrepareFreshBar`; the exact-due decision now returns
`R11_DELAY_EXPIRE_HELD` before it can set an override. The handler consumes the
pending event and suppresses candidate generation before `OriginalOnTick`
manages positions. Thus a position closed by `ManageOpenPositions()` on the
same callback cannot revive that pending entry. Added deterministic fixture
`held_at_due_even_if_management_closes`; source contract tests also cover the
held path.

The final narrow fix also passes `heldAtStart` to the first due-state precheck
and consumes `expired_held_at_due` before `CopyRates` or indicator reads. The
strict offline auditor requires blank confirmation context and quote on this
status, plus `held_before=true`; the emitted source row satisfies that contract.

## Reviewed behavior

- Delay-off and mode 0 bypass the persistence state machine; treatment-only
  wrapping is outside the inherited immediate `CandidateSignal` logic.
- Arm requires the completed signal bar to be exactly one minute before the
  decision bar. Due time is signal-bar + 120 seconds, with the next completed
  bar required at signal-bar + 60 seconds.
- Confirmation uses closed M1 rates/EMA9 and `ClosedTrendDirection()`; missing
  history, mismatched trend/EMA side, skipped due bars, and late callbacks
  consume without fallback or re-signal.
- Pending signals suppress new candidate evaluation while waiting. Cooldown,
  margin rejection, and order rejection are consumed after the original path.
- No R10 veto or other entry/exit parameter change found in the reviewed
  R11 wrapper and execution path.

Review status: source-level compile approval granted for the exact hash above.
The compiled source differs only by renaming the `R11DecideDelay` parameter
from `candidateSide` to `freshSignalSide`, removing compiler shadowing without
changing positional behavior. Final source and binary hashes were rechecked
against the runner pins. Runner validation checks actual specs, exact raw/signal
join, pending lifecycle, terminal-status chronology, and equality of audited
confirmed fills to the verified native trade count. Focused source/adapter/
auditor tests: 75 passed.
R11 remains tester research only; native treatment acceptance still requires
the frozen controls/gates and independent review. No release/deployment
approval.

## Saved native evidence revalidation

Offline `validate_result` passed for all four accepted runs after checking the
actual accepted/started signatures, final source/binary hashes, SET/INI, USD70
deposit, 1:500 leverage, real-tick HTML, strict 19-fixture journal marker,
position/deal/cash reconciliation, and per-bar delay auditor. Independently
recomputed native parity passed for mode 0 against the accepted V24 production
reference (392 report rows) and for delay-off development against accepted R9
hold-60 control (224 report rows).

Delay-off ledgers joined all rows 1:1: mode-0 286,859 rows / 98 attempts;
immediate-control DEV 171,154 rows / 56 attempts. Delayed DEV audit:
5,818 armed, 125 confirmed fills, 5,693 expired, zero order rejects or
right-censored pending events; 125 confirmed fills match 125 verified native
positions. Expiries: 5,007 margin blocks, 650 EMA-close, 35 trend mismatch,
one skipped bar. Descriptive full: 7,798 armed, 125 confirmed fills, 7,673
expired, zero rejects/censored; fills again match 125 positions. Expiries:
6,836 margin blocks, 788 EMA-close, 46 trend mismatch, three skipped bars.

Both treatment windows yielded 125 trades, net `-$59.53`, PF `0.8555`, native
equity drawdown `90.29%`, final balance `$10.47`, and no native stopout.
Actual accounting: profit `-$59.15`, swap `-$0.38`, commission/fee `$0.00`;
the `$0.20` cost sensitivity was `-$84.53` (`-$122.03` at `$0.50`). All 125
trades occurred in December 2025; other months had no trading activity. Thus
the descriptive 10-month run does not show ten active trading months and
cannot rescue the failed DEV gate. DEV failed net/PF/N/cost gates; validation
and selection lock correctly remain null, and complete status is `FAILED`.
No V25 qualification or deployment inference.
