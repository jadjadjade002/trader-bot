# Capital-70 R11 signal-persistence design

Status: tester-only implementation design. R11 is not V25, not release-qualified, and not a profit claim. All dates used in the research chain are historical and already inspected; results remain post-selection.

## Motivation, not directional selection

Accepted R9 development results show asymmetry, but do not identify its cause. In `reports/v25_research_20261008_capital70/runs/r9_70_a_dev_hold60/accepted.json`, hold-60 BUY results were 24 trades, 8 wins, +$20.91, PF 1.2862; SELL results were 32 trades, 6 wins, −$80.21, PF 0.4385. Both sides used fixed 0.01 lots. The arm failed overall development gates: 56 trades, −$59.30, PF 0.7253.

Hold-90 did not explain or repair SELL performance: 32 SELL trades, 5 wins, −$78.61, PF 0.4382. BUY was 26 trades, 8 wins, +$13.90, PF 1.1553. Overall it was 58 trades, −$64.71, PF 0.7180. Direction aggregates cannot separate entry staleness, market regime, signal quality, and execution effects. They do not justify disabling SELLs or choosing long-only.

R11 tests one symmetric mechanism: whether waiting for exactly one completed M1 bar of continuation persistence helps enough to offset later executable pricing and opportunity occupancy. No side filter, threshold sweep, risk cap, or exit change.

## Frozen run contract

Only these input contracts are valid:

- Exact V24 control: mode 0, P0, SL 1.5 ATR, TP 2R, hold 60, delay off.
- Immediate continuation control: mode 1, P2, SL 2 ATR, TP 3R, hold 60, delay off.
- Delayed continuation: mode 1, P2, SL 2 ATR, TP 3R, hold 60, delay on.

Shared settings remain fixed: tester only, optimization off, XAUUSD M1, fixed 0.01 lot, grid off, session and spread guards off, margin and hard-SL guards on, 150-point minimum SL, magic 992300, target account 0, breaker 4 losses / 90 minutes, 20-period Donchian, 14-period ATR, hours 11–16 and spread input 25. No R10 cash-risk veto exists in R11. SL/TP use inherited price rounding; delayed orders use ATR from the latest completed bar and unchanged SL/TP multipliers.

Run controls before treatment. Require exact mode-0 parity and same-runtime/cache immediate mode-1 control. Compare only identical windows and fixed USD 70, 1:500, MetaQuotes-Demo real-tick runs. Existing development/validation/confirmation dates are retrospective, not unseen OOS. No confirmation-based reselection.

## One-bar state machine

At fresh decision bar `B`, inherited mode-1 `CandidateSignal` runs unchanged. If it returns BUY or SELL, R11 stores side, completed signal-bar timestamp `S`, decision Bid/Ask, and ATR, then returns no trade (`delay_armed`). It arms only when `S == B − 60 seconds`; stale Friday/weekend-bar signals cannot arm.

Due bar is exactly `S + 120 seconds`. At that fresh bar, R11 reads only completed data: `CopyRates(M1, shift=1, count=1)`, closed M1 EMA9, and inherited `ClosedTrendDirection()` (closed M5/M1 inputs). Confirmation requires the just-closed M1 bar timestamp to equal `S + 60 seconds`, current closed trend to equal saved side, and its close to be above EMA9 for BUY or below EMA9 for SELL. No shift-0 candle data, retry, alternate signal, extra chase threshold, or second waiting bar.

On confirmation, R11 passes saved side through inherited execution path once. Existing held-position, breaker, history, margin, order and hard-stop behavior remains in force. The normal mode-1 path recomputes ATR-based stop/target geometry at the delayed decision quote using original multipliers and rounding. A position held at callback start on exact due bar expires pending signal before inherited position management; it cannot become an entry if management closes that position. If the due bar is skipped, data are unavailable/gapped, trend/close fails, or an inherited gate blocks the due callback, pending signal is consumed and expires. No same-callback resignal/fallback; no late fill. Pending state clears on initialization and is never restored after restart.

## Diagnostics and fixtures

Signals CSV preserves parent first 13 columns, then appends exactly:

`delay_original_bar, delay_due_bar, delay_original_side, delay_origin_bid, delay_origin_ask, delay_origin_atr, delay_status, delay_confirmation_bar, delay_confirmation_close, delay_confirmation_ema9, delay_confirmation_trend, delay_decision_bid, delay_decision_ask, delay_decision_atr`

Status values: blank (no R11 event), `armed`, `waiting`, `confirmed_order_filled`, `expired_origin_bar_gap`, `expired_skipped_bar`, `expired_history`, `expired_bar_gap`, `expired_trend_mismatch`, `expired_ema9_close`, `expired_held_at_due`, `expired_held_position`, `expired_circuit_breaker`, `expired_no_new_bar`, `expired_margin_block`, and `expired_order_rejected`. Gate column and native order result remain separate evidence. Captured quotes are diagnostics only; actual order uses inherited local Ask/Bid variables.

OnTester adds only symbol `point`, `digits`, `delay_enabled`, and fixed `delay_seconds=60` spec rows. It does not change online logic. Nineteen deterministic native fixture checks cover delay off/mode 0, arm and stale-arm rejection, before-due wait, BUY/SELL confirmation, trend/EMA failure, unavailable history, bar/due gaps, skipped/blocked due, held-at-start expiry, and duplicate/pending replacement behavior. Python tests pin immutable parent SHA, frozen inputs, no-lookahead indexing, CSV columns, fixture count, original economic functions and exact V24 execution body after removing two reporting-only quote assignments.

Expired/held/breaker callbacks are censored events, not hypothetical saved losses. Report both sides, all actual entries/exits, unmatched outcomes, occupancy, blocked/expired states, native accounting, and actual fill prices. Do not assign PnL to expired signals or infer a counterfactual benefit from them. No result from this protocol authorizes deployment.
