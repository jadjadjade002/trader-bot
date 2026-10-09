# R4 exhaustion exit ablation protocol

Status: frozen design, before any R4 outcomes. This is an exit-only experiment using the exact accepted R2 mode-5 exhaustion signal. It is not new signal mining and cannot establish a release candidate by itself.

## Motivation and evidence boundary

R2 mode 5 exhaustion was tested only with V24 exits: SL 1.5 ATR, TP 2R, 60-bar maximum hold, break-even off. Preset 0 returned +$41.97, PF 1.0369, 339 positions; preset 1 returned +$7.61, PF 1.0142, 156 positions. Neither met the development gate. These modest positive nets with near-one PF motivate a bounded payoff-timing ablation; they do not show that exits caused weak expectancy. The test isolates stop and target distances while holding the signal fixed.

Run R4 only if no R3 development configuration survives its predeclared gate. Do not use later R3 outcomes to decide whether to run or shape R4. R4 development window is `[2025-12-01,2026-06-01)` broker time, on the same native real ticks and execution setup as accepted R2 development. The 16-row matrix is fixed before any R4 result. Validation or later months must never add/remove matrix rows or change entry/exits. Finalist selection uses the development/validation sequence defined below, exactly as the parent frozen protocol. Confirmation/full-period outcomes never select or reselect the finalist.

## Frozen configurations

Candidate mode is exactly R2 `InpExperimentMode=5` (`R2Exhaustion`), with both existing presets `InpEntryStrength ∈ {0,1}`. Cross these with `InpStopLossATRMul ∈ {1.0,1.5}` and `InpTakeProfitRRMul ∈ {0.75,1.0,1.5,2.0}` for 16 configurations. No other combinations or parameter changes.

The exact V24 parity control remains mode 0, strength 0, SL 1.5 ATR and TP 2R. It is a single control run and is not one of the 16 exhaustion configurations. All other V24 economics and guards remain fixed: 0.01 lot, minimum SL 150 points, ATR period 14, Donchian period 20, magic 992300, hard SL enabled, 60-bar maximum hold, BE off, one position at a time, margin gate enabled, and four-loss/90-minute circuit breaker enabled. Session and spread guards remain off; tester target account remains 0. Tester mode required. No leverage, delay, deposit, broker-history, source, signal, cooldown, account, or execution changes.

The R4 builder reads the exact generated R2 source at SHA256 `74AC68D78650411B1364AA2EF6E18FD375928D0C528CBC23085C95867F1354FD`. It changes only the bounded input-validation function to permit the frozen matrix (while locking mode 0 to exact V24 economics), artifact version/description, and fixture log prefix. `CandidateR2Signal`, `R2Exhaustion`, every trade/risk function, SL/TP calculations and all 25 native R2 fixture predicates stay byte-for-byte unchanged. The original R2 source and signal extension remain untouched.

## Evaluation and interpretation

First verify source hash, compile, run the existing 25 real MQL fixture checks for each R4 tester initialization, and confirm mode-0 native parity against frozen V24. Reconcile accepted deals by position ID with profit, commission, swap and fee; preserve tick/cache hashes and monthly coverage. No synthetic trades or replacement economics permitted.

Before any R4 outcomes, the continuation policy is fixed: at most the top three development-qualified configurations in this one family proceed to validation, ranked by lower native equity DD, then higher net, then sorted input tuple. Use the existing frozen validation/confirmation/full-period gates. Lock one validation survivor before confirmation. No reselection after confirmation failure. If none survives, a development-only maximum may receive a rejected descriptive ten-month replay, never promotion.

Apply the frozen development qualification independently to each of the 16 rows: net > 0, net PF >= 1.20, and at least 150 closed positions. Report the complete matrix, monthly net, PF, positions, drawdown, long/short margins, exit-reason counts and native errors. Compare exit settings only within the same exhaustion preset and state which paired rows change. Do not pool counts across configurations. Do not call a best-scoring unqualified row a winner. If no row qualifies, report no candidate and stop the qualification path: no validation, selection lock, confirmation, or capital/stress qualification. Only the explicitly rejected descriptive replay permitted above may run outside that path.

The ablation can show whether this fixed exit grid changes outcomes for this fixed signal population. It cannot prove a general exit defect, identify a best regime, establish BUY/SELL direction error, or predict live performance. Any subsequent validation needs the frozen research protocol and a separate lock before its outcomes are viewed.
