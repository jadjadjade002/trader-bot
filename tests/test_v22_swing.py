"""Unit tests for QuantumTitan V22 Multi-Timeframe Swing EA specifications and logic."""

import re
import unittest
from pathlib import Path


class TestV22Swing(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.source_file = self.root / "QuantumTitan_v22_Swing.mq5"
        self.ex5_file = self.root / "QuantumTitan_v22_Swing.ex5"
        self.compile_log = self.root / "compile_v22.log"
        self.assertTrue(self.source_file.exists(), f"Source file missing: {self.source_file}")
        self.source_code = self.source_file.read_text(encoding="utf-8", errors="replace")

    def test_ex5_binary_exists(self):
        self.assertTrue(self.ex5_file.exists(), f"EX5 binary missing: {self.ex5_file}")
        self.assertGreater(self.ex5_file.stat().st_size, 50000, "EX5 binary size is too small")

    def test_compilation_clean(self):
        if self.compile_log.exists():
            try:
                log_content = self.compile_log.read_text(encoding="utf-16", errors="replace")
            except Exception:
                log_content = self.compile_log.read_text(encoding="utf-8", errors="replace")
            self.assertIn("0 errors, 0 warnings", log_content)

    def test_security_and_account_isolation(self):
        # Must protect live baseline 112334471 from ever being touched
        self.assertNotIn("112334471", self.source_code, "Protected account 112334471 found in source code!")
        
        # Must target demo account 112468807
        self.assertIn("112468807", self.source_code)
        self.assertIn("InpDemoOnly", self.source_code)
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", self.source_code)

    def test_lot_size_scaling(self):
        # Initial lot 0.01, scaling to 0.02 when equity >= 120.0
        base_match = re.search(r"InpBaseLotSize\s*=\s*([\d\.]+);", self.source_code)
        scaled_match = re.search(r"InpScaledLotSize\s*=\s*([\d\.]+);", self.source_code)
        threshold_match = re.search(r"InpEquityScaleThreshold\s*=\s*([\d\.]+);", self.source_code)
        self.assertIsNotNone(base_match)
        self.assertIsNotNone(scaled_match)
        self.assertIsNotNone(threshold_match)
        self.assertEqual(float(base_match.group(1)), 0.01)
        self.assertEqual(float(scaled_match.group(1)), 0.02)
        self.assertEqual(float(threshold_match.group(1)), 120.0)
        self.assertIn("ComputeCurrentLotSize", self.source_code)

    def test_m5_timeframe_floor_enforcement(self):
        # Must strictly enforce M5 as minimum timeframe
        self.assertIn("_Period < PERIOD_M5", self.source_code)
        self.assertIn("locked to M5 and higher", self.source_code)

    def test_order_and_spread_journaling(self):
        # Must record all orders and spread points to CSV
        self.assertIn("v22_swing_orders.csv", self.source_code)
        self.assertIn("LogOrderJournal", self.source_code)
        self.assertIn("SpreadPoints", self.source_code)

    def test_high_conviction_threshold(self):
        # Minimum confidence score must be >= 80 for swing accuracy
        score_match = re.search(r"InpMinConfidenceScore\s*=\s*(\d+);", self.source_code)
        self.assertIsNotNone(score_match, "InpMinConfidenceScore parameter not found")
        min_score = int(score_match.group(1))
        self.assertGreaterEqual(min_score, 80, f"Expected conviction threshold >= 80, got {min_score}")

    def test_swing_risk_parameters(self):
        # Risk:Reward must be >= 2.0
        rr_match = re.search(r"InpRewardRiskRatio\s*=\s*([\d\.]+);", self.source_code)
        self.assertIsNotNone(rr_match, "InpRewardRiskRatio parameter not found")
        rr = float(rr_match.group(1))
        self.assertGreaterEqual(rr, 2.0, f"Expected R:R >= 2.0, got {rr}")

        # ATR stop multiplier must be >= 1.5
        atr_mult_match = re.search(r"InpAtrStopMultiplier\s*=\s*([\d\.]+);", self.source_code)
        self.assertIsNotNone(atr_mult_match, "InpAtrStopMultiplier parameter not found")
        atr_mult = float(atr_mult_match.group(1))
        self.assertGreaterEqual(atr_mult, 1.5, f"Expected ATR multiplier >= 1.5, got {atr_mult}")

        # Breakeven & Trailing Stop enabled
        self.assertIn("InpEnableBreakeven", self.source_code)
        self.assertIn("InpEnableChandelier", self.source_code)

    def test_multi_timeframe_hierarchy_logic(self):
        # Must have dynamic hierarchy resolution for M5, M15, M30, H1, H4, D1
        self.assertIn("ResolveTimeframeHierarchy", self.source_code)
        self.assertIn("PERIOD_M5", self.source_code)
        self.assertIn("PERIOD_M15", self.source_code)
        self.assertIn("PERIOD_M30", self.source_code)
        self.assertIn("PERIOD_H1", self.source_code)
        self.assertIn("PERIOD_H4", self.source_code)
        self.assertIn("PERIOD_D1", self.source_code)

    def test_risk_guardian_tripwires(self):
        # Circuit breakers: daily drawdown halt & Friday weekend lockout
        self.assertIn("InpMaxDailyDrawdownPct", self.source_code)
        self.assertIn("InpFridayLockout", self.source_code)
        self.assertIn("IsDailyLossBreakerTripped", self.source_code)
        self.assertIn("IsFridayLockout", self.source_code)

    def test_audit_logging(self):
        # Must implement OnTradeTransaction with explicit PnL logging
        self.assertIn("OnTradeTransaction", self.source_code)
        self.assertIn("DEAL_ENTRY_OUT", self.source_code)
        self.assertIn("Net PnL", self.source_code)


if __name__ == "__main__":
    unittest.main()
