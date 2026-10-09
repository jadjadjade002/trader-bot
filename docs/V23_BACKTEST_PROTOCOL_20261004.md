# V23 — Frozen native backtest protocol, 2026-10-04

Preregistered **2026-10-04T15:08:16Z**, before full-period comparisons. Machine-readable counterpart: [protocol.json](../reports/v23_backtest_20261004/protocol.json).

Method clarification **2026-10-04T15:49:51Z**, before any full strategy run: independent market-data audit, explicit capital-halt outcome and exact signal/order linkage. No strategy, input, economic or metric change.

Scope: native MT5 tester, isolated lab only. Compare current frozen V23 Fade, momentum, and close-back-inside Fade. Source, production binary, VM, live EA/config remain untouched. No execution/risk repairs in this batch.

Existing May4–May8 original-EX5 smoke is setup evidence only. Exclude pilot profit from strategy selection/inference. May–September is **retrospective/exploratory**; September already inspected. No untouched holdout.

## Frozen inputs and artifacts

| Original input | Value |
|---|---:|
| InpEnableSessionGuard | false |
| InpEnableSpreadGuard | false |
| InpEnableMarginGuard | true |
| InpEnableHardSL | true |
| InpStartHour | 11 |
| InpEndHour | 16 |
| InpMaxSpreadPts | 25 |
| InpMaxHoldBars | 60 |
| InpDonchianPeriod | 20 |
| InpATRPeriod | 14 |
| InpStopLossATRMul | 1.5 |
| InpTakeProfitRRMul | 2.0 |
| InpMinSLPoints | 150 |
| InpLotSize | 0.01 |
| InpFadeBreakouts | true |
| InpMagicNumber | 992300 |
| InpTargetAccount | 0 |
| InpEnableCircuitBreaker | true |
| InpMaxConsecutiveLosses | 4 |
| InpCooldownMinutes | 90 |

Session/spread guards disabled means **24H and no spread threshold**. Start/end/spread inputs remain frozen but inactive. Margin guard, hard SL and original circuit breaker remain enabled.

| Artifact | SHA-256 |
|---|---|
| AegisPredator_v23.mq5 | C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0 |
| Original AegisPredator_v23.ex5, including lab copy | E5B725EC83945B9E2126B72978E02A2EFCA28EC33AD649E575B4F5E2F4021AC0 |
| MetaEditor build6182 | 197CA3DD8D1971831366F54CB57BF3F120B420700E573135509D406E4E23709E |

Tester-only harness uses separate filename and records source/binary hashes and compilation diagnostics. Mode0 preserves original decision/order/risk behavior. Instrumentation may export evidence; it may not fix source defects or add trading actions.

Selected active terminal/tester/agent build **6238**, re-frozen **2026-10-04T15:52:37Z** before any full strategy run. LiveUpdate actually changed6207→6238 during parity_original_v3 startup: native terminal log lines169/174 show journal22:50:44 update and22:50:54 build6238 start; agent log line7511 and tester log line7596 confirm6238. Initial runner failed fresh-report check due update relaunch; retain failed artifacts, do not accept parity. Engineering-only runtime change; no strategy/input/risk change.

Previous protocol preserved as [Markdown archive](../reports/v23_backtest_20261004/protocol_before_runtime_update.md) / [JSON archive](../reports/v23_backtest_20261004/protocol_before_runtime_update.json), hashes in current protocol.json. No6207 restore or undocumented update bypass. **Rerun originalEX5/harnessmode0 parity on6238**, then use6238 for market probe and six comparisons. Check runtime before/after each run; drift blocks acceptance.

| Frozen6238 artifact | SHA-256 |
|---|---|
| terminal64.exe | 33C04BC146C3881FEA12DAA4C842F60BB402B79C542DB6919D232819820C9351 |
| metatester64.exe | D9DC88909ACC2377248D8A390D9C70B0C73BD2DADB2A19275263EE50799C25FF |

