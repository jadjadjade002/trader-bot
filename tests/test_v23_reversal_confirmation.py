import unittest

from research.screen_v23_reversal_confirmation import signal


class ReversalConfirmationTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(dc_high=101, dc_low=99, atr=2, break_close=102,
                   retest_open=101.1, retest_close=100.8,
                   retest_high=101.3, retest_low=100.5)
        row.update(changes)
        return row

    def test_bearish_closeback_sells(self):
        self.assertEqual(signal(self.row()), -1)

    def test_bullish_closeback_buys(self):
        self.assertEqual(signal(self.row(break_close=98, retest_open=98.9,
                                        retest_close=99.2, retest_high=99.5,
                                        retest_low=98.7)), 1)

    def test_wrong_candle_direction_and_channel_boundary_rejected(self):
        self.assertEqual(signal(self.row(retest_open=100.6)), 0)
        self.assertEqual(signal(self.row(retest_close=101)), 0)
        self.assertEqual(signal(self.row(retest_low=99.9)), 0)

    def test_invalid_features_rejected(self):
        for changes in ({"atr": float("nan")}, {"retest_high": 100}, {"dc_low": 102}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                signal(self.row(**changes))


if __name__ == "__main__":
    unittest.main()
