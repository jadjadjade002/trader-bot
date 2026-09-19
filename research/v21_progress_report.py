"""V21 Progress Report CLI and Library.

Audits QTForward collector files, tracks acquisition progress against
1,000 bars and 15 broker sessions targets, and evaluates acquisition gate.
Deployment gate is ALWAYS BLOCKED in this report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

TARGET_ROWS: int = 1000
TARGET_SESSIONS: int = 15
HEALTH_INTERVAL_SECONDS: int = 300
ALLOWED_HEALTH_LAG_SECONDS: int = 360

EXPECTED_BAR_HEADER = [
    "schema_version",
    "collector_version",
    "run_id",
    "symbol",
    "time_broker_epoch",
    "time_broker_iso",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "real_volume",
    "bar_spread_points",
    "open_spread_points",
    "open_bid",
    "open_ask",
    "open_tick_time_msc",
    "close_observed_time_msc",
    "flags",
]

EXPECTED_HEALTH_HEADER = [
    "schema_version",
    "collector_version",
    "run_id",
    "broker_time_epoch",
    "broker_time_iso",
    "terminal_connected",
    "symbol_synchronized",
    "last_tick_age_seconds",
    "last_closed_bar_epoch",
    "rows_written",
    "duplicate_skips",
    "gap_count",
    "write_errors",
    "status",
]


def session_date_from_dt(moment: datetime) -> date:
    """Session date based on 18:00 cutoff.
    18:00..23:59 belongs to same date.
    00:00..17:59 belongs to previous date.
    """
    if moment.hour >= 18:
        return moment.date()
    return (moment - timedelta(days=1)).date()


def session_date_from_iso(iso_str: str) -> date:
    clean = iso_str.strip().replace(" ", "T")
    moment = datetime.fromisoformat(clean)
    return session_date_from_dt(moment)


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class HealthRow:
    schema_version: str
    collector_version: str
    run_id: str
    broker_time_epoch: int
    broker_time_iso: str
    terminal_connected: int
    symbol_synchronized: int
    last_tick_age_seconds: int
    last_closed_bar_epoch: int
    rows_written: int
    duplicate_skips: int
    gap_count: int
    write_errors: int
    status: str
    source_file: str
    row_index: int


@dataclass
class BarAggregation:
    source_files: List[str] = field(default_factory=list)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    valid_rows: int = 0
    malformed_rows: int = 0
    invalid_ohlc_rows: int = 0
    duplicate_rows: int = 0
    quality_ok: int = 0
    flags_breakdown: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    run_ids: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    schema_versions: List[str] = field(default_factory=list)
    collector_versions: List[str] = field(default_factory=list)
    first_broker_timestamp: Optional[str] = None
    latest_broker_timestamp: Optional[str] = None
    first_bar_epoch: Optional[int] = None
    latest_bar_epoch: Optional[int] = None
    session_dates: List[str] = field(default_factory=list)
    rows_by_session: Dict[str, int] = field(default_factory=dict)
    non_monotonic_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)


def discover_bar_files(directory: Path) -> List[Path]:
    return sorted(directory.glob("QTForward_XAUUSD_M1_*.csv"))


def discover_health_files(directory: Path) -> List[Path]:
    return sorted(directory.glob("QTForward_health_*.csv"))


def _parse_health_int(r: Dict[str, Any], field: str) -> int:
    val = r.get(field)
    if val is None:
        raise ValueError(f"Missing required health field: {field}")
    s = str(val).strip()
    if not s:
        raise ValueError(f"Empty required health field: {field}")
    if s.lower() in ("nan", "inf", "-inf", "+inf"):
        raise ValueError(f"Invalid non-finite numeric value '{s}' for field: {field}")
    try:
        f = float(s)
        if not f.is_integer() or f != f:
            raise ValueError(f"Value '{s}' is not integer for field: {field}")
        return int(f)
    except ValueError:
        raise ValueError(f"Cannot parse '{s}' as integer for field: {field}")


def _parse_health_str(r: Dict[str, Any], field: str) -> str:
    val = r.get(field)
    if val is None:
        raise ValueError(f"Missing required health field: {field}")
    s = str(val).strip()
    if not s:
        raise ValueError(f"Empty required health field: {field}")
    return s


def parse_health_files(files: List[Path]) -> Tuple[List[HealthRow], List[Dict[str, Any]]]:
    rows: List[HealthRow] = []
    errors: List[Dict[str, Any]] = []

    for f in files:
        try:
            with f.open("r", encoding="utf-8", errors="replace") as fp:
                reader = csv.DictReader(fp)
                if not reader.fieldnames:
                    errors.append({"code": "EMPTY_HEALTH_FILE", "file": f.name})
                    continue
                if list(reader.fieldnames) != EXPECTED_HEALTH_HEADER:
                    errors.append({
                        "code": "BAD_HEADER",
                        "file": f.name,
                        "expected": EXPECTED_HEALTH_HEADER,
                        "actual": list(reader.fieldnames),
                    })
                    continue

                for idx, r in enumerate(reader, start=2):
                    try:
                        h = HealthRow(
                            schema_version=_parse_health_str(r, "schema_version"),
                            collector_version=_parse_health_str(r, "collector_version"),
                            run_id=_parse_health_str(r, "run_id"),
                            broker_time_epoch=_parse_health_int(r, "broker_time_epoch"),
                            broker_time_iso=_parse_health_str(r, "broker_time_iso"),
                            terminal_connected=_parse_health_int(r, "terminal_connected"),
                            symbol_synchronized=_parse_health_int(r, "symbol_synchronized"),
                            last_tick_age_seconds=_parse_health_int(r, "last_tick_age_seconds"),
                            last_closed_bar_epoch=_parse_health_int(r, "last_closed_bar_epoch"),
                            rows_written=_parse_health_int(r, "rows_written"),
                            duplicate_skips=_parse_health_int(r, "duplicate_skips"),
                            gap_count=_parse_health_int(r, "gap_count"),
                            write_errors=_parse_health_int(r, "write_errors"),
                            status=_parse_health_str(r, "status"),
                            source_file=f.name,
                            row_index=idx,
                        )
                        rows.append(h)
                    except Exception as ex:
                        errors.append({
                            "code": "HEALTH_PARSE_ERROR",
                            "file": f.name,
                            "row": idx,
                            "error": str(ex),
                        })
        except Exception as ex:
            errors.append({"code": "HEALTH_FILE_READ_ERROR", "file": f.name, "error": str(ex)})

    return rows, errors


def select_latest_health(rows: List[HealthRow]) -> Optional[HealthRow]:
    if not rows:
        return None
    return max(rows, key=lambda r: r.broker_time_epoch)


def select_data_quality_health(rows: List[HealthRow]) -> Optional[HealthRow]:
    """Newest heartbeat tied to an observed closed bar.

    Weekend/holiday MARKET_IDLE rows intentionally reset last_closed_bar_epoch
    and counters to zero after a terminal restart. They describe current
    liveness, not integrity of the latest collected bar file.
    """
    with_bars = [row for row in rows if row.last_closed_bar_epoch > 0]
    if not with_bars:
        return select_latest_health(rows)
    latest_bar = max(row.last_closed_bar_epoch for row in with_bars)
    same_bar = [row for row in with_bars if row.last_closed_bar_epoch == latest_bar]
    integrity_failures = [row for row in same_bar if row.write_errors > 0 or row.duplicate_skips > 0]
    if integrity_failures:
        return max(integrity_failures, key=lambda row: row.broker_time_epoch)
    healthy = [row for row in same_bar if row.status.upper() == "HEALTHY"]
    if healthy:
        return max(healthy, key=lambda row: row.broker_time_epoch)
    liveness_only = {"MARKET_IDLE", "STALE_TICKS", "UNSYNCHRONIZED"}
    active = [row for row in same_bar if row.status.upper() not in liveness_only]
    return max(active, key=lambda row: row.broker_time_epoch) if active else max(same_bar, key=lambda row: row.broker_time_epoch)


def aggregate_bars(files: List[Path], compute_hashes: bool = True) -> BarAggregation:
    agg = BarAggregation()
    seen_keys: Set[Tuple[str, int]] = set()
    run_id_set: Set[str] = set()
    symbol_set: Set[str] = set()
    schema_set: Set[str] = set()
    collector_set: Set[str] = set()
    session_counts: Dict[str, int] = defaultdict(int)

    last_epoch: Optional[int] = None

    for f in files:
        agg.source_files.append(f.name)
        if compute_hashes:
            try:
                agg.file_hashes[f.name] = compute_file_sha256(f)
            except Exception as e:
                agg.warnings.append({"code": "HASH_FAILED", "file": f.name, "error": str(e)})

        try:
            with f.open("r", encoding="utf-8", errors="replace") as fp:
                reader = csv.DictReader(fp)
                if not reader.fieldnames:
                    agg.errors.append({"code": "EMPTY_BAR_FILE", "file": f.name})
                    continue
                if list(reader.fieldnames) != EXPECTED_BAR_HEADER:
                    agg.errors.append({
                        "code": "BAD_HEADER",
                        "file": f.name,
                        "expected": EXPECTED_BAR_HEADER,
                        "actual": list(reader.fieldnames),
                    })
                    continue

                for line_idx, r in enumerate(reader, start=2):
                    if not r or any(k not in r or r[k] is None for k in EXPECTED_BAR_HEADER):
                        agg.malformed_rows += 1
                        continue

                    try:
                        symbol = r["symbol"].strip()
                        if not symbol:
                            raise ValueError("empty symbol")

                        epoch_f = float(r["time_broker_epoch"].strip())
                        if not math.isfinite(epoch_f) or not epoch_f.is_integer():
                            raise ValueError("non-finite or non-integer epoch")
                        epoch = int(epoch_f)

                        iso_ts = r["time_broker_iso"].strip()
                        if not iso_ts:
                            raise ValueError("empty time_broker_iso")

                        o = float(r["open"].strip())
                        h = float(r["high"].strip())
                        l = float(r["low"].strip())
                        c = float(r["close"].strip())
                        if not (math.isfinite(o) and math.isfinite(h) and math.isfinite(l) and math.isfinite(c)):
                            agg.invalid_ohlc_rows += 1
                            continue

                        flags = r["flags"].strip()
                        if not flags:
                            raise ValueError("empty flags")

                        run_id = r["run_id"].strip()
                        if not run_id:
                            raise ValueError("empty run_id")

                        schema_ver = r["schema_version"].strip()
                        if not schema_ver:
                            raise ValueError("empty schema_version")

                        coll_ver = r["collector_version"].strip()
                        if not coll_ver:
                            raise ValueError("empty collector_version")

                        # Validate all other numeric fields using math.isfinite()
                        tv = float(r["tick_volume"].strip())
                        rv = float(r["real_volume"].strip())
                        b_sp = float(r["bar_spread_points"].strip())
                        o_sp = float(r["open_spread_points"].strip())
                        ob = float(r["open_bid"].strip())
                        oa = float(r["open_ask"].strip())
                        ot = float(r["open_tick_time_msc"].strip())
                        ct = float(r["close_observed_time_msc"].strip())

                        if not all(math.isfinite(x) for x in (tv, rv, b_sp, o_sp, ob, oa, ot, ct)):
                            agg.malformed_rows += 1
                            continue

                        if not (tv.is_integer() and rv.is_integer() and ot.is_integer() and ct.is_integer()):
                            agg.malformed_rows += 1
                            continue
                    except Exception:
                        agg.malformed_rows += 1
                        continue

                    # OHLC validity
                    if not (h >= max(o, c) and l <= min(o, c) and l <= h and o > 0 and c > 0):
                        agg.invalid_ohlc_rows += 1
                        continue

                    # Duplicate check
                    key = (symbol, epoch)
                    if key in seen_keys:
                        agg.duplicate_rows += 1
                        continue
                    seen_keys.add(key)

                    # Monotonic check
                    if last_epoch is not None and epoch <= last_epoch:
                        agg.non_monotonic_count += 1
                    last_epoch = epoch

                    # Valid bar confirmed
                    agg.valid_rows += 1
                    if flags == "OK":
                        agg.quality_ok += 1
                    agg.flags_breakdown[flags] += 1

                    run_id_set.add(run_id)
                    symbol_set.add(symbol)
                    schema_set.add(schema_ver)
                    collector_set.add(coll_ver)

                    # Timestamp range
                    if agg.first_bar_epoch is None or epoch < agg.first_bar_epoch:
                        agg.first_bar_epoch = epoch
                        agg.first_broker_timestamp = iso_ts
                    if agg.latest_bar_epoch is None or epoch > agg.latest_bar_epoch:
                        agg.latest_bar_epoch = epoch
                        agg.latest_broker_timestamp = iso_ts

                    # Session counting
                    try:
                        s_date = session_date_from_iso(iso_ts).isoformat()
                        session_counts[s_date] += 1
                    except Exception:
                        pass

        except Exception as ex:
            agg.errors.append({"code": "BAR_FILE_READ_ERROR", "file": f.name, "error": str(ex)})

    agg.run_ids = sorted(run_id_set)
    agg.symbols = sorted(symbol_set)
    agg.schema_versions = sorted(schema_set)
    agg.collector_versions = sorted(collector_set)
    agg.session_dates = sorted(session_counts.keys())
    agg.rows_by_session = dict(sorted(session_counts.items()))

    if len(agg.run_ids) > 1:
        agg.warnings.append({"code": "MULTIPLE_RUN_IDS", "values": agg.run_ids})
    for sym in agg.symbols:
        if sym != "XAUUSD":
            agg.warnings.append({"code": "UNEXPECTED_SYMBOL", "symbol": sym})

    return agg


def evaluate_acquisition_gate(
    bar_agg: BarAggregation,
    latest_health: Optional[HealthRow],
    health_errors: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Evaluates acquisition gate status.
    Precedence:
    1. NO_DATA (only when no files or completely empty files)
    2. DATA_QUALITY_BLOCKED (when invalid/malformed rows, health unhealthy, write_errors, lag exceeded)
    3. COLLECTING
    4. READY_FOR_REVIEW
    """
    # Check bad headers or health parse errors first
    bad_headers = [e for e in (bar_agg.errors + health_errors) if e.get("code") == "BAD_HEADER"]
    health_parse_errs = [e for e in health_errors if e.get("code") == "HEALTH_PARSE_ERROR"]

    if bad_headers or health_parse_errs:
        reasons = []
        if bad_headers:
            reasons.append(f"bad_headers_count={len(bad_headers)}")
        if health_parse_errs:
            reasons.append(f"health_parse_errors_count={len(health_parse_errs)}")
        return "DATA_QUALITY_BLOCKED", reasons

    # Any corruption, invalid OHLC, or non-monotonic timestamps block the gate
    if bar_agg.malformed_rows > 0 or bar_agg.invalid_ohlc_rows > 0 or bar_agg.non_monotonic_count > 0:
        reasons = []
        if bar_agg.malformed_rows > 0:
            reasons.append(f"malformed_rows={bar_agg.malformed_rows}")
        if bar_agg.invalid_ohlc_rows > 0:
            reasons.append(f"invalid_ohlc_rows={bar_agg.invalid_ohlc_rows}")
        if bar_agg.non_monotonic_count > 0:
            reasons.append("non_monotonic_timestamp")
        return "DATA_QUALITY_BLOCKED", reasons

    if bar_agg.valid_rows == 0:
        return "NO_DATA", ["No valid bar rows found"]

    reasons: List[str] = []

    # Check health block conditions
    if latest_health is None:
        reasons.append("missing_health_data")
    else:
        if latest_health.status.upper() != "HEALTHY":
            reasons.append(f"latest_health_status={latest_health.status}")
        if latest_health.write_errors > 0:
            reasons.append(f"write_errors={latest_health.write_errors}")
        if latest_health.duplicate_skips > 0:
            reasons.append(f"duplicate_skips={latest_health.duplicate_skips}")

        # Check heartbeat lag
        if bar_agg.latest_bar_epoch is not None:
            lag = bar_agg.latest_bar_epoch - latest_health.last_closed_bar_epoch
            if lag > ALLOWED_HEALTH_LAG_SECONDS:
                reasons.append(f"heartbeat_lag_exceeded={lag}s_over_{ALLOWED_HEALTH_LAG_SECONDS}s")

    if reasons:
        return "DATA_QUALITY_BLOCKED", reasons

    # Check target progress
    sessions_count = len(bar_agg.session_dates)
    if bar_agg.valid_rows < TARGET_ROWS or sessions_count < TARGET_SESSIONS:
        missing = []
        if bar_agg.valid_rows < TARGET_ROWS:
            missing.append(f"rows={bar_agg.valid_rows}/{TARGET_ROWS}")
        if sessions_count < TARGET_SESSIONS:
            missing.append(f"sessions={sessions_count}/{TARGET_SESSIONS}")
        return "COLLECTING", [f"Acquisition in progress: {', '.join(missing)}"]

    return "READY_FOR_REVIEW", ["All acquisition targets and quality checks passed"]


