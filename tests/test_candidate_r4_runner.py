"""R4 matrix/activation and shared shortlist contracts, no native execution."""
import copy
import unittest
from unittest.mock import patch
from research.run_candidate_r4 import activation_ok, configurations, SOURCE, FAMILIES
from research.run_candidate_r2 import run_all


def result(net=100, pf=1.3, trades=200, dd=1):
    return dict(net=net, net_profit_factor=pf, trades=trades, native_equity_dd_pct=dd,
                monthly={f"2026-{m:02d}": {"net": 10} for m in range(1, 11)})


class R4RunnerTests(unittest.TestCase):
    def test_matrix_is_exact_unique_16(self):
        rows = configurations()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len({tag for _, _, tag in rows}), 16)
        self.assertTrue(all(mode == 5 for mode, _, _ in rows))
        self.assertEqual({tuple(sorted(p.items())) for _, p, _ in rows}, {
            tuple(sorted(dict(InpEntryStrength=e, InpStopLossATRMul=s, InpTakeProfitRRMul=t).items()))
            for e in (0, 1) for s in (1., 1.5) for t in (.75, 1., 1.5, 2.)})

    def test_activation_fail_closed(self):
        evidence = dict(round_label="R3", parity={"passed": True}, development=[
            dict(mode=m, parameters={"InpEntryStrength": p}, result=result(trades=3), eligible=False)
            for m in (1, 2, 3) for p in (0, 1)])
        self.assertTrue(activation_ok(evidence))
        for change in ("missing", "duplicate", "qualified", "parity", "override"):
            broken = copy.deepcopy(evidence)
            if change == "missing": broken["development"].pop()
            elif change == "duplicate": broken["development"][-1] = broken["development"][0]
            elif change == "qualified": broken["development"][0]["result"] = result()
            elif change == "parity": broken["parity"]["passed"] = False
            else: broken["development"][0]["parameters"]["InpStopLossATRMul"] = 1
            self.assertFalse(activation_ok(broken), change)

    def test_top_three_and_lock_before_confirmation(self):
        saved, calls = [], []
        def fake_execute(name, *args, **kwargs):
            calls.append(name)
            if "production" in name or name.endswith("baseline"): return result(net=0, dd=10)
            if "_dev_" in name:
                tag = name.split("_dev_")[1]
                index = next(i for i, row in enumerate(configurations()) if row[2] == tag)
                return result(net=100 + index, dd=1 + index / 100)
            if "confirmation" in name:
                self.assertTrue(any(path.name.endswith("selection_lock.json") for path, _ in saved))
            return result(net=200)
        with patch("research.run_candidate_r2.execute", side_effect=fake_execute), \
             patch("builtins.print"), \
             patch("research.run_candidate_r2.parity", return_value={"passed": True}), \
             patch("research.run_candidate_r2.save", side_effect=lambda p, v: saved.append((p, copy.deepcopy(v)))), \
             patch("research.run_candidate_r2.evaluate", return_value={"promotion": False}), \
             patch("research.run_candidate_r2.BASE", __import__("pathlib").Path("unused_r4_unit_only")):
            run_all("unit_r4", SOURCE, FAMILIES, "R4", configurations(), 3)
        validations = [n for n in calls if "_val_" in n]
        self.assertEqual(validations, ["unit_r4_val_" + row[2] for row in configurations()[:3]])
        complete = saved[-1][1]
        self.assertEqual(len(complete["development"]), 16)
        self.assertEqual(len(complete["development_shortlist"]), 3)
        self.assertEqual(len(complete["validation"]), 3)
        self.assertFalse(complete["promotion"])


if __name__ == "__main__":
    unittest.main()