## Signal predicates: fixed before results

On first observed tick of new M1 bar, preserve original first-attachment bar skip. CopyRates starts at closed-bar shift1:

- rates[0]: completed retest bar1.
- rates[1]: completed breakout bar2.
- Channel: rates[2..21], completed bars3..22.
- ATR: iATR(M1,14), CopyBuffer shift1; completed retest included.

Let H/L = Donchian high/low, A = ATR, O/C = retest open/close, RH/RL = retest high/low, B = breakout close.

| Pattern | Original | Closeback |
|---|---|---|
| Bullish breakout | B > H && RL >= H - 0.5*A && C > O | B > H && RL >= H - 0.5*A && L < C && C < H |
| Bearish breakout | B < L && RH <= L + 0.5*A && C < O | B < L && RH <= L + 0.5*A && L < C && C < H |

Closeback **replaces candle-color condition**, preserving original 0.5ATR proximity. Equality at channel edge excluded. No added touch/wick requirement. Green or red retest can qualify. Closeback is **not a subset** of original: both removed and added candidates exist.

| Variant | Predicate | Bullish breakout order | Bearish breakout order | Fade input |
|---|---|---|---|---|
| original_fade / mode0 | original | SELL | BUY | true |
| momentum / mode1 | original | BUY | SELL | false |
| closeback_fade / mode2 | closeback | SELL | BUY | true |

Momentum changes Fade flag only. Other settings identical. For anti-lookahead, prohibit forming-bar OHLC, future/final entry-bar spread, entry-at-retest-close or later entry-bar extrema. Entry uses actual first eligible new-bar tick, original quote refresh and gate order.

## Period, native settings and capital

Continuous broker/tester-clock interval **[2026-05-01 00:00:00, 2026-10-01 00:00:00)**. Report May, June, July, August, September. No monthly restart, state reset or redeposit. Preserve native warmup and first-tick behavior; verify actual first/last ticks and exclusive end.

Native settings: XAUUSD/M1, USD, **Model=4**, **ExecutionMode=200ms**, fixed **0.01 lot**, **leverage1:200**, Optimization=0, ForwardMode=0, Visual=0, UseLocal=1, UseRemote=0, UseCloud=0. Common Experts Enabled=0, AllowLiveTrading=0, AllowDllImport=0. All 20 original inputs explicit in each .set file.

| Full run | Deposit | Purpose |
|---|---:|---|
| original_fade_10000 | $10000 | fixed-lot signal diagnostic |
| momentum_10000 | $10000 | fixed-lot signal diagnostic |
| closeback_fade_10000 | $10000 | fixed-lot signal diagnostic |
| original_fade_70 | $70 | account feasibility |
| momentum_70 | $70 | account feasibility |
| closeback_fade_70 | $70 | account feasibility |

$10000 limits margin truncation while preserving original guards; its percentage return/DD does not represent $70 risk. $70 must retain any margin block/stopout and later zero-trade months. Do not refill/rerun months to conceal capital exhaustion.

If native $70 simulation terminates early from **explicitly evidenced stopout/capital exhaustion**, classify **failed_feasibility**. Preserve halt reason, completed_to, ending balance/equity, cost-reconciled deals and remaining-position status. Independent full-market probe must already pass. Compare $70 processed prefix to probe; Sep30/five observed simulation months not required after evidenced economic halt. Later months = inactive_due_feasibility_halt, zero count/net only when no remaining position/liability; PF/DD null with inactive status. Missing data, runtime failure or export failure never qualifies. Margin gate blocking entries while tester continues still requires normal full-period coverage and observed zero-trade months.

Preserve SL=max(1.5*ATR,150*point), TP=2*SL distance, original side-specific tick-size rounding, original symbol+magic single-position gate, and per-tick iBarShift>=60 time exit. Preserve original DEAL_PROFIT-only three-day breaker and 4-loss/90-minute cooldown, including original zero handling and defects. Net-loss analysis may differ from this gross-profit breaker.

