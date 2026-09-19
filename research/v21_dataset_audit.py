"""Audit only genuinely forward, observed data for the preregistered v21 study.

This program deliberately has no trading logic, optimisation, or PnL calculation.
It refuses data outside the sealed FWD_20260909_4W acquisition window.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


RUN_ID = "FWD_20260909_4W"
SCHEMA_VERSION = "1"
COLLECTOR_VERSION = "2.00"
SYMBOL = "XAUUSD"
WINDOW_START = datetime(2026, 9, 9)
WINDOW_END = datetime(2026, 10, 7, 15)
HEADER = (
    "schema_version,collector_version,run_id,symbol,time_broker_epoch,"
    "time_broker_iso,open,high,low,close,tick_volume,real_volume,"
    "bar_spread_points,open_spread_points,open_bid,open_ask,"
    "open_tick_time_msc,close_observed_time_msc,flags"
).split(",")


class AuditError(ValueError):
    """The acquisition data cannot enter the v21 study."""


def _files(paths: Iterable[Path]) -> list[Path]:
    files = sorted({path for source in paths for path in source.glob("QTForward_XAUUSD_M1_*.csv")})
    if not files:
        raise AuditError("no forward bar files found")
    return files


def audit(paths: Iterable[Path]) -> dict[str, object]:
    """Return integrity facts, rejecting non-forward or malformed collector rows."""
    rows = 0
    prior_epoch: int | None = None
    gap_count = 0
    digest = hashlib.sha256()
    first: datetime | None = None
    last: datetime | None = None
    flagged_rows = 0
    for path in _files(paths):
        raw = path.read_bytes()
        digest.update(path.name.encode("utf-8") + b"\0" + raw)
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADER:
                raise AuditError(f"{path.name}: unexpected schema")
            for line, row in enumerate(reader, start=2):
                if list(row) != HEADER or any(row[key] is None or row[key] == "" for key in HEADER):
                    raise AuditError(f"{path.name}:{line}: incomplete row")
                if (row["schema_version"], row["collector_version"], row["run_id"], row["symbol"]) != (
                    SCHEMA_VERSION, COLLECTOR_VERSION, RUN_ID, SYMBOL
                ):
                    raise AuditError(f"{path.name}:{line}: wrong collector identity")
                try:
                    epoch = int(row["time_broker_epoch"])
                    moment = datetime.fromisoformat(row["time_broker_iso"])
                    values = [float(row[key]) for key in ("open", "high", "low", "close", "open_bid", "open_ask")]
                except ValueError as exc:
                    raise AuditError(f"{path.name}:{line}: invalid numeric or timestamp value") from exc
                if epoch % 60 != 0 or moment.second != 0:
                    raise AuditError(f"{path.name}:{line}: bar timestamp is not M1-aligned")
                if not WINDOW_START <= moment < WINDOW_END:
                    raise AuditError(f"{path.name}:{line}: outside sealed forward window")
                if not (values[0] <= values[1] and values[2] <= values[0] and values[2] <= values[3] <= values[1]):
                    raise AuditError(f"{path.name}:{line}: invalid OHLC")
                if values[4] <= 0.0 or values[5] < values[4]:
                    raise AuditError(f"{path.name}:{line}: invalid observed quote")
                if prior_epoch is not None:
                    if epoch <= prior_epoch:
                        raise AuditError(f"{path.name}:{line}: duplicate or unordered timestamp")
                    if epoch - prior_epoch != 60:
                        gap_count += 1
                prior_epoch = epoch
                first = moment if first is None else first
                last = moment
                flagged_rows += int(row["flags"] != "OK")
                rows += 1
    return {
        "schema_version": 1,
        "study": "v21_forward_observational_research",
        "status": "integrity_only_no_outcome_analysis",
        "run_id": RUN_ID,
        "rows": rows,
        "first_broker_time": first.isoformat() if first else None,
        "last_broker_time": last.isoformat() if last else None,
        "nonconsecutive_intervals": gap_count,
        "non_ok_flag_rows": flagged_rows,
        "input_sha256": digest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="+", help="directories containing collector CSV files")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
