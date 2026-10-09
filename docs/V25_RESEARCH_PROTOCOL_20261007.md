# V25 bounded native research, frozen before new outcomes

User request: develop V25 from V24 using demonstrated backtest defects, compare configurations and confirm the best candidate over ten months. No VM deployment or account changes authorized in this round.

## Team and baseline

Three delegated roles: signal attribution, candidate implementation, independent verification. Main orchestrator owns native execution, selection and evidence reconciliation. Baseline is the deployed V24 production binary, not V23 fade. Frozen source SHA256 `5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E`, EX5 SHA256 `5A11086D05F7AA5C4E0B3D806B58BFF446BE08CC0EC8A48944A7681D42A539AF`.

V24 already follows completed M5 EMA20/50, EMA20 slope and completed M1 EMA9 reclaim. Invert=false. Do not assume that every SELL during a recent M1 rally is a direction bug. Separate causal replay from descriptive subsets.

## Dates and contamination

Ten latest complete calendar months: `[2025-12-01,2026-10-01)` broker clock.

- Development: `[2025-12-01,2026-06-01)` six months.
- Validation: `[2026-06-01,2026-08-01)` two months.
- Locked historical confirmation: `[2026-08-01,2026-10-01)` two months.
- Whole ten-month replay is retrospective robustness evidence, not an independent confirmation sample.

May-September was already inspected and May-July previously used for tuning. Therefore none of the later reused historical slices may be advertised as untouched out-of-sample. A genuine future confirmation requires October onward after configuration lock. If broker real ticks cannot cover all ten months, report that blocker and do not substitute generated ticks, synthetic trades, or a shorter sample labeled ten months.

## Fixed hypotheses and parameter budget

Mode0: exact V24 signal and economics for harness parity.

Mode1: completed-M1 continuation beyond previous completed candle high/low, aligned with the same completed-M5 trend and M1 EMA9/20.

Mode2: V24 pullback/reclaim plus minimum body, favorable close position and reclaim buffer.

Mode3: completed-M1 breakout of ten prior completed bars, aligned with the same M5 trend and M1 EMA9/20.

Modes1-3 reject candle range above2ATR. Strength index0/1/2 maps respectively to minimum body/ATR `{0.10,0.20,0.30}`, favorable close-location `{0.60,0.70,0.80}` and buffer/ATR `{0.00,0.05,0.10}`. These are coupled presets, not three independently tuned variables. Baseline mode ignores strength.

Development grid per candidate: SL ATR `{1.0,1.5,2.0}` x TP R `{1.0,1.5,2.0,3.0}` x strength `{0,1,2}`.36 passes each,108 total. Max hold60 unchanged. BE off because previous five-month native BE variants performed worse and would confound signal attribution. Do not expand the grid after seeing outcomes in this batch.

## Execution and accounting

Native MT5 real ticks, XAUUSD M1, same broker history, fixed200ms execution delay, fixed0.01lot, leverage1:200, structural capital$10,000. Original margin gate, hard SL, minimum150points, magic992300 and4loss/90min breaker preserved. Tester account selection0 only inside isolated demo lab. No grid or martingale. No modification to the running VM, V21 collector or accounts112334471/112468807.

Before candidate search, compare V24 production and mode0 harness ordered native orders/deals and net/gross/trades/bars/ticks/DD. Include both2025 and2026 timestamps. Freeze source/binary/runtime/set/INI hashes and all requested monthly TKC cache hashes. Audit per-month observed tick/bar coverage, native100%real-tick report and journal warnings. First/last timestamps alone are insufficient.

Net uses all entry and exit profit+commission+swap+fee grouped by positionID. Reconcile with native profit, position counts and final balance. Cash adjustments other than initial deposit block acceptance. Real bid/ask spread is embedded in fill economics, not treated as a second explicit charge. Broker MetaQuotes results do not establish XM performance.

## Selection gates before outcomes

Development qualification: net>0, net PF>=1.20, closed positions>=150. At most three configurations per family proceed. Rank first by lower equity DD%, then higher net, then stable deterministic parameter ordering. Prefer a configuration with neighboring positive development results where available, report fragility rather than inventing stability.

Validation qualification: net>0, PF>=1.20, positions>=40. Rank the remaining candidates using validation DD%, then validation net, then deterministic configID. Lock exactly one candidate before viewing its historical-confirmation outcomes. Never reselect because its final result disappoints.

Confirmation: net>0, PF>=1.10, positions>=40. Whole ten-month criteria: net>0, PF>=1.15, at least7/10 positive monthly net values, higher net than V24, equity DD% no higher than V24. Report daily expectancy, Buy/Sell/month/regime/exit attribution and all rejected configs. No claim of guaranteed daily profit or high winrate.

Independently replay locked candidate at$70 without redeposit, compare baseline under same capital. Report broker stopout separately from margin-blocked entries. Additional cost sensitivity: subtract an explicitly hypothetical extra$0.20/$0.50 per completed0.01lot position from deal totals. This is accounting stress only, not a simulated change in spreads or entry timing. If practical, native500ms delay replay is an execution stress, with unchanged candidate.

If no config passes development or validation, no qualified V25 exists. A development-only least-loss configuration may be replayed over ten months for diagnosis, labeled descriptive and failed, not promoted. All setup failures retained. Development best is not the full-sample maximum.

## Deliverables

V25 candidate source and compiled artifact, frozen experiment manifest, full native artifacts, tests, independent review and outcome document. Only qualified/locked configuration may be described as historically successful. Deployment requires a separate user instruction.
