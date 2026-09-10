# QuantumTitan V16 Bot Architecture

**English** | [ภาษาไทย](V16_BOT_ARCHITECTURE_TH.md)

This document explains how the V16 bot is structured and how the currently running VM instance behaves.

## Running Instance

Live observed account:

- Account: `112334471`
- Symbol: `XAUUSD`
- Visible active chart: `XAUUSD,M5`
- Confirmed active EAs from the VM expert log:
  - `QuantumTitan_v16_Velocity` on `XAUUSD,M1`
  - `QuantumTitan_v16_Apex` on `XAUUSD,M5`

The most important practical point is this:

`Velocity M1` is the fast order-entry engine. `Apex M5` is the slower framework and manager around the broader market context.

## High-Level Flow

```text
Market ticks
  |
  +-- Velocity M1
  |     |
  |     +-- Read EMA14, EMA50, Bollinger Bands, ATR, RSI
  |     +-- Check spread
  |     +-- Check no active Velocity position
  |     +-- Check post-exit cooldown
  |     +-- Wait for a new completed M1 bar
  |     +-- Evaluate scalp setup
  |     +-- Open BUY or SELL 0.01 lot
  |     +-- Move SL to breakeven when profit reaches trigger
  |
  +-- Apex M5
        |
        +-- Read ATR and market context
        +-- Run AlphaScoring
        +-- Update TrailingSafety
        +-- Run DynamicGrid basket management
        +-- Render HUD
        +-- Open Alpha entries only when its own signal passes
```

## Main Components

## 1. Velocity M1

File:

- `QuantumTitan_v16_Velocity.mq5`

Role:

- Fast scalp execution.
- This is the component currently responsible for most observed order activity.

Core inputs:

- Magic number: `991602`
- Base lot: `0.01`
- Max spread: `60 points`
- Take profit: `180 points`
- Stop loss: `260 points`
- Breakeven trigger: `85 points`
- Breakeven lock: `15 points`
- Cooldown: `1` M1 bar after exit

Entry logic:

- Trades only when there is no active Velocity position for the same symbol and magic number.
- Requires spread to be below `InpMaxSpreadPoints`.
- Evaluates only once per new M1 bar.
- Uses the just-completed M1 candle, not the still-forming candle.

BUY setup:

- EMA14 above EMA50.
- Completed candle closes above EMA50.
- Candle pulls back near EMA14.
- Lower wick rejection or bullish close.
- Squeeze momentum is not strongly bearish.
- RSI is in the allowed momentum range.

SELL setup:

- EMA14 below EMA50.
- Completed candle closes below EMA50.
- Candle pulls back near EMA14.
- Upper wick rejection or bearish close.
- Squeeze momentum is not strongly bullish.
- RSI is in the allowed momentum range.

Position management:

- If BUY reaches the breakeven trigger, SL moves to entry plus lock buffer.
- If SELL reaches the breakeven trigger, SL moves to entry minus lock buffer.
- It checks `PositionSelectByTicket()` before modifying a position.
- It starts cooldown when a deal close is detected.

Practical behavior:

- Wins tend to be small and fast.
- Breakeven lock is what turns many risky scalps into small wins or protected exits.
- Spread matters a lot because the target is only `180 points`.

## 2. Apex M5

File:

- `QuantumTitan_v16_Apex.mq5`

Role:

- Multi-timeframe framework.
- On the current VM, the latest active profile seen in logs is `M5 FAST INTRADAY`.

Observed current profile:

- Timeframe: `M5`
- Magic number: `991605`
- Higher timeframe reference: `H1`
- Min buffer: `450 points`
- SL multiplier: `1.40`
- TP ratio: `1.25R`
- Grid step: `1.20 ATR`
- Max grid orders: `4`
- Min margin reserve: `60%`

Apex modules:

- `AlphaScoring.mqh`
- `TrailingSafety.mqh`
- `DynamicGrid.mqh`
- `TelemetryHUD.mqh`

Main tick flow:

- Confirm terminal and EA trading permissions.
- Confirm symbol trading is enabled.
- Read ATR from the chart timeframe.
- Refresh bid/ask.
- Update trailing and breakeven management.
- Check basket close logic.
- Evaluate AlphaScoring.
- Render HUD once per second.
- Manage grid layer placement if a basket exists.
- Evaluate a new Alpha entry only once per new chart bar.

## 3. AlphaScoring

File:

- `Include/QuantumTitan/AlphaScoring.mqh`

Role:

- Produces directional signal quality.
- Apex uses it to decide whether a BUY or SELL entry is allowed.

Conceptual factors:

- Higher timeframe direction.
- Discount or premium zone.
- Fair value gap or imbalance.
- Liquidity sweep behavior.
- Order block context.
- Displacement.
- RSI exhaustion.
- Squeeze momentum.
- EMA structure.
- Volume expansion.
- Killzone/session filter.

For the M5 Apex profile, the score threshold observed is `75`.

## 4. TrailingSafety

File:

- `Include/QuantumTitan/TrailingSafety.mqh`

Role:

- Protect open Apex positions.
- Move stop loss to breakeven.
- Trail stop after sufficient favorable movement.

Observed Apex M5 settings:

- Breakeven around `0.3R`
- Trail around `0.8R`
- ATR trail multiplier: `0.45`

## 5. DynamicGrid

File:

- `Include/QuantumTitan/DynamicGrid.mqh`

Role:

- Manage basket/grid behavior for Apex positions.
- Add grid layers only when spacing and margin conditions allow.

Observed Apex M5 settings:

- Max orders: `4`
- Grid step: `1.20 ATR`
- Min margin reserve: `60%`
- Base lot remains `0.01`

Risk note:

Grid can help average entries, but it also increases exposure. For a small account, this is one of the main things to monitor.

## 6. TelemetryHUD

File:

- `Include/QuantumTitan/TelemetryHUD.mqh`

Role:

- Draw runtime information on the MT5 chart.
- Shows market regime, scores, basket status, margin, bias, and session context.

It does not create the trading edge. It is a visibility layer.

## Magic Numbers

The design uses separated magic numbers so EAs can identify only their own positions.

| Component | Timeframe | Magic |
|---|---:|---:|
| Apex M1 | M1 | `991601` |
| Velocity M1 | M1 | `991602` |
| Apex M5 | M5 | `991605` |
| Apex M15 | M15 | `991615` |
| Apex H1 | H1 | `1007985` |

The current VM log confirms active Velocity M1 and Apex M5 activity.

## Why It Made Profit In The Latest Run

The recent positive result appears to come from this pattern:

- Velocity finds short M1 momentum bursts.
- It opens 0.01 lot scalps quickly.
- It moves SL to breakeven after a small favorable move.
- Several positions close before momentum fades.
- Apex M5 stays active as the broader manager and visual/control framework.

The result is good when XAUUSD gives clean short bursts. It is vulnerable when spread widens, price whipsaws, or execution slips.

## Main Real-Use Risks

## Spread Risk

Velocity TP is short:

- TP: `180 points`
- SL: `260 points`

If broker spread widens, the expected value can flip quickly. This is especially important on XM real accounts.

Recommended XM controls before any real-money use:

- Hard MaxSpread gate.
- Rollover block around server day change.
- High-impact USD news block.
- Spread distribution logging on the actual account type.

## Whipsaw Risk

Velocity can enter after a short momentum burst that immediately reverses.

This is the exact risk V21 Research is trying to measure with the forward collector and whipsaw gate.

## Grid Exposure Risk

Apex M5 has DynamicGrid active with up to `4` orders. Lot size is fixed small, but exposure can still stack.

## Demo Versus Real Execution

The currently observed account is demo. Real execution can differ because of:

- Spread.
- Slippage.
- Requotes or fill mode behavior.
- Stop execution during fast movement.
- Rollover liquidity.

## Operational Rule

Current recommendation:

- Do not modify the live V16 instance while it is profitable and stable.
- Monitor V16 separately.
- Keep V21 as collector-only.
- Keep V21.67 rejected.
- Treat V22 as offline research until explicitly authorized.

