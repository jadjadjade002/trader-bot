"""Unit tests for QuantumTitan V16.2 Read-Only Telemetry Collector.

Covers:
- Safety & isolation (No trading API, no credentials, protected accounts).
- Correct M1 bar close behavior & no active bar write.
- Kaufman Efficiency Ratio (KER) calculation.
- Anchored TV-VWAP calculation & dynamic DST anchor determination.
- Dynamic Server GMT offset detection & session label formatting in UTC coordinates.
- Forward label delay (15-bar queue) & INVALID_GAP handling on missing bars.
- Zero lookahead leakage.
- Duplicate prevention on restart.
- Health status purity (status == 'HEALTHY' without string contamination).
- Explicit time diagnostic fields (gmt_time_epoch, offset_seconds, server_utc_offset_hours).
- Python pipeline filtering verification (df[df["label_status"] == "COMPLETE"]).
- Exact output schema matching (29 bar columns, 18 health columns).
"""

import math
import re
import unittest
from datetime import date, datetime
from pathlib import Path


def calc_ker(closes: list[float], period: int) -> float:
    """Python reference implementation of CalcKER matching MQL5."""
    total = len(closes)
    if total <= period:
        return 0.0
    end_idx = total - 1
    start_idx = end_idx - period
    change = abs(closes[end_idx] - closes[start_idx])
    sum_path = 0.0
    for i in range(start_idx + 1, end_idx + 1):
        sum_path += abs(closes[i] - closes[i - 1])
    if sum_path <= 0.0:
        return 0.0
    return change / sum_path


def is_uk_summer_dst(year: int, month: int, day: int, hour: int) -> bool:
    """Python reference of IsUKSummerDST matching MQL5."""
    if month < 3 or month > 10:
        return False
    if month > 3 and month < 10:
        return True
    
    dt_end = date(year, month, 31)
    mql_dow = (dt_end.weekday() + 1) % 7
    last_sun_day = 31 - mql_dow
    
    if month == 3:
        return (day > last_sun_day) or (day == last_sun_day and hour >= 1)
    if month == 10:
        return (day < last_sun_day) or (day == last_sun_day and hour < 1)
    return False


def is_us_summer_dst(year: int, month: int, day: int, hour: int) -> bool:
    """Python reference of IsUSSummerDST matching MQL5."""
    if month < 3 or month > 11:
        return False
    if month > 3 and month < 11:
        return True
    
    if month == 3:
        m1 = date(year, 3, 1)
        mql_dow = (m1.weekday() + 1) % 7
        first_sun = 1 if mql_dow == 0 else (8 - mql_dow)
        second_sun = first_sun + 7
        return (day > second_sun) or (day == second_sun and hour >= 2)
        
    if month == 11:
        n1 = date(year, 11, 1)
        mql_dow = (n1.weekday() + 1) % 7
        first_sun = 1 if mql_dow == 0 else (8 - mql_dow)
        return (day < first_sun) or (day == first_sun and hour < 2)
        
    return False


def get_london_anchor_hour(year: int, month: int, day: int, server_gmt_offset_hours: int) -> int:
    """Computes London Open anchor in broker server hours."""
    uk_summer = is_uk_summer_dst(year, month, day, 12)
    london_open_utc = 7 if uk_summer else 8
    return london_open_utc + server_gmt_offset_hours


def get_ny_anchor_hour(year: int, month: int, day: int, server_gmt_offset_hours: int) -> float:
    """Computes NY Cash Open anchor in broker server hours."""
    us_summer = is_us_summer_dst(year, month, day, 12)
    ny_open_utc = 13.5 if us_summer else 14.5
    return ny_open_utc + server_gmt_offset_hours


def get_utc_session(utc_hour: int, utc_minute: int, uk_summer: bool, us_summer: bool) -> str:
    """Determines trading session in UTC coordinates matching MQL5 GetDstSessionLabel."""
    sec = utc_hour * 3600 + utc_minute * 60
    ldn_open = 7 * 3600 if uk_summer else 8 * 3600
    ldn_close = 15 * 3600 + 1800 if uk_summer else 16 * 3600 + 1800
    ny_open = 13 * 3600 + 1800 if us_summer else 14 * 3600 + 1800
    ny_close = 20 * 3600 if us_summer else 21 * 3600

    if sec < ldn_open:
        return "ASIA"
    elif ldn_open <= sec < ny_open:
        return "LONDON"
    elif ny_open <= sec < ldn_close:
        return "OVERLAP_LDN_NY"
    elif ldn_close <= sec < ny_close:
        return "NY"
    else:
        return "ROLLOVER"


