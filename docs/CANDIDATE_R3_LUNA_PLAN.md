# Candidate R3 conditional research plan

Date: 2026-10-07  
Role: design only. No R2 economic outcomes reviewed or used.

## Trigger and evidence boundary

Run R3 only if none of the ten R2 family/preset configs passes the frozen development screen: net > $0, native net profit factor >= 1.20, and >= 150 closed positions on `[2025-12-01, 2026-06-01)`. Keep the same native XAUUSD M1 real-tick source, execution delay, broker costs, and accounting used for the R2 comparison. If any R2 config passes, stop R3 and continue the predeclared R2 selection path.

R1 development covered six months `[2025-12-01, 2026-06-01)`. The 108 R1 configs (36 each for continuation, strength reclaim, and ten-bar breakout) had no config meet all three development gates. Best net rows per family were: continuation +$808.41, PF 1.090, 1,797 positions; reclaim +$567.39, PF 1.064, 1,728 positions; breakout +$388.91, PF 1.046, 1,762 positions. These are in-sample development screens, not confirmation. R1 used no separate untouched holdout in this evidence record.

No R2 results are used here, including results after the development window. May-September 2026 has already been seen in prior work. If no genuinely fresh confirmation data exists after candidate freeze, R3 results remain a historical development screen only. Do not call a candidate validated, promoted, or independently confirmed from reused history.

## Shared rules and economics

- Run each signal once on first tick of a new M1 bar. Use closed bars only: `s1` latest completed M1 bar; `s2...` older. M5 indicators also use shift >= 1.
- Fail closed on missing/nonfinite indicators, malformed OHLC, nonpositive ATR, irregular/gapped required bars, unavailable quote, or stale `s1` time.
- Common quote gates for every R3 family: spread <= 0.10 * closed M1 ATR14; absolute executable quote midpoint minus `s1.close` <= 0.50 * ATR14. Signal-bar range <= 2.0 ATR. Enter at next available executable bid/ask; never use the candle close as a fill price.
- BUY/SELL predicates are exact sign mirrors. No signal-specific spread threshold.
- Freeze V24 economics: 0.01 lot, SL 1.5 * M1 ATR14 subject to 150-point minimum, TP 2R, hard broker SL enabled, one position at a time, existing margin gate, four-loss/90-minute circuit breaker, 60 M1-bar time exit, BE off. No exit tuning, sizing, stacking, or family-specific management.
- Native spread is already reflected in bid/ask fills. Calculate net and PF from completed position P&L after profit, commission, swap and fee; do not subtract spread a second time. Also report mechanical extra-cost stresses of $0.20 and $0.50 per completed 0.01-lot position as accounting sensitivity, not a new spread model.

## R3 candidate families

Exactly three distinct hypotheses, two presets per family: six total configs. Preset index 0/1 changes only the one named axis in its family. All other thresholds below are fixed. Do not add combinations or nearby values after outcomes.

### R3-A: Trend blow-off rejection, fade against the mature trend

Hypothesis: an extended M5 trend that loses slope can produce a marginal new extreme followed by a failed continuation. Fade that failed push. This trades against the M5 trend; R2-E instead trades back in the M5 trend direction after a countertrend snapback, and R2-C only fades a break in a flat range.

- Define `d=+1` when closed M5 EMA20 > EMA50, EMA20 > its value five completed M5 bars ago, and separation >= 0.10 * closed M5 ATR14. Define `d=-1` with all inequalities mirrored. Let `slopeNow = d*(EMA20[1]-EMA20[2])`, `slopePrior = d*(EMA20[2]-EMA20[6])/4`. Require `slopePrior>0`, `slopeNow>0`, and `slopeNow <= 0.50*slopePrior`.
- Extension setup: signed M1 displacement `d*(s2.close-s9.close) >= x * ATR14(s2)`, where `x ∈ {1.50, 2.00}`. `s2` must make a fresh ten-bar high/low versus `s3..s12` in direction `d`.
- Trigger: `s1` extends the `s2` extreme by >= 0.05 * ATR14(s1), then closes back past the `s2` extreme against `d`. Candle body must point against `d`; favorable close location in the fade direction >= 0.70; `s1.close` must cross EMA9 against `d`. Absolute `s1.close-EMA9` <= 0.50 * ATR. Enter opposite `d` only if common quote gates pass.
- Two presets: `x=1.50` or `x=2.00`. No other variable threshold.
- False positives: trend resumes after a single pause; EMA slope contraction is short/noisy; stop run exceeds the fixed 0.05 ATR marginal extreme; low-frequency sample misses 150-position floor.

### R3-B: Internal range-band rejection, no outside sweep

