import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research import analyze_r3 as r3
from research.analyze import Bar


BASE = datetime(2025, 12, 8, 18, 0)
BASE_EPOCH = int(BASE.timestamp())


def bar(index, *, price=None, weight=1, spread=2.0):
    moment = BASE + timedelta(minutes=index)
    value = 99.0 if index % 2 == 0 else 101.0
    if price is not None:
        value = price
    return Bar(
        epoch=BASE_EPOCH + index * 60,
        broker_time=moment,
        open=value,
        high=value,
        low=value,
        close=value,
        tick_volume=weight,
        spread_points=spread,
        real_volume=0,
    )


def outcome(pnl=1.0):
    return r3.R3Outcome(1, 2, 4, 1, pnl, pnl - 0.01, "2026-02-03")


class SessionStatisticTests(unittest.TestCase):
    def test_weighted_vwap_sigma_and_median_are_causal(self):
        bars = [bar(i, weight=1 if i % 2 == 0 else 3) for i in range(31)]
        states = r3.session_statistics(bars)
        state = states[29]
        self.assertIsNotNone(state)
        self.assertAlmostEqual(state.vwap, 100.5)
        self.assertAlmostEqual(state.sigma, 0.75 ** 0.5)
        self.assertAlmostEqual(state.median_abs_change_20, 2.0)
        self.assertTrue(state.decelerating)
        changed = bars[:30] + [bar(30, price=150.0)]
        self.assertEqual(r3.session_statistics(changed)[29], state)

    def test_missing_minute_invalidates_remainder_of_session(self):
        bars = [bar(i) for i in range(40) if i != 10]
        states = r3.session_statistics(bars)
        self.assertTrue(all(state is None for state in states))

    def test_mid_session_input_without_1800_never_becomes_valid(self):
        bars = [bar(i) for i in range(5, 45)]
        self.assertTrue(all(state is None for state in r3.session_statistics(bars)))


class SignalTests(unittest.TestCase):
    def test_signal_is_statistical_fade_and_mirrored(self):
        bars = [bar(i, price=100.0) for i in range(4)]
        bars[0] = bar(0, price=103.0)
        bars[3] = bar(3, price=99.0)
        state = r3.SessionState(BASE.date(), 30, 100.5, 1.0, -1.5, 1.0, True)
        states = [None, None, None, state]
        self.assertEqual(r3.signal_direction(bars, states, 3, 1.5), 1)
        bars[0] = bar(0, price=97.0)
        bars[3] = bar(3, price=101.0)
        states[3] = r3.SessionState(BASE.date(), 30, 99.5, 1.0, 1.5, 1.0, True)
        self.assertEqual(r3.signal_direction(bars, states, 3, 1.5), -1)
        states[3] = r3.SessionState(BASE.date(), 30, 99.5, 1.0, 1.5, 1.0, False)
        self.assertEqual(r3.signal_direction(bars, states, 3, 1.5), 0)

    def test_entry_session_boundaries(self):
        self.assertFalse(r3.in_entry_session(datetime(2026, 1, 5, 18, 29)))
        self.assertTrue(r3.in_entry_session(datetime(2026, 1, 5, 18, 30)))
        self.assertTrue(r3.in_entry_session(datetime(2026, 1, 6, 1, 56)))
        self.assertFalse(r3.in_entry_session(datetime(2026, 1, 6, 1, 57)))

    def test_outcome_charges_entry_spread_and_fixed_stress_for_long(self):
        bars = [bar(i, price=100.0) for i in range(35)]
        bars[27] = bar(27, price=103.0)
        bars[30] = bar(30, price=99.0)
        bars[31] = bar(31, price=100.0, spread=2.0)
        bars[33] = bar(33, price=102.0)
        states = [None] * len(bars)
        states[30] = r3.SessionState(BASE.date(), 31, 100.5, 1.0, -1.5, 1.0, True)
        sample = r3.outcomes_for_window(
            bars, states, 1.5, 0.01, BASE, BASE + timedelta(days=1)
        )
        self.assertEqual(len(sample), 1)
        self.assertAlmostEqual(sample[0].pnl, 1.98)
        self.assertAlmostEqual(sample[0].stress_pnl, 1.97)


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.original = r3.outcomes_for_window

    def tearDown(self):
        r3.outcomes_for_window = self.original

    def test_guard_blocks_validation(self):
        calls = []
        def fake(*args):
            calls.append(args[-2:])
            return [outcome()] * 34
        r3.outcomes_for_window = fake
        result = r3.analyze_bars([bar(0)], 0.01)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(fold["validation"] is None for fold in result["folds"]))

    def test_validation_runs_once_per_fold_and_variant_after_guard(self):
        calls = []
        def fake(*args):
            start, end, variant = args[-2], args[-1], args[-4]
            phase = "train" if end - start == timedelta(days=28) else "validation"
            calls.append((phase, variant, start))
            return [outcome()] * (35 if phase == "train" else 20)
        r3.outcomes_for_window = fake
        result = r3.analyze_bars([bar(0)], 0.01)
        validations = [call for call in calls if call[0] == "validation"]
        self.assertEqual(len(validations), 12)
        self.assertEqual(len(set(validations)), 12)
        self.assertEqual(result["aggregate_validation"]["1.50"]["trades"], 80)
        self.assertIn("nominal_expectancy_positive_at_1_5x_spread", result["gates"])


if __name__ == "__main__":
    unittest.main()
