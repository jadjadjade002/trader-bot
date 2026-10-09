import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from research.audit_v23_v21_forward import Bar, compute_atr_sma, reconstruct, restrict_window


class ForwardReconstructionTests(unittest.TestCase):
    def bars(self):
        start = datetime(2026, 10, 7, 1, 0)
        bars = [Bar(start + timedelta(minutes=i), 100, 101, 99, 100,
                    100, 100.1, "OK") for i in range(24)]
        bars[21] = replace(bars[21], open=100, high=102.3, low=99.7, close=102)
        bars[22] = replace(bars[22], open=100.2, high=101.2, low=100.5, close=100.8)
        return bars

    def test_atr_is_rolling_true_range_mean(self):
        bars = [Bar(datetime(2026, 10, 7) + timedelta(minutes=i),
                    100, 101, 99, 100, 100, 100.1, "OK") for i in range(20)]
        atr = compute_atr_sma(bars)
        self.assertIsNone(atr[13])
        self.assertAlmostEqual(atr[14], 2.0)
        self.assertAlmostEqual(atr[19], 2.0)

    def test_uses_only_completed_bars(self):
        bars = self.bars()
        snap, feat = reconstruct(bars)
        self.assertTrue(feat[23]["eligible"])
        self.assertEqual((snap[23].original, snap[23].closeback), (1, 1))
        bars[23] = replace(bars[23], open=1, high=1000, low=1, close=999,
                           flags="FUTURE_BAR_QUALITY_UNKNOWN_AT_ENTRY")
        changed, _ = reconstruct(bars)
        self.assertEqual((changed[23].original, changed[23].closeback), (1, 1))

    def test_gap_or_flag_blocks_signal(self):
        bars = self.bars()
        bars[10] = replace(bars[10], time=bars[10].time + timedelta(seconds=5))
        snap, feat = reconstruct(bars)
        self.assertFalse(feat[23]["eligible"])
        self.assertEqual(snap[23].original, 0)
        bars = self.bars()
        bars[10] = replace(bars[10], flags="OPEN_MISMATCH")
        snap, feat = reconstruct(bars)
        self.assertFalse(feat[23]["eligible"])
        self.assertEqual(snap[23].closeback, 0)

    def test_broker_window_is_half_open(self):
        snapshots, _ = reconstruct(self.bars())
        first = snapshots[22].bar
        selected = restrict_window(snapshots, first, first + timedelta(minutes=1))
        self.assertEqual([row.bar for row in selected], [first])
        with self.assertRaises(ValueError):
            restrict_window(snapshots, first, first)


if __name__ == "__main__":
    unittest.main()
