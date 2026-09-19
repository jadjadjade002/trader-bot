"""V16 Diagnostic Report CLI and Library.

Parses MT5 expert log (specifically deploy/v16_20260910_mql5.log) in UTF-16-LE,
extracts Velocity and Apex trading events, and records explicit PnL numbers only.
Does NOT extrapolate account balance or unstated PnL.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_log_text(path: Path) -> str:
    """Reads log file with UTF-16 / UTF-16-LE handling (standard MT5 log format)."""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-16")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


@dataclass
class LogEvent:
    line_number: int
    raw_timestamp: str
    ea: str
    event_type: str
    symbol: str = "XAUUSD"
    timeframe: str = ""
    side: str = ""
    lot: Optional[float] = None
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    ticket: Optional[int] = None
    deal_id: Optional[int] = None
    pnl: Optional[float] = None
    pnl_explicit: bool = False
    message: str = ""


def parse_v16_log(content: str) -> Dict[str, Any]:
    lines = content.splitlines()

    events_by_ea: Dict[str, List[LogEvent]] = defaultdict(list)
    event_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    explicit_pnl_by_ea: Dict[str, List[float]] = defaultdict(list)
    raw_samples: Dict[str, List[str]] = defaultdict(list)

    first_ts: Optional[str] = None
    last_ts: Optional[str] = None

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        time_str = parts[2] if len(parts) > 2 else ""
        source_str = parts[3] if len(parts) > 3 else ""
        msg = parts[4] if len(parts) > 4 else line

        if time_str:
            if first_ts is None:
                first_ts = time_str
            last_ts = time_str

        # Classify EA
        if "QuantumTitan_v16_Velocity" in source_str or "Velocity" in msg:
            ea_name = "QuantumTitan_v16_Velocity"
        elif "QuantumTitan_v16_Apex" in source_str or "Apex" in msg:
            ea_name = "QuantumTitan_v16_Apex"
        else:
            ea_name = "Other"

        # Timeframe
        tf_match = re.search(r",([A-Z0-9]+)\)", source_str)
        tf = tf_match.group(1) if tf_match else ""

        # Event type classification
        evt = LogEvent(
            line_number=line_idx,
            raw_timestamp=time_str,
            ea=ea_name,
            event_type="UNKNOWN",
            timeframe=tf,
            message=msg,
        )

        if "SCALP OPENED" in msg:
            evt.event_type = "OPEN"
            side_m = re.search(r"\b(BUY|SELL)\b", msg)
            if side_m:
                evt.side = side_m.group(1)
            price_m = re.search(r"@\s*([\d\.]+)", msg)
            if price_m:
                evt.price = float(price_m.group(1))
            lot_m = re.search(r"Lot:\s*([\d\.]+)", msg)
            if lot_m:
                evt.lot = float(lot_m.group(1))
            sl_m = re.search(r"SL:\s*([\d\.]+)", msg)
            if sl_m:
                evt.sl = float(sl_m.group(1))
            tp_m = re.search(r"TP:\s*([\d\.]+)", msg)
            if tp_m:
                evt.tp = float(tp_m.group(1))

        elif "Grid #" in msg or "Executing" in msg and "Grid" in msg:
            evt.event_type = "GRID_OPEN"
            side_m = re.search(r"\b(BUY|SELL)\b", msg)
            if side_m:
                evt.side = side_m.group(1)
            price_m = re.search(r"(?:Mid|at):\s*([\d\.]+)", msg)
            if price_m:
                evt.price = float(price_m.group(1))
            lot_m = re.search(r"Lot:\s*([\d\.]+)", msg)
            if lot_m:
                evt.lot = float(lot_m.group(1))

        elif "DEAL CLOSED" in msg or "closed; cooldown" in msg:
            evt.event_type = "CLOSE"
            deal_m = re.search(r"#(\d+)", msg)
            if deal_m:
                evt.deal_id = int(deal_m.group(1))

            # Explicit PnL search
            pnl_m = re.search(r"Net PnL:\s*([+-]?\$?-?[\d\.]+)", msg)
            if pnl_m:
                raw_pnl = pnl_m.group(1).replace("$", "").replace("+", "")
                try:
                    val = float(raw_pnl)
                    evt.pnl = val
                    evt.pnl_explicit = True
                    explicit_pnl_by_ea[ea_name].append(val)
                except ValueError:
                    evt.pnl = None
            else:
                # Velocity notices have no PnL
                evt.pnl = None
                evt.pnl_explicit = False

        elif "BREAKEVEN LOCKED" in msg:
            evt.event_type = "BREAKEVEN"
            sl_m = re.search(r"SL set to\s*([\d\.]+)", msg)
            if sl_m:
                evt.sl = float(sl_m.group(1))

        elif "Trail SL" in msg or "TrailingSafety" in msg:
            evt.event_type = "TRAILING"

        elif "INITIALIZING" in msg or "Profile" in msg:
            evt.event_type = "INITIALIZING"

        elif "Deinitializing" in msg:
            evt.event_type = "DEINITIALIZING"

        elif "Error" in msg or "failed" in msg or "REJECT" in msg:
            evt.event_type = "ERROR_OR_REJECT"

        events_by_ea[ea_name].append(evt)
        event_counts[ea_name][evt.event_type] += 1

        if len(raw_samples[evt.event_type]) < 3:
            raw_samples[evt.event_type].append(f"Line {line_idx} [{time_str}]: {msg}")

    # Summaries
    ea_reports: Dict[str, Any] = {}
    for ea, evts in events_by_ea.items():
        if ea == "Other":
            continue
        counts = event_counts[ea]
        pnl_list = explicit_pnl_by_ea[ea]
        explicit_sum = round(sum(pnl_list), 2) if pnl_list else None

        ea_reports[ea] = {
            "evidence_level": {
                "events_count": "observed",
                "explicit_pnl_sum": "derived" if explicit_sum is not None else "unknown",
                "account_balance": "unknown",
                "total_strategy_pnl": "unknown" if ea == "QuantumTitan_v16_Velocity" else "derived_from_log_fragment",
            },
            "events_breakdown": dict(counts),
            "open_count": counts.get("OPEN", 0) + counts.get("GRID_OPEN", 0),
            "close_count": counts.get("CLOSE", 0),
            "breakeven_count": counts.get("BREAKEVEN", 0),
            "trailing_count": counts.get("TRAILING", 0),
            "init_deinit_count": counts.get("INITIALIZING", 0) + counts.get("DEINITIALIZING", 0),
            "error_count": counts.get("ERROR_OR_REJECT", 0),
            "explicit_pnl_deals_count": len(pnl_list),
            "explicit_pnl_values": pnl_list,
            "explicit_pnl_sum": explicit_sum,
            "explicit_log_pnl_only": True,
            "notes": (
                "Velocity log lines record deal numbers only without dollar profit."
                if ea == "QuantumTitan_v16_Velocity"
                else "Apex deals log explicit Net PnL."
            ),
        }

    all_pnl = [p for lst in explicit_pnl_by_ea.values() for p in lst]
    total_explicit_pnl = round(sum(all_pnl), 2) if all_pnl else None

    return {
        "schema_version": "1",
        "study": "v16_expert_log_diagnostic",
        "log_window": {
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "total_lines": len(lines),
        },
        "eas": ea_reports,
        "overall_summary": {
            "total_explicit_pnl": total_explicit_pnl,
            "explicit_log_pnl_only": True,
            "account_pnl_provenance": "unknown_requires_broker_history_statement",
            "winrate_provenance": "unknown_incomplete_pnl_and_unclosed_positions",
        },
        "sample_lines_by_event": dict(raw_samples),
    }


def render_diagnostic_text(rep: Dict[str, Any]) -> str:
    lines = [
        "=" * 60,
        "V16 DIAGNOSTIC REPORT (EXPERT LOG AUDIT)",
        "=" * 60,
        f"Log Window First Timestamp: {rep['log_window']['first_timestamp']}",
        f"Log Window Last Timestamp : {rep['log_window']['last_timestamp']}",
        f"Total Log Lines           : {rep['log_window']['total_lines']}",
        "",
    ]

    for ea_name, ea_data in rep["eas"].items():
        pnl_disp = f"${ea_data['explicit_pnl_sum']:+.2f}" if ea_data["explicit_pnl_sum"] is not None else "null"
        lines.extend([
            f"--- EA: {ea_name} ---",
            f"Open Events           : {ea_data['open_count']}",
            f"Close Events          : {ea_data['close_count']}",
            f"Breakeven Locks       : {ea_data['breakeven_count']}",
            f"Trailing Steps        : {ea_data['trailing_count']}",
            f"Init/Deinit Events    : {ea_data['init_deinit_count']}",
            f"Errors / Rejects      : {ea_data['error_count']}",
            f"Deals with Explicit PnL: {ea_data['explicit_pnl_deals_count']}",
            f"Explicit PnL Sum      : {pnl_disp}",
            f"Evidence / Note       : {ea_data['notes']}",
            "",
        ])

    tot_pnl_disp = f"${rep['overall_summary']['total_explicit_pnl']:+.2f}" if rep["overall_summary"]["total_explicit_pnl"] is not None else "null"
    lines.extend([
        "--- OVERALL ACCOUNT ASSESSMENT ---",
        f"Total Explicit PnL (Log Only) : {tot_pnl_disp}",
        "Account Balance / Net PnL      : UNKNOWN (Log fragment only, statement required)",
        "Winrate Calculation            : UNKNOWN (Velocity PnL not recorded in log)",
        "=" * 60,
    ])
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V16 Diagnostic Report CLI")
    parser.add_argument("log_file", type=Path, help="Path to MT5 log file (UTF-16)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", type=Path, default=None, help="Output destination file")

    args = parser.parse_args(argv)

    if not args.log_file.exists() or not args.log_file.is_file():
        print(f"Error: {args.log_file} is not an existing file", file=sys.stderr)
        return 1

    content = read_log_text(args.log_file)
    report = parse_v16_log(content)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if args.format == "json":
        output_str = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        output_str = render_diagnostic_text(report)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_str, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
