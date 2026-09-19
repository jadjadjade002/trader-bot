# V16 Tick-Path Telemetry Specification

Status: implemented and deployed read-only on V21 Research  
Trading permission: **none**

Deployment evidence, 2026-09-13:

- Source: `QuantumTitan_V16_TickPathCollector.mq5`
- Schema/collector version: `2` / `16.31`
- Binary SHA-256: `094e1c21774e72d2237417ba4d661ed7b8ade5dbc344215caaf769a126897d0d`
- Compilation: 0 errors, 0 warnings
- Focused tests: 16 passed
- Full Python suite: 158 passed
- Terminal account: `5055724796`
- Independent XAUUSD M1 chart added beside the existing ForwardCollector chart
- MT5 journal: both `QuantumTitan_ForwardCollector` and `QuantumTitan_V16_TickPathCollector` loaded successfully
- Protected terminals and accounts were not restarted or modified

## Purpose

M1 OHLC cannot determine the order in which TP, break-even activation, break-even stop, and initial SL were reached. This collector records enough tick-path information to tune V16 exit management without placing or modifying orders.

## Isolation rules

- Run only in the V21 Research terminal on demo account `5055724796`.
- Never attach to account `112334471` or `112468807`.
- No trading API, position API, order API, chart mutation, WebRequest, DLL import, or shared `FILE_COMMON` output.
- Output only under `MQL5/Files/V16TickResearch/`.
- Append-only daily files with a unique run ID.

## Observation unit

For every completed XAUUSD M1 signal bar:

1. Freeze all signal features using completed bars only.
2. Record simulated buy and sell entry prices from the first eligible tick after the bar closes.
3. Observe every subsequent bid and ask tick for 15 completed bars.
4. Flush one record only after the 15-bar horizon is complete.
5. Mark gaps, terminal disconnects, missing ticks, and rollover windows invalid rather than filling or inferring data.

## Required fields

### Identity and timing

- schema_version
- collector_version
- run_id
- symbol
- signal_bar_epoch
- signal_bar_iso
- entry_tick_time_msc
- horizon_end_time_msc
- broker_utc_offset_seconds
- session_label

### Frozen signal features

- signal_side
- signal_score
- linreg_slope_current
- linreg_slope_previous
- ema_fast
- ema_slow
- rsi
- atr_points
- signal_bar_range_points
- signal_bar_tick_volume

### Entry and spread

- entry_bid
- entry_ask
- entry_spread_points
- spread_mean_points
- spread_max_points
- spread_p95_points

### Tick-path outcome

- buy_mfe_points
- buy_mae_points
- sell_mfe_points
- sell_mae_points
- buy_mfe_time_msc
- buy_mae_time_msc
- sell_mfe_time_msc
- sell_mae_time_msc

### First-passage timestamps

Record first touch time in milliseconds for both buy and sell paths at these distances:

- Favorable: 15, 20, 30, 50, 85, 100, 130, 150, 180, 200, 220, 240 points
- Adverse: 15, 20, 30, 50, 85, 100, 130, 180, 220, 260 points

A value stays null when never touched. Use executable quote sides: bid closes buys, ask closes sells.

Schema 2 also records first return to every lock level after each break-even trigger has armed. Trigger grid: 50, 75, 85, 100, 130, and 150 points. Lock grid: 0, 10, 15, 20, and 30 points. Buy calculations use ask entry and bid exit. Sell calculations use bid entry and ask exit.

### Quality

- observed_tick_count
- completed_bar_count
- largest_tick_gap_msc
- missing_bar_count
- disconnect_seen
- rollover_seen
- label_status
- quality_flags

Allowed `label_status` values:

- `COMPLETE`
- `INVALID_GAP`
- `INVALID_DISCONNECT`
- `INVALID_ROLLOVER`
- `INCOMPLETE_HORIZON`

## No-lookahead requirements

- Signal features cannot read active bar index 0.
- Entry must occur after the signal bar close.
- Future ticks may be used only for labels, never signal features.
- Incomplete records remain memory-only and are never treated as complete after restart.
- Duplicate key is `(run_id, symbol, signal_bar_epoch, signal_side)`.

## Analysis gate

Threshold selection remains blocked until at least five normal liquid sessions are captured, with London and New York overlap represented. Fifteen sessions remain preferred for robustness.

Candidate management must be evaluated by chronological split:

- Development sessions: threshold search
- Validation sessions: one-time model selection
- Holdout sessions: final untouched decision

Report expectancy after spread, estimated commission, slippage stress, maximum drawdown, profit factor, trades per session, and parameter stability. Reject any setting that depends on one session or collapses under modest spread/slippage stress.
