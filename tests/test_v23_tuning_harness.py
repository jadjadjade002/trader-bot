import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.build_v23_tuning import generate
from research.run_v23_tuning import check_coverage, settings


def function_body(text, name):
    start = text.index(name + "(")
    left = text.index("{", start)
    depth = 1
    for right in range(left + 1, len(text)):
        depth += (text[right] == "{") - (text[right] == "}")
        if depth == 0:
            return text[left:right + 1]
    raise ValueError("Unclosed function")


class TuningHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = generate()
        cls.frozen = Path("research/V23_BacktestBenchmark.mq5").read_text(encoding="utf-8")

    def test_breaker_unchanged(self):
        self.assertEqual(function_body(self.generated, "IsCircuitBreakerActive"),
                         function_body(self.frozen, "IsCircuitBreakerActive"))

    def test_tester_guard_and_be_disabled_default(self):
        self.assertIn("if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;", self.generated)
        self.assertIn("input double InpBETriggerR=0.0", self.generated)
        self.assertIn("if(trigger<=0) return;", self.generated)

    def test_only_closed_bar_trend_reads(self):
        body = function_body(self.generated, "ProposedSignal")
        self.assertIn("ReadClosed(trendFast,1,fast)", body)
        self.assertIn("ReadClosed(trendFast,6,past)", body)
        self.assertIn("CopyRates(_Symbol,PERIOD_M1,1,1,r)", body)
        self.assertNotIn("ReadClosed(trendFast,0", body)

    def test_original_binary_set_has_no_research_controls(self):
        text = settings("test", 0, {}, False, True)
        self.assertIn("InpFadeBreakouts=true", text)
        self.assertNotIn("InpBE", text)
        self.assertNotIn("InpExperimentMode", text)

    def test_grid_uses_explicit_indices_and_fade_mapping(self):
        text = settings("test", 1, {}, True, False)
        self.assertIn("InpFadeBreakouts=false", text)
        self.assertIn("InpTPGridIndex=0||0||1||3||Y", text)
        self.assertIn("InpBEGridIndex=0||0||1||2||Y", text)

    def test_coverage_rejects_early_termination(self):
        def epoch(date):
            return datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp() * 1000
        check_coverage(epoch("2026-05-06T01:00:00"), epoch("2026-10-05T22:59:59"),
                       "2026.05.06", "2026.10.06")
        with self.assertRaises(ValueError):
            check_coverage(epoch("2026-05-06T01:00:00"), epoch("2026-09-30T22:59:59"),
                           "2026.05.06", "2026.10.06")
