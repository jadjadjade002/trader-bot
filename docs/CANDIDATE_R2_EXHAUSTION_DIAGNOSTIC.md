# R2 mode 5 exhaustion: evidence diagnostic

Scope: accepted development runs `r2_a_dev_5_0` and `r2_a_dev_5_1` only, each XAUUSD M1 from 2025-12-01 through 2026-06-01. Both signatures identify mode 5; preset 0 has `InpEntryStrength=0`, preset 1 has `InpEntryStrength=1`. Source inspected: `research/ResearchCandidate_R2.mq5`. This diagnoses observed outcomes. It does not choose a preset or propose a strategy/filter.

Mode 5 source requires M5 trend direction, a prior swing retest, countertrend displacement from closed bar 6 to bar 2 of at least 1.25 ATR (preset 0) or 1.75 ATR (preset 1), and a strong trend-direction candle reclaiming EMA9 with close near EMA9. Both retain same 2R target, initial stop distance `max(1.5 × M1 ATR, 150 points)`, and 60-bar time management. R in excursion summaries is measured against each position's actual initial stop distance. These are rule mechanics, not proof that any individual loss came from a specific condition.

## Why PF is weak

The prescribed 2R target / 1R stop produces low win frequency barely above break-even for observed average win/loss sizes. Native report figures:

| Preset | Trades | Win rate | Avg win / avg loss | Net | Gross profit / gross loss | PF |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 339 | 33.63% | $10.34 / -$5.05 | $41.97 | $1,179.01 / -$1,137.04 | 1.04 |
| 1 | 156 | 31.41% | $11.12 / -$5.02 | $7.61 | $544.65 / -$537.04 | 1.01 |

Using those rounded native averages, break-even win rate is about 32.8% for preset 0 and 31.1% for preset 1 (`avg loss / (avg win + avg loss)`). Observed rates clear those thresholds by under one percentage point. That leaves tiny aggregate edge: native gross profit minus native gross loss is $41.97 and $7.61 respectively. Native report records commission $0, fee $0 and aggregate swap -$0.13 each; charges do not explain weak PF. Per-position `DEAL_PROFIT` before separate charges sums to +$42.10 and +$7.74; commission $0 plus swap -$0.13 plus fee $0 reconciles each to net. Its positive/negative position components are +$1,179.14 / -$1,137.04 and +$544.78 / -$537.04. Native report Gross Profit/Loss fields are $1,179.01 / -$1,137.04 and $544.65 / -$537.04 respectively; retain these native fields separately from precharge deal-profit components.

Preset 0 took 339 trades; preset 1 took 156, with materially overlapping but not identical trade sets. In each, every stop-loss exit was a losing trade and every take-profit exit a winner; the few EA closes account for the remainder. The 2R payout structure cannot compensate for roughly two losses per win unless win rate rises above its break-even boundary. These reports show rates essentially at that boundary, not a robust margin.

## Side × exit evidence

Counts and net are joined by native position id from deals. PF is standard trade-level profit factor within each cell; `—` means no losing trades, hence undefined PF. Exit reason codes are MT5 meanings: 3 Expert, 4 Stop Loss, 5 Take Profit. Source uses EA `PositionClose` for the 60-bar time exit; reason 3 is therefore labeled Expert close, not asserted as an independently verified cause beyond the source and two observed rows.

| Preset | Side / exit | Count | Net | PF |
|---|---|---:|---:|---:|
| 0 | Buy / Expert close (3) | 2 | $1.81 | 1.47 |
| 0 | Buy / SL (4) | 129 | -$601.35 | 0.00 |
| 0 | Buy / TP (5) | 55 | $527.04 | — |
| 0 | Sell / SL (4) | 95 | -$531.84 | 0.00 |
| 0 | Sell / TP (5) | 58 | $646.31 | — |
| 1 | Buy / Expert close (3) | 1 | $5.66 | — |
| 1 | Buy / SL (4) | 64 | -$291.84 | 0.00 |
| 1 | Buy / TP (5) | 23 | $246.94 | — |
| 1 | Sell / SL (4) | 43 | -$245.20 | 0.00 |
| 1 | Sell / TP (5) | 25 | $292.05 | — |

Direction split is descriptive evidence only: buys had 30.11% wins and -$72.50 net versus sells 37.91% and +$114.47 for preset 0; preset 1 buys had 27.27% wins and -$39.24 versus sells 36.76% and +$46.85. This does not establish a stable conditional effect and is not a data-mined filter recommendation.

## Sampled excursions and duration

The source path schema stores `initial_risk = abs(entry - initial SL)`, plus favorable/adverse price movement computed on observed quote callbacks (Bid for buy MFE / sell MAE; Ask for sell MFE / buy MAE). Thus sampled MFE and MAE can be divided by initial risk into R units. All 339 and 156 traded position ids matched one path row.

Path event timestamps expose a fill-timing exception. Source stores `PositionInfo.Time()` only in whole seconds, then samples `SymbolInfoTick()` before and after `OriginalOnTick()`; it does not require quote timestamp to be at or after entry deal millisecond. Five preset-0 MAE samples and two preset-1 MAE samples predate entry deal timestamp; none of the MFE samples do. Earliest such sample was 200 ms before entry in both presets. These events remain at or after `PositionInfo.Time() × 1000` second-floor guard; events before that floor are rejected by the analyzer. Treat those pre-deal observations as stale/lagged quote timing, not as proven post-fill excursions. Therefore exports are not fully intraholding-time paths even though all position ids have path rows. MFE/MAE remain sampled extrema and cannot recover first-hit ordering for alternate exits.

Predeclared descriptive bins: `<0.5R`, `0.5-<1R`, `1-<2R`, `>=2R`; bins are not proposed filters.

| Preset | Excursion | n | Median R | P25–P75 R | `<0.5R` | `0.5-<1R` | `1-<2R` | `>=2R` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | Sampled MFE | 339 | 0.97 | 0.27–1.94 | 124 | 48 | 138 | 29 |
| 0 | Sampled MAE | 339 | 0.97 | 0.67–0.99 | 70 | 269 | 0 | 0 |
| 1 | Sampled MFE | 156 | 1.06 | 0.33–1.93 | 52 | 23 | 69 | 12 |
| 1 | Sampled MAE | 156 | 0.97 | 0.71–0.99 | 30 | 126 | 0 | 0 |

Native holding-time summaries: preset 0 min 6 seconds, average 11:34, max 1:20:12; preset 1 min 19 seconds, average 12:06, max 1:20:12. From deal timestamps, median duration was 8:17 for preset 0 (P25 3:35, P75 15:56), and 7:38 for preset 1 (P25 3:36, P75 15:57).

## Attribution limits

MFE/MAE are sampled extrema, not complete tick paths. Coverage metadata says observations are EA callbacks, not every raw native tick, and interior gap-free coverage is not proven. Exports do not preserve first-hit order for hypothetical alternative stop/target/trailing/time exits. Therefore no alternate exit result, missed-profit claim, or counterfactual PF can be inferred. Deal and native report totals support outcome attribution above; they do not establish why each losing setup failed or predict future performance.

Reproduce summaries with `python research/candidate_exhaustion_diagnostic.py` (optional `--preset 0` or `--preset 1`). Script reads only the two scoped run directories and checks their accepted signatures before aggregation.
