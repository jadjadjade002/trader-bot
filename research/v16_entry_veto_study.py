"""Read-only, chronological V16 observational entry-veto study.

Methodology & Safety Principles:
- Strict zero causal claims: evaluations measure historical observational associations, not causal proofs.
- Only rows with label_status == COMPLETE are included.
- Strict chronological train/validation temporal split with mandatory 15-MINUTE (900s) LABEL-HORIZON EMBARGO.
- Enforce veto coverage ceiling (coverage_blocked <= 50%) to prevent over-vetoing and trivial trade suppression.
- Enforce split sample size floors (minimum 20 samples per partition).
- Collector 16.31 threshold data is marked EXPLORATORY ONLY.
- Labels are OBSERVABLE-ONLY proxy outcomes based on forward tick quotes, not live broker fills.
- Explicit governance verdict: RESEARCH_ONLY / INCONCLUSIVE. Never DEPLOY_READY.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.v16_entry_parity_replay import (
    POLICY_PRESETS,
    evaluate_v16_macro_filters,
    load_and_validate_telemetry,
    resolve_trade_path,
)

POINT = 0.01

MAX_ALLOWED_VETO_COVERAGE = 0.50
MIN_SPLIT_SAMPLE_FLOOR = 20
LABEL_HORIZON_EMBARGO_SECONDS = 900  # 15 minutes
COLLECTOR_DATA_CLASSIFICATION = "EXPLORATORY_ONLY"


@dataclass
class VetoCandidate:
    veto_id: str
    name: str
    description: str
    rule_fn: Callable[[Dict[str, Any]], bool]  # Returns True to BLOCK the trade


def get_candidate_vetoes() -> List[VetoCandidate]:
    """Defines observational entry veto filters based strictly on pre-entry observable indicators."""
    return [
        VetoCandidate(
            veto_id="VETO_HIGH_SPREAD_45",
            name="Spread Ceiling (45 pts)",
            description="Observational filter: Block entries where current spread exceeds 45.0 points (4.5 pips)",
            rule_fn=lambda r: float(r.get("entry_spread_points", 0.0)) > 45.0,
        ),
        VetoCandidate(
            veto_id="VETO_LOW_ATR_100",
            name="Dead Market ATR Filter (<100 pts)",
            description="Observational filter: Block entries when M1 ATR(14) is under 100.0 points ($1.00)",
            rule_fn=lambda r: float(r.get("atr_points", 0.0)) < 100.0,
        ),
        VetoCandidate(
            veto_id="VETO_HIGH_ATR_200",
            name="Volatility Shock ATR Ceiling (>200 pts)",
            description="Observational filter: Block entries when M1 ATR(14) exceeds 200.0 points ($2.00)",
            rule_fn=lambda r: float(r.get("atr_points", 0.0)) > 200.0,
        ),
        VetoCandidate(
            veto_id="VETO_COUNTER_SLOPE",
            name="Counter-Momentum Slope Veto",
            description="Observational filter: Block BUY if LinReg slope < 0; block SELL if LinReg slope > 0",
            rule_fn=lambda r: (
                (r.get("resolved_side") == "BUY" and float(r.get("linreg_slope_current", 0.0)) < 0.0)
                or (r.get("resolved_side") == "SELL" and float(r.get("linreg_slope_current", 0.0)) > 0.0)
            ),
        ),
        VetoCandidate(
            veto_id="VETO_RSI_OVEREXTENDED",
            name="RSI Overextended Veto",
            description="Observational filter: Block BUY if RSI > 60.0; block SELL if RSI < 40.0",
            rule_fn=lambda r: (
                (r.get("resolved_side") == "BUY" and float(r.get("rsi", 50.0)) > 60.0)
                or (r.get("resolved_side") == "SELL" and float(r.get("rsi", 50.0)) < 40.0)
            ),
        ),
        VetoCandidate(
            veto_id="VETO_WEAK_SCORE_10",
            name="Weak Trend Score (<10 pts) [Exploratory]",
            description="Exploratory filter: Block entries where collector EMA separation score is below 10.0 points",
            rule_fn=lambda r: float(r.get("collector_score", 0.0)) < 10.0,
        ),
        VetoCandidate(
            veto_id="VETO_SESSION_ROLLOVER",
            name="Rollover Session Veto",
            description="Observational filter: Block entries during ROLLOVER session",
            rule_fn=lambda r: "ROLLOVER" in r.get("session_label", "").upper(),
        ),
    ]


def prepare_dataset(
    telemetry_path: Path,
    policy: Dict[str, float],
) -> List[Dict[str, Any]]:
    """Loads, validates, filters for COMPLETE, and resolves observable proxy paths."""
    raw_rows, _ = load_and_validate_telemetry(telemetry_path)
    clean_rows: List[Dict[str, Any]] = []

    for r in raw_rows:
        if r.get("label_status") != "COMPLETE":
            continue

        atr = float(r.get("atr_points", 0.0))
        spread = float(r.get("entry_spread_points", 0.0))
        session = r.get("session_label", "")
        side = r.get("signal_side", "BUY")

        macro_ok, _ = evaluate_v16_macro_filters(atr, spread, session)
        rsi = float(r.get("rsi", 50.0))
        rsi_ok = (35.0 <= rsi <= 65.0)

        # Basic proxy eligibility
        if not (macro_ok and rsi_ok):
            continue

        outcome, pts, exit_msc, reason = resolve_trade_path(r, side, policy)

        clean_rows.append({
            "signal_bar_epoch": int(r["signal_bar_epoch"]),
            "signal_bar_iso": r["signal_bar_iso"],
            "entry_tick_time_msc": int(r["entry_tick_time_msc"]),
            "horizon_end_time_msc": int(r["horizon_end_time_msc"]),
            "session_label": session,
            "resolved_side": side,
            "collector_score": float(r.get("signal_score", 0.0)),
            "linreg_slope_current": float(r.get("linreg_slope_current", 0.0)),
            "rsi": rsi,
            "atr_points": atr,
            "entry_spread_points": spread,
            "outcome": outcome,
            "points": pts,
            "exit_msc": exit_msc,
            "exit_reason": reason,
            "label_classification": "OBSERVABLE_PROXY_ONLY",
        })

    # Sort strictly chronologically
    clean_rows.sort(key=lambda x: (x["signal_bar_epoch"], x["entry_tick_time_msc"]))
    return clean_rows


def compute_metrics(
    rows: List[Dict[str, Any]],
    veto_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> Dict[str, Any]:
    """Computes trade counts, outcomes, coverage, and expectancy."""
    n_total = len(rows)
    if n_total == 0:
        return {
            "n": 0, "blocked": 0, "kept": 0, "coverage_blocked": 0.0,
            "coverage_valid": True,
            "outcomes_total": {}, "outcomes_kept": {}, "outcomes_blocked": {},
            "tp_retained": 0.0, "sl_removed": 0.0, "be_removed": 0.0,
            "net_points_kept": 0.0, "expectancy_points_per_trade": 0.0,
        }

    total_counts = Counter(r["outcome"] for r in rows)

    if veto_fn is None:
        kept_rows = rows
        blocked_rows = []
    else:
        blocked_rows = [r for r in rows if veto_fn(r)]
        kept_rows = [r for r in rows if not veto_fn(r)]

    blocked_counts = Counter(r["outcome"] for r in blocked_rows)
    kept_counts = Counter(r["outcome"] for r in kept_rows)

    net_points = sum(r["points"] for r in kept_rows)
    n_kept = len(kept_rows)
    expectancy = round(net_points / n_kept, 2) if n_kept > 0 else 0.0

    tp_total = total_counts.get("TP", 0)
    sl_total = total_counts.get("INITIAL_SL", 0)
    be_total = total_counts.get("BE", 0)

    tp_retained = round(kept_counts.get("TP", 0) / tp_total, 4) if tp_total > 0 else 0.0
    sl_removed = round(blocked_counts.get("INITIAL_SL", 0) / sl_total, 4) if sl_total > 0 else 0.0
    be_removed = round(blocked_counts.get("BE", 0) / be_total, 4) if be_total > 0 else 0.0
    coverage = round(len(blocked_rows) / n_total, 4)

    return {
        "n": n_total,
        "blocked": len(blocked_rows),
        "kept": n_kept,
        "coverage_blocked": coverage,
        "coverage_valid": coverage <= MAX_ALLOWED_VETO_COVERAGE,
        "outcomes_total": dict(total_counts),
        "outcomes_kept": dict(kept_counts),
        "outcomes_blocked": dict(blocked_counts),
        "tp_retained": tp_retained,
        "sl_removed": sl_removed,
        "be_removed": be_removed,
        "net_points_kept": round(net_points, 1),
        "expectancy_points_per_trade": expectancy,
    }


def run_veto_study(
    telemetry_path: Path,
    policy_name: str = "v16_live_20260910",
    train_ratio: float = 0.65,
    embargo_seconds: int = LABEL_HORIZON_EMBARGO_SECONDS,
) -> Dict[str, Any]:
    """Runs observational veto study with 15-minute label-horizon embargo and sample floors."""
    policy = POLICY_PRESETS.get(policy_name, POLICY_PRESETS["v16_live_20260910"])
    dataset = prepare_dataset(telemetry_path, policy)

    n_total = len(dataset)
    if n_total < (MIN_SPLIT_SAMPLE_FLOOR * 2):
        raise ValueError(
            f"Insufficient usable dataset size: {n_total} rows (minimum {MIN_SPLIT_SAMPLE_FLOOR * 2} required)."
        )

    # Chronological partition
    split_idx = int(n_total * train_ratio)
    train_rows = dataset[:split_idx]
    train_max_epoch = max(r["signal_bar_epoch"] for r in train_rows)
    train_max_horizon_msc = max(r["horizon_end_time_msc"] for r in train_rows)

    # Labels may observe a path for 15 minutes. Validation must begin strictly
    # after the actual latest train horizon, not merely after the train signal bar.
    val_rows = [r for r in dataset[split_idx:] if r["entry_tick_time_msc"] > train_max_horizon_msc]
    embargoed_rows = [r for r in dataset[split_idx:] if r["entry_tick_time_msc"] <= train_max_horizon_msc]

    if len(train_rows) < MIN_SPLIT_SAMPLE_FLOOR:
        raise ValueError(f"Train split ({len(train_rows)}) below sample floor ({MIN_SPLIT_SAMPLE_FLOOR})")
    if len(val_rows) < MIN_SPLIT_SAMPLE_FLOOR:
        raise ValueError(f"Validation split ({len(val_rows)}) below sample floor ({MIN_SPLIT_SAMPLE_FLOOR})")

    val_min_epoch = min(r["signal_bar_epoch"] for r in val_rows)
    val_min_entry_msc = min(r["entry_tick_time_msc"] for r in val_rows)
    actual_embargo_msc = val_min_entry_msc - train_max_horizon_msc
    if actual_embargo_msc <= 0:
        raise ValueError(
            "Embargo violation! Validation entry is not strictly after the latest train label horizon"
        )

    # Baseline performance
    baseline_train = compute_metrics(train_rows)
    baseline_val = compute_metrics(val_rows)

    candidates = get_candidate_vetoes()
    veto_results: List[Dict[str, Any]] = []

    for c in candidates:
        train_res = compute_metrics(train_rows, c.rule_fn)
        val_res = compute_metrics(val_rows, c.rule_fn)

        train_exp_delta = round(train_res["expectancy_points_per_trade"] - baseline_train["expectancy_points_per_trade"], 2)
        val_exp_delta = round(val_res["expectancy_points_per_trade"] - baseline_val["expectancy_points_per_trade"], 2)

        # Enforce veto coverage <= 50%
        coverage_pass = (train_res["coverage_blocked"] <= MAX_ALLOWED_VETO_COVERAGE) and (
            val_res["coverage_blocked"] <= MAX_ALLOWED_VETO_COVERAGE
        )

        train_beneficial = (train_exp_delta > 0) and (train_res["sl_removed"] > 0)
        # A research hypothesis cannot be accepted when its held-out
        # expectancy deteriorates, even slightly. Tolerance masks overfit.
        val_robust = val_exp_delta > 0

        if not coverage_pass:
            verdict = f"REJECTED_EXCESSIVE_COVERAGE (> {MAX_ALLOWED_VETO_COVERAGE*100:.0f}%)"
        elif train_beneficial and val_robust:
            verdict = "ACCEPTED_HYPOTHESIS"
        else:
            verdict = "REJECTED_HYPOTHESIS"

        veto_results.append({
            "veto_id": c.veto_id,
            "name": c.name,
            "description": c.description,
            "train": train_res,
            "train_expectancy_delta": train_exp_delta,
            "validation": val_res,
            "validation_expectancy_delta": val_exp_delta,
            "coverage_pass": coverage_pass,
            "train_beneficial": train_beneficial,
            "val_robust": val_robust,
            "evaluation_verdict": verdict,
        })

    report = {
        "metadata": {
            "title": "V16 Observational Entry Veto Study",
            "telemetry_file": str(telemetry_path),
            "policy_name": policy_name,
            "policy_parameters": policy,
            "total_dataset_rows": n_total,
            "train_ratio": train_ratio,
            "label_horizon_embargo_seconds": embargo_seconds,
            "embargoed_rows_count": len(embargoed_rows),
            "max_allowed_coverage": MAX_ALLOWED_VETO_COVERAGE,
            "split_sample_floor": MIN_SPLIT_SAMPLE_FLOOR,
            "collector_data_classification": COLLECTOR_DATA_CLASSIFICATION,
            "label_classification": "OBSERVABLE_PROXY_ONLY",
            "train_split": {
                "count": len(train_rows),
                "start_time": train_rows[0]["signal_bar_iso"],
                "end_time": train_rows[-1]["signal_bar_iso"],
                "max_epoch": train_max_epoch,
                "max_horizon_time_msc": train_max_horizon_msc,
            },
            "validation_split": {
                "count": len(val_rows),
                "start_time": val_rows[0]["signal_bar_iso"],
                "end_time": val_rows[-1]["signal_bar_iso"],
                "min_epoch": val_min_epoch,
                "min_entry_time_msc": val_min_entry_msc,
                "embargo_gap_milliseconds": actual_embargo_msc,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "baseline": {
            "train": baseline_train,
            "validation": baseline_val,
        },
        "candidates": veto_results,
        "decision_summary": {
            "total_candidates": len(veto_results),
            "accepted_candidates": [v["name"] for v in veto_results if v["evaluation_verdict"] == "ACCEPTED_HYPOTHESIS"],
            "rejected_candidates": [v["name"] for v in veto_results if v["evaluation_verdict"] != "ACCEPTED_HYPOTHESIS"],
        },
        "governance_verdict": {
            "verdict": "RESEARCH_ONLY",
            "deployment_status": "BLOCKED",
            "reasons": [
                "Dataset covers single Asian session (2026-09-14); statistical power is exploratory.",
                "Zero causal proof; evaluations measure historical correlations under proxy assumptions.",
                "Tick paths represent observable-only proxy outcomes; live broker fills/slippage unmodeled.",
                "Veto coverage ceiling (<=50%) and 15-min label-horizon embargo enforced.",
                "Zero parameter-fitting or production deployment permitted.",
            ],
        },
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="V16 Observational Entry Veto Study")
    parser.add_argument(
        "--telemetry",
        type=Path,
        default=Path("data/V16TickTelemetry_XAUUSD_M1_20260914.csv"),
        help="Path to Schema-2 tick telemetry CSV",
    )
    parser.add_argument(
        "--policy",
        type=str,
        default="v16_live_20260910",
        choices=list(POLICY_PRESETS.keys()),
        help="Policy preset for TP/SL/BE levels",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.65,
        help="Chronological train split ratio",
    )
    parser.add_argument(
        "--embargo-seconds",
        type=int,
        default=LABEL_HORIZON_EMBARGO_SECONDS,
        help="Forward label horizon embargo seconds",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/v16_entry_veto_study_results.json"),
        help="Output JSON report path",
    )

    args = parser.parse_args()
    report = run_veto_study(args.telemetry, args.policy, args.train_ratio, args.embargo_seconds)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("================================================================================")
    print("             QUANTUM TITAN V16 OBSERVATIONAL ENTRY VETO STUDY                   ")
    print("================================================================================")
    print(f"Policy: {args.policy} | Usable Rows: {report['metadata']['total_dataset_rows']}")
    print(f"Train Split: {report['metadata']['train_split']['count']} rows")
    print(
        "Embargo Gap: "
        f"{report['metadata']['validation_split']['embargo_gap_milliseconds']}ms "
        f"after latest train horizon (Excluded: {report['metadata']['embargoed_rows_count']} rows)"
    )
    print(f"Val Split  : {report['metadata']['validation_split']['count']} rows")
    print("--------------------------------------------------------------------------------")
    b_tr = report["baseline"]["train"]
    b_val = report["baseline"]["validation"]
    print(f"BASELINE Train: {b_tr['outcomes_total']} | Net: {b_tr['net_points_kept']} pts | Exp: {b_tr['expectancy_points_per_trade']} pts/trade")
    print(f"BASELINE Val  : {b_val['outcomes_total']} | Net: {b_val['net_points_kept']} pts | Exp: {b_val['expectancy_points_per_trade']} pts/trade")
    print("--------------------------------------------------------------------------------")
    print("CANDIDATE VETO EVALUATION (Train vs Val with Coverage <= 50% Check):")
    print(f"{'Veto Name':<32} | {'Tr Cov':<6} | {'Val Cov':<7} | {'Tr d':<6} | {'Val d':<6} | {'Verdict'}")
    print("-" * 85)
    for c in report["candidates"]:
        print(
            f"{c['name']:<32} | "
            f"{c['train']['coverage_blocked']*100:5.1f}% | "
            f"{c['validation']['coverage_blocked']*100:6.1f}% | "
            f"{c['train_expectancy_delta']:+6.1f} | "
            f"{c['validation_expectancy_delta']:+6.1f} | "
            f"{c['evaluation_verdict']}"
        )
    print("--------------------------------------------------------------------------------")
    print(f"VERDICT: {report['governance_verdict']['verdict']} (Deployment: {report['governance_verdict']['deployment_status']})")
    for r in report["governance_verdict"]["reasons"]:
        print(f"  - {r}")
    print(f"JSON Results written to: {args.output_json}")
    print("================================================================================")


if __name__ == "__main__":
    main()
