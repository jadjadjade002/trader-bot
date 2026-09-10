# V16 Live Status - 2026-09-10

Status: live demo account `112334471`, observed on VM via read-only inspection.

## Current Setup

- Terminal: MetaTrader 5 portable instance on VM
- Account: `112334471`
- Active chart window: `XAUUSD,M5`
- Main execution symbol: `XAUUSD`
- Confirmed active EAs from expert log:
  - `QuantumTitan_v16_Velocity` on `XAUUSD,M1`
  - `QuantumTitan_v16_Apex` on `XAUUSD,M5`

## Live Behavior Observed

`QuantumTitan_v16_Velocity` is the main order-entry engine.

- Mode: M1 scalp
- Lot size observed: `0.01`
- Sides observed: BUY and SELL
- Typical initial stop: about `260 points`
- Typical initial target: about `180 points`
- Breakeven lock observed after about `85-157 points` of favorable movement
- Cooldown messages observed after closed deals

Latest parsed Velocity open from the copied expert log:

- Time: `01:19:26.363`
- Side: `BUY`
- Entry: `4415.06`
- SL: `4412.46`
- TP: `4416.86`
- Lot: `0.01`

`QuantumTitan_v16_Apex` is active as the M5 framework/manager.

- Latest profile: `M5 FAST INTRADAY`
- Magic number: `991605`
- HTF trend reference: `PERIOD_H1`
- Modules active:
  - Alpha Scoring
  - TTP and Safety
  - Geometric Grid
  - Matrix HUD
- Grid setting observed: Max Orders `4`, Grid Step `1.20 ATR`, Cash Buffer `60.0%`

## Parsed Log Snapshot

The live MQL5 expert log snapshot for `2026-09-10` produced:

- Velocity opens: `13`
- Velocity closes/cooldown notices: `14`
- Velocity breakeven locks: `12`
- Velocity BUY opens: `10`
- Velocity SELL opens: `3`
- Explicit Apex closed PnL events parsed: `2`
- Explicit Apex parsed closed PnL: `+$5.15`

Important: Velocity close notices in the expert log do not include exact PnL. The user observed account profit around `+$30`, which is plausible from the terminal/account view, but exact realized total should be confirmed from MT5 account history or a native account statement export.

## Why V16 Is Working Right Now

The current positive result appears to come mainly from fast M1 momentum scalps:

- It enters frequently when short-term movement is strong.
- It moves SL to breakeven or small profit quickly.
- Several trades close fast before the market reverses.
- Apex M5 remains active and provides the broader framework and safety modules.

## Real-Money Risk Notes

V16 is spread-sensitive because its TP is short compared with its SL.

- TP is about `180 points`.
- SL is about `260 points`.
- A widened spread can consume a large part of the expected gain.
- XM real execution should require spread controls before any real-money use.

Recommended live safeguards for XM:

- Use the lowest-spread XM account type available.
- Add a hard MaxSpread gate before entry.
- Block rollover windows.
- Block major USD news windows.
- Track real spread distribution before using real funds.

Suggested starting spread policy for XAUUSD on XM:

- Normal MaxSpread: `35 points`
- Hard block: above `45 points`
- Rollover block: `23:55-00:15` broker time
- Red-news block: USD high-impact news plus/minus `15-30` minutes

## Operational Decision

Do not modify the live V16 instance while it is profitable and stable.

Continue to:

- Monitor V16 live behavior.
- Keep V21 Research as collector-only.
- Keep V21.67 rejected and undeployed.
- Develop V22 only as offline research until separately authorized.