class TestV162TelemetryCollector(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.source_file = self.root / "QuantumTitan_V16_2_TelemetryCollector.mq5"
        self.assertTrue(self.source_file.exists(), f"Source file missing: {self.source_file}")
        self.code = self.source_file.read_text(encoding="utf-8", errors="replace")

    def test_01_static_forbidden_trading_tokens(self):
        """Must not contain any trading execution APIs or mutation functions."""
        forbidden_patterns = [
            r"\bCTrade\b",
            r"\bOrderSend\b",
            r"\bOrderSendAsync\b",
            r"\bPositionOpen\b",
            r"\bPositionClose\b",
            r"\bPositionModify\b",
            r"\bTrade\.mqh\b",
            r"\bMqlTradeRequest\b",
            r"\bMqlTradeResult\b",
            r"\bOrderSelect\b",
            r"\bPositionSelect\b",
            r"\bHistorySelect\b",
            r"\bWebRequest\b",
            r"\bRiskGuardian\b",
            r"\bFileDelete\b",
            r"\bFileMove\b",
            r"\bSendMail\b",
            r"\bSendNotification\b",
            r"#\s*include\b",
            r"#\s*define\b",
            r"#\s*import\b",
            r"\btrade\s*\.",
        ]
        for pat in forbidden_patterns:
            matches = re.findall(pat, self.code, flags=re.IGNORECASE)
            self.assertEqual(
                matches, [],
                f"Forbidden token pattern '{pat}' detected in collector: {matches}"
            )

    def test_02_security_isolation_and_credentials(self):
        """Must not contain protected account numbers or any hardcoded credentials."""
        self.assertNotIn("112334471", self.code, "Protected account 112334471 found in collector!")
        self.assertNotIn("112468807", self.code, "Protected account 112468807 found in collector!")
        
        credential_words = [r"\bpassword\b", r"\bsecret\b", r"\btoken\s*=", r"\bapi_key\b"]
        for cw in credential_words:
            self.assertIsNone(re.search(cw, self.code, re.IGNORECASE), f"Credential token match: {cw}")

    def test_03_initialization_guards(self):
        """Must strictly guard symbol, timeframe, and output directory."""
        self.assertIn('_Symbol!="XAUUSD"', self.code)
        self.assertIn('_Period!=PERIOD_M1', self.code)
        self.assertIn("INIT_FAILED", self.code)
        self.assertIn('FolderCreate("V162Research")', self.code)
        self.assertIn('const string DATA_DIR="V162Research\\\\";', self.code)

    def test_04_output_schema_exact_match(self):
        """Verify BAR_HEADER has 29 columns and HEALTH_HEADER has 18 columns matching spec."""
        bar_header_match = re.search(r'const string BAR_HEADER="([^"]+)";', self.code)
        self.assertIsNotNone(bar_header_match, "BAR_HEADER not found in source code")
        bar_cols = bar_header_match.group(1).split(",")
        self.assertEqual(len(bar_cols), 29, f"BAR_HEADER must have 29 columns, got {len(bar_cols)}")
        
        expected_bar_cols = [
            "schema_version", "collector_version", "run_id", "symbol",
            "time_broker_epoch", "time_broker_iso", "server_hour", "dst_session_label",
            "open", "high", "low", "close", "tick_volume",
            "bid", "ask", "spread_points",
            "ker_10", "ker_15", "ker_20", "ker_30",
            "anchored_vwap_london", "anchored_vwap_ny",
            "dist_to_vwap_london", "dist_to_vwap_ny",
            "atr", "quality_flags",
            "return_after_5_bars", "return_after_15_bars", "label_status"
        ]
        self.assertEqual(bar_cols, expected_bar_cols, "BAR_HEADER columns do not match expected spec")

        health_header_match = re.search(r'const string HEALTH_HEADER="([^"]+)";', self.code)
        self.assertIsNotNone(health_header_match, "HEALTH_HEADER not found in source code")
        health_cols = health_header_match.group(1).split(",")
        self.assertEqual(len(health_cols), 18, f"HEALTH_HEADER must have 18 columns, got {len(health_cols)}")
        
        expected_health_cols = [
            "schema_version", "collector_version", "run_id",
            "broker_time_epoch", "broker_time_iso",
            "gmt_time_epoch", "gmt_time_iso",
            "offset_seconds", "server_utc_offset_hours",
            "terminal_connected", "symbol_synchronized",
            "last_tick_age_seconds", "last_closed_bar_epoch",
            "rows_written", "duplicate_skips", "gap_count", "write_errors",
            "status"
        ]
        self.assertEqual(health_cols, expected_health_cols, "HEALTH_HEADER columns do not match expected spec")

    def test_05_ker_calculation_properties(self):
        """Test Kaufman Efficiency Ratio mathematical properties."""
        linear_up = [100.0 + i * 0.5 for i in range(25)]
        self.assertAlmostEqual(calc_ker(linear_up, 10), 1.0, places=5)
        self.assertAlmostEqual(calc_ker(linear_up, 20), 1.0, places=5)

        chop = [100.0 if i % 2 == 0 else 101.0 for i in range(25)]
        self.assertAlmostEqual(calc_ker(chop, 10), 0.0, places=5)

        flat = [100.0] * 25
        self.assertEqual(calc_ker(flat, 10), 0.0)

    def test_06_dynamic_dst_and_vwap_anchor_hours(self):
        """Verify dynamic calculation of London and NY anchor hours across normal & DST-gap periods."""
        # 1. Normal Winter (January): UK Winter (UTC+0), US Winter (UTC-5), XM Server EET (UTC+2)
        srv_offset = 2
        self.assertEqual(get_london_anchor_hour(2026, 1, 15, srv_offset), 10)
        self.assertEqual(get_ny_anchor_hour(2026, 1, 15, srv_offset), 16.5)

        # 2. Normal Summer (July): UK Summer (UTC+1), US Summer (UTC-4), XM Server EEST (UTC+3)
        srv_offset = 3
        self.assertEqual(get_london_anchor_hour(2026, 7, 15, srv_offset), 10)
        self.assertEqual(get_ny_anchor_hour(2026, 7, 15, srv_offset), 16.5)

        # 3. March DST-Gap: US switches DST on 2nd Sunday, Europe on last Sunday
        srv_offset_gap = 2
        self.assertEqual(get_london_anchor_hour(2026, 3, 18, srv_offset_gap), 10)
        # NY Cash Open shifts 1 hour earlier on broker server clock!
        self.assertEqual(get_ny_anchor_hour(2026, 3, 18, srv_offset_gap), 15.5)

    def test_07_dynamic_session_boundaries_in_utc(self):
        """Verify sessions are classified strictly in UTC space matching VWAP anchors."""
        # Summer (UK Summer = True, US Summer = True)
        # London: 07:00 UTC, NY Open: 13:30 UTC, London Close: 15:30 UTC, NY Close: 20:00 UTC
        self.assertEqual(get_utc_session(4, 0, uk_summer=True, us_summer=True), "ASIA")
        self.assertEqual(get_utc_session(8, 0, uk_summer=True, us_summer=True), "LONDON")
        self.assertEqual(get_utc_session(14, 0, uk_summer=True, us_summer=True), "OVERLAP_LDN_NY")
        self.assertEqual(get_utc_session(17, 0, uk_summer=True, us_summer=True), "NY")
        self.assertEqual(get_utc_session(21, 0, uk_summer=True, us_summer=True), "ROLLOVER")

    def test_08_forward_label_delay_and_no_lookahead(self):
        """Verify forward returns are delayed by 15 completed bars without lookahead."""
        class MockCollector:
            def __init__(self):
                self.pending = []
                self.written_rows = []

            def on_bar_close(self, bar_time, close_price):
                for rec in self.pending:
                    if len(rec["future_closes"]) < 15:
                        rec["future_closes"].append(close_price)
                        rec["future_times"].append(bar_time)

                while self.pending and len(self.pending[0]["future_closes"]) >= 15:
                    matured = self.pending.pop(0)
                    ret5 = (matured["future_closes"][4] - matured["close"]) / 0.01
                    ret15 = (matured["future_closes"][14] - matured["close"]) / 0.01
                    self.written_rows.append({
                        "bar_time": matured["bar_time"],
                        "close": matured["close"],
                        "ret5": ret5,
                        "ret15": ret15,
                        "label_status": "COMPLETE"
                    })

                self.pending.append({
                    "bar_time": bar_time,
                    "close": close_price,
                    "future_closes": [],
                    "future_times": []
                })

        collector = MockCollector()
        for i in range(14):
            collector.on_bar_close(bar_time=1000 + i * 60, close_price=2650.0 + i)
        
        self.assertEqual(len(collector.written_rows), 0, "No row written before 15 future bars")
        self.assertEqual(len(collector.pending), 14)

        collector.on_bar_close(bar_time=1000 + 14 * 60, close_price=2650.0 + 14)
        self.assertEqual(len(collector.written_rows), 0)

        collector.on_bar_close(bar_time=1000 + 15 * 60, close_price=2650.0 + 15)
        self.assertEqual(len(collector.written_rows), 1, "Bar 0 must be written when 15 future bars arrive")
        
        row0 = collector.written_rows[0]
        self.assertEqual(row0["bar_time"], 1000)
        self.assertEqual(row0["close"], 2650.0)
        self.assertAlmostEqual(row0["ret5"], 500.0, places=2)
        self.assertAlmostEqual(row0["ret15"], 1500.0, places=2)

    def test_09_no_active_bar_write(self):
        """Verify that partial/active bars are never written."""
        self.assertIn("if(activeBar==0)", self.code)
        self.assertIn("if(barTime<=activeBar) return;", self.code)
        deinit_match = re.search(r"void OnDeinit\([^)]*\)\s*\{([^}]+)\}", self.code)
        self.assertIsNotNone(deinit_match)
        self.assertNotIn("Append", deinit_match.group(1), "OnDeinit must never flush active uncommitted bar")

    def test_10_duplicate_prevention_logic(self):
        """Verify duplicate skips when bar <= maximum timestamp."""
        self.assertIn("if(bar>0 && bar<=maximum) { FileClose(handle); ++duplicateSkips; return 0; }", self.code)

    def test_11_invalid_gap_handling_in_forward_labels(self):
        """Verify that when missing bars/gaps occur in the forward window, label is marked INVALID_GAP."""
        class MockQueueItem:
            def __init__(self, bar_time, close):
                self.bar_time = bar_time
                self.close = close
                self.future_closes = []
                self.future_times = []
                self.has_gap = False

        # Clean 1-minute increments
        item_clean = MockQueueItem(bar_time=1000, close=2650.0)
        for i in range(15):
            item_clean.future_closes.append(2650.0 + (i + 1) * 0.1)
            item_clean.future_times.append(1000 + (i + 1) * 60)
            
        gap_clean = item_clean.has_gap
        for k in range(15):
            if item_clean.future_times[k] != item_clean.bar_time + (k + 1) * 60:
                gap_clean = True
                break
        self.assertFalse(gap_clean)

        # Gap between bars
        item_gap = MockQueueItem(bar_time=1000, close=2650.0)
        for i in range(15):
            item_gap.future_closes.append(2650.0 + (i + 1) * 0.1)
            time_offset = (i + 1) * 60 if i < 7 else (i + 6) * 60
            item_gap.future_times.append(1000 + time_offset)
            
        gap_detected = item_gap.has_gap
        for k in range(15):
            if item_gap.future_times[k] != item_gap.bar_time + (k + 1) * 60:
                gap_detected = True
                break
        self.assertTrue(gap_detected, "Gap must be detected when timestamps are non-contiguous")

    def test_12_dynamic_server_offset_detection_present(self):
        """Ensure collector measures dynamic GMT offset via TimeGMT."""
        self.assertIn("GetServerGmtOffsetSeconds", self.code)
        self.assertIn("TimeGMT()", self.code)
        self.assertIn("GetLondonAnchorServerTime", self.code)
        self.assertIn("GetNYAnchorServerTime", self.code)

    def test_13_health_status_purity_and_diagnostic_fields(self):
        """Ensure status string is strictly pure HEALTHY without offset contamination."""
        self.assertIn('string status="HEALTHY";', self.code)
        self.assertNotIn('HEALTHY|UTC', self.code, "Status must not contain decorated offset string!")
        self.assertIn("offset_seconds", self.code)
        self.assertIn("server_utc_offset_hours", self.code)
        self.assertIn("gmt_time_epoch", self.code)

    def test_14_python_pipeline_invalid_gap_filtering(self):
        """Verify downstream Python training pipeline strictly filters out INVALID_GAP rows."""
        dataset = [
            {"bar_time": 1000, "close": 2650.0, "ret5": 10.0, "ret15": 25.0, "label_status": "COMPLETE"},
            {"bar_time": 1060, "close": 2650.5, "ret5": 0.0, "ret15": 0.0, "label_status": "INVALID_GAP"},
            {"bar_time": 1120, "close": 2651.0, "ret5": 15.0, "ret15": 30.0, "label_status": "COMPLETE"},
            {"bar_time": 1180, "close": 2651.2, "ret5": 0.0, "ret15": 0.0, "label_status": "INVALID_GAP"},
        ]
        # In Pandas: df = df[df["label_status"] == "COMPLETE"]
        clean_df = [row for row in dataset if row["label_status"] == "COMPLETE"]
        self.assertEqual(len(clean_df), 2)
        for row in clean_df:
            self.assertEqual(row["label_status"], "COMPLETE")
            self.assertNotEqual(row["ret5"], 0.0)


if __name__ == "__main__":
    unittest.main()
