"""Independent frozen-baseline and fee-aware accounting checks. No native launch."""
from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

from research.analyze_v23_backtest import bucket, parse_deals
from research.build_v24 import function


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E"


def deal(ticket, entry, volume, profit=0, commission=0, swap=0, fee=0):
    return dict(ticket=str(ticket), position="42", time_msc=str(1764590400000 + ticket * 1000),
                type="0" if entry == 0 else "1", entry=str(entry), reason="0", magic="992300",
                symbol="XAUUSD", volume=str(volume), price="4200", profit=str(profit),
                commission=str(commission), swap=str(swap), fee=str(fee), comment="test")


class IndependentReviewTests(unittest.TestCase):
    def test_frozen_v24_source_unchanged(self):
        self.assertEqual(sha256((ROOT / "AegisPredator_v24.mq5").read_bytes()).hexdigest().upper(), SOURCE_SHA)

    def test_baseline_breaker_management_margin_unchanged(self):
        baseline = (ROOT / "AegisPredator_v23.mq5").read_text(encoding="utf-8")
        current = (ROOT / "AegisPredator_v24.mq5").read_text(encoding="utf-8")
        for name in ("IsCircuitBreakerActive", "ManageOpenPositions", "HasOpenPosition", "CheckMargin"):
            with self.subTest(function=name):
                self.assertEqual(function(current, name), function(baseline, name))

    def test_completed_trend_signal_exactly_tested_signal(self):
        current = (ROOT / "AegisPredator_v24.mq5").read_text(encoding="utf-8")
        extension = (ROOT / "research/v23_tuning_extension.mqh").read_text(encoding="utf-8")
        self.assertEqual(function(current, "ProposedSignal"), function(extension, "ProposedSignal"))

    def test_entry_charges_partial_exits_and_december_preserved(self):
        rows = [deal(1, 0, .02, commission=-.20, fee=-.10),
                deal(2, 1, .01, profit=1, commission=-.10, swap=-.05),
                deal(3, 1, .01, profit=2, commission=-.10, swap=-.05)]
        trades, cash = parse_deals(rows)
        self.assertEqual(len(trades), 1)
        self.assertEqual(cash, [])
        self.assertTrue(trades[0]["open"].startswith("2025-12-01"))
        result = bucket(trades)
        self.assertEqual(result["net"], 2.40)
        self.assertEqual(result["commission"], -.40)
        self.assertEqual(result["swap"], -.10)
        self.assertEqual(result["fee"], -.10)
        self.assertEqual(result["trades"], 1)

    def test_gross_winner_net_loser_is_not_win(self):
        trades, _ = parse_deals([deal(1, 0, .01, commission=-.30), deal(2, 1, .01, profit=.20)])
        self.assertEqual(bucket(trades)["wins"], 0)
        self.assertEqual(bucket(trades)["losses"], 1)
        self.assertEqual(bucket(trades)["net"], -.10)

    def test_nonfinite_fee_rejected(self):
        for value in ("NaN", "inf", "-inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_deals([deal(1, 0, .01, fee=value), deal(2, 1, .01)])

    def test_unclosed_or_oversize_exit_rejected(self):
        cases = [[deal(1, 0, .01)], [deal(1, 0, .01), deal(2, 1, .02)]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                parse_deals(rows)

    def test_v25_generation_keeps_baseline_management_exact(self):
        from research.build_v25 import generate
        generated = generate()
        baseline = (ROOT / "AegisPredator_v24.mq5").read_text(encoding="utf-8")
        for name in ("IsCircuitBreakerActive", "ManageOpenPositions", "HasOpenPosition", "CheckMargin", "ProposedSignal"):
            with self.subTest(function=name):
                self.assertEqual(function(generated, name), function(baseline, name))

    def test_v25_mode_zero_calls_exact_v24_signal(self):
        from research.build_v25 import generate
        candidate = function(generate(), "CandidateSignal")
        mode_zero = candidate.split("if(InpExperimentMode==0)", 1)[1].split("candidateReason=\"invalid_atr\"", 1)[0]
        self.assertIn("candidateSide=ProposedSignal(atr);", mode_zero)
        self.assertIn("return candidateSide;", mode_zero)

    def test_native_parity_rows_include_2025(self):
        from research.run_v25_native import native_sequence
        rows = [["2025.12.02 10:00", "buy", ".01"], ["2026.01.02 10:00", "sell", ".01"], ["summary"]]
        with patch("research.run_v25_native.report_rows", return_value=({}, rows)):
            self.assertEqual(native_sequence(Path("unused.htm")), rows[:2])

    def test_ten_complete_months_exact(self):
        from research.run_v25_native import months
        self.assertEqual(months("2025.12.01", "2026.10.01"), [202512, 202601, 202602, 202603, 202604, 202605, 202606, 202607, 202608, 202609])
        with self.assertRaises(ValueError):
            months("2025.12.02", "2026.10.01")

    def test_fractional_coverage_identifiers_rejected(self):
        from research.run_v25_native import validate_coverage
        millis = lambda d: int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp() * 1000)
        row = dict(pass_=0, month=202603, ticks=10, first_tick_msc=millis("2026-03-02T01:00:00"), last_tick_msc=millis("2026-03-31T23:00:00"))
        row["pass"] = row.pop("pass_")
        self.assertEqual(validate_coverage([row], "2026.03.01", "2026.04.01", {0})["observations"], 1)
        for key, value in (("pass", .5), ("month", 202603.5)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_coverage([dict(row, **{key: value})], "2026.03.01", "2026.04.01", {0})

    def test_failed_final_does_not_reselect_other_survivor(self):
        from research import run_v25_native as runner
        calls, saved = [], {}

        def fake_execute(name, mode=0, overrides=None, **kwargs):
            calls.append((name, mode))
            if "_dev_" in name:
                return dict(rows=[dict(net=100, gross_net_wins=150, gross_net_losses=50,
                                      positions=150, wins=100, equity_dd=1, equity_dd_pct=mode,
                                      native_net=100, sl_atr=1.5, tp_r=2, entry_strength=0)])
            if name.endswith("_production_v24"):
                return dict(evidence_run=name, native={})
            result = dict(net=100, net_profit_factor=1.5, trades=150,
                          native_equity_dd_pct=mode or 10, evidence_run=name,
                          monthly={str(i): dict(net=10) for i in range(10)})
            if name.endswith("_confirmation"):
                self.assertTrue(any(p.name.endswith("_selection_lock.json") for p in saved))
                result.update(net=-10, net_profit_factor=.5)
            return result

        with TemporaryDirectory() as folder, patch.object(runner, "BASE", Path(folder)), \
                patch.object(runner, "execute", side_effect=fake_execute), \
                patch.object(runner, "parity", return_value={"passed": True}), \
                patch.object(runner, "save", side_effect=lambda p, v: saved.update({p: v})):
            runner.run_all("independent_lock")
        confirmations = [(name, mode) for name, mode in calls if name.endswith("_confirmation")]
        self.assertEqual(confirmations, [("independent_lock_confirmation", 1)])
        complete = next(v for p, v in saved.items() if p.name.endswith("_complete.json"))
        self.assertFalse(complete["qualified"])
        self.assertFalse(complete["promotion"])
        self.assertEqual(complete["selection_lock"]["mode"], 1)


if __name__ == "__main__":
    unittest.main()
