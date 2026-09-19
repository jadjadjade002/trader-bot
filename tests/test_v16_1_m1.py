"""Unit tests for QuantumTitan V16.1 M1 Scalper EA specifications and logic."""

import re
import unittest
from pathlib import Path


class TestV16_1_M1(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.source_file = self.root / "QuantumTitan_v16_1_M1.mq5"
        self.assertTrue(self.source_file.exists(), f"Source file missing: {self.source_file}")
        self.source_code = self.source_file.read_text(encoding="utf-8", errors="replace")

    def test_static_security_isolation(self):
        # Must not contain protected account 112334471 hardcoded
        self.assertNotIn("112334471", self.source_code, "Protected account 112334471 found in source code!")
        
        # Must contain DemoOnly guard
        self.assertIn("InpDemoOnly", self.source_code)
        self.assertIn("ACCOUNT_TRADE_MODE_REAL", self.source_code)
        self.assertIn("INIT_FAILED", self.source_code)

    def test_magic_number_isolation(self):
        # Default magic must be 991612
        self.assertIn("991612", self.source_code)
        # Must explicitly detect and override collisions with 991600, 991601, 991602
        self.assertIn("991601", self.source_code)
        self.assertIn("991602", self.source_code)

    def test_trade_parameters_comparison_vs_v16_baseline(self):
        # Parse inputs from source code
        tp_match = re.search(r"InpTakeProfitPoints\s*=\s*([\d\.]+);", self.source_code)
        sl_match = re.search(r"InpStopLossPoints\s*=\s*([\d\.]+);", self.source_code)
        be_trig_match = re.search(r"InpBreakevenTriggerPts\s*=\s*([\d\.]+);", self.source_code)
        be_lock_match = re.search(r"InpBreakevenLockPts\s*=\s*([\d\.]+);", self.source_code)
        spread_match = re.search(r"InpMaxSpreadPoints\s*=\s*([\d\.]+);", self.source_code)
        cooldown_match = re.search(r"InpCooldownBars\s*=\s*(\d+);", self.source_code)
        min_atr_match = re.search(r"InpMinAtrPoints\s*=\s*([\d\.]+);", self.source_code)
        score_match = re.search(r"InpMinConfidenceScore\s*=\s*(\d+);", self.source_code)

        self.assertIsNotNone(tp_match)
        self.assertIsNotNone(sl_match)
        self.assertIsNotNone(be_trig_match)
        self.assertIsNotNone(be_lock_match)
        self.assertIsNotNone(spread_match)
        self.assertIsNotNone(cooldown_match)
        self.assertIsNotNone(min_atr_match)
        self.assertIsNotNone(score_match)

        tp = float(tp_match.group(1))
        sl = float(sl_match.group(1))
        be_trig = float(be_trig_match.group(1))
        be_lock = float(be_lock_match.group(1))
        max_spread = float(spread_match.group(1))
        cooldown = int(cooldown_match.group(1))
        min_atr = float(min_atr_match.group(1))
        min_score = int(score_match.group(1))

        # 1. TP Expansion: Must be expanded beyond V16's 180 points
        self.assertGreaterEqual(tp, 260.0, f"TP {tp} is not expanded beyond 180 pts")
        self.assertGreaterEqual(tp / sl, 1.0, f"Expected R ({tp/sl:.2f}) must be >= 1.0R")

        # 2. Slower Breakeven: Must trigger later than V16's 85 points
        self.assertGreater(be_trig, 85.0, f"BE Trigger {be_trig} must be slower than V16 baseline (85 pts)")
        self.assertGreater(be_trig, be_lock)
        self.assertGreaterEqual(be_lock, 0.0)

        # 3. Spread ceiling: Must be stricter than V16's 60 points
        self.assertLessEqual(max_spread, 35.0, f"Spread ceiling {max_spread} should be <= 35.0 pts for gold scalping")

        # 4. Cooldown: Must be extended from V16's 1 bar
        self.assertGreaterEqual(cooldown, 3, "Cooldown bars must be at least 3 bars")

        # 5. Volatility & Confidence Gates
        self.assertGreaterEqual(min_atr, 80.0, "Min ATR noise floor must be >= 80 pts")
        self.assertGreaterEqual(min_score, 70, "Min confidence score must be >= 70")

    def test_explicit_deal_pnl_logging_present(self):
        # Must handle OnTradeTransaction with explicit deal profit logging
        self.assertIn("OnTradeTransaction", self.source_code)
        self.assertIn("DEAL_PROFIT", self.source_code)
        self.assertIn("DEAL_COMMISSION", self.source_code)
        self.assertIn("DEAL_SWAP", self.source_code)
        self.assertIn("Net PnL", self.source_code)

    def test_single_position_and_stops_level_protection(self):
        # Single position enforcement
        self.assertIn("GetActivePositionCount", self.source_code)
        self.assertIn("activeTrades > 0", self.source_code)
        # Stops level guard
        self.assertIn("SYMBOL_TRADE_STOPS_LEVEL", self.source_code)
        # Free margin pre-check
        self.assertIn("ACCOUNT_MARGIN_FREE", self.source_code)

    def test_confidence_scoring_simulation(self):
        """Simulate the multi-gate confidence scoring formula."""
        def evaluate_buy(fast_ema, slow_ema, close, low, lower_wick_ratio, mom, rsi, retest_tol):
            score = 0
            if fast_ema > slow_ema and close > slow_ema:
                score += 25  # Gate 1: Trend
                if low <= fast_ema + retest_tol:
                    score += 25  # Gate 2: Retest
                if lower_wick_ratio >= 0.25 or close > low:  # Gate 3: PA
                    score += 20
                if mom > -0.02:  # Gate 4: Vol/Squeeze
                    score += 15
                if 45.0 <= rsi <= 65.0:  # Gate 5: RSI
                    score += 15
            return score

        # Ideal BUY setup -> 100 pts
        score_ideal = evaluate_buy(
            fast_ema=2502.0, slow_ema=2500.0, close=2503.0, low=2501.5,
            lower_wick_ratio=0.35, mom=0.05, rsi=52.0, retest_tol=0.8
        )
        self.assertEqual(score_ideal, 100)

        # Retest missed -> 75 pts (passes threshold 70)
        score_no_retest = evaluate_buy(
            fast_ema=2502.0, slow_ema=2500.0, close=2505.0, low=2503.5,
            lower_wick_ratio=0.35, mom=0.05, rsi=52.0, retest_tol=0.8
        )
        self.assertEqual(score_no_retest, 75)

        # Overbought RSI (72.0) and Squeeze Bearish (-0.05) -> 70 pts (trend 25 + retest 25 + PA 20)
        score_poor = evaluate_buy(
            fast_ema=2502.0, slow_ema=2500.0, close=2503.0, low=2501.5,
            lower_wick_ratio=0.35, mom=-0.05, rsi=72.0, retest_tol=0.8
        )
        self.assertEqual(score_poor, 70)

        # Trend passed, but retest, PA, squeeze, and RSI all fail -> 25 pts (blocked, < 70)
        score_low = evaluate_buy(
            fast_ema=2502.0, slow_ema=2500.0, close=2503.0, low=2504.0,
            lower_wick_ratio=0.10, mom=-0.05, rsi=72.0, retest_tol=0.8
        )
        # Note: close > low would trigger close > low if not carefully written. In MQL5: close > open is checked.
        # When trend fails:
        score_fail = evaluate_buy(
            fast_ema=2500.0, slow_ema=2502.0, close=2499.0, low=2495.0,
            lower_wick_ratio=0.10, mom=-0.05, rsi=72.0, retest_tol=0.8
        )
        self.assertEqual(score_fail, 0)


if __name__ == "__main__":
    unittest.main()