def build_full_report(directory: Path, compute_hashes: bool = True) -> Dict[str, Any]:
    bar_files = discover_bar_files(directory)
    health_files = discover_health_files(directory)

    bar_agg = aggregate_bars(bar_files, compute_hashes=compute_hashes)
    health_rows, health_errors = parse_health_files(health_files)
    latest_h = select_latest_health(health_rows)
    quality_h = select_data_quality_health(health_rows)

    # Calculate lag
    lag_seconds: Optional[int] = None
    if bar_agg.latest_bar_epoch is not None and quality_h is not None:
        lag_seconds = bar_agg.latest_bar_epoch - quality_h.last_closed_bar_epoch
        if lag_seconds > ALLOWED_HEALTH_LAG_SECONDS:
            bar_agg.errors.append({
                "code": "HEALTH_BAR_LAG_EXCEEDED",
                "lag_seconds": lag_seconds,
                "limit": ALLOWED_HEALTH_LAG_SECONDS,
            })
        elif lag_seconds > 0:
            bar_agg.warnings.append({
                "code": "HEALTH_HEARTBEAT_LAG",
                "lag_seconds": lag_seconds,
                "note": "Normal async lag between 60s bar and 300s heartbeat",
            })

    acq_status, acq_reasons = evaluate_acquisition_gate(bar_agg, quality_h, health_errors)

    sessions_count = len(bar_agg.session_dates)
    rows_remaining = max(TARGET_ROWS - bar_agg.valid_rows, 0)
    sessions_remaining = max(TARGET_SESSIONS - sessions_count, 0)
    rows_pct = min((bar_agg.valid_rows / TARGET_ROWS) * 100.0, 100.0) if TARGET_ROWS else 100.0
    sessions_pct = min((sessions_count / TARGET_SESSIONS) * 100.0, 100.0) if TARGET_SESSIONS else 100.0

    health_dict: Optional[Dict[str, Any]] = None
    if latest_h is not None:
        health_dict = {
            "status": latest_h.status,
            "terminal_connected": latest_h.terminal_connected,
            "symbol_synchronized": latest_h.symbol_synchronized,
            "write_errors": latest_h.write_errors,
            "duplicate_skips": latest_h.duplicate_skips,
            "gap_count": latest_h.gap_count,
            "rows_written": latest_h.rows_written,
            "broker_time_iso": latest_h.broker_time_iso,
            "broker_time_epoch": latest_h.broker_time_epoch,
            "last_closed_bar_epoch": latest_h.last_closed_bar_epoch,
            "source_file": latest_h.source_file,
            "data_quality_basis_status": quality_h.status if quality_h else None,
            "data_quality_basis_broker_time_iso": quality_h.broker_time_iso if quality_h else None,
            "data_quality_basis_last_closed_bar_epoch": quality_h.last_closed_bar_epoch if quality_h else None,
            "current_market_idle": latest_h.status.upper() == "MARKET_IDLE",
        }

    report = {
        "schema_version": "1",
        "study": "v21_forward_observational_research",
        "run_id": bar_agg.run_ids[0] if bar_agg.run_ids else "UNKNOWN",
        "run_ids": bar_agg.run_ids,
        "source_directory": str(directory),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reproducibility": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "file_hashes": bar_agg.file_hashes,
        },
        "files": {
            "bar_count": len(bar_files),
            "health_count": len(health_files),
            "bar_files": [f.name for f in bar_files],
            "health_files": [f.name for f in health_files],
        },
        "bars": {
            "valid": bar_agg.valid_rows,
            "malformed": bar_agg.malformed_rows,
            "invalid_ohlc": bar_agg.invalid_ohlc_rows,
            "duplicates": bar_agg.duplicate_rows,
            "non_monotonic": bar_agg.non_monotonic_count,
            "quality_ok": bar_agg.quality_ok,
            "flags_breakdown": dict(bar_agg.flags_breakdown),
            "symbols": bar_agg.symbols,
            "first_broker_timestamp": bar_agg.first_broker_timestamp,
            "latest_broker_timestamp": bar_agg.latest_broker_timestamp,
            "bar_health_lag_seconds": lag_seconds,
        },
        "sessions": {
            "count": sessions_count,
            "dates": bar_agg.session_dates,
            "rows_by_date": bar_agg.rows_by_session,
        },
        "health": health_dict,
        "acquisition_gate": {
            "status": acq_status,
            "rows_target": TARGET_ROWS,
            "rows_current": bar_agg.valid_rows,
            "rows_remaining": rows_remaining,
            "rows_progress_pct": round(rows_pct, 1),
            "sessions_target": TARGET_SESSIONS,
            "sessions_current": sessions_count,
            "sessions_remaining": sessions_remaining,
            "sessions_progress_pct": round(sessions_pct, 1),
            "reasons": acq_reasons,
        },
        "deployment_gate": {
            "status": "BLOCKED",
            "promotion": False,
            "reason": "Acquisition report only; does not validate hypothesis or execution safety",
        },
        "errors": bar_agg.errors + health_errors,
        "warnings": bar_agg.warnings,
    }
    return report


