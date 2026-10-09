# V25 fixed candidate design

Research-only harness. Native Tester required. No VM or deployment operation.
Baseline source `AegisPredator_v24.mq5` SHA256:
`5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E`.

## Evidence versus hypotheses

Evidence from source: V24 already trades with completed M5 trend direction.
`InpFadeBreakouts=false`. Example "M1 rising, sells only" is not proven V24
behavior. A short M1 upswing inside a completed bearish M5 trend can still
receive sell signals. Native deal/bar diagnostics required before attributing
losses to direction. V24 five-month historical result remains negative.

Hypotheses below are fixed candidate rules, not established profitable edges.
Mode zero native parity with production V24 must pass before comparative search.

## Frozen entry rules

| Mode | Rule |
| --- | --- |
| 0 | Original V24 `ProposedSignal` copied unchanged. Strength ignored. |
| 1 | Continuation. Completed M1 candle closes beyond prior completed candle high/low and EMA9 in M5 trend direction. |
| 2 | Pullback reclaim. Completed M1 low/high touches EMA9 and closes back beyond EMA9 in M5 trend direction. |
| 3 | Breakout. Completed M1 close beyond high/low of prior ten completed M1 bars, excluding signal bar, aligned with M5 trend and EMA9. |

Modes1–3 use exact V24 shared trend constraints: closed M5 EMA20/EMA50,
EMA20 slope versus five completed M5 bars earlier, separation>=0.1 closed M5ATR,
closed M1 EMA9/EMA20 alignment. No current M5 feature or active M1 candle used.
Shared quote constraints remain spread<=0.1 closed M1ATR and midpoint chase
<=0.5ATR from signal close. Bid/ask executable side preserved in original trade
core. These inputs are available before entry, unlike future returns.

Strength `InpEntryStrength` is ordinal index, not free-form discovery:

| Index | Minimum body/M1ATR | Favorable close location | Entry buffer/M1ATR |
| --- | --- | --- | --- |
| 0 | 0.10 | 0.60 | 0.00 |
| 1 | 0.20 | 0.70 | 0.05 |
| 2 | 0.30 | 0.80 | 0.10 |

Buy close location=(close-low)/(high-low). Sell=(high-close)/(high-low).
Directional body required. Signal range must be positive and <=2ATR.
Continuation/breakout buffer applies to prior high/low. Reclaim buffer applies
to EMA9. All candidate entries retain the M5 trend sign, never invert it.

## Risk controls and search interface

Existing `InpStopLossATRMul`, `InpTakeProfitRRMul`, `InpMaxHoldBars` remain
economic controls. `InpUseGridIndices=true` maps `InpTPGridIndex`0..3 to
TP{1,1.5,2,3}R. SL search{1,1.5,2}ATR, strength{0,1,2}, hold60 unchanged.
36 configurations per candidate. Mode0 fixed SL1.5ATR/TP2R/hold60 baseline.

No BE control or stop-modification code. Breaker and existing position/margin
management functions preserved verbatim after newline normalization. Existing
breaker failure behavior is intentionally not fixed in this experiment.
Builder accepts safety bounds SL0.5..3ATR, TP0.5..4R, hold15..120 solely to
fail-close unreasonable runner inputs, not authorize grid expansion.

## Export interface

Native optimizer frames `v25_native_grid` contain19 doubles, preserving V23
metric order plus `entry_strength`. One additional `v25_month_coverage` frame
per month contains YYYYMM, observed callback ticks, first/last tick epoch-ms.

`<tag>_optimization.csv`: old19 columns plus final `entry_strength`.
`be_r=0`, `be_lock_r=0.05`, BE attempts/rejected=0 are compatibility metadata.
No actual BE behavior. Net is position-grouped profit+commission+swap+fee,
restricted to expert magic/symbol. Native total profit exported separately.

`<tag>_coverage.csv`: pass,month,ticks,first_tick_msc,last_tick_msc.
Standalone pass=0. Supports ten-month coverage cross-checking.
Counts alone cannot establish real-tick authenticity. Native report and journal
must establish100%real ticks, full coverage and no synthetic/replaced ticks.

Standalone exports reuse hash-frozen deals/equity/spec/path formats. `_raw.csv`
retains legacy schema for runner compatibility, but `original` now means actual
candidate signal. `closeback`, `dc_low`, `dc_high` are zero legacy placeholders,
not valid V23 Donchian diagnostics. `_signals.csv` provides explicit candidate
mode, strength, trend, reason, body/ATR, close location, entry level, execution
gate and attempted order. Blocked bars are marked not evaluated, not fake
counterfactual rejected opportunities. This harness does not measure skipped
signal profitability. Path MFE/MAE are callback samples, not exact tick extrema.

## Validation boundaries

Python tests validate generation/guards/schema/static rule wiring. They do not
execute MQL5 or prove economic parity. Native compile, mode0 ordered deal/order
parity, ten-month ticks and chronological development/validation/holdout results
must be recorded separately by orchestrator. No profitable result assumed.
