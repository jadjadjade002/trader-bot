"""Unit and regression tests for V16 Entry Parity Replay and Microsecond Trade Path Resolution."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from research.v16_entry_parity_replay import (
    POLICY_PRESETS,
    V16_CONDITION_MATRIX,
    evaluate_v16_macro_filters,
    load_and_validate_telemetry,
    parse_v16_live_deploy_log,
    resolve_trade_path,
    run_replay,
)


class TestV16EntryParityReplay(unittest.TestCase):

    def setUp(self):
        self.policy = POLICY_PRESETS["v16_live_20260910"]

    def test_condition_matrix_traceability(self):
        """Verifies that all conditions map to valid source lines and classify reconstructibility."""
        self.assertGreater(len(V16_CONDITION_MATRIX), 8)
        unreconstructible = [c for c in V16_CONDITION_MATRIX if not c.reconstructible_from_telemetry]
        self.assertTrue(any(c.condition_id == "COND_SETUP1_SMC_SWEEP" for c in unreconstructible))
        self.assertTrue(any(c.condition_id == "COND_SETUP2_TREND_RETEST_FVG" for c in unreconstructible))
        for c in unreconstructible:
            self.assertGreater(len(c.missing_fields), 0)

    def test_full_parity_unresolvable_without_m5_swing_fvg_account_news(self):
        """Regression test: Full parity is strictly unresolvable without M5/swing/FVG/account/news state."""
        matrix_dict = {c.condition_id: c for c in V16_CONDITION_MATRIX}

        # Daily loss requires live account equity
        self.assertFalse(matrix_dict["COND_DAILY_LOSS"].reconstructible_from_telemetry)
        self.assertIn("live_account_balance_equity", matrix_dict["COND_DAILY_LOSS"].missing_fields)

        # News filter requires MQL5 calendar state
        self.assertFalse(matrix_dict["COND_NEWS_LOCKOUT"].reconstructible_from_telemetry)
        self.assertIn("mql5_economic_calendar_events", matrix_dict["COND_NEWS_LOCKOUT"].missing_fields)

        # Concurrency & Cooldown require deal ledger state
        self.assertFalse(matrix_dict["COND_CONCURRENCY"].reconstructible_from_telemetry)
        self.assertFalse(matrix_dict["COND_COOLDOWN"].reconstructible_from_telemetry)
        self.assertFalse(matrix_dict["COND_LOSS_STREAK"].reconstructible_from_telemetry)

        # Setups require M5 HTF, swing lookback, FVG
        self.assertFalse(matrix_dict["COND_SETUP1_SMC_SWEEP"].reconstructible_from_telemetry)
        self.assertFalse(matrix_dict["COND_SETUP2_TREND_RETEST_FVG"].reconstructible_from_telemetry)

    def test_schema_version_and_malformed_header_rejection(self):
        """Verifies that invalid schema version or missing columns raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("schema_version,collector_version,run_id\n1,16.31,TEST\n")
            temp_path = Path(f.name)

        try:
            with self.assertRaises(ValueError) as ctx:
                load_and_validate_telemetry(temp_path)
            self.assertIn("Missing required fields", str(ctx.exception))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_reject_invalid_schema_version_number(self):
        """Rejects files where schema_version != 2."""
        header = (
            "schema_version,signal_bar_epoch,signal_bar_iso,entry_tick_time_msc,"
            "session_label,signal_side,signal_score,linreg_slope_current,ema_fast,"
            "ema_slow,rsi,atr_points,entry_bid,entry_ask,entry_spread_points,"
            "label_status,quality_flags,buy_mfe_points,buy_mae_points,"
            "sell_mfe_points,sell_mae_points\n"
        )
        row = "1,1789349400,2026-09-14T01:30:00,1789349460000,ASIA,BUY,10,1,100,90,50,150,4000,4000.5,50,COMPLETE,OK,100,50,50,100\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(header + row)
            temp_path = Path(f.name)

        try:
            with self.assertRaises(ValueError) as ctx:
                load_and_validate_telemetry(temp_path)
            self.assertIn("Invalid schema version", str(ctx.exception))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_path_resolution_tp_first(self):
        """TP occurs when favor level reached before adverse or BE recross."""
        row = {
            "buy_fav_180_msc": "1000",
            "buy_adv_260_msc": "2000",
            "buy_fav_85_msc": "500",
            "buy_be_t85_l15_recross_msc": "1500",
            "buy_mfe_points": "200",
            "buy_mae_points": "50",
        }
        outcome, pts, exit_msc, reason = resolve_trade_path(row, "BUY", self.policy)
        self.assertEqual(outcome, "TP")
        self.assertEqual(pts, 180.0)
        self.assertEqual(exit_msc, 1000)

    def test_path_resolution_sl_first(self):
        """Initial SL occurs when adverse level hit before BE trigger or TP."""
        row = {
            "buy_fav_180_msc": "5000",
            "buy_adv_260_msc": "1000",
            "buy_fav_85_msc": "2000",
            "buy_be_t85_l15_recross_msc": "",
            "buy_mfe_points": "50",
            "buy_mae_points": "260",
        }
        outcome, pts, exit_msc, reason = resolve_trade_path(row, "BUY", self.policy)
        self.assertEqual(outcome, "INITIAL_SL")
        self.assertEqual(pts, -260.0)
        self.assertEqual(exit_msc, 1000)

    def test_path_resolution_be_lock_and_recross(self):
        """BE occurs when BE trigger hit, then price pulls back to lock level before TP."""
        row = {
            "buy_fav_180_msc": "5000",
            "buy_adv_260_msc": "",
            "buy_fav_85_msc": "1000",
            "buy_be_t85_l15_recross_msc": "1500",
            "buy_mfe_points": "120",
            "buy_mae_points": "40",
        }
        outcome, pts, exit_msc, reason = resolve_trade_path(row, "BUY", self.policy)
        self.assertEqual(outcome, "BE")
        self.assertEqual(pts, 15.0)
        self.assertEqual(exit_msc, 1500)

    def test_path_resolution_timeout(self):
        """TIMEOUT occurs when no target levels hit within observation horizon."""
        row = {
            "sell_fav_180_msc": "",
            "sell_adv_260_msc": "",
            "sell_fav_85_msc": "",
            "sell_be_t85_l15_recross_msc": "",
            "sell_mfe_points": "45",
            "sell_mae_points": "30",
        }
        outcome, pts, exit_msc, reason = resolve_trade_path(row, "SELL", self.policy)
        self.assertEqual(outcome, "TIMEOUT")
        self.assertEqual(pts, 0.0)
        self.assertIsNone(exit_msc)

    def test_strict_fail_closed_mode(self):
        """Strict mode must mark 100% of rows as PARITY_UNRESOLVABLE due to missing M5/lookback data."""
        telemetry_file = Path("data/V16TickTelemetry_XAUUSD_M1_20260914.csv")
        if not telemetry_file.exists():
            self.skipTest("Telemetry data not found")

        report = run_replay(telemetry_file, mode="strict_fail_closed")
        self.assertEqual(report["telemetry_replay_results"]["parity_passed_rows"], 0)
        self.assertEqual(report["telemetry_audit"]["usable_complete_rows"], 154)
        self.assertEqual(report["limitations_and_verdict"]["verdict"], "RESEARCH_ONLY")

    def test_deploy_log_does_not_prove_tp_sl_be_pnl(self):
        """Regression test: Close/cooldown logs only confirm a close event, NOT TP/SL/BE/PnL."""
        deploy_log = Path("deploy/v16_20260910_mql5.log")
        if not deploy_log.exists():
            self.skipTest("Deploy log not found")

        trades = parse_v16_live_deploy_log(deploy_log)
        self.assertEqual(len(trades), 14)

        paired = [t for t in trades if t["match_status"] == "PAIRED_CLOSE_OBSERVED"]
        unmatched = [t for t in trades if t["match_status"] == "UNMATCHED"]

        self.assertEqual(len(paired), 13)
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["outcome"], "UNMATCHED_CLOSE")

        # All 13 paired trades are marked as unverified outcome with unproven PnL
        for t in paired:
            self.assertEqual(t["outcome"], "CLOSE_OBSERVED_UNVERIFIED")
            self.assertEqual(t["pnl_status"], "UNPROVEN_FROM_LOG")
            self.assertIsNone(t["realized_pts"])
            self.assertIn("unproven", t["notes"].lower())

        # BE arming is observable as an interim event
        be_armed_count = sum(1 for t in paired if t["be_locked"])
        self.assertEqual(be_armed_count, 11)

    def test_unpaired_lines_marked_unmatched(self):
        """Regression test: Unpaired open or close lines are explicitly recorded as UNMATCHED."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", encoding="utf-16le", delete=False) as f:
            # An open line without close, followed by an isolated close
            text = (
                "00:00:01.000 Core 1 [M1 Velocity] BUY SCALP OPENED @ 4000.00 | SL: 3990.00 (-100 pts) | TP: 4010.00 (+100 pts)\n"
                "00:00:02.000 Core 1 [M1 Velocity] BUY SCALP OPENED @ 4005.00 | SL: 3995.00 (-100 pts) | TP: 4015.00 (+100 pts)\n"
                "00:00:05.000 Core 1 [Velocity Safety] Deal #100 closed\n"
                "00:00:10.000 Core 1 [Velocity Safety] Deal #999 closed\n"
            )
            f.write(text)
            temp_path = Path(f.name)

        try:
            records = parse_v16_live_deploy_log(temp_path)
            # Record 1: Open @ 4000 has no close before next open -> UNMATCHED_OPEN
            self.assertEqual(records[0]["outcome"], "UNMATCHED_OPEN")
            self.assertEqual(records[0]["match_status"], "UNMATCHED")

            # Record 2: Open @ 4005 paired with Deal #100 -> CLOSE_OBSERVED_UNVERIFIED
            self.assertEqual(records[1]["outcome"], "CLOSE_OBSERVED_UNVERIFIED")
            self.assertEqual(records[1]["match_status"], "PAIRED_CLOSE_OBSERVED")

            # Record 3: Deal #999 closed without matching open -> UNMATCHED_CLOSE
            self.assertEqual(records[2]["outcome"], "UNMATCHED_CLOSE")
            self.assertEqual(records[2]["match_status"], "UNMATCHED")
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
