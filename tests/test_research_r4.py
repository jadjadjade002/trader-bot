import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research import analyze_r4 as r4
from research.analyze import Bar


BASE = datetime(2025, 8, 11)
BASE_EPOCH = int(BASE.timestamp())


def bar(index, *, open_=100.0, high=100.5, low=99.5, close=100.0, spread=2.0):
    return Bar(BASE_EPOCH + index * 60, BASE + timedelta(minutes=index), open_, high, low, close, 1, spread, 0)


def outcome(pnl=1.0, day="2025-10-07"):
    return r4.R4Outcome(1, 2, 4, 1, pnl, pnl - 0.02, day)


class IndicatorTests(unittest.TestCase):
    def test_ema_uses_sma_seed_and_is_causal(self):
        values = [1.0, 2.0, 3.0, 4.0]
        result = r4.ema(values, 3)
        self.assertEqual(result[:2], [None, None])
        self.assertEqual(result[2], 2.0)
        self.assertEqual(result[3], 3.0)

    def test_wilder_atr_seed_and_update(self):
        bars = [bar(i) for i in range(15)]
        atr = r4.wilder_atr14(bars)
        self.assertIsNone(atr[12])
        self.assertAlmostEqual(atr[13], 1.0)
        self.assertAlmostEqual(atr[14], 1.0)


class SignalTests(unittest.TestCase):
    def test_crossover_and_filters_are_exact(self):
        bars = [bar(i, high=100.2, low=99.8, close=100.1) for i in range(121)]
        fast = [100.0] * 121
        slow = [100.0] * 121
        atr = [1.0] * 121
        fast[120] = 100.1
        self.assertEqual(r4.signal_direction(bars, fast, slow, atr, 120), 1)
        chased = list(bars)
        chased[120] = bar(120, high=100.5, low=100.3, close=100.4)
        self.assertEqual(r4.signal_direction(chased, fast, slow, atr, 120), 0)

    def test_120_bar_window_must_be_consecutive(self):
        bars = [bar(i) for i in range(121)]
        broken = list(bars)
        original = broken[60]
        broken[60] = Bar(original.epoch + 60, original.broker_time + timedelta(minutes=1), original.open, original.high, original.low, original.close, 1, 2.0, 0)
        fast, slow, atr = [100.0] * 121, [100.0] * 121, [1.0] * 121
        fast[120] = 100.1
        self.assertEqual(r4.signal_direction(broken, fast, slow, atr, 120), 0)

    def test_two_x_spread_outcome_is_fixed(self):
        bars = [bar(i) for i in range(125)]
        fast, slow, atr = [100.0] * 125, [100.0] * 125, [1.0] * 125
        fast[120] = 100.1
        bars[121] = bar(121, open_=100.0, high=100.2, low=99.8, close=100.0, spread=2.0)
        bars[123] = bar(123, open_=101.0, high=102.2, low=100.8, close=102.0)
        start = bars[121].broker_time - timedelta(minutes=1)
        start = start.replace(hour=18, minute=0)
        shifted = []
        offset = datetime(2025, 8, 11, 18, 0) - BASE
        for item in bars:
            shifted.append(Bar(item.epoch + int(offset.total_seconds()), item.broker_time + offset, item.open, item.high, item.low, item.close, item.tick_volume, item.spread_points, item.real_volume))
        sample = r4.outcomes_for_window(shifted, fast, slow, atr, 0.01, datetime(2025, 8, 11), datetime(2025, 8, 12))
        self.assertEqual(len(sample), 1)
        self.assertAlmostEqual(sample[0].pnl, 1.98)
        self.assertAlmostEqual(sample[0].stress_pnl, 1.96)


class EvidenceAndWalkForwardTests(unittest.TestCase):
    def test_daily_t_statistic_uses_daily_net(self):
        sample = [outcome(1.0, "2025-10-07"), outcome(1.0, "2025-10-07"), outcome(4.0, "2025-10-08")]
        evidence = r4.daily_evidence(sample)
        self.assertEqual(evidence["days"], 2)
        self.assertAlmostEqual(evidence["daily_net_t_statistic"], 3.0)

    def setUp(self):
        self.original = r4.outcomes_for_window

    def tearDown(self):
        r4.outcomes_for_window = self.original

    def test_guard_blocks_validation(self):
        calls = []
        def fake(*args):
            calls.append(args[-2:])
            return [outcome()] * 34
        r4.outcomes_for_window = fake
        result = r4.analyze_bars([bar(0)], 0.01)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(fold["validation"] is None for fold in result["folds"]))

    def test_validation_once_and_strong_gates_are_reported(self):
        calls = []
        def fake(*args):
            start, end = args[-2], args[-1]
            phase = "train" if end - start == timedelta(days=28) else "validation"
            identity = id(args[1])
            calls.append((phase, identity, start))
            count = 35 if phase == "train" else 20
            return [outcome(1.0 + (index % 3), f"2025-10-{7 + index % 20:02d}") for index in range(count)]
        r4.outcomes_for_window = fake
        result = r4.analyze_bars([bar(0)], 0.01)
        validations = [call for call in calls if call[0] == "validation"]
        self.assertEqual(len(validations), 12)
        self.assertEqual(len(set(validations)), 12)
        self.assertEqual(result["aggregate_validation"]["6/24"]["trades"], 80)
        self.assertIn("nominal_daily_net_t_statistic_at_least_2_50", result["gates"])
        self.assertIn("robustness_5/20_profit_factor_at_least_1_10", result["gates"])


if __name__ == "__main__":
    unittest.main()
