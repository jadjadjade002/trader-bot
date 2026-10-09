# Codex: signal evidence, 2026-10-06

This is a local evidence handoff, not a claim that a new model conversation occurred. The user requested signal work only and retained the existing breaker.

## Evidence checked locally

1. Native May-September comparison in `reports/v23_backtest_20261004/comparison.json`: original fade 2,987 positions / -$1,342.34; momentum 2,705 / -$1,221.67; close-back fade 1,436 / -$464.50.
2. Frozen first-quote raw snapshots contain 143,336 bars. The 15-minute all-candidate screen matches 7,881 original signals and 1,938 close-back signals. Original fade mean before quoted spread is +0.040385, quoted spread drag 0.276873, after quoted spread -0.236488. Momentum after spread -0.317258. Close-back before spread +0.112023, drag 0.274536, after spread -0.162513. These units are price changes, not account dollars. They exclude SL/TP, charges beyond spread, execution delay and position state.
3. The completed-candle reversal candidate was frozen before its run. It failed: 1,937 matched 15-minute marks, after-spread mean -0.162633, interval [-0.458411,+0.141257], one positive month out of five. All 1,961 candidate entries already existed in the 1,963-entry close-back set. Candle-direction confirmation supplies almost no additional selectivity here.
4. V21 closed-bar reconstruction matched native signal classifications on 14,749/14,749 overlapping eligible bars. First quotes matched 14,722/14,749. Signal parity does not establish exact fill parity. Entry-bar flags were removed from the entry gate because they are finalized after entry. Historical-bar quality checks remain.
5. Focused tests: 11/11 passed. Deployed V23 source SHA-256 unchanged: `C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0`.

## Interpretation and remaining hypotheses

The evidence does not support flipping every Buy/Sell or promoting the close-back/reversal conditions. At these fixed mark horizons, the slight historical directional drift does not cover quoted spread. Native strategy totals also remain negative. This does not prove every possible entry/exit combination impossible, and the markout screen does not isolate all exit interactions.

Any new candidate should contain genuinely new information available at entry, not a condition already implied by the old candidate set. Specify its mechanism and acceptance rule before screening. Spread/cost selectivity, broader trend context and regime are hypotheses until tested. Repeatedly inspected May-September data can generate candidates but cannot validate their profitability.

The old close-back hypothesis has a diagnostic forward window reserved for [2026-10-07,2026-12-02) broker time. That reservation does not require stopping new research. A changed candidate needs its own freeze before inspecting its validation outcomes. Last isolated native tester attempt lacked a demo account, so no fresh native candidate PnL exists.

Reproducible implementation and evidence: `research/audit_v23_signal_markouts.py`, `research/audit_v23_v21_forward.py`, `research/screen_v23_reversal_confirmation.py`, `docs/V23_SIGNAL_EDGE_AUDIT_20261006.md`, `docs/V23_REVERSAL_CONFIRMATION_PROTOCOL_20261006.md`.
