"""Static regression tests for the isolated V16.56 ProfitRunner candidate."""

import re
import unittest
from pathlib import Path


class TestV1656ProfitRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.candidate = (cls.root / "QuantumTitan_v16_56_ProfitRunner.mq5").read_text(
            encoding="utf-8", errors="strict"
        )
        cls.baseline = (cls.root / "QuantumTitan_v16_Velocity.mq5").read_text(
            encoding="utf-8", errors="strict"
        )

    @staticmethod
    def input_number(source: str, name: str) -> float:
        match = re.search(rf"\b{name}\s*=\s*([0-9.]+)\s*;", source)
        if not match:
            raise AssertionError(f"Missing numeric input: {name}")
        return float(match.group(1))

    @staticmethod
    def entry_block(source: str) -> str:
        start = source.index("// BUY SETUP 1:")
        end = source.index("// Execute Scalp Order", start)
        return source[start:end]

    def test_identity_and_magic_are_isolated(self):
        self.assertIn('#property version   "16.56"', self.candidate)
        self.assertEqual(self.input_number(self.candidate, "InpMagicNumber"), 991656)
        self.assertNotIn("112334471", self.candidate)
        self.assertNotIn("112468807", self.candidate)

    def test_entry_logic_is_byte_identical_to_live_baseline(self):
        self.assertEqual(self.entry_block(self.candidate), self.entry_block(self.baseline))

    def test_first_lock_matches_baseline_and_later_stages_advance(self):
        self.assertIn("InpEnableStagedProfitLock = false", self.candidate)
        for name in ("InpAtrBeTriggerMult", "InpAtrBeLockMult"):
            self.assertEqual(
                self.input_number(self.candidate, name),
                self.input_number(self.baseline, name),
            )
        self.assertGreater(
            self.input_number(self.candidate, "InpStage2TriggerAtr"),
            self.input_number(self.candidate, "InpAtrBeTriggerMult"),
        )
        self.assertGreater(
            self.input_number(self.candidate, "InpStage3TriggerAtr"),
            self.input_number(self.candidate, "InpStage2TriggerAtr"),
        )
        self.assertGreater(
            self.input_number(self.candidate, "InpStage3LockAtr"),
            self.input_number(self.candidate, "InpStage2LockAtr"),
        )

    def test_initial_sl_and_tp_match_baseline(self):
        for name in ("InpAtrTpMult", "InpAtrSlMult"):
            self.assertEqual(
                self.input_number(self.candidate, name),
                self.input_number(self.baseline, name),
            )

    def test_dynamic_policy_uses_configurable_bounds(self):
        self.assertIn("MathMax(InpMinBeTriggerPts, MathMin(InpMaxBeTriggerPts", self.candidate)
        self.assertIn("MathMax(InpMinBeLockPts, MathMin(InpMaxBeLockPts", self.candidate)
        self.assertIn("STAGE %d LOCK", self.candidate)
        self.assertIn("INIT_PARAMETERS_INCORRECT", self.candidate)

    def test_demo_and_target_account_guards_remain(self):
        self.assertIn("InpDemoOnly", self.candidate)
        self.assertIn("ACCOUNT_TRADE_MODE_REAL", self.candidate)
        self.assertIn("InpTargetAccount", self.candidate)
        self.assertIn("INIT_FAILED", self.candidate)

    def test_daily_rollover_gap_guard_flattens_and_blocks(self):
        self.assertIn("InpDailyRolloverLock    = true", self.candidate)
        self.assertIn("InpRolloverFlatHour     = 22", self.candidate)
        self.assertIn("InpRolloverFlatMinute   = 30", self.candidate)
        self.assertIn("InpRolloverResumeHour   = 1", self.candidate)
        self.assertIn("InpRolloverResumeMinute = 15", self.candidate)
        self.assertIn("g_trade.PositionClose(activeTicket)", self.candidate)
        self.assertGreaterEqual(self.candidate.count("IsDailyRolloverLockout()"), 3)


if __name__ == "__main__":
    unittest.main()
