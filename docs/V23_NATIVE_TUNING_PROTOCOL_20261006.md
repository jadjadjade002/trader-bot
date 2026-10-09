# V23 native comparison and bounded tuning, 2026-10-06

User authorized three-model comparison and subsequent configuration research. No live deployment is included. Existing breaker is retained verbatim.

## Verified VM baseline

Read-only SSH inspection at 2026-10-06 10:42 UTC found the running terminal in `MetaTrader 5 V16.59 V22 New Demo`, account 5056497798, chart XAUUSD M1, expert AegisPredator_v23. Today's expert journal contains filled order notices. Source SHA-256 `C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0`; EX5 SHA-256 `E5B725EC83945B9E2126B72978E02A2EFCA28EC33AD649E575B4F5E2F4021AC0` match local artifacts.

Chart inputs: session guard false, spread guard false, margin guard true, hard SL true, session hours 11-16 (inactive), max spread 25 (inactive), hold 60 M1 bars, Donchian 20, ATR 14, SL 1.5 ATR with floor 150 points, TP 2R, fixed 0.01 lot, FadeBreakouts true, magic 992300, circuit breaker true / four losses / 90 minutes. There is no BE in this source. The tester uses TargetAccount=0 because the cached local demo account differs from the VM account. This changes identity selection only.

## Period and models

Latest five complete calendar months: [2026-05-01 00:00,2026-10-01 00:00) broker time. May warmup and closed M5 data before evaluation are required. May-September has been inspected already. All results are retrospective research, including any selected validation slice. This replaces the initial rolling May6-Oct6 setup before any valid full-period result. A history-cache failure occurred during the incomplete October request, but root cause is not established. No rolling-window comparison was accepted. The five complete months have an existing independently audited real-tick cache.

1. `vm_fade`: original signal and exits, FadeBreakouts=true, BE disabled.
2. `normal`: identical model/settings except FadeBreakouts=false, BE disabled.
3. `proposed`: completed M5 EMA20/EMA50 trend with positive/negative EMA20 slope over five completed M5 bars and separation >=0.1 M5 ATR; completed M1 EMA9 pullback and reclaim in trend direction; M1 EMA9 aligned with EMA20; no entries more than 0.5 M1 ATR from the closed signal candle; entry spread <=0.1 M1 ATR. Initial SL 1.5 ATR/floor150, TP2R, BE at 1.2R with 0.05R profit buffer. Trend/range and spread thresholds are fixed hypotheses, not optimized thresholds. Quotes used for entry gating are current first eligible tick quotes. Breaker, lot, margin and original time exit remain identical.

BE additions are isolated in the research harness and can be disabled exactly. The buffer is not a guarantee of net break-even after fees or gaps. Report modification rejects and actual broker-deal net outcomes.

## Tuning fixed before new results

For each model, full five-month Cartesian grid: SL ATR in {1.0,1.5,2.0}, TP R in {1.0,1.5,2.0,3.0}, BE trigger R in {0,0.8,1.2}. Hold remains60, BE lock remains0.05R, lot remains0.01. Total 36 settings/model, 108 passes. Zero disables BE. Do not expand search after inspecting results in this batch.

Record full-grid in-sample winner separately from the selected candidate. Rank development [May1,Aug1), use [Aug1,Sep1) as validation, and reserve [Sep1,Oct1) for final diagnostic confirmation. The shared five-month optimization report is descriptive: selection must be recreated using development-only runs before confirmation is consulted. At most three development candidates/model advance to validation. Select by positive net first, net PF>=1.20, sufficient trades (>=100 development; >=30 validation/confirmation), then smaller native equity DD; net profit breaks ties. If no candidate passes, report no qualified configuration instead of renaming the least-loss setting profitable.

Retest finalists continuously over all five months and at $70/1:200, no redeposit. Structural grid capital $10,000/1:200 prevents early bankruptcy from hiding later signal behavior. Report capital halt at $70, native equity DD, months, net commission/swap/fee, stop/TP/time/BE exits, and sampled MFE/MAE. Prefer stable neighboring parameters; full-sample maximum is not validation.

Execution: native MT5 real ticks, 200ms fixed delay, local agents only, cloud and remote farms disabled. Snapshot source/binary/runtime/set/INI and tick-cache hashes. Runtime change requires a fresh batch freeze and recheck baseline parity. A report with zero bars/ticks, agent errors, history substitutions, missing end coverage or accounting mismatch is invalid. Failed setup runs are retained as setup failures.

## Current setup finding

Restoring the isolated lab's cached demo account fixed the missing account selector. Smoke runs auth_smoke_20261006 through auth_smoke3_20261006 returned empty native reports because the local tester agent failed authorization. Those runs are invalid and must not be interpreted as zero-profit strategies. Agent selector/agent state backups are recoverable inside the old lab.

The fresh local lab updated to build6241. Prestarting its local agent within the same process ownership as the batch and restoring the preserved May-Sep history enabled valid native runs. Both runtime executables were hashed and frozen. Do not claim the cold-start failure's underlying cause is established. Primary comparison native evidence: 58,118,739 ticks,143,336 bars,100% real ticks through September30. Original EX5 ordered economics are checked against the instrumented baseline, not only aggregate net.

The complete batch contains108 full-period passes and108 development-only passes. Supplemental checks replay the full-sample maximum of each model individually at $10,000 and $70, six runs total. These maxima remain descriptive, regardless of rejection by the development gate. No additional grid dimensions are introduced. Tick-cache hashes are audited against the earlier frozen May-Sep cache and checked before/after supplemental retests. This is a shared-cache post-run reconciliation, not an independently captured pre/post manifest for every optimization pass.
