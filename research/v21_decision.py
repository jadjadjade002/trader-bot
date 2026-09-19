"""Evaluate only the preregistered v21 observational gates.

This is intentionally not a strategy tester. It never simulates orders or
calculates PnL, and labels every partial acquisition as INCONCLUSIVE.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from research.v21_dataset_audit import HEADER, audit
from research.v21_whipsaw import ObservedBar, analyze, causal_feature_at, delayed_label_at, eligible_probe, wilder_atr14


MIN_PROBES = 1000
MIN_SESSIONS = 15


def _source_files(directories: Iterable[Path]) -> list[Path]:
    return sorted({path for directory in directories for path in directory.glob("QTForward_XAUUSD_M1_*.csv")})


def load_bars(directories: Iterable[Path]) -> list[ObservedBar]:
    """Load audited M1 observations in chronological order."""
    result: list[ObservedBar] = []
    for path in _source_files(directories):
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADER:
                raise ValueError(f"{path.name}: unexpected schema")
            for row in reader:
                result.append(ObservedBar(
                    epoch=int(row["time_broker_epoch"]),
                    broker_time=datetime.fromisoformat(row["time_broker_iso"]),
                    high=float(row["high"]), low=float(row["low"]),
                    close=float(row["close"]), flags=row["flags"],
                ))
    return result


def _session_day(moment: datetime) -> date:
    """Broker session 18:00..01:56 belongs to the date on which it starts."""
    return moment.date() if moment.hour >= 18 else (moment - timedelta(days=1)).date()


def decision(directories: Iterable[Path]) -> dict[str, object]:
    """Return the fixed decision gates without inventing a trading conclusion."""
    integrity = audit(directories)
    bars = load_bars(directories)
    atr = wilder_atr14(bars)
    eligible: list[tuple[object, object, date]] = []
    for index, bar in enumerate(bars):
        if not eligible_probe(bar):
            continue
        feature = causal_feature_at(bars, atr, index)
        label = delayed_label_at(bars, atr, index)
        if feature is not None and label is not None:
            eligible.append((feature, label, _session_day(bar.broker_time)))

    vetoed = [(label, session) for feature, label, session in eligible if feature.gate_veto]
    kept = [(label, session) for feature, label, session in eligible if not feature.gate_veto]
    rate = lambda rows: sum(label.whipsaw3 for label, _ in rows) / len(rows) if rows else None
    veto_rate, kept_rate = rate(vetoed), rate(kept)
    sessions = sorted({session for _, _, session in eligible})
    veto_by_session = Counter(session for label, session in vetoed if label.whipsaw3)
    total_veto_labels = sum(veto_by_session.values())
    max_concentration = max(veto_by_session.values(), default=0) / total_veto_labels if total_veto_labels else None

    weekly: dict[int, list[tuple[object, object]]] = defaultdict(list)
    first_session = sessions[0] if sessions else None
    for feature, label, session in eligible:
        assert first_session is not None
        weekly[(session - first_session).days // 7].append((feature, label))
    weekly_positive = 0
    for rows in weekly.values():
        weekly_veto = [label for feature, label in rows if feature.gate_veto]
        weekly_kept = [label for feature, label in rows if not feature.gate_veto]
        if weekly_veto and weekly_kept:
            if sum(item.whipsaw3 for item in weekly_veto) / len(weekly_veto) > sum(item.whipsaw3 for item in weekly_kept) / len(weekly_kept):
                weekly_positive += 1

    summary = analyze(bars)
    coverage = len(vetoed) / len(eligible) if eligible else None
    gates = {
        "minimum_probes": len(eligible) >= MIN_PROBES,
        "minimum_broker_session_dates": len(sessions) >= MIN_SESSIONS,
        "veto_coverage_10_to_40_percent": coverage is not None and .10 <= coverage <= .40,
        "veto_prevalence_at_least_1_25x_kept": veto_rate is not None and kept_rate is not None and veto_rate >= 1.25 * kept_rate,
        "absolute_separation_at_least_5pp": veto_rate is not None and kept_rate is not None and veto_rate - kept_rate >= .05,
        "positive_separation_in_3_of_4_weeks": len(weekly) >= 4 and weekly_positive >= 3,
        "vetoed_label_session_concentration_at_most_20_percent": max_concentration is not None and max_concentration <= .20,
    }
    complete = gates["minimum_probes"] and gates["minimum_broker_session_dates"]
    passed = complete and all(gates.values())
    return {
        "schema_version": 1,
        "study": "v21_forward_whipsaw_observational",
        "status": "PASS_SEPARATE_EXECUTION_EXPERIMENT_REQUIRES_AUTHORIZATION" if passed else ("FAIL_FROZEN_HYPOTHESIS" if complete else "INCONCLUSIVE_ACQUISITION_INCOMPLETE"),
        "integrity": integrity,
        "summary": summary,
        "broker_session_dates": [item.isoformat() for item in sessions],
        "weekly_blocks_observed": len(weekly),
        "positive_weekly_separation_blocks": weekly_positive,
        "vetoed_whipsaw_label_max_session_concentration": max_concentration,
        "gates": gates,
        "promotion": False,
        "promotion_reason": "Observational results never deploy an EA. A PASS only permits a separately authorized experiment on a separate stream.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(decision(args.directory), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
