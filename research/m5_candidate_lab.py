"""
M5 Quantitative Research Lab
Evaluates M5 session breakout, pullback, and swing strategies with conservative execution.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from research.quantitative_candidate_lab import load_dataset, compute_metrics

def prepare_m5_data() -> pd.DataFrame:
    df_m1 = load_dataset()
    df_m1.set_index('time', inplace=True)
    df_m5 = df_m1.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum',
        'bar_spread_points': 'mean'
    }).dropna().reset_index()
    
    c = df_m5['close'].values
    h = df_m5['high'].values
    l = df_m5['low'].values
    n = len(df_m5)
    
    # ATR 14
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    df_m5['atr14'] = pd.Series(tr).rolling(14).mean().values
    
    df_m5['ema9'] = pd.Series(c).ewm(span=9, adjust=False).mean().values
    df_m5['ema21'] = pd.Series(c).ewm(span=21, adjust=False).mean().values
    df_m5['ema50'] = pd.Series(c).ewm(span=50, adjust=False).mean().values
    df_m5['ema200'] = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # KER 10 on M5
    change = np.abs(c - np.roll(c, 10))
    vol = pd.Series(np.abs(c - np.roll(c, 1))).rolling(10).sum().values
    ker = np.where(vol > 0, change / vol, 0.0)
    ker[:10] = 0.0
    df_m5['ker10'] = ker
    
    df_m5['hour'] = df_m5['time'].dt.hour
    return df_m5

def simulate_m5_strategy(df: pd.DataFrame, signals: np.ndarray, sl_pts: np.ndarray, tp_pts: np.ndarray, max_hold_bars: int = 36) -> List[Dict[str, Any]]:
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
                
                if pos_dir == 1:
                    entry_price = opens[i] + (bar_spread * point)
                    sl_dist = sl_pts[i-1] * point
                    tp_dist = tp_pts[i-1] * point
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + tp_dist
                else:
                    entry_price = opens[i]
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

# Strategy 1 on M5: Dynamic Trend Pullback with Session Filter & 1.5R target
def run_m5_trend_pullback(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    ema21 = df["ema21"].values
    ema50 = df["ema50"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    ker = df["ker10"].values
    
    for i in range(1, n):
        # London & NY overlap: 11:00 to 20:00
        if hour[i] < 11 or hour[i] >= 20:
            continue
        if spread[i] > 25.0:
            continue
        if ker[i] < 0.25: # filter chop
            continue
            
        # Uptrend: EMA 21 > EMA 50
        if ema21[i] > ema50[i]:
            # Pullback to EMA 21: Low touched EMA 21 and bar closes green above EMA 21
            if l[i] <= ema21[i] and c[i] > ema21[i] and c[i] > o[i]:
                sig[i] = 1
                stop_dist = max(1.5 * atr[i] / 0.01, 250.0) # min 250 pts = $2.50
                sl[i] = stop_dist
                tp[i] = stop_dist * 1.5 # 1.5R target
                
        # Downtrend: EMA 21 < EMA 50
        elif ema21[i] < ema50[i]:
            if h[i] >= ema21[i] and c[i] < ema21[i] and c[i] < o[i]:
                sig[i] = -1
                stop_dist = max(1.5 * atr[i] / 0.01, 250.0)
                sl[i] = stop_dist
                tp[i] = stop_dist * 1.5
                
    return sig, sl, tp

# Strategy 2 on M5: London/NY Momentum Expansion (Donchian 12-bar breakout on M5 = 1 hour high/low)
def run_m5_donchian_breakout(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    
    roll_h = pd.Series(h).shift(1).rolling(12).max().values
    roll_l = pd.Series(l).shift(1).rolling(12).min().values
    
    for i in range(13, n):
        # 11:00 to 19:00
        if hour[i] < 11 or hour[i] >= 19:
            continue
        if spread[i] > 25.0:
            continue
            
        if c[i] > roll_h[i] and c[i] > o[i]:
            sig[i] = 1
            stop_dist = max(1.5 * atr[i] / 0.01, 250.0)
            sl[i] = stop_dist
            tp[i] = stop_dist * 1.5
        elif c[i] < roll_l[i] and c[i] < o[i]:
            sig[i] = -1
            stop_dist = max(1.5 * atr[i] / 0.01, 250.0)
            sl[i] = stop_dist
            tp[i] = stop_dist * 1.5
            
    return sig, sl, tp

def main():
    print("Preparing M5 dataset...")
    df = prepare_m5_data()
    print(f"Total M5 bars: {len(df)} from {df['time'].min()} to {df['time'].max()}")
    
    split_date = pd.Timestamp("2026-09-18 00:00:00")
    df_dev = df[df["time"] < split_date].copy().reset_index(drop=True)
    df_val = df[df["time"] >= split_date].copy().reset_index(drop=True)
    
    print(f"Development Set: {len(df_dev)} M5 bars ({df_dev['time'].min()} -> {df_dev['time'].max()})")
    print(f"Validation Set:  {len(df_val)} M5 bars ({df_val['time'].min()} -> {df_val['time'].max()})\n")
    
    strategies = [
        ("M5 Candidate 1: Session Trend Pullback (1.5R)", run_m5_trend_pullback, 24),
        ("M5 Candidate 2: Session Donchian Breakout (1.5R)", run_m5_donchian_breakout, 24)
    ]
    
    for name, func, max_hold in strategies:
        # Dev evaluation
        sig_d, sl_d, tp_d = func(df_dev)
        trades_d = simulate_m5_strategy(df_dev, sig_d, sl_d, tp_d, max_hold_bars=max_hold)
        m_d = compute_metrics(trades_d)
        
        # Val evaluation
        sig_v, sl_v, tp_v = func(df_val)
        trades_v = simulate_m5_strategy(df_val, sig_v, sl_v, tp_v, max_hold_bars=max_hold)
        m_v = compute_metrics(trades_v)
        
        print(f"=== {name} ===")
        print(f"  DEV: Trades={m_d['trades']}, Net=${m_d['net_usd']}, PF={m_d['pf']}, WR={m_d['winrate']}%, AvgWin=${m_d['avg_win']}, AvgLoss=${m_d['avg_loss']}, MaxDD=${m_d['max_dd_usd']}")
        print(f"  VAL: Trades={m_v['trades']}, Net=${m_v['net_usd']}, PF={m_v['pf']}, WR={m_v['winrate']}%, AvgWin=${m_v['avg_win']}, AvgLoss=${m_v['avg_loss']}, MaxDD=${m_v['max_dd_usd']}")
        print()

if __name__ == "__main__":
    main()
