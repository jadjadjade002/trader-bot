"""Audit raw V23 signal direction independently of position/breaker state.

Descriptive research only. Uses first-observed-tick bid/ask quotes, not native
fills. It includes quoted spread but excludes delay, slippage, fees, SL/TP and
position occupancy. OOS status depends on the selected dates and frozen protocol.
"""

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median


REQUIRED = {"bar", "original", "closeback", "bid", "ask", "gate"}
VARIANTS = {
    "original_fade": ("original", -1),
    "original_momentum": ("original", 1),
    "closeback_fade": ("closeback", -1),
}


@dataclass(frozen=True)
class Snapshot:
    bar: datetime
    original: int
    closeback: int
    bid: float
    ask: float
    gate: str = "no_signal"


def load_snapshots(path: Path) -> list[Snapshot]:
    out = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("Missing required raw-candidate fields")
        for line, row in enumerate(reader, start=2):
            try:
                item = Snapshot(
                    datetime.strptime(row["bar"], "%Y.%m.%d %H:%M:%S"),
                    int(row["original"]),
                    int(row["closeback"]),
                    float(row["bid"]),
                    float(row["ask"]),
                    row["gate"],
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Malformed raw row {line}") from exc
            if (item.original not in (-1, 0, 1) or item.closeback not in (-1, 0, 1)
                    or not all(math.isfinite(x) and x > 0 for x in (item.bid, item.ask))
                    or item.ask < item.bid):
                raise ValueError(f"Invalid signal or quote at row {line}")
            if out and item.bar <= out[-1].bar:
                raise ValueError(f"Non-monotonic/duplicate bar at row {line}")
            out.append(item)
    if not out:
        raise ValueError("Empty raw-candidate file")
    return out


def markout(entry: Snapshot, exit_: Snapshot, side: int) -> tuple[float, float, float]:
    if side not in (-1, 1):
        raise ValueError("Side must be -1 or +1")
    entry_mid = (entry.bid + entry.ask) / 2
    exit_mid = (exit_.bid + exit_.ask) / 2
    mid = side * (exit_mid - entry_mid)
    traded = (exit_.bid - entry.ask) if side == 1 else (entry.bid - exit_.ask)
    spread_drag = mid - traded
    if spread_drag < -1e-9:
        raise ValueError("Negative quoted spread drag")
    return mid, traded, spread_drag


def bootstrap_daily_mean(day_sums: dict[str, tuple[float, int]], *, samples: int = 2000, seed: int = 20261006):
    if len(day_sums) < 2:
        return None
    values = list(day_sums.values())
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        chosen = rng.choices(values, k=len(values))
        total = sum(value for value, _ in chosen)
        count = sum(count for _, count in chosen)
        estimates.append(total / count)
    estimates.sort()
    return [estimates[int(0.025 * samples)], estimates[int(0.975 * samples) - 1]]


def audit(snapshots: list[Snapshot], horizons: tuple[int, ...] = (5, 15, 60)) -> dict:
    by_time = {item.bar: item for item in snapshots}
    if len(by_time) != len(snapshots):
        raise ValueError("Duplicate bar timestamps")
    results = {}
    for variant, (field, multiplier) in VARIANTS.items():
        raw_candidates = [item for item in snapshots if getattr(item, field) and item.gate != "attach"]
        per_horizon = {}
        for horizon in horizons:
            if horizon <= 0:
                raise ValueError("Horizon must be positive")
            deltas = []
            mids = []
            costs = []
            monthly = defaultdict(lambda: {"count": 0, "quoted_sum": 0.0})
            daily = defaultdict(lambda: [0.0, 0])
            for entry in raw_candidates:
                future = entry.bar + timedelta(minutes=horizon)
                exit_ = by_time.get(future)
                if exit_ is None:
                    continue
                # Do not bridge market closures, CSV gaps, or missing callback bars.
                if any(entry.bar + timedelta(minutes=n) not in by_time for n in range(1, horizon)):
                    continue
                side = getattr(entry, field) * multiplier
                mid, traded, cost = markout(entry, exit_, side)
                deltas.append(traded)
                mids.append(mid)
                costs.append(cost)
                month = entry.bar.strftime("%Y-%m")
                monthly[month]["count"] += 1
                monthly[month]["quoted_sum"] += traded
                day = entry.bar.strftime("%Y-%m-%d")
                daily[day][0] += traded
                daily[day][1] += 1
            count = len(deltas)
            per_horizon[str(horizon)] = {
                "raw_candidates": len(raw_candidates),
                "matched": count,
                "missing_continuous_window": len(raw_candidates) - count,
                "broker_days": len(daily),
                "mean_mid_price_delta": sum(mids) / count if count else None,
                "mean_quoted_spread_drag": sum(costs) / count if count else None,
                "mean_spread_aware_price_delta": sum(deltas) / count if count else None,
                "median_spread_aware_price_delta": median(deltas) if count else None,
                "positive_pct": 100 * sum(x > 0 for x in deltas) / count if count else None,
                "day_block_bootstrap_95_mean": bootstrap_daily_mean(daily) if count else None,
                "monthly": dict(monthly),
            }
        results[variant] = per_horizon
    return {
        "scope": "Descriptive first-quote raw signal screen; NOT native PnL. OOS status requires a separately frozen protocol.",
        "units": "XAUUSD quote-price delta per signal, not account dollars",
        "bar_count": len(snapshots),
        "first_bar": snapshots[0].bar.isoformat(),
        "last_bar": snapshots[-1].bar.isoformat(),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_csv", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(load_snapshots(args.raw_csv)), indent=2, allow_nan=False))
