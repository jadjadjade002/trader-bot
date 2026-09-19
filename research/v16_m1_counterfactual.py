"""Approximate fixed-exit counterfactuals for verified V16 Velocity entries.

Uses QTForward M1 OHLC, not tick order. Ambiguous intrabar paths are never
resolved in the strategy's favour. Results are research evidence, not fills.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    from research.v16_velocity_live_report import build_report
except ModuleNotFoundError:  # Direct `python research/...py` execution.
    from v16_velocity_live_report import build_report


POINT = 0.01


@dataclass(frozen=True)
class Scenario:
    name: str
    tp_points: float
    sl_points: float
    be_trigger_points: float
    be_lock_points: float


def load_bars(paths):
    bars = []
    for path in sorted(map(Path, paths)):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("flags") != "OK":
                    continue
                bars.append({
                    "time": datetime.fromisoformat(row["time_broker_iso"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "spread": float(row["bar_spread_points"]) * POINT,
                })
    return sorted(bars, key=lambda row: row["time"])


def _levels(entry, side, scenario):
    direction = 1 if side == "buy" else -1
    return (
        entry + direction * scenario.tp_points * POINT,
        entry - direction * scenario.sl_points * POINT,
        entry + direction * scenario.be_trigger_points * POINT,
        entry + direction * scenario.be_lock_points * POINT,
    )


def simulate_trade(position, bars, scenario):
    entry_time = datetime.strptime(position["entry_terminal_time"], "%Y%m%d %H:%M:%S.%f")
    if not bars or entry_time < bars[0]["time"] - timedelta(minutes=1) or entry_time > bars[-1]["time"]:
        return {"status": "NOT_COVERED"}
    # Skip the entry minute because its OHLC contains price action before the
    # fill timestamp. Treating that full candle as post-entry would leak data.
    eligible = [bar for bar in bars if bar["time"].replace(second=0, microsecond=0) > entry_time.replace(second=0, microsecond=0)]
    if not eligible:
        return {"status": "NOT_COVERED"}
    side, entry = position["side"], float(position["entry"])
    tp, initial_sl, trigger, be_sl = _levels(entry, side, scenario)
    armed = False
    for bar in eligible:
        # MT5 chart OHLC is bid-like. Approximate sell exits using one recorded
        # per-bar spread; exact tick spread and ordering remain unavailable.
        high = bar["high"] if side == "buy" else bar["high"] + bar["spread"]
        low = bar["low"] if side == "buy" else bar["low"] + bar["spread"]
        current_sl = be_sl if armed else initial_sl
        tp_hit = high >= tp if side == "buy" else low <= tp
        sl_hit = low <= current_sl if side == "buy" else high >= current_sl
        trigger_hit = high >= trigger if side == "buy" else low <= trigger
        if tp_hit and sl_hit:
            return {"status": "AMBIGUOUS_INTRABAR", "time": bar["time"].isoformat()}
        if not armed and trigger_hit and sl_hit:
            return {"status": "AMBIGUOUS_INTRABAR", "time": bar["time"].isoformat()}
        if tp_hit:
            return {"status": "TP", "pnl": scenario.tp_points * POINT, "time": bar["time"].isoformat()}
        if sl_hit:
            pnl = scenario.be_lock_points * POINT if armed else -scenario.sl_points * POINT
            return {"status": "BE_LOCK" if armed else "INITIAL_SL", "pnl": pnl, "time": bar["time"].isoformat()}
        if not armed and trigger_hit:
            same_bar_retrace = low <= be_sl if side == "buy" else high >= be_sl
            if same_bar_retrace:
                return {"status": "AMBIGUOUS_INTRABAR", "time": bar["time"].isoformat()}
            armed = True
    return {"status": "UNRESOLVED_AT_DATA_END"}


def compare(positions, bars, scenarios):
    output = {"limitations": [
        "M1 OHLC cannot reveal tick ordering inside a bar",
        "sell-side ask is approximated from bar spread; spread is not a tick path",
        "PnL is gross XAUUSD 0.01-lot price delta; fees and slippage excluded",
        "same historical entries isolate exit management only; candidate signal quality is not tested",
        "entry-minute candles are skipped because pre-fill and post-fill ticks cannot be separated",
    ], "coverage": {"first_bar": bars[0]["time"].isoformat() if bars else None,
                     "last_bar": bars[-1]["time"].isoformat() if bars else None}, "scenarios": {}}
    baseline_pairs = []
    for scenario in scenarios:
        counts = {}
        pnl = 0.0
        rows = []
        for position in positions:
            result = simulate_trade(position, bars, scenario)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            if "pnl" in result:
                pnl += result["pnl"]
            rows.append({"entry_deal": position["entry_deal"], "actual_class": position.get("class"), **result})
            if scenario.name == "v16_original" and result["status"] in ("TP", "BE_LOCK", "INITIAL_SL"):
                baseline_pairs.append((position.get("class"), result["status"]))
        resolved = sum(counts.get(key, 0) for key in ("TP", "BE_LOCK", "INITIAL_SL"))
        output["scenarios"][scenario.name] = {
            "settings": scenario.__dict__, "counts": counts, "resolved": resolved,
            "gross_pnl_estimate": round(pnl, 2), "rows": rows,
        }
    compared = len(baseline_pairs)
    agreement = sum(actual == simulated for actual, simulated in baseline_pairs)
    rate = agreement / compared if compared else 0.0
    output["validation"] = {
        "baseline_outcomes_compared": compared,
        "baseline_exact_class_agreement": agreement,
        "agreement_rate": round(rate, 4),
        "decision_valid": compared >= 30 and rate >= 0.90,
        "gate": "PASS" if compared >= 30 and rate >= 0.90 else "INCONCLUSIVE_OHLC_CANNOT_REPRODUCE_LIVE_EXITS",
    }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experts", required=True, type=Path)
    parser.add_argument("--terminal", required=True, type=Path)
    parser.add_argument("--bars", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    live = build_report(list(args.experts.glob("*.log")), list(args.terminal.glob("*.log")))
    bars = load_bars(args.bars.glob("QTForward_XAUUSD_M1_*.csv"))
    report = compare(live["positions"], bars, [
        Scenario("v16_original", 180, 260, 85, 15),
        Scenario("v16_3_candidate", 220, 220, 130, 20),
        Scenario("compromise", 200, 240, 100, 15),
    ])
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
