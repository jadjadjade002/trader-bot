"""Reconstruct frozen V23 raw signals from V21 collector M1 bars.

Research only. Requires parity against native raw snapshots before any forward
result is accepted. Uses closed bars and stored first-tick bid/ask quotes.
"""

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from research.audit_v23_signal_markouts import Snapshot, audit


REQUIRED = {
    "run_id", "symbol", "time_broker_iso", "open", "high", "low", "close",
    "open_bid", "open_ask", "flags",
}


@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    bid: float
    ask: float
    flags: str


def load_collector(directory: Path) -> list[Bar]:
    files = sorted(directory.glob("QTForward_XAUUSD_M1_*.csv"))
    if not files:
        raise ValueError("No V21 XAUUSD M1 collector files")
    run_ids = set()
    bars = []
    for file in files:
        with file.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not REQUIRED.issubset(reader.fieldnames):
                raise ValueError(f"Missing required V21 fields: {file.name}")
            for line, row in enumerate(reader, start=2):
                try:
                    if not row["run_id"]:
                        raise ValueError("Empty run ID")
                    run_ids.add(row["run_id"])
                    item = Bar(
                        datetime.fromisoformat(row["time_broker_iso"]),
                        *(float(row[k]) for k in ("open", "high", "low", "close", "open_bid", "open_ask")),
                        row["flags"],
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Malformed V21 row: {file.name}:{line}") from exc
                if (row["symbol"] != "XAUUSD" or not all(math.isfinite(x) for x in
                    (item.open, item.high, item.low, item.close, item.bid, item.ask))
                    or min(item.open, item.high, item.low, item.close, item.bid, item.ask) <= 0
                    or item.high < max(item.open, item.close, item.low)
                    or item.low > min(item.open, item.close, item.high)
                    or item.ask < item.bid):
                    raise ValueError(f"Invalid V21 bar/quote: {file.name}:{line}")
                if bars and item.time <= bars[-1].time:
                    raise ValueError(f"Duplicate/non-monotonic V21 time: {file.name}:{line}")
                bars.append(item)
    if len(run_ids) != 1:
        raise ValueError("Mixed V21 run IDs")
    return bars


def compute_atr_sma(bars: list[Bar], period: int = 14) -> list[float | None]:
    """MT5 iATR candidate reconstruction: rolling mean of True Range."""
    if period <= 0:
        raise ValueError("ATR period must be positive")
    atr = [None] * len(bars)
    tr = [None] * len(bars)
    for i in range(1, len(bars)):
        bar = bars[i]
        previous_close = bars[i - 1].close
        tr[i] = max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close))
        if i >= period:
            atr[i] = sum(tr[i - period + 1:i + 1]) / period
    return atr


def reconstruct(bars: list[Bar], *, require_clean_lookback: bool = True) -> tuple[list[Snapshot], list[dict]]:
    """Return first-tick snapshots and feature rows, never using the active bar OHLC."""
    atr = compute_atr_sma(bars)
    snapshots = []
    features = []
    for i, entry in enumerate(bars):
        original = closeback = 0
        channel_high = channel_low = None
        used_atr = atr[i - 1] if i else None
        eligible = False
        if i >= 22 and used_atr is not None and used_atr > 0:
            history = bars[i - 22:i]
            continuous = (entry.time - history[-1].time == timedelta(minutes=1)
                          and all(history[j].time - history[j - 1].time == timedelta(minutes=1)
                                  for j in range(1, len(history))))
            # Entry bar flags are only known after that bar closes. Never gate a
            # first-tick entry on their future value.
            clean = all(b.flags == "OK" for b in history)
            eligible = continuous and (clean or not require_clean_lookback)
            if eligible:
                channel_high = max(b.high for b in bars[i - 22:i - 2])
                channel_low = min(b.low for b in bars[i - 22:i - 2])
                breakout = bars[i - 2]
                retest = bars[i - 1]
                if breakout.close > channel_high and retest.low >= channel_high - 0.5 * used_atr:
                    original = int(retest.close > retest.open)
                    closeback = int(channel_low < retest.close < channel_high)
                elif breakout.close < channel_low and retest.high <= channel_low + 0.5 * used_atr:
                    original = -int(retest.close < retest.open)
                    closeback = -int(channel_low < retest.close < channel_high)
        snapshots.append(Snapshot(entry.time, original, closeback, entry.bid, entry.ask,
                                  "no_signal" if eligible else "data_unavailable"))
        features.append({"time": entry.time, "eligible": eligible, "atr": used_atr,
                         "dc_high": channel_high, "dc_low": channel_low,
                         "entry_flag": entry.flags})
    return snapshots, features