200ms is fixed modeled delay. It does not recreate audit-observed long live delays, outages or changing production broker costs. Export actual MetaQuotes-Demo server/symbol contracts, digits, tick size/value, volume constraints, margin/stopout, stops/freeze, sessions, spread, commission/swap/fee policy. Broker context limits conclusions.

## Original EX5 smoke parity: prerequisite

Original EX5 and harness mode0: **[May4 00:00, May8 00:00)**, deposit10000, leverage200, delay200, same accepted data/runtime/inputs.

Both parity runs must use frozen **6238**. Earlier6207 smokes and failed update-relaunch setup remain engineering evidence; they do not satisfy new-runtime parity.

Compare complete ordered entry/exit deals: timestamps, direction, volume, prices, net cost components, SL/TP, exit reasons, breaker triggers/cooldowns, trade counts/native net, native equity DD and first/last ticks. Normalize ticket IDs/log prefixes only; preserve event order/economic values. Matching net alone insufficient.

Parity failure blocks variant inference. Resolve instrumentation/compiler/runtime discrepancy before full comparison. Preserve original EX5 and all smoke reports/logs.

## Real-tick quality: fail closed

Seed cache is not coverage proof. Prefer v20 April–July; v17 August–September. v17 July starts July31 and cannot replace full v20 July. v17 September seed last written September28; Sep29–30 requires sync/proof. Old copied bar cache yielded zero ticks; successful rebuilt smoke does not prove full-period coverage.

Run **independent tester-only market-data probe**, full [May1,Oct1) interval, Model4, **no trades and no delay**, same frozen6238 runtime/cache. This audits data; it is not a fourth strategy. Export daily/monthly source-tick counts, first/last tick, every intraday intertick gap >300s, daily M1 bar counts, current quote/trade sessions/specs, native bar/tick totals, history quality and native logs.

Verify expected first active May1 tick, final active Sep30 tick, each active day/month, M1/tick consistency and every flagged gap. Current sessions help explain closures; they do not prove historical holiday/schedule changes. Unexplained active-market omissions or substituted ticks fail closed. After probe passes, freeze synchronized cache hashes/runtime/specs. Every completed **$10000** strategy run must match probe native full-period bar/tick totals and range. Trading-EA callback counts may differ during synchronous200ms orders; they do not prove raw coverage. Evidenced $70 capital halt uses exception above.

Acceptance requires:

1. Verify broker history from May1 through final active Sep30 tick. Export first/last tick and daily/monthly tick counts; compare corresponding M1 bars and broker sessions.
2. Explain scheduled closures separately from missing active-market data. No unexplained active-market gaps or tick substitution accepted as full real-tick validation.
3. Native history quality100% necessary but insufficient. Preserve terminal/agent logs, generated/substituted-tick warnings, native bar/tick totals and uncovered intervals.
4. Freeze cache sizes/SHA256 **after sync**, runtime/spec/data manifest, and compare before/after all runs. Reject unexplained cache/build/spec drift.
5. Reject zero-tick, stale/missing report, initialization/runtime failure, incomplete dates or out-of-range entry. Only evidenced $70 economic halt after accepted independent full-market probe may yield failed_feasibility with partial processed dates. Verify every entry < Oct1 00:00. Required deal/position, raw-candidate, equity and symbol-spec exports must parse with expected records; HistorySelect failure, unexplained header-only exports or missing files fail closed. EA callback count is not source-tick coverage proof.
6. Identify native end-of-test liquidation; do not silently treat it as ordinary exit.

Unresolved quality => artifacts labeled failed_quality/incomplete; no valid five-month comparison or superiority claim. Do not substitute Python bar simulation for missing native data.

## Position accounting, monthly metrics and DD

