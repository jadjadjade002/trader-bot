"""Preregistered R3: contiguous-session VWAP statistical-fade proxy."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

try:
    from .analyze import Bar, ValidationError, gap_summary, load_csv
    from .analyze_r2 import metrics
except ImportError:  # Direct execution: python research/analyze_r3.py
    from analyze import Bar, ValidationError, gap_summary, load_csv
    from analyze_r2 import metrics


VARIANTS = (1.25, 1.50, 1.75)
NOMINAL = 1.50
MAX_ENTRY_SPREAD_POINTS = 40.0
HOLD_BARS = 3
RESEARCH_START = datetime(2025, 12, 8)
RESEARCH_END = datetime(2026, 3, 30)


@dataclass(frozen=True)
class SessionState:
    session_date: date
    count: int
    vwap: float
    sigma: float
    z: float
    median_abs_change_20: float
    decelerating: bool


@dataclass(frozen=True)
class R3Outcome:
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
    Fold("fold_1", datetime(2026, 1, 5), datetime(2026, 2, 2), datetime(2026, 2, 16)),
    Fold("fold_2", datetime(2026, 1, 19), datetime(2026, 2, 16), datetime(2026, 3, 2)),
    Fold("fold_3", datetime(2026, 2, 2), datetime(2026, 3, 2), datetime(2026, 3, 16)),
    Fold("fold_4", datetime(2026, 2, 16), datetime(2026, 3, 16), datetime(2026, 3, 30)),
)


def _session_date(moment: datetime) -> date | None:
    if moment.hour >= 18:
        return moment.date()
    if moment.hour < 2:
        return (moment - timedelta(days=1)).date()
    return None


def session_statistics(bars: Sequence[Bar]) -> list[SessionState | None]:
    """Calculate inclusive, causal VWAP states for uninterrupted sessions only."""
    result: list[SessionState | None] = [None] * len(bars)
    active_date: date | None = None
    valid = False
    prior_epoch: int | None = None
    prices: list[float] = []
    closes: list[float] = []
    total_weight = total_weighted_price = total_weighted_square = 0.0
    for index, bar in enumerate(bars):
        session_date = _session_date(bar.broker_time)
        if session_date is None:
            active_date = None
            valid = False
            prior_epoch = None
            prices = []
            closes = []
            total_weight = total_weighted_price = total_weighted_square = 0.0
            continue
        starts_session = bar.broker_time.hour == 18 and bar.broker_time.minute == 0
        if starts_session:
            active_date = session_date
            valid = True
            prior_epoch = None
            prices = []
            closes = []
            total_weight = total_weighted_price = total_weighted_square = 0.0
        elif active_date != session_date:
            valid = False
        if not valid:
            continue
        if prior_epoch is not None and bar.epoch - prior_epoch != 60:
            valid = False
            continue
        typical = (bar.high + bar.low + bar.close) / 3.0
        weight = float(bar.tick_volume)
        prices.append(typical)
        closes.append(bar.close)
        total_weight += weight
        total_weighted_price += weight * typical
        total_weighted_square += weight * typical * typical
        prior_epoch = bar.epoch
        if len(prices) < 30 or len(closes) < 21 or total_weight <= 0.0:
            continue
        vwap = total_weighted_price / total_weight
        variance = max(0.0, total_weighted_square / total_weight - vwap * vwap)
        sigma = math.sqrt(variance)
        changes = [abs(closes[pos] - closes[pos - 1]) for pos in range(len(closes) - 20, len(closes))]
        median_change = statistics.median(changes)
        if sigma <= 0.0 or median_change <= 0.0:
            continue
        current_change = abs(closes[-1] - closes[-2])
        result[index] = SessionState(
            session_date=session_date,
            count=len(prices),
            vwap=vwap,
            sigma=sigma,
            z=(bar.close - vwap) / sigma,
            median_abs_change_20=median_change,
            decelerating=current_change <= median_change,
        )
    return result


def signal_direction(bars: Sequence[Bar], states: Sequence[SessionState | None], index: int, threshold: float) -> int:
    if index < 3 or bars[index].epoch - bars[index - 3].epoch != 180:
        return 0
    state = states[index]
    if state is None or not state.decelerating:
        return 0
    if state.z <= -threshold and bars[index].close < bars[index - 3].close:
        return 1
    if state.z >= threshold and bars[index].close > bars[index - 3].close:
        return -1
    return 0


def in_entry_session(moment: datetime) -> bool:
    minute = moment.hour * 60 + moment.minute
    return minute >= 18 * 60 + 30 or minute < 117


def outcomes_for_window(
    bars: Sequence[Bar],
    states: Sequence[SessionState | None],
    threshold: float,
    point: float,
    entry_start: datetime,
    entry_end: datetime,
) -> list[R3Outcome]:
    outcomes: list[R3Outcome] = []
    last_exit = -1
    for signal in range(3, len(bars) - HOLD_BARS):
        entry_index, exit_index = signal + 1, signal + HOLD_BARS
        entry, exit_bar = bars[entry_index], bars[exit_index]
        if signal < last_exit or not (entry_start <= entry.broker_time < entry_end):
            continue
        if exit_bar.broker_time >= entry_end:
            continue
        if any(bars[pos].epoch - bars[pos - 1].epoch != 60 for pos in range(signal - 2, exit_index + 1)):
            continue
        if not in_entry_session(entry.broker_time) or entry.spread_points > MAX_ENTRY_SPREAD_POINTS:
            continue
        direction = signal_direction(bars, states, signal, threshold)
        if direction == 0:
            continue
        if direction > 0:
            gross = exit_bar.close - entry.open
            spread_cost = entry.spread_points * point
        else:
            gross = entry.open - exit_bar.close
            spread_cost = exit_bar.spread_points * point
        outcomes.append(
            R3Outcome(
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
    return outcomes


def _positive(metric: dict[str, object], field: str) -> bool:
    value = metric[field]
    return isinstance(value, (int, float)) and value > 0.0


def analyze_bars(bars: Sequence[Bar], point: float) -> dict[str, object]:
    if not math.isfinite(point) or point <= 0.0:
        raise ValidationError("point must be finite and positive")
    if any(bar.broker_time < RESEARCH_START or bar.broker_time >= RESEARCH_END for bar in bars):
        raise ValidationError("R3 input must be restricted to 2025-12-08 through 2026-03-29 broker time")
    states = session_statistics(bars)
    folds: list[dict[str, object]] = []
    aggregate: dict[float, list[R3Outcome]] = {variant: [] for variant in VARIANTS}
    all_viable = True
    for fold in FOLDS:
        training: dict[str, object] = {}
        for variant in VARIANTS:
            sample = outcomes_for_window(bars, states, variant, point, fold.train_start, fold.validation_start)
            training[f"{variant:.2f}"] = metrics(sample)
        viable = training[f"{NOMINAL:.2f}"]["trades"] >= 35
        all_viable = all_viable and viable
        validation: dict[str, object] | None = None
        if viable:
            validation = {}
            validation_start = fold.validation_start + timedelta(minutes=3)
            for variant in VARIANTS:
                sample = outcomes_for_window(bars, states, variant, point, validation_start, fold.validation_end)
                aggregate[variant].extend(sample)
                validation[f"{variant:.2f}"] = metrics(sample)
        folds.append(
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
        for fold in folds
        if fold["validation"] is not None and _positive(fold["validation"][f"{NOMINAL:.2f}"], "net")
    )
    each_fold_ten = all(
        fold["validation"] is not None and fold["validation"][f"{NOMINAL:.2f}"]["trades"] >= 10
        for fold in folds
    )
    pf = nominal["profit_factor"]
    concentration = nominal["max_positive_day_share"]
    gates = {
        "all_nominal_training_viability_guards_pass": all_viable,
        "nominal_validation_trades_at_least_70": nominal["trades"] >= 70,
        "each_nominal_validation_fold_at_least_10_trades": each_fold_ten,
        "nominal_validation_expectancy_positive": _positive(nominal, "expectancy"),
        "nominal_validation_profit_factor_at_least_1_10": bool(nominal["profit_factor_is_infinite"]) or (isinstance(pf, (int, float)) and pf >= 1.10),
        "nominal_validation_drawdown_at_most_20_percent": nominal["max_drawdown_percent"] <= 20.0,
        "at_least_three_positive_nominal_validation_folds": positive_folds >= 3,
        "nominal_max_positive_day_share_at_most_50_percent": isinstance(concentration, (int, float)) and concentration <= 0.50,
        "nominal_expectancy_positive_at_1_5x_spread": _positive(nominal_stress, "expectancy"),
        "loose_robustness_expectancy_positive": _positive(aggregate_metrics["1.25"], "expectancy"),
        "strict_robustness_expectancy_positive": _positive(aggregate_metrics["1.75"], "expectancy"),
    }
    valid_states = sum(state is not None for state in states)
    return {
        "schema_version": 1,
        "family": "R3_session_vwap_statistical_fade",
        "status": "exploratory_proxy_not_execution_backtest",
        "rows": len(bars),
        "input_gaps": gap_summary(bars),
        "valid_contiguous_session_states": valid_states,
        "rules": {
            "z_variants": list(VARIANTS),
            "nominal_z": NOMINAL,
            "minimum_session_bars": 30,
            "deceleration": "current_abs_close_change_lte_median_last_20_abs_close_changes",
            "entry": "next_consecutive_M1_open",
            "holding_bars": HOLD_BARS,
            "entry_session": "18:30-01:57_exclusive_broker_time",
            "max_entry_spread_points": MAX_ENTRY_SPREAD_POINTS,
            "validation_embargo_bars": 3,
            "spread_stress_multiplier": 1.5,
            "point": point,
        },
        "folds": folds,
        "aggregate_validation": aggregate_metrics,
        "aggregate_nominal_1_5x_spread": nominal_stress,
        "positive_nominal_validation_folds": positive_folds,
        "gates": gates,
        "overall_pass": all(gates.values()),
        "stopping_rule": "any failed gate abandons R3; no inversion, variant promotion, formula/session/date/exit/gate change",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--point", required=True, type=float)
    parser.add_argument("--output", type=Path, default=Path("research/results_r3.json"))
    args = parser.parse_args(argv)
    result = analyze_bars(load_csv(args.csv), args.point)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
