import re
import unittest
from pathlib import Path


class TestV1657SafetyHotfix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).parents[1] / "QuantumTitan_v16_57_SafetyHotfix.mq5").read_text(
            encoding="utf-8", errors="replace"
        )

    def test_dedicated_version_and_magic(self):
        self.assertIn('#property version   "16.57"', self.source)
        self.assertRegex(self.source, r"InpMagicNumber\s*=\s*991657")

    def test_risk_guardian_is_enabled(self):
        self.assertRegex(self.source, r"InpEnableRiskGuardian\s*=\s*true")
        self.assertRegex(self.source, r"InpMaxDailyLossCash\s*=\s*3\.0")

    def test_persistent_daily_limits_use_broker_history(self):
        self.assertIn("GetTodaySafetyStats", self.source)
        self.assertIn("HistorySelect(todayStart, TimeCurrent())", self.source)
        self.assertIn("IsPersistentDailySafetyHalt()", self.source)
        self.assertRegex(self.source, r"InpMaxTradesPerDay\s*=\s*4")
        self.assertRegex(self.source, r"InpMaxLosingTradesDay\s*=\s*2")
        safety_stats = self.source.split("bool GetTodaySafetyStats", 1)[1].split(
            "bool IsPersistentDailySafetyHalt", 1
        )[0]
        self.assertNotIn("DEAL_MAGIC", safety_stats)

    def test_stop_and_spread_are_bounded(self):
        self.assertRegex(self.source, r"InpMaxStopLossPoints\s*=\s*150\.0")
        self.assertIn("MathMin(InpMaxStopLossPoints, InpAtrSlMult * currentAtrPts)", self.source)
        self.assertRegex(self.source, r"InpMaxSpreadPoints\s*=\s*45\.0")

    def test_retest_requires_strict_directional_evidence(self):
        self.assertRegex(self.source, r"InpRequireFvgAndWick\s*=\s*true")
        self.assertIn("rejectionWick && hasBullFvg", self.source)
        self.assertIn("rejectionWick && hasBearFvg", self.source)
        self.assertIn("sqz.momentum > 0.0", self.source)
        self.assertIn("sqz.momentum < 0.0", self.source)
        self.assertIn("completedBar.close > completedBar.open", self.source)
        self.assertIn("completedBar.close < completedBar.open", self.source)

    def test_compile_log_is_clean(self):
        log = Path(__file__).parents[1] / "v16_57_compile.log"
        text = log.read_text(encoding="utf-16", errors="replace")
        self.assertIn("0 errors, 0 warnings", text)


if __name__ == "__main__":
    unittest.main()
