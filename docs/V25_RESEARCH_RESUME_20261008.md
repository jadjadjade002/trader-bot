# Research resume, 2026-10-08

## Current status, updated 2026-10-08

The user created local research demo `113802049`, MetaQuotes-Demo, USD70 and leverage1:500. Main read-only terminal API verification confirmed the isolated research data directory, demo mode, connected state, and no positions or pending orders. MT5 saved its authorization in `Config/accounts.dat`. The private ignored record is `credentials.v25_research.local.md`. No plaintext password was captured or extracted. This saved local authorization is not a portable VM credential.

Authentication is resolved. A resumed attempt exposed changed full SHA256 values in all ten tick-cache month files. Subsequent automatic LiveUpdate changed the terminal and tester binaries from build6241 to build6246. Preserve old accepted records, freezes and the `r5_c_production_v24` failed-parent/quarantined-child evidence. No cached file equality or header-only rewrite is assumed.

The fresh batch uses `reports/v25_research_20261008_postupdate/`, R5 prefix `r5_d` and R6 prefix `r6_b`. Updated-runtime production V24 and R5 mode0 have both been accepted with exact ordered native economics and same runtime/cache provenance. Baseline ten-month net remains $130.00 over 3,768 positions. R5's actual MQL behavioral fixtures have now run and passed 27 checks in mode0. These facts do not establish a qualified new strategy or authorize release.

Every candidate month must match the reference baseline's complete accepted cache record before selection. The runner also checks lab process identity before launch and after parent exit, rejects any LiveUpdate handoff, and keeps drifted evidence unaccepted. Independent review approved the described fixes for isolated research provisionally using supplied actual code snippets because its command launcher could not reread files. Main inspected actual files and ran **173 affected Python tests plus 143 subtests**. No claim of independent final-file execution or complete repository testing is made.

The frozen native research leverage remains1:200. The newly connected account's1:500 does not alter these tests. A qualified candidate still requires a separate declared USD70/1:500 operating-condition test before that deployment. No V25 package or VM replacement exists yet.

R5_d and R6_b have completed, with 148 distinct development configurations across all rounds, including eight new cells in this runtime. None is qualified. R5 P1/A0 development passed but validation had only28 trades, below40. Descriptive ten-month net-$2.68, PF0.9955. R6 F1 descriptive ten-month net$21.70, PF1.1326, only53 trades and4 positive months. Actual paired R5 alignment filtering removed profitable subsets, so adding M1 EMA alignment was not supported by this sample. Detailed evidence is in `docs/CANDIDATE_R5_RESULTS_r5_d.md` and `docs/CANDIDATE_R6_RESULTS_r6_b.md`.

R7 preregistration is `docs/CANDIDATE_R7_PROTOCOL_20261008.md`: exactly four low-target cells, TP0.5/0.6R crossed with unchanged P0/P1 exhaustion entries. Controls precede outcomes, all previous gates retained. Its new generator and source are research-only. No profitable R7 result is implied by preparation or compilation.

R7_a now completed ten accepted native runs with31 actual fixtures each. Allfour development cells and both validation survivors retained. Both survivors had28 validation positions, below40. P1/TP0.6 descriptive ten-month net$73.61/PF1.2128/N202/DD0.34%,six positive months. Main verified whole-period202-entry pairing against fresh R5 TP1, no unmatched entries. Aggregate gain$76.29 is dominated by one avoided held quote-gap loss with paired improvement$144.11. Other201 pairs lose$67.82 of net versus TP1. Do not claim entry accuracy improved. See `docs/CANDIDATE_R7_RESULTS_r7_a.md`. Distinct development configurations now152, zero qualified.

R8 fixed continuation-quality factorial is preregistered in `docs/CANDIDATE_R8_PROTOCOL_20261008.md`. Three new treatments, ER10>=0.30 and/or extension<=1ATR, plus exact R1 off/off control. Initial `r8_a` stopped before treatments because the R1 post-test history export omitted one native forced liquidation beyond its last-quote upper bound. Native HTML has1,797 closed positions/net$808.43 but CSV has1,797 opens and1,796 closes. Strict parser rejected it. Preserve all evidence and the retrospectively labeled diagnostic, do not treat incomplete$808.41 as an accepted result. `r8_b` repeats the same protocol with an export-only reporting clone and equivalent R8 export endpoint. See `docs/CANDIDATE_R8_EXPORT_RECOVERY_20261008.md`. Runtime, ticks, predicates, exits and gates stay fixed. This remains post-selection historical mechanism research, not independent validation or V25.

Current bounded commands, sequential only:

