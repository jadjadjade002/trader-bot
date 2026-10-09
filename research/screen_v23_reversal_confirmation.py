"""One frozen failed-breakout hypothesis, descriptive research only."""

import argparse
import csv
import json
import math
from dataclasses import replace
from pathlib import Path

from research.audit_v23_signal_markouts import audit, load_snapshots


FEATURES = ("dc_high", "dc_low", "atr", "break_close", "retest_open",
            "retest_close", "retest_high", "retest_low")


def signal(row):
    values = {name: float(row[name]) for name in FEATURES}
    if not all(math.isfinite(v) and v > 0 for v in values.values()):
        raise ValueError("Invalid closed-bar feature")
    high, low, atr = (values[k] for k in ("dc_high", "dc_low", "atr"))
    opened, closed = values["retest_open"], values["retest_close"]
    if (high < low or values["retest_high"] < max(opened, closed)
            or values["retest_low"] > min(opened, closed)):
        raise ValueError("Invalid channel or retest OHLC")
    if not low < closed < high:
        return 0
    if (values["break_close"] > high
            and values["retest_low"] >= high - 0.5 * atr
            and closed < opened):
        return -1
    if (values["break_close"] < low
            and values["retest_high"] <= low + 0.5 * atr
            and closed > opened):
        return 1
    return 0


def evaluate(path):
    snapshots = load_snapshots(Path(path))
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    # The shared auditor applies -1 to its fade field. Encode the actual side
    # accordingly, and clear closeback so only this predeclared hypothesis runs.
    candidate = [replace(item, original=-signal(row), closeback=0)
                 for item, row in zip(snapshots, rows)]
    result = audit(candidate)
    stats = result["results"]["original_fade"]
    primary = stats["15"]
    ci = primary["day_block_bootstrap_95_mean"]
    positive_months = sum(m["quoted_sum"] > 0 for m in primary["monthly"].values())
    passed = (primary["matched"] >= 100
              and primary["mean_spread_aware_price_delta"] > 0
              and ci is not None and ci[0] > 0
              and len(primary["monthly"]) == 5 and positive_months >= 4)
    return {"candidate": "reversal_confirmation", "status": "ADVANCE_TO_NATIVE_TEST" if passed else "REJECTED",
            "scope": "Exploratory May-Sep screen, not OOS or deployment approval",
            "units": result["units"], "bar_count": result["bar_count"],
            "positive_primary_months": positive_months, "horizons": stats}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_csv", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.raw_csv), indent=2, allow_nan=False))
