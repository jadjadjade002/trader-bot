from hashlib import sha256
from pathlib import Path
from unittest import TestCase

from research.build_v25 import EXPECTED, OUT, function, generate, replace_once


class V25CandidateTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = generate()
        cls.baseline = Path("AegisPredator_v24.mq5").read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.extension = Path("research/v25_signal_extension.mqh").read_text(encoding="utf-8")

    def test_baseline_hash_frozen(self):
        self.assertEqual(sha256(Path("AegisPredator_v24.mq5").read_bytes()).hexdigest().upper(), EXPECTED)

    def test_generated_artifact_matches_builder(self):
        self.assertEqual(OUT.read_text(encoding="utf-8"), self.generated)

    def test_mode_zero_signal_and_risk_management_verbatim(self):
        for name in ("ProposedSignal", "ReadClosed", "IsCircuitBreakerActive", "ManageOpenPositions", "HasOpenPosition", "CheckMargin", "InitV24Signal"):
            with self.subTest(name=name):
                self.assertEqual(function(self.generated, name), function(self.baseline, name))
        body = function(self.generated, "CandidateSignal")
        self.assertIn("candidateSide=ProposedSignal(atr);\n      return candidateSide;", body)
        self.assertLess(body.index("if(InpExperimentMode==0)"), body.index("minBody[3]"))

    def test_tester_guard_and_no_be(self):
        self.assertIn("if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;", self.generated)
        for forbidden in ("PositionModify(", "InpBETriggerR", "ManageBreakEven", "CopyTicks(", "WebRequest("):
            self.assertNotIn(forbidden, self.generated)
        self.assertIn('InpFadeBreakouts    = false;', self.generated)

    def test_closed_features_and_excluded_signal_breakout_bar(self):
        trend = function(self.generated, "ClosedTrendDirection")
        self.assertIn("ReadClosed(trendFast,1,fast)", trend)
        self.assertIn("ReadClosed(trendFast,6,past)", trend)
        self.assertNotIn(",0,", trend)
        candidate = function(self.generated, "CandidateSignal")
        self.assertIn("CopyRates(_Symbol,PERIOD_M1,1,11,r)", candidate)
        self.assertIn("diagnosticLevel=buy?r[1].high:r[1].low;", candidate)
        self.assertIn("for(int i=2;i<11;i++)", candidate)
        self.assertNotIn("PERIOD_M5,0", candidate)

    def test_frozen_strength_and_symmetric_trend_direction(self):
        body = function(self.generated, "CandidateSignal")
        self.assertIn("minBody[3]={0.10,0.20,0.30}", body)
        self.assertIn("minClose[3]={0.60,0.70,0.80}", body)
        self.assertIn("buffer[3]={0.0,0.05,0.10}", body)
        self.assertEqual(body.count("candidateSide=candidateTrend;"), 3)
        self.assertNotIn("candidateSide=-candidateTrend", body)
        self.assertIn("range>2.0*atr", body)

    def test_bounds_fail_closed(self):
        body = function(self.generated, "ValidateV25Inputs")
        for required in ("InpExperimentMode>3", "InpEntryStrength>2", "InpTPGridIndex>3", "InpFadeBreakouts", "InpStopLossATRMul<0.5", "EffectiveTPR()>4.0", "InpMaxHoldBars>120"):
            self.assertIn(required, body)

    def test_optimizer_schema_and_costs(self):
        body = function(self.generated, "ExportOptimizationFrame")
        for required in ("DEAL_POSITION_ID", "DEAL_PROFIT", "DEAL_COMMISSION", "DEAL_SWAP", "DEAL_FEE", "DEAL_MAGIC", "DEAL_SYMBOL", "HistorySelect(0,TimeCurrent())", 'FrameAdd("v25_native_grid"', "double d[19]", "d[18]=InpEntryStrength", 'FrameAdd("v25_month_coverage"'):
            self.assertIn(required, body)
        self.assertIn('"last_tick_msc","entry_strength"', self.generated)
        self.assertIn('InpRunTag+"_coverage.csv"', self.generated)

    def test_monthly_coverage_no_year_filter(self):
        body = function(self.generated, "ObserveEquity")
        self.assertIn("id=d.year*100+d.mon", body)
        self.assertNotIn("d.year==2026", body)
        self.assertIn("monthIds[12]", self.generated)
        self.assertIn("monthTicks[monthN-1]++", function(self.generated, "OnTick"))

    def test_diagnostic_reads_after_economic_execution(self):
        body = function(self.generated, "OnTick")
        self.assertLess(body.index("OriginalOnTick();"), body.index("CopyRates("))
        self.assertIn('candidateReason="not_evaluated_execution_block"', body)
        self.assertIn('"execution_gate","held_before","order_attempt"', self.generated)

    def test_replace_refuses_drift(self):
        with self.assertRaises(ValueError):
            replace_once("a a", "a", "b")
        with self.assertRaises(ValueError):
            replace_once("z", "a", "b")

    def test_preserved_demo_account_guard(self):
        body = function(self.generated, "OnInit")
        self.assertIn("ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO", body)
        self.assertIn("AccountInfoInteger(ACCOUNT_LOGIN) != InpTargetAccount", body)

    def test_reproducible_generation(self):
        self.assertEqual(generate(), generate())