def render_text_report(rep: Dict[str, Any]) -> str:
    b = rep["bars"]
    s = rep["sessions"]
    h = rep["health"] or {}
    ag = rep["acquisition_gate"]
    dg = rep["deployment_gate"]

    lines = [
        "=" * 60,
        "V21 PROGRESS REPORT (ACQUISITION AUDIT)",
        "=" * 60,
        f"Run ID                 : {rep['run_id']}",
        f"Source Directory       : {rep['source_directory']}",
        f"Bar Files              : {rep['files']['bar_count']}",
        f"Health Files           : {rep['files']['health_count']}",
        f"First Broker Timestamp : {b['first_broker_timestamp']}",
        f"Latest Broker Timestamp: {b['latest_broker_timestamp']}",
        "",
        "--- BAR METRICS ---",
        f"Valid Bars             : {b['valid']} / {ag['rows_target']} ({ag['rows_progress_pct']}%)",
        f"Rows Remaining         : {ag['rows_remaining']}",
        f"Quality OK Flags       : {b['quality_ok']} / {b['valid']}",
        f"Malformed Rows         : {b['malformed']}",
        f"Invalid OHLC Rows      : {b['invalid_ohlc']}",
        f"Duplicate Rows         : {b['duplicates']}",
        f"Flags Breakdown        : {dict(b['flags_breakdown'])}",
        "",
        "--- SESSIONS METRICS ---",
        f"Distinct Sessions      : {s['count']} / {ag['sessions_target']} ({ag['sessions_progress_pct']}%)",
        f"Sessions Remaining     : {ag['sessions_remaining']}",
        f"Session Dates          : {s['dates']}",
        f"Rows by Session        : {s['rows_by_date']}",
        "",
        "--- HEALTH SUMMARY ---",
        f"Current Status         : {h.get('status', 'NONE')}",
        f"Data Quality Basis     : {h.get('data_quality_basis_status', 'N/A')} @ {h.get('data_quality_basis_broker_time_iso', 'N/A')}",
        f"Terminal Connected     : {h.get('terminal_connected', 'N/A')}",
        f"Symbol Synchronized    : {h.get('symbol_synchronized', 'N/A')}",
        f"Write Errors           : {h.get('write_errors', 'N/A')}",
        f"Duplicate Skips        : {h.get('duplicate_skips', 'N/A')}",
        f"Gap Count              : {h.get('gap_count', 'N/A')}",
        f"Rows Written Counter   : {h.get('rows_written', 'N/A')}",
        f"Bar vs Health Lag      : {b['bar_health_lag_seconds']}s (limit: {ALLOWED_HEALTH_LAG_SECONDS}s)",
        "",
        "--- GATE EVALUATION ---",
        f"Acquisition Gate Status: {ag['status']}",
        f"Acquisition Reasons    : {', '.join(ag['reasons'])}",
        f"Deployment Gate        : {dg['status']} (Promotion: {dg['promotion']})",
        f"Deployment Reason      : {dg['reason']}",
        "=" * 60,
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V21 Progress Report CLI")
    parser.add_argument("directory", type=Path, help="Directory containing QTForward collector CSVs")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", type=Path, default=None, help="Output destination file")
    parser.add_argument("--no-hashes", action="store_true", help="Skip calculating file SHA256")

    args = parser.parse_args(argv)

    directory: Path = args.directory
    if not directory.exists() or not directory.is_dir():
        print(f"Error: {directory} is not an existing directory", file=sys.stderr)
        return 1

    if args.output is not None:
        try:
            if args.output.resolve() == directory.resolve() or args.output.resolve() in directory.resolve().iterdir():
                print("Error: OUTPUT_INPUT_COLLISION - output path cannot collide with input directory", file=sys.stderr)
                return 1
        except Exception:
            pass

    report = build_full_report(directory, compute_hashes=not args.no_hashes)

    if args.format == "json":
        output_str = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        output_str = render_text_report(report)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_str, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