Hypothesis: repeated rejection inside an established range can mean-revert before price sweeps the boundary. R2-C requires an outside sweep and close back in; R3-B explicitly forbids the sweep and fades an internal edge rejection.

- Range regime: prior 20 completed M1 bars `s2..s21` have width `H-L` between 2.0 and 6.0 * current closed M1 ATR14. Closed M5 EMA20 slope over five bars has absolute value <= 0.10 * M5 ATR14; absolute EMA20-EMA50 separation <= 0.20 * M5 ATR14.
- Set `pos=(s1.close-L)/(H-L)`. Preset edge `q ∈ {0.80, 0.85}`. SELL requires `pos >= q`, `s1.high < H` (no sweep), bearish body, upper wick >= 0.25 * full candle range, and favorable sell close location `(s1.high-s1.close)/(s1.high-s1.low) >= 0.60`. BUY requires `pos <= 1-q`, `s1.low > L`, bullish body, lower wick >= 0.25 * candle range, and favorable buy close location `(s1.close-s1.low)/(s1.high-s1.low) >= 0.60`.
- Zero-width range, zero-range signal candle, range > 2 ATR, invalid range regime, or equality/outside excursion at the boundary means no signal. Entry subject to common cost gates.
- Two presets: `q=0.80` or `q=0.85`. No tuning of range width or wick fraction.
- False positives: range is transitioning into a trend; edge rejection is weak and quote costs consume small return-to-midpoint; one side produces too few independent positions. Breaks outside the range belong to R2-C and must not be relabeled as R3-B.

### R3-C: Efficient M5 impulse, multi-bar M1 flag resumption

Hypothesis: persistent M5 directional travel plus a bounded, multi-bar M1 pullback pause has different continuation quality than R1's one-bar continuation/reclaim and R2-B's low-range coil.

- M5 efficiency ratio over 12 completed bars: `ER = abs(C1-C13) / sum(abs(Ci-C(i+1)), i=1..12)`. Denominator must be positive. M5 signed net move in `d` direction >= 1.0 * M5 ATR14. M5 EMA20/EMA50 order and five-bar EMA20 slope must agree with `d`; separation >= 0.10 * M5 ATR14.
- Two strength presets: require `ER >= e`, with `e ∈ {0.60, 0.70}`. No other regime axis.
- M1 leg/pause: displacement `d*(s5.close-s8.close) >= 1.00 * ATR14(s5)`. Both `s4` and `s3` bodies close against `d`; `s2` close also lies against `d` or is a neutral/doji bar. Pullback from `s5.close` to `s2.close` must be in direction `-d` and between 0.15 and 0.60 of the prior `s8..s5` impulse magnitude.
- Trigger: `s1` closes beyond the highest high / lowest low of pause bars `s2..s4` by >= 0.05 * ATR14(s1), resumes in direction `d`, has favorable close location >= 0.70, and closes on the `d` side of M1 EMA9. Common quote gates apply.
- False positives: M5 efficiency remains high through an impending reversal; flag retracement is actually a regime flip; trend impulse and pause ordering becomes ambiguous across gaps; high filter reduces count below 150.

## Selection, cost and stopping gates

- Test only six predeclared R3 configs on development window `[2025-12-01, 2026-06-01)`. Preserve all six outcomes and setup failures. No full-history ranking, no new preset after seeing results.
- A development-screen pass requires all three: >= 150 closed positions, native net PF >= 1.20, net after broker costs > $0. Apply same position grouping and report PF/net alongside V24 and every R1/R2 comparison under identical tester settings.
- Report monthly net, BUY/SELL net and count, native drawdown, 0.01-lot path, and $0.20/$0.50 extra-cost sensitivity. The gate uses native costed net/PF; cost stresses must be shown and must not be represented as simulated execution.
- If no config passes, stop signal expansion and record R3 as a failed historical screen. Do not lower trade/PF thresholds, retune rules, change exits, or mine the whole ten-month period.
- A pass still does not qualify a V25 for use. Freeze one config by the existing predeclared development/validation protocol; require a genuinely new forward period after freeze for independent confirmation. If no such data is available, report historical screening results only and keep V24 as the exact baseline.

## Explicitly rejected as redundant

- More one-bar continuation, EMA9 reclaim-strength or ten-bar close-break presets: R1 already covers these.
- EMA20 pullback, short compression breakout, flat-range outside-sweep reversal, ten-bar break/retest, or trend-aligned exhaustion snapback: R2 already covers these.
- Generic buy/sell inversion, long-only/short-only selection, candle-strength-only thresholds, or standalone RSI/MACD presets: no distinct causal mechanism here and large false-selection surface.

No R3 design or development result promises profit or daily income.
