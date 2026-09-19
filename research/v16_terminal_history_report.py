"""Offline, fail-closed reconstruction of MT5 terminal trade logs.

Terminal logs do not contain account-history deal reasons or money PnL.  This
tool therefore reports only reconstructed price PnL and labels an exit only
when the terminal evidence uniquely supports it.  It never infers EA/module
ownership from a terminal log.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


ACCOUNT = "112334471"
EPSILON = 0.00001

DEAL_RE = re.compile(
    r"deal #(?P<deal>\d+) (?P<side>buy|sell) (?P<volume>[\d.]+) "
    r"(?P<symbol>[A-Z0-9._-]+) at (?P<price>[\d.]+) done "
    r"\(based on order #(?P<order>\d+)\)", re.I)
ENTRY_RE = re.compile(
    r"^market (?P<side>buy|sell) (?P<volume>[\d.]+) (?P<symbol>[A-Z0-9._-]+)"
    r" sl: (?P<sl>[\d.]+) tp: (?P<tp>[\d.]+)$", re.I)
CLOSE_RE = re.compile(
    r"^market (?P<side>buy|sell) (?P<volume>[\d.]+) (?P<symbol>[A-Z0-9._-]+), "
    r"close #(?P<position>\d+) (?P<old_side>buy|sell) (?P<old_volume>[\d.]+) "
    r"(?P<old_symbol>[A-Z0-9._-]+) (?P<open_price>[\d.]+)$", re.I)
MODIFY_RE = re.compile(
    r"accepted modify #(?P<position>\d+) (?P<side>buy|sell) (?P<volume>[\d.]+) "
    r"(?P<symbol>[A-Z0-9._-]+) sl: [\d.]+, tp: [\d.]+ -> sl: (?P<sl>[\d.]+), tp: (?P<tp>[\d.]+)", re.I)


@dataclass
class Modification:
    timestamp: str
    sl: float
    tp: float


@dataclass
class Position:
    position_ticket: int
    entry_deal: int
    timestamp: str
    side: str
    volume: float
    symbol: str
    entry_price: float
    initial_sl: float
    initial_tp: float
    modifications: list[Modification] = field(default_factory=list)
    exit_deal: int | None = None
    exit_timestamp: str | None = None
    exit_price: float | None = None
    exit_kind: str = "OPEN"
    price_pnl: float | None = None

    @property
    def current_sl(self) -> float:
        return self.modifications[-1].sl if self.modifications else self.initial_sl

    @property
    def current_tp(self) -> float:
        return self.modifications[-1].tp if self.modifications else self.initial_tp


def read_log(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-16")
    except UnicodeError:
        return raw.decode("utf-8", errors="replace")


def log_timestamp(path: Path, line: str) -> str:
    fields = line.split("\t")
    clock = fields[2] if len(fields) > 2 else ""
    return f"{path.stem} {clock}".strip()


def near(a: float, b: float) -> bool:
    return abs(a - b) <= EPSILON


def classify_stop(position: Position, exit_price: float) -> str:
    """Classify a broker-side deal at a known exact level; else UNKNOWN."""
    if near(exit_price, position.current_tp):
        return "TP"
    if near(exit_price, position.initial_sl):
        return "INITIAL_SL"
    if not near(exit_price, position.current_sl) or not position.modifications:
        return "UNKNOWN"
    risk = abs(position.entry_price - position.initial_sl)
    lock_distance = (position.entry_price - position.current_sl) if position.side == "sell" else (position.current_sl - position.entry_price)
    # A lock must be on the profitable side and close enough to entry.  Larger
    # protected SL moves are trailing; ambiguous distances remain UNKNOWN.
    if risk > EPSILON and lock_distance >= -EPSILON and lock_distance <= risk * 0.10:
        return "BE_LOCK"
    if risk > EPSILON and lock_distance > risk * 0.10:
        return "TRAILING"
    return "UNKNOWN"


def _record_unmatched(unmatched: list[dict[str, str]], path: Path, line_no: int, kind: str, line: str) -> None:
    unmatched.append({"file": str(path), "line": str(line_no), "kind": kind, "raw": line})


def parse_paths(paths: Iterable[Path], account: str = ACCOUNT) -> dict:
    positions: dict[int, Position] = {}
    pending_entries: list[dict] = []
    # MT5 emits both a request ("market ...") and an acknowledgement
    # ("accepted market ...").  Only the request is evidence of the intended
    # operation.  Keep its target ticket so a later deal does not get matched
    # to another same-sized grid position.
    pending_closes: list[dict] = []
    unmatched: list[dict[str, str]] = []

    for path in sorted(paths):
        for line_no, raw in enumerate(read_log(path).splitlines(), 1):
            prefix = f"'{account}': "
            prefix_at = raw.find(prefix)
            if prefix_at < 0:
                continue
            ts = log_timestamp(path, raw)
            # Regexes below are deliberately anchored.  Strip precisely the
            # terminal account prefix, rather than the entire last TSV field.
            msg = raw[prefix_at + len(prefix):].strip()
            # An acknowledgement is not a second request.  In particular,
            # treating it as one creates duplicate entry intents and can make
            # later broker-side exits look ambiguous.
            if msg.lower().startswith("accepted market "):
                continue
            if match := CLOSE_RE.search(msg):
                pending_closes.append({
                    **match.groupdict(),
                    "timestamp": ts,
                    "path": path,
                    "line_no": line_no,
                    "raw": raw,
                })
                continue
            if match := ENTRY_RE.search(msg):
                pending_entries.append({**match.groupdict(), "timestamp": ts})
                continue
            if match := MODIFY_RE.search(msg):
                ticket = int(match["position"])
                position = positions.get(ticket)
                if position is None:
                    _record_unmatched(unmatched, path, line_no, "modify_without_open", raw)
                else:
                    mod = Modification(ts, float(match["sl"]), float(match["tp"]))
                    if not position.modifications or (position.current_sl, position.current_tp) != (mod.sl, mod.tp):
                        position.modifications.append(mod)
                continue
            match = DEAL_RE.search(msg)
            if not match:
                continue
            deal = int(match["deal"])
            order = int(match["order"])
            side, volume, symbol, price = match["side"].lower(), float(match["volume"]), match["symbol"], float(match["price"])
            entry = next((x for x in reversed(pending_entries)
                          if x["side"].lower() == side and float(x["volume"]) == volume and x["symbol"] == symbol), None)
            if entry is not None:
                pending_entries.remove(entry)
                positions[order] = Position(order, deal, entry["timestamp"], side, volume, symbol, price,
                                             float(entry["sl"]), float(entry["tp"]))
                continue
            # First honor an explicit close request.  Its position ticket is
            # stronger evidence than symbol/side/volume, which may identify
            # several open grid positions.
            requested = []
            for request in pending_closes:
                position = positions.get(int(request["position"]))
                if (position is not None and position.exit_deal is None
                        and position.symbol == symbol and position.volume == volume
                        and position.side != side and request["side"].lower() == side
                        and request["old_side"].lower() == position.side
                        and float(request["old_volume"]) == position.volume
                        and request["old_symbol"] == position.symbol):
                    requested.append((request, position))
            if len(requested) == 1:
                request, position = requested[0]
                pending_closes.remove(request)
                position.exit_kind = "MANUAL"
                position.exit_deal, position.exit_timestamp, position.exit_price = deal, ts, price
                position.price_pnl = (price - position.entry_price) * position.volume * (1 if position.side == "buy" else -1)
                continue
            if len(requested) > 1:
                _record_unmatched(unmatched, path, line_no, "deal_unmatched_or_ambiguous", raw)
                continue

            # Without a close request, terminal logs cannot identify which of
            # several equal grid positions a broker SL/TP deal closed.  Pair
            # only a single candidate; otherwise fail closed.
            candidates = [p for p in positions.values() if p.exit_deal is None and p.symbol == symbol
                          and p.volume == volume and p.side != side]
            if len(candidates) != 1:
                _record_unmatched(unmatched, path, line_no, "deal_unmatched_or_ambiguous", raw)
                continue
            position = candidates[0]
            position.exit_kind = classify_stop(position, price)
            position.exit_deal, position.exit_timestamp, position.exit_price = deal, ts, price
            position.price_pnl = (price - position.entry_price) * position.volume * (1 if position.side == "buy" else -1)

    for request in pending_closes:
        ticket = int(request["position"])
        kind = "close_without_open" if ticket not in positions else "close_without_deal"
        _record_unmatched(unmatched, request["path"], request["line_no"], kind, request["raw"])
    for entry in pending_entries:
        unmatched.append({"file": "", "line": "", "kind": "entry_without_deal", "raw": str(entry)})

    result = sorted(positions.values(), key=lambda p: (p.timestamp, p.position_ticket))
    return {
        "schema_version": "1",
        "account": account,
        "limitations": [
            "price_pnl is price difference times volume, not account-currency PnL",
            "terminal logs lack DEAL_REASON, magic, EA/module, commission, swap, fee, and tick spread",
            "UNKNOWN means evidence was insufficient; it is not a manual or EA exit",
        ],
        "positions": [asdict(p) for p in result],
        "summary": {"opened": len(result), "closed": sum(p.exit_deal is not None for p in result), "unmatched_records": len(unmatched)},
        "unmatched_records": unmatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="terminal log file or directory")
    parser.add_argument("--account", default=ACCOUNT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = [args.path] if args.path.is_file() else list(args.path.rglob("*.log"))
    report = parse_paths(paths, args.account)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
