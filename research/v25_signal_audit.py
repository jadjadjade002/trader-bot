"""Read-only V24 trade attribution. No simulated strategy or promotion claims.

Uses position-ID economics exported by the parity-matched native V24 harness.
Five-bar impulse is descriptive and available only across contiguous M1 bars.
"""
from collections import defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.analyze_v23_backtest import bucket, csv_rows, parse_deals, report_rows

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/v23_tuning_20261006/runs/complete5m_batch1_descriptive_best_proposed"


def impulse_label(row, previous, direction, threshold=.25):
    """Closed M1 five-minute delta in trade direction, scaled by entry M1 ATR.

    Null means unknown, not zero. Caller proves all intervening bars contiguous.
    """
    if previous is None:
        return "unknown", None
    if direction not in ("buy", "sell"):
        raise ValueError("Unsupported trade direction")
    atr = float(row["atr"])
    now, past = float(row["retest_close"]), float(previous["retest_close"])
    if not all(math.isfinite(v) for v in (atr, now, past, threshold)) or threshold < 0:
        raise ValueError("Invalid feature or threshold")
    if atr <= 0:
        raise ValueError("Nonpositive ATR")
    delta = (now - past) / atr
    signed = delta if direction == "buy" else -delta
    return ("aligned" if signed >= threshold else "opposed" if signed <= -threshold else "flat"), signed


def analyze(folder=RUN):
    folder = Path(folder)
    name = folder.name
    trades, cash = parse_deals(csv_rows(folder / (name + "_deals.csv")))
    native, _ = report_rows(folder / (name + ".htm"))
    if native["History Quality"] != "100% real ticks":
        raise ValueError("Non-real-tick report")
    total = bucket(trades)
    if total["trades"] != int(native["Total Trades"]) or abs(total["net"] - float(native["Total Net Profit"].replace(" ", ""))) > .021:
        raise ValueError("Native economics mismatch")
    raw = csv_rows(folder / (name + "_raw.csv"))
    by_deal = {}
    for i, row in enumerate(raw):
        ticket = int(row["deal_ticket"])
        if ticket:
            if ticket in by_deal:
                raise ValueError("Duplicate entry-ticket join")
            by_deal[ticket] = (i, row)
    times = [datetime.strptime(r["bar"], "%Y.%m.%d %H:%M:%S") for r in raw]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Nonmonotonic bar evidence")
    regime, regime_side, spreads, signed = defaultdict(list), defaultdict(list), [], []
    for t in trades:
        i, r = by_deal[t["deals"][0]["ticket"]]
        if r["order_attempt"] not in ("true", "1") or int(r["retcode"]) != 10009:
            raise ValueError("Unconfirmed entry attempt")
        previous = raw[i-5] if i >= 5 and all(times[k]-times[k-1] == timedelta(minutes=1) for k in range(i-4, i+1)) else None
        label, value = impulse_label(r, previous, t["direction"])
        regime[label].append(t)
        regime_side[(label, t["direction"])].append(t)
        if value is not None:
            signed.append(value)
        spread = float(r["ask"]) - float(r["bid"])
        if spread < 0:
            raise ValueError("Crossed snapshot quote")
        spreads.append(spread / float(r["atr"]))
    if set(by_deal) != {t["deals"][0]["ticket"] for t in trades}:
        raise ValueError("Unmatched filled attempt")
    months = sorted({t["close"][:7] for t in trades})
    return dict(source=str(folder.relative_to(ROOT)), total=total,
        direction={side:bucket([t for t in trades if t["direction"] == side]) for side in ("buy", "sell")},
        month_direction={m:{side:bucket([t for t in trades if t["close"][:7] == m and t["direction"] == side]) for side in ("buy", "sell")} for m in months},
        exits={reason:bucket([t for t in trades if t["exit_reason"] == reason]) for reason in sorted({t["exit_reason"] for t in trades})},
        five_bar_impulse={label:bucket(items) for label, items in regime.items()},
        five_bar_impulse_direction={label+"_"+side:bucket(items) for (label, side), items in regime_side.items()},
        entry_spread_atr=dict(mean=sum(spreads)/len(spreads), maximum=max(spreads)),
        entry_hour_broker={h:bucket([t for t in trades if int(t["open"][11:13]) == h]) for h in range(24)},
        joined_positions=len(trades), native_quality=native["History Quality"],
        limitations=["Five-bar impulse threshold .25 ATR chosen for audit, not optimized or a tested filter",
                      "No M5 EMA regime snapshots exported, so exact M5 trend reconstruction unavailable",
                      "Spread already embedded in executed-price PnL. DEAL_PROFIT is not pre-spread gross alpha",
                      "Existing five months already inspected. No fresh out-of-sample claim",
                      "Filtered trade subsets are not native strategy counterfactuals due to occupancy/breaker changes"])


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
