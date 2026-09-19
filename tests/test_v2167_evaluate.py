import importlib.util
import math
import unittest
from datetime import date, timedelta
from pathlib import Path


PATH = Path(__file__).parents[1] / "research" / "v2167_evaluate.py"
SPEC = importlib.util.spec_from_file_location("v2167_evaluate", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def favorable(windows=40, carried=0):
    start = date(2026, 1, 1)
    sessions = {
        (start + timedelta(days=index)).isoformat(): {"trades": 10, "wins": 9, "net": 8.5, "carried_past_wake": carried if index == 0 else 0}
        for index in range(windows)
    }
    pnl = [1.0] * 360 + [-0.5] * 40
    return {
        "trades": 400, "wins": 360, "net": sum(pnl),
        "closed": [{"net": value} for value in pnl], "sessions": sessions,
        "native": {"Equity Drawdown Relative": "10.00% (10.00)"},
        "forced_test_end_exits": 0,
        "independent_trial_assumption": "Wilson assumes independent trades",
    }


class V2167EvaluationTests(unittest.TestCase):
    def test_historical_result_cannot_promote_even_when_favorable(self):
        result = MODULE.evaluate_analysis(favorable(), "EXPOSED_ENGINEERING_ONLY", True)
        self.assertFalse(result["eligible_for_promotion"])
        self.assertIn("engineering-only evaluator; no prospective source/start/schedule freeze manifest is verified", result["promotion_blockers"])
        self.assertFalse(result["gates"]["positive_expectancy_after_extra_half_spread_cost_stress"])
        self.assertEqual(result["evaluator_scope"], "ENGINEERING_ONLY_NEVER_PROMOTES")

    def test_carry_past_wake_makes_night_incomplete_and_fails_closed(self):
        result = MODULE.evaluate_analysis(favorable(carried=1), "PROSPECTIVE_SEALED", True)
        self.assertEqual(result["metrics"]["complete_windows"], 39)
        self.assertFalse(result["sessions"]["2026-01-01"]["joint_target_met"])
        self.assertFalse(result["gates"]["no_positions_carried_past_wake"])
        self.assertFalse(result["eligible_for_promotion"])

    def test_incomplete_window_count_fails_minimum(self):
        result = MODULE.evaluate_analysis(favorable(windows=39), "PROSPECTIVE_SEALED", True)
        self.assertFalse(result["gates"]["at_least_40_full_weekday_windows"])

    def test_zero_trade_night_stays_in_denominator(self):
        data = favorable()
        data["sessions"]["2026-01-01"] = {"trades": 0, "wins": 0, "net": 0.0, "carried_past_wake": 0}
        result = MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY", True)
        self.assertEqual(result["metrics"]["zero_trade_windows"], 1)
        self.assertEqual(result["metrics"]["joint_target_nights"], 39)
        self.assertEqual(result["metrics"]["joint_target_night_pct"], 97.5)

    def test_nonfinite_trade_value_is_rejected(self):
        data = favorable()
        data["closed"][0]["net"] = math.nan
        with self.assertRaisesRegex(MODULE.EvaluationError, "not finite"):
            MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY")

    def test_missing_deal_fee_column_is_disclosed_and_blocks_promotion(self):
        result = MODULE.evaluate_analysis(favorable(), "PROSPECTIVE_SEALED", False)
        self.assertFalse(result["fee_accounting"]["per_trade_and_per_night_fee_allocation_complete"])
        self.assertIn("DEAL_FEE", result["fee_accounting"]["limitation"])
        self.assertFalse(result["eligible_for_promotion"])

    def test_fractional_count_is_rejected_not_truncated(self):
        data = favorable()
        data["trades"] = 400.5
        with self.assertRaisesRegex(MODULE.EvaluationError, "nonnegative integer"):
            MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY")

    def test_relative_not_maximal_equity_drawdown_is_used(self):
        data = favorable()
        data["native"]["Equity Drawdown Relative"] = "21.00% (5.00)"
        data["native"]["Equity Drawdown Maximal"] = "5.00 (10.00%)"
        result = MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY", True)
        self.assertEqual(result["metrics"]["equity_drawdown_pct"], 21.0)
        self.assertFalse(result["gates"]["equity_drawdown_at_most_20_pct"])

    def test_drawdown_over_100_is_valid_negative_equity_evidence(self):
        data = favorable()
        data["native"]["Equity Drawdown Relative"] = "106.80% (53.40)"
        result = MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY", True)
        self.assertEqual(result["metrics"]["equity_drawdown_pct"], 106.8)
        self.assertFalse(result["gates"]["equity_drawdown_at_most_20_pct"])

    def test_reconciliation_mismatch_is_rejected(self):
        data = favorable()
        data["net"] += 1.0
        with self.assertRaisesRegex(MODULE.EvaluationError, "reconcile"):
            MODULE.evaluate_analysis(data, "EXPOSED_ENGINEERING_ONLY")


if __name__ == "__main__":
    unittest.main()
