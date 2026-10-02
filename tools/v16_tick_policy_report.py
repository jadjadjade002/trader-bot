#!/usr/bin/env python3
"""Read-only policy reconstruction for V16 schema-2 tick telemetry."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

FAVOR = (15, 20, 30, 50, 85, 100, 130, 150, 180, 200, 220, 240)
ADVERSE = (15, 20, 30, 50, 85, 100, 130, 180, 220, 260)
BE_TRIGGERS = (50, 75, 85, 100, 130, 150)
BE_LOCKS = (0, 10, 15, 20, 30)


def num(row, key):
    value = row.get(key, "")
    return int(value) if value not in (None, "") else None


def valid_row(row):
    """Return (bool, reason), rejecting ambiguity rather than guessing."""
    if row.get("schema_version") != "2":
        return False, "schema_version"
    if row.get("label_status") != "COMPLETE":
        return False, row.get("label_status") or "label_status"
    try:
        entry, horizon = num(row, "entry_tick_time_msc"), num(row, "horizon_end_time_msc")
        if entry is None or horizon is None or horizon <= entry:
            return False, "horizon"
        if num(row, "disconnect_seen") or num(row, "rollover_seen") or num(row, "missing_bar_count"):
            return False, "quality"
        for key in ("signal_bar_epoch", "observed_tick_count", "completed_bar_count"):
            if num(row, key) is None:
                return False, key
        return True, ""
    except (TypeError, ValueError):
        return False, "numeric"


def event_time(row, side, kind, level):
    prefix = "buy" if side == "BUY" else "sell"
    return num(row, f"{prefix}_{'fav' if kind == 'tp' else 'adv'}_{level}_msc")


def reconstruct(row, side, tp, sl, be_trigger, be_lock):
    """Reconstruct one policy. Any impossible/ambiguous chronology is INVALID."""
    entry, horizon = num(row, "entry_tick_time_msc"), num(row, "horizon_end_time_msc")
    tp_t, sl_t = event_time(row, side, "tp", tp), event_time(row, side, "sl", sl)
    prefix = "buy" if side == "BUY" else "sell"
    trigger_t = event_time(row, side, "tp", be_trigger)
    recross_t = num(row, f"{prefix}_be_t{be_trigger}_l{be_lock}_recross_msc")
    events = []
    for label, t in (("TP", tp_t), ("SL", sl_t)):
        if t is not None:
            if not entry <= t <= horizon:
                return {"outcome": "INVALID", "reason": label + "_time_range"}
            events.append((t, label))
    if recross_t is not None:
        if trigger_t is None:
            return {"outcome": "INVALID", "reason": "recross_without_trigger"}
        if not entry <= trigger_t <= recross_t <= horizon:
            return {"outcome": "INVALID", "reason": "be_chronology"}
        events.append((recross_t, "BE"))
    if not events:
        return {"outcome": "TIMEOUT", "reason": ""}
    first = min(t for t, _ in events)
    at_first = [label for t, label in events if t == first]
    if len(at_first) != 1:
        return {"outcome": "INVALID", "reason": "same_timestamp:" + "/".join(sorted(at_first))}
    label = at_first[0]
    return {"outcome": label, "reason": "", "time_msc": first,
            "pnl_points": tp if label == "TP" else -sl if label == "SL" else be_lock}


def metric(rows, side, tp, sl, be_trigger, be_lock):
    counts, pnls, invalid = Counter(), [], Counter()
    for row in rows:
        result = reconstruct(row, side, tp, sl, be_trigger, be_lock)
        counts[result["outcome"]] += 1
        if result["outcome"] == "INVALID":
            invalid[result["reason"]] += 1
        elif result["outcome"] in ("TP", "SL", "BE"):
            pnls.append(result["pnl_points"])
    resolved = len(pnls)
    return {"tp": tp, "sl": sl, "be_trigger": be_trigger, "be_lock": be_lock,
            "rows": len(rows), "counts": dict(counts), "invalid_reasons": dict(invalid),
            "resolved": resolved, "expectancy_points": (sum(pnls) / resolved if resolved else None),
            "sum_points": sum(pnls), "profit_factor": (
                sum(x for x in pnls if x > 0) / -sum(x for x in pnls if x < 0)
                if any(x < 0 for x in pnls) else (math.inf if any(x > 0 for x in pnls) else None))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    with args.csv.open(newline="", encoding="utf-8-sig") as fh:
        raw = list(csv.DictReader(fh))
    usable, rejects = [], Counter()
    for row in raw:
        ok, reason = valid_row(row)
        if ok:
            usable.append(row)
        else:
            rejects[reason] += 1
    original = {"tp": 180, "sl": 260, "be_trigger": 85, "be_lock": 15}
    signal_rows = {s: [r for r in usable if r.get("signal_side") == s] for s in ("BUY", "SELL")}
    def one(rows, side, p=original): return metric(rows, side, **p)
    original_signal = {s: one(signal_rows[s], s) for s in signal_rows}
    original_both = {s: one(usable, s) for s in ("BUY", "SELL")}
    grid = []
    for side in ("BUY", "SELL"):
        rows = signal_rows[side]
        for tp in FAVOR:
            for sl in ADVERSE:
                for trig in BE_TRIGGERS:
                    for lock in BE_LOCKS:
                        grid.append(metric(rows, side, tp, sl, trig, lock))
    ranked = sorted((x for x in grid if x["resolved"] >= 10 and not x["invalid_reasons"]),
                    key=lambda x: x["expectancy_points"], reverse=True)
    report = {"source": str(args.csv), "schema": 2, "raw_rows": len(raw),
              "usable_complete_rows": len(usable), "rejected_rows": dict(rejects),
              "sessions": sorted({r.get("signal_bar_iso", "")[:10] for r in usable}),
              "warning": "Partial session; exploratory diagnostics only. No promotion decision.",
              "policy": original, "original_signal_side": original_signal,
              "original_both_side": original_both,
              "grid": {"candidate_count": len(grid), "eligible_count": len(ranked),
                        "top_signal_side": ranked[:20]},
              "definitions": {"TP": "first favorable passage", "SL": "first adverse passage",
                              "BE": "first post-trigger return to lock level", "TIMEOUT": "no recorded event",
                              "INVALID": "bad quality, missing chronology, or same-ms ambiguity"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"raw_rows": len(raw), "usable": len(usable), "rejected": dict(rejects),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
