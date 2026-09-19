"""Tests for V21 daily report helper functions."""

import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path

from research.v21_dataset_audit import HEADER, audit as audit_func
from research.v21_decision import decision
from research.v21_daily_report import main as daily_report_main


def _session_day(moment: datetime) -> datetime.date:
    """Broker session 18:00..01:56 belongs to the date on which it starts."""
    return moment.date() if moment.hour >= 18 else (moment - timedelta(days=1)).date()


def _make_row(epoch: int, iso: str, close: float = 100.0) -> dict[str, str]:
    return dict(zip(HEADER, [
        "1", "2.00", "FWD_20260909_4W", "XAUUSD", str(epoch), iso,
        "100", "101", "99", str(close), "10", "0", "20", "21",
        "100", "100.2", str(epoch * 1000), str(epoch * 1000 + 59000), "OK",
    ]))


class V21DailyReportTestFunctions(unittest.TestCase):
    def test_session_day_midnight_crossing(self) -> None:
        # 23:40 belongs to the date on which it starts (Sep 9)
        sd = _session_day(datetime(2026, 9, 9, 23, 40))
        self.assertEqual(sd, datetime(2026, 9, 9).date())

    def test_session_day_before_midnight(self) -> None:
        # 18:00 belongs to the date on which it starts
        sd = _session_day(datetime(2026, 9, 9, 18, 0))
        self.assertEqual(sd, datetime(2026, 9, 9).date())

    def test_audit_accepts_forward_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            base = int(datetime(2026, 9, 9, 0, 1).timestamp())
            with open(directory / "QTForward_XAUUSD_M1_20260909.csv", "w", newline="", encoding="utf-8") as f:
                f.write("schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,real_volume,bar_spread_points,open_spread_points,open_bid,open_ask,open_tick_time_msc,close_observed_time_msc,flags\n")
                f.write("1,2.00,FWD_20260909_4W,XAUUSD," + str(base) + ",2026-09-09T00:01:00,100,101,99,100.0,10,0,20,21,100,100.2," + str(base * 1000) + "," + str(base * 1000 + 59000) + ",OK\n")
            result = audit_func([directory])
            self.assertEqual(result["rows"], 1)

    def test_decision_small_dataset(self) -> None:
        # Use M1-aligned timestamp: epoch must be multiple of 60, ISO second must be 0
        aligned_epoch = 1788985440  # 2026-09-09T20:24:00 M1-aligned
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with open(root / "QTForward_XAUUSD_M1_20260909.csv", "w", newline="", encoding="utf-8") as f:
                f.write("schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,real_volume,bar_spread_points,open_spread_points,open_bid,open_ask,open_tick_time_msc,close_observed_time_msc,flags\n")
                f.write("1,2.00,FWD_20260909_4W,XAUUSD," + str(aligned_epoch) + ",2026-09-09T20:24:00,100,101,99,100.0,10,0,20,21,100,100.2," + str(aligned_epoch * 1000) + "," + str(aligned_epoch * 1000 + 59000) + ",OK\n")
            dec = decision([root])
            self.assertIn("status", dec)

    def test_daily_report_main_outputs_incomplete_status_and_health(self) -> None:
        aligned_epoch = 1788985440  # 2026-09-09T20:24:00 M1-aligned
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with open(root / "QTForward_XAUUSD_M1_20260909.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADER)
                writer.writeheader()
                writer.writerow(_make_row(aligned_epoch, "2026-09-09T20:24:00"))
            with open(root / "QTForward_health_20260909.csv", "w", newline="", encoding="utf-8") as f:
                f.write("terminal_connected,symbol_synchronized,write_errors,duplicate_skips,gap_count,status\n")
                f.write("1,1,0,0,120,HEALTHY\n")

            old_argv = sys.argv
            sys.argv = ["v21_daily_report.py", str(root)]
            try:
                output = io.StringIO()
                with redirect_stdout(output):
                    rc = daily_report_main()
            finally:
                sys.argv = old_argv

            self.assertEqual(rc, 0)
            text = output.getvalue()
            self.assertIn("INCONCLUSIVE_ACQUISITION_INCOMPLETE", text)
            self.assertIn("HEALTHY", text)
            self.assertIn("2026-09-09T20:24:00", text)


if __name__ == "__main__":
    unittest.main()
