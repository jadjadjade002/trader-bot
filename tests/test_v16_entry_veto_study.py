"""Unit and regression tests for V16 Observational Entry Veto Study."""
from __future__ import annotations

import unittest
from pathlib import Path

from research.v16_entry_veto_study import (
    LABEL_HORIZON_EMBARGO_SECONDS,
    MAX_ALLOWED_VETO_COVERAGE,
    MIN_SPLIT_SAMPLE_FLOOR,
    compute_metrics,
    get_candidate_vetoes,
    prepare_dataset,
    run_veto_study,
)


class TestV16EntryVetoStudy(unittest.TestCase):

    def setUp(self):
        self.telemetry_path = Path("data/V16TickTelemetry_XAUUSD_M1_20260914.csv")
        self.policy = {
            "tp_pts": 180.0,
            "sl_pts": 260.0,
            "be_trigger_pts": 85.0,
            "be_lock_pts": 15.0,
        }

    def test_metrics_calculation_formula(self):
        """Verifies correct calculation of tp_retained, sl_removed, be_removed, coverage, and expectancy."""
        rows = [
            {"outcome": "TP", "points": 180.0, "spread": 20.0},
            {"outcome": "INITIAL_SL", "points": -260.0, "spread": 50.0},
            {"outcome": "INITIAL_SL", "points": -260.0, "spread": 30.0},
            {"outcome": "BE", "points": 15.0, "spread": 48.0},
        ]
        # Veto high spread > 40: blocks row 1 (SL) and row 3 (BE)
        veto_fn = lambda r: r["spread"] > 40.0
        res = compute_metrics(rows, veto_fn)

        self.assertEqual(res["n"], 4)
        self.assertEqual(res["blocked"], 2)
        self.assertEqual(res["kept"], 2)
        self.assertEqual(res["coverage_blocked"], 0.5)
        self.assertTrue(res["coverage_valid"])

        # Kept: row 0 (TP), row 2 (SL)
        self.assertEqual(res["tp_retained"], 1.0)
        self.assertEqual(res["sl_removed"], 0.5)
        self.assertEqual(res["be_removed"], 1.0)
        self.assertEqual(res["net_points_kept"], -80.0)
        self.assertEqual(res["expectancy_points_per_trade"], -40.0)

    def test_15_minute_label_horizon_embargo(self):
        """Regression test: Enforces 15-minute (900s) forward embargo between train and validation."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path, train_ratio=0.65, embargo_seconds=900)
        train_max_horizon = report["metadata"]["train_split"]["max_horizon_time_msc"]
        val_min_entry = report["metadata"]["validation_split"]["min_entry_time_msc"]
        embargo_gap = report["metadata"]["validation_split"]["embargo_gap_milliseconds"]

        self.assertGreater(
            embargo_gap,
            0,
            "Validation entry must be strictly after the latest train label horizon",
        )
        self.assertGreater(val_min_entry, train_max_horizon)
        self.assertGreater(report["metadata"]["embargoed_rows_count"], 0)

    def test_veto_coverage_ceiling_enforced(self):
        """Regression test: Candidates blocking > 50% must be disqualified for excessive coverage."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path)
        candidates = {c["veto_id"]: c for c in report["candidates"]}

        # VETO_HIGH_ATR_200 blocks 100% of trades in early session -> must be rejected for excessive coverage
        atr_shock = candidates["VETO_HIGH_ATR_200"]
        self.assertFalse(atr_shock["coverage_pass"])
        self.assertIn("EXCESSIVE_COVERAGE", atr_shock["evaluation_verdict"])

    def test_validation_deterioration_cannot_be_accepted(self):
        """A train-only gain with negative held-out delta is overfit, never accepted."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path)
        candidates = {c["veto_id"]: c for c in report["candidates"]}
        rsi = candidates["VETO_RSI_OVEREXTENDED"]
        self.assertGreater(rsi["train_expectancy_delta"], 0)
        self.assertLess(rsi["validation_expectancy_delta"], 0)
        self.assertEqual(rsi["evaluation_verdict"], "REJECTED_HYPOTHESIS")

    def test_split_sample_floors_enforced(self):
        """Regression test: Both train and validation partitions must satisfy minimum sample floors."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path)
        train_count = report["metadata"]["train_split"]["count"]
        val_count = report["metadata"]["validation_split"]["count"]

        self.assertGreaterEqual(train_count, MIN_SPLIT_SAMPLE_FLOOR)
        self.assertGreaterEqual(val_count, MIN_SPLIT_SAMPLE_FLOOR)

    def test_no_causal_claims_and_exploratory_marking(self):
        """Regression test: Verifies zero causal claims, observable proxy labels, and exploratory status."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path)
        title = report["metadata"]["title"].lower()
        self.assertNotIn("causal", title)
        self.assertIn("observational", title)

        self.assertEqual(report["metadata"]["collector_data_classification"], "EXPLORATORY_ONLY")
        self.assertEqual(report["metadata"]["label_classification"], "OBSERVABLE_PROXY_ONLY")

    def test_anti_promotion_guard(self):
        """Verifies that single-session telemetry cannot be promoted to DEPLOY_READY."""
        if not self.telemetry_path.exists():
            self.skipTest("Telemetry data not found")

        report = run_veto_study(self.telemetry_path)
        verdict = report["governance_verdict"]["verdict"]
        deployment = report["governance_verdict"]["deployment_status"]

        self.assertIn(verdict, ["RESEARCH_ONLY", "INCONCLUSIVE"])
        self.assertNotEqual(verdict, "DEPLOY_READY")
        self.assertEqual(deployment, "BLOCKED")
        self.assertGreater(len(report["governance_verdict"]["reasons"]), 0)


if __name__ == "__main__":
    unittest.main()
