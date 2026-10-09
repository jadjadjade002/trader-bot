import unittest

from research.screen_v23_leveltouch import signal


class LevelTouchPredicateTests(unittest.TestCase):
    def setUp(self):
        self.bar = dict(dc_high="100", dc_low="90", atr="4", break_close="101",
                        retest_open="100.2", retest_close="100.6", retest_high="101",
                        retest_low="99.5")

    def test_buy_requires_touch_and_reclaim(self):
        self.assertEqual(signal(self.bar), 1)
        self.bar["retest_low"] = "100.1"
        self.assertEqual(signal(self.bar), 0)
        self.bar["retest_low"] = "99.5"
        self.bar["retest_close"] = "99.9"
        self.assertEqual(signal(self.bar), 0)

    def test_sell_requires_touch_and_rejection(self):
        self.bar.update(break_close="89", retest_open="89.7", retest_close="89.2",
                        retest_high="90.5", retest_low="88.9")
        self.assertEqual(signal(self.bar), -1)
        self.bar["retest_high"] = "89.9"
        self.assertEqual(signal(self.bar), 0)


if __name__ == "__main__":
    unittest.main()
