"""Post-update R6 must stay in its explicit batch and validate before selection."""
from unittest.mock import patch

import pytest

from research import run_candidate_r6 as runner


def test_unapproved_root_rejected_before_any_launch():
    with patch.object(runner, "_call") as launch:
        with pytest.raises(ValueError, match="approved postupdate"):
            runner.run_all("r6_test", 123456789, evidence_base=runner.ROOT / "reports/arbitrary")
        launch.assert_not_called()


def test_selected_root_contains_all_calls_and_saved_records():
    calls, saved, checked = [], [], []
    control = dict(evidence_run="r5_d_baseline")
    def call(name, *args, **kwargs):
        calls.append((name, kwargs))
        return dict(evidence_run=name, net=-1, net_profit_factor=.5,
                    trades=1, native_equity_dd_pct=1)
    def verify(left, right, **kwargs):
        checked.append((left, right, kwargs))
        return dict(passed=True)
    with patch.object(runner, "accepted_r5_mode0", return_value=control) as lookup, \
         patch.object(runner, "accepted_v24_production") as old, \
         patch.object(runner, "_call", side_effect=call), \
         patch.object(runner.native, "parity", return_value=dict(passed=True)) as parity, \
         patch.object(runner.native, "verify_environment", side_effect=verify), \
         patch.object(runner, "save", side_effect=lambda path, value: saved.append(path)):
        progress = runner.run_all("r6_test", 123456789, evidence_base=runner.POSTUPDATE_BASE)
    old.assert_not_called()
    lookup.assert_called_once_with(123456789, evidence_base=runner.POSTUPDATE_BASE.resolve())
    assert len(calls) == 6 and len(checked) == 5
    assert all(kwargs["evidence_base"] == runner.POSTUPDATE_BASE.resolve() for _, kwargs in calls)
    assert all(path.parent == runner.POSTUPDATE_BASE.resolve() for path in saved)
    assert parity.call_args.kwargs["production_base"] == runner.POSTUPDATE_BASE.resolve()
    assert progress["parity_control_run"] == "r5_d_baseline"
    assert progress["parity_control_root"] == "reports/v25_research_20261008_postupdate"
    assert progress["promotion"] is False


def test_cache_drift_prevents_qualification_or_shortlist():
    def call(name, *args, **kwargs):
        return dict(evidence_run=name)
    with patch.object(runner, "accepted_r5_mode0", return_value=dict(evidence_run="r5_d_baseline")), \
         patch.object(runner, "_call", side_effect=call), \
         patch.object(runner.native, "parity", return_value=dict(passed=True)), \
         patch.object(runner.native, "verify_environment", side_effect=ValueError("Tick cache differs")), \
         patch.object(runner, "save"), patch.object(runner, "qualify") as qualify:
        with pytest.raises(ValueError, match="Tick cache differs"):
            runner.run_all("r6_test", 123456789, evidence_base=runner.POSTUPDATE_BASE)
        qualify.assert_not_called()
