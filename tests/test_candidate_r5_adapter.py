"""The R5 adapter must not broaden older candidate execution contracts."""
import inspect
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from research import run_v25_native as runner


class R5AdapterTests(TestCase):
    def test_alignment_setting_is_scoped_to_r5(self):
        for kwargs in ({}, {"r2": True}, {"production": True}):
            with self.subTest(kwargs=kwargs):
                self.assertNotIn("InpRequireM1Alignment", runner.settings("check", 0, {}, **kwargs))
                with self.assertRaises(ValueError):
                    runner.settings("check", 0, {"InpRequireM1Alignment": True}, **kwargs)

    def test_r5_settings_serialize_boolean_and_preserve_parity(self):
        for aligned in (False, True):
            text = runner.settings("r5_check", 5, {"InpRequireM1Alignment": aligned,
                "InpTakeProfitRRMul": 1.0}, r2=True, r5=True)
            self.assertIn(f"InpRequireM1Alignment={str(aligned).lower()}\n", text)
            self.assertIn("InpTakeProfitRRMul=1.0\n", text)
            self.assertNotIn("InpUseGridIndices", text)
        text = runner.settings("r5_parity", 0, {}, r2=True, r5=True)
        self.assertIn("InpTakeProfitRRMul=2.0\n", text)
        self.assertIn("InpRequireM1Alignment=false\n", text)

    def test_bad_r5_adapter_arguments_rejected(self):
        for kwargs in ({"r5": True}, {"r2": True, "r5": True, "optimize": True},
                       {"r2": True, "r5": True, "production": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                runner.settings("r5_check", 5, {}, **kwargs)
        for mode, overrides in ((1, {}), (0, {"InpRequireM1Alignment": True}),
                                (5, {"InpRequireM1Alignment": "perhaps"})):
            with self.subTest(mode=mode, overrides=overrides), self.assertRaises(ValueError):
                runner.settings("r5_check", mode, overrides, r2=True, r5=True)

    def test_output_path_cannot_leave_reports(self):
        with patch.object(runner, "freeze") as freeze:
            with self.assertRaisesRegex(ValueError, "remain in project reports"):
                runner.execute("r5_check", candidate_source="research/ResearchCandidate_R5.mq5",
                               evidence_base=runner.ROOT / "elsewhere")
            freeze.assert_not_called()

    def test_scoped_base_is_forwarded_on_retry_and_parity(self):
        source = inspect.getsource(runner.execute)
        self.assertIn("evidence_base=output_base", source)
        self.assertIn("freeze(output_base)", source)
        params = inspect.signature(runner.parity).parameters
        self.assertIn("evidence_base", params)
        self.assertIn("production_base", params)

    def test_unknown_candidate_source_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported isolated candidate source"):
            runner.execute("r5_check", candidate_source="research/unreviewed.mq5")

    def test_native_alignment_fixtures_cannot_be_truncated(self):
        source = inspect.getsource(runner.execute)
        self.assertIn("R5_NATIVE_FIXTURES_PASS checks=27", source)
        self.assertIn("R4_NATIVE_FIXTURES_PASS checks=25", source)
