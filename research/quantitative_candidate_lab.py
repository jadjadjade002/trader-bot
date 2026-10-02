"""
Quantitative Candidate Lab
Tests 3 quantitative hypotheses on XAUUSD M1 forward snapshot with realistic execution,
conservative intrabar collision handling, and chronological train/validation splits.
"""

import os
import glob
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple

def load_dataset() -> pd.DataFrame:
    files = sorted(glob.glob("data/v21_snapshot_20260924_a/QTForward_XAUUSD_M1_*.csv"))
    if not files:
        raise FileNotFoundError("Snapshot CSV files not found in data/v21_snapshot_20260924_a/")
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df["time"] = pd.to_datetime(df["time_broker_iso"])
    df = df.sort_values("time").reset_index(drop=True)
    return df

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    n = len(df)
    
    # ATR 14
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    atr = pd.Series(tr).rolling(14).mean().values
    df["atr14"] = atr
    
    # EMAs
    df["ema6"] = pd.Series(c).ewm(span=6, adjust=False).mean().values
    df["ema20"] = pd.Series(c).ewm(span=20, adjust=False).mean().values
    df["ema24"] = pd.Series(c).ewm(span=24, adjust=False).mean().values
    df["ema50"] = pd.Series(c).ewm(span=50, adjust=False).mean().values
    df["ema200"] = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # Rolling ATR median (120 bars)
    df["atr_median120"] = pd.Series(atr).rolling(120).median().values
    df["atr_ratio"] = np.where(df["atr_median120"] > 0, df["atr14"] / df["atr_median120"], 1.0)
    
    # Kaufman Efficiency Ratio (KER 20)
    change = np.abs(c - np.roll(c, 20))
    vol = pd.Series(np.abs(c - np.roll(c, 1))).rolling(20).sum().values
    ker = np.where(vol > 0, change / vol, 0.0)
    ker[:20] = 0.0
    df["ker20"] = ker
    
    # Session timing (Broker time)
    df["hour"] = df["time"].dt.hour
    df["minute"] = df["time"].dt.minute
    df["minute_of_day"] = df["hour"] * 60 + df["minute"]
    
    return df

