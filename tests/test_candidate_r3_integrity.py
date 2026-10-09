from pathlib import Path
from unittest import TestCase
from research.run_candidate_r3 import activation_ok
from research.build_candidate_r3 import generate, function, OUT


class R3IntegrityTests(TestCase):
    def test_activation_requires_ten_failures(self):
        self.assertTrue(activation_ok(dict(development=[dict(eligible=False)]*10)))
        self.assertFalse(activation_ok(dict(development=[dict(eligible=False)]*9)))
        self.assertFalse(activation_ok(dict(development=[dict(eligible=False)]*9+[dict(eligible=True)])))
        self.assertFalse(activation_ok(dict(development=[{}]*10)))

    def test_exact_baseline_and_economic_management_preserved(self):
        generated = generate()
        baseline = Path("AegisPredator_v24.mq5").read_text(encoding="utf-8")
        self.assertEqual(OUT.read_text(encoding="utf-8"), generated)
        for name in ("ProposedSignal", "ReadClosed", "IsCircuitBreakerActive", "ManageOpenPositions", "HasOpenPosition", "CheckMargin", "InitV24Signal"):
            self.assertEqual(function(generated, name), function(baseline, name))
        self.assertIn("!RunR3FixtureTests()", function(generated, "OnInit"))
