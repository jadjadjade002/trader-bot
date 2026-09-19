"""Summarize live v16 MT5 expert logs without touching the terminal.

This reads MT5/MQL5 log files and extracts the v16 events we care about:
Velocity scalp opens, breakeven locks, close notifications, Apex profile starts,
and explicit Apex Net PnL lines when available.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


OPEN_RE = re.compile(
    r"(?P<time>\d\d:\d\d:\d\d\.\d+).*QuantumTitan_v16_Velocity "
    r"\(XAUUSD,M1\).*?(?P<side>BUY|SELL) SCALP OPENED @ (?P<entry>\d+\.\d+)"
    r" \| SL: (?P<sl>\d+\.\d+).*?\| TP: (?P<tp>\d+\.\d+).*?\| Lot: (?P<lot>\d+\.\d+)"
)
BE_RE = re.compile(
    r"(?P<time>\d\d:\d\d:\d\d\.\d+).*QuantumTitan_v16_Velocity "
    r"\(XAUUSD,M1\).*?(?P<side>BUY|SELL) BREAKEVEN LOCKED: Profit (?P<points>\d+\.\d+) pts"
)
CLOSE_RE = re.compile(
    r"(?P<time>\d\d:\d\d:\d\d\.\d+).*QuantumTitan_v16_Velocity "
    r"\(XAUUSD,M1\).*Deal #(?P<deal>\d+) closed; cooldown started"
)
APEX_INIT_RE = re.compile(
    r"(?P<time>\d\d:\d\d:\d\d\.\d+).*QuantumTitan_v16_Apex "
    r"\(XAUUSD,(?P<tf>M1|M5|M15|H1)\).*Adaptive Profile\s*: \[(?P<profile>[^\]]+)\]"
)
APEX_PNL_RE = re.compile(
    r"(?P<time>\d\d:\d\d:\d\d\.\d+).*QuantumTitan_v16_Apex .*"
    r"DEAL CLOSED #(?P<deal>\d+).*Net PnL: (?P<sign>[+-])\$(?P<pnl>\d+\.\d+)"
)


def _decode(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-16le")
    except UnicodeDecodeError:
        return raw.decode("utf-8-sig")


def summarize(paths: Iterable[Path]) -> dict[str, object]:
    opens: list[dict[str, object]] = []
    be_locks: list[dict[str, object]] = []
    closes: list[dict[str, object]] = []
    apex_profiles: list[dict[str, object]] = []
    apex_net_pnls: list[float] = []

    for path in paths:
        for line in _decode(path).splitlines():
            if match := OPEN_RE.search(line):
                item = match.groupdict()
                opens.append({
                    "time": item["time"],
                    "side": item["side"],
                    "entry": float(item["entry"]),
                    "sl": float(item["sl"]),
                    "tp": float(item["tp"]),
                    "lot": float(item["lot"]),
                })
            if match := BE_RE.search(line):
                item = match.groupdict()
                be_locks.append({
                    "time": item["time"],
                    "side": item["side"],
                    "points": float(item["points"]),
                })
            if match := CLOSE_RE.search(line):
                closes.append(match.groupdict())
            if match := APEX_INIT_RE.search(line):
                apex_profiles.append(match.groupdict())
            if match := APEX_PNL_RE.search(line):
                item = match.groupdict()
                value = float(item["pnl"])
                apex_net_pnls.append(value if item["sign"] == "+" else -value)

    side_counts = Counter(item["side"] for item in opens)
    latest_open = opens[-1] if opens else None
    latest_apex_profile = apex_profiles[-1] if apex_profiles else None
    return {
        "schema_version": 1,
        "source": "v16_mql5_expert_log",
        "velocity_opens": len(opens),
        "velocity_closes": len(closes),
        "velocity_breakeven_locks": len(be_locks),
        "velocity_buy_opens": side_counts.get("BUY", 0),
        "velocity_sell_opens": side_counts.get("SELL", 0),
        "latest_velocity_open": latest_open,
        "latest_apex_profile": latest_apex_profile,
        "apex_explicit_closed_pnl": round(sum(apex_net_pnls), 2),
        "apex_explicit_pnl_events": len(apex_net_pnls),
        "note": "Velocity close notices do not include PnL; use MT5 account history for exact realized PnL.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.log)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