def simulate_strategy(df: pd.DataFrame, signals: np.ndarray, sl_pts: np.ndarray, tp_pts: np.ndarray, max_hold_bars: int = 120) -> List[Dict[str, Any]]:
    """
    Simulates trades with conservative execution:
    - Signal on bar i (close).
    - Entry at bar i+1 open.
    - Cost: spread in points added to entry for buy / subtracted for sell.
    - Intrabar check: if both TP and SL are hit in the same bar, assume SL first (worst-case).
    - 0.01 lot = $0.01 per point on XAUUSD.
    """
    trades = []
    in_pos = False
    entry_idx = 0
    pos_dir = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    cost_pts = 0.0
    
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    spreads = df["bar_spread_points"].values
    times = df["time"].values
    point = 0.01
    
    n = len(df)
    
    for i in range(1, n - 1):
        if not in_pos:
            sig = signals[i-1]
            if sig != 0:
                pos_dir = int(sig)
                entry_idx = i
                bar_spread = spreads[i]
                if np.isnan(bar_spread) or bar_spread <= 0:
                    bar_spread = 20.0
                cost_pts = bar_spread
                
                # Entry at Open of bar i
                if pos_dir == 1:
                    entry_price = opens[i] + (bar_spread * point) # Buy at Ask
                    sl_dist = sl_pts[i-1] * point
                    tp_dist = tp_pts[i-1] * point
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + tp_dist
                else:
                    entry_price = opens[i] # Sell at Bid
                    sl_dist = sl_pts[i-1] * point
                    tp_dist = tp_pts[i-1] * point
                    sl_price = entry_price + sl_dist
                    tp_price = entry_price - tp_dist
                
                in_pos = True
        else:
            held_bars = i - entry_idx
            curr_h = highs[i]
            curr_l = lows[i]
            exit_price = 0.0
            exit_reason = ""
            
            if pos_dir == 1:
                hit_sl = (curr_l <= sl_price)
                hit_tp = (curr_h >= tp_price)
                
                if hit_sl and hit_tp:
                    exit_price = sl_price
                    exit_reason = "SL_COLLISION"
                elif hit_sl:
                    exit_price = sl_price
                    exit_reason = "SL"
                elif hit_tp:
                    exit_price = tp_price
                    exit_reason = "TP"
                elif held_bars >= max_hold_bars:
                    exit_price = closes[i]
                    exit_reason = "TIME"
            else:
                spread_val = spreads[i] * point if spreads[i] > 0 else 0.20
                hit_sl = (curr_h + spread_val >= sl_price)
                hit_tp = (curr_l + spread_val <= tp_price)
                
                if hit_sl and hit_tp:
                    exit_price = sl_price
                    exit_reason = "SL_COLLISION"
                elif hit_sl:
                    exit_price = sl_price
                    exit_reason = "SL"
                elif hit_tp:
                    exit_price = tp_price
                    exit_reason = "TP"
                elif held_bars >= max_hold_bars:
                    exit_price = closes[i] + spread_val
                    exit_reason = "TIME"
                    
            if exit_reason != "":
                if pos_dir == 1:
                    pnl_pts = (exit_price - entry_price) / point
                else:
                    pnl_pts = (entry_price - exit_price) / point
                    
                pnl_usd = pnl_pts * 0.01
                
                trades.append({
                    "entry_time": times[entry_idx],
                    "exit_time": times[i],
                    "direction": pos_dir,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "cost_pts": cost_pts,
                    "pnl_pts": pnl_pts,
                    "pnl_usd": pnl_usd,
                    "held_bars": held_bars,
                    "exit_reason": exit_reason
                })
                in_pos = False
                
    return trades

def compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"trades": 0, "net_usd": 0.0, "pf": 0.0, "winrate": 0.0, "expectancy": 0.0, "max_dd_usd": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "payoff": 0.0}
    
    pnls = [t["pnl_usd"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    net = sum(pnls)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    winrate = len(wins) / len(pnls)
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses)) / len(losses)) if losses else 0.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    expectancy = net / len(pnls)
    
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = np.max(dd) if len(dd) > 0 else 0.0
    
    return {
        "trades": len(trades),
        "net_usd": round(net, 2),
        "pf": round(pf, 2),
        "winrate": round(winrate * 100, 1),
        "expectancy": round(expectancy, 2),
        "max_dd_usd": round(max_dd, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff": round(payoff, 2)
    }

# --- Candidate 0: Baseline V16.59 (EMA6/24 crossover, 3-bar hold, session >= 18:00 or < 01:57) ---
def run_v16_59(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.full(n, 500.0) # Emergency stop ~ 5 ATR (500 pts)
    tp = np.full(n, 1000.0)
    
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    fast = df["ema6"].values
    slow = df["ema24"].values
    atr = df["atr14"].values
    ratio = df["atr_ratio"].values
    spread = df["bar_spread_points"].values
    mod = df["minute_of_day"].values
    
    for i in range(1, n):
        # Session check
        sess_ok = (mod[i] >= 1080 or mod[i] < 117)
        if not sess_ok or spread[i] > 40.0:
            continue
        if ratio[i] < 0.5 or ratio[i] > 1.5:
            continue
        if abs(c[i] - slow[i]) > 0.35 * atr[i] or (h[i] - l[i]) > 1.5 * atr[i]:
            continue
            
        prior_fast = fast[i-1]
        prior_slow = slow[i-1]
        
        if fast[i] > slow[i] and prior_fast <= prior_slow:
            sig[i] = 1
        elif fast[i] < slow[i] and prior_fast >= prior_slow:
            sig[i] = -1
            
    return sig, sl, tp

# --- Candidate 1: Session-Anchored Trend Pullback (London/NY overlap, EMA 50/200 trend, EMA 20 pullback, 2.0R target) ---
def run_candidate_1(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    ema20 = df["ema20"].values
    ema50 = df["ema50"].values
    ema200 = df["ema200"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    ker = df["ker20"].values
    
    for i in range(1, n):
        # Prime sessions: London & NY (10:00 to 20:00 broker time)
        if hour[i] < 10 or hour[i] >= 20:
            continue
        if spread[i] > 25.0:
            continue
        # Market not dead/chop
        if ker[i] < 0.20:
            continue
            
        # Uptrend: EMA 50 > EMA 200 and EMA 20 > EMA 50
        if ema50[i] > ema200[i] and ema20[i] > ema50[i]:
            # Pullback to EMA 20: Previous low dipped to or below EMA 20, but current close reclaims above EMA 20
            if (l[i-1] <= ema20[i-1] or l[i] <= ema20[i]) and c[i] > ema20[i] and c[i] > o[i]:
                # Bullish confirmation
                sig[i] = 1
                stop_dist = max(2.0 * atr[i] / 0.01, 150.0) # in points (min 150 pts = $1.50)
                sl[i] = stop_dist
                tp[i] = stop_dist * 2.0 # 2.0R payoff!
                
        # Downtrend: EMA 50 < EMA 200 and EMA 20 < EMA 50
        elif ema50[i] < ema200[i] and ema20[i] < ema50[i]:
            # Pullback to EMA 20: Previous high reached or rose above EMA 20, but current close rejects below EMA 20
            if (h[i-1] >= ema20[i-1] or h[i] >= ema20[i]) and c[i] < ema20[i] and c[i] < o[i]:
                # Bearish confirmation
                sig[i] = -1
                stop_dist = max(2.0 * atr[i] / 0.01, 150.0)
                sl[i] = stop_dist
                tp[i] = stop_dist * 2.0 # 2.0R payoff!
                
    return sig, sl, tp

# --- Candidate 2: London/NY Momentum Retest (20-bar Donchian High/Low breakout + 1-bar retest hold) ---
def run_candidate_2(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    
    # Rolling 20-bar High and Low
    roll_h = pd.Series(h).shift(1).rolling(20).max().values
    roll_l = pd.Series(l).shift(1).rolling(20).min().values
    
    for i in range(21, n):
        # Active sessions: 11:00 to 18:00 broker time
        if hour[i] < 11 or hour[i] >= 18:
            continue
        if spread[i] > 25.0:
            continue
            
        # Breakout occurred on previous bar, current bar holds above breakout level (retest)
        if c[i-1] > roll_h[i-1] and l[i] >= roll_h[i-1] - (0.5 * atr[i]) and c[i] > o[i]:
            sig[i] = 1
            stop_dist = max(1.5 * atr[i] / 0.01, 150.0)
            sl[i] = stop_dist
            tp[i] = stop_dist * 2.0 # 2.0R
        elif c[i-1] < roll_l[i-1] and h[i] <= roll_l[i-1] + (0.5 * atr[i]) and c[i] < o[i]:
            sig[i] = -1
            stop_dist = max(1.5 * atr[i] / 0.01, 150.0)
            sl[i] = stop_dist
            tp[i] = stop_dist * 2.0 # 2.0R
            
    return sig, sl, tp

# --- Candidate 3: KER-Gated Mean Reversion (Low noise KER < 0.20, fade 2.5 ATR stretch, TP at mean) ---
def run_candidate_3(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    ema50 = df["ema50"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    ker = df["ker20"].values
    hour = df["hour"].values
    
    for i in range(1, n):
        # Active hours: 10:00 to 21:00
        if hour[i] < 10 or hour[i] >= 21:
            continue
        if spread[i] > 22.0:
            continue
        # Only when KER is low (Chop / Mean Reverting regime)
        if ker[i] >= 0.22:
            continue
            
        dev = (c[i] - ema50[i]) / (atr[i] if atr[i] > 0 else 1.0)
        
        # Over-extended to downside -> Buy reversion back to EMA50
        if dev <= -2.5 and c[i] > o[i]:
            sig[i] = 1
            target_pts = abs(c[i] - ema50[i]) / 0.01
            stop_pts = target_pts * 1.0 # 1:1 R:R
            sl[i] = stop_pts
            tp[i] = target_pts
        # Over-extended to upside -> Sell reversion back to EMA50
        elif dev >= 2.5 and c[i] < o[i]:
            sig[i] = -1
            target_pts = abs(c[i] - ema50[i]) / 0.01
            stop_pts = target_pts * 1.0
            sl[i] = stop_pts
            tp[i] = target_pts
            
    return sig, sl, tp

def main():
    print("Loading data...")
    df = load_dataset()
    print(f"Total dataset: {len(df)} bars from {df['time'].min()} to {df['time'].max()}")
    df = calculate_indicators(df)
    
    # Chronological Split
    # Dev: 2026-09-09 to 2026-09-17 inclusive (up to 2026-09-17 23:59:59)
    # Val: 2026-09-18 to 2026-09-24 inclusive
    split_date = pd.Timestamp("2026-09-18 00:00:00")
    df_dev = df[df["time"] < split_date].copy().reset_index(drop=True)
    df_val = df[df["time"] >= split_date].copy().reset_index(drop=True)
    
    print(f"Development Set: {len(df_dev)} bars ({df_dev['time'].min()} -> {df_dev['time'].max()})")
    print(f"Validation Set:  {len(df_val)} bars ({df_val['time'].min()} -> {df_val['time'].max()})\n")
    
    strategies = [
        ("Baseline V16.59 (EMA6/24 3-bar hold)", run_v16_59, 3),
        ("Candidate 1: Session Trend Pullback (2.0R)", run_candidate_1, 60),
        ("Candidate 2: Session Retest Breakout (2.0R)", run_candidate_2, 60),
        ("Candidate 3: KER Mean Reversion (1.0R)", run_candidate_3, 40),
    ]
    
    results = []
    
    for name, func, max_hold in strategies:
        # Dev evaluation
        sig_d, sl_d, tp_d = func(df_dev)
        trades_d = simulate_strategy(df_dev, sig_d, sl_d, tp_d, max_hold_bars=max_hold)
        m_d = compute_metrics(trades_d)
        
        # Val evaluation
        sig_v, sl_v, tp_v = func(df_val)
        trades_v = simulate_strategy(df_val, sig_v, sl_v, tp_v, max_hold_bars=max_hold)
        m_v = compute_metrics(trades_v)
        
        results.append({
            "name": name,
            "dev_trades": m_d["trades"],
            "dev_net": m_d["net_usd"],
            "dev_pf": m_d["pf"],
            "dev_wr": m_d["winrate"],
            "dev_payoff": m_d["payoff"],
            "dev_dd": m_d["max_dd_usd"],
            "val_trades": m_v["trades"],
            "val_net": m_v["net_usd"],
            "val_pf": m_v["pf"],
            "val_wr": m_v["winrate"],
            "val_payoff": m_v["payoff"],
            "val_dd": m_v["max_dd_usd"]
        })
        
    res_df = pd.DataFrame(results)
    print("=" * 115)
    print(f"{'STRATEGY':<42} | {'DEV TRADES':<10} {'DEV NET':<9} {'DEV PF':<7} {'DEV WR%':<8} | {'VAL TRADES':<10} {'VAL NET':<9} {'VAL PF':<7} {'VAL WR%':<8}")
    print("=" * 115)
    for r in results:
        print(f"{r['name']:<42} | {r['dev_trades']:<10} ${r['dev_net']:<8.2f} {r['dev_pf']:<7.2f} {r['dev_wr']:<7.1f}% | {r['val_trades']:<10} ${r['val_net']:<8.2f} {r['val_pf']:<7.2f} {r['val_wr']:<7.1f}%")
    print("=" * 115)
    
if __name__ == "__main__":
    main()
