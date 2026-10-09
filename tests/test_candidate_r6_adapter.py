import inspect
from unittest import TestCase
from research import run_v25_native as native


class R6AdapterTests(TestCase):
    def test_fixed_four_cells_and_parity_serialize(self):
        for mode in (6, 7):
            for preset in (0, 1):
                with self.subTest(mode=mode, preset=preset):
                    text = native.settings("r6_check", mode, {"InpEntryStrength": preset}, r2=True, r6=True)
                    self.assertIn(f"InpExperimentMode={mode}\n", text)
                    self.assertIn(f"InpEntryStrength={preset}\n", text)
                    self.assertIn("InpRequireM1Alignment=false\n", text)
                    self.assertIn("InpStopLossATRMul=1.5\n", text)
                    self.assertIn("InpTakeProfitRRMul=2.0\n", text)
        native.settings("r6_baseline", 0, {}, r2=True, r6=True)

    def test_scope_cannot_broaden_older_rounds(self):
        for kwargs in ({"r6": True}, {"r2": True, "r5": True, "r6": True},
                       {"r2": True, "r6": True, "production": True},
                       {"r2": True, "r6": True, "optimize": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                native.settings("r6_check", 6, {}, **kwargs)
        for mode in (1, 2, 3, 4, 5, 8):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                native.settings("r6_check", mode, {}, r2=True, r6=True)

    def test_cell_controls_cannot_be_changed(self):
        for override in ({"InpRequireM1Alignment": True}, {"InpLotSize": 0.1},
                         {"InpStopLossATRMul": 2}, {"InpTakeProfitRRMul": 1},
                         {"InpEntryStrength": 2}, {"InpEntryStrength": 0.5},
                         {"InpEntryStrength": "NaN"}, {"InpExperimentMode": 5}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                native.settings("r6_check", 6, override, r2=True, r6=True)
        with self.assertRaises(ValueError):
            native.settings("r6_baseline", 0, {"InpEntryStrength": 1}, r2=True, r6=True)

    def test_exact_native_fixture_contract_and_components(self):
        source = inspect.getsource(native.execute)
        self.assertIn("R5_NATIVE_FIXTURES_PASS checks=27", source)
        self.assertIn("R6_NATIVE_FIXTURES_PASS checks=20", source)
        self.assertIn("R6_NATIVE_FIXTURES_TOTAL checks=47 R5=27 R6=20", source)
        self.assertIn('"R5_NATIVE_FIXTURE_FAIL" in journal', source)
        self.assertIn('native_mql_fixture_components={"R5": 27, "R6": 20}', source)
