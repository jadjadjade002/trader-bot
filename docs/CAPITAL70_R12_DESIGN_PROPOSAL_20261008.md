# Capital-70 R12 design proposal

Status: design only. Not approved, preregistered, implemented, compiled, or run.
Tester research only; no V25 claim or deployment authority.

## Evidence, not a performance claim

The current continuation entry requires a directional closed M1 candle to break
the previous candle's high/low, while execution follows at current Ask/Bid. The
frozen control also rejects quotes whose midpoint is more than 0.5 closed-ATR
from the signal close (`research/ResearchControl_R1_R8.mq5:120-170`). Its initial
stop is `max(ATR multiplier, 150 points)`, rounded outward, not anchored to a
recent invalidation level (`:755-766`). This is a plausible chase/stop-distance
question, not evidence either condition caused losses.

At USD70, R9's accepted attribution records 56 hold-60 continuation positions,
net -$59.30, PF 0.7253, and 89.51% native equity drawdown; all fills occurred in
December, then margin blocked later entries (`docs/CAPITAL70_R9_ATTRIBUTION_20261008.md`).
Hold90 was worse. R10's 2.5%-equity planned-risk veto admitted only three
historical positions (+$1.05) and failed the frozen sample floor
(`docs/CAPITAL70_R10_ATTRIBUTION_20261008.md`). R11's accepted run also failed:
125 positions, net -$59.53, final balance $10.47, all positions in December
(`reports/v25_research_20261008_capital70/r11_70_a_complete.json`). These results
argue against another timing-only delay or ATR stop tweak. They do not prove a
new setup will succeed.

Older results add caution, not a recipe: R4 had no validation-qualified exit
configuration (`docs/CANDIDATE_R4_RESULTS_r4_a.md`); R6's four cells all missed
the 150-trade development floor and had no validation survivor
(`docs/CANDIDATE_R6_RESULTS_r6_b.md`); R7's two validation survivors had only
28 positions each, and its positive descriptive aggregate was below V24 and
dominated by one avoided historical quote-gap loss
(`docs/CANDIDATE_R7_RESULTS_r7_a.md`). No buy-only/sell-only selection or
historical-window claim follows.

## One symmetric hypothesis: breakout retest with structural invalidation

Question: does requiring a completed retest of the actual breakout boundary,
then placing the initial stop beyond the retest candle's invalidation extreme,
reduce chase and make fixed-minimum-lot planned risk feasible at USD70?

Treat entry plus structural stop as one coupled policy. Any outcome cannot
identify which component caused a change. Do not add a separate timing arm,
side filter, threshold sweep, or stop/target optimization.

Use fixed continuation preset P2 and its already-defined thresholds. At a fresh
M1 decision bar, let `s1` be the latest completed M1 bar and `s2` the completed
bar before it. Require contiguous one-minute bars and finite positive closed
ATR14/EMA9 data. Current closed M5 trend `d` remains inherited
`ClosedTrendDirection()`; it must be nonzero. Define breakout level `L` as
`s3.high` for BUY or `s3.low` for SELL, with `s3` the bar before `s2`.

- BUY setup at `s2`: bullish body; body/ATR >= 0.30; close location from low >=
  0.80; range <= 2 ATR; `s2.close > L + 0.10*ATR(s2)` and above closed EMA9.
- SELL is the exact sign mirror: bearish body; same body, location, and range
  limits; `s2.close < L - 0.10*ATR(s2)` and below closed EMA9.
- BUY retest at `s1`: `s1.low <= L`, `s1.close > L`, `s1.close > EMA9(s1)`,
  bullish body. SELL mirror: `s1.high >= L`, `s1.close < L`,
  `s1.close < EMA9(s1)`, bearish body.
- Current M5 trend must agree with side. Evaluate existing spread and
  midpoint-to-`s1.close` chase gates at the actual current quote. Use Ask for
  BUY and Bid for SELL. No active bar feature, prior-bar order assumption,
  delayed callback, fallback, or resignal.

Only `s1` confirmation is an entry opportunity; the older `s2` breakout is a
closed-bar setup, not a presumed executable order. Report setup, retest,
rejection, held/circuit-censored and order-attempt events separately. Never
assign counterfactual PnL to an unfilled setup.

### Stop and cash-risk contract

The retest candle defines structural invalidation. Let `tick` be the actual
positive `SYMBOL_TRADE_TICK_SIZE` and `point` the actual positive
`SYMBOL_POINT`.

