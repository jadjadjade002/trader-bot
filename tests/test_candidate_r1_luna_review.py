"""Independent, non-native checks for the Candidate R1 evidence contract."""
import json
import unittest
from pathlib import Path

from research.analyze_v23_backtest import bucket, parse_deals
from research.run_v25_native import (
    audit_xml,
    csv_rows,
    qualify,
    strict_int,
    validate_coverage,
)
from research.candidate_release_evidence import evaluate


ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "reports/v25_research_20261007/r1_b_progress.json"
COMPLETE = ROOT / "reports/v25_research_20261007/r1_b_complete.json"
RETRY_NAME = "r1_b_dev_continuation_retry1"
RAW = ROOT / ".mt5-v23-tuning.local/MQL5/Files"
REPORT = ROOT / ".mt5-v23-tuning.local/reports"


class LunaCandidateReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
        cls.complete = json.loads(COMPLETE.read_text(encoding="utf-8"))

    def test_reference_baseline_profit_is_too_small_for_stated_cost_stress(self):
        baseline = self.progress["baseline"]
        self.assertEqual(baseline["trades"], 3768)
        self.assertAlmostEqual(baseline["net"], 130.0)
        self.assertAlmostEqual(baseline["net_profit_factor"], 1.0096)
        self.assertLess(baseline["extra_cost_stress"]["0.2"], 0)
        self.assertLess(baseline["extra_cost_stress"]["0.5"], 0)

    def test_callback_observations_are_not_claimed_as_raw_tick_coverage(self):
        coverage = self.progress["baseline"]["coverage"]
        self.assertIn("callbacks", coverage["metric"])
        self.assertFalse(coverage["interior_gap_free_proven"])
        self.assertLess(coverage["observed_callbacks"], coverage["native_raw_ticks"])
        self.assertEqual(coverage["callbacks_skipped_by_execution"], 12810)

    def test_reused_history_is_not_labeled_unseen(self):
        self.assertFalse(self.progress["genuinely_unseen_oos"])
        self.assertFalse(self.progress["promotion"])
        self.assertTrue(self.progress["parity"]["passed"])
        self.assertTrue(self.progress["parity"]["includes_2025"])
        self.assertEqual(self.progress["parity"]["native_rows"], 15072)

    def test_runner_qualification_can_pass_even_when_recorded_stress_loses(self):
        # The native runner stores these stresses beside the summary but qualify()
        # accepts only net, PF, trade count, and DD. This test exposes that gap.
        candidate = dict(net=500, net_profit_factor=1.25, trades=200,
                         native_equity_dd_pct=2,
                         extra_cost_stress={"0.2": -100, "0.5": -500},
                         delay500={"net": -25})
        self.assertTrue(qualify(candidate))

    def test_retry_optimizer_frames_monthly_coverage_and_native_xml_reconcile(self):
        frames = csv_rows(RAW / f"{RETRY_NAME}_optimization.csv")
        coverage_rows = csv_rows(RAW / f"{RETRY_NAME}_coverage.csv")
        passes = {strict_int(row["pass"]) for row in frames}
        coverage = validate_coverage(
            coverage_rows, "2025.12.01", "2026.06.01", passes
        )
        self.assertEqual(len(frames), 36)
        self.assertEqual(coverage["passes"], 36)
        self.assertEqual(coverage["months"], [202512, 202601, 202602, 202603, 202604, 202605])
        self.assertEqual(coverage["observations"], 216)
        self.assertFalse(coverage["interior_gap_free_proven"])
        self.assertTrue(all(
            strict_int(row["observed_ticks"], low=1)
            == coverage["total_ticks"][str(strict_int(row["pass"]))]
            for row in frames
        ))
        self.assertEqual(
            audit_xml(REPORT / f"{RETRY_NAME}.xml", frames),
            {"native_rows": 36, "independently_reconciled": 36},
        )

    def test_separate_release_screen_fails_closed_and_never_promotes(self):
        evidence = {
            "qualified": True,
            "full": {"extra_cost_stress": {"0.2": 25}},
            "delay500": {"net": 30, "net_profit_factor": 1.12},
            "capital70": {"net": 2, "native_stopout": False},
        }
        passed = evaluate(evidence)
        self.assertTrue(passed["historically_robust"])
        self.assertFalse(passed["promotion"])
        self.assertFalse(passed["genuinely_unseen_oos"])
        self.assertEqual(passed["prospective_confirmation"], "NOT_ESTABLISHED")

        for field in ("full", "delay500", "capital70"):
            with self.subTest(missing=field):
                incomplete = dict(evidence)
                incomplete.pop(field)
                result = evaluate(incomplete)
                self.assertFalse(result["historically_robust"])
                self.assertTrue(result["reasons"])

    def test_all_108_development_frames_reconcile_and_no_validation_survivor(self):
        total = 0
        best = None
        for mode, development in self.complete["development"].items():
            name = development["evidence_run"]
            frames = csv_rows(RAW / f"{name}_optimization.csv")
            coverage = validate_coverage(
                csv_rows(RAW / f"{name}_coverage.csv"),
                "2025.12.01", "2026.06.01",
                {strict_int(row["pass"]) for row in frames},
            )
            self.assertEqual(len(frames), 36)
            self.assertEqual(coverage["observations"], 216)
            self.assertEqual(
                audit_xml(REPORT / f"{name}.xml", frames),
                {"native_rows": 36, "independently_reconciled": 36},
            )
            self.assertTrue(all(
                strict_int(row["observed_ticks"], low=1)
                == coverage["total_ticks"][str(strict_int(row["pass"]))]
                for row in frames
            ))
            total += len(frames)
            for row in development["rows"]:
                candidate = (int(mode), float(row["net"]), row)
                if best is None or (candidate[1], -float(row["equity_dd_pct"])) > (best[1], -float(best[2]["equity_dd_pct"])):
                    best = candidate

        self.assertEqual(total, 108)
        self.assertEqual(self.complete["validation"], [])
        self.assertFalse(self.complete["qualified"])
        self.assertFalse(self.complete["promotion"])
        self.assertEqual(best[0], 1)
        self.assertAlmostEqual(best[1], 808.41, places=2)
        self.assertEqual(self.complete["descriptive_failed_candidate"]["parameters"], {
            "InpStopLossATRMul": 2.0,
            "InpTakeProfitRRMul": 3.0,
            "InpEntryStrength": 2,
        })

    def test_descriptive_replay_deals_match_labeled_nonqualified_result(self):
        name = "r1_b_descriptive10m"
        run_dir = ROOT / f"reports/v25_research_20261007/runs/{name}"
        accepted = json.loads((run_dir / "accepted.json").read_text(encoding="utf-8"))["result"]
        trades, cash = parse_deals(csv_rows(run_dir / f"{name}_deals.csv"))
        summary = bucket(trades)
        self.assertEqual(len(cash), 1)
        self.assertEqual(cash[0]["type"], 2)
        self.assertAlmostEqual(cash[0]["net"], 10000)
        self.assertEqual(summary["trades"], 2490)
        self.assertAlmostEqual(summary["net"], 547.26)
        self.assertAlmostEqual(summary["net_profit_factor"], 1.0457, places=4)
        self.assertEqual(summary["net"], accepted["net"])
        self.assertEqual(self.complete["failure_reason"], "No development/validation-qualified candidate")
        self.assertEqual(
            self.complete["descriptive_failed_candidate"]["selection"],
            "Development-only maximum, not validated or promotion-eligible",
        )


if __name__ == "__main__":
    unittest.main()
