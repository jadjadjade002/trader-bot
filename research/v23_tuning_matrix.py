"""Frozen bounded grid and deterministic configuration selection."""
from itertools import product
import math

SL_VALUES = (1.0, 1.5, 2.0)
TP_VALUES = (1.0, 1.5, 2.0, 3.0)
BE_VALUES = (0.0, 0.8, 1.2)
MODE_NAMES = {0: "vm_fade", 1: "normal", 2: "proposed"}


def grid(mode):
    if mode not in MODE_NAMES:
        raise ValueError("Unknown model")
    return [dict(mode=mode, sl_atr=sl, tp_r=tp, be_r=be, be_lock_r=0.05)
            for sl, tp, be in product(SL_VALUES, TP_VALUES, BE_VALUES)]


def metrics(row):
    def number(name):
        v = float(row[name])
        if not math.isfinite(v):
            raise ValueError(f"Invalid {name}")
        return v
    net, positive, negative = (number(k) for k in ("net", "gross_net_wins", "gross_net_losses"))
    positions, wins = (number(k) for k in ("positions", "wins"))
    if positions != int(positions) or wins != int(wins) or not 0 <= wins <= positions:
        raise ValueError("Invalid position counts")
    if positive < 0 or negative < 0 or abs(net - positive + negative) > 0.03:
        raise ValueError("Net reconciliation failed")
    if abs(net - number("native_net")) > 0.03:
        raise ValueError("Native profit reconciliation failed")
    return dict(net=net, pf=positive/negative if negative else None,
                trades=int(positions), wins=int(wins), dd=number("equity_dd"),
                dd_pct=number("equity_dd_pct"))


def rank(rows, min_trades=100):
    qualified = []
    for row in rows:
        m = metrics(row)
        if m["net"] > 0 and m["trades"] >= min_trades and m["pf"] is not None and m["pf"] >= 1.2:
            qualified.append((row, m))
    return [row for row, m in sorted(qualified, key=lambda x: (x[1]["dd_pct"], -x[1]["net"]))]
