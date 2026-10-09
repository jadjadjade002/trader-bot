import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from research.finalize_v23_tuning import audit_grid, NS
from research.v23_tuning_matrix import grid, TP_VALUES, BE_VALUES


class TuningEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.frames = []
        self.rows = []
        for i, item in enumerate(grid(0)):
            frame = dict(item, **{"pass": str(i), "net": -100-i/100, "positions": 100+i,
                                 "equity_dd_pct": 1.123456})
            self.frames.append(frame)
            self.rows.append(dict(Pass=i, Profit=round(frame["net"], 2), Trades=100+i,
                **{"Equity DD %": 1.1235, "InpStopLossATRMul": item["sl_atr"],
                   "InpTPGridIndex": TP_VALUES.index(item["tp_r"]),
                   "InpBEGridIndex": BE_VALUES.index(item["be_r"])}))

    def check(self):
        root = ET.Element("{"+NS["s"]+"}Workbook")
        table = ET.SubElement(root, "{"+NS["s"]+"}Table")
        header = list(self.rows[0])
        values = [header] + [[r[k] for k in header] for r in self.rows]
        for values_row in values:
            row = ET.SubElement(table, "{"+NS["s"]+"}Row")
            for value in values_row:
                cell = ET.SubElement(row, "{"+NS["s"]+"}Cell")
                ET.SubElement(cell, "{"+NS["s"]+"}Data").text = str(value)
        ET.ElementTree(root).write(self.folder / "sample.xml", encoding="utf-8")
        return audit_grid(self.folder, "sample", self.frames)

    def test_complete_exact_grid_accepts_native_rounding(self):
        self.assertEqual(self.check()["exact_parameter_matches"], 36)

    def test_duplicate_native_pass_rejected(self):
        self.rows[-1]["Pass"] = self.rows[0]["Pass"]
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.check()

    def test_profit_mismatch_rejected(self):
        self.rows[10]["Profit"] += .03
        with self.assertRaisesRegex(ValueError, "profit"):
            self.check()

    def test_trade_mismatch_rejected(self):
        self.rows[10]["Trades"] += 1
        with self.assertRaisesRegex(ValueError, "trade"):
            self.check()

    def test_drawdown_mismatch_rejected(self):
        self.rows[10]["Equity DD %"] += .001
        with self.assertRaisesRegex(ValueError, "drawdown"):
            self.check()

    def test_parameter_mismatch_rejected(self):
        self.rows[10]["InpStopLossATRMul"] += .5
        with self.assertRaisesRegex(ValueError, "inputs"):
            self.check()

    def test_nonfinite_native_value_rejected(self):
        self.rows[10]["Profit"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            self.check()

    def test_tick_substitution_warning_rejected(self):
        (self.folder / "journal_0.txt").write_text("XAUUSD: generated ticks substituted", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "tick-quality"):
            self.check()

    def test_negative_native_index_rejected(self):
        self.rows[3]["InpTPGridIndex"] = -1
        with self.assertRaisesRegex(ValueError, "out of range"):
            self.check()