def compare_native(snapshots: list[Snapshot], features: list[dict], native_csv: Path) -> dict:
    native = {}
    with native_csv.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            time = datetime.strptime(row["bar"], "%Y.%m.%d %H:%M:%S")
            if time in native:
                raise ValueError(f"Duplicate native raw bar: {time}")
            native[time] = row
    matched = signal_matches = quote_matches = 0
    entry_ok_bars = entry_ok_quote_matches = 0
    original_candidates = closeback_candidates = 0
    atr_errors = []
    channel_errors = []
    examples = []
    quote_examples = []
    for item, feat in zip(snapshots, features):
        other = native.get(item.bar)
        if not feat["eligible"] or other is None:
            continue
        signal_equal = item.original == int(other["original"]) and item.closeback == int(other["closeback"])
        signal_matches += signal_equal
        original_candidates += item.original != 0
        closeback_candidates += item.closeback != 0
        quote_equal = abs(item.bid - float(other["bid"])) < 1e-8 and abs(item.ask - float(other["ask"])) < 1e-8
        quote_matches += quote_equal
        if feat["entry_flag"] == "OK":
            entry_ok_bars += 1
            entry_ok_quote_matches += quote_equal
        if not quote_equal and len(quote_examples) < 5:
            quote_examples.append({"bar": item.bar.isoformat(), "collector": [item.bid, item.ask],
                                   "native": [float(other["bid"]), float(other["ask"])]})
        atr_errors.append(abs(feat["atr"] - float(other["atr"])))
        channel_errors.append(max(abs(feat["dc_high"] - float(other["dc_high"])),
                                  abs(feat["dc_low"] - float(other["dc_low"]))))
        if not signal_equal and len(examples) < 5:
            examples.append({"bar": item.bar.isoformat(), "reconstructed": [item.original, item.closeback],
                             "native": [int(other["original"]), int(other["closeback"])]})
        matched += 1
    return {"eligible_matched_bars": matched, "signal_matches": signal_matches,
            "original_candidates": original_candidates, "closeback_candidates": closeback_candidates,
            "entry_ok_bars": entry_ok_bars, "entry_ok_quote_matches": entry_ok_quote_matches,
            "quote_matches": quote_matches, "signal_match_pct": 100 * signal_matches / matched if matched else None,
            "quote_match_pct": 100 * quote_matches / matched if matched else None,
            "mean_atr_abs_error": sum(atr_errors) / len(atr_errors) if atr_errors else None,
            "max_atr_abs_error": max(atr_errors) if atr_errors else None,
            "max_channel_abs_error": max(channel_errors) if channel_errors else None,
            "signal_mismatch_examples": examples, "quote_mismatch_examples": quote_examples}


def restrict_window(snapshots: list[Snapshot], start: datetime, end: datetime) -> list[Snapshot]:
    if end <= start:
        raise ValueError("Invalid broker-time evaluation window")
    selected = [item for item in snapshots if start <= item.bar < end]
    if not selected:
        raise ValueError("No collector bars in broker-time evaluation window")
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("collector_dir", type=Path)
    parser.add_argument("--native-raw", type=Path)
    parser.add_argument("--from-broker")
    parser.add_argument("--to-broker")
    args = parser.parse_args()
    if bool(args.from_broker) != bool(args.to_broker):
        parser.error("--from-broker and --to-broker must be supplied together")
    bars = load_collector(args.collector_dir)
    snapshots, features = reconstruct(bars)
    evaluated = snapshots
    if args.from_broker:
        evaluated = restrict_window(snapshots, datetime.fromisoformat(args.from_broker),
                                    datetime.fromisoformat(args.to_broker))
    result = {"source": str(args.collector_dir), "first": bars[0].time.isoformat(),
              "last": bars[-1].time.isoformat(), "signal_screen": audit(evaluated)}
    if args.native_raw:
        result["native_parity"] = compare_native(snapshots, features, args.native_raw)
    print(json.dumps(result, indent=2, allow_nan=False))
