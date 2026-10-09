from hashlib import sha256
from pathlib import Path
import unittest

from research.build_v24 import generate, function, EXPECTED


class V24PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = generate()
        cls.old = Path("AegisPredator_v23.mq5").read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.extension = Path("research/v23_tuning_extension.mqh").read_text(encoding="utf-8")

    def test_frozen_v23_unchanged(self):
        self.assertEqual(sha256(Path("AegisPredator_v23.mq5").read_bytes()).hexdigest().upper(), EXPECTED)

    def test_signal_copied_from_tested_harness(self):
        for name in ("ProposedSignal", "ReadClosed", "ReleaseExperiment"):
            self.assertEqual(function(self.source, name), function(self.extension, name))

    def test_breaker_preserved_exactly(self):
        self.assertEqual(function(self.source, "IsCircuitBreakerActive"), function(self.old, "IsCircuitBreakerActive"))

    def test_demo_account_symbol_timeframe_guards(self):
        self.assertIn('ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO', self.source)
        self.assertIn('_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || InpFadeBreakouts', self.source)
        self.assertIn('AccountInfoInteger(ACCOUNT_LOGIN) != InpTargetAccount', self.source)

    def test_no_be_or_research_export_code(self):
        for forbidden in ("PositionModify(", "FileOpen(", "FrameAdd(", "InpExperimentMode", "InpBETriggerR"):
            self.assertNotIn(forbidden, self.source)
        self.assertIn('InpFadeBreakouts    = false;', self.source)

    def test_position_management_and_magic_preserved(self):
        for name in ("ManageOpenPositions", "HasOpenPosition", "CheckMargin"):
            self.assertEqual(function(self.source, name), function(self.old, name))
        self.assertIn('InpMagicNumber      = 992300;', self.source)
        self.assertIn('InpLotSize          = 0.01;', self.source)

    def test_timer_is_passive(self):
        body = function(self.source, "OnTimer")
        self.assertNotIn("trade.", body)
        self.assertIn("LogV24Health();", body)
