import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from research.v21_dataset_audit import HEADER
from research.v21_decision import decision


def record(moment: datetime, close: float) -> dict[str, str]:
    epoch = int(moment.timestamp())
    return dict(zip(HEADER, [
        "1", "2.00", "FWD_20260909_4W", "XAUUSD", str(epoch), moment.isoformat(),
        str(close), str(close + 1), str(close - 1), str(close), "10", "0", "20", "21",
        str(close), str(close + .2), str(epoch * 1000), str(epoch * 1000 + 59000), "OK",
    ]))


class V21DecisionTests(unittest.TestCase):
    def test_partial_study_is_explicitly_inconclusive_and_never_promoted(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            start = datetime(2026, 9, 9, 18)
            with (root / "QTForward_XAUUSD_M1_20260909.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()
                writer.writerows(record(start + timedelta(minutes=index), 100 + index) for index in range(40))
            result = decision([root])
        self.assertEqual(result["status"], "INCONCLUSIVE_ACQUISITION_INCOMPLETE")
        self.assertFalse(result["promotion"])
        self.assertFalse(result["gates"]["minimum_probes"])

    def test_session_after_midnight_is_assigned_to_start_date(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            start = datetime(2026, 9, 9, 23, 40)
            with (root / "QTForward_XAUUSD_M1_20260909.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()
                writer.writerows(record(start + timedelta(minutes=index), 100 + index) for index in range(80))
            result = decision([root])
        self.assertEqual(result["broker_session_dates"], ["2026-09-09"])
