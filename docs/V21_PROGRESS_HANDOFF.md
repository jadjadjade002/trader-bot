# V21 Progress and V16 Diagnostic Handoff Note

**Date**: 2026-09-11  
**Author**: Data/Research Engineer  
**Status**: Read-Only Audit & Progress Infrastructure Completed  

> [!IMPORTANT]
> **Dataset Classification**: The data in `data/v21_live/` and `deploy/v16_20260910_mql5.log` evaluated below is a **LOCAL STATIC SNAPSHOT** (frozen as of 2026-09-10 06:16 broker time). It is **NOT** the live runtime stream on the VM. Live collection on VM continues independently.

---

## 1. Commands Used

```powershell
# Progress Report on local snapshot
python research/v21_progress_report.py data/v21_live

# V16 Diagnostic Report on local expert log
python research/v16_diagnostic_report.py deploy/v16_20260910_mql5.log

# Run full unit test suite
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 2. Input Datasets & Provenance (Local Snapshot)

### V21 QTForward Files (`data/v21_live/`)
- `QTForward_XAUUSD_M1_20260909.csv`: 155 data rows, SHA256: `9bc0b64d4204ff388e63a34a36f643e26bb5b51ae16538350aa829c9df3a55dc`
- `QTForward_XAUUSD_M1_20260910.csv`: 317 data rows, SHA256: `78bb156c703b41dbf1c4992569e5d4cb077eeef04374b7c1ea598ee73295c52c`
- `QTForward_health_20260909.csv`: 44 rows, SHA256: `e06c74fb5f4460506ba50a80e0db12f60570b555fa33923c5095d36e2ccbeee2`
- `QTForward_health_20260910.csv`: 75 rows, SHA256: `4a9b5f3964ffdf501dfad20a1ceb10c598c4d293818e59ea2633ca07925dfc7c`

### V16 Diagnostic Log (`deploy/v16_20260910_mql5.log`)
- Format: UTF-16-LE with BOM, 87 non-empty lines, window `00:00:03.301` to `01:27:58.669`.

---

## 3. Summary Metrics

### V21 Acquisition Progress (Local Snapshot)
- **Total Valid Bars**: 472 / 1,000 (47.2%, remaining: 528 rows)
- **Broker Sessions**: 1 / 15 (6.7%, remaining: 14 sessions)
  - Session date `2026-09-09`: 472 rows (span `2026-09-09 20:25` to `2026-09-10 06:16` belongs to single session under 18:00 cutoff)
- **Quality & Header Validation**:
  - `EXPECTED_BAR_HEADER` exact match: Verified
  - `EXPECTED_HEALTH_HEADER` exact match: Verified
  - `malformed_rows`: 0
  - `invalid_ohlc`: 0
  - `duplicates`: 0
  - `non_monotonic`: 0
  - `quality_ok`: 469 / 472
  - `write_errors`: 0
  - `duplicate_skips`: 0
  - `gap_count`: 120 (rollover closure between 22:59 and 01:00)
  - `latest_health_status`: `HEALTHY` (epoch `1789020865` / `2026-09-10T06:14:25`)
  - `bar_health_lag`: 180s (within allowed 360s limit)

### V16 Execution Diagnostics
- **QuantumTitan_v16_Velocity**:
  - 13 BUY scalp opens, 12 breakeven locks, 14 closed deals.
  - Deals with explicit PnL: 0
  - `explicit_pnl_sum`: `null` (deal notices omit dollar values; unknown PnL is NOT represented as 0.0).
  - `explicit_log_pnl_only`: `true`
- **QuantumTitan_v16_Apex**:
  - 1 grid order, 15 trailing steps, 3 closed deals with explicit Net PnL.
  - Deals with explicit PnL: 3
  - Explicit closed PnL in log: +$1.50, -$4.16, +$3.65 (Sum = +$0.99).
- **Account Balance & Net PnL**: UNKNOWN (cannot be inferred from log snippet without broker history statement).

---

## 4. Gate Status

- **Acquisition Gate**: `COLLECTING`
  - Reason: Data quality is clean, timestamps monotonic, exact headers match, but acquisition targets are incomplete (472/1000 bars, 1/15 sessions).
- **Deployment Gate**: `BLOCKED` (Promotion: `false`)
  - Reason: Mandatory policy; acquisition monitoring cannot approve live execution or EA promotion.

---

## 5. Security & Safety Compliance

- No modifications to EA source (`.mq5`) or compiled binaries (`.ex5`).
- No modifications to MT5, VM processes, or network connections.
- Protected accounts `112468807` and `112334471` untouched.
- Input CSV files in `data/v21_live/` strictly read-only.
- No Git commit or push executed.

---

## 6. Files Changed / Created

- `research/v21_progress_report.py` (Exact header enforcement, strict health field parser, 360s lag rule, non-monotonic blocking, finite check for all numeric bar fields)
- `research/v16_diagnostic_report.py` (UTF-16-LE parser, null representation for missing explicit PnL)
- `tests/test_v21_progress_report.py` (Tests for missing/extra headers, malformed fields, lag bounds, non-monotonic timestamps, non-finite numeric bar fields)
- `tests/test_v16_diagnostic_report.py` (Tests for UTF-16, null PnL representation)
- `docs/OPENCODE_V21_PROGRESS_PROMPT.md` (Patched prompt specification)
- `docs/V21_PROGRESS_HANDOFF.md` (Handoff report)

---

## 7. Test Results

Command:
`python -m unittest discover -s tests -p "test_*.py" -v`

Result:
**Ran 79 tests in 0.449s - OK**
