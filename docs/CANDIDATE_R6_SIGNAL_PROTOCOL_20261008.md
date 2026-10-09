# R6 signal research protocol

Status: preregistration only. No EA, native run, V25 qualification, or deployment authorized by this document. R1–R3 already cover 11 named entry families. R6 screens two additional event definitions; neither is supported as profitable by current evidence.

## Scope and frozen controls

- Exactly four cells: `R6-F0`, `R6-F1` (reclaim-failure fade) and `R6-V0`, `R6-V1` (volatility-release breakout). No added presets or thresholds after outcomes.
- Use XAUUSD M1, MetaQuotes-Demo real ticks, 200 ms delay, $10,000 structural deposit, 1:200 leverage, 0.01 lot. One position at a time; native costs; hard SL, margin guard, four-loss/90-minute circuit breaker remain enabled.
- Freeze exits for all cells: SL 1.5 × closed M1 ATR(14), minimum 150 points; TP 2R; 60 completed M1 bars maximum hold; BE off. No sizing, stacking, inversion, grid, or exit tuning.
- Keep V24 exact-signal parity control. Apply existing quote gates: spread <= 0.10 × ATR(14), quote midpoint within 0.50 × ATR(14) of signal close; signal range <= 2.0 × ATR(14). Use executable Bid/Ask. Do not subtract spread twice.
- Signal features use completed bars only. Reject nonfinite/invalid data, missing bars, zero ranges, stale bars, Bid > Ask, or any required M1 time gap. Do not use post-entry MFE/MAE or future outcomes in predicates.
- Development window `[2025-12-01, 2026-06-01)`; validation `[2026-06-01, 2026-08-01)`; confirmation `[2026-08-01, 2026-10-01)`. These historical periods have been inspected before; none is unseen OOS. Genuine prospective confirmation starts only after source/settings/selection lock and the next broker session.

### Runtime recovery amendment, 2026-10-08

MT5 automatically updated the isolated runtime from build6241 to build6246 while launching an R5 production control. Its old-signature attempt remains unaccepted. Before any R6 native outcome, declare `reports/v25_research_20261008_postupdate/` with prefix `r6_b`. Reuse only the exact-signature-validated R5 mode0 control from this selected root with the confirmed local demo connection. R6 must reproduce its native economics and accepted runtime/cache provenance. All four cells, all-development-survivor selection, thresholds and costs remain frozen. Check every candidate's month cache identity against the full-period baseline before eligibility. Do not resolve manifest-supplied arbitrary paths or silently overwrite the old evidence root.

## Common indexing

For a signal evaluated at a new M1 bar, `s1` is latest completed bar (shift 1), `s2` shift 2, and so on. Indicator shifts follow the same convention. Use M5 values at shift >= 1. Arrays must be chronological by shift and contiguous at 60 seconds. Direction `d=+1` means BUY / up; `d=-1` means SELL / down. Every inequality has an exact sign-mirrored counterpart; equality does not pass a strict inequality.

## F family: second-leg failure after exhaustion reclaim

Hypothesis: an R2-style exhaustion reclaim can fail immediately. A completed follow-through failure may distinguish a failed reversal attempt from R2's original entry. This tests a new event sequence; it is not evidence that fading M5 direction has positive expectancy. Signal side is always `-d`, explicitly counter to the M5 exhaustion direction.

1. Determine `d` from closed M5 EMA20/EMA50, EMA20 slope over five completed M5 bars, and separation >= 0.10 × M5 ATR(14), exactly as `ReadR2Context` in `research/ResearchCandidate_R2.mq5`. For the historical `s2` event check, use only M5 bars completed at or before `s2` close; require that context's direction also equals `d`. At current `s1`, require closed M5 direction still equals `d`. Do not require M1 alignment; do not override `d` with M1.
2. Require `s2` to satisfy the canonical R2 exhaustion signal predicate in direction `d`, evaluated with exact inherited `R2Exhaustion` indexing as if `s2` were `r[0]`. In current indexing, displacement is `s3.close - s8.close <= -1.25*ATR14(s2)` for `d=+1`, or `s3.close - s8.close >= 1.25*ATR14(s2)` for `d=-1`. Either `s3` or `s4` must test the prior extreme: minimum low for `d=+1` or maximum high for `d=-1` across `s5..s14`. Reclaim requires `s3.close <= EMA9(s3)` and `s2.close > EMA9(s2)` for `d=+1`; mirror both inequalities for `d=-1`. `s2` must be a direction-`d` candle with range <= 2 ATR, close location >= 0.70, and close within 0.25 ATR of EMA9(s2). This historical event is a signal-predicate match, not an assertion that an R2 order was tradable: no historical quote or `R2CostGate` is applied. Require contiguous bars for all lookbacks. This corrected indexing specification was fixed before any R6 outcome exists.
3. Failure bar is `s1`. For `d=+1`, require `s1.high <= s2.high`, `s1.close < (s2.high+s2.low)/2 - b*ATR(s1)`, bearish body, and `s1.close < EMA9(s1)`. Enter SELL. For `d=-1`, require `s1.low >= s2.low`, `s1.close > (s2.high+s2.low)/2 + b*ATR(s1)`, bullish body, and `s1.close > EMA9(s1)`. Enter BUY.
4. Coupled preset is the only variant: `F0: b=0.00`; `F1: b=0.10`. All other thresholds are fixed. `s1` must satisfy common signal-range and quote gates.

