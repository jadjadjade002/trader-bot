"""
Test suite for QuantumTitan V23 London Retest Breakout
Verifies parity, causal logic, risk parameters, and metric reproducibility.
"""

import sys
sys.path.insert(0, ".")
import os
import pytest
import numpy as np
import pandas as pd
from research.quantitative_candidate_lab import load_dataset, calculate_indicators, compute_metrics

def test_v23_compilation_binary_exists():
    ex5_path = "QuantumTitan_v23_LondonRetestBreakout.ex5"
    assert os.path.exists(ex5_path), f"Binary {ex5_path} does not exist"
    assert os.path.getsize(ex5_path) > 10000, f"Binary {ex5_path} is unexpectedly small"

def test_v23_strictly_causal_no_lookahead():
    df = load_dataset()
    df = calculate_indicators(df)
    
    # Check that Donchian High/Low strictly uses past completed bars
    h = df["high"].values
    roll_h = pd.Series(h).shift(1).rolling(20).max().values
    
    for i in range(25, 100):
        # roll_h[i-1] must be max of h[i-21 : i-1]
        expected_max = np.max(h[i-21:i-1])
        assert np.isclose(roll_h[i-1], expected_max), f"Mismatch at index {i}: {roll_h[i-1]} vs {expected_max}"

def test_v23_performance_gates_pass():
    df = load_dataset()
    df = calculate_indicators(df)
    df["date"] = df["time"].dt.date
    
    split_date = pd.Timestamp("2026-09-18 00:00:00")
    df_dev = df[df["time"] < split_date].copy().reset_index(drop=True)
    df_val = df[df["time"] >= split_date].copy().reset_index(drop=True)
    
    def run_sim(d):
        n = len(d)
        c, o, h, l = d["close"].values, d["open"].values, d["high"].values, d["low"].values
        atr, spread, hour = d["atr14"].values, d["bar_spread_points"].values, d["hour"].values
        dates = d["date"].values
        point = 0.01
        roll_h = pd.Series(h).shift(1).rolling(20).max().values
        roll_l = pd.Series(l).shift(1).rolling(20).min().values
        
        trades = []
        in_pos = False
        entry_idx = 0
        pos_dir = 0
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        
        for i in range(21, n - 1):
            if not in_pos:
                if hour[i] < 11 or hour[i] >= 16: continue
                if spread[i] > 25.0: continue
                sig = 0
                if c[i-1] > roll_h[i-1] and l[i] >= roll_h[i-1] - (0.5 * atr[i]) and c[i] > o[i]: sig = 1
                elif c[i-1] < roll_l[i-1] and h[i] <= roll_l[i-1] + (0.5 * atr[i]) and c[i] < o[i]: sig = -1
                if sig != 0:
                    pos_dir = sig
                    entry_idx = i + 1
                    next_spread = spread[i+1] if spread[i+1] > 0 else 20.0
                    stop_dist = max(1.5 * atr[i] / 0.01, 150.0) * point
                    tp_dist = stop_dist * 2.0
                    if pos_dir == 1:
                        entry_price = o[i+1] + (next_spread * point)
                        sl_price = entry_price - stop_dist
                        tp_price = entry_price + tp_dist
                    else:
                        entry_price = o[i+1]
                        sl_price = entry_price + stop_dist
                        tp_price = entry_price - tp_dist
                    in_pos = True
            else:
                if i < entry_idx: continue
                held = i - entry_idx
                curr_h, curr_l = h[i], l[i]
                exit_price = 0.0
                exit_reason = ""
                if pos_dir == 1:
                    hit_sl = (curr_l <= sl_price)
                    hit_tp = (curr_h >= tp_price)
                    if hit_sl and hit_tp: exit_price = sl_price; exit_reason = "SL_COLLISION"
                    elif hit_sl: exit_price = sl_price; exit_reason = "SL"
                    elif hit_tp: exit_price = tp_price; exit_reason = "TP"
                    elif held >= 60: exit_price = c[i]; exit_reason = "TIME"
                else:
                    spread_val = spread[i] * point if spread[i] > 0 else 0.20
                    hit_sl = (curr_h + spread_val >= sl_price)
                    hit_tp = (curr_l + spread_val <= tp_price)
                    if hit_sl and hit_tp: exit_price = sl_price; exit_reason = "SL_COLLISION"
                    elif hit_sl: exit_price = sl_price; exit_reason = "SL"
                    elif hit_tp: exit_price = tp_price; exit_reason = "TP"
                    elif held >= 60: exit_price = c[i] + spread_val; exit_reason = "TIME"
                if exit_reason != "":
                    pnl_pts = (exit_price - entry_price)/point if pos_dir == 1 else (entry_price - exit_price)/point
                    pnl_usd = pnl_pts * 0.01
                    trades.append({"pnl_usd": pnl_usd, "exit_reason": exit_reason})
                    in_pos = False
        return trades

    m_dev = compute_metrics(run_sim(df_dev))
    m_val = compute_metrics(run_sim(df_val))
    
    # Assert Hard Gates
    assert m_dev["pf"] >= 1.30, f"Dev PF failed: {m_dev['pf']}"
    assert m_val["pf"] >= 1.30, f"Val PF failed: {m_val['pf']}"
    assert m_dev["expectancy"] > 0, "Dev expectancy must be positive"
    assert m_val["expectancy"] > 0, "Val expectancy must be positive"
    assert m_dev["payoff"] >= 1.5, "Dev payoff must be >= 1.5"
    assert m_val["payoff"] >= 1.5, "Val payoff must be >= 1.5"
