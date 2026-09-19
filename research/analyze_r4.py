"""Preregistered final R4: causal M1 EMA state-transition proxy."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

try:
    from .analyze import Bar, ValidationError, gap_summary, load_csv
    from .analyze_r2 import metrics
except ImportError:  # Direct execution: python research/analyze_r4.py
    from analyze import Bar, ValidationError, gap_summary, load_csv
    from analyze_r2 import metrics


PAIRS = ((5, 20), (6, 24), (8, 32))
NOMINAL = (6, 24)
MAX_ENTRY_SPREAD_POINTS = 40.0
HOLD_BARS = 3
RESEARCH_START = datetime(2025, 8, 11)
RESEARCH_END = datetime(2025, 12, 1)


@dataclass(frozen=True)
class R4Outcome:
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
    Fold("fold_1", datetime(2025, 9, 8), datetime(2025, 10, 6), datetime(2025, 10, 20)),
    Fold("fold_2", datetime(2025, 9, 22), datetime(2025, 10, 20), datetime(2025, 11, 3)),
    Fold("fold_3", datetime(2025, 10, 6), datetime(2025, 11, 3), datetime(2025, 11, 17)),
    Fold("fold_4", datetime(2025, 10, 20), datetime(2025, 11, 17), datetime(2025, 12, 1)),
)


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


def wilder_atr14(bars: Sequence[Bar]) -> list[float | None]:
    result: list[float | None] = [None] * len(bars)
    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        if index == 0:
            true_range = bar.high - bar.low
        else:
            prior_close = bars[index - 1].close
            true_range = max(bar.high - bar.low, abs(bar.high - prior_close), abs(bar.low - prior_close))
        true_ranges.append(true_range)
        if index == 13:
            result[index] = sum(true_ranges) / 14.0
        elif index >= 14:
            prior = result[index - 1]
            assert prior is not None
            result[index] = (prior * 13.0 + true_range) / 14.0
    return result


def pair_key(pair: tuple[int, int]) -> str:
    return f"{pair[0]}/{pair[1]}"


def signal_direction(
    bars: Sequence[Bar],
    fast: Sequence[float | None],
    slow: Sequence[float | None],
    atr14: Sequence[float | None],
    index: int,
) -> int:
    if index < 120:
        return 0
    if any(bars[pos].epoch - bars[pos - 1].epoch != 60 for pos in range(index - 118, index + 1)):
        return 0
    atr_window = atr14[index - 119 : index + 1]
    if len(atr_window) != 120 or any(value is None or value <= 0.0 for value in atr_window):
        return 0
    current_atr = atr14[index]
    assert current_atr is not None
    median_atr = statistics.median(value for value in atr_window if value is not None)
    if median_atr <= 0.0:
        return 0
    volatility_ratio = current_atr / median_atr
    current_fast, prior_fast = fast[index], fast[index - 1]
    current_slow, prior_slow = slow[index], slow[index - 1]
    if None in (current_fast, prior_fast, current_slow, prior_slow):
        return 0
    if not (0.50 <= volatility_ratio <= 1.50):
        return 0
    bar = bars[index]
    if abs(bar.close - current_slow) > 0.35 * current_atr or bar.high - bar.low > 1.50 * current_atr:
        return 0
    if current_fast > current_slow and prior_fast <= prior_slow:
        return 1
    if current_fast < current_slow and prior_fast >= prior_slow:
        return -1
    return 0


def in_entry_session(moment: datetime) -> bool:
    minute = moment.hour * 60 + moment.minute
    return minute >= 18 * 60 or minute < 117


def outcomes_for_window(
    bars: Sequence[Bar],
    fast: Sequence[float | None],
    slow: Sequence[float | None],
    atr14: Sequence[float | None],
    point: float,
    entry_start: datetime,
    entry_end: datetime,
) -> list[R4Outcome]:
    outcomes: list[R4Outcome] = []
    last_exit = -1
    for signal in range(120, len(bars) - HOLD_BARS):
        entry_index, exit_index = signal + 1, signal + HOLD_BARS
        entry, exit_bar = bars[entry_index], bars[exit_index]
        if signal < last_exit or not (entry_start <= entry.broker_time < entry_end):
            continue
        if exit_bar.broker_time >= entry_end:
            continue
        if any(bars[pos].epoch - bars[pos - 1].epoch != 60 for pos in range(signal, exit_index + 1)):
            continue
        if not in_entry_session(entry.broker_time) or entry.spread_points > MAX_ENTRY_SPREAD_POINTS:
            continue
        direction = signal_direction(bars, fast, slow, atr14, signal)
        if direction == 0:
            continue
        if direction > 0:
            gross = exit_bar.close - entry.open
            spread_cost = entry.spread_points * point
        else:
            gross = entry.open - exit_bar.close
            spread_cost = exit_bar.spread_points * point
        outcomes.append(
            R4Outcome(
                signal,
                entry_index,
                exit_index,
                direction,
                gross - spread_cost,
                gross - 2.0 * spread_cost,
                exit_bar.broker_time.date().isoformat(),
            )
        )
        last_exit = exit_index
    return outcomes


def daily_evidence(outcomes: Sequence[R4Outcome]) -> dict[str, object]:
    daily: dict[str, float] = {}
    for outcome in outcomes:
        daily[outcome.exit_day] = daily.get(outcome.exit_day, 0.0) + outcome.pnl
    values = list(daily.values())
    t_statistic: float | None = None
    if len(values) >= 2:
        sample_deviation = statistics.stdev(values)
        if sample_deviation > 0.0:
            t_statistic = statistics.mean(values) / (sample_deviation / math.sqrt(len(values)))
    return {"days": len(values), "daily_net_t_statistic": t_statistic}


def _positive(metric: dict[str, object], field: str) -> bool:
    value = metric[field]
    return isinstance(value, (int, float)) and value > 0.0


def _pf_at_least(metric: dict[str, object], threshold: float) -> bool:
    value = metric["profit_factor"]
    return bool(metric["profit_factor_is_infinite"]) or (isinstance(value, (int, float)) and value >= threshold)


def analyze_bars(bars: Sequence[Bar], point: float) -> dict[str, object]:
    if not math.isfinite(point) or point <= 0.0:
        raise ValidationError("point must be finite and positive")
    if any(bar.broker_time < RESEARCH_START or bar.broker_time >= RESEARCH_END for bar in bars):
        raise ValidationError("R4 input must be restricted to 2025-08-11 through 2025-11-30 broker time")
    closes = [bar.close for bar in bars]
    pair_indicators = {pair: (ema(closes, pair[0]), ema(closes, pair[1])) for pair in PAIRS}
    atr = wilder_atr14(bars)
    folds: list[dict[str, object]] = []
    aggregate: dict[tuple[int, int], list[R4Outcome]] = {pair: [] for pair in PAIRS}
    all_viable = True
    for fold in FOLDS:
        training: dict[str, object] = {}
        for pair in PAIRS:
            fast, slow = pair_indicators[pair]
            sample = outcomes_for_window(bars, fast, slow, atr, point, fold.train_start, fold.validation_start)
            training[pair_key(pair)] = metrics(sample)
        viable = training[pair_key(NOMINAL)]["trades"] >= 35
        all_viable = all_viable and viable
        validation: dict[str, object] | None = None
        if viable:
            validation = {}
            validation_start = fold.validation_start + timedelta(minutes=3)
            for pair in PAIRS:
                fast, slow = pair_indicators[pair]
                sample = outcomes_for_window(bars, fast, slow, atr, point, validation_start, fold.validation_end)
                aggregate[pair].extend(sample)
                validation[pair_key(pair)] = metrics(sample)
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
    aggregate_metrics = {pair_key(pair): metrics(aggregate[pair]) for pair in PAIRS}
    nominal_key = pair_key(NOMINAL)
    nominal = aggregate_metrics[nominal_key]
    nominal_stress = metrics(aggregate[NOMINAL], stressed=True)
    evidence = daily_evidence(aggregate[NOMINAL])
    nominal_fold_positive = sum(
        1 for fold in folds
        if fold["validation"] is not None and _positive(fold["validation"][nominal_key], "net")
    )
    each_nominal_ten = all(
        fold["validation"] is not None and fold["validation"][nominal_key]["trades"] >= 10
        for fold in folds
    )
    robustness_gates: dict[str, bool] = {}
    robustness_fold_counts: dict[str, int] = {}
    for pair in (PAIRS[0], PAIRS[2]):
        key = pair_key(pair)
        positive_folds = sum(
            1 for fold in folds
            if fold["validation"] is not None and _positive(fold["validation"][key], "net")
        )
        robustness_fold_counts[key] = positive_folds
        robustness_gates[f"robustness_{key}_trades_at_least_50"] = aggregate_metrics[key]["trades"] >= 50
        robustness_gates[f"robustness_{key}_expectancy_positive"] = _positive(aggregate_metrics[key], "expectancy")
        robustness_gates[f"robustness_{key}_profit_factor_at_least_1_10"] = _pf_at_least(aggregate_metrics[key], 1.10)
        robustness_gates[f"robustness_{key}_at_least_three_positive_folds"] = positive_folds >= 3
    concentration = nominal["max_positive_day_share"]
    t_statistic = evidence["daily_net_t_statistic"]
    gates = {
        "all_nominal_training_viability_guards_pass": all_viable,
        "nominal_validation_trades_at_least_70": nominal["trades"] >= 70,
        "each_nominal_validation_fold_at_least_10_trades": each_nominal_ten,
        "all_four_nominal_validation_folds_positive": nominal_fold_positive == 4,
        "nominal_validation_expectancy_positive": _positive(nominal, "expectancy"),
        "nominal_validation_profit_factor_at_least_1_20": _pf_at_least(nominal, 1.20),
        "nominal_validation_drawdown_at_most_15_percent": nominal["max_drawdown_percent"] <= 15.0,
        "nominal_max_positive_day_share_at_most_35_percent": isinstance(concentration, (int, float)) and concentration <= 0.35,
        "nominal_expectancy_positive_at_2x_spread": _positive(nominal_stress, "expectancy"),
        "nominal_daily_evidence_at_least_20_days": evidence["days"] >= 20,
        "nominal_daily_net_t_statistic_at_least_2_50": isinstance(t_statistic, (int, float)) and t_statistic >= 2.50,
        **robustness_gates,
    }
    return {
        "schema_version": 1,
        "family": "R4_M1_EMA_state_transition",
        "status": "exploratory_proxy_not_execution_backtest",
        "rows": len(bars),
        "input_gaps": gap_summary(bars),
        "rules": {
            "ema_pairs": [list(pair) for pair in PAIRS],
            "nominal_pair": list(NOMINAL),
            "atr": "Wilder_14",
            "atr_median_window_consecutive_bars": 120,
            "volatility_ratio_bounds_inclusive": [0.50, 1.50],
            "max_close_distance_from_slow_atr": 0.35,
            "max_signal_range_atr": 1.50,
            "entry": "next_consecutive_M1_open",
            "holding_bars": HOLD_BARS,
            "entry_session": "18:00-01:57_exclusive_broker_time",
            "max_entry_spread_points": MAX_ENTRY_SPREAD_POINTS,
            "spread_stress_multiplier": 2.0,
            "validation_embargo_bars": 3,
            "point": point,
        },
        "folds": folds,
        "aggregate_validation": aggregate_metrics,
        "aggregate_nominal_2x_spread": nominal_stress,
        "nominal_daily_evidence": evidence,
        "positive_nominal_validation_folds": nominal_fold_positive,
        "positive_robustness_validation_folds": robustness_fold_counts,
        "gates": gates,
        "overall_pass": all(gates.values()),
        "stopping_rule": "any failed gate ends historical strategy-family search; no inversion, pair promotion, filter/session/date/exit/gate change",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--point", required=True, type=float)
    parser.add_argument("--output", type=Path, default=Path("research/results_r4.json"))
    args = parser.parse_args(argv)
    result = analyze_bars(load_csv(args.csv), args.point)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
