"""Fail-closed evaluation of native MT5 v21.67 overnight reports.

Historical tester evidence is engineering-only, regardless of its result.  Native
reports used here expose Commission, Swap and Profit per deal, but not DEAL_FEE;
the evaluator therefore reports that per-trade fee allocation is incomplete.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class EvaluationError(ValueError):
    pass


def _load_parser():
    path = Path(__file__).parents[1] / "scripts" / "analyze_v17_report.py"
    spec = importlib.util.spec_from_file_location("qt_native_report", path)
    if spec is None or spec.loader is None:
        raise EvaluationError(f"cannot load native report parser: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise EvaluationError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise EvaluationError(f"{label} is not finite")
    return result


def _count(value: Any, label: str) -> int:
    result = _finite(value, label)
    if result < 0 or not result.is_integer():
        raise EvaluationError(f"{label} is not a nonnegative integer")
    return int(result)


def _percent(text: str, label: str) -> float:
    matches = re.findall(r"(-?[0-9][0-9 ,.]*)%", text)
    if not matches:
        raise EvaluationError(f"{label} percentage is missing")
    return _finite(matches[-1].replace(" ", "").replace(",", ""), label)


def _deal_header(path: Path) -> list[str]:
    parser_module = _load_parser()
    raw = path.read_bytes()
    content = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    rows = parser_module.Rows()
    rows.feed(content)
    try:
        marker = rows.rows.index(["Deals"])
    except ValueError as exc:
        raise EvaluationError("native Deals table is missing") from exc
    for row in rows.rows[marker + 1 :]:
        if "Commission" in row and "Profit" in row:
            return row
    raise EvaluationError("native Deals header is missing")


def evaluate_analysis(analysis: dict[str, Any], evidence_classification: str,
                      fee_column_present: bool = False) -> dict[str, Any]:
    trades = _count(analysis.get("trades"), "trades")
    wins = _count(analysis.get("wins"), "wins")
    net = _finite(analysis.get("net"), "net")
    if trades < 0 or wins < 0 or wins > trades:
        raise EvaluationError("invalid trade/win counts")
    closed = analysis.get("closed")
    sessions = analysis.get("sessions")
    native = analysis.get("native")
    if not isinstance(closed, list) or not isinstance(sessions, dict) or not isinstance(native, dict):
        raise EvaluationError("native analysis is incomplete")
    pnl = [_finite(trade.get("net"), f"closed[{index}].net") for index, trade in enumerate(closed)]
    if len(pnl) != trades or abs(sum(pnl) - net) > 0.021:
        raise EvaluationError("closed trades do not reconcile to evaluated net PnL")
    calculated_wins = sum(value > 0.00001 for value in pnl)
    if wins != calculated_wins:
        raise EvaluationError("win count does not reconcile to positive net-cost trades")
    gross_win = sum(value for value in pnl if value > 0.00001)
    gross_loss = -sum(value for value in pnl if value < -0.00001)
    positive = [value for value in pnl if value > 0.00001]
    negative = [value for value in pnl if value < -0.00001]
    mean_positive = sum(positive) / len(positive) if positive else 0.0
    mean_negative = sum(negative) / len(negative) if negative else 0.0
    break_even_win_rate = (-mean_negative / (mean_positive - mean_negative) * 100.0) if mean_positive > 0 and mean_negative < 0 else None
    profit_factor = gross_win / gross_loss if gross_loss else (math.inf if gross_win else 0.0)
    if not math.isfinite(profit_factor):
        # No-loss samples are valid but retain a JSON-safe representation.
        profit_factor_value: float | str = "infinite"
    else:
        profit_factor_value = round(profit_factor, 4)
    equity_dd = _percent(str(native.get("Equity Drawdown Relative", "")), "relative equity drawdown")
    if equity_dd < 0:
        raise EvaluationError("equity drawdown percentage is negative")

    carried = 0
    joint = 0
    complete = 0
    session_results: dict[str, Any] = {}
    for name, raw_bucket in sessions.items():
        bucket = dict(raw_bucket)
        bucket_trades = _count(bucket.get("trades"), f"{name}.trades")
        bucket_wins = _count(bucket.get("wins"), f"{name}.wins")
        bucket_net = _finite(bucket.get("net"), f"{name}.net")
        bucket_carried = _count(bucket.get("carried_past_wake", 0), f"{name}.carried_past_wake")
        if min(bucket_trades, bucket_wins, bucket_carried) < 0 or bucket_wins > bucket_trades:
            raise EvaluationError(f"{name}: invalid overnight counts")
        carried += bucket_carried
        is_complete = bucket_carried == 0
        complete += int(is_complete)
        rate = 100.0 * bucket_wins / bucket_trades if bucket_trades else None
        target = bool(is_complete and 10 <= bucket_trades <= 20 and rate is not None and rate >= 80.0 and bucket_net > 0)
        joint += int(target)
        session_results[name] = {**bucket, "complete": is_complete, "joint_target_met": target}

    windows = len(sessions)
    joint_ratio = joint / windows if windows else 0.0
    session_trade_total = sum(_count(bucket.get("trades"), f"{name}.trades") for name, bucket in sessions.items())
    mean_frequency = session_trade_total / windows if windows else 0.0
    zero_trade_windows = sum(_count(bucket.get("trades"), f"{name}.trades") == 0 for name, bucket in sessions.items())
    ordered_nets = [_finite(sessions[name].get("net"), f"{name}.net") for name in sorted(sessions)]
    five_session_blocks = [sum(ordered_nets[index:index + 5]) for index in range(0, len(ordered_nets), 5) if len(ordered_nets[index:index + 5]) == 5]
    profitable_blocks = sum(total > 0.0 for total in five_session_blocks)
    win_rate = 100.0 * wins / trades if trades else 0.0
    forced = _count(analysis.get("forced_test_end_exits", 0), "forced_test_end_exits")
    cost_stress_raw = analysis.get("extra_half_spread_cost_stress_net")
    cost_stress_net = None if cost_stress_raw is None else _finite(cost_stress_raw, "extra_half_spread_cost_stress_net")
    exit_categories = {"tp": 0, "positive_stop": 0, "negative_stop": 0, "time_end": 0, "other": 0}
    closed_output = []
    for trade, value in zip(closed, pnl):
        comment = str(trade.get("comment", "")).lower()
        duration = None
        try:
            duration = (datetime.fromisoformat(str(trade["close"])) - datetime.fromisoformat(str(trade["open"]))).total_seconds()
        except (KeyError, TypeError, ValueError):
            pass
        if "end of test" in comment or "time" in comment or "session" in comment or (not comment and duration is not None and duration >= 599):
            category = "time_end"
        elif "tp" in comment:
            category = "tp"
        elif "sl" in comment or "stop" in comment:
            category = "positive_stop" if value > 0.00001 else "negative_stop"
        else:
            category = "other"
        exit_categories[category] += 1
        closed_output.append({**trade, "duration_seconds": duration, "exit_category": category})
    gates = {
        "at_least_400_closed_trades": trades >= 400,
        "at_least_40_full_weekday_windows": windows >= 40 and complete == windows,
        "mean_frequency_between_10_and_20": 10.0 <= mean_frequency <= 20.0,
        "overall_win_rate_at_least_80_pct": win_rate >= 80.0,
        "net_cost_profit_factor_at_least_1_2": profit_factor >= 1.2,
        "equity_drawdown_at_most_20_pct": equity_dd <= 20.0,
        "suggested_net_profit_guard_at_least_40_usd": net >= 40.0,
        "at_least_80_pct_nights_meet_joint_target": windows > 0 and joint_ratio >= 0.8,
        "at_least_6_of_first_8_five_session_blocks_profitable": len(five_session_blocks) >= 8 and sum(total > 0.0 for total in five_session_blocks[:8]) >= 6,
        "no_positions_carried_past_wake": carried == 0,
        "no_forced_test_end_exits": forced == 0,
        "positive_expectancy_after_extra_half_spread_cost_stress": cost_stress_net is not None and cost_stress_net > 0.0,
    }
    historical = evidence_classification != "PROSPECTIVE_SEALED"
    # analyze_v17_report parses only the known 13-column Commission/Swap/Profit
    # layout. Merely seeing a Fee heading would not prove that DEAL_FEE was parsed.
    fee_complete = False
    engineering_pass = all(gates.values())
    return {
        "schema_version": 1,
        "strategy_version": "21.67",
        "evidence_classification": evidence_classification,
        "historical_or_exposed": historical,
        "evaluator_scope": "ENGINEERING_ONLY_NEVER_PROMOTES",
        "historical_cannot_promote_even_if_favorable": True,
        "fee_accounting": {
            "native_global_net_reconciled": True,
            "deal_components_used": ["Commission", "Swap", "Profit"],
            "deal_fee_column_present": fee_column_present,
            "per_trade_and_per_night_fee_allocation_complete": fee_complete,
            "limitation": None if fee_complete else "Native deal table has no DEAL_FEE column; aggregate reconciliation cannot allocate omitted fees by trade/night.",
        },
        "metrics": {
            "closed_trades": trades, "wins": wins, "overall_win_rate_pct": round(win_rate, 2),
            "net_profit": round(net, 2), "net_cost_profit_factor": profit_factor_value,
            "mean_positive_trade": round(mean_positive, 4), "mean_negative_trade": round(mean_negative, 4),
            "break_even_win_rate_pct_from_mean_net_outcomes": None if break_even_win_rate is None else round(break_even_win_rate, 2),
            "exit_categories": exit_categories,
            "equity_drawdown_pct": round(equity_dd, 2), "full_weekday_windows": windows,
            "complete_windows": complete, "joint_target_nights": joint,
            "joint_target_night_pct": round(100.0 * joint_ratio, 2),
            "mean_trades_per_overnight": round(mean_frequency, 2),
            "zero_trade_windows": zero_trade_windows,
            "complete_five_session_blocks": len(five_session_blocks),
            "profitable_five_session_blocks": profitable_blocks,
            "carried_past_wake": carried, "forced_test_end_exits": forced,
            "extra_half_spread_cost_stress_net": cost_stress_net,
        },
        "gates": gates,
        "observed_engineering_thresholds_met": engineering_pass,
        "all_qualification_criteria_met": False,
        "eligible_for_promotion": False,
        "promotion_blockers": [
            "engineering-only evaluator; no prospective source/start/schedule freeze manifest is verified",
            "per-trade DEAL_FEE accounting is unavailable",
            "session-level uncertainty/qualification analysis is not implemented",
            *( ["extra half-spread cost-stress evidence unavailable or nonpositive"] if cost_stress_net is None or cost_stress_net <= 0.0 else [] ),
            *( ["one or more observable engineering thresholds failed"] if not engineering_pass else [] ),
        ],
        "wilson_caveat": analysis.get("independent_trial_assumption", "Wilson intervals assume independent trades; correlated scalps can make them overconfident."),
        "sessions": session_results,
        "closed": closed_output,
    }


def evaluate_report(report: Path, metadata: Path | None = None) -> dict[str, Any]:
    evidence = "EXPOSED_ENGINEERING_ONLY"
    if metadata is not None:
        try:
            meta = json.loads(metadata.read_text(encoding="utf-8-sig"))
            evidence = str(meta["evidenceClassification"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EvaluationError("metadata is missing or malformed") from exc
    try:
        analysis = _load_parser().analyze(report)
    except Exception as exc:
        raise EvaluationError(f"native report rejected: {exc}") from exc
    return evaluate_analysis(analysis, evidence, "Fee" in _deal_header(report))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_report(args.report, args.metadata)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "sessions"}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
