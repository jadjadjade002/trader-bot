"""R4 source-contract checks; these do not compile or execute MQL."""
from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
R2 = ROOT / "research/ResearchCandidate_R2.mq5"
R4 = ROOT / "research/ResearchCandidate_R4.mq5"
BUILDER = ROOT / "research/build_candidate_r4.py"
PROTOCOL = ROOT / "docs/CANDIDATE_R4_EXIT_PROTOCOL.md"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_candidate_r4", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateR4SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = R2.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.r4 = R4.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.protocol = PROTOCOL.read_text(encoding="utf-8")
        cls.build_module = load_builder()

    def test_generated_output_is_reproducible(self):
        self.assertEqual(self.r4, self.build_module.generate())

    def test_frozen_signal_and_economic_execution_are_identical(self):
        names = (
            "CandidateR2Signal", "R2Exhaustion", "OnTick", "OriginalOnTick",
            "ObservePath", "ExportPaths", "OnTester", "RunR2FixtureTests",
            "R2Assert", "R2FixtureBar", "R2Reflect",
        )
        for name in names:
            with self.subTest(function=name):
                self.assertEqual(
                    self.build_module.function(self.r2, name).replace("R2_NATIVE_FIXTURE_FAIL", "R4_NATIVE_FIXTURE_FAIL").replace("R2_NATIVE_FIXTURES_PASS", "R4_NATIVE_FIXTURES_PASS"),
                    self.build_module.function(self.r4, name),
                )
        for statement in (
            "double slDistance = MathMax(InpStopLossATRMul * atr, InpMinSLPoints * point);",
            "double tpDistance = slDistance * InpTakeProfitRRMul;",
            "if(InpEnableHardSL)",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, self.r4)
                self.assertEqual(self.r2.count(statement), self.r4.count(statement))

    def test_only_bounded_validation_and_metadata_change(self):
        r2_remainder = self.r2
        r4_remainder = self.r4
        for name in (
            "ValidateR2Inputs",
        ):
            r2_remainder = r2_remainder.replace(self.build_module.function(self.r2, name), "<VALIDATION>", 1)
            r4_remainder = r4_remainder.replace(self.build_module.function(self.r4, name), "<VALIDATION>", 1)
        for old, new in (
            ('#property version   "24.91"', '#property version   "24.93"'),
            ('#property description "Research Candidate R2, tester-only. Fixed V24 economics. Not a V25 release."',
             '#property description "Research Candidate R4 exit ablation, tester-only. R2 exhaustion signal frozen. Not a V25 release."'),
            ("R2_NATIVE_FIXTURE_FAIL", "R4_NATIVE_FIXTURE_FAIL"),
            ("R2_NATIVE_FIXTURES_PASS", "R4_NATIVE_FIXTURES_PASS"),
        ):
            r2_remainder = r2_remainder.replace(old, new, 1)
        self.assertEqual(r2_remainder, r4_remainder)

    def test_input_contract_is_exact_matrix_and_parity_locked(self):
        validation = self.build_module.function(self.r4, "ValidateR2Inputs")
        for token in (
            "InpExperimentMode==0", "InpExperimentMode==5", "InpEntryStrength>=0",
            "InpEntryStrength<=1", "InpStopLossATRMul==1.0", "InpStopLossATRMul==1.5",
            "InpTakeProfitRRMul==0.75", "InpTakeProfitRRMul==1.0",
            "InpTakeProfitRRMul==1.5", "InpTakeProfitRRMul==2.0",
            "InpExperimentMode==0 && InpEntryStrength==0",
            "InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0",
            "InpMaxHoldBars!=60", "InpLotSize!=0.01", "InpTargetAccount!=0",
        ):
            with self.subTest(token=token):
                self.assertIn(token, validation)
        self.assertIn("16 configurations", self.protocol)
        self.assertIn("only if no R3 development configuration survives", self.protocol)
        self.assertIn("25 real MQL fixture checks", self.protocol)

    def test_source_hash_and_fixture_prefix_are_guarded(self):
        self.assertIn('EXPECTED_R2_SHA256 = "74AC68D78650411B1364AA2EF6E18FD375928D0C528CBC23085C95867F1354FD"', self.builder)
        self.assertIn('"R2_NATIVE_FIXTURE_FAIL", "R4_NATIVE_FIXTURE_FAIL"', self.builder)
        self.assertIn('"R2_NATIVE_FIXTURES_PASS", "R4_NATIVE_FIXTURES_PASS"', self.builder)
        self.assertIn('#property version   "24.93"', self.r4)
        self.assertIn('R4_NATIVE_FIXTURES_PASS checks=', self.r4)
        self.assertIn('R4_NATIVE_FIXTURE_FAIL', self.r4)


if __name__ == "__main__":
    unittest.main()