```powershell
python -m research.run_candidate_r5 --activate --prefix r5_d --tester-login 113802049 --fresh-controls --evidence-root reports/v25_research_20261008_postupdate
python -m research.run_candidate_r6 --activate --prefix r6_b --tester-login 113802049 --evidence-root reports/v25_research_20261008_postupdate
```

## Historical authentication blocker

R5 is a tester-only research candidate, not V25. Its native baseline stopped before the EA initialized. MT5 logged `Accounts deleted due security reason`, followed by `tester not started because the account is not specified`. Exit code was `3294954943` (signed `-1000012353`). This proves that the tester could not use its saved account. It does not prove account expiry, a trading loss, or a signal defect.

Evidence: `reports/v25_research_20261008/runs/r5_a_baseline/started.json`, `journal_2.txt`, `journal_6.txt`, and an explicitly labeled post-run diagnostic `failure.json`. There is no native report, accepted record, or R5 profit result. Preserve this failed attempt. Do not repeatedly retry unchanged authentication.

Existing V24, other VM accounts, positions, and V21 collectors were not changed in this research turn. Deployment is blocked until a qualified package and fresh confirmed demo target exist.

## Restore only the isolated local tester

Run this command yourself to open the interactive research terminal with chart EA trading and DLLs disabled. This is not the VM or a production terminal.

```powershell
Start-Process -FilePath 'D:\project\trader-bot\.mt5-v23-tuning.local\terminal64.exe' -ArgumentList '/portable','/config:D:\project\trader-bot\research\tester_login_setup.ini'
```

In that terminal, choose File > Login to Trade Account. Use a user-owned **MetaQuotes-Demo** account and save its authorization locally. Never provide its password in a prompt, transcript, CLI argument, Git, or this document. Do not use or switch any protected production or deployment account for this setup. No chart EA should be enabled.

After the terminal connects, close only this isolated research window normally. Report its demo login number. A user-selected replacement login is recorded in new run provenance. The historical accepted controls keep their original signatures and are reused only after validation. Do not copy another terminal's account database or remove account-security protections.

If the setup does not connect, report the non-secret error. Do not register a different broker, change caches, weaken security, or run a live account as a workaround.

## Resume the fixed research batch

After review and confirmed local login, run from the repository root. Replace the numeric placeholder with the confirmed local research demo account. This starts backtests only, not chart trading or deployment.

```powershell
python -m research.run_candidate_r5 --activate --prefix r5_b --tester-login 1234567890
```

Use a new prefix when the connection provenance changes. The previous `r5_a` failure remains preserved. Do not delete it or reuse an accepted result whose signature differs. Once all development records and controls are accepted, use the matching attribution prefix rather than assuming the default run names.

R5 has four fixed cells: P0/P1 displacement presets crossed with completed M1 alignment off/on. SL is 1.5 ATR, TP is 1R, BE is off, and the baseline is exact V24/2R. Both no-alignment cells must reproduce accepted R4 economics before selection. The four schedule-dependent C1 cells remain unrun, not zero-profit outcomes.

R6 has a separate preregistration for two additional families with two fixed presets each. Independent source review and clean compilation are complete. Exact native fixtures and native V24 parity still must pass before its four development runs. Preparation and compile success do not count as profitable native results.

After the same local login is confirmed, its separate fixed batch uses this command. Do not run R5 and R6 concurrently because both use the same isolated native tester lab.

```powershell
python -m research.run_candidate_r6 --activate --prefix r6_a --tester-login 1234567890
```

## Final local preparation evidence

Three delegated Luna agents handled the candidate build, new signal families, and independent source review. The main agent verified their files, compilation, and the combined affected Python suite. No external-model debate or Antigravity transcript is claimed.

- Eight new configurations are prepared, not eight completed profit experiments. R5 tests P0/P1 exhaustion with M1 alignment off/on. R6 tests two failed-reclaim fade presets and two volatility-contraction breakout presets.
- R5 source SHA256: `98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494`.
- R5 binary SHA256: `842722988E75991E79996EC0C969B8115ABF18EBFFD5C1E9AD49F217B7F2A320`.
- R6 source SHA256: `F01ED3FD3E6994991B7420079331755C0E4BEEB03EE2F0A8005C98375D9A9F67`.
- R6 binary SHA256: `53E26478DD69A7F59C7EA1E74BBDCE66C3E9713E6525DB16A9BD54F654762DB3`, 115298 bytes, written `2026-10-07T19:42:42.0566890Z`.
- R6 compile log: `r6_compile.log`, `0 errors, 0 warnings`, 1590 ms. Independent reviewer verified the same final source hash before compilation.
- R6 fixes made before any native outcomes: failed-reclaim mode uses 23 contiguous M1 bars and two closed ATR values. Contraction mode retains 80 bars and 66 ATR values. Current-body normalization uses signal ATR. Held-position and circuit-breaker events remain explicitly censored, not fabricated zero-valued observations.
- Combined affected suite: **123 passed, 143 subtests passed** in 1.28 seconds. This is not a claim that the entire repository suite or the MQL behavioral fixtures ran.
- Python source-contract tests verify reproducible generation. R5 native fixture contract is 27 checks. R6 contract is inherited 27 plus 20 new checks. Their native execution is still unverified because the tester baseline failed before EA initialization.
- Pre-order Bid/Ask and order return code, order ID, and deal ID exist in the inherited raw CSV. They must be joined by exact event identity, not guessed from legacy zero-valued breakout fields or censored feature columns.
- R4 source and binary hashes remained unchanged. No VM terminal, account, position, V21 collector, or Git history was modified.

