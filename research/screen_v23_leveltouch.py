"""Descriptive, non-execution screen for the V23 level-touch signal.

Uses historical first-tick bid/ask snapshots. This is not a native strategy
backtest: it excludes order rejection, SL/TP, slippage, fees and path-dependent
position/breaker state. Never use its result alone to promote a trading EA.
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def signal(row):
    high = float(row["dc_high"])
    low = float(row["dc_low"])
    atr = float(row["atr"])
    if atr <= 0:
        return 0
    breakout = float(row["break_close"])
    retest_open = float(row["retest_open"])
    retest_close = float(row["retest_close"])
    retest_high = float(row["retest_high"])
    retest_low = float(row["retest_low"])
    if breakout > high and high - 0.5 * atr <= retest_low <= high and retest_close > max(high, retest_open):
        return 1
    if breakout < low and low <= retest_high <= low + 0.5 * atr and retest_close < min(low, retest_open):
        return -1
    return 0


def evaluate(path, horizons=(5, 15, 60)):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    by_time = {datetime.strptime(row["bar"], "%Y.%m.%d %H:%M:%S"): row for row in rows}
    if len(by_time) != len(rows):
        raise ValueError("Duplicate bar timestamps")
    result = {str(h): {"all_signals": 0, "matched": 0, "positive": 0, "sum_price_delta": 0.0,
                       "months": defaultdict(lambda: {"count": 0, "sum_price_delta": 0.0})} for h in horizons}
    for timestamp, row in by_time.items():
        side = signal(row)
        if not side:
            continue
        entry = float(row["ask"] if side > 0 else row["bid"])
        for horizon in horizons:
            stats = result[str(horizon)]
            stats["all_signals"] += 1
            # Strict continuous calendar interval. Never bridge market/CSV gaps.
            if any(timestamp + timedelta(minutes=n) not in by_time for n in range(1, horizon + 1)):
                continue
            exit_row = by_time[timestamp + timedelta(minutes=horizon)]
            exit_quote = float(exit_row["bid"] if side > 0 else exit_row["ask"])
            delta = side * (exit_quote - entry)
            stats["matched"] += 1
            stats["positive"] += delta > 0
            stats["sum_price_delta"] += delta
            month = timestamp.strftime("%Y-%m")
            stats["months"][month]["count"] += 1
            stats["months"][month]["sum_price_delta"] += delta
    for stats in result.values():
        stats["mean_price_delta"] = stats["sum_price_delta"] / stats["matched"] if stats["matched"] else None
        stats["positive_pct"] = 100 * stats["positive"] / stats["matched"] if stats["matched"] else None
        stats["months"] = dict(stats["months"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_csv", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.raw_csv), indent=2, allow_nan=False))
