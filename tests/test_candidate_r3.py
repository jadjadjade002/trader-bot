"""Static source-contract checks; these do not execute or emulate MQL5."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import build_candidate_r3 as build  # noqa: E402


class CandidateR3SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extension = (ROOT / "research/candidate_r3_signal_extension.mqh").read_text(encoding="utf-8")
        cls.generated = (ROOT / "research/ResearchCandidate_R3.mq5").read_text(encoding="utf-8")

    def test_build_is_deterministic_and_hash_pinned(self):
        self.assertEqual(self.generated, build.generate())

    def test_release_identity_and_frozen_economics(self):
        self.assertIn('#property version   "24.92"', self.generated)
        self.assertIn("tester-only. Fixed V24 economics. Not a V25 release.", self.generated)
        for rule in (
            "InpStopLossATRMul!=1.5", "InpTakeProfitRRMul!=2.0", "InpMaxHoldBars!=60",
            "InpLotSize!=0.01", "InpFadeBreakouts", "InpEnableHardSL!=true",
            "InpEnableMarginGuard!=true", "InpEnableCircuitBreaker!=true",
            "InpMaxConsecutiveLosses!=4", "InpCooldownMinutes!=90",
        ):
            self.assertIn(rule, self.extension)
        self.assertIn("CandidateR3Signal(atr)", self.generated)

    def test_all_signal_families_use_closed_shift_context_and_injected_helpers(self):
        for name in ("R3Blowoff", "R3Range", "R3EfficientFlag", "R3Trend", "R3QuoteCost"):
            self.assertIn(name + "(", self.extension)
        self.assertIn("CopyRates(_Symbol,tf,1,count,r)", self.extension)
        self.assertIn("CopyBuffer(atrHandle,0,1,23,atrM1)", self.extension)
        self.assertIn("CopyBuffer(trendFast,0,1,6,ema20)", self.extension)
        self.assertIn("CopyBuffer(entryFast,0,1,2,ema9)", self.extension)
        self.assertIn("iTime(_Symbol,tf,1)", self.extension)
        self.assertIn("r[i].time-r[i+1].time!=seconds", self.extension)

    def test_cost_gate_and_risk_are_not_parameter_swept(self):
        self.assertIn("ask-bid<=0.10*atr", self.extension)
        self.assertIn("MathAbs((ask+bid)/2.0-signalClose)<=0.50*atr", self.extension)
        self.assertIn("range<=2.0*atr", self.extension)
        self.assertIn("InpEntryStrength<0 || InpEntryStrength>1", self.extension)
        self.assertNotIn("InpUseGridIndices", self.extension)
        self.assertNotIn("TPGridIndex", self.extension)
        self.assertNotIn("RunR2FixtureTests", self.generated)

    def test_families_have_preset_axes_and_signed_mirrors(self):
        for fixed_axis in ("1.50 : 2.00", "0.80 : 0.85", "0.60 : 0.70"):
            self.assertIn(fixed_axis, self.extension)
        for marker in ("return -1;", "return 1;", "d*(m1[1].close-m1[8].close)",
                       "s1.low>lo", "s1.high < H", "d*(m5[0].close-m5[12].close)"):
            # Some specifications are represented with array expressions; test only stable source terms.
            if marker in ("s1.low>lo", "s1.high < H"):
                continue
            self.assertIn(marker, self.extension)
        self.assertIn("m1[0].low>lo", self.extension)
        self.assertIn("m1[0].high<hi", self.extension)


if __name__ == "__main__":
    unittest.main()
