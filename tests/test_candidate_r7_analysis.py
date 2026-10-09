from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research/analyze_candidate_r7.py"
spec = importlib.util.spec_from_file_location("analyze_candidate_r7", MODULE_PATH)
analyzer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(analyzer)

BAR = "2025.12.01 00:00:00"
BAR_MS = 1764547200000


def trade(open_msc, net, *, side="buy", reason=4, price=100):
    return dict(open_msc=open_msc, direction=side, entry_price=price, volume=.01,
                net=net, profit=net, commission=0.0, swap=0.0, fee=0.0,
                exit_reason=reason, close="2025-12-01T00:05:00")


def test_pair_conserves_matched_unmatched_zero_and_negative_pnl():
    control = dict(name="tp1", trades=[trade(1, 0), trade(2, -2, side="sell", reason=4)])
    treatment = dict(name="tp05", trades=[trade(1, -1), trade(2, -3, side="sell", reason=5),
                                          trade(3, 4, side="buy")])
    result = analyzer._pair(control, treatment)
    assert result["totals"]["control"]["zero"] == 1
    assert result["totals"]["control"]["losses"] == 1
    assert result["totals"]["treatment"]["losses"] == 2
    assert result["unmatched"]["treatment_count"] == 1
    assert result["decomposition"]["observed_total_delta"] == result["decomposition"]["reconstructed_total_delta"]
    assert "4->5" in result["paired"]["exit_reason_transitions"]


def test_duplicate_or_nonfinite_pair_key_fails_closed():
    same = trade(1, 1)
    with pytest.raises(ValueError, match="Duplicate"):
        analyzer._pair(dict(name="a", trades=[same, dict(same)]),
                       dict(name="b", trades=[same]))
    bad = trade(2, 1)
    bad["entry_price"] = float("nan")
    with pytest.raises(ValueError, match="Nonfinite"):
        analyzer.entry_key(bad)


