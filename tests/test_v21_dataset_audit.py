import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from research.v21_dataset_audit import AuditError, HEADER, audit


def row(epoch: int, stamp: str) -> dict[str, str]:
    return dict(zip(HEADER, [
        "1", "2.00", "FWD_20260909_4W", "XAUUSD", str(epoch), stamp,
        "100", "101", "99", "100.5", "10", "0", "20", "21", "100", "100.2",
        str(epoch * 1000), str(epoch * 1000 + 59000), "OK",
    ]))


class V21DatasetAuditTests(unittest.TestCase):
    def write_rows(self, directory: Path, rows: list[dict[str, str]]) -> None:
        with (directory / "QTForward_XAUUSD_M1_20260909.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(rows)

    def test_accepts_forward_rows_and_reports_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            base = int(datetime(2026, 9, 9, 0, 1).timestamp())
            self.write_rows(directory, [row(base, "2026-09-09T00:01:00"), row(base + 120, "2026-09-09T00:03:00")])
            result = audit([directory])
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["nonconsecutive_intervals"], 1)

    def test_rejects_pre_forward_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            base = int(datetime(2026, 9, 8, 23, 59).timestamp())
            self.write_rows(directory, [row(base, "2026-09-08T23:59:00")])
            with self.assertRaises(AuditError):
                audit([directory])

    def test_rejects_duplicate_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            base = int(datetime(2026, 9, 9, 0, 1).timestamp())
            self.write_rows(directory, [row(base, "2026-09-09T00:01:00"), row(base, "2026-09-09T00:01:00")])
            with self.assertRaises(AuditError):
                audit([directory])
