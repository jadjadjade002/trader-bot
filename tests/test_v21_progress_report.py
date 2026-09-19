"""Unit tests for V21 Progress Report."""

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from research.v21_progress_report import (
    ALLOWED_HEALTH_LAG_SECONDS,
    EXPECTED_BAR_HEADER,
    EXPECTED_HEALTH_HEADER,
    TARGET_ROWS,
    TARGET_SESSIONS,
    HealthRow,
    build_full_report,
    evaluate_acquisition_gate,
    session_date_from_dt,
    session_date_from_iso,
)


def _make_bar_line(
    epoch: int,
    iso_str: str,
    o: float = 2500.0,
    h: float = 2505.0,
    l: float = 2495.0,
    c: float = 2502.0,
    flags: str = "OK",
    run_id: str = "FWD_TEST",
    symbol: str = "XAUUSD",
) -> str:
    return f"1,2.00,{run_id},{symbol},{epoch},{iso_str},{o},{h},{l},{c},10,0,10,12,2500.0,2500.2,100,200,{flags}\n"


def _make_health_line(
    epoch: int,
    iso_str: str,
    last_bar_epoch: int,
    status: str = "HEALTHY",
    write_errors: int = 0,
    duplicate_skips: int = 0,
    gap_count: int = 0,
    rows_written: int = 100,
) -> str:
    return f"1,2.00,FWD_TEST,{epoch},{iso_str},1,1,0,{last_bar_epoch},{rows_written},{duplicate_skips},{gap_count},{write_errors},{status}\n"


