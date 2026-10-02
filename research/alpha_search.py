"""
Comprehensive Quantitative Alpha Search
Systematically evaluates:
1. Calibrated Asian Liquidity Sweep (Judas Reversal)
2. London/NY Momentum Continuation (Clean Bar Breakout)
3. Intraday VWAP Standard Deviation Reversion
4. Micro-trend Pullback with Strict Session and Volatility Windows
Evaluates with exact metric gates across Dev and Validation.
"""

import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from research.quantitative_candidate_lab import load_dataset, compute_metrics, calculate_indicators, simulate_strategy

def run_calibrated_asia_sweep(df: pd.DataFrame, sweep_min_pts: float = 100.0, sweep_max_pts: float = 1500.0, rr: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    spread = df["bar_spread_points"].values
    mod = df["minute_of_day"].values
    dates = df["date"].values
    point = 0.01
    
    for d in np.unique(dates):
        day_indices = np.where(dates == d)[0]
        if len(day_indices) == 0:
            continue
            
        asia_idx = day_indices[(mod[day_indices] >= 180) & (mod[day_indices] < 600)]
        if len(asia_idx) < 60:
            continue
            
        asia_h = np.max(h[asia_idx])
        asia_l = np.min(l[asia_idx])
        
        # London window: 10:30 to 14:00 (630 to 840)
        london_idx = day_indices[(mod[day_indices] >= 630) & (mod[day_indices] < 840)]
        traded = False
        
        for idx in london_idx:
            if traded:
                break
            if spread[idx] > 25.0:
                continue
                
            # Sweep below Asia Low
            if l[idx-1] < asia_l and c[idx] > asia_l and c[idx] > o[idx]:
                sweep_low = min(l[idx-1], l[idx])
                dist = (asia_l - sweep_low) / point
                if sweep_min_pts <= dist <= sweep_max_pts:
                    sig[idx] = 1
                    stop_dist = max((c[idx] - sweep_low) / point + 50.0, 200.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * rr
                    traded = True
            # Sweep above Asia High
            elif h[idx-1] > asia_h and c[idx] < asia_h and c[idx] < o[idx]:
                sweep_high = max(h[idx-1], h[idx])
                dist = (sweep_high - asia_h) / point
                if sweep_min_pts <= dist <= sweep_max_pts:
                    sig[idx] = -1
                    stop_dist = max((sweep_high - c[idx]) / point + 50.0, 200.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * rr
                    traded = True
                    
    return sig, sl, tp

def run_ny_open_momentum(df: pd.DataFrame, rr: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    NY Open Momentum: 15:30 to 17:30 broker time (US Economic data & Cash Open)
    High tick volume impulse bar > 1.5 ATR breaking 15-bar high/low.
    """
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
    mod = df["minute_of_day"].values
    dates = df["date"].values
    point = 0.01
    
    roll_h = pd.Series(h).shift(1).rolling(15).max().values
    roll_l = pd.Series(l).shift(1).rolling(15).min().values
    
    for d in np.unique(dates):
        day_indices = np.where(dates == d)[0]
        ny_idx = day_indices[(mod[day_indices] >= 930) & (mod[day_indices] < 1050)] # 15:30 to 17:30
        traded = False
        
        for idx in ny_idx:
            if traded:
                break
            if spread[idx] > 25.0:
                continue
            bar_body = abs(c[idx] - o[idx])
            
            # Strong impulse breakout
            if c[idx] > roll_h[idx] and bar_body >= 1.2 * atr[idx] and c[idx] > o[idx]:
                sig[idx] = 1
                stop_dist = max(bar_body / point, 200.0)
                sl[idx] = stop_dist
                tp[idx] = stop_dist * rr
                traded = True
            elif c[idx] < roll_l[idx] and bar_body >= 1.2 * atr[idx] and c[idx] < o[idx]:
                sig[idx] = -1
                stop_dist = max(bar_body / point, 200.0)
                sl[idx] = stop_dist
                tp[idx] = stop_dist * rr
                traded = True
                
    return sig, sl, tp

def run_vwap_stretch_reversion(df: pd.DataFrame, stretch_mult: float = 2.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Mean reversion when price stretches far from session rolling VWAP/EMA in low-efficiency conditions.
    """
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    ema50 = df["ema50"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    ker = df["ker20"].values
    point = 0.01
    
    for i in range(1, n):
        # 12:00 to 21:00
        if hour[i] < 12 or hour[i] >= 21:
            continue
        if spread[i] > 20.0:
            continue
        if ker[i] > 0.20: # Must be ranging / low momentum
            continue
            
        dev = (c[i] - ema50[i]) / (atr[i] if atr[i] > 0 else 1.0)
        
        if dev < -stretch_mult and c[i] > o[i] and (c[i] - l[i]) > (h[i] - c[i]):
            sig[i] = 1
            dist = abs(c[i] - ema50[i]) / point
            sl[i] = max(dist * 0.8, 150.0)
            tp[i] = max(dist, 180.0)
        elif dev > stretch_mult and c[i] < o[i] and (h[i] - c[i]) > (c[i] - l[i]):
            sig[i] = -1
            dist = abs(c[i] - ema50[i]) / point
            sl[i] = max(dist * 0.8, 150.0)
            tp[i] = max(dist, 180.0)
            
    return sig, sl, tp

def run_micro_channel_scalp(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    1-minute Micro Channel Scalping:
    EMA 9 / EMA 21 alignment.
    Enter on 2 consecutive pullback bars followed by 1 continuation bar.
    Strict 1.5R target, 30-bar time stop.
    """
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    ema6 = df["ema6"].values
    ema20 = df["ema20"].values
    ema50 = df["ema50"].values
    atr = df["atr14"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    ker = df["ker20"].values
    point = 0.01
    
    for i in range(3, n):
        # London / NY prime: 11:00 to 19:00
        if hour[i] < 11 or hour[i] >= 19:
            continue
        if spread[i] > 22.0:
            continue
        if ker[i] < 0.28: # Must have clear directional momentum
            continue
            
        # Uptrend
        if ema6[i] > ema20[i] > ema50[i]:
            # Pullback on i-2 and i-1, resumption on i
            if c[i-2] < o[i-2] and c[i-1] < o[i-1] and c[i] > o[i] and c[i] > h[i-1]:
                sig[i] = 1
                stop_dist = max((c[i] - min(l[i-1], l[i-2])) / point + 20.0, 150.0)
                sl[i] = stop_dist
                tp[i] = stop_dist * 1.5
        # Downtrend
        elif ema6[i] < ema20[i] < ema50[i]:
            if c[i-2] > o[i-2] and c[i-1] > o[i-1] and c[i] < o[i] and c[i] < l[i-1]:
                sig[i] = -1
                stop_dist = max((max(h[i-1], h[i-2]) - c[i]) / point + 20.0, 150.0)
                sl[i] = stop_dist
                tp[i] = stop_dist * 1.5
                
    return sig, sl, tp

def main():
    df = load_dataset()
    df = calculate_indicators(df)
    df["date"] = df["time"].dt.date
    
    split_date = pd.Timestamp("2026-09-18 00:00:00")
    df_dev = df[df["time"] < split_date].copy().reset_index(drop=True)
    df_val = df[df["time"] >= split_date].copy().reset_index(drop=True)
    
    models = [
        ("Model A: Calibrated Asia Sweep (2.0R)", lambda d: run_calibrated_asia_sweep(d, 100.0, 2000.0, 2.0), 90),
        ("Model B: NY Open Impulse Momentum (1.5R)", lambda d: run_ny_open_momentum(d, 1.5), 60),
        ("Model C: VWAP Deviation Reversion (1.2R)", lambda d: run_vwap_stretch_reversion(d, 2.5), 45),
        ("Model D: Micro Channel Momentum Resumption (1.5R)", run_micro_channel_scalp, 30),
    ]
    
    print("=" * 120)
    print(f"{'MODEL':<45} | {'DEV T':<6} {'DEV NET':<9} {'DEV PF':<7} {'DEV WR%':<8} | {'VAL T':<6} {'VAL NET':<9} {'VAL PF':<7} {'VAL WR%':<8}")
    print("=" * 120)
    
    for name, func, max_hold in models:
        sig_d, sl_d, tp_d = func(df_dev)
        t_d = simulate_strategy(df_dev, sig_d, sl_d, tp_d, max_hold_bars=max_hold)
        m_d = compute_metrics(t_d)
        
        sig_v, sl_v, tp_v = func(df_val)
        t_v = simulate_strategy(df_val, sig_v, sl_v, tp_v, max_hold_bars=max_hold)
        m_v = compute_metrics(t_v)
        
        print(f"{name:<45} | {m_d['trades']:<6} ${m_d['net_usd']:<8.2f} {m_d['pf']:<7.2f} {m_d['winrate']:<7.1f}% | {m_v['trades']:<6} ${m_v['net_usd']:<8.2f} {m_v['pf']:<7.2f} {m_v['winrate']:<7.1f}%")
        
    print("=" * 120)

if __name__ == "__main__":
    main()
