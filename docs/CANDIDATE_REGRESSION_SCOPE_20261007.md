# Regression scope and legacy test triage — 2026-10-07

## Summary

The main Python suite ran 313 tests: 38 failures and 7 errors (root-run result). Root attributes most failures to old EA tests resolving sources or compiler logs at the repository root after those artifacts were archived under `versions/`. This is not a clean global suite. No aliases or legacy-test edits made.

Candidate checks are separate: a targeted run of 56 R1–R4 source, integrity and mocked-runner tests passed; root reports 60 candidate-related checks passed overall. These Python checks cover source contracts and test harness behavior, not native backtests or profitability. Root reports R4 compiled clean; its isolated ablation is running, so no R4 outcomes are included here.

The additional V24/V25 subset has 46 tests, with 44 passing and 2 errors reported by root. Both errors trace to root-level V25 source expectations; matching files and compile logs exist under `versions/` and `versions/logs/`.

## Legacy path mismatch evidence

The old test modules form paths relative to the repository root. The archived EA source files remain under `versions/`; legacy compile logs remain under `versions/logs/`. Path existence was checked read-only.

| Legacy test | Expected root asset | Present archived asset |
|---|---|---|
| `test_v16_1_m1.py` | `QuantumTitan_v16_1_M1.mq5` | `versions/QuantumTitan_v16_1_M1.mq5` |
| `test_v16_2_telemetry.py` | `QuantumTitan_V16_2_TelemetryCollector.mq5` | `versions/QuantumTitan_V16_2_TelemetryCollector.mq5` |
| `test_v16_3_precision.py` | `QuantumTitan_v16_3_Precision.mq5` | `versions/QuantumTitan_v16_3_Precision.mq5` |
| `test_v16_56_profit_runner.py` | candidate and `QuantumTitan_v16_Velocity.mq5` | both sources under `versions/` |
| `test_v16_57_safety_hotfix.py` | source and `v16_57_compile.log` | source under `versions/`; log at `versions/logs/v16_57_compile.log` |
| `test_v16_59_r4_ea.py` | `QuantumTitan_v16_59_R4StateTransition.mq5` | `versions/QuantumTitan_v16_59_R4StateTransition.mq5` |
| `test_v16_tick_path_collector.py` | source and `v16_tick_compile.log` | source under `versions/`; log at `versions/logs/v16_tick_compile.log` |
| `test_v22_swing.py` | source and EX5; optional `compile_v22.log` | source/EX5 under `versions/`; log at `versions/logs/compile_v22.log` |
| `test_v221_precision_contract.py` | `QuantumTitan_v22_1_Precision.mq5` | `versions/QuantumTitan_v22_1_Precision.mq5` |
| `test_v25_forensics.py` | `QuantumTitan_v25_EvidenceFirst.mq5`, `V25_ContractProbe.mq5` | both under `versions/`; logs under `versions/logs/` |

The V16.57 and tick-path tests directly read root compiler logs. The V22 swing test requires a root source and EX5; its compile-log check is conditional on root log existence, so that missing optional log alone is not a failure. V16 telemetry data referenced by replay tests exists at `data/V16TickTelemetry_XAUUSD_M1_20260914.csv`; those data-dependent tests are not explained by the source-location mismatch.

## Reading the result correctly

The 38 failures and 7 errors are the supplied full-suite totals; no broad suite rerun or per-test failure transcript was available for independent classification. The path inventory confirms a cluster of stale root-path assumptions, but it does not prove every global failure has that cause. In particular, tests that reach source assertions may also fail because of historical contract drift, and data-backed tests need separate diagnosis.

Use the candidate-focused pass as evidence only for the R1–R4 Python contracts and mocked runner logic. Use the parent-reported R4 clean compile as compile evidence. Keep global legacy-suite status red until its failures receive a failure-by-failure disposition. Archived originals remain under `versions/`; no root aliases or restorations were made.
