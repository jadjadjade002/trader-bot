"""Independent static audit of Candidate R4 source and runner contracts; no native execution."""
from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
R2 = ROOT / "research/ResearchCandidate_R2.mq5"
R4 = ROOT / "research/ResearchCandidate_R4.mq5"
BUILDER = ROOT / "research/build_candidate_r4.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_candidate_r4_luna_review", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateR4LunaReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = R2.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.r4 = R4.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.builder = load_builder()

    def test_r4_is_builder_output_and_preserves_r2_signal_execution_and_fixtures(self):
        self.assertEqual(self.r4, self.builder.generate())
        for name in (
            "R2Exhaustion", "CandidateR2Signal", "OnTick", "OriginalOnTick",
            "ManageOpenPositions", "RunR2FixtureTests", "R2Assert",
        ):
            with self.subTest(function=name):
                self.assertEqual(
                    self.builder.function(self.r2, name)
                    .replace("R2_NATIVE_FIXTURE_FAIL", "R4_NATIVE_FIXTURE_FAIL")
                    .replace("R2_NATIVE_FIXTURES_PASS", "R4_NATIVE_FIXTURES_PASS"),
                    self.builder.function(self.r4, name),
                )

    def test_exit_distances_are_only_economic_equations_changed_by_grid_inputs(self):
        for source in (self.r2, self.r4):
            self.assertEqual(
                source.count("double slDistance = MathMax(InpStopLossATRMul * atr, InpMinSLPoints * point);"),
                1,
            )
            self.assertEqual(source.count("double tpDistance = slDistance * InpTakeProfitRRMul;"), 1)
        validation = self.builder.function(self.r4, "ValidateR2Inputs")
        self.assertIn("InpExperimentMode==0 && InpEntryStrength==0", validation)
        self.assertIn("InpExperimentMode==5 && InpEntryStrength>=0 && InpEntryStrength<=1", validation)
        for value in ("1.0", "1.5"):
            self.assertIn(f"InpStopLossATRMul=={value}", validation)
        for value in ("0.75", "1.0", "1.5", "2.0"):
            self.assertIn(f"InpTakeProfitRRMul=={value}", validation)

    def test_signal_and_position_identity_inputs_are_locked(self):
        """R4 must freeze signal periods and position identity along with exit grid."""
        validation = self.builder.function(self.r4, "ValidateR2Inputs")
        for guard in (
            "InpATRPeriod!=14",
            "InpDonchianPeriod!=20",
            "InpMagicNumber!=992300",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, validation)

    def test_r4_runner_matrix_activation_and_shared_flow_are_present(self):
        runner = (ROOT / "research/run_candidate_r4.py").read_text(encoding="utf-8")
        shared = (ROOT / "research/run_candidate_r2.py").read_text(encoding="utf-8")
        native = (ROOT / "research/run_v25_native.py").read_text(encoding="utf-8")
        protocol = (ROOT / "docs/CANDIDATE_R4_EXIT_PROTOCOL.md").read_text(encoding="utf-8")
        for token in (
            "product((0, 1), (1.0, 1.5), (0.75, 1.0, 1.5, 2.0))",
            "len(rows) == 6", "and actual == expected", "not qualify(r[\"result\"])",
            "run_all(args.prefix, SOURCE, FAMILIES, \"R4\", configurations(), max_per_family=3)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, runner)
        self.assertIn("progress[\"development_shortlist\"]", shared)
        self.assertIn("selection_lock.json", shared)
        self.assertIn("R4_NATIVE_FIXTURES_PASS checks=25", native)
        for policy in (
            "The 16-row matrix is fixed before any R4 result.",
            "at most the top three development-qualified configurations",
            "Finalist selection uses the development/validation sequence",
            "Lock one validation survivor before confirmation.",
            "Confirmation/full-period outcomes never select or reselect the finalist.",
            "a development-only maximum may receive a rejected descriptive ten-month replay",
            "no validation, selection lock, confirmation, or capital/stress qualification",
        ):
            with self.subTest(policy=policy):
                self.assertIn(policy, protocol)


if __name__ == "__main__":
    unittest.main()
