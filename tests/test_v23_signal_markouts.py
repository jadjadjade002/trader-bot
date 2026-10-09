import unittest
from datetime import datetime, timedelta

from research.audit_v23_signal_markouts import Snapshot, audit, bootstrap_daily_mean, markout


class MarkoutTests(unittest.TestCase):
    def test_quoted_spread_drag_is_counted_both_sides(self):
        t = datetime(2026, 5, 1, 10, 0)
        a = Snapshot(t, 1, 0, 100.0, 100.2)
        b = Snapshot(t + timedelta(minutes=1), 0, 0, 101.0, 101.2)
        self.assertAlmostEqual(markout(a, b, 1)[0], 1.0)
        self.assertAlmostEqual(markout(a, b, 1)[1], 0.8)
        self.assertAlmostEqual(markout(a, b, 1)[2], 0.2)
        self.assertAlmostEqual(markout(a, b, -1)[1], -1.2)
        self.assertAlmostEqual(markout(a, b, -1)[2], 0.2)

    def test_signal_direction_and_gap_rejection(self):
        t = datetime(2026, 5, 1, 10, 0)
        rows = [Snapshot(t, 1, 1, 100.0, 100.2),
                Snapshot(t + timedelta(minutes=1), 0, 0, 101.0, 101.2)]
        out = audit(rows, (1,))['results']
        self.assertAlmostEqual(out['original_momentum']['1']['mean_spread_aware_price_delta'], 0.8)
        self.assertAlmostEqual(out['original_fade']['1']['mean_spread_aware_price_delta'], -1.2)
        self.assertAlmostEqual(out['closeback_fade']['1']['mean_spread_aware_price_delta'], -1.2)
        rows[1] = Snapshot(t + timedelta(minutes=2), 0, 0, 101.0, 101.2)
        self.assertEqual(audit(rows, (2,))['results']['original_momentum']['2']['matched'], 0)

    def test_bootstrap_requires_multiple_broker_days(self):
        self.assertIsNone(bootstrap_daily_mean({'2026-05-01': (1.0, 1)}))


if __name__ == '__main__':
    unittest.main()
