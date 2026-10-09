#!/usr/bin/env python3
"""Evidence-only R2 mode-5 preset 0/1 exhaustion diagnostic."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.analyze_v23_backtest import bucket, finite, parse_deals, csv_rows

RUNS = {
    0: ROOT / "reports/v25_research_20261007/runs/r2_a_dev_5_0",
    1: ROOT / "reports/v25_research_20261007/runs/r2_a_dev_5_1",
}
# Fixed before aggregation. Descriptive only; never used as trade filters.
R_BINS = ((0.0, 0.5, "<0.5R"), (0.5, 1.0, "0.5-<1R"),
          (1.0, 2.0, "1-<2R"), (2.0, math.inf, ">=2R"))


def stats(values):
    xs = sorted(values)
    if not xs:
        return {"n": 0, "median": None, "p25": None, "p75": None}

    def quantile(p):
        at = (len(xs) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return xs[lo] + (xs[hi] - xs[lo]) * (at - lo)

    return {"n": len(xs), "median": median(xs), "p25": quantile(.25), "p75": quantile(.75)}


def bin_counts(values):
    counts = {label: 0 for _, _, label in R_BINS}
    for value in values:
        for lo, hi, label in R_BINS:
            if lo <= value < hi:
                counts[label] += 1
                break
    return counts


def _validate_signature(accepted, preset):
    sig = accepted["signature"]
    expected = {"start": "2025.12.01", "end": "2026.06.01", "mode": 5,
                "deposit": 10000, "delay_ms": 200, "optimize": False,
                "production": False, "overrides": {"InpEntryStrength": preset}}
    for key, value in expected.items():
        if sig.get(key) != value:
            raise ValueError(f"Accepted signature mismatch for {key}: expected {value!r}")


def _count(value, field):
    number = finite(value)
    if number < 0 or not number.is_integer():
        raise ValueError(f"Invalid integer count for {field}")
    return int(number)


def analyze_records(accepted, deal_rows, path_rows, preset):
    """Aggregate validated accepted run rows; exported for focused unit tests."""
    _validate_signature(accepted, preset)
    trades, cash = parse_deals(deal_rows)
    deposit = finite(accepted["signature"]["deposit"])
    if len(cash) != 1 or cash[0]["type"] != 2 or abs(cash[0]["net"] - deposit) > .021:
        raise ValueError("Expected exactly one valid initial cash/deposit deal")

    result = accepted["result"]
    native = result["native"]
    reported_trades = _count(result["trades"], "accepted trades")
    native_trades = _count(native["Total Trades"], "native total trades")
    derived = bucket(trades)
    accepted_net = finite(result["net"])
    native_net = finite(native["Total Net Profit"])
    if len(trades) != reported_trades or len(trades) != native_trades:
        raise ValueError("Derived trade count does not reconcile to accepted/native report")
    if abs(derived["net"] - accepted_net) > .021 or abs(derived["net"] - native_net) > .021:
        raise ValueError("Derived net does not reconcile to accepted/native report")

    paths = {}
    for row in path_rows:
        required = {"position", "opened", "entry", "initial_risk", "mfe_price_sampled", "mae_price_sampled",
                    "mfe_time_msc", "mae_time_msc"}
        if not required <= set(row):
            raise ValueError("Path schema incomplete")
        pos = str(int(row["position"]))
        if pos in paths:
            raise ValueError(f"Duplicate path row for position {pos}")
        numeric = {field: finite(row[field]) for field in
                   ("opened", "entry", "initial_risk", "mfe_price_sampled", "mae_price_sampled",
                    "mfe_time_msc", "mae_time_msc")}
        for field in ("opened", "mfe_time_msc", "mae_time_msc"):
            if not numeric[field].is_integer():
                raise ValueError(f"Noninteger path timestamp {field} for position {pos}")
        paths[pos] = row
    trade_ids = {str(t["position"]) for t in trades}
    if set(paths) != trade_ids:
        missing = sorted(trade_ids - set(paths))
        extra = sorted(set(paths) - trade_ids)
        raise ValueError(f"Path coverage mismatch; missing={missing}, extra={extra}")

    all_trades = []
    preentry_lags = {"mfe": [], "mae": []}
    for trade in trades:
        if trade["close_msc"] < trade["open_msc"]:
            raise ValueError(f"Reversed deal timestamps for position {trade['position']}")
        p = paths[str(trade["position"])]
        opened = int(finite(p["opened"]))
        risk = finite(p["initial_risk"])
        mfe = finite(p["mfe_price_sampled"])
        mae = finite(p["mae_price_sampled"])
        mfe_time = int(finite(p["mfe_time_msc"]))
        mae_time = int(finite(p["mae_time_msc"]))
        if risk <= 0 or mfe < 0 or mae < 0:
            raise ValueError(f"Invalid path risk/excursion for position {trade['position']}")
        if opened != trade["open_msc"] // 1000:
            raise ValueError(f"Path open time mismatch for position {trade['position']}")
        close_msc = trade["close_msc"]
        for label, value, event_time in (("MFE", mfe, mfe_time), ("MAE", mae, mae_time)):
            if (value == 0) != (event_time == 0):
                raise ValueError(f"Path {label} timestamp sentinel mismatch for position {trade['position']}")
            path_open_msc = opened * 1000
            if event_time and not path_open_msc <= event_time <= close_msc:
                raise ValueError(f"Path {label} timestamp outside position for {trade['position']}")
            if event_time and event_time < trade["open_msc"]:
                preentry_lags[label.lower()].append(trade["open_msc"] - event_time)
        duration = (trade["close_msc"] - trade["open_msc"]) / 1000
        all_trades.append({**trade, "mfe_r": mfe / risk, "mae_r": mae / risk,
                           "duration_seconds": duration})

    # DEAL_PROFIT before separately recorded commission/swap/fee; native report
    # Gross Profit/Loss fields are retained separately and not conflated with it.
    profit_wins = sum(t["profit"] for t in all_trades if t["profit"] > 0)
    profit_losses = sum(t["profit"] for t in all_trades if t["profit"] < 0)
    cross = defaultdict(list)
    for trade in all_trades:
        cross[(trade["direction"], trade["exit_reason"])].append(trade)
    output = {
        "preset": preset, "trades": derived["trades"], "net_from_positions": derived["net"],
        "deal_profit_positive_before_charges": round(profit_wins, 2),
        "deal_profit_negative_before_charges": round(profit_losses, 2),
        "commission": derived["commission"], "swap": derived["swap"], "fee": derived["fee"],
        "native_net": native["Total Net Profit"], "native_gross_profit": native["Gross Profit"],
        "native_gross_loss": native["Gross Loss"], "native_pf": native["Profit Factor"],
        "native_period": native.get("Period"), "side_exit": {},
        "duration_seconds": stats([t["duration_seconds"] for t in all_trades]),
        "sampled_mfe_r": stats([t["mfe_r"] for t in all_trades]),
        "sampled_mae_r": stats([t["mae_r"] for t in all_trades]),
        "sampled_mfe_r_bins": bin_counts([t["mfe_r"] for t in all_trades]),
        "sampled_mae_r_bins": bin_counts([t["mae_r"] for t in all_trades]),
        "path_match_count": len(paths), "path_count": len(paths),
        "sample_events_before_entry_deal": {
            key: {"count": len(lags), "earliest_lag_ms": max(lags) if lags else None}
            for key, lags in preentry_lags.items()
        },
        "exit_labels": {"3": "Expert close", "4": "Stop Loss", "5": "Take Profit"},
    }
    for (side, reason), selected in sorted(cross.items()):
        wins = [t["net"] for t in selected if t["net"] > 1e-8]
        losses = [t["net"] for t in selected if t["net"] < -1e-8]
        net_wins, net_losses = sum(wins), sum(losses)
        output["side_exit"][f"{side}/reason_{reason}"] = {
            "count": len(selected), "net": round(sum(t["net"] for t in selected), 2),
            "wins": len(wins), "losses": len(losses),
            "pf": round(net_wins / -net_losses, 4) if net_losses else None,
            "net_wins": round(net_wins, 2), "net_losses": round(net_losses, 2),
        }
    return output


def analyze(preset: int):
    folder = RUNS[preset]
    stem = f"r2_a_dev_5_{preset}"
    accepted = json.loads((folder / "accepted.json").read_text(encoding="utf-8-sig"))
    return analyze_records(accepted,
                          csv_rows(folder / f"{stem}_deals.csv"),
                          csv_rows(folder / f"{stem}_paths.csv"), preset)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", type=int, choices=(0, 1), help="one preset; default both")
    args = ap.parse_args()
    selected = (args.preset,) if args.preset is not None else (0, 1)
    print(json.dumps([analyze(p) for p in selected], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
