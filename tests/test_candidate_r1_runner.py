from datetime import datetime, timezone
from unittest import TestCase
from research.run_v25_native import months, settings, validate_coverage, qualify, parameters, strict_int
import inspect
from research.run_v25_native import execute, completion_ok


def epoch(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp() * 1000)


def coverage(month=202512, pid=0):
    return dict(pass_=pid, month=month, ticks=100, first_tick_msc=epoch("2025-12-01T01:00:00"),
                last_tick_msc=epoch("2025-12-31T20:00:00"))


def row(**kw):
    r = coverage()
    r["pass"] = r.pop("pass_")
    r.update(kw)
    return r


class CandidateRunnerTests(TestCase):
    def test_completion_separates_optimizer_from_single_test(self):
        optimization = 'optimization finished, total passes 36\nlocal 36 tasks (100%), remote 0 tasks (0%), cloud 0 tasks (0%)\nprocessing stopped'
        self.assertTrue(completion_ok(optimization, True))
        self.assertFalse(completion_ok(optimization))
        self.assertTrue(completion_ok('automatic testing finished'))
        for partial in ('optimization finished, total passes 35', 'processing stopped', 'automatic testing finished'):
            self.assertFalse(completion_ok(partial, True))

    def test_unaccepted_runs_preserved_and_retries_bounded(self):
        body = inspect.getsource(execute)
        self.assertIn("count >= 2", body)
        self.assertIn('f"{original_name}_retry{count+1}"', body)
        self.assertNotIn("rmtree", body)

    def test_ten_months_includes_2025(self):
        self.assertEqual(months("2025.12.01", "2026.10.01"), [202512] + list(range(202601, 202610)))

    def test_not_partial_window(self):
        for a, b in (("2025.12.02", "2026.10.01"), ("2026.10.01", "2026.10.01")):
            with self.assertRaises(ValueError):
                months(a, b)

    def test_production_same_baseline_inputs_no_research_inputs(self):
        s = settings("x", 0, {}, production=True)
        self.assertIn("InpFadeBreakouts=false", s)
        self.assertIn("InpStopLossATRMul=1.5", s)
        self.assertNotIn("InpExperimentMode", s)
        self.assertNotIn("InpBE", s)
        self.assertIn("InpCooldownMinutes=90", s)

    def test_optimizer_exact_axes(self):
        s = settings("x", 2, {}, optimize=True)
        self.assertIn("InpStopLossATRMul=1.5||1.0||0.5||2.0||Y", s)
        self.assertIn("InpTPGridIndex=2||0||1||3||Y", s)
        self.assertIn("InpEntryStrength=0||0||1||2||Y", s)
        self.assertNotIn("InpBE", s)

    def test_settings_reject_unknown_or_inverted(self):
        for override in ({"unknown": 0}, {"InpFadeBreakouts": "true"}):
            with self.assertRaises(ValueError):
                settings("x", 0, override)

    def test_month_coverage_accepts_complete(self):
        result = validate_coverage([row()], "2025.12.01", "2026.01.01", {0})
        self.assertEqual(result["total_ticks"], {"0": 100})

    def test_missing_or_duplicate_month_rejected(self):
        for rows in ([], [row(), row()]):
            with self.assertRaises(ValueError):
                validate_coverage(rows, "2025.12.01", "2026.01.01", {0})

    def test_invalid_coverage_rejected(self):
        for field, value in (("ticks", 0), ("ticks", "NaN"), ("first_tick_msc", epoch("2025-12-20T00:00:00")),
                             ("last_tick_msc", epoch("2025-12-15T00:00:00")), ("pass", 2)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_coverage([row(**{field: value})], "2025.12.01", "2026.01.01", {0})

    def test_fractional_or_negative_identifiers_rejected(self):
        for n in (-1, .5, "NaN", "inf", 4):
            with self.subTest(n=n), self.assertRaises(ValueError):
                strict_int(n, high=3)

    def test_qualification_not_less_loss(self):
        base = dict(net=20, net_profit_factor=1.25, trades=200, native_equity_dd_pct=2)
        self.assertTrue(qualify(base))
        for field, value in (("net", -1), ("net_profit_factor", 1.1), ("trades", 100)):
            with self.subTest(field=field):
                self.assertFalse(qualify(dict(base, **{field: value})))

    def test_parameters_reproduce_frame(self):
        self.assertEqual(parameters(dict(sl_atr="1.5", tp_r="2", entry_strength="1")),
                         dict(InpStopLossATRMul=1.5, InpTakeProfitRRMul=2.0, InpEntryStrength=1))
