"""
Session Liquidity & Structure Lab
Tests structural institutional hypotheses:
1. Asian Range Liquidity Sweep (Judas Swing Reversal)
2. London/NY 15-minute Opening Range Breakout (ORB)
3. M15 Trend Bias + M1 Pullback with 1-trade/session limit
"""

import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from research.quantitative_candidate_lab import load_dataset, compute_metrics, calculate_indicators

def prepare_data_with_sessions() -> pd.DataFrame:
    df = load_dataset()
    df = calculate_indicators(df)
    
    # Add date and time attributes
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["minute"] = df["time"].dt.minute
    df["minute_of_day"] = df["hour"] * 60 + df["minute"]
    
    # Calculate M15 indicators by resampling and merging back
    df_m15 = df.set_index("time").resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna().reset_index()
    
    c15 = df_m15["close"].values
    df_m15["m15_ema20"] = pd.Series(c15).ewm(span=20, adjust=False).mean().values
    df_m15["m15_ema50"] = pd.Series(c15).ewm(span=50, adjust=False).mean().values
    
    # Merge M15 back to M1 using merge_asof
    df = pd.merge_asof(df, df_m15[["time", "m15_ema20", "m15_ema50"]], on="time", direction="backward")
    
    return df

# --- Hypothesis 4: Asian Range Sweep & Reversal ---
# Asia Session: 03:00 to 10:00 broker time
# Sweep Window: 11:00 to 14:00 broker time (London Open)
# Max 1 trade per day
def run_asia_sweep(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    sig = np.zeros(n)
    sl = np.zeros(n)
    tp = np.zeros(n)
    
    c = df["close"].values
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    spread = df["bar_spread_points"].values
    hour = df["hour"].values
    minute = df["minute"].values
    mod = df["minute_of_day"].values
    dates = df["date"].values
    atr = df["atr14"].values
    point = 0.01
    
    unique_dates = np.unique(dates)
    
    for d in unique_dates:
        mask = (dates == d)
        day_indices = np.where(mask)[0]
        if len(day_indices) == 0:
            continue
            
        # Asia session: 03:00 (180 min) to 10:00 (600 min)
        asia_indices = day_indices[(mod[day_indices] >= 180) & (mod[day_indices] < 600)]
        if len(asia_indices) < 60:
            continue
            
        asia_high = np.max(h[asia_indices])
        asia_low = np.min(l[asia_indices])
        asia_range = (asia_high - asia_low) / point
        
        # We only trade if Asia range is healthy (between 300 and 2000 points)
        if asia_range < 300 or asia_range > 2500:
            continue
            
        # London sweep window: 11:00 (660 min) to 14:00 (840 min)
        london_indices = day_indices[(mod[day_indices] >= 660) & (mod[day_indices] < 840)]
        traded_today = False
        
        for idx in london_indices:
            if traded_today:
                break
            if spread[idx] > 25.0:
                continue
                
            # Bullish Sweep: Price penetrated below Asia Low, and current candle closes back above Asia Low
            # with bullish close
            if l[idx-1] < asia_low and c[idx] > asia_low and c[idx] > o[idx]:
                sweep_low = min(l[idx-1], l[idx])
                sweep_dist = (asia_low - sweep_low) / point
                if 20 <= sweep_dist <= 600: # Valid sweep depth
                    sig[idx] = 1
                    stop_dist = max((c[idx] - sweep_low) / point + 50.0, 150.0) # Stop below sweep low
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 2.0 # 2.0R target
                    traded_today = True
                    
            # Bearish Sweep: Price penetrated above Asia High, and current candle closes back below Asia High
            # with bearish close
            elif h[idx-1] > asia_high and c[idx] < asia_high and c[idx] < o[idx]:
                sweep_high = max(h[idx-1], h[idx])
                sweep_dist = (sweep_high - asia_high) / point
                if 20 <= sweep_dist <= 600:
                    sig[idx] = -1
                    stop_dist = max((sweep_high - c[idx]) / point + 50.0, 150.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 2.0 # 2.0R target
                    traded_today = True
                    
    return sig, sl, tp

# --- Hypothesis 5: 15-Minute Opening Range Breakout (London & NY) ---
# London OR: 11:00 to 11:15 (trade 11:15 to 13:30)
# NY OR: 16:00 to 16:15 (trade 16:15 to 18:30)
# Max 1 trade per session
def run_orb_breakout(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    atr = df["atr14"].values
    point = 0.01
    
    sessions = [
        ("London", 660, 675, 675, 810), # 11:00-11:15 OR, trade until 13:30
        ("NY", 960, 975, 975, 1110)      # 16:00-16:15 OR, trade until 18:30
    ]
    
    unique_dates = np.unique(dates)
    
    for d in unique_dates:
        day_indices = np.where(dates == d)[0]
        if len(day_indices) == 0:
            continue
            
        for sess_name, or_start, or_end, trade_start, trade_end in sessions:
            or_idx = day_indices[(mod[day_indices] >= or_start) & (mod[day_indices] < or_end)]
            if len(or_idx) < 10:
                continue
                
            or_high = np.max(h[or_idx])
            or_low = np.min(l[or_idx])
            or_range = (or_high - or_low) / point
            
            # OR range must be reasonable (not already blown out)
            if or_range < 150 or or_range > 1500:
                continue
                
            trade_idx = day_indices[(mod[day_indices] >= trade_start) & (mod[day_indices] < trade_end)]
            traded = False
            
            for idx in trade_idx:
                if traded:
                    break
                if spread[idx] > 25.0:
                    continue
                    
                # Bullish Breakout
                if c[idx] > or_high and c[idx] > o[idx]:
                    sig[idx] = 1
                    stop_dist = max(or_range * 0.75, 150.0) # SL at 75% of OR range
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 1.5 # 1.5R target
                    traded = True
                # Bearish Breakout
                elif c[idx] < or_low and c[idx] < o[idx]:
                    sig[idx] = -1
                    stop_dist = max(or_range * 0.75, 150.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 1.5
                    traded = True
                    
    return sig, sl, tp

# --- Hypothesis 6: M15 Trend Bias + M1 Low-Vol Compression Pullback ---
# Filter: M15 EMA 20 > EMA 50
# M1 session: 11:00 to 20:00
# Reversal candle on M1 after pullback to M1 EMA 50
# Max 2 trades per day, circuit breaker on 1 loss per day!
def run_m15_trend_pullback(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    atr = df["atr14"].values
    ema20 = df["ema20"].values
    ema50 = df["ema50"].values
    m15_ema20 = df["m15_ema20"].values
    m15_ema50 = df["m15_ema50"].values
    ker = df["ker20"].values
    point = 0.01
    
    unique_dates = np.unique(dates)
    
    for d in unique_dates:
        day_indices = np.where(dates == d)[0]
        if len(day_indices) == 0:
            continue
            
        trade_count = 0
        for idx in day_indices:
            if trade_count >= 2:
                break
            # Time: 11:00 (660) to 20:00 (1200)
            if mod[idx] < 660 or mod[idx] >= 1200:
                continue
            if spread[idx] > 22.0:
                continue
            if ker[idx] < 0.25:
                continue
                
            # M15 Trend Bullish
            if m15_ema20[idx] > m15_ema50[idx]:
                # M1 Pullback to M1 EMA 50: Low touched or penetrated EMA 50, Close reclaimed above EMA 20
                if l[idx-1] <= ema50[idx-1] and c[idx] > ema20[idx] and c[idx] > o[idx]:
                    sig[idx] = 1
                    stop_dist = max((c[idx] - min(l[idx-1], l[idx])) / point + 30.0, 150.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 2.0 # 2.0R target
                    trade_count += 1
                    
            # M15 Trend Bearish
            elif m15_ema20[idx] < m15_ema50[idx]:
                if h[idx-1] >= ema50[idx-1] and c[idx] < ema20[idx] and c[idx] < o[idx]:
                    sig[idx] = -1
                    stop_dist = max((max(h[idx-1], h[idx]) - c[idx]) / point + 30.0, 150.0)
                    sl[idx] = stop_dist
                    tp[idx] = stop_dist * 2.0
                    trade_count += 1
                    
    return sig, sl, tp

def main():
    print("Preparing dataset with multi-timeframe sessions...")
    df = prepare_data_with_sessions()
    print(f"Total bars: {len(df)}")
    
    split_date = pd.Timestamp("2026-09-18 00:00:00")
    df_dev = df[df["time"] < split_date].copy().reset_index(drop=True)
    df_val = df[df["time"] >= split_date].copy().reset_index(drop=True)
    
    print(f"Dev bars: {len(df_dev)} ({df_dev['time'].min()} to {df_dev['time'].max()})")
    print(f"Val bars: {len(df_val)} ({df_val['time'].min()} to {df_val['time'].max()})\n")
    
    from research.quantitative_candidate_lab import simulate_strategy
    
    models = [
        ("Hypothesis 4: Asian Range Sweep (Judas Reversal)", run_asia_sweep, 120),
        ("Hypothesis 5: 15-Min Opening Range Breakout (ORB)", run_orb_breakout, 90),
        ("Hypothesis 6: M15 Trend + M1 Pullback Reclaim", run_m15_trend_pullback, 60),
    ]
    
    for name, func, max_hold in models:
        sig_d, sl_d, tp_d = func(df_dev)
        t_d = simulate_strategy(df_dev, sig_d, sl_d, tp_d, max_hold_bars=max_hold)
        m_d = compute_metrics(t_d)
        
        sig_v, sl_v, tp_v = func(df_val)
        t_v = simulate_strategy(df_val, sig_v, sl_v, tp_v, max_hold_bars=max_hold)
        m_v = compute_metrics(t_v)
        
        print(f"=== {name} ===")
        print(f"  DEV: Trades={m_d['trades']}, Net=${m_d['net_usd']}, PF={m_d['pf']}, WR={m_d['winrate']}%, AvgWin=${m_d['avg_win']}, AvgLoss=${m_d['avg_loss']}, MaxDD=${m_d['max_dd_usd']}")
        print(f"  VAL: Trades={m_v['trades']}, Net=${m_v['net_usd']}, PF={m_v['pf']}, WR={m_v['winrate']}%, AvgWin=${m_v['avg_win']}, AvgLoss=${m_v['avg_loss']}, MaxDD=${m_v['max_dd_usd']}")
        print()

if __name__ == "__main__":
    main()
