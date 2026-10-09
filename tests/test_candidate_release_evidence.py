from copy import deepcopy
from unittest import TestCase
from research.candidate_release_evidence import evaluate


def passing():
    return dict(qualified=True, full=dict(extra_cost_stress={"0.2": 10}),
                delay500=dict(net=10, net_profit_factor=1.2),
                capital70=dict(net=5, native_stopout=False))


class ReleaseEvidenceTests(TestCase):
    def test_all_checks_needed_but_never_deployment_authority(self):
        result = evaluate(passing())
        self.assertTrue(result["historically_robust"])
        self.assertFalse(result["promotion"])
        self.assertFalse(result["genuinely_unseen_oos"])
        self.assertTrue(result["independent_review_required"])

    def test_qualified_alone_not_enough(self):
        self.assertFalse(evaluate(dict(qualified=True))["historically_robust"])

    def test_missing_or_nonfinite_evidence_fails_closed(self):
        for value in (None, float("nan"), float("inf"), -1, 0, True):
            e = passing()
            e["full"]["extra_cost_stress"]["0.2"] = value
            self.assertFalse(evaluate(e)["historically_robust"])

    def test_each_economic_check_blocks(self):
        for group, key, value in (("delay500", "net", -1), ("delay500", "net_profit_factor", 1.09),
                                  ("capital70", "net", -1), ("capital70", "native_stopout", True)):
            e = deepcopy(passing())
            e[group][key] = value
            self.assertFalse(evaluate(e)["historically_robust"])