Group by **DEAL_POSITION_ID**, symbol and magic. Net completed-position PnL sums **DEAL_PROFIT + DEAL_COMMISSION + DEAL_SWAP + DEAL_FEE** across entry and exit deals. Export non-trade fee/charge/balance adjustments separately; reconcile total net and final balance minus deposit, excluding cash transfers. Money tolerance $0.02. No omitted or unattributed costs.

Existing HTML parser cols8+9+10 lacks fee proof. Fallback permitted only for complete unambiguous single-position round trips with exported/proven fee=0. Ambiguous concurrency, reversal, out_by or partial grouping needs position-ID export.

Requested PF is **netPF**: sum positive completed-position net / absolute sum negative net. If no losses, report null with no_losses status. epsilon=$1e-8: net>epsilon wins; net<-epsilon losses; others breakeven. Show gross profit/loss and cost totals beside netPF; native PF may differ.

Monthly closed counts, net, netPF and win/loss counts use **broker exit month**. Also report entries, open-position carry and cross-month positions. Position-level cost attribution follows final exit month, including earlier entry costs; distinguish from calendar cashflow timing. Forced-test-end closes stay in reconciled totals, with count/net disclosed separately.

Loss streak: chronological completed-position **net losses**, breakeven resets metric, carry streak across months. Report monthly opening carried streak and maximum ongoing streak; also report original gross-profit breaker events separately. Trading/account/breaker state never resets monthly.

DD:

- Overall native equity DD money/% authoritative; native balance DD separate.
- Monthly: sample equity before/after each native OnTick; update month peak/max peak-to-trough; final OnTester sample includes test-end liquidation.
- Monthly peak starts at first observed equity of month. Monthly DD excludes inherited drawdown from previous-month peak; account/trading state remains continuous.
- Reconcile sampled whole-period DD against native. Matching overall DD alone does not prove monthly DD exact. Synchronous200ms trading may consume ticks without EA callbacks: monthly callback DD is **lower bound** unless full-tick reconstruction validates completeness. Disclose sampling gaps/mismatch and label monthly values **EA-observed-tick equity DD**. Never relabel closed-trade balance DD as equity DD.

## Filtered winners and path dependence

Candidate key = new M1 bar broker timestamp + breakout side, on identical closed-bar snapshot. Log **every observed new bar**, including all-false predicates, data-unavailable and first-attach/evaluation status. Export original/closeback raw predicates independently of gates plus explicit evaluated/gate/order-attempt outcomes.

Classify raw common/removed/added **within one ledger using both predicates on same row**. Another run missing callback is callback divergence, never proof predicate removed opportunity. Link filled position to exact signal using successful attempt signal_bar + order_ticket + deal_ticket, then native DEAL_ORDER/DEAL_POSITION_ID. Do not join by fill minute: 200ms may cross bar boundary. Unknown/ambiguous linkage fails closed for filtered-winner attribution.

Classify **common / removed original / added closeback** raw candidates. For original_fade filled completed positions, classify closeback predicate at original signal. Removed baseline winner = closeback fails and observed baseline trade net>epsilon. Report removed winners count/net, removed losers count/net, breakeven, retained baseline positions, added raw candidates and monthly baseline-exit attribution.

These are baseline observed outcome labels. They do not predict counterfactual variant profits. Occupancy, exits, breaker and margin create path-dependent portfolios; opposite strategies are not paired trades or PnL negations. Report gate/occupancy/breaker divergence separately.

## Deliverables and acceptance

Save unique-run native reports/logs, harness source/binary/compile log, explicit .set/.ini files, source/binary/config/input hashes, frozen runtime/cache/spec manifests, independent market-probe/gap/coverage exports, fee-aware deal/position/candidate/equity summaries and monthly/overall comparison JSON/Markdown.

Result acceptance requires frozen artifacts, original parity, full real-tick coverage without unexplained substitution, same runtime/data/specs, complete net/fees reconciliation and honest DD/end-boundary accounting. No parameter/predicate/capital/delay changes after full-period result inspection. Changed protocol needs versioned exploratory batch. No deployment or live trading in this task.
