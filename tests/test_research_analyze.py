import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("research_analyze", ROOT / "research" / "analyze.py")
analyze = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = analyze
SPEC.loader.exec_module(analyze)


def bar(index, *, open_=100.0, high=101.0, low=99.0, close=100.0, spread=2.0):
    moment = datetime(2026, 8, 3, 18, 0) + timedelta(minutes=index)
    return analyze.Bar(
        epoch=1_775_000_000 + index * 60,
        broker_time=moment,
        open=open_,
        high=high,
        low=low,
        close=close,
        tick_volume=1,
        spread_points=spread,
        real_volume=0,
    )


class CsvValidationTests(unittest.TestCase):
    def test_exact_header_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("time_broker_epoch,open\n1,100\n", encoding="utf-8")
            with self.assertRaisesRegex(analyze.ValidationError, "header must exactly"):
                analyze.load_csv(path)

    def test_valid_csv_and_bad_ohlc(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            row = ["1775000040", "2026-08-03 18:00:00", "100", "101", "99", "100", "4", "2", "0"]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(analyze.CSV_COLUMNS)
                writer.writerow(row)
            self.assertEqual(len(analyze.load_csv(path)), 1)
            row[3] = "98"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(analyze.CSV_COLUMNS)
                writer.writerow(row)
            with self.assertRaisesRegex(analyze.ValidationError, "inconsistent OHLC"):
                analyze.load_csv(path)


class FeatureAndOutcomeTests(unittest.TestCase):
    def test_atr_is_causal_wilder_average(self):
        bars = [bar(i) for i in range(20)]
        first = analyze.wilder_atr14(bars)
        changed = bars[:-1] + [bar(19, high=200.0, low=1.0)]
        second = analyze.wilder_atr14(changed)
        self.assertIsNone(first[12])
        self.assertEqual(first[13], 2.0)
        self.assertEqual(first[18], second[18])
        self.assertNotEqual(first[19], second[19])

    def test_session_cutoff(self):
        self.assertTrue(analyze.in_entry_session(datetime(2026, 8, 3, 18, 0)))
        self.assertTrue(analyze.in_entry_session(datetime(2026, 8, 4, 1, 56)))
        self.assertFalse(analyze.in_entry_session(datetime(2026, 8, 4, 1, 57)))
        self.assertFalse(analyze.in_entry_session(datetime(2026, 8, 3, 17, 59)))

    def test_long_proxy_pays_entry_spread_and_signals_do_not_overlap(self):
        bars = [bar(i) for i in range(25)]
        for index in (13, 14):
            bars[index] = bar(index, open_=100.0, high=103.0, low=99.0, close=103.0)
        bars[14] = bar(14, open_=100.0, high=103.0, low=99.0, close=103.0, spread=2.0)
        bars[16] = bar(16, open_=100.0, high=102.0, low=99.0, close=102.0)
        atr = [2.0] * len(bars)
        outcomes = analyze.outcomes_for_range(bars, atr, 0.75, 0.01, 0, len(bars))
        self.assertEqual([item.signal_index for item in outcomes[:1]], [13])
        self.assertAlmostEqual(outcomes[0].pnl, 102.0 - 100.02)

    def test_short_proxy_pays_exit_spread(self):
        bars = [bar(i) for i in range(25)]
        bars[13] = bar(13, open_=100.0, high=101.0, low=97.0, close=97.0)
        bars[16] = bar(16, open_=99.0, high=100.0, low=97.0, close=98.0, spread=3.0)
        atr = [2.0] * len(bars)
        outcomes = analyze.outcomes_for_range(bars, atr, 0.75, 0.01, 0, len(bars))
        self.assertEqual(outcomes[0].direction, -1)
        self.assertAlmostEqual(outcomes[0].pnl, 100.0 - 98.03)

    def test_split_has_three_bar_embargo(self):
        bars = [bar(i) for i in range(100)]
        result = analyze.analyze_bars(bars, 0.01)
        self.assertEqual(result["split"]["split_index"], 70)
        self.assertEqual(result["split"]["training_signal_stop_exclusive"], 67)
        self.assertEqual(result["split"]["validation_signal_start"], 73)
        self.assertEqual(len(result["attempts"]), 3)
        self.assertEqual([a["threshold_atr"] for a in result["attempts"]], [0.75, 1.0, 1.25])
        evaluated = [a for a in result["attempts"] if a["validation"] is not None]
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0]["threshold_atr"], result["selected_threshold_atr"])

    def test_gap_summary_counts_missing_minutes_without_filling(self):
        bars = [bar(0), bar(1), bar(4), bar(5), bar(8)]
        summary = analyze.gap_summary(bars)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["missing_whole_minutes"], 4)
        self.assertEqual(summary["max_gap_minutes"], 2)
        result = analyze.analyze_bars(bars, 0.01)
        self.assertEqual(result["rows"], 5)
        self.assertEqual(result["input_gaps"], summary)


if __name__ == "__main__":
    unittest.main()
