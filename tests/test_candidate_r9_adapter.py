"""R9 is a narrow settings profile, not permission to change source or controls."""
import pytest

from research import run_v25_native as native


def params(hold):
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpMaxHoldBars=hold)


@pytest.mark.parametrize("hold", [60, 90])
def test_hold_profile_accepts_only_frozen_contract(hold):
    text = native.settings("r9_fixture", 1, params(hold),
                           r2=True, control_r1=True, r9_hold=True)
    assert f"InpMaxHoldBars={hold}\n" in text
    assert "InpLotSize=0.01\n" in text
    assert "InpUseGridIndices=false\n" in text
    assert "InpRequireEfficiency=" not in text
    assert "InpRequireNearMean=" not in text


@pytest.mark.parametrize("hold", [0, 59, 61, 120, 90.5, True, float("nan"), float("inf")])
def test_other_hold_values_rejected(hold):
    with pytest.raises(ValueError):
        native.settings("r9_fixture", 1, params(hold),
                        r2=True, control_r1=True, r9_hold=True)


@pytest.mark.parametrize("extra", [
    dict(InpEntryStrength=1), dict(InpStopLossATRMul=1.5),
    dict(InpTakeProfitRRMul=2.0), dict(InpLotSize=.02),
    dict(InpEnableCircuitBreaker=False), dict(InpUseGridIndices=True),
])
def test_other_inputs_cannot_be_swept(extra):
    with pytest.raises(ValueError):
        native.settings("r9_fixture", 1, params(90) | extra,
                        r2=True, control_r1=True, r9_hold=True)


@pytest.mark.parametrize("flags", [dict(), dict(r2=True), dict(r2=True, r8=True),
    dict(r2=True, control_r1=True, optimize=True),
    dict(r2=True, control_r1=True, production=True),
    dict(r2=True, control_r1=True, r7=True)])
def test_r9_rejects_conflicting_profiles(flags):
    with pytest.raises(ValueError):
        native.settings("r9_fixture", 1, params(90), r9_hold=True, **flags)


def test_legacy_control_contract_unchanged():
    old = {k: v for k, v in params(60).items() if k != "InpMaxHoldBars"}
    assert native.settings("r8_fixture", 1, old, r2=True, control_r1=True) == \
        native.settings("r8_fixture", 1, old, r2=True, control_r1=True, r9_hold=False)
    with pytest.raises(ValueError):
        native.settings("r8_fixture", 1, params(90), r2=True, control_r1=True)


@pytest.mark.parametrize("kwargs", [
    dict(candidate_source="research/ResearchCandidate_R8.mq5", mode=1),
    dict(candidate_source="research/ResearchControl_R1_R8.mq5", mode=0),
    dict(candidate_source="research/ResearchControl_R1_R8.mq5", mode=1, production=True),
    dict(candidate_source="research/ResearchControl_R1_R8.mq5", mode=1, optimize=True),
    dict(candidate_source="research/ResearchControl_R1_R8.mq5", mode=1, r9_hold=1),
])
def test_execute_rejects_before_native_or_filesystem_freeze(monkeypatch, kwargs):
    def forbidden(*args, **kw):
        pytest.fail("invalid profile reached runtime freeze")
    monkeypatch.setattr(native, "freeze", forbidden)
    with pytest.raises(ValueError):
        native.execute("r9_invalid", **(dict(r9_hold=True) | kwargs))
