# Capital-70 next hypotheses (preregister before any follow-up)

Status: proposals only. Do not run before the current R9 hold60/hold90 capital-70 batch is reconciled and independently reviewed. No V25 qualification or deployment follows from these tests. Scope: research demo only, USD70, leverage 1:500, fixed 0.01 lot, XAUUSD M1, MetaQuotes-Demo real ticks. Protected V24 terminal/account remains out of scope.

## What current evidence says

`reports/v25_research_20261008_postupdate/r8_b_attribution.json` is explicitly `ATTRIBUTION_ONLY_NOT_RELEASE_QUALIFICATION`, post-selection historical research. Its development control (`controls.off_off_stats`) is N=1,797, net +$808.43, PF 1.0896. The three R8 entry-quality arms were worse: extension-only N=1,328/net +$381.19/PF 1.0555; ER-only N=1,435/net +$319.08/PF 1.0424; both N=645/net -$229.04/PF 0.9342. Their development net deltas versus off/off were -$427.24, -$489.35 and -$1,037.47 (`treatments.*.pair_vs_off_off`). Exact paired entries had $0 economic delta; differences came from changed unmatched entries and resulting occupancy. In the extension-only arm, 585 unmatched treatment entries netted -$427.09; this is evidence against that filter in this sample, not evidence that all continuation filters fail.

The R8 ten-month descriptive replay has no same-configuration ten-month off/off control (`full_period.same_config_full_control_available=false`) and is not a causal full-period comparison. Its baseline also reports `native_end_close_verified=false`; do not use its $130 result as a fully reconciled capital benchmark. Attribution warning states held/breaker callbacks are censored, not strategy exclusions. The event ledger reports 31,006 held events and 29,497 breaker events for the extension-only arm. Do not infer their hypothetical trade outcomes.

The current R9 hypothesis is separate: unchanged mode-1 P2/SL2ATR/TP3R continuation, hold90 versus hold60, and fixed USD70/1:500 test conditions. Its source, run order, gates and no-release scope are frozen in `docs/CAPITAL70_RESEARCH_PROTOCOL_20261008.md` and `docs/CANDIDATE_R9_PROTOCOL_20261008.md`. R1 development control evidence motivating R9 shows 247 time exits, 201 closed positive, median sampled MFE 2.002R; samples are not counterfactual fills or realized target opportunities.

R8 records realized native Bid/Ask economics, but its attribution JSON does not establish a spread-conditioned edge or causal spread threshold. Existing `InpMaxSpreadPts=25` remains unchanged in both proposals. Do not derive spread cutoffs from inspected outcomes. Likewise, do not convert exported tick-value fields into dollar risk estimates.

## Follow-up A — one-bar persistence entry timing

Question: does the inherited continuation trigger become stale between its closed-M1 signal and a usable entry quote, such that waiting one completed M1 bar for persistence improves executable outcomes enough to offset worse entry price and longer occupancy?

If R9 does not qualify and review authorizes this follow-up, compare only two arms on identical USD70/1:500 development dates: the frozen mode-1 P2/SL2ATR/TP3R/hold60 control and one delayed-entry treatment. At the original R1 signal, save side and signal-bar time; do not order. At the next completed M1 close, require the saved side still matches `ClosedTrendDirection()` and close remains above EMA9 for BUY / below EMA9 for SELL; then place once at the first eligible quote. Expire the saved signal after that single bar. No re-signal, other filter, threshold search, exit change, or multiple-delay arm. Preserve fixed lot, stops/target, spread/margin/session guards and breaker. Capture original signal quote, delayed eligible quote, actual fill, spread and rejection reason; native Bid/Ask and actual fills remain the cost evidence.

Falsify if the arm misses the frozen development floor (net>0, PF>=1.20, N>=150), or if its same-period native net/drawdown and operational outcomes do not improve over control. If it passes, use the existing validation floor (net>0, PF>=1.20, N>=40) and lock before confirmation. Report all delayed, expired, blocked and occupied events. Never label rejected/expired signals as saved losses. R9's hold90 result must be kept distinct; no mixing arms or selecting delay from confirmation outcomes.

## Follow-up B — fixed-lot planned-stop cash-risk veto

Question: can the fixed 0.01-lot continuation setup operate at USD70 without accepting a planned initial stop loss disproportionate to available equity?

If R9 does not qualify and review authorizes a separate risk experiment, compare unchanged P2/SL2ATR/TP3R/hold60 against one treatment on identical USD70/1:500 dates. Keep lot fixed at 0.01. At the actual pre-order Bid/Ask, compute the existing rounded structural SL exactly as the EA would, then call broker-native `OrderCalcProfit` for 0.01 lot from entry quote to that SL. Veto only when the returned finite account-currency loss is greater than 3% of current equity (initial USD70 equity means $2.10). Fail closed if calculation or quote is unavailable; retain the existing margin guard. Do not scale volume, loosen SL, use exported tick-value conversion, top up capital, or alter any other signal/exit rule. Log planned cash risk, equity fraction, calculation availability and veto reason for every order-eligible event.

Falsify as operationally infeasible if the veto causes fewer than 150 development positions, or the unchanged net>0/PF>=1.20 floor fails; also reject if native stopout occurs or the fixed-position $0.20 additional-cost stress is nonpositive. A pass proceeds only to the unchanged validation/lock/confirmation/full-period/cost gates from the capital-70 protocol, against its exact USD70 V24 baseline. Report blocked opportunities and margin-blocked attempts; no selection among further caps.

## Shared limits

These dates are already inspected historical data. Any pass remains retrospective, not genuinely unseen OOS. Controls must precede outcomes, and every run must use same verified runtime/cache, actual tester deposit/leverage, ordered native accounting and complete close ledger. Stop on parity, environment or accounting failure. Keep failed evidence. Do not choose between A and B by confirmation profit; run at most one follow-up after R9 review, with a fresh preregistration and explicit authorization. No V25 label or MT5 deployment authorization is implied.
