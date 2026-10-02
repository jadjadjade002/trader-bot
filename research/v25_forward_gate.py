"""Locked prospective review gate for V25 native MT5 reports.

Passing means *reviewable*, never approved to deploy. Previous test periods must
fail the date gate. This program does not connect to a terminal or place orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.analyze_v17_report import analyze


FROZEN_BROKER_CUTOFF = datetime.fromisoformat("2026-09-28T12:10:00")
FROZEN_SOURCE_SHA256 = "A087DECBF02FBB120D9154C31AA278A8575ED96D6688CDDE8A2B1E488182BD44"
FROZEN_BINARY_SHA256 = "D1E9DCC190879BCC8D359BBC4D83A102D22B11B77E1FC62F0A0832579D773F51"


def evaluate(report_path: Path, metadata_path: Path) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    result = analyze(report_path)
    trades = result["closed"]
    reasons: list[str] = []
    if metadata.get("sourceSha256") != FROZEN_SOURCE_SHA256:
        reasons.append("SOURCE_HASH_MISMATCH")
    if metadata.get("binarySha256") != FROZEN_BINARY_SHA256:
        reasons.append("BINARY_HASH_MISMATCH")
    if any(datetime.fromisoformat(t["open"]) < FROZEN_BROKER_CUTOFF for t in trades):
        reasons.append("REUSED_PRE_FREEZE_TRADE")
    if not trades:
        reasons.append("NO_FORWARD_TRADES")
    if len(trades) < 30:
        reasons.append("FEWER_THAN_30_TRADES")
    days = {t["open"][:10] for t in trades}
    if len(days) < 10:
        reasons.append("FEWER_THAN_10_TRADE_DAYS")
    if result["net"] <= 0:
        reasons.append("NONPOSITIVE_NET")
    pf = float(result["native"].get("Profit Factor", "0").replace(" ", ""))
    if pf < 1.30:
        reasons.append("PF_BELOW_1_30")
    equity_dd_raw = result["native"].get("Equity Drawdown Relative", "")
    try:
        dd_pct = float(equity_dd_raw.split("%")[0].strip())
    except ValueError:
        reasons.append("DRAWDOWN_UNREADABLE")
        dd_pct = None
    if dd_pct is not None and dd_pct > 15.0:
        reasons.append("DRAWDOWN_ABOVE_15_PERCENT")
    wins = [t["net"] for t in trades if t["net"] > 0]
    largest_win_share = max(wins) / sum(wins) if wins else None
    if largest_win_share is not None and largest_win_share > 0.35:
        reasons.append("SINGLE_WIN_CONCENTRATION_ABOVE_35_PERCENT")
    return {
        "status": "REVIEWABLE_NOT_DEPLOY_APPROVED" if not reasons else "BLOCKED_OR_INCOMPLETE",
        "cutoff_broker": FROZEN_BROKER_CUTOFF.isoformat(),
        "report": str(report_path),
        "trades": len(trades),
        "trade_days": len(days),
        "net_usd": result["net"],
        "profit_factor": pf,
        "equity_dd_pct": dd_pct,
        "largest_win_share": round(largest_win_share, 4) if largest_win_share is not None else None,
        "reasons": reasons,
        "deployment_approved": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.report, args.metadata), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
