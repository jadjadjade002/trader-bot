"""Strict R12 standalone backend contract, no native terminal invocation."""
import pytest

from research import run_v25_native as native


def treatment(enabled=True):
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0,
                InpTakeProfitRRMul=3.0, InpStructuralRetest=enabled)


def test_off_parity_and_one_fixed_policy():
    text = native.settings("r12_test", 0, {}, r2=True, r12=True)
    assert "InpStructuralRetest=false\n" in text
    assert "InpStopLossATRMul=1.5\n" in text
    for enabled in (False, True):
        text = native.settings("r12_test", 1, treatment(enabled), r2=True, r12=True)
        assert f"InpStructuralRetest={str(enabled).lower()}\n" in text
        assert "InpLotSize=0.01\n" in text
        assert "InpMaxHoldBars=60\n" in text
        assert "InpEnableHardSL=true\n" in text
        assert "InpUseGridIndices=false\n" in text
        assert "InpDelayOneBar" not in text and "InpEnableCashRiskVeto" not in text


@pytest.mark.parametrize("field,value", [
    ("InpStructuralRetest", 0), ("InpStructuralRetest", 1),
    ("InpStructuralRetest", "true"), ("InpStructuralRetest", None),
    ("InpStopLossATRMul", 1.5), ("InpTakeProfitRRMul", 2.0),
    ("InpEntryStrength", 0), ("InpMaxHoldBars", 90),
    ("InpLotSize", 0.001), ("InpMinSLPoints", 1),
    ("InpEnableMarginGuard", False), ("InpEnableCashRiskVeto", True),
    ("InpDelayOneBar", True), ("InpStartHour", 12),
])
def test_profile_drift_rejected(field, value):
    overrides = treatment()
    overrides[field] = value
    with pytest.raises(ValueError):
        native.settings("r12_test", 1, overrides, r2=True, r12=True)


@pytest.mark.parametrize("profile", ["r5", "r6", "r7", "r8", "r10", "r11", "control_r1", "r9_hold"])
def test_profiles_cannot_mix(profile):
    kwargs = dict(r2=True, r12=True)
    kwargs[profile] = True
    with pytest.raises(ValueError):
        native.settings("r12_test", 1, treatment(), **kwargs)


@pytest.mark.parametrize("kwargs", [
    dict(r12=True), dict(r12=True, r2=True, optimize=True),
    dict(r12=True, r2=True, production=True), dict(r12=1, r2=True),
])
def test_activation_profile_rejected(kwargs):
    with pytest.raises(ValueError):
        native.settings("r12_test", 1, treatment(), **kwargs)


def test_mode0_cannot_enable_structural_policy():
    with pytest.raises(ValueError):
        native.settings("r12_test", 0, {"InpStructuralRetest": True}, r2=True, r12=True)


def test_fixture_requires_finalized_count_and_both_native_checks(monkeypatch):
    monkeypatch.setattr(native, "R12_NATIVE_FIXTURE_COUNT", None)
    with pytest.raises(ValueError, match="not finalized"):
        native.validate_r12_native_fixtures("", 0)
    monkeypatch.setattr(native, "R12_NATIVE_FIXTURE_COUNT", 37)
    good = "R12_NATIVE_FIXTURES_PASS checks=37 preset=2\nR12_NATIVE_PLATFORM_PROFIT_PASS checks=2"
    native.validate_r12_native_fixtures(good, 2)
    for bad in (good.replace("checks=37", "checks=36"), good.replace("preset=2", "preset=0"),
                good.replace("checks=2", "checks=1"), good + "\nR12_NATIVE_FIXTURE_FAIL bad",
                good + "\nR12_NATIVE_PLATFORM_PROFIT_FAIL checks=2"):
        with pytest.raises(ValueError):
            native.validate_r12_native_fixtures(bad, 2)
