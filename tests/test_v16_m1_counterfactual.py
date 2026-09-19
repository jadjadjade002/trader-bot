import unittest
from datetime import datetime, timedelta

from research.v16_m1_counterfactual import Scenario, compare, simulate_trade


def position(side="buy"):
    return {"entry_terminal_time": "20260910 00:00:10.000", "side": side,
            "entry": 100.0, "entry_deal": "1"}


def bar(minute, high, low, spread=0.0):
    return {"time": datetime(2026, 9, 10) + timedelta(minutes=minute),
            "high": high, "low": low, "spread": spread}


class CounterfactualTests(unittest.TestCase):
    def setUp(self):
        self.scenario = Scenario("x", 200, 200, 100, 20)

    def test_tp(self):
        result = simulate_trade(position(), [bar(1, 102.1, 99.5)], self.scenario)
        self.assertEqual(result["status"], "TP")

    def test_initial_stop(self):
        result = simulate_trade(position(), [bar(1, 100.5, 97.9)], self.scenario)
        self.assertEqual(result["status"], "INITIAL_SL")

    def test_trigger_then_later_be(self):
        result = simulate_trade(position(), [bar(1, 101.1, 100.3), bar(2, 100.5, 100.1)], self.scenario)
        self.assertEqual(result["status"], "BE_LOCK")

    def test_trigger_and_retrace_same_bar_is_ambiguous(self):
        result = simulate_trade(position(), [bar(1, 101.1, 100.1)], self.scenario)
        self.assertEqual(result["status"], "AMBIGUOUS_INTRABAR")

    def test_tp_and_stop_same_bar_is_ambiguous(self):
        result = simulate_trade(position(), [bar(1, 102.1, 97.9)], self.scenario)
        self.assertEqual(result["status"], "AMBIGUOUS_INTRABAR")

    def test_not_covered(self):
        self.assertEqual(simulate_trade(position(), [], self.scenario)["status"], "NOT_COVERED")

    def test_entry_before_dataset_is_not_covered(self):
        old = position()
        old["entry_terminal_time"] = "20260909 23:59:00.000"
        self.assertEqual(simulate_trade(old, [bar(1, 101, 99)], self.scenario)["status"], "NOT_COVERED")

    def test_validation_fails_closed_when_baseline_not_reproduced(self):
        trade = position()
        trade["class"] = "BE_LOCK"
        report = compare([trade], [bar(1, 102.1, 99.5)], [Scenario("v16_original", 200, 200, 100, 20)])
        self.assertFalse(report["validation"]["decision_valid"])
        self.assertEqual(report["validation"]["gate"], "INCONCLUSIVE_OHLC_CANNOT_REPRODUCE_LIVE_EXITS")


if __name__ == "__main__":
    unittest.main()
