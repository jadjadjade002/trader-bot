from unittest import TestCase
from research.run_v25_native import settings
from research.run_candidate_r2 import FAMILIES


class R2RunnerTests(TestCase):
    def test_ten_configs_with_fixed_exits(self):
        self.assertEqual(len(FAMILIES) * 2, 10)
        for mode in FAMILIES:
            for preset in (0, 1):
                text = settings("r2", mode, dict(InpEntryStrength=preset), r2=True)
                for fixed in ("InpStopLossATRMul=1.5", "InpTakeProfitRRMul=2.0", "InpMaxHoldBars=60", "InpLotSize=0.01"):
                    self.assertIn(fixed, text)
                self.assertNotIn("InpTPGridIndex", text)
                self.assertNotIn("InpUseGridIndices", text)

    def test_adapter_rejects_unsupported_grid_or_production(self):
        for kwargs in (dict(optimize=True), dict(production=True)):
            with self.assertRaises(ValueError):
                settings("r2", 1, {}, r2=True, **kwargs)
