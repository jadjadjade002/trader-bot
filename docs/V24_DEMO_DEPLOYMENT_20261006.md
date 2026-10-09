# V24 demo deployment, 2026-10-06

Status: deployed and verified, user-authorized forward demo experiment. This overrides the previous research-only deployment prohibition for this specific candidate/account. It does not convert failed profitability screens into a pass.

## Active deployment

- Account: **5056497798**, MetaQuotes-Demo, hedging demo
- Expert: `AegisPredator_v24`, version24.00
- Chart: XAUUSD M1
- Signal: verbatim tested completed-M5 EMA20/EMA50 trend/slope/separation, completed-M1 EMA9 pullback/reclaim aligned with EMA20, spread<=0.1 M1ATR and chase distance<=0.5 M1ATR
- Lot0.01, SL1.5ATR/floor150points, TP2R, maximum hold60 M1bars, BE absent/off
- FadeBreakouts=false. Strategy follows the proposed trend signal rather than blindly inverting an old breakout.
- Magic992300 retained to preserve management of same-magic positions and original breaker-history scope
- Session guard off, legacy fixed spread guard off, proposed spread/ATR filter active, margin guard on, broker hardSL on
- Circuit breaker unchanged:4 losses/90-minute pause. Its known old limitations are not fixed in this release.
- Demo-only/account/symbol/timeframe initialization guards. Switching to another account fails the configured target-account check. Real account always rejected.

## Build and native parity

- Source SHA256: `5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E`
- EX5 SHA256: `5A11086D05F7AA5C4E0B3D806B58BFF446BE08CC0EC8A48944A7681D42A539AF`
- MetaEditor compile:0errors,0warnings
- Five-month native packaging parity:1,476 positions, net **-$165.23**,100%real ticks
- V24 native ordered orders/deals match the chosen proposed/BE-off model. Only the order-comment version tag was normalized for comparison. Nine native metrics, including tick/bar counts and drawdown, match.
- Evidence: `reports/v23_tuning_20261006/v24_demo_20261006_v24_parity.json`
- Packaging/deployment/regression tests are recorded separately. Full-repository tests were not claimed to pass because two legacy EA sources are missing.

## Deployment verification

Target terminal only was closed via ICCCM WM_DELETE_WINDOW. V23 journal confirms deinitialization reason9. No forced kill, no manual position close, no blanket Wine restart, no account relogin.

- Previous target PID473494; new PID516476
- V24 initialized2026-10-06 13:03:15 UTC
- Runtime health:Connected1,AutoTrading1,EAAllowed1,AccountTrading1,AccountExperts1
- At startup:positions0,balance/equity/free margin **$114.84**. This is the V24 forward baseline, not V24 profit.
- Other terminal PIDs unchanged:102616,220476,234804,238977,306652
- V21 Research remains PID220476. Accounts112334471 and112468807 were not modified.
- Uploaded MQ5/EX5 hashes match the parity-verified local artifacts. Both chart-profile copies now referenceV24.
- Local deployment evidence: `reports/v24_deployment_20261006.json`

## Current pause is expected

At13:04:00 UTC the V24 expert inherited four losing historical V23 exits under magic992300 and triggered the existing90-minute breaker. Pause ends at broker17:34, approximately**21:34 Thailand on2026-10-06**. Restart resets its RAM cooldown, so the old pause was restarted. No streak/history was cleared. The inherited breaker print still saysV23 because its function body was preserved exactly. The log's expert prefix isAegisPredator_v24.

After the pause, V24 still waits for its actual signal and margin/cost gates. No immediate trade is promised. Report future V24 PnL from this deployment baseline and V24-comment-tagged positions, not total account history including predecessors.

## Recoverable backup

VM folder:

`/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo/v24_upgrade_backups/20261006T130241Z`

Contains originalV23MQ5/EX5, pre-close and post-close charts, preflight and deployment metadata. The old expert files remain available but are no longer attached to the target chart. Launch logs use a new timestamped filename rather than overwriting earlier logs.

No Git commit/push performed. No further strategy/configuration changes were made after the parity check.
