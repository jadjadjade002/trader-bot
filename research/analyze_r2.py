"""Preregistered R2: causal M15/M5/M1 trend-pullback continuation proxy."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

try:
    from .analyze import Bar, ValidationError, gap_summary, load_csv
except ImportError:  # Direct execution: python research/analyze_r2.py
    from analyze import Bar, ValidationError, gap_summary, load_csv


VARIANTS = (0.05, 0.10, 0.15)
NOMINAL = 0.10
POINT_MAX_SPREAD = 40.0
HOLD_BARS = 3
STARTING_EQUITY = 50.0
RESEARCH_START = datetime(2026, 4, 6)
RESEARCH_END = datetime(2026, 7, 27)


@dataclass(frozen=True)
class HigherBar:
    start_epoch: int
    end_epoch: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class R2Outcome:
    signal_index: int
    entry_index: int
    exit_index: int
    direction: int
    pnl: float
    stress_pnl: float
    exit_day: str


@dataclass(frozen=True)
class Fold:
    name: str
    train_start: datetime
    validation_start: datetime
    validation_end: datetime


FOLDS = (
    Fold("fold_1", datetime(2026, 5, 4), datetime(2026, 6, 1), datetime(2026, 6, 15)),
    Fold("fold_2", datetime(2026, 5, 18), datetime(2026, 6, 15), datetime(2026, 6, 29)),
    Fold("fold_3", datetime(2026, 6, 1), datetime(2026, 6, 29), datetime(2026, 7, 13)),
    Fold("fold_4", datetime(2026, 6, 15), datetime(2026, 7, 13), datetime(2026, 7, 27)),
)


def aggregate_complete(bars: Sequence[Bar], minutes: int) -> list[HigherBar]:
    """Aggregate only buckets containing every aligned M1 constituent."""
    if minutes not in (5, 15):
        raise ValueError("only M5 and M15 aggregation is supported")
    width = minutes * 60
    grouped: dict[int, list[Bar]] = {}
    for bar in bars:
        start = bar.epoch - bar.epoch % width
        grouped.setdefault(start, []).append(bar)
    result: list[HigherBar] = []
    for start in sorted(grouped):
        sample = grouped[start]
        expected = [start + offset * 60 for offset in range(minutes)]
        if len(sample) != minutes or [bar.epoch for bar in sample] != expected:
            continue
        result.append(
            HigherBar(
                start_epoch=start,
                end_epoch=start + width,
                open=sample[0].open,
                high=max(bar.high for bar in sample),
                low=min(bar.low for bar in sample),
                close=sample[-1].close,
            )
        )
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    result[period - 1] = sum(values[:period]) / period
    alpha = 2.0 / (period + 1.0)
    for index in range(period, len(values)):
        prior = result[index - 1]
        assert prior is not None
        result[index] = alpha * values[index] + (1.0 - alpha) * prior
    return result


def wilder_atr(bars: Sequence[HigherBar], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(bars)
    ranges: list[float] = []
    for index, bar in enumerate(bars):
        if index == 0:
            value = bar.high - bar.low
        else:
            prior_close = bars[index - 1].close
            value = max(bar.high - bar.low, abs(bar.high - prior_close), abs(bar.low - prior_close))
        ranges.append(value)
        if index == period - 1:
            result[index] = sum(ranges) / period
        elif index >= period:
            prior = result[index - 1]
            assert prior is not None
            result[index] = (prior * (period - 1) + value) / period
    return result


def latest_complete_index(bars: Sequence[HigherBar], decision_epoch: int, minutes: int) -> int | None:
    """Return a fresh completed bucket, never a stale or still-forming one."""
    expected_end = decision_epoch - decision_epoch % (minutes * 60)
    low, high = 0, len(bars)
    while low < high:
        middle = (low + high) // 2
        if bars[middle].end_epoch <= decision_epoch:
            low = middle + 1
        else:
            high = middle
    index = low - 1
    if index < 0 or bars[index].end_epoch != expected_end:
        return None
    return index


def trend_direction(
    m15: Sequence[HigherBar],
    index: int,
    ema20: Sequence[float | None],
    ema50: Sequence[float | None],
    atr14: Sequence[float | None],
    separation: float,
) -> int:
    if index < 2 or m15[index].start_epoch - m15[index - 2].start_epoch != 1800:
        return 0
    e20, e20_prior, e50, atr = ema20[index], ema20[index - 2], ema50[index], atr14[index]
    if e20 is None or e20_prior is None or e50 is None or atr is None or atr <= 0.0:
        return 0
    close = m15[index].close
    if close > e20 > e50 and e20 > e20_prior and (e20 - e50) / atr >= separation:
        return 1
    if close < e20 < e50 and e20 < e20_prior and (e50 - e20) / atr >= separation:
        return -1
    return 0


def pullback_ok(m5: Sequence[HigherBar], index: int, direction: int, e20: float, e50: float) -> bool:
    if index < 1 or m5[index].start_epoch - m5[index - 1].start_epoch != 300:
        return False
    recent, prior = m5[index], m5[index - 1]
    if direction > 0:
        low = min(recent.low, prior.low)
        return low <= e20 and low > e50 and recent.close >= e20
    if direction < 0:
        high = max(recent.high, prior.high)
        return high >= e20 and high < e50 and recent.close <= e20
    return False


def m1_reacceleration(bars: Sequence[Bar], index: int, direction: int) -> bool:
    if index < 2 or bars[index].epoch - bars[index - 2].epoch != 120:
        return False
    bar = bars[index]
    width = bar.high - bar.low
    if width <= 0.0:
        return False
    location = (bar.close - bar.low) / width
    if direction > 0:
        return bar.close > bar.open and bar.close > max(bars[index - 1].high, bars[index - 2].high) and location >= 0.70
    if direction < 0:
        return bar.close < bar.open and bar.close < min(bars[index - 1].low, bars[index - 2].low) and location <= 0.30
    return False


def in_session(moment: datetime) -> bool:
    minute = moment.hour * 60 + moment.minute
    return minute >= 18 * 60 or minute < 117


def outcomes_for_window(
    bars: Sequence[Bar],
    m5: Sequence[HigherBar],
    m15: Sequence[HigherBar],
    ema20: Sequence[float | None],
    ema50: Sequence[float | None],
    atr14: Sequence[float | None],
    separation: float,
    point: float,
    entry_start: datetime,
    entry_end: datetime,
) -> list[R2Outcome]:
    results: list[R2Outcome] = []
    last_exit = -1
    for signal in range(2, len(bars) - HOLD_BARS):
        entry_index, exit_index = signal + 1, signal + HOLD_BARS
        entry = bars[entry_index]
        exit_bar = bars[exit_index]
        if signal < last_exit or not (entry_start <= entry.broker_time < entry_end):
            continue
        if exit_bar.broker_time >= entry_end:
            continue
        if any(bars[i].epoch - bars[i - 1].epoch != 60 for i in range(signal - 1, exit_index + 1)):
            continue
        if not in_session(entry.broker_time) or entry.spread_points > POINT_MAX_SPREAD:
            continue
        decision_epoch = bars[signal].epoch + 60
        i15 = latest_complete_index(m15, decision_epoch, 15)
        i5 = latest_complete_index(m5, decision_epoch, 5)
        if i15 is None or i5 is None:
            continue
        direction = trend_direction(m15, i15, ema20, ema50, atr14, separation)
        e20, e50 = ema20[i15], ema50[i15]
        if direction == 0 or e20 is None or e50 is None:
            continue
        if not pullback_ok(m5, i5, direction, e20, e50) or not m1_reacceleration(bars, signal, direction):
            continue
        if direction > 0:
            gross = exit_bar.close - entry.open
            spread_cost = entry.spread_points * point
        else:
            gross = entry.open - exit_bar.close
            spread_cost = exit_bar.spread_points * point
        results.append(
            R2Outcome(
                signal,
                entry_index,
                exit_index,
                direction,
                gross - spread_cost,
                gross - 1.5 * spread_cost,
                exit_bar.broker_time.date().isoformat(),
            )
        )
        last_exit = exit_index
    return results


def metrics(outcomes: Iterable[R2Outcome], stressed: bool = False) -> dict[str, object]:
    sample = list(outcomes)
    pnls = [item.stress_pnl if stressed else item.pnl for item in sample]
    gains = sum(value for value in pnls if value > 0.0)
    losses = -sum(value for value in pnls if value < 0.0)
    equity = peak = STARTING_EQUITY
    drawdown = 0.0
    daily: dict[str, float] = {}
    for item, pnl in zip(sample, pnls):
        equity += pnl
        peak = max(peak, equity)
        if peak > 0.0:
            drawdown = max(drawdown, (peak - equity) / peak * 100.0)
        daily[item.exit_day] = daily.get(item.exit_day, 0.0) + pnl
    net = sum(pnls)
    positive_days = sum(value for value in daily.values() if value > 0.0)
    concentration = max((value for value in daily.values() if value > 0.0), default=0.0) / positive_days if positive_days else None
    return {
        "trades": len(sample),
        "net": net,
        "expectancy": net / len(sample) if sample else None,
        "profit_factor": gains / losses if losses else None,
        "profit_factor_is_infinite": gains > 0.0 and losses == 0.0,
        "max_drawdown_percent": drawdown,
        "max_positive_day_share": concentration,
    }


def _metric_positive(value: dict[str, object], field: str) -> bool:
    item = value[field]
    return isinstance(item, (int, float)) and item > 0.0


def analyze_bars(bars: Sequence[Bar], point: float) -> dict[str, object]:
    if not math.isfinite(point) or point <= 0.0:
        raise ValidationError("point must be finite and positive")
    if any(bar.broker_time < RESEARCH_START or bar.broker_time >= RESEARCH_END for bar in bars):
        raise ValidationError("R2 input must be restricted to 2026-04-06 through 2026-07-26 broker time")
    m5, m15 = aggregate_complete(bars, 5), aggregate_complete(bars, 15)
    closes = [bar.close for bar in m15]
    e20, e50, atr = ema(closes, 20), ema(closes, 50), wilder_atr(m15)
    fold_results: list[dict[str, object]] = []
    aggregate: dict[float, list[R2Outcome]] = {variant: [] for variant in VARIANTS}
    viability_passed = True
    for fold in FOLDS:
        training: dict[str, object] = {}
        for variant in VARIANTS:
            sample = outcomes_for_window(
                bars, m5, m15, e20, e50, atr, variant, point, fold.train_start, fold.validation_start
            )
            training[f"{variant:.2f}"] = metrics(sample)
        viable = training[f"{NOMINAL:.2f}"]["trades"] >= 35
        viability_passed = viability_passed and viable
        validation: dict[str, object] | None = None
        if viable:
            validation = {}
            validation_start = fold.validation_start + timedelta(minutes=3)
            for variant in VARIANTS:
                sample = outcomes_for_window(
                    bars, m5, m15, e20, e50, atr, variant, point, validation_start, fold.validation_end
                )
                aggregate[variant].extend(sample)
                validation[f"{variant:.2f}"] = metrics(sample)
        fold_results.append(
            {
                "name": fold.name,
                "train_start": fold.train_start.isoformat(),
                "validation_start_after_embargo": (fold.validation_start + timedelta(minutes=3)).isoformat(),
                "validation_end_exclusive": fold.validation_end.isoformat(),
                "nominal_viability_pass": viable,
                "training": training,
                "validation": validation,
            }
        )
    aggregate_metrics = {f"{variant:.2f}": metrics(aggregate[variant]) for variant in VARIANTS}
    nominal = aggregate_metrics[f"{NOMINAL:.2f}"]
    nominal_stress = metrics(aggregate[NOMINAL], stressed=True)
    positive_folds = sum(
        1
        for fold in fold_results
        if fold["validation"] is not None and _metric_positive(fold["validation"][f"{NOMINAL:.2f}"], "net")
    )
    pf = nominal["profit_factor"]
    concentration = nominal["max_positive_day_share"]
    gates = {
        "all_nominal_training_viability_guards_pass": viability_passed,
        "nominal_validation_trades_at_least_140": nominal["trades"] >= 140,
        "nominal_validation_expectancy_positive": _metric_positive(nominal, "expectancy"),
        "nominal_validation_profit_factor_at_least_1_10": bool(nominal["profit_factor_is_infinite"]) or (isinstance(pf, (int, float)) and pf >= 1.10),
        "nominal_validation_drawdown_at_most_20_percent": nominal["max_drawdown_percent"] <= 20.0,
        "at_least_three_positive_validation_folds": positive_folds >= 3,
        "nominal_max_positive_day_share_at_most_50_percent": isinstance(concentration, (int, float)) and concentration <= 0.50,
        "nominal_expectancy_positive_at_1_5x_spread": _metric_positive(nominal_stress, "expectancy"),
        "loose_robustness_expectancy_positive": _metric_positive(aggregate_metrics["0.05"], "expectancy"),
        "strict_robustness_expectancy_positive": _metric_positive(aggregate_metrics["0.15"], "expectancy"),
    }
    return {
        "schema_version": 1,
        "family": "R2_trend_pullback_continuation",
        "status": "exploratory_proxy_not_execution_backtest",
        "rows": len(bars),
        "input_gaps": gap_summary(bars),
        "complete_buckets": {"M5": len(m5), "M15": len(m15)},
        "rules": {
            "variants_m15_ema_separation_atr": list(VARIANTS),
            "nominal_variant": NOMINAL,
            "entry": "next_consecutive_M1_open",
            "holding_bars": HOLD_BARS,
            "session": "18:00-01:57_exclusive_broker_time",
            "max_entry_spread_points": POINT_MAX_SPREAD,
            "validation_embargo_bars": 3,
            "spread_stress_multiplier": 1.5,
            "point": point,
        },
        "folds": fold_results,
        "aggregate_validation": aggregate_metrics,
        "aggregate_nominal_1_5x_spread": nominal_stress,
        "positive_nominal_validation_folds": positive_folds,
        "gates": gates,
        "overall_pass": all(gates.values()),
        "stopping_rule": "any failed gate abandons R2; no inversion, threshold promotion, formula/date/session/exit/gate change",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--point", required=True, type=float)
    parser.add_argument("--output", type=Path, default=Path("research/results_r2.json"))
    args = parser.parse_args(argv)
    result = analyze_bars(load_csv(args.csv), args.point)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
