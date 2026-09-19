# QuantumTitan codebase status

This document is the current engineering map. It is more reliable than the
legacy README and historical audit documents, which describe older versions.

## Active source paths

- `QuantumTitan_v16_Apex.mq5` is the multi-timeframe Apex EA. It uses
  `AlphaScoring.mqh`, `TrailingSafety.mqh`, `DynamicGrid.mqh`, and
  `TelemetryHUD.mqh`.
- `QuantumTitan_v16_Velocity.mq5` is the standalone M1 Velocity EA.
- `QuantumTitan_v17.mq5` is the single-position XAUUSD M1 research candidate.
  It uses the pure closed-bar signal module `V17Signal.mqh` and is the only
  candidate with a reproducible native-tester runner.

## Historical source warning

Versions v9 through v15 import mutable shared headers. Recompiling one of
those historical source files today can produce a binary that differs from the
original. Historical reports and `AUDIT_*.md` are not proof of the behavior of
the current source.

## Current operational rule

Only the v17 build and test scripts are current:

1. `scripts/compile_v17.ps1` compiles and requires the compiler log to contain
   zero errors and zero warnings. It writes a SHA-256 build manifest.
2. `scripts/run_v17_test.ps1` runs the isolated local MT5 tester with real
   ticks, live trading disabled, cloud disabled, and every v17 input frozen in
   the generated set file.
3. `scripts/analyze_v17_report.py` reconciles native net PnL to complete,
   single-position round trips including commission, swap, and fees.

No script in this repository should be treated as permission to deploy to the
VM. Deployment requires a separately validated candidate and an explicit
request.

## Known non-current tooling

`scripts/compile.ps1` and `scripts/deploy.ps1` target legacy versions and are
not used for v17. `StressTest_500_Scenarios.py` is a synthetic Python model,
not an MT5 EA backtest. `docs/walkthrough.md` documents v5 only.
