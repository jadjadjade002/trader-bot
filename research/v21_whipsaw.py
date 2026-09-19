"""Frozen causal feature and delayed-label analysis for v21 forward research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class ObservedBar:
    epoch: int
    broker_time: datetime
    high: float
    low: float
    close: float
    flags: str


@dataclass(frozen=True)
class FeatureRow:
    decision_epoch: int
    feature_max_epoch: int
    atr14: float
    path20: float
    displacement20: float
    efficiency20: float
    gate_veto: bool


@dataclass(frozen=True)
class LabelRow:
    decision_epoch: int
    label_available_epoch: int
    forward_path3: float
    forward_efficiency3: float
    whipsaw3: bool


def wilder_atr14(bars: Sequence[ObservedBar]) -> list[float | None]:
    values: list[float | None] = [None] * len(bars)
    ranges: list[float] = []
    for index, bar in enumerate(bars):
        prior = bars[index - 1].close if index else bar.close
        ranges.append(max(bar.high - bar.low, abs(bar.high - prior), abs(bar.low - prior)))
        if index == 13:
            values[index] = sum(ranges) / 14.0
        elif index > 13:
            assert values[index - 1] is not None
            values[index] = (13.0 * values[index - 1] + ranges[-1]) / 14.0
    return values


def _consecutive_ok(bars: Sequence[ObservedBar], start: int, end: int) -> bool:
    return start >= 0 and end < len(bars) and all(
        bars[index].flags == "OK" and bars[index].epoch - bars[index - 1].epoch == 60
        for index in range(start + 1, end + 1)
    ) and bars[start].flags == "OK"


def eligible_probe(bar: ObservedBar) -> bool:
    minute = bar.broker_time.hour * 60 + bar.broker_time.minute
    return (minute >= 18 * 60 or minute <= 116) and bar.broker_time.minute % 4 == 0


def causal_feature_at(bars: Sequence[ObservedBar], atr: Sequence[float | None], index: int) -> FeatureRow | None:
    if index < 20 or atr[index] is None or not _consecutive_ok(bars, index - 20, index):
        return None
    path = sum(abs(bars[pos].close - bars[pos - 1].close) for pos in range(index - 19, index + 1))
    if path <= 0.0:
        return None
    displacement = abs(bars[index].close - bars[index - 20].close)
    return FeatureRow(bars[index].epoch, bars[index].epoch, float(atr[index]), path, displacement, displacement / path, displacement / path <= 0.25)


def delayed_label_at(bars: Sequence[ObservedBar], atr: Sequence[float | None], index: int) -> LabelRow | None:
    if atr[index] is None or not _consecutive_ok(bars, index, index + 3):
        return None
    path = sum(abs(bars[pos].close - bars[pos - 1].close) for pos in range(index + 1, index + 4))
    if path <= 0.0:
        return None
    efficiency = abs(bars[index + 3].close - bars[index].close) / path
    return LabelRow(bars[index].epoch, bars[index + 3].epoch, path, efficiency, efficiency <= 0.25 and path >= 0.25 * float(atr[index]))


def analyze(bars: Sequence[ObservedBar]) -> dict[str, object]:
    atr = wilder_atr14(bars)
    samples = [(causal_feature_at(bars, atr, i), delayed_label_at(bars, atr, i)) for i, bar in enumerate(bars) if eligible_probe(bar)]
    usable = [(feature, label) for feature, label in samples if feature is not None and label is not None]
    vetoed = [label for feature, label in usable if feature.gate_veto]
    kept = [label for feature, label in usable if not feature.gate_veto]
    rate = lambda labels: sum(label.whipsaw3 for label in labels) / len(labels) if labels else None
    veto_rate, kept_rate = rate(vetoed), rate(kept)
    return {"schema_version": 1, "study": "v21_forward_whipsaw_observational", "probes": len(usable), "vetoed": len(vetoed), "kept": len(kept), "veto_whipsaw_rate": veto_rate, "kept_whipsaw_rate": kept_rate, "absolute_rate_separation": veto_rate - kept_rate if veto_rate is not None and kept_rate is not None else None}
