"""Conservative, reproducible bar-level audit of the V23 claim on V21 data.

This is a diagnostic, NOT an MT5 tick backtest. In particular the collector does
not record the ask high/low, so sell stops use a conservative spread proxy.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd


POINT = 0.01
USD_PER_POINT = 0.01  # Valid only for the sampled 0.01-standard-lot XAUUSD contract.


def load_bars(directory: Path) -> pd.DataFrame:
    files = sorted(glob.glob(str(directory / "QTForward_XAUUSD_M1_*.csv")))
    if not files:
        raise ValueError("No collector bar files")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df = df.sort_values("time_broker_epoch").reset_index(drop=True)
    if df.time_broker_epoch.duplicated().any():
        raise ValueError("Duplicate timestamps")
    required = ("open", "high", "low", "close", "open_bid", "open_ask",
                "open_spread_points", "bar_spread_points", "flags")
    if df[list(required)].isna().any().any():
        raise ValueError("Missing prices, spread, or quality flag")
    df["time"] = pd.to_datetime(df.time_broker_iso)
    df["continuous"] = df.time_broker_epoch.diff().eq(60)
    return df


def v23_signals(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Match V23's closed-bar 20-bar Donchian + retest setup, before inversion."""
    c, o, h, l = (df[k].to_numpy(dtype=float) for k in ("close", "open", "high", "low"))
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    ref_h = pd.Series(h).shift(1).rolling(20).max().to_numpy()
    ref_l = pd.Series(l).shift(1).rolling(20).min().to_numpy()
    sig = np.zeros(len(df), dtype=np.int8)
    for i in range(22, len(df) - 1):
        if not (df.continuous.iloc[i] and df.continuous.iloc[i - 1]):
            continue
        if not np.isfinite(atr[i]) or not 11 <= df.time.iloc[i + 1].hour < 16:
            continue
        if c[i - 1] > ref_h[i - 1] and l[i] >= ref_h[i - 1] - .5 * atr[i] and c[i] > o[i]:
            sig[i] = 1
        elif c[i - 1] < ref_l[i - 1] and h[i] <= ref_l[i - 1] + .5 * atr[i] and c[i] < o[i]:
            sig[i] = -1
    return sig, atr


def simulate(df: pd.DataFrame, *, invert: bool, max_entry_spread: float | None,
             spread_stress: float = 1.0, conservative_gaps: bool = True) -> list[dict]:
    """Entry at observed first quote of next bar; inspect entry bar for SL/TP.

    Bad gaps or unsupported prices close at a conservative loss, not a free skip.
    No commissions/slippage included, so result remains an upper bound on live PnL.
    """
    signal, atr = v23_signals(df)
    trades: list[dict] = []
    position = None
    for i in range(23, len(df)):
        row = df.iloc[i]
        if position is None and signal[i - 1]:
            if not row.continuous or row["flags"] != "OK":
                continue
            raw_spread = float(row.open_spread_points)
            spread = raw_spread * spread_stress
            if raw_spread <= 0 or (max_entry_spread is not None and raw_spread > max_entry_spread):
                continue
            direction = int(signal[i - 1]) * (-1 if invert else 1)
            bid = float(row.open_bid)
            ask = bid + spread * POINT
            dist = max(1.5 * float(atr[i - 1]), 1.5)
            entry = ask if direction > 0 else bid
            position = dict(index=i, direction=direction, entry=entry,
                            stop=entry - direction * dist,
                            target=entry + direction * 2 * dist,
                            entry_time=str(row.time), entry_spread=spread)
        if position is None:
            continue
        # Quote uncertainty: only bid OHLC collected. For shorts, use the wider
        # of entry and close spread at ask extremes (not exact tick path).
        spread = max(float(row.open_spread_points), float(row.bar_spread_points)) * spread_stress * POINT
        if not row.continuous and i > position["index"]:
            if conservative_gaps:
                price = position["stop"]
                reason = "GAP_ASSUMED_STOP"
            else:
                position = None
                continue
        else:
            direction = position["direction"]
            high = float(row.high) + (spread if direction < 0 else 0)
            low = float(row.low) + (spread if direction < 0 else 0)
            stop_hit = low <= position["stop"] if direction > 0 else high >= position["stop"]
            target_hit = high >= position["target"] if direction > 0 else low <= position["target"]
            if stop_hit:
                price, reason = position["stop"], "STOP_OR_COLLISION"
            elif target_hit:
                price, reason = position["target"], "TARGET"
            elif i - position["index"] >= 60:
                price = float(row.close) + (spread if direction < 0 else 0)
                reason = "TIME"
            else:
                continue
        pnl = (price - position["entry"]) * position["direction"] / POINT * USD_PER_POINT
        trades.append(dict(entry_time=position["entry_time"], exit_time=str(row.time),
                           direction=position["direction"], entry_spread=position["entry_spread"],
                           pnl=round(pnl, 4), reason=reason))
        position = None
    return trades


def metrics(trades: list[dict]) -> dict:
    pnl = np.array([t["pnl"] for t in trades], dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    dd = np.maximum.accumulate(np.r_[0.0, np.cumsum(pnl)]) - np.r_[0.0, np.cumsum(pnl)]
    return dict(trades=len(trades), net_usd=round(float(pnl.sum()), 2),
                win_rate_pct=round(100 * len(wins) / len(pnl), 1) if len(pnl) else 0,
                profit_factor=round(float(wins.sum() / -losses.sum()), 3) if losses.sum() < 0 else None,
                max_drawdown_usd=round(float(dd.max()), 2),
                entry_bar_exits=sum(t["entry_time"] == t["exit_time"] for t in trades),
                median_entry_spread=round(float(np.median([t["entry_spread"] for t in trades])), 1) if trades else None)


def audit(directory: Path) -> dict:
    df = load_bars(directory)
    spreads = df.open_spread_points.to_numpy(dtype=float)
    result = dict(source=str(directory), bars=len(df), first_time=str(df.time.iloc[0]),
                  last_time=str(df.time.iloc[-1]), non_ok_flags=int((df["flags"] != "OK").sum()),
                  gaps=int((~df.continuous.iloc[1:]).sum()),
                  open_spread_points={"median": float(np.median(spreads)),
                                      "p90": float(np.percentile(spreads, 90)),
                                      "p99": float(np.percentile(spreads, 99)),
                                      "over_25_pct": round(float((spreads > 25).mean() * 100), 1)})
    cut = pd.Timestamp("2026-09-24 11:00:00")
    result["scenarios"] = {}
    for name, invert, guard, stress in (
        ("v23_defaults_inverted_no_spread_guard", True, None, 1.0),
        ("v23_inverted_spread_25", True, 25, 1.0),
        ("v23_noninverted_spread_25", False, 25, 1.0),
        ("v23_inverted_spread_25_double_cost", True, 25, 2.0),
    ):
        trades = simulate(df, invert=invert, max_entry_spread=guard, spread_stress=stress)
        result["scenarios"][name] = {"all": metrics(trades),
                                      "pre_sep24": metrics([t for t in trades if pd.Timestamp(t["entry_time"]) < cut]),
                                      "post_sep24": metrics([t for t in trades if pd.Timestamp(t["entry_time"]) >= cut])}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), indent=2))


if __name__ == "__main__":
    main()
