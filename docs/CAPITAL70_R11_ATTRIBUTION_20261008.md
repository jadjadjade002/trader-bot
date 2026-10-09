# R11 capital-70 attribution — 2026-10-08

## Verdict

R11 did not qualify and is not V25. The one-completed-M1-bar persistence treatment produced 125 trades, net **-$59.53**, PF **0.8555**, max equity DD **$97.36 / 90.29%**, and final balance **$10.47** from $70. Its same-period delay-off mode-1 control produced 56 trades, **-$59.30**, PF **0.7253**, DD **$91.31 / 89.51%**, final balance **$10.70**. The treatment added 69 fills and raised aggregate PF, but lost $0.23 more and worsened DD by 0.78 percentage point. Those are batch aggregates, not paired outcomes for any arm or expired signal.

Both arms exhausted most capital in December 2025: all 125 treatment trades and all 56 development-control trades are in December. R11's treatment full replay has no January-through-September fills. The accepted R9 hold60 full-period parent reference also has no later fills, but R11 did not separately rerun a full-period mode1 delay-OFF parity control. The data therefore do not show sustained monthly evidence. Qualification gates remain failed; no V25 claim or deployment authorization follows.

## Evidence and queue accounting

Primary source is `reports/v25_research_20261008_capital70/r11_70_a_complete.json`; run-level raw/signal/deal files and `delay_audit.json` are under `reports/v25_research_20261008_capital70/runs/`. All four runs were accepted, with real-tick native reports and frozen source/binary hashes recorded in the completion record. The offline delay-state audit reconciles the emitted rows; it establishes execution history, not hypothetical PnL.

| Window | Armed | Filled | Margin-blocked at due | EMA9-close expiry | Trend-mismatch expiry | Other expiry | Censored | Trades / net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dev, Dec–May | 5,818 | 125 | 5,007 | 650 | 35 | 1 skipped bar | 0 | 125 / -$59.53 |
| Full, Dec–Sep | 7,798 | 125 | 6,836 | 788 | 46 | 3 skipped bars | 0 | 125 / -$59.53 |

Lifecycle closes exactly: dev `5,818 = 125 + 5,693 + 0`; full `7,798 = 125 + 7,673 + 0` (filled + expired + censored). No waiting row remained unresolved; no request rejection or held-at-due expiry occurred. Margin-blocked confirmations were the largest observed terminal group. This shows the $70 / fixed-0.01-lot environment constrained execution after account depletion; it does **not** show those blocked entries would have been profitable or that a larger account would qualify the signal.

The same-period delay-off control had 56 trades and net -$59.30, with 24 buys / +$20.91 and 32 sells / -$80.21. R11 treatment had 68 buys / +$34.13 and 57 sells / -$93.66. Side aggregates are descriptive only: timing changed which trades executed and account state, so subtracting sides does not form a paired signal effect. No BUY-only filter is justified by these results.

## Loss and exposure profile

Treatment exits: 88 stop-loss exits (reason 4), all losing, net -$400.73; 22 take-profit exits (reason 5), net +$285.97; 15 other managed exits (reason 3), 12 winners / 3 losers, net +$55.23. Their sum reconciles to -$59.53. Reported largest single loss was -$12.50, equal to 17.86% of starting $70; equity drawdown peaked at 90.29%. Native report recorded no stopout. The costs already reflected in the ledger include -$0.38 swap and zero commission/fee. An additional per-trade cost stress of $0.20 made net -$84.53; $0.50 made net -$122.03. These are sensitivity calculations, not actual charges.

For 125 filled entries, logged decision ATR14 ranged **0.92–6.1279**, median **2.0229** in quote-price units. With frozen stop geometry `max(2 × ATR, 150 points)` and point 0.01, planned stop widths were **1.84–12.2557**, median **4.0457** quote-price units; all 125 had `2×ATR > 1.50`, so minimum-stop floor did not bind on this fill sample. ATR/stop width is not cash risk: no trustworthy per-entry OrderCalcProfit/cash-risk record is available here. Do not convert using exported tick value or equate stop width with a guaranteed maximum loss; gaps/slippage and account margin remain relevant.

## Interpretation and next step

The test supports a narrow finding: one-bar confirmation changed the executed trade set and aggregate PF, but did not improve net or capital survival. Queue expiries—especially due-time margin blocks—are execution constraints, not evidence that a signal filter should target a side. The complete period is descriptive reuse of the same historical tape, not unseen OOS.

Do not launch another signal batch on the same $70/fixed-lot setup yet. If a next symmetric hypothesis is preregistered after a separate, explicitly authorized capital-feasibility design, use this bounded rule: preserve R11 arm/due timing, but at due require the completed confirmation close to extend at least **0.10 × origin ATR** beyond EMA9 in the original direction (`BUY: close − EMA9 ≥ 0.10×originATR`; `SELL: EMA9 − close ≥ 0.10×originATR`). Keep both sides, exits, lot, costs, and all qualification gates fixed; compare to delay-off and R11 unchanged controls. Rationale is testable follow-through strength, not a claimed R11 feature or observed edge. Falsify on failure of existing sample/economic gates, inability to execute enough trades, or no net/DD improvement over controls. This threshold is a proposed preregistration only, not selected from confirmation PnL; if capital feasibility cannot be fixed without changing other conditions, stop rather than run it.

No expired, margin-blocked, or vetoed event is assigned counterfactual profit. No losses removed. No parameter was reselected from validation/full-period results.