F requires the inherited R2 23-bar contiguous M1 window and two closed ATR14 values, shifts 1 and 2. This covers the reclaim's ATR prior-close input through shift 16. Do not apply V's 80-bar/66-ATR median lookback to F. This implementation correction was fixed before any R6 outcome exists, not after a signal-count or PnL result. Both families still use the six-bar contiguous completed M5 context.

Falsify if either cell fails the frozen development gate, if it mostly duplicates R2/R3 event entries without better qualified economics, or if validation does not pass. Count every opened position and changed occupancy; do not claim avoided R2 losses as profit without replay.

## V family: five-bar volatility contraction then 20-bar release

Hypothesis: a measured multi-bar volatility contraction followed by a boundary close may identify expansion continuation, unlike R2 compression's three-bar range contraction. It still overlaps R1 breakout; event deduplication is mandatory.

1. Define `M = median(ATR14 shifts 7..66)`; this is 60 completed M1 ATR observations strictly before the five-bar contraction and excludes active `s0`, signal `s1`, and contraction bars 2..6. Require positive finite ATR values and all required M1 history contiguous. Require each of shifts 2..6 to have ATR14 <= `q*M`.
2. At `s1`, calculate 20-bar channel from highs/lows of shifts 2..21, excluding signal bar. Require closed M5 direction `d` using only EMA20/EMA50 order, EMA20(shift1) versus EMA20(shift6), and separation >= 0.10 × closed M5 ATR(14), same thresholds as R2. No M1 trend-alignment condition.
3. BUY: `s1.close > channelHigh + 0.10*ATR14(s1)`, bullish body, and close location >=0.70. SELL mirror: close below channelLow minus the same buffer, bearish body, close location >=0.70. Require `s1` range <=2 ATR and common quote gates.
4. Coupled preset: `V0: q=0.60`; `V1: q=0.65`. Only q varies. Need M1 rates sufficient to calculate ATR14 through shift 66, including its prior-close input at shift 80; reject any gap across shifts 1..80. No partial-history fallback.

Falsify if either cell fails the frozen development gate, if signals are predominantly duplicates of R1 breakout/R2 compression events, or if validation fails. Report excluded and duplicate events, missed entries, unmatched trades, and all occupancy changes.

## Event identity, accounting, and gates

- Before native results are examined, define canonical signal event key: broker signal-bar timestamp in milliseconds + side + signal close + family. Also report cross-family duplicates on timestamp + side, independent of close. Dedupe novel R6 signals against R1 modes 1–3, R2 modes 1–5, and R3 modes 1–3. Duplicate share is diagnostic; never silently remove events from a native strategy run. No result-based threshold changes.
- Development pass per cell: net > $0, native net PF >= 1.20, and >=150 closed positions. Validation pass: net > $0, PF >=1.20, >=40 positions. Preserve all four outcomes; no pooling counts across cells. If none passes, stop this family batch.
- Send every development-passing cell to validation (up to all four); do not apply a global top-three cap. Keep stable mode/preset order for execution. If no development cell passes, stop.
- For a validation-qualified cell only, lock one by validation DD, then net, then stable cell ID before confirmation. Confirmation must pass net > $0, PF >=1.10, >=40 positions. Do not reselect after failed confirmation.
- Whole ten-month gate: net > $0, PF >=1.15, >=150 positions, at least 7/10 positive months, native equity DD <= V24, and net > V24. Apply only to the locked cell and require all other preregistered confirmation/release checks; no reselection.
- Report baseline parity, native count/net/PF/equity DD, monthly/side/exit tables, actual paired and unmatched entries, duplicate rate, changed gates, and worst trade. Include fixed-trade $0.20/$0.50 per-position accounting stresses; separately require positive native result and PF >=1.10 at 500 ms, positive $70 native run with no stopout, and positive net under $0.20 stress before any release review.
- Historical evidence is contaminated by prior inspection. Any future confirmation is unseen only after immutable source/binary/settings/selection lock. No qualifying result means no V25 and no VM replacement.

## Deferred R5 closure policy

R5 closure-policy C1 remains `UNRUN_SCHEDULE_UNVERIFIED` until broker clock semantics and historical session applicability are evidenced. Current weekday session metadata cannot establish the historical schedule by itself. Do not hardcode the known gap time or substitute zero-profit outcomes.

## Evidence basis and limits

R1 accepted development summaries show all 108 optimizer cells below PF 1.20; their optimizer rows lack per-trade context. R2 has no side-by-exit attribution. R3's descriptive 10-month high-PF cell has four positions and does not establish an edge. R4's 156-entry matched TP1/TP2 comparison is informative about realized exit outcomes for that sample only; its TP1 ten-month replay is negative. These facts motivate careful signal studies but do not establish either R6 hypothesis. References: `docs/CANDIDATE_WINNER_ANALYSIS_20261008.md`, `docs/CANDIDATE_R5_EXPERIMENT_PLAN_20261008.md`, `research/ResearchCandidate_R2.mq5`.