def _write_csv(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _events(tmp_path: Path, *, tick=BAR_MS + 59900, deal_time=BAR_MS + 60100,
            deal_ticket=10, raw_ticket=None, side=1):
    name = "synthetic"
    raw_ticket = deal_ticket if raw_ticket is None else raw_ticket
    signals = [dict(bar=BAR, tick_msc=str(tick), mode="5", entry_strength="0",
                    signal=str(side), order_attempt="true", execution_gate="order_attempt")]
    raw = [dict(bar=BAR, tick_msc=str(tick), original=str(side), order_attempt="true",
                gate="order_attempt", retcode="10009", order_ticket="9",
                deal_ticket=str(raw_ticket))]
    _write_csv(tmp_path / f"{name}_signals.csv", signals)
    _write_csv(tmp_path / f"{name}_raw.csv", raw)
    deals = [
        dict(ticket=str(deal_ticket), position="20", time_msc=str(deal_time), type="0", entry="0",
             reason="0", magic="992300", symbol="XAUUSD", volume="0.01", price="100",
             profit="0", commission="0", swap="0", fee="0", comment=""),
        dict(ticket=str(deal_ticket + 1), position="20", time_msc=str(deal_time + 1000), type="1", entry="1",
             reason="4", magic="992300", symbol="XAUUSD", volume="0.01", price="99",
             profit="-1", commission="0", swap="0", fee="0", comment=""),
    ]
    from research.analyze_v23_backtest import parse_deals
    trades, _ = parse_deals(deals)
    return name, trades, deals


def test_exact_deal_ticket_join_allows_boundary_crossing_fill(tmp_path):
    name, trades, deals = _events(tmp_path)
    linked = analyzer._link_events(tmp_path, name, 0, trades, deals)
    assert linked[0]["entry_event"] == (BAR, BAR_MS + 59900)


@pytest.mark.parametrize("kwargs,match", [
    ({"raw_ticket": 999}, "Unmatched/duplicate"),
    ({"deal_time": BAR_MS + 59800}, "future"),
    ({"side": -1}, "wrong-side"),
    ({"raw_ticket": "nan"}, "Noninteger"),
    ({"tick": "nan"}, "Noninteger"),
    ({"side": "nan"}, "Noninteger"),
])
def test_mismatched_future_or_nonfinite_event_identity_fails(tmp_path, kwargs, match):
    name, trades, deals = _events(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=match):
        analyzer._link_events(tmp_path, name, 0, trades, deals)


def test_missing_opening_event_and_duplicate_signal_fail_closed(tmp_path):
    name, trades, deals = _events(tmp_path)
    _write_csv(tmp_path / f"{name}_raw.csv", [
        dict(bar=BAR, tick_msc=str(BAR_MS + 59900), original="0", order_attempt="false",
             gate="no_signal", retcode="0", order_ticket="0", deal_ticket="0")])
    with pytest.raises(ValueError, match="Signal/raw identity|Opening lacks"):
        analyzer._link_events(tmp_path, name, 0, trades, deals)
    name, trades, deals = _events(tmp_path)
    rows = csv.DictReader((tmp_path / f"{name}_signals.csv").open(encoding="utf-8"))
    duplicate = list(rows) * 2
    _write_csv(tmp_path / f"{name}_signals.csv", duplicate)
    with pytest.raises(ValueError, match="Duplicate signal"):
        analyzer._link_events(tmp_path, name, 0, trades, deals)
    name, trades, deals = _events(tmp_path)
    raw_rows = list(csv.DictReader((tmp_path / f"{name}_raw.csv").open(encoding="utf-8")))
    _write_csv(tmp_path / f"{name}_raw.csv", raw_rows * 2)
    with pytest.raises(ValueError, match="Duplicate raw"):
        analyzer._link_events(tmp_path, name, 0, trades, deals)


def test_artifact_sha_mismatch_is_hard_failure(tmp_path, monkeypatch):
    bad = tmp_path / "ResearchCandidate_R7.mq5"
    bad.write_text("stale", encoding="utf-8")
    monkeypatch.setattr(analyzer, "SOURCE", bad)
    with pytest.raises(ValueError, match="SHA mismatch"):
        analyzer._check_artifacts()


def test_signature_configuration_and_period_are_exact(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    directory = run_root / "r7_a_dev_p0_tp0p5"
    directory.mkdir(parents=True)
    overrides = dict(InpEntryStrength=0, InpStopLossATRMul=1.5, InpTakeProfitRRMul=.5)
    text = analyzer.native.settings("r7_a_dev_p0_tp0p5", 5, overrides, r2=True, r7=True)
    (directory / "r7_a_dev_p0_tp0p5.set").write_text(text, encoding="utf-16")
    sig = dict(start=analyzer.START, end=analyzer.DEV_END, mode=5,
        overrides=overrides,
        deposit=10000, optimize=False, production=False, delay_ms=200,
        source_sha=analyzer.SOURCE_SHA, binary_sha=analyzer.BINARY_SHA,
        set_sha=hashlib.sha256(text.encode("utf-16")).hexdigest(),
        runtime={"terminal64.exe": "A"}, tick_cache=[{"month": m} for m in analyzer.native.months(analyzer.START, analyzer.DEV_END)])
    reference = dict(runtime=sig["runtime"], tick_cache=[{"month": m} for m in analyzer.native.months(analyzer.START, analyzer.END)])
    expected_ref = reference["tick_cache"]
    reference["tick_cache"] = [dict(x) for x in expected_ref]
    monkeypatch.setattr(analyzer, "BASE", tmp_path)
    monkeypatch.setattr(analyzer.native, "verified_signature", lambda result, base: sig)
    result = dict(evidence_run="r7_a_dev_p0_tp0p5")
    assert analyzer._expect_sig(result, result["evidence_run"], 5, sig["overrides"],
                                analyzer.DEV_END, reference) == sig
    with pytest.raises(ValueError, match="signature drift"):
        analyzer._expect_sig(result, result["evidence_run"], 5,
                             dict(sig["overrides"], InpTakeProfitRRMul=.6), analyzer.DEV_END, reference)
    with pytest.raises(ValueError, match="signature drift"):
        bad_sig = dict(sig, start="2026.01.01")
        monkeypatch.setattr(analyzer.native, "verified_signature", lambda result, base: bad_sig)
        analyzer._expect_sig(result, result["evidence_run"], 5, sig["overrides"], analyzer.DEV_END, reference)
