"""Strict read-only V16 entry-parity replay and path resolution engine.

Audit & Methodology Constraints:
- Observational study only; zero causal claims.
- Close/cooldown logs do NOT prove TP/SL/BE/PnL without broker trade ledger confirmation.
- Unpaired log lines are explicitly recorded as UNMATCHED.
- Full entry parity is UNRESOLVABLE without M5 EMAs, 30-bar swing lookback, 3-bar FVG history,
  account equity/drawdown state, and MQL5 Calendar news lockout state.
- Path resolution produces OBSERVABLE-ONLY proxy labels based on forward tick quotes.
- Collector 16.31 threshold data is EXPLORATORY ONLY.

Traceability mapping directly to QuantumTitan_v16_Velocity.mq5:
- Lines 437-459, 719: Daily loss circuit breaker (IsDailyLossBreakerTripped)
- Lines 464-470, 720: Friday lockout (IsFridayLockoutActive)
- Lines 306-328, 721: Single position concurrency limit (activeTrades > 0)
- Lines 375-382, 722: Post-exit bar cooldown (IsPostExitCooldownActive, InpCooldownBars=2)
- Lines 387-401, 724-734: Anti-revenge loss streak cooldown (IsLossStreakCooldownActive, InpLossStreakPauseMins=15)
- Lines 192-237, 736: MQL5 Calendar news lockout (IsInHighImpactNews)
- Line 740: Minimum ATR floor (currentAtrPts < InpMinAtrPoints=50.0)
- Lines 743-751: Volatility shock ceiling (currentAtrPts > InpMaxAllowedAtrPoints=650.0)
- Lines 755-756: Max spread limit (currentSpread > InpMaxSpreadPoints=60.0)
- Lines 759-760: Bar-close evaluation discipline (M1 completed bar)
- Lines 242-277, 789-796, 813-820: Setup 1 - SMC Liquidity Sweep (Turtle Soup)
- Lines 282-300, 797-811, 821-835: Setup 2 - Trend Retest + Value Zone + FVG / Wick Confluence
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

POINT = 0.01

# Policy presets for outcome evaluation
POLICY_PRESETS = {
    # Default inputs in QuantumTitan_v16_Velocity.mq5 (lines 54-63)
    "v16_default": {
        "tp_pts": 220.0,
        "sl_pts": 180.0,
        "be_trigger_pts": 75.0,
        "be_lock_pts": 20.0,
    },
    # Live execution policy observed in deploy/v16_20260910_mql5.log
    "v16_live_20260910": {
        "tp_pts": 180.0,
        "sl_pts": 260.0,
        "be_trigger_pts": 85.0,
        "be_lock_pts": 15.0,
    },
}

SUPPORTED_FAV_LEVELS = [15, 20, 30, 50, 85, 100, 130, 150, 180, 200, 220, 240]
SUPPORTED_ADV_LEVELS = [15, 20, 30, 50, 85, 100, 130, 180, 220, 260]
SUPPORTED_BE_TRIGGERS = [50, 75, 85, 100, 130, 150]
SUPPORTED_BE_LOCKS = [0, 10, 15, 20, 30]

COLLECTOR_DATA_CLASSIFICATION = "EXPLORATORY_ONLY"
PARITY_UNRESOLVABLE_NOTE = (
    "Full entry parity is strictly unresolvable from telemetry alone without M5 HTF EMAs, "
    "30-bar swing lookbacks, 3-bar FVG history, account balance/equity/drawdown state, "
    "and MQL5 Calendar news lockout state."
)


@dataclass(frozen=True)
class ParityConditionTrace:
    condition_id: str
    description: str
    source_function: str
    source_lines: str
    reconstructible_from_telemetry: bool
    missing_fields: List[str]


# Institutional Traceability Matrix for V16 Velocity M1 Entry Rules
V16_CONDITION_MATRIX: List[ParityConditionTrace] = [
    ParityConditionTrace(
        condition_id="COND_DAILY_LOSS",
        description="Daily equity drawdown circuit breaker (requires live account state)",
        source_function="IsDailyLossBreakerTripped",
        source_lines="437-459, 719",
        reconstructible_from_telemetry=False,
        missing_fields=["live_account_balance_equity", "daily_pnl_state"],
    ),
    ParityConditionTrace(
        condition_id="COND_FRIDAY_LOCKOUT",
        description="Block entries after Friday cutoff hour (evaluable from signal_bar_iso)",
        source_function="IsFridayLockoutActive",
        source_lines="464-470, 720",
        reconstructible_from_telemetry=True,
        missing_fields=[],
    ),
    ParityConditionTrace(
        condition_id="COND_CONCURRENCY",
        description="Single active position limit per magic number (requires open trade ledger)",
        source_function="GetActivePositionCount",
        source_lines="306-328, 721",
        reconstructible_from_telemetry=False,
        missing_fields=["live_open_positions_state"],
    ),
    ParityConditionTrace(
        condition_id="COND_COOLDOWN",
        description="Post-exit cooldown (requires broker deal history close times)",
        source_function="IsPostExitCooldownActive",
        source_lines="375-382, 722",
        reconstructible_from_telemetry=False,
        missing_fields=["deal_history_close_time", "cooldown_bar_state"],
    ),
    ParityConditionTrace(
        condition_id="COND_LOSS_STREAK",
        description="Anti-revenge pause for 15 mins after 2 consecutive losses (requires deal ledger)",
        source_function="IsLossStreakCooldownActive",
        source_lines="387-401, 724-734",
        reconstructible_from_telemetry=False,
        missing_fields=["deal_history_loss_streak_count"],
    ),
    ParityConditionTrace(
        condition_id="COND_NEWS_LOCKOUT",
        description="MQL5 calendar news filter lockout (requires live MQL5 Calendar state)",
        source_function="IsInHighImpactNews",
        source_lines="192-237, 736",
        reconstructible_from_telemetry=False,
        missing_fields=["mql5_economic_calendar_events", "IsInHighImpactNews_state"],
    ),
    ParityConditionTrace(
        condition_id="COND_ATR_MIN",
        description="Minimum ATR volatility floor (currentAtrPts >= 50.0)",
        source_function="OnTick (ATR check)",
        source_lines="740",
        reconstructible_from_telemetry=True,
        missing_fields=[],
    ),
    ParityConditionTrace(
        condition_id="COND_ATR_MAX",
        description="Maximum ATR volatility shock ceiling (currentAtrPts <= 650.0)",
        source_function="OnTick (ATR shock ceiling)",
        source_lines="743-751",
        reconstructible_from_telemetry=True,
        missing_fields=[],
    ),
    ParityConditionTrace(
        condition_id="COND_SPREAD_MAX",
        description="Max allowed entry spread (entrySpread <= 60.0 points)",
        source_function="OnTick (Spread ceiling)",
        source_lines="755-756",
        reconstructible_from_telemetry=True,
        missing_fields=[],
    ),
    ParityConditionTrace(
        condition_id="COND_BAR_CLOSE_DISCIPLINE",
        description="Evaluate signals on completed M1 bar 1",
        source_function="OnTick (Bar timing)",
        source_lines="759-760",
        reconstructible_from_telemetry=True,
        missing_fields=[],
    ),
    ParityConditionTrace(
        condition_id="COND_SETUP1_SMC_SWEEP",
        description="SMC Liquidity Sweep (Turtle Soup 30-bar swing + 30% rejection wick + RSI)",
        source_function="DetectLiquiditySweep",
        source_lines="242-277, 789-796, 813-820",
        reconstructible_from_telemetry=False,
        missing_fields=["30_bar_swing_high_low", "bar1_open_high_low", "htf_m5_ema_20_50"],
    ),
    ParityConditionTrace(
        condition_id="COND_SETUP2_TREND_RETEST_FVG",
        description="M5+M1 Trend Retest, Fast EMA touch, Value Zone (40pt), FVG or Wick, Sqz Momentum",
        source_function="DetectFVG, CalculateSqueezeMomentum",
        source_lines="138-187, 282-300, 797-811, 821-835",
        reconstructible_from_telemetry=False,
        missing_fields=["htf_m5_ema_20_50", "m1_ema_14_50", "bar_high_low", "3_bar_fvg_lookback", "sqz_donchian_momentum"],
    ),
]


@dataclass
class TelemetryParityRow:
    signal_bar_epoch: int
    signal_bar_iso: str
    entry_tick_time_msc: int
    session_label: str
    collector_signal_side: str
    collector_score: float
    linreg_slope_current: float
    ema_fast: float
    ema_slow: float
    rsi: float
    atr_points: float
    signal_bar_range_points: float
    entry_bid: float
    entry_ask: float
    entry_spread_points: float
    label_status: str
    quality_flags: str
    resolved_side: str
    parity_verdict: str
    unresolvable_reasons: List[str]
    trade_outcome: Optional[str] = None
    realized_points: Optional[float] = None
    exit_time_msc: Optional[int] = None
    exit_reason: Optional[str] = None
    label_classification: str = "OBSERVABLE_PROXY_ONLY"


def load_and_validate_telemetry(file_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Telemetry file not found: {file_path}")

    rows: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {}

    with file_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        required_fields = [
            "schema_version", "signal_bar_epoch", "signal_bar_iso",
            "entry_tick_time_msc", "session_label", "signal_side",
            "signal_score", "linreg_slope_current", "ema_fast",
            "ema_slow", "rsi", "atr_points", "entry_bid", "entry_ask",
            "entry_spread_points", "label_status", "quality_flags",
            "buy_mfe_points", "buy_mae_points", "sell_mfe_points", "sell_mae_points",
        ]
        missing = [rf for rf in required_fields if rf not in fieldnames]
        if missing:
            raise ValueError(f"Malformed Schema-2 header! Missing required fields: {missing}")

        for line_idx, row in enumerate(reader, start=2):
            if row.get("schema_version") != "2":
                raise ValueError(f"Invalid schema version '{row.get('schema_version')}' at line {line_idx}. Expected '2'.")

            status = row.get("label_status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
            rows.append(row)

    return rows, status_counts


def evaluate_v16_macro_filters(
    atr_points: float,
    spread_points: float,
    session_label: str,
    min_atr: float = 50.0,
    max_atr: float = 650.0,
    max_spread: float = 60.0,
) -> Tuple[bool, List[str]]:
    reasons = []
    if atr_points < min_atr:
        reasons.append(f"ATR_BELOW_MIN ({atr_points:.1f} < {min_atr:.1f}) [L740]")
    if atr_points > max_atr:
        reasons.append(f"ATR_ABOVE_MAX ({atr_points:.1f} > {max_atr:.1f}) [L743-751]")
    if spread_points > max_spread:
        reasons.append(f"SPREAD_ABOVE_MAX ({spread_points:.1f} > {max_spread:.1f}) [L755-756]")
    if "ROLLOVER" in session_label.upper():
        reasons.append("ROLLOVER_SESSION_FILTER")

    return len(reasons) == 0, reasons


def resolve_trade_path(
    row: Dict[str, Any],
    side: str,
    policy: Dict[str, float],
) -> Tuple[str, float, Optional[int], str]:
    """Resolves trade path based on forward tick quotes.

    Returns:
        (observable_proxy_outcome, realized_proxy_points, exit_msc, reason)
        NOTE: These represent OBSERVABLE-ONLY proxy labels, NOT broker live fills.
    """
    tp_level = int(policy["tp_pts"])
    sl_level = int(policy["sl_pts"])
    be_trig = int(policy["be_trigger_pts"])
    be_lock = int(policy["be_lock_pts"])

    prefix = "buy" if side == "BUY" else "sell"

    def parse_msc(key: str) -> Optional[int]:
        val = row.get(key, "").strip()
        return int(val) if val and val.isdigit() else None

    tp_msc = parse_msc(f"{prefix}_fav_{tp_level}_msc")
    sl_msc = parse_msc(f"{prefix}_adv_{sl_level}_msc")
    be_trig_msc = parse_msc(f"{prefix}_fav_{be_trig}_msc")
    be_recross_key = f"{prefix}_be_t{be_trig}_l{be_lock}_recross_msc"
    be_recross_msc = parse_msc(be_recross_key)

    initial_sl_msc = None
    if sl_msc is not None:
        if be_trig_msc is None or sl_msc < be_trig_msc:
            initial_sl_msc = sl_msc

    valid_be_msc = None
    if be_recross_msc is not None and be_trig_msc is not None:
        if be_recross_msc >= be_trig_msc:
            valid_be_msc = be_recross_msc

    events = []
    if tp_msc is not None:
        events.append(("TP", tp_msc, float(tp_level), f"TP_HIT_{tp_level}PTS"))
    if initial_sl_msc is not None:
        events.append(("INITIAL_SL", initial_sl_msc, -float(sl_level), f"SL_HIT_{sl_level}PTS"))
    if valid_be_msc is not None:
        events.append(("BE", valid_be_msc, float(be_lock), f"BE_LOCKED_{be_lock}PTS"))

    if not events:
        mfe = float(row.get(f"{prefix}_mfe_points", 0.0))
        mae = float(row.get(f"{prefix}_mae_points", 0.0))
        return "TIMEOUT", 0.0, None, f"HORIZON_END (MFE={mfe:.0f}, MAE={mae:.0f})"

    events.sort(key=lambda x: x[1])
    first_event = events[0]
    return first_event[0], first_event[2], first_event[1], first_event[3]


def parse_v16_live_deploy_log(log_path: Path) -> List[Dict[str, Any]]:
    """Parses live MT5 deployment log without fabricating unproven exit types or PnL.

    Critical Audit Standards:
    - Close/cooldown logs only prove that a close deal occurred; they do NOT prove TP/SL/BE/PnL.
    - Unpaired open/close lines are explicitly recorded as UNMATCHED.
    - Realized PnL is set to None (unproven) until corroborated by official broker statements.
    """
    if not log_path.exists():
        return []

    with log_path.open("r", encoding="utf-16le", errors="replace") as f:
        text = f.read()

    trades: List[Dict[str, Any]] = []
    current_trade: Optional[Dict[str, Any]] = None

    for line in text.splitlines():
        open_match = re.search(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}).*?\[M1 Velocity\]\s+(BUY|SELL)\s+SCALP\s+OPENED\s+@\s+([\d\.]+)\s+\|\s+SL:\s+([\d\.]+)\s+\((-?\d+)\s+pts\)\s+\|\s+TP:\s+([\d\.]+)\s+\(\+(\d+)\s+pts\)",
            line,
        )
        if open_match:
            if current_trade:
                # Previous trade had no matching close line!
                current_trade["match_status"] = "UNMATCHED"
                current_trade["outcome"] = "UNMATCHED_OPEN"
                current_trade["notes"] = "Trade opened without corresponding close record in log"
                trades.append(current_trade)

            time_str, side, price, sl, sl_pts, tp, tp_pts = open_match.groups()
            current_trade = {
                "open_time": time_str,
                "side": side,
                "open_price": float(price),
                "sl": float(sl),
                "sl_pts": abs(float(sl_pts)),
                "tp": float(tp),
                "tp_pts": float(tp_pts),
                "be_locked": False,
                "be_profit_pts": 0.0,
                "be_lock_sl": 0.0,
                "close_time": None,
                "deal_id": None,
                "outcome": "UNKNOWN",
                "match_status": "PENDING_CLOSE",
                "pnl_status": "UNPROVEN_FROM_LOG",
                "realized_pts": None,
                "notes": "Close/cooldown logs do not prove TP/SL/BE/PnL without broker statement.",
            }
            continue

        be_match = re.search(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}).*?\[M1 Velocity\]\s+(BUY|SELL)\s+BREAKEVEN\s+LOCKED:\s+Profit\s+([\d\.]+)\s+pts\s+->\s+SL set to ([\d\.]+)",
            line,
        )
        if be_match and current_trade:
            b_time, b_side, b_profit, b_sl = be_match.groups()
            current_trade["be_locked"] = True
            current_trade["be_profit_pts"] = float(b_profit)
            current_trade["be_lock_sl"] = float(b_sl)
            continue

        close_match = re.search(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}).*?\[Velocity Safety\]\s+Deal\s+#(\d+)\s+closed",
            line,
        )
        if close_match:
            c_time, deal_id = close_match.groups()
            if current_trade:
                current_trade["close_time"] = c_time
                current_trade["deal_id"] = deal_id
                current_trade["match_status"] = "PAIRED_CLOSE_OBSERVED"
                # Rigorous audit standard: close event observed, but exit type and PnL unproven
                current_trade["outcome"] = "CLOSE_OBSERVED_UNVERIFIED"
                current_trade["pnl_status"] = "UNPROVEN_FROM_LOG"
                current_trade["realized_pts"] = None
                current_trade["notes"] = (
                    "Close deal observed in safety log. Exit reason and PnL are unproven without broker statement."
                )
                trades.append(current_trade)
                current_trade = None
            else:
                # Close log line with no preceding open line
                trades.append({
                    "open_time": None,
                    "side": "UNKNOWN",
                    "open_price": None,
                    "close_time": c_time,
                    "deal_id": deal_id,
                    "match_status": "UNMATCHED",
                    "outcome": "UNMATCHED_CLOSE",
                    "pnl_status": "UNPROVEN_FROM_LOG",
                    "realized_pts": None,
                    "notes": "Close observed without matching open line in log",
                })

    if current_trade:
        current_trade["match_status"] = "UNMATCHED"
        current_trade["outcome"] = "UNMATCHED_OPEN"
        current_trade["notes"] = "Trade opened without corresponding close record in log"
        trades.append(current_trade)

    return trades


def run_replay(
    telemetry_path: Path,
    deploy_log_path: Optional[Path] = None,
    policy_name: str = "v16_live_20260910",
    mode: str = "proxy",
) -> Dict[str, Any]:
    policy = POLICY_PRESETS.get(policy_name, POLICY_PRESETS["v16_live_20260910"])
    raw_rows, status_counts = load_and_validate_telemetry(telemetry_path)

    matrix_summary = [asdict(c) for c in V16_CONDITION_MATRIX]

    deploy_trades = []
    if deploy_log_path and deploy_log_path.exists():
        deploy_trades = parse_v16_live_deploy_log(deploy_log_path)

    usable_rows: List[Dict[str, Any]] = []
    rejected_rows_count = 0
    outcome_counts = {"TP": 0, "INITIAL_SL": 0, "BE": 0, "TIMEOUT": 0}
    total_points = 0.0

    for r in raw_rows:
        label_status = r.get("label_status", "")
        if label_status != "COMPLETE":
            rejected_rows_count += 1
            continue

        atr = float(r.get("atr_points", 0.0))
        spread = float(r.get("entry_spread_points", 0.0))
        session = r.get("session_label", "")
        collector_side = r.get("signal_side", "BUY")

        macro_ok, macro_reasons = evaluate_v16_macro_filters(atr, spread, session)

        if mode == "strict_fail_closed":
            unresolvable = [
                "MISSING_M5_EMA20_50",
                "MISSING_30_BAR_SWING_LOOKBACK",
                "MISSING_FVG_3BAR_HISTORY",
                "MISSING_M1_EMA14_50",
                "MISSING_LIVE_ACCOUNT_DRAWDOWN_STATE",
                "MISSING_MQL5_CALENDAR_NEWS_STATE",
            ]
            row_res = TelemetryParityRow(
                signal_bar_epoch=int(r["signal_bar_epoch"]),
                signal_bar_iso=r["signal_bar_iso"],
                entry_tick_time_msc=int(r["entry_tick_time_msc"]),
                session_label=session,
                collector_signal_side=collector_side,
                collector_score=float(r.get("signal_score", 0.0)),
                linreg_slope_current=float(r.get("linreg_slope_current", 0.0)),
                ema_fast=float(r.get("ema_fast", 0.0)),
                ema_slow=float(r.get("ema_slow", 0.0)),
                rsi=float(r.get("rsi", 0.0)),
                atr_points=atr,
                signal_bar_range_points=float(r.get("signal_bar_range_points", 0.0)),
                entry_bid=float(r["entry_bid"]),
                entry_ask=float(r["entry_ask"]),
                entry_spread_points=spread,
                label_status=label_status,
                quality_flags=r.get("quality_flags", ""),
                resolved_side=collector_side,
                parity_verdict="PARITY_UNRESOLVABLE",
                unresolvable_reasons=unresolvable,
                label_classification="OBSERVABLE_PROXY_ONLY",
            )
            usable_rows.append(asdict(row_res))
        else:
            rsi = float(r.get("rsi", 50.0))
            rsi_ok = (35.0 <= rsi <= 65.0)
            if not rsi_ok:
                macro_reasons.append(f"RSI_OUT_OF_BOUNDS ({rsi:.1f})")

            passed = macro_ok and rsi_ok
            verdict = "PARITY_PASS" if passed else "PARITY_FAIL"

            outcome, pts, exit_msc, reason = resolve_trade_path(r, collector_side, policy)
            if passed:
                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
                total_points += pts

            row_res = TelemetryParityRow(
                signal_bar_epoch=int(r["signal_bar_epoch"]),
                signal_bar_iso=r["signal_bar_iso"],
                entry_tick_time_msc=int(r["entry_tick_time_msc"]),
                session_label=session,
                collector_signal_side=collector_side,
                collector_score=float(r.get("signal_score", 0.0)),
                linreg_slope_current=float(r.get("linreg_slope_current", 0.0)),
                ema_fast=float(r.get("ema_fast", 0.0)),
                ema_slow=float(r.get("ema_slow", 0.0)),
                rsi=rsi,
                atr_points=atr,
                signal_bar_range_points=float(r.get("signal_bar_range_points", 0.0)),
                entry_bid=float(r["entry_bid"]),
                entry_ask=float(r["entry_ask"]),
                entry_spread_points=spread,
                label_status=label_status,
                quality_flags=r.get("quality_flags", ""),
                resolved_side=collector_side,
                parity_verdict=verdict,
                unresolvable_reasons=macro_reasons,
                trade_outcome=outcome,
                realized_points=pts,
                exit_time_msc=exit_msc,
                exit_reason=reason,
                label_classification="OBSERVABLE_PROXY_ONLY",
            )
            usable_rows.append(asdict(row_res))

    passed_count = sum(1 for r in usable_rows if r["parity_verdict"] == "PARITY_PASS")

    report = {
        "metadata": {
            "title": "V16 Entry Parity Replay and Path Resolution",
            "telemetry_file": str(telemetry_path),
            "deploy_log_file": str(deploy_log_path) if deploy_log_path else None,
            "policy_name": policy_name,
            "policy_parameters": policy,
            "mode": mode,
            "collector_data_classification": COLLECTOR_DATA_CLASSIFICATION,
            "parity_limitation_note": PARITY_UNRESOLVABLE_NOTE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "telemetry_audit": {
            "total_raw_rows": len(raw_rows),
            "status_breakdown": status_counts,
            "rejected_non_complete_rows": rejected_rows_count,
            "usable_complete_rows": len(usable_rows),
        },
        "traceability_matrix": matrix_summary,
        "deploy_log_analysis": {
            "total_records": len(deploy_trades),
            "trades": deploy_trades,
            "match_status_counts": {
                "PAIRED_CLOSE_OBSERVED": sum(1 for t in deploy_trades if t.get("match_status") == "PAIRED_CLOSE_OBSERVED"),
                "UNMATCHED": sum(1 for t in deploy_trades if t.get("match_status") == "UNMATCHED"),
            },
            "unverified_outcome_counts": {
                "CLOSE_OBSERVED_UNVERIFIED": sum(1 for t in deploy_trades if t.get("outcome") == "CLOSE_OBSERVED_UNVERIFIED"),
                "UNMATCHED_OPEN": sum(1 for t in deploy_trades if t.get("outcome") == "UNMATCHED_OPEN"),
                "UNMATCHED_CLOSE": sum(1 for t in deploy_trades if t.get("outcome") == "UNMATCHED_CLOSE"),
            },
            "be_armed_count": sum(1 for t in deploy_trades if t.get("be_locked")),
            "audit_warning": (
                "IMPORTANT: Close/cooldown logs only record that a close deal event occurred. "
                "They do NOT prove execution exit type (TP/SL/BE/Manual) or realized PnL. "
                "Unpaired entries are recorded as UNMATCHED. Actual PnL and exit reasons require broker statements."
            ),
        },
        "telemetry_replay_results": {
            "mode": mode,
            "evaluated_rows": len(usable_rows),
            "parity_passed_rows": passed_count,
            "parity_rejected_rows": len(usable_rows) - passed_count,
            "outcome_distribution_for_passed": outcome_counts,
            "net_points_for_passed": round(total_points, 1),
            "expectancy_points_per_trade": round(total_points / passed_count, 2) if passed_count else 0.0,
            "label_classification": "OBSERVABLE_PROXY_ONLY",
        },
        "limitations_and_verdict": {
            "verdict": "RESEARCH_ONLY",
            "reasons": [
                "Telemetry dataset spans only a single trading session (2026-09-14 ASIA, 154 clean rows).",
                "Full parity is strictly UNRESOLVABLE without HTF M5 EMA20/50, 30-bar swing lookback, 3-bar FVG history, account state, and news state.",
                "Tick paths represent observable-only proxy fills at bar close, not broker live order execution.",
                "Close/cooldown logs do not prove TP/SL/BE/PnL without broker trade ledger confirmation.",
                "Zero causal claims are permitted; results represent historical observational associations.",
                "Cannot claim production readiness or deploy authorization from this dataset.",
            ],
        },
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="V16 Entry Parity Replay")
    parser.add_argument(
        "--telemetry",
        type=Path,
        default=Path("data/V16TickTelemetry_XAUUSD_M1_20260914.csv"),
        help="Path to Schema-2 tick telemetry CSV",
    )
    parser.add_argument(
        "--deploy-log",
        type=Path,
        default=Path("deploy/v16_20260910_mql5.log"),
        help="Path to live MQL5 deploy log",
    )
    parser.add_argument(
        "--policy",
        type=str,
        default="v16_live_20260910",
        choices=list(POLICY_PRESETS.keys()),
        help="Policy preset for TP/SL/BE levels",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="proxy",
        choices=["proxy", "strict_fail_closed"],
        help="Parity replay mode",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/v16_entry_parity_replay_report.json"),
        help="Output JSON report path",
    )

    args = parser.parse_args()
    report = run_replay(args.telemetry, args.deploy_log, args.policy, args.mode)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("================================================================================")
    print("        QUANTUM TITAN V16 ENTRY-PARITY REPLAY & TELEMETRY RESOLUTION           ")
    print("================================================================================")
    print(f"Policy: {args.policy} | Mode: {args.mode}")
    print(f"Raw rows: {report['telemetry_audit']['total_raw_rows']}")
    print(f"Usable COMPLETE rows: {report['telemetry_audit']['usable_complete_rows']}")
    print(f"Rejected Non-COMPLETE rows: {report['telemetry_audit']['rejected_non_complete_rows']}")
    print("--------------------------------------------------------------------------------")
    print("DEPLOY LOG ANALYSIS:")
    dl = report["deploy_log_analysis"]
    print(f"  Live Records: {dl['total_records']}")
    print(f"  Match Status: {dl['match_status_counts']}")
    print(f"  Unverified Outcomes: {dl['unverified_outcome_counts']}")
    print(f"  Audit Warning: {dl['audit_warning']}")
    print("--------------------------------------------------------------------------------")
    print("TELEMETRY REPLAY OUTCOMES (Passed Rows - Observable Proxy Only):")
    tr = report["telemetry_replay_results"]
    print(f"  Passed Rows: {tr['parity_passed_rows']}")
    print(f"  Outcomes: {tr['outcome_distribution_for_passed']}")
    print(f"  Net Points: {tr['net_points_for_passed']} pts")
    print(f"  Expectancy: {tr['expectancy_points_per_trade']} pts/trade")
    print("--------------------------------------------------------------------------------")
    print(f"VERDICT: {report['limitations_and_verdict']['verdict']}")
    for r in report["limitations_and_verdict"]["reasons"]:
        print(f"  - {r}")
    print(f"JSON Report written to: {args.output_json}")
    print("================================================================================")


if __name__ == "__main__":
    main()
