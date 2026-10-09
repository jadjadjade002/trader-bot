# Capital-70 continuation research

Date: 2026-10-08, Asia/Bangkok. Frozen before any new native capital-70 outcome.
User changed the research capital to USD 70 and protected the open V24 window.
This supersedes the structural USD 10,000 capital for new experiments only.
Existing evidence, criteria and failed outcomes remain unchanged.

## Isolation

- Never act on `C:/Program Files/MetaTrader 5/terminal64.exe`, its data folder,
  account, chart, inputs, Algo Trading switch, positions or UI. This is protected
  V24 on account 10013053330.
- Native research uses only `.mt5-v23-tuning.local`, local tester agents and
  `reports/v25_research_20261008_capital70`. No VM, SSH or Git mutation.
- Research authentication was completed manually by the user on 2026-10-08.
  The separate idle research window was closed normally before the batch.
  Do not extract passwords, interact with an authentication dialog or bypass
  a process-idle guard if authentication is required again.
- After user authentication, close only the positively identified idle research
  window normally to release the tester lab. Never use blanket process kills.
- Native launch is owned by the main orchestrator. Team files-only until review.

## New test contract

Every new baseline, control, treatment, validation, confirmation, full-period and
execution-stress run starts with USD 70, leverage 1:500, fixed 0.01 lot, XAUUSD
M1 on MetaQuotes-Demo real ticks. 1:500 retains the user's earlier account brief.
No deposit top-ups, grid, martingale, BE, dynamic lot increase or synthetic loss
caps. Broker spread remains in actual Bid/Ask fills. Additional USD 0.20/0.50
per-position stress is hypothetical accounting sensitivity, not an altered
native spread or a compounded equity replay.

Record requested deposit/leverage in run identity and verify actual Initial
Deposit/Leverage in native HTML and exported leverage in the EA specification.
Reconcile grouped net, native balance, one initial deposit, all closes including
any verified native end-of-test liquidation, and explicit broker stopouts.
Report margin-blocked attempts separately: a strategy that becomes too poor to
open another 0.01-lot position has not demonstrated operational success merely
because it never reaches broker stopout.

Old implicit 1:200 signatures stay byte/logically unchanged. New 1:500 signatures
cannot reuse accepted 1:200 results. Freeze runtime and each complete month's
real-tick cache. Exact V24 mode-0 parity comes first at the new capital/leverage.
Historical comparison with USD 10,000 is descriptive, never direct capital parity.

## R9: one change only

Use unchanged `ResearchControl_R1_R8.mq5` reporting clone, source SHA256
`961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B`, binary
`2F59FC1F06CDAFF468F137ACF650C4198CE4BDB68CC6962551CFEBDBC46535CE`.
Immutable R1 parent stays
`0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2`.

Compare mode1 continuation P2 / SL2ATR / TP3R / hold60 against hold90 on identical
development dates. `hold` means existing iBarShift M1 bar distance, not guaranteed
wall-clock minutes. Change only InpMaxHoldBars. Existing hard SL, quote filters,
one-position policy, margin gate and four-loss/90-minute breaker remain identical.

Control rationale: the accepted structural-capital development run had 247 time
exits, 201 positive, median sampled MFE 2R, target 3R. This is an exit-horizon
hypothesis, not proof that those trades would reach TP or that small-capital
occupancy will match. Sampled MFE is not a counterfactual return.

Execution order: pinned V24 production70 full -> exact mode0 baseline70 full ->
continuation hold60 development -> hold90 development. Stop on parity, accounting,
runtime/cache or process-identity failure. No new signal/configuration grid here.

## Dates and gates

- Development: 2025.12.01 to 2026.06.01. Net >0, PF >=1.20, N >=150.
- Validation: 2026.06.01 to 2026.08.01. Net >0, PF >=1.20, N >=40.
- Lock exact source/binary/configuration before confirmation, no reselection.
- Historical confirmation: 2026.08.01 to 2026.10.01. Net >0, PF >=1.10, N >=40.
- Full: 2025.12.01 to 2026.10.01. Net >0, PF >=1.15, N >=150, at least 7 positive
  months, net above capital70 V24 and DD no worse than capital70 V24.
- No stopout and positive additional USD 0.20 stress are also required. Native
  500ms full replay must be positive with PF >=1.10. Report USD 0.50 sensitivity.

All stages use USD 70. Never scale structural profits to USD 70 or discard months
after depletion. Count idle and margin-blocked months. If hold90 fails development
or validation, it remains rejected. A matched hold60/90 full-period diagnostic may
still run with `qualified=false` to measure occupancy and capital survival.

Every historical month is already inspected. A pass is retrospective/post-selection,
not genuinely unseen OOS or a future-profit guarantee. No candidate auto-deployment
or overwrite of the protected V24 window. V25 naming requires reconciled evidence
and independent review, not merely lower historical loss.

## Advisory and team availability

The earlier three-agent quota block expired at 17:16 Bangkok. The three existing
agents resumed for runner review, loss attribution and a bounded risk-veto design.
Fresh-run review found no launch blocker. Resume-lock chronology was hardened
separately without changing the running fresh-prefix experiment or its gates.
An earlier Antigravity advisory timed out after 50 seconds. A new abstract-only
advisory was requested after the capital70 results. No response or model identity
is claimed before receiving it. No secrets supplied.
