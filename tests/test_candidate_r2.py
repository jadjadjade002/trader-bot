"""Source-contract checks for R2 MQL. These do not execute or compile MQL."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "research/candidate_r2_signal_extension.mqh"
BUILD = ROOT / "research/build_candidate_r2.py"
PLAN = ROOT / "docs/CANDIDATE_R2_LUNA_PLAN.md"


class CandidateR2SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ext = EXT.read_text(encoding="utf-8")
        cls.build = BUILD.read_text(encoding="utf-8")
        cls.plan = PLAN.read_text(encoding="utf-8")

    def test_modes_and_fixed_v24_economics(self):
        self.assertIn("InpExperimentMode<0 || InpExperimentMode>5", self.ext)
        self.assertIn("InpEntryStrength<0 || InpEntryStrength>1", self.ext)
        for frozen in (
            "InpStopLossATRMul!=1.5", "InpTakeProfitRRMul!=2.0",
            "InpMaxHoldBars!=60", "InpLotSize!=0.01", "InpFadeBreakouts",
        ):
            with self.subTest(frozen=frozen):
                self.assertIn(frozen, self.ext)
        self.assertIn("InpEnableHardSL!=true", self.ext)
        self.assertIn("BE off", self.ext)

    def test_all_signal_reads_use_completed_bars(self):
        self.assertIn("CopyRates(_Symbol,PERIOD_M1,1,count,r)", self.ext)
        self.assertIn("ReadClosed(trendFast,1", self.ext)
        self.assertIn("ReadClosed(trendFast,6", self.ext)
        self.assertIn("ReadClosed(entryFast,2", self.ext)
        self.assertNotIn("CopyRates(_Symbol,PERIOD_M1,0,", self.ext)
        self.assertNotIn("CopyBuffer(atrHandle,0,0,", self.ext)
        self.assertIn("r[i].time-r[i+1].time!=60", self.ext)

    def test_buy_sell_predicates_are_symmetric_in_each_family(self):
        pairs = (
            ("s1.close>=ema20+b", "s1.close<=ema20-b"),
            ("r[0].close>hi+pad", "r[0].close<lo-pad"),
            ("r[1].low<=priorLo-minSweep", "r[1].high>=priorHi+minSweep"),
            ("r2ArmedDirection=1", "r2ArmedDirection=-1"),
            ("r.low<=level+0.15*atr", "r.high>=level-0.15*atr"),
            ("r[1].close-r[6].close<=-x", "r[1].close-r[6].close>=x"),
        )
        for buy, sell in pairs:
            with self.subTest(buy=buy, sell=sell):
                self.assertIn(buy, self.ext)
                self.assertIn(sell, self.ext)

    def test_threshold_boundaries_and_causality_contract_fixtures(self):
        # Hand-authored edge fixtures document expected comparisons; source checks
        # ensure MQL uses inclusive comparisons where the protocol says equality passes.
        edge_fixtures = {
            "spread_equal_0_10_atr": ("ask-bid<=0.1*atr", "pass"),
            "midpoint_equal_0_50_atr": ("<=0.5*atr", "pass"),
            "compression_range_equal_0_80_atr": ("r[i+1].high-r[i+1].low>0.8*a2[i]", "reject only above"),
            "candle_range_equal_2_atr": ("range>2.0*atr", "pass"),
            "range_width_equal_2_atr": ("width<2.0*atr", "pass"),
            "range_width_equal_6_atr": ("width>6.0*atr", "pass"),
            "sweep_equal_minimum": ("r[1].low<=priorLo-minSweep", "pass"),
            "sweep_equal_maximum": ("r[1].low>=priorLo-maxSweep", "pass"),
        }
        self.assertEqual(len(edge_fixtures), 8)
        for name, (predicate, _expectation) in edge_fixtures.items():
            with self.subTest(fixture=name):
                self.assertIn(predicate, self.ext)
        self.assertIn("CopyR2Rates(23,r)", self.ext)
        self.assertIn("if(r[i].time-r[i+1].time!=60) return false", self.ext)

    def test_break_retest_state_fixtures_have_expiry_cancel_and_reset(self):
        fixtures = {
            "first_next_bar": "r2ArmedAge++",
            "third_bar_still_eligible": "r2ArmedAge>3",
            "fourth_bar_expired": "r2ArmedAge>3",
            "cancel_after_level_close": "r2ArmedLevel-0.15*atr",
            "no_duplicate_level_within_point": "MathAbs(priorHigh-r2LastArmLevel)>_Point",
            "state_advances_before_execution_gates": "if(fresh) R2AdvanceArmOnFreshBar();",
            "trend_loss_cancels_arm": "direction!=r2ArmedDirection",
            "gap_cancels_arm": "{ ResetR2State();return; }",
            "fresh_instance_reset": "ResetR2State()",
        }
        for name, token in fixtures.items():
            with self.subTest(fixture=name):
                self.assertIn(token, self.ext if token != "ResetR2State()" else self.build)
        self.assertIn("r2ArmedDirection=0;r2ArmedAge=0;r2ArmedLevel=0", self.ext)

    def test_c_and_e_predicates_accept_fixture_context_without_indicator_io(self):
        range_start = self.ext.index("int R2RangeReversal(")
        range_end = self.ext.index("int R2BreakRetest(", range_start)
        exhaustion_start = self.ext.index("int R2Exhaustion(")
        exhaustion_end = self.ext.index("int CandidateR2Signal(", exhaustion_start)
        range_fn = self.ext[range_start:range_end]
        exhaustion_fn = self.ext[exhaustion_start:exhaustion_end]
        self.assertIn("double m5fast,double m5slow,double m5past,double m5atr", range_fn)
        self.assertNotIn("ReadClosed(", range_fn)
        self.assertIn("double ema9,double e9prev", exhaustion_fn)
        self.assertNotIn("ReadClosed(", exhaustion_fn)
        self.assertIn("void R2AdvanceArm(int direction,double ema9,double ema20,double atr,const MqlRates &s1)", self.ext)

    def test_builder_is_hash_guarded_and_separate_from_r1(self):
        self.assertIn('"AegisPredator_v24.mq5", EXPECTED', self.build)
        self.assertIn('"research/V23_BacktestBenchmark.mq5", BENCH_HASH', self.build)
        self.assertIn('"research/v23_tuning_extension.mqh", TUNING_HASH', self.build)
        self.assertIn('research/ResearchCandidate_R2.mq5', self.build)
        self.assertNotIn("ResearchCandidate_R1.mq5", self.build)
        self.assertIn('source.replace(\'"24.00"\', \'"24.91"\', 1)', self.build)
        self.assertIn("tester-only", self.build)
        self.assertTrue((ROOT / "research/ResearchCandidate_R2.mq5").is_file())

    def test_r2_plan_freezes_exits_and_ten_configs(self):
        for token in ("SL 1.5 ATR", "TP 2R", "60 M1-bar", "BE off", "0.01 lot", "exactly two entry presets"):
            with self.subTest(token=token):
                self.assertIn(token, self.plan)
        self.assertNotIn("108-point", self.plan)


if __name__ == "__main__":
    unittest.main()
