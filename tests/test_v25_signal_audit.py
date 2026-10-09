import unittest
from research.v25_signal_audit import impulse_label


class ImpulseAttributionTests(unittest.TestCase):
    def test_direction_symmetry(self):
        now = {"atr": "2", "retest_close": "101"}
        past = {"retest_close": "100"}
        self.assertEqual(impulse_label(now, past, "buy"), ("aligned", .5))
        self.assertEqual(impulse_label(now, past, "sell"), ("opposed", -.5))

    def test_unknown_is_not_zero(self):
        self.assertEqual(impulse_label({"atr":"2", "retest_close":"101"}, None, "buy"), ("unknown", None))

    def test_flat_and_exact_boundary(self):
        now = {"atr": "2", "retest_close": "100.5"}
        self.assertEqual(impulse_label(now, {"retest_close":"100"}, "buy"), ("aligned", .25))
        self.assertEqual(impulse_label(now, {"retest_close":"100.5"}, "buy"), ("flat", 0.))

    def test_invalid_atr_rejected(self):
        with self.assertRaises(ValueError):
            impulse_label({"atr":"0", "retest_close":"100"}, {"retest_close":"99"}, "buy")

    def test_nonfinite_rejected(self):
        for field in ("atr", "retest_close"):
            for value in ("nan", "inf", "-inf"):
                now = {"atr":"2", "retest_close":"100"}
                now[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    impulse_label(now, {"retest_close":"99"}, "buy")

    def test_invalid_direction_rejected(self):
        with self.assertRaises(ValueError):
            impulse_label({"atr":"2", "retest_close":"100"}, {"retest_close":"99"}, "hold")
