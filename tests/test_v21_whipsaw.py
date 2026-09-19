import unittest
from datetime import datetime, timedelta

from research.v21_whipsaw import ObservedBar, causal_feature_at, delayed_label_at, wilder_atr14


def bars(closes):
    start = datetime(2026, 9, 9, 18)
    return [ObservedBar(i * 60, start + timedelta(minutes=i), close + 1, close - 1, close, "OK") for i, close in enumerate(closes)]


class V21WhipsawTests(unittest.TestCase):
    def test_monotonic_path_passes_gate_and_is_causal(self):
        data = bars([float(i) for i in range(30)])
        atr = wilder_atr14(data)
        feature = causal_feature_at(data, atr, 20)
        self.assertIsNotNone(feature)
        assert feature is not None
        self.assertEqual(feature.efficiency20, 1.0)
        self.assertFalse(feature.gate_veto)
        changed = data[:21] + bars([1000.0] * 9)
        self.assertEqual(feature, causal_feature_at(changed, wilder_atr14(changed), 20))

    def test_alternating_path_is_vetoed(self):
        data = bars([float(i % 2) for i in range(30)])
        feature = causal_feature_at(data, wilder_atr14(data), 20)
        self.assertIsNotNone(feature)
        assert feature is not None
        self.assertTrue(feature.gate_veto)

    def test_label_requires_three_future_bars(self):
        data = bars([float(i) for i in range(16)])
        self.assertIsNone(delayed_label_at(data, wilder_atr14(data), 13))
