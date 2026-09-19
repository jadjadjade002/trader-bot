"""Daily markdown report for V21 forward collector.

Reads real collected files from a given QTForward directory and calls
existing audit/whipsaw/decision code where possible.

Usage:
    python research/v21_daily_report.py <collector-directory>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from research.v21_dataset_audit import HEADER, AuditError, audit
from research.v21_whipsaw import ObservedBar, eligible_probe, wilder_atr14, analyze as whipsaw_analyze
from research.v21_decision import decision


def _source_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("QTForward_XAUUSD_M1_*.csv"))


def _health_file(directory: Path) -> Path | None:
    matches = list(directory.glob("QTForward_health_*.csv"))
    return matches[0] if matches else None


def _parse_health_rows(path: Path) -> dict | None:
    """Parse health CSV: returns last row dict or None."""
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                return None
            return rows[-1]
    except Exception:
        return None


def _broker_dates_from_bars(directories: list[Path]) -> dict[date, int]:
    """Count rows per broker date."""
    counts: dict[date, int] = Counter()
    for directory in directories:
        for path in _source_files(directory):
            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        from datetime import datetime as _dt
                        moment = _dt.fromisoformat(row["time_broker_iso"])
                        counts[_session_day(moment)] += 1
                    except Exception:
                        pass
    return counts


def _session_day(moment: datetime) -> date:
    """Broker session 18:00..01:56 belongs to the date on which it starts."""
    return moment.date() if moment.hour >= 18 else (moment - timedelta(days=1)).date()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="QTForward collector directory")
    args = parser.parse_args()

    directory: Path = args.directory
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        return 1

    files = _source_files(directory)
    run_id = "FWD_20260909_4W"

    # Audit integrity
    try:
        audit_info = audit([directory])
        rows = audit_info["rows"]
        gap_count = audit_info["nonconsecutive_intervals"]
        non_ok = audit_info["non_ok_flag_rows"]
        integrity_status = "OK"
    except AuditError as e:
        rows = 0
        gap_count = "?"
        non_ok = "?"
        integrity_status = "AUDIT_ERROR"
        print(f"Audit error: {e}", file=sys.stderr)

    # Health file summary
    health = _health_file(directory)
    health_summary = None
    if health is not None:
        hrow = _parse_health_rows(health)
        if hrow is not None:
            health_summary = {
                "status": hrow.get("status", "UNKNOWN"),
                "terminal_connected": hrow.get("terminal_connected", "?"),
                "symbol_synchronized": hrow.get("symbol_synchronized", "?"),
                "write_errors": hrow.get("write_errors", "?"),
                "duplicate_skips": hrow.get("duplicate_skips", "?"),
                "gap_count": hrow.get("gap_count", "?"),
            }

    # Decision
    try:
        dec = decision([directory])
        decision_status = dec["status"]
        promotion = dec.get("promotion", False)
        gates = dec.get("gates", {})
    except Exception as e:
        dec = {}
        decision_status = f"DECISION_ERROR: {e}"
        promotion = False
        gates = {}

    # Row counts by date
    date_counts = _broker_dates_from_bars([directory])

    # Build markdown
    lines: list[str] = []

    # Run ID & timestamp
    # Find latest broker timestamp from bars
    latest_ts: str | None = None
    for path in files:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    from datetime import datetime as _dt
                    moment = _dt.fromisoformat(row["time_broker_iso"])
                    if latest_ts is None or moment > _dt.fromisoformat(latest_ts):
                        latest_ts = row["time_broker_iso"]
                except Exception:
                    pass

    lines.append(f"# V21 Daily Report")
    lines.append(f"**Run ID**: `{run_id}`")
    lines.append(f"**Latest broker timestamp**: `{latest_ts or 'N/A'}`")
    lines.append("")

    # Row counts by date
    lines.append("## Row counts by broker date")
    if date_counts:
        for d in sorted(date_counts.keys()):
            lines.append(f"- {d.isoformat()}: {date_counts[d]} rows")
    else:
        lines.append("- No bar data found")
    lines.append("")

    # Health summary
    if health_summary is not None:
        lines.append("## Health summary")
        hs = health_summary
        lines.append(f"- **status**: `{hs['status']}`")
        lines.append(f"- **terminal_connected**: `{hs['terminal_connected']}`")
        lines.append(f"- **symbol_synchronized**: `{hs['symbol_synchronized']}`")
        lines.append(f"- **write_errors**: `{hs['write_errors']}`")
        lines.append(f"- **duplicate_skips**: `{hs['duplicate_skips']}`")
        lines.append(f"- **gap_count**: `{hs['gap_count']}`")
        lines.append("")

    # Decision
    lines.append("## Decision status")
    lines.append(f"- **status**: `{decision_status}`")
    lines.append(f"- **promotion**: `{promotion}`")
    if isinstance(gates, dict):
        failed_gates = [k for k, v in gates.items() if v is False]
        if failed_gates:
            lines.append(f"- **failed gates**: {', '.join(failed_gates)}")
        else:
            lines.append("- **all gates passed** (or not applicable)")
    lines.append("")

    # Next action
    lines.append("## Next action")
    if decision_status == "INCONCLUSIVE_ACQUISITION_INCOMPLETE":
        lines.append("- Continue collector operation; acquire more broker-session dates and valid probes")
    elif decision_status == "FAIL_FROZEN_HYPOTHESIS":
        lines.append("- Hypothesis failed; do not retune. Document and move to offline notes.")
    elif decision_status == "PASS_SEPARATE_EXECUTION_EXPERIMENT_REQUIRES_AUTHORIZATION":
        lines.append("- Observational pass: separately authorized experiment on separate stream required")
    else:
        lines.append("- Review decision status above")

    # Write output to stdout (markdown)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