Final affected-suite command:

```powershell
python -m pytest tests/test_candidate_r1_runner.py tests/test_candidate_r1_luna_review.py tests/test_candidate_r2.py tests/test_candidate_r2_runner.py tests/test_candidate_r2_integrity.py tests/test_candidate_r3.py tests/test_candidate_r3_integrity.py tests/test_candidate_r3_luna_review.py tests/test_candidate_r4.py tests/test_candidate_r4_runner.py tests/test_candidate_r4_luna_review.py tests/test_candidate_r5.py tests/test_candidate_r5_analysis.py tests/test_candidate_r5_adapter.py tests/test_candidate_r6.py tests/test_candidate_r6_adapter.py tests/test_candidate_native_failure.py tests/test_candidate_native_login.py tests/test_candidate_winner_attribution.py tests/test_candidate_release_evidence.py -q
```

## Continuation audit, 2026-10-08

The local tester still has no saved `Config/accounts.dat` and no active terminal process. No unchanged native authentication retry was launched in this continuation. The previous setup failure remains preserved. This is still an input/connection blocker, not a completed strategy experiment.

The same three Luna agents audited selection/release gates, attribution integrity, and the existing economic evidence. Main review retained the frozen R5 top-three development shortlist and R6 all-survivor shortlist. These are different preregistered protocols, not a reason to change thresholds after outcomes. The exported $0.50 additional-cost stress remains a reported sensitivity. It was not silently promoted into a new mandatory gate.

Source-free attribution hardening changed only `research/analyze_candidate_r5.py` and its tests:

- Require `started.json.signature` to match `accepted.json.signature` after validation of the pinned source, binary, SET, period, and runtime contract.
- Join diagnostic and raw rows by exact `(bar, tick_msc)` identity and matching side, attempt, held state, and execution gate.
- Link raw `ResultDeal` to the actual native opening-deal ticket and position. Missing, duplicate, unmatched, future, or ambiguous events fail closed. Every completed position must reconcile. No same-minute fallback or silent position exclusion remains.
- A fill crossing a minute boundary is supported only through exact ticket identity and event time preceding the actual fill. No guessed delay limit is introduced.
- Reject unsupported opening volume, multiple opening fills, fractional integer identifiers, and direction values outside `-1, 0, 1`. Preserve unavailable-feature censoring.
- Raw output has no mode column. Mode and preset are checked in the actual diagnostic schema and run signature, not fabricated raw fields.

Independent review approved the final source-free patch. Main reran the focused suite: 28 passed. The same combined affected-suite command above now reports **141 passed, 143 subtests passed** in 1.71 seconds. These are Python validation tests, not new profitable backtests or MQL behavioral fixture passes.

Main also applied the strict updated read-only loader to both actual accepted R4 controls. Their existing native records reconciled: preset0 has 351 positions and net $54.85, preset1 has 156 positions and net $98.82 over development only. This is old evidence revalidation, not a new native replay, whole-ten-month profit, or release approval. R5/R6 source and binary hashes and production V24 source and binary hashes remained unchanged. No VM, chart, position, account, collector, or Git history was modified.

Next meaningful strategy action remains the fixed R5 four-cell native batch, then R6 according to its protocol. It requires restoring the isolated local demo authorization above. Do not repeatedly generate more variants or report a profitable V25 merely to avoid acknowledging missing tester authentication.

## Qualification and deployment

Keep the frozen six-month development, two-month validation, two-month historical confirmation, and whole ten-month gates. Keep independent cost, execution-delay, and $70/no-stopout tests. Historical data already inspected is not genuinely unseen OOS. No sample-floor reduction, outcome-driven reselection, or cherry-picked deletion of losses is allowed.

Only after all applicable gates and independent review pass may a production package be named V25. Confirm the intended VM demo account and current positions before any replacement. The latest user authorized that qualified deployment, not deployment of a failed or untested candidate. Do not close positions manually or restart unrelated terminals.