- BUY structural SL: outward tick-round `s1.low - tick` downward.
- SELL structural SL: outward tick-round `s1.high + tick` upward.
- Require SL strictly on the loss side of intended Ask/Bid. Do not replace this
  level with `max(ATR distance, 150 points)`, squeeze it to a risk budget, or
  scale the fixed 0.01 lot. A wider retest structure can fail the cash veto; a
  narrow structure can fail broker-distance checks. Both are rejected.
- Require valid broker `SYMBOL_TRADE_STOPS_LEVEL` and
  `SYMBOL_TRADE_FREEZE_LEVEL`. Conservatively reject if structural stop distance
  is below `max(stops_level, freeze_level)*point`; never widen SL to make an
  order pass. Reject missing/invalid quote, symbol geometry, equity, or native
  calculation. Freeze-level applicability to initial placement must be
  verified against the tester symbol contract before implementation.
- Call `OrderCalcProfit` for fixed 0.01 lot, actual intended executable Ask/Bid,
  and this exact structural SL. Accept only finite negative calculated P/L
  whose absolute value is <= 0.025 of current account equity. At $70 equity the
  initial estimate cap is $1.75; it changes with equity. No conversion through
  tick value. R10's helper demonstrates the native calculation and
  fail-closed pattern (`research/ResearchCandidate_R10.mq5:625-684`).
- This is planned stop risk only, not a maximum realized loss. Gaps, stop
  slippage, spread changes, commission and execution failure can exceed it.
- Hold remains 60 completed M1 bars. TP remains fixed 3R of the *actual
  structural entry-to-SL distance*, rounded outward; this couples exit distance
  to risk geometry and must be disclosed. No breakeven, trailing, grid,
  martingale, top-up, or other exit change.

Keep original margin guard, four-loss/90-minute breaker, hard server-side SL,
fixed 0.01 lot, current session/spread settings, and protected V24 untouched.
Reject the candidate if 0.01 lot, symbol minimum/step, or tester margin rules
make its policy infeasible; never lower lot to manufacture a pass.

## Controls, falsification, feasibility

If root separately approves implementation, use one R12 clone of immutable
`research/ResearchControl_R1_R8.mq5` (parent source SHA256
`961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B`). Mode 0
must match same-cache USD70 V24 exactly. A mode-1 P2/SL2/TP3/hold60 structural
policy-OFF run must match its exact frozen continuation control. Controls must
precede the single treatment. Do not reuse USD10,000 / 1:200 results to stand in
for USD70 / 1:500 economics.

Before any launch: independently reconcile the failed R11 accepted ledger and
freeze one runtime, full tick-cache identity, period, capital, leverage, delay,
source/binary/settings hashes and control mapping. Protected desktop V24
account/window/process/data are out of scope. No native launch is authorized by
this proposal.

If later approved, run one treatment only on the already-inspected historical
development window. Retain existing gates without lowering floors: net > 0,
PF >= 1.20, >=150 closed positions, no stopout, and positive fixed $0.20 per
position accounting sensitivity. Report full actual native orders/deals/cash,
monthly/side/exit results, every setup/retest rejection, broker-level rejects,
cash-risk vetoes, margin blocks, time inactive, worst trade, and 500 ms / full
period costs only if frozen progression authorizes them. Failure stops selection;
descriptive replay cannot rescue failure. Dates are inspected, not unseen OOS.

## Required deterministic tests before source review

Require symmetric BUY/SELL fixtures for setup breakout, valid retest, no
retest, retest not reclaimed, EMA/trend mismatch, stale/gapped bars, missing
closed data, occupied/cooldown due callback and duplicate event. Structural
stop fixtures must prove tick rounding and side placement. Broker stop/freeze
boundary equality and one tick inside must reject without widening. Native
cash-risk fixtures must prove $1.75 equality passes at $70, one increment above
vetoes, equity changes update cap, and invalid/zero/positive/nonfinite
`OrderCalcProfit` fails closed. Verify mode0 and mode1-OFF economic functions
against parent byte-for-byte except reporting-only additions. Do not compile or
launch until independent source and adapter review pass.

## Decision boundary

This proposal is not an approval to implement or run. Root should first decide
whether sample scarcity and all-December account depletion warrant another
historical mechanism study at all. No V25 candidate qualifies from R4–R11
evidence described here. No profit outcome is promised.