class TestV21ProgressReport(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_no_data(self):
        rep = build_full_report(self.dir)
        self.assertEqual(rep["acquisition_gate"]["status"], "NO_DATA")
        self.assertEqual(rep["bars"]["valid"], 0)
        self.assertEqual(rep["deployment_gate"]["status"], "BLOCKED")
        self.assertFalse(rep["deployment_gate"]["promotion"])

    def test_header_is_not_counted_and_multiple_daily_files(self):
        f1 = self.dir / "QTForward_XAUUSD_M1_20260909.csv"
        f2 = self.dir / "QTForward_XAUUSD_M1_20260910.csv"

        f1.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1788990000, "2026-09-09T20:00:00") +
            _make_bar_line(1788990060, "2026-09-09T20:01:00")
        )
        f2.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1788990120, "2026-09-10T02:00:00")
        )

        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(
            ",".join(EXPECTED_HEALTH_HEADER) + "\n" +
            _make_health_line(1788990125, "2026-09-10T02:00:05", 1788990120)
        )

        rep = build_full_report(self.dir)
        self.assertEqual(rep["bars"]["valid"], 3)
        self.assertEqual(rep["files"]["bar_count"], 2)

    def test_session_boundary_1759_and_1800(self):
        dt_1759 = datetime.fromisoformat("2026-09-09T17:59:59")
        dt_1800 = datetime.fromisoformat("2026-09-09T18:00:00")
        dt_midnight = datetime.fromisoformat("2026-09-10T00:00:00")
        dt_morning = datetime.fromisoformat("2026-09-10T06:16:00")

        self.assertEqual(session_date_from_dt(dt_1759), date(2026, 9, 8))
        self.assertEqual(session_date_from_dt(dt_1800), date(2026, 9, 9))
        self.assertEqual(session_date_from_dt(dt_midnight), date(2026, 9, 9))
        self.assertEqual(session_date_from_dt(dt_morning), date(2026, 9, 9))

    def test_latest_health_is_selected_by_timestamp_across_files(self):
        # File 1 has old timestamp
        h1 = self.dir / "QTForward_health_20260909.csv"
        h1.write_text(
            ",".join(EXPECTED_HEALTH_HEADER) + "\n" +
            _make_health_line(1000, "2026-09-09T10:00:00", 940, status="STALE_TICKS")
        )
        # File 2 has new timestamp
        h2 = self.dir / "QTForward_health_20260910.csv"
        h2.write_text(
            ",".join(EXPECTED_HEALTH_HEADER) + "\n" +
            _make_health_line(2000, "2026-09-10T10:00:00", 1980, status="HEALTHY", gap_count=120)
        )

        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1980, "2026-09-10T10:00:00")
        )

        rep = build_full_report(self.dir)
        self.assertIsNotNone(rep["health"])
        self.assertEqual(rep["health"]["status"], "HEALTHY")
        self.assertEqual(rep["health"]["gap_count"], 120)
        self.assertEqual(rep["health"]["broker_time_epoch"], 2000)

    def test_malformed_bar_is_reported_not_crashed(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1000, "2026-09-10T10:00:00") +
            "bad,row,with,missing,fields\n" +
            _make_bar_line(1060, "2026-09-10T10:01:00")
        )
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1100, "2026-09-10T10:01:05", 1060))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["bars"]["valid"], 2)
        self.assertEqual(rep["bars"]["malformed"], 1)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")

    def test_invalid_ohlc_is_blocked(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        # High < Open -> Invalid
        f.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1000, "2026-09-10T10:00:00", o=2500.0, h=2490.0, l=2480.0, c=2485.0)
        )
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1100, "2026-09-10T10:01:05", 1000))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["bars"]["invalid_ohlc"], 1)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")

    def test_write_error_and_duplicate_skip_block_gate(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + _make_bar_line(1000, "2026-09-10T10:00:00"))
        
        # Test write_errors > 0
        h1 = self.dir / "QTForward_health_20260910.csv"
        h1.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1100, "2026-09-10T10:01:05", 1000, write_errors=1))
        rep1 = build_full_report(self.dir)
        self.assertEqual(rep1["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")

        # Test duplicate_skips > 0
        h1.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1100, "2026-09-10T10:01:05", 1000, duplicate_skips=1))
        rep2 = build_full_report(self.dir)
        self.assertEqual(rep2["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")

    def test_missing_bar_header(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        # Missing 'flags' column in header
        bad_header = [col for col in EXPECTED_BAR_HEADER if col != "flags"]
        f.write_text(",".join(bad_header) + "\n" + "1,2.00,FWD_TEST,XAUUSD,1000,2026-09-10T10:00:00,2500,2505,2495,2502,10,0,10,12,2500,2500.2,100,200\n")
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1005, "2026-09-10T10:00:05", 1000))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
        self.assertTrue(any(e.get("code") == "BAD_HEADER" for e in rep["errors"]))

    def test_extra_bar_header(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        extra_header = list(EXPECTED_BAR_HEADER) + ["extra_column"]
        f.write_text(",".join(extra_header) + "\n" + _make_bar_line(1000, "2026-09-10T10:00:00").strip() + ",extra_val\n")
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1005, "2026-09-10T10:00:05", 1000))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
        self.assertTrue(any(e.get("code") == "BAD_HEADER" for e in rep["errors"]))

    def test_missing_health_field(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + _make_bar_line(1000, "2026-09-10T10:00:00"))
        # Health header missing 'status'
        bad_h_header = [col for col in EXPECTED_HEALTH_HEADER if col != "status"]
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(bad_h_header) + "\n" + "1,2.00,FWD_TEST,1005,2026-09-10T10:00:05,1,1,0,1000,100,0,0,0\n")

        rep = build_full_report(self.dir)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
        self.assertTrue(any(e.get("code") == "BAD_HEADER" for e in rep["errors"]))

    def test_malformed_health_numeric_value(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + _make_bar_line(1000, "2026-09-10T10:00:00"))
        h = self.dir / "QTForward_health_20260910.csv"
        # NaN in write_errors
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + "1,2.00,FWD_TEST,1005,2026-09-10T10:00:05,1,1,0,1000,100,0,0,NaN,HEALTHY\n")

        rep = build_full_report(self.dir)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
        self.assertTrue(any(e.get("code") == "HEALTH_PARSE_ERROR" for e in rep["errors"]))

    def test_exact_360_second_heartbeat_lag_is_not_blocked(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        # Bar epoch 1360
        f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + _make_bar_line(1360, "2026-09-10T10:00:00"))
        # Last closed bar in health is 1000 -> lag = 360s exactly == limit -> allowed
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1050, "2026-09-10T09:50:00", 1000))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["bars"]["bar_health_lag_seconds"], 360)
        self.assertEqual(rep["acquisition_gate"]["status"], "COLLECTING")

    def test_lag_greater_than_360_seconds_is_blocked(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        # Bar epoch 1361
        f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + _make_bar_line(1361, "2026-09-10T10:00:00"))
        # Last closed bar in health is 1000 -> lag = 361s > 360s -> blocked
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1050, "2026-09-10T09:50:00", 1000))

        rep = build_full_report(self.dir)
        self.assertEqual(rep["bars"]["bar_health_lag_seconds"], 361)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")

    def test_non_monotonic_timestamp_blocks_gate(self):
        f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
        f.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(1060, "2026-09-10T10:01:00") +
            _make_bar_line(1000, "2026-09-10T10:00:00")
        )
        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1100, "2026-09-10T10:01:05", 1000))

        rep = build_full_report(self.dir)
        self.assertGreater(rep["bars"]["non_monotonic"], 0)
        self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
        self.assertIn("non_monotonic_timestamp", rep["acquisition_gate"]["reasons"])

    def test_non_finite_numeric_bar_fields_rejected(self):
        fields_to_test = [
            "tick_volume",
            "real_volume",
            "bar_spread_points",
            "open_spread_points",
            "open_bid",
            "open_ask",
            "open_tick_time_msc",
            "close_observed_time_msc",
        ]
        non_finite_values = ["NaN", "+inf", "-inf"]

        base_row = {
            "schema_version": "1",
            "collector_version": "2.00",
            "run_id": "FWD_TEST",
            "symbol": "XAUUSD",
            "time_broker_epoch": "1000",
            "time_broker_iso": "2026-09-10T10:00:00",
            "open": "2500.0",
            "high": "2505.0",
            "low": "2495.0",
            "close": "2502.0",
            "tick_volume": "10",
            "real_volume": "0",
            "bar_spread_points": "10",
            "open_spread_points": "12",
            "open_bid": "2500.0",
            "open_ask": "2500.2",
            "open_tick_time_msc": "100",
            "close_observed_time_msc": "200",
            "flags": "OK",
        }

        h = self.dir / "QTForward_health_20260910.csv"
        h.write_text(",".join(EXPECTED_HEALTH_HEADER) + "\n" + _make_health_line(1005, "2026-09-10T10:00:05", 1000))

        for field in fields_to_test:
            for val in non_finite_values:
                with self.subTest(field=field, val=val):
                    f = self.dir / "QTForward_XAUUSD_M1_20260910.csv"
                    row = dict(base_row)
                    row[field] = val
                    line = ",".join(row[c] for c in EXPECTED_BAR_HEADER) + "\n"
                    f.write_text(",".join(EXPECTED_BAR_HEADER) + "\n" + line)

                    rep = build_full_report(self.dir)
                    self.assertEqual(rep["bars"]["malformed"], 1, f"Failed to mark malformed for {field}={val}")
                    self.assertEqual(rep["acquisition_gate"]["status"], "DATA_QUALITY_BLOCKED")
                    self.assertTrue(any("malformed_rows=1" in r for r in rep["acquisition_gate"]["reasons"]))

    def test_weekend_market_idle_uses_last_active_health_for_data_quality(self):
        bars = self.dir / "QTForward_XAUUSD_M1_20260911.csv"
        bars.write_text(
            ",".join(EXPECTED_BAR_HEADER) + "\n" +
            _make_bar_line(2000, "2026-09-11T22:58:00")
        )
        health = self.dir / "QTForward_health_20260913.csv"
        health.write_text(
            ",".join(EXPECTED_HEALTH_HEADER) + "\n" +
            _make_health_line(2060, "2026-09-11T22:59:00", 2000, status="HEALTHY") +
            _make_health_line(2360, "2026-09-11T23:04:00", 2000, status="STALE_TICKS") +
            _make_health_line(999999, "2026-09-13T18:35:00", 0, status="MARKET_IDLE", rows_written=0)
        )

        rep = build_full_report(self.dir)
        self.assertEqual(rep["health"]["status"], "MARKET_IDLE")
        self.assertTrue(rep["health"]["current_market_idle"])
        self.assertEqual(rep["health"]["data_quality_basis_status"], "HEALTHY")
        self.assertEqual(rep["bars"]["bar_health_lag_seconds"], 0)
        self.assertEqual(rep["acquisition_gate"]["status"], "COLLECTING")

    def test_json_output_is_serializable(self):
        rep = build_full_report(self.dir)
        dumped = json.dumps(rep)
        loaded = json.loads(dumped)
        self.assertEqual(loaded["study"], "v21_forward_observational_research")


if __name__ == "__main__":
    unittest.main()
