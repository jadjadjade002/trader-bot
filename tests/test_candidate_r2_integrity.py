from pathlib import Path
from unittest import TestCase
from research.build_candidate_r2 import generate, function, OUT


class R2IntegrityTests(TestCase):
    def test_generation_matches_and_risk_management_unmodified(self):
        generated = generate()
        baseline = Path("AegisPredator_v24.mq5").read_text(encoding="utf-8")
        self.assertEqual(OUT.read_text(encoding="utf-8"), generated)
        for name in ("ProposedSignal", "ReadClosed", "IsCircuitBreakerActive", "ManageOpenPositions", "CheckMargin", "HasOpenPosition", "InitV24Signal"):
            self.assertEqual(function(generated, name), function(baseline, name))

    def test_native_fixtures_call_actual_predicates_and_reset_state(self):
        body = Path("research/candidate_r2_native_tests.mqh").read_text(encoding="utf-8")
        for name in ("R2Pullback", "R2Compression", "R2RangeReversal", "R2Exhaustion", "R2BreakRetest", "R2AdvanceArm", "R2QuoteCost"):
            self.assertIn(name + "(", body)
        self.assertIn("ResetR2State();\n   if(ok)", body)
        generated = generate()
        init = function(generated, "OnInit")
        self.assertIn("!RunR2FixtureTests()", init)
        self.assertLess(init.index("RunR2FixtureTests()"), init.index("BenchInitR2()"))
