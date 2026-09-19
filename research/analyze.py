"""Caveman XAUUSD M1 research proxy.

The input is deliberately raw and small.  Features are calculated from completed
bars only; this is a research filter, not a replacement for an MT5 backtest.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


CSV_COLUMNS = (
    "time_broker_epoch",
    "time_broker_iso",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread_points",
    "real_volume",
)
THRESHOLDS = (0.75, 1.0, 1.25)
ATR_PERIOD = 14
TRAIN_FRACTION = 0.70
EMBARGO_BARS = 3
HOLD_BARS = 3
STARTING_EQUITY = 50.0
MIN_TOTAL_TRADES = 140
MIN_TRAIN_TRADES = 98
MIN_VALIDATION_TRADES = 42


class ValidationError(ValueError):
    """Raised when the raw export is not safe to analyze."""


@dataclass(frozen=True)
class Bar:
    epoch: int
    broker_time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread_points: float
    real_volume: int


@dataclass(frozen=True)
class Outcome:
    signal_index: int
    entry_index: int
    exit_index: int
    direction: int
    pnl: float
    exit_day: str


def _finite_float(value: str, field: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"row {row_number}: {field} is not numeric") from exc
    if not math.isfinite(parsed):
        raise ValidationError(f"row {row_number}: {field} is not finite")
    return parsed


def _nonnegative_int(value: str, field: str, row_number: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"row {row_number}: {field} is not an integer") from exc
    if parsed < 0:
        raise ValidationError(f"row {row_number}: {field} is negative")
    return parsed


def load_csv(path: Path) -> list[Bar]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValidationError(
                "CSV header must exactly equal: " + ",".join(CSV_COLUMNS)
            )
        bars: list[Bar] = []
        previous_epoch: int | None = None
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(row[column] is None for column in CSV_COLUMNS):
                raise ValidationError(f"row {row_number}: wrong number of columns")
            epoch = _nonnegative_int(row["time_broker_epoch"], "time_broker_epoch", row_number)
            if epoch % 60:
                raise ValidationError(f"row {row_number}: timestamp is not M1-aligned")
            try:
                broker_time = datetime.fromisoformat(row["time_broker_iso"])
            except ValueError as exc:
                raise ValidationError(f"row {row_number}: invalid broker ISO time") from exc
            if broker_time.second or broker_time.microsecond:
                raise ValidationError(f"row {row_number}: broker time is not M1-aligned")
            if previous_epoch is not None:
                delta = epoch - previous_epoch
                if delta <= 0:
                    raise ValidationError(f"row {row_number}: timestamps are not strictly increasing")
                if delta % 60:
                    raise ValidationError(f"row {row_number}: timestamp gap is not whole M1 bars")
            prices = {
                key: _finite_float(row[key], key, row_number)
                for key in ("open", "high", "low", "close")
            }
            if any(value <= 0.0 for value in prices.values()):
                raise ValidationError(f"row {row_number}: prices must be positive")
            if not (
                prices["low"] <= prices["open"] <= prices["high"]
                and prices["low"] <= prices["close"] <= prices["high"]
            ):
                raise ValidationError(f"row {row_number}: inconsistent OHLC values")
            spread = _finite_float(row["spread_points"], "spread_points", row_number)
            if spread < 0.0:
                raise ValidationError(f"row {row_number}: spread_points is negative")
            bars.append(
                Bar(
                    epoch=epoch,
                    broker_time=broker_time,
                    open=prices["open"],
                    high=prices["high"],
                    low=prices["low"],
                    close=prices["close"],
                    tick_volume=_nonnegative_int(row["tick_volume"], "tick_volume", row_number),
                    spread_points=spread,
                    real_volume=_nonnegative_int(row["real_volume"], "real_volume", row_number),
                )
            )
            previous_epoch = epoch
    if not bars:
        raise ValidationError("CSV contains no data rows")
    return bars


def wilder_atr14(bars: Sequence[Bar]) -> list[float | None]:
    """Return causal Wilder ATR(14), aligned with each completed bar."""
    result: list[float | None] = [None] * len(bars)
    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        if index == 0:
            true_range = bar.high - bar.low
        else:
            previous_close = bars[index - 1].close
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(true_range)
        if index == ATR_PERIOD - 1:
            result[index] = sum(true_ranges) / ATR_PERIOD
        elif index >= ATR_PERIOD:
            prior = result[index - 1]
            assert prior is not None
            result[index] = (prior * (ATR_PERIOD - 1) + true_range) / ATR_PERIOD
    return result


def in_entry_session(moment: datetime) -> bool:
    minutes = moment.hour * 60 + moment.minute
    return minutes >= 18 * 60 or minutes < 1 * 60 + 57


def _consecutive(bars: Sequence[Bar], first: int, last: int) -> bool:
    return all(bars[index].epoch - bars[index - 1].epoch == 60 for index in range(first + 1, last + 1))


def outcomes_for_range(
    bars: Sequence[Bar],
    atr: Sequence[float | None],
    threshold: float,
    point: float,
    signal_start: int,
    signal_stop: int,
) -> list[Outcome]:
    """Build non-overlapping next-open/three-bar-close proxy outcomes."""
    outcomes: list[Outcome] = []
    last_exit = -1
    upper = min(signal_stop, len(bars) - HOLD_BARS)
    for signal_index in range(max(signal_start, ATR_PERIOD - 1), upper):
        if signal_index < last_exit:
            continue
        entry_index = signal_index + 1
        exit_index = signal_index + HOLD_BARS
        if not _consecutive(bars, signal_index, exit_index):
            continue
        if not in_entry_session(bars[entry_index].broker_time):
            continue
        value = atr[signal_index]
        bar = bars[signal_index]
        candle_range = bar.high - bar.low
        if value is None or value <= 0.0 or candle_range <= 0.0:
            continue
        body = bar.close - bar.open
        close_location = (bar.close - bar.low) / candle_range
        direction = 0
        if body >= threshold * value and close_location >= 0.80:
            direction = 1
        elif -body >= threshold * value and close_location <= 0.20:
            direction = -1
        if direction == 0:
            continue
        entry = bars[entry_index]
        exit_bar = bars[exit_index]
        if direction > 0:
            pnl = exit_bar.close - (entry.open + entry.spread_points * point)
        else:
            pnl = entry.open - (exit_bar.close + exit_bar.spread_points * point)
        outcomes.append(
            Outcome(
                signal_index=signal_index,
                entry_index=entry_index,
                exit_index=exit_index,
                direction=direction,
                pnl=pnl,
                exit_day=exit_bar.broker_time.date().isoformat(),
            )
        )
        last_exit = exit_index
    return outcomes


def metrics(outcomes: Iterable[Outcome]) -> dict[str, object]:
    sample = list(outcomes)
    pnls = [item.pnl for item in sample]
    gains = sum(value for value in pnls if value > 0.0)
    losses = -sum(value for value in pnls if value < 0.0)
    net = sum(pnls)
    peak = STARTING_EQUITY
    equity = STARTING_EQUITY
    maximum_drawdown = 0.0
    daily: dict[str, float] = {}
    for item in sample:
        equity += item.pnl
        peak = max(peak, equity)
        if peak > 0.0:
            maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak * 100.0)
        daily[item.exit_day] = daily.get(item.exit_day, 0.0) + item.pnl
    positive_daily = sum(value for value in daily.values() if value > 0.0)
    concentration = (
        max((value for value in daily.values() if value > 0.0), default=0.0) / positive_daily
        if positive_daily > 0.0
        else None
    )
    return {
        "trades": len(sample),
        "net": net,
        "expectancy": net / len(sample) if sample else None,
        "profit_factor": gains / losses if losses > 0.0 else None,
        "profit_factor_is_infinite": bool(gains > 0.0 and losses == 0.0),
        "max_drawdown_percent": maximum_drawdown,
        "max_positive_day_share": concentration,
    }


def _pf_pass(value: dict[str, object]) -> bool:
    profit_factor = value["profit_factor"]
    return bool(value["profit_factor_is_infinite"]) or (
        isinstance(profit_factor, (int, float)) and profit_factor >= 1.10
    )


def gap_summary(bars: Sequence[Bar]) -> dict[str, int]:
    """Describe missing whole M1 bars without modifying the input sequence."""
    missing_by_gap = [
        (bars[index].epoch - bars[index - 1].epoch) // 60 - 1
        for index in range(1, len(bars))
        if bars[index].epoch - bars[index - 1].epoch > 60
    ]
    return {
        "count": len(missing_by_gap),
        "missing_whole_minutes": sum(missing_by_gap),
        "max_gap_minutes": max(missing_by_gap, default=0),
    }


def analyze_bars(bars: Sequence[Bar], point: float) -> dict[str, object]:
    if not math.isfinite(point) or point <= 0.0:
        raise ValidationError("point must be finite and positive")
    split_index = int(len(bars) * TRAIN_FRACTION)
    train_signal_stop = max(0, split_index - EMBARGO_BARS)
    validation_signal_start = min(len(bars), split_index + EMBARGO_BARS)
    atr = wilder_atr14(bars)
    attempts: list[dict[str, object]] = []
    for threshold in THRESHOLDS:
        train_outcomes = outcomes_for_range(
            bars, atr, threshold, point, 0, train_signal_stop
        )
        attempts.append(
            {
                "threshold_atr": threshold,
                "training": metrics(train_outcomes),
                "validation": None,
            }
        )
    selected = max(
        attempts,
        key=lambda item: (
            item["training"]["expectancy"]
            if item["training"]["expectancy"] is not None
            else -math.inf,
            -item["threshold_atr"],
        ),
    )
    selected_validation_outcomes = outcomes_for_range(
        bars,
        atr,
        selected["threshold_atr"],
        point,
        validation_signal_start,
        len(bars),
    )
    selected["validation"] = metrics(selected_validation_outcomes)
    training = selected["training"]
    validation = selected["validation"]
    total_trades = training["trades"] + validation["trades"]
    concentration = validation["max_positive_day_share"]
    gates = {
        "training_trades_at_least_98": training["trades"] >= MIN_TRAIN_TRADES,
        "validation_trades_at_least_42": validation["trades"] >= MIN_VALIDATION_TRADES,
        "total_trades_at_least_140": total_trades >= MIN_TOTAL_TRADES,
        "validation_expectancy_positive": (
            validation["expectancy"] is not None and validation["expectancy"] > 0.0
        ),
        "validation_profit_factor_at_least_1_10": _pf_pass(validation),
        "validation_drawdown_at_most_20_percent": validation["max_drawdown_percent"] <= 20.0,
        "validation_max_positive_day_share_at_most_50_percent": (
            concentration is not None and concentration <= 0.50
        ),
    }
    return {
        "schema_version": 1,
        "research_status": "exploratory_proxy_not_execution_backtest",
        "rules": {
            "thresholds_atr": list(THRESHOLDS),
            "atr": "causal_wilder_14",
            "entry": "next_bar_open",
            "holding_bars": HOLD_BARS,
            "non_overlapping": True,
            "session_broker_time": "18:00-01:57_exclusive",
            "spread_adjustment": "entry_ask_for_long_exit_ask_for_short",
            "point": point,
        },
        "rows": len(bars),
        "input_gaps": gap_summary(bars),
        "split": {
            "training_fraction": TRAIN_FRACTION,
            "split_index": split_index,
            "training_signal_stop_exclusive": train_signal_stop,
            "embargo_bars": EMBARGO_BARS,
            "validation_signal_start": validation_signal_start,
        },
        "attempts": attempts,
        "selected_threshold_atr": selected["threshold_atr"],
        "selection_rule": "highest_training_expectancy_tie_lower_threshold",
        "gates": gates,
        "overall_pass": all(gates.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="validated raw M1 export")
    parser.add_argument("--point", type=float, required=True, help="symbol point size")
    parser.add_argument("--output", type=Path, default=Path("research/results.json"))
    args = parser.parse_args(argv)
    result = analyze_bars(load_csv(args.csv), args.point)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
