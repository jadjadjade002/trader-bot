import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research import analyze_r2 as r2
from research.analyze import Bar


BASE = datetime(2026, 4, 6)
BASE_EPOCH = int(BASE.timestamp())


def bar(index, *, open_=100.0, high=101.0, low=99.0, close=100.0, spread=2.0):
    return Bar(
        epoch=BASE_EPOCH + index * 60,
        broker_time=BASE + timedelta(minutes=index),
        open=open_, high=high, low=low, close=close,
        tick_volume=1, spread_points=spread, real_volume=0,
    )


def outcome(pnl=1.0):
    return r2.R2Outcome(1, 2, 4, 1, pnl, pnl - 0.01, "2026-06-02")


class AggregationTests(unittest.TestCase):
    def test_only_complete_aligned_buckets_are_emitted(self):
        bars = [bar(i) for i in range(15)]
        self.assertEqual(len(r2.aggregate_complete(bars, 5)), 3)
        self.assertEqual(len(r2.aggregate_complete(bars, 15)), 1)
        missing = bars[:7] + bars[8:]
        self.assertEqual(len(r2.aggregate_complete(missing, 5)), 2)
        self.assertEqual(len(r2.aggregate_complete(missing, 15)), 0)

    def test_bucket_is_usable_only_after_completion(self):
        m5 = r2.aggregate_complete([bar(i) for i in range(10)], 5)
        self.assertIsNone(r2.latest_complete_index(m5, BASE_EPOCH + 4 * 60, 5))
        self.assertEqual(r2.latest_complete_index(m5, BASE_EPOCH + 5 * 60, 5), 0)
        self.assertEqual(r2.latest_complete_index(m5, BASE_EPOCH + 9 * 60, 5), 0)
        self.assertEqual(r2.latest_complete_index(m5, BASE_EPOCH + 10 * 60, 5), 1)


class FormulaTests(unittest.TestCase):
    def test_m1_reacceleration_is_strict_and_mirrored(self):
        bars = [bar(0), bar(1), bar(2, open_=100, high=103, low=99, close=102.5)]
        self.assertTrue(r2.m1_reacceleration(bars, 2, 1))
        self.assertFalse(r2.m1_reacceleration(bars, 2, -1))
        short = [bar(0), bar(1), bar(2, open_=100, high=101, low=97, close=97.5)]
        self.assertTrue(r2.m1_reacceleration(short, 2, -1))

    def test_pullback_formula_is_mirrored(self):
        m5 = [
            r2.HigherBar(0, 300, 100, 102, 100.5, 101),
            r2.HigherBar(300, 600, 101, 103, 100.8, 102),
        ]
        self.assertTrue(r2.pullback_ok(m5, 1, 1, 101.0, 100.0))
        self.assertFalse(r2.pullback_ok(m5, 1, -1, 101.0, 103.5))


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.original = r2.outcomes_for_window

    def tearDown(self):
        r2.outcomes_for_window = self.original

    def test_viability_guard_prevents_validation_inspection(self):
        calls = []
        def fake(*args):
            calls.append((args[-2], args[-1], args[-4]))
            return [outcome()] * 34
        r2.outcomes_for_window = fake
        result = r2.analyze_bars([bar(0)], 0.01)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(fold["validation"] is None for fold in result["folds"]))
        self.assertFalse(result["gates"]["all_nominal_training_viability_guards_pass"])

    def test_each_variant_validation_is_evaluated_once_after_guard(self):
        calls = []
        def fake(*args):
            entry_start, entry_end, variant = args[-2], args[-1], args[-4]
            phase = "train" if entry_end - entry_start == timedelta(days=28) else "validation"
            calls.append((phase, variant, entry_start))
            return [outcome()] * (35 if phase == "train" else 40)
        r2.outcomes_for_window = fake
        result = r2.analyze_bars([bar(0)], 0.01)
        validation_calls = [call for call in calls if call[0] == "validation"]
        self.assertEqual(len(validation_calls), 12)
        self.assertEqual(len(set(validation_calls)), 12)
        self.assertTrue(all(fold["validation"] is not None for fold in result["folds"]))
        self.assertEqual(result["aggregate_validation"]["0.10"]["trades"], 160)
        self.assertIn("nominal_expectancy_positive_at_1_5x_spread", result["gates"])


if __name__ == "__main__":
    unittest.main()
