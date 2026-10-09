# Capital-70 planned-risk veto — R10 design proposal

Status: preparation only. No source change, compile, or native test authorized here. R9 hold-60/hold-90 USD70 results and attribution must be reviewed first. No qualification or deployment claim.

## Evidence and mechanism

The immutable continuation control `research/ResearchControl_R1_R8.mq5` preserves the R1 signal and execution logic. It permits one owned position, checks existing position and the four-loss/90-minute breaker before a new signal, computes the original ATR/minimum-point stop, rounds that stop outward to tick size, applies the existing margin guard, then sends a fixed 0.01-lot order. Relevant code: `ManageOpenPositions` / hold exit at lines 547-560; `CheckMargin` at 583-596; `IsCircuitBreakerActive` from 603; order/SL construction and `trade.Buy` / `trade.Sell` at 755-797. The margin check blocks when required margin exceeds 70% of free margin; it is not a cash-loss budget and does not cap stop loss.

Existing evidence motivates risk measurement, not a claim that a veto will improve returns. R8 same-cache off/off development at P2 / SL2 / TP3 produced 1,797 trades, +$808.43, PF 1.0896; it did not meet PF 1.20. R8's three entry-quality arms all failed the development screen; exact paired entries showed no exit-economic improvement. R7's fixed-small-target ten-month result used structural $10,000 / 1:200, failed its full qualification criteria, and was not a USD70 / 1:500 test. R5 similarly states the isolated account's $70 / 1:500 is not the structural-test condition. Capital-70 R9 protocol now requires all new native runs to use $70 / 1:500; its outcomes are not yet available in the cited handoff. Do not substitute old 1:200 signatures or scale those historical profits.

`InpMinSLPoints=150` is price-distance geometry: 150 points multiplied by the symbol point, with further outward tick rounding. It is not inherently $1.50 of cash loss. Earlier 1:200 symbol specs report contract size 100, tick size .01, and tick value .1; those fields do not authorize a cash-risk conversion for a new $70 / 1:500 run. Obtain each order's estimated account-currency loss from `OrderCalcProfit` using the actual run's executable-side quote and original rounded SL.

## One limit hypothesis

If R9 review authorizes an R10, test a single pre-registered maximum planned stop risk of **2.5% of current account equity per new position**. At $70 equity the initial budget is $1.75; budget then moves with `ACCOUNT_EQUITY`. This is a proposed risk ceiling, not a claim that existing stop geometry produces $1.75 risk or that the threshold is optimized. No sweep or post-outcome retuning.

Use the already selected R9 hold configuration without alteration. Keep its signal, P2 preset, 2 ATR stop multiplier, 3R target, hold policy, fixed 0.01 lot, one-position rule, hard SL, margin check, breaker, and all other predicates unchanged. Compute the original stop exactly as today:

- Buy: `entry_quote=Ask`; `SL=floor((Ask-slDistance)/tickSize)*tickSize` after current digit normalization.
- Sell: `entry_quote=Bid`; `SL=ceil((Bid+slDistance)/tickSize)*tickSize` after current digit normalization.
- `slDistance=max(InpStopLossATRMul*closedATR, InpMinSLPoints*point)`.

After the existing signal and margin checks pass, but immediately before sending the order, call `OrderCalcProfit` with the intended side, symbol, unchanged 0.01 volume, executable-side entry quote, and the already-computed original SL. Let `plannedRiskCash=-estimatedProfit`; let `riskBudget=ACCOUNT_EQUITY*0.025`. A valid estimate passes when `plannedRiskCash <= riskBudget`; equality passes. Greater risk rejects that entry with a distinct `risk_veto` gate. Failed calculation, nonfinite/nonpositive equity, absent/invalid hard SL, nonfinite/nonnegative estimated loss, or invalid budget fails closed with `risk_calc_failed`. No order attempt follows either rejection.

Mode 0 keeps risk veto disabled for exact V24 parity. Compare same-settings mode-1 control with veto off against exactly one mode-1 treatment with veto on. Do not alter `CheckMargin` semantics or allow risk veto to stand in for the margin guard. Record intended quote, rounded SL, equity budget, planned cash risk, calculation status, and veto reason as diagnostics; diagnostics must not enter signal predicates.

## What estimate does and does not mean

`OrderCalcProfit` measures modeled PnL from the quote-time executable-side entry price to the original SL price in account currency. Using Ask for a buy and Bid for a sell avoids a mid-price shortcut; actual stop geometry and quote spread affect that estimate. Do not subtract spread again as a second fee.

It is not a guaranteed maximum loss. The market order can fill after the quote-time estimate at a worse price; the stop can gap or execute with slippage beyond its level. Future spread widening, commission, swap, broker execution rules, and liquidation are not fully bounded by this pre-entry estimate. Report these separately from the planned-risk veto and reconcile actual openings/exits. Never claim that the veto guarantees a 2.5% loss cap.

## Test plan, only after R9 decision

Keep the research lab isolated in `.mt5-v23-tuning.local`, use the approved capital-70 evidence root, and run every new native baseline/control/treatment/stress at USD70 / leverage1:500 / fixed0.01 lot. Never interact with protected V24 terminal, chart, settings, orders, or account10013053330. No 1:200 run may be reused as a 1:500 control; no redeposit, lot scaling, stop widening, BE, grid, martingale, or VM action.

1. Preserve existing R9 full-period V24 production70 and exact mode-0 parity controls; verify actual HTML deposit/leverage, signatures, runtime/cache, SET, deal count/net, cash ledger and final balance.
2. Rerun the chosen fixed R9 mode-1 hold control with veto off. Confirm same runtime/cache and exact economic parity to its accepted R9 source/configuration.
3. Run one otherwise identical mode-1 veto-on development treatment. Do not test both hold values again unless R9 attribution identifies a separately preregistered reason.
4. Preserve existing capital-70 floors: development net>0 / PF>=1.20 / N>=150; validation net>0 / PF>=1.20 / N>=40; confirmation net>0 / PF>=1.10 / N>=40; full-period net>0 / PF>=1.15 / N>=150, at least7 positive months, net above capital-70 V24 and drawdown no worse than capital-70 V24. Require no native stopout, positive additional $0.20 fixed-trade stress, and positive 500ms full replay with PF>=1.10; report $0.50 stress. A veto-heavy run with too few trades, idle/depleted months, or poor net fails; no-stopout alone is not success.

Python/mocked and native fixtures should verify correct buy/sell order type and entry quote, use of already-rounded original SL, dynamic equity recomputation, exact 2.5% boundary, over-budget rejection before any order send, invalid/nonfinite calculation fail-closed behavior, mode-0 parity bypass, and unchanged lot/SL/TP/breaker/exit functions. Inspect and independently review final generated source and binary before any native execution. Keep every veto count, margin block, attempted order, fill, stopout, loss, and unmatched/occupancy change in the report. Do not call a vetoed historical entry a saved loss without native replay under the changed occupancy.

All available research months are already inspected. Any USD70 historical pass remains retrospective/post-selection, not prospective OOS or a future-profit guarantee. R10 requires separate parent approval after R9 results; this document alone authorizes no implementation or run.
