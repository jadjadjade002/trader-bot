"""Static audit guards for the independent R3 source review; no MQL execution."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CandidateR3LunaReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = (ROOT / "research/build_candidate_r3.py").read_text(encoding="utf-8")
        cls.extension = (ROOT / "research/candidate_r3_signal_extension.mqh").read_text(encoding="utf-8")
        cls.fixtures = (ROOT / "research/candidate_r3_native_tests.mqh").read_text(encoding="utf-8")
        cls.runner = (ROOT / "research/run_v25_native.py").read_text(encoding="utf-8")

    def test_builder_is_hash_pinned_and_only_swaps_signal(self):
        for marker in ("EXPECTED =", "BENCH_HASH =", "TUNING_HASH =", 'source = frozen("AegisPredator_v24.mq5"',
                       'source = replace_once(source, "void OnTick()", "void OriginalOnTick()")',
                       'source = replace_once(source, "   signal=ProposedSignal(atr);", "   signal=CandidateR3Signal(atr);")'):
            self.assertIn(marker, self.builder)

    def test_closed_context_cost_gates_and_fixed_economics_exist(self):
        for marker in ("CopyRates(_Symbol,tf,1,count,r)", "r[0].time!=latestClosed",
                       "r[i].time-r[i+1].time!=seconds", "ask-bid<=0.10*atr",
                       "MathAbs((ask+bid)/2.0-signalClose)<=0.50*atr", "range<=2.0*atr",
                       "InpStopLossATRMul!=1.5", "InpTakeProfitRRMul!=2.0",
                       "InpMaxHoldBars!=60", "InpLotSize!=0.01", "InpEnableHardSL!=true",
                       "InpEnableCircuitBreaker!=true", "InpCooldownMinutes!=90"):
            self.assertIn(marker, self.extension)

    def test_native_fixtures_are_required_and_cover_each_family_mirrors(self):
        for marker in ("R3Blowoff", "R3Range", "R3EfficientFlag", "A_fade_sell", "A_fade_buy_mirror",
                       "B_internal_sell", "B_internal_buy_mirror", "C_flag_buy", "C_flag_sell_mirror",
                       "B_boundary_sweep_rejected", "R3_NATIVE_FIXTURES_PASS"):
            self.assertIn(marker, self.fixtures)
        self.assertIn("!RunR3FixtureTests()", self.builder)
        self.assertIn("Actual MQL behavioral fixtures missing/failed", self.runner)

    def test_position_accounting_includes_all_cash_components_and_parity_rows(self):
        for component in ("DEAL_PROFIT", "DEAL_COMMISSION", "DEAL_SWAP", "DEAL_FEE"):
            self.assertIn(component, self.extension)
        self.assertIn("Native position net/count mismatch", self.runner)
        self.assertIn("def parity(production, harness, *, evidence_base=None, production_base=None):", self.runner)
        self.assertIn("left != right", self.runner)


if __name__ == "__main__":
    unittest.main()
