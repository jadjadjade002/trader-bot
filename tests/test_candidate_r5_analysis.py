"""Strict read-only R5 attribution validation tests."""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from research import analyze_candidate_r5 as analysis


@pytest.fixture
def local_tmp_path():
    with tempfile.TemporaryDirectory(prefix=".r5_analysis_test_", dir=Path(__file__).resolve().parents[1]) as temp:
        yield Path(temp)


def _set_values(name, preset=0, aligned=False):
    values = dict(analysis.FIXED_SET)
    values.update(InpRunTag=name, InpExperimentMode="5", InpEntryStrength=str(preset),
                  InpStopLossATRMul="1.5", InpTakeProfitRRMul="1.0",
                  InpRequireM1Alignment=str(aligned).lower())
    return values


def _signal(name, preset=0, *, bar="2025.12.01 01:00:00", tick_msc=None,
            features="true", ema9="101.0", ema20="100.0", status="context_evaluated"):
    if tick_msc is None:
        stamp = datetime.strptime(bar, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
        tick_msc = int(stamp.timestamp() * 1000) + 1000
    row = {key: "" for key in analysis.SIGNAL_REQUIRED}
    row.update(bar=bar, tick_msc=str(tick_msc), mode="5", entry_strength=str(preset),
        signal="1", trend="1", reason="r2_candidate_signal_m1_aligned", execution_gate="order_attempt",
        held_before="false", order_attempt="true", features_evaluated=features,
        opportunity_status=status, m1_ema9=ema9, m1_ema20=ema20, m5_ema20="100.0",
        m5_ema50="99.0", m5_ema20_past6="98.0", m5_slope_5bar_delta="2.0",
        m1_atr="1.0", m5_atr="2.0", signed_displacement_atr_5bars="-1.5",
        quote_bid="100.0", quote_ask="100.1", spread="0.1",
        initial_sl_distance="1.5", initial_tp_distance="1.5",
        initial_sl_price="98.6", initial_tp_price="101.6", session_id="n/a",
        session_endpoint="n/a", time_to_close="n/a", signal_bar_open="99.0",
        signal_bar_high="101.0", signal_bar_low="98.0", signal_bar_close="100.5",
        signal_body_atr="1.5", close_location_from_low="0.83333333")
    return row


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _control_manifest(policy, prefix, r5_root="reports/v25_research_20261008"):
    fresh = policy == "fresh_same_cache"
    names = {str(preset): (f"{prefix}_r4_control_p{preset}" if fresh
                           else analysis.R4_RUNS[preset]) for preset in (0, 1)}
    root = r5_root if fresh else "reports/v25_research_20261007"
    provenance = {str(preset): dict(kind="fresh_native" if fresh else "accepted_reuse",
        evidence_run=names[str(preset)], evidence_root=root,
        source_sha256=analysis.R4_SOURCE_SHA256, signature_sha256="A" * 64,
        native_run_id=names[str(preset)] if fresh else None) for preset in (0, 1)}
    alias = "r5_base" if fresh else "r4_base"
    return dict(control_policy=policy, control_mapping=names,
                control_roots={"baseline_production": alias, "r4_controls": alias},
                evidence_roots={"r4_base": "reports/v25_research_20261007", "r5_base": r5_root},
                baseline_control_run=f"{prefix}_production_v24" if fresh else "r1_b_production_v24",
                r4_control_provenance=provenance)


def _make_r5_run(root: Path, name="r5_a_dev_p0_a0_c0", preset=0, aligned=False):
    run_dir = root / "runs" / name
    run_dir.mkdir(parents=True)
    runtime = {key: f"{index+1:064X}" for index, key in enumerate(analysis.RUNTIME_NAMES)}
    (root / "runtime_freeze.json").write_text(json.dumps(runtime), encoding="utf-8")
    settings = _set_values(name, preset, aligned)
    settings_text = "".join(f"{key}={value}\n" for key, value in settings.items())
    set_path = run_dir / f"{name}.set"
    set_path.write_text(settings_text, encoding="utf-16")
    set_sha = hashlib.sha256(settings_text.encode("utf-16")).hexdigest()
    signature = dict(start=analysis.PERIOD_START, end=analysis.PERIOD_END, mode=5,
        overrides={"InpEntryStrength": preset, "InpStopLossATRMul": 1.5,
                    "InpTakeProfitRRMul": 1.0, "InpRequireM1Alignment": aligned},
        deposit=10000, optimize=False, production=False, delay_ms=200,
        runtime=runtime, source_sha=analysis.R5_SOURCE_SHA256,
        binary_sha=analysis.R5_BINARY_SHA256, set_sha=set_sha,
        tick_cache=[dict(month=int(month.replace("-", "")), bytes=2048,
                         sha256=f"{index+1:064X}") for index, month in enumerate(analysis.MONTHS)])
    (run_dir / "started.json").write_text(json.dumps(dict(signature=signature,
        started_utc="2026-10-08T00:00:00+00:00")), encoding="utf-8")
    deal_fields = ("ticket", "position", "time_msc", "type", "entry", "reason", "magic",
                   "symbol", "volume", "price", "profit", "commission", "swap", "fee", "comment")
    deals = [
        dict(ticket="1", position="0", time_msc="1764547200000", type="2", entry="0", reason="0",
             magic="0", symbol="", volume="0", price="0", profit="10000", commission="0", swap="0", fee="0", comment=""),
        dict(ticket="2", position="2", time_msc="1764550801000", type="0", entry="0", reason="3",
             magic="992300", symbol="XAUUSD", volume="0.01", price="100.1", profit="0", commission="0", swap="0", fee="0", comment="Buy"),
        dict(ticket="3", position="2", time_msc="1764550810000", type="1", entry="1", reason="4",
             magic="992300", symbol="XAUUSD", volume="0.01", price="98.6", profit="-1.5", commission="0", swap="0", fee="0", comment="sl"),
    ]
    with (run_dir / f"{name}_deals.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=deal_fields)
        writer.writeheader()
        writer.writerows(deals)
    with (run_dir / f"{name}_spec.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("key", "value"))
        writer.writeheader()
        writer.writerows((dict(key="history_export_ok", value="true"),
                          dict(key="final_balance", value="9998.5")))
    raw_fields = ("bar", "tick_msc", "original", "closeback", "dc_low", "dc_high", "atr",
                  "break_close", "retest_open", "retest_close", "retest_high", "retest_low",
                  "bid", "ask", "held_before", "cooldown_before", "gate", "order_attempt",
                  "retcode", "order_ticket", "deal_ticket")
    with (run_dir / f"{name}_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=raw_fields)
        writer.writeheader()
        writer.writerow(dict(bar="2025.12.01 01:00:00", tick_msc="1764550801000",
            original="1", held_before="false", gate="order_attempt", order_attempt="true",
            retcode="10009", order_ticket="10", deal_ticket="2"))
    (run_dir / f"{name}.htm").write_text(
        "<table><tr><td>History Quality:</td><td>100% real ticks</td></tr>"
        "<tr><td>Period:</td><td>M1 (2025.12.01 - 2026.06.01)</td></tr>"
        "<tr><td>Total Trades:</td><td>1</td></tr>"
        "<tr><td>Total Net Profit:</td><td>-1.50</td></tr></table>", encoding="utf-8")
    _write_csv(run_dir / f"{name}_signals.csv", [_signal(name, preset)])
    accepted = dict(signature=signature, result=dict(
        evidence_run=name, cache_hashes_verified=True, terminal_cache_read_warnings=[],
        native_mql_fixture_checks=27, trades=1, net=-1.5, final_balance=9998.5,
        native={"History Quality": "100% real ticks", "Period": "M1 (2025.12.01 - 2026.06.01)",
                "Total Trades": "1", "Total Net Profit": "-1.50"}))
    accepted_path = run_dir / "accepted.json"
    accepted_path.write_text(json.dumps(accepted), encoding="utf-8")
    return run_dir


def test_missing_accepted_record_rejects_partial_run(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = root / "runs" / "r5_a_dev_p0_a0_c0"
    run_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="Run not accepted"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_stored_signature_mismatch_fails_hard(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    accepted_path = run_dir / "accepted.json"
    accepted = json.loads(accepted_path.read_text())
    accepted["signature"]["source_sha"] = "0" * 64
    accepted_path.write_text(json.dumps(accepted), encoding="utf-8")
    with pytest.raises(ValueError, match="Stored source/binary signature mismatch"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_started_signature_drift_fails_hard(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    started = json.loads((run_dir / "started.json").read_text())
    started["signature"]["delay_ms"] = 500
    (run_dir / "started.json").write_text(json.dumps(started), encoding="utf-8")
    with pytest.raises(ValueError, match="Started/accepted signature mismatch"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_nonfinite_feature_fails_hard(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_signals.csv"
    rows = analysis.csv_rows(path)
    rows[0]["m1_ema9"] = "NaN"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="Nonfinite"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_stale_signal_context_fails_hard(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_signals.csv"
    rows = analysis.csv_rows(path)
    rows[0]["tick_msc"] = str(int(rows[0]["tick_msc"]) + 61000)
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="Stale or unordered signal context"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_missing_features_do_not_become_numeric_zero(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_signals.csv"
    rows = analysis.csv_rows(path)
    rows[0]["features_evaluated"] = "false"
    rows[0]["opportunity_status"] = "blocked_before_context"
    rows[0]["m1_ema9"] = "0"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="Unavailable/stale feature values must be blank"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_exact_deal_ticket_links_diagnostics_to_open_position(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    run = analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)
    contexts = analysis._signal_entries(run)
    context = next(iter(contexts.values()))
    assert context["signal_tick_msc"] == 1764550801000


def test_missing_raw_export_fails_closed(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    (run_dir / f"{run_dir.name}_raw.csv").unlink()
    with pytest.raises(ValueError, match="raw execution export missing"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_mismatched_raw_deal_ticket_fails_closed(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_raw.csv"
    rows = analysis.csv_rows(path)
    rows[0]["deal_ticket"] = "999"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="Raw deal ticket has no matching opening deal"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_duplicate_raw_event_fails_closed(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_raw.csv"
    rows = analysis.csv_rows(path)
    _write_csv(path, rows + rows)
    with pytest.raises(ValueError, match="Stale or unordered raw execution context"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_duplicate_deal_ticket_across_events_is_ambiguous(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    for suffix in ("_raw.csv", "_signals.csv"):
        path = run_dir / f"{run_dir.name}{suffix}"
        rows = analysis.csv_rows(path)
        duplicate = dict(rows[0])
        duplicate["bar"] = "2025.12.01 01:01:00"
        duplicate["tick_msc"] = "1764550861000"
        _write_csv(path, rows + [duplicate])
    with pytest.raises(ValueError, match="linked by multiple raw events"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_raw_signal_side_attempt_and_mode_consistency(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    raw_path = run_dir / f"{run_dir.name}_raw.csv"
    raw = analysis.csv_rows(raw_path)
    raw[0]["original"] = "-1"
    _write_csv(raw_path, raw)
    with pytest.raises(ValueError, match="Raw/signal event mismatch"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)

    raw[0]["original"] = "1"
    raw[0]["order_attempt"] = "false"
    _write_csv(raw_path, raw)
    with pytest.raises(ValueError, match="Raw attempt/gate mismatch"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)

    signal_path = run_dir / f"{run_dir.name}_signals.csv"
    signals = analysis.csv_rows(signal_path)
    signals[0]["mode"] = "4"
    _write_csv(signal_path, signals)
    with pytest.raises(ValueError, match="Signal row identity mismatch"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_future_raw_event_fails_closed(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    for suffix in ("_raw.csv", "_signals.csv"):
        path = run_dir / f"{run_dir.name}{suffix}"
        rows = analysis.csv_rows(path)
        rows[0]["tick_msc"] = "1764550802000"
        _write_csv(path, rows)
    with pytest.raises(ValueError, match="Opening deal predates its raw event"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_exact_deal_link_allows_boundary_crossing_fill(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_deals.csv"
    rows = analysis.csv_rows(path)
    rows[1]["time_msc"] = "1764550861000"
    rows[2]["time_msc"] = "1764550870000"
    _write_csv(path, rows)
    run = analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)
    context = next(iter(analysis._signal_entries(run).values()))
    assert context["signal_tick_msc"] < 1764550861000


@pytest.mark.parametrize("field,value", [
    ("mode", "5.5"), ("entry_strength", "0.5"),
    ("signal", "1.5"), ("trend", "1.5"),
    ("tick_msc", "1764550801000.5"),
])
def test_fractional_signal_identifiers_are_not_silently_truncated(field, value):
    row = _signal("fractional")
    row[field] = value
    with pytest.raises(ValueError, match="Noninteger value"):
        analysis.validate_signals([row], "fractional", 0)


@pytest.mark.parametrize("field,value", [("signal", "2"), ("trend", "-2")])
def test_signal_directions_reject_out_of_domain_integers(field, value):
    row = _signal("direction_domain")
    row[field] = value
    with pytest.raises(ValueError, match="Signal/trend side outside"):
        analysis.validate_signals([row], "direction_domain", 0)


def test_opening_volume_outside_fixed_contract_fails_closed(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_deals.csv"
    rows = analysis.csv_rows(path)
    rows[1]["volume"] = "0.005"
    rows[2]["volume"] = "0.005"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="fixed 0.01-lot contract"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_multiple_opening_fills_do_not_get_one_guessed_signal(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    path = run_dir / f"{run_dir.name}_deals.csv"
    rows = analysis.csv_rows(path)
    extra = dict(rows[1], ticket="4", volume="0.005", time_msc="1764550801500")
    rows[1]["volume"] = "0.005"
    _write_csv(path, rows + [extra])
    with pytest.raises(ValueError, match="Unsupported concurrent/add-on entry"):
        analysis._load_run(root, run_dir.name, 0, aligned=False, load_signals=True)


def test_pairing_reconciles_matched_and_unmatched_economics():
    base_bar = int(datetime(2025, 12, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    def trade(position, minute, price, net):
        opened = base_bar + minute * 60000 + 1000
        return dict(position=position, open_msc=opened, close_msc=opened+10000,
            direction="buy", entry_price=price, exit_price=price+net, volume=0.01,
            net=net, profit=net, commission=0.0, swap=0.0, fee=0.0,
            exit_reason=5, close="2025-12-01T01:00:10")
    a0trades = [trade(1, 0, 100.1, 1.0), trade(2, 1, 101.1, -2.0)]
    a1trades = [trade(3, 0, 100.1, 1.5), trade(4, 2, 102.1, 3.0)]
    def context(trades):
        signals = []
        entry_event_keys = {}
        for t in trades:
            bar = (t["open_msc"] // 60000) * 60000
            tick = bar+500
            event_key = (bar, tick)
            entry_event_keys[analysis._entry_key(t)] = event_key
            signals.append(dict(_bar_msc=bar, _tick_msc=tick, _signal=1, _attempt=True, _features=True,
                opportunity_status="context_evaluated",
                _m1_relation="up", m1_ema9=101.0, m1_ema20=100.0,
                m5_ema20=100.0, m5_ema50=99.0, _trend=1,
                bar=datetime.fromtimestamp(bar/1000, timezone.utc).strftime("%Y.%m.%d %H:%M:%S")))
        return dict(trades=trades, signals=signals, name="test", entry_event_keys=entry_event_keys)
    result = analysis._pair_comparison(context(a0trades), context(a1trades))
    assert result["paired"]["count"] == 1
    assert result["unmatched"]["a0_count"] == result["unmatched"]["a1_count"] == 1
    assert result["decomposition"]["observed_total_delta"] == 5.5


def test_native_html_must_match_accepted_summary(local_tmp_path):
    root = local_tmp_path / "evidence"
    run_dir = _make_r5_run(root)
    report = run_dir / f"{run_dir.name}.htm"
    report.write_text(report.read_text(encoding="utf-8").replace("-1.50", "-2.50"), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from native HTML"):
        analysis._load_run(root, run_dir.name, 0, aligned=False)


def test_retry_prefix_mapping_comes_from_manifest_and_requires_controls(local_tmp_path):
    prefix = "r5_b"
    rows = []
    parity = {}
    for tag, (preset, aligned) in analysis.R5_CONFIGS.items():
        name = f"{prefix}_dev_{tag}_retry1"
        rows.append(dict(config_tag=tag, mode=5, parameters={
            "InpEntryStrength": preset, "InpRequireM1Alignment": aligned,
            "InpStopLossATRMul": 1.5, "InpTakeProfitRRMul": 1.0},
            result={"evidence_run": name}))
        if not aligned:
            parity[str(preset)] = dict(passed=True,
                r4_control=analysis.R4_RUNS[preset], r5_run=name)
    manifest = dict(
        round_label="R5", schedule_status="UNRUN_SCHEDULE_UNVERIFIED",
        development=rows, r4_control_parity=parity, **_control_manifest("legacy_r4", prefix))
    for preset in (0, 1):
        manifest["r4_control_parity"][str(preset)]["control_root"] = "r4_base"
        manifest["r4_control_parity"][str(preset)]["control_provenance"] = manifest["r4_control_provenance"][str(preset)]
    (local_tmp_path / "r5_b_progress.json").write_text(json.dumps(manifest), encoding="utf-8")
    mapped = analysis._r5_run_mapping(local_tmp_path, prefix)
    assert mapped["p0_a0"][0] == "r5_b_dev_p0_a0_c0_retry1"
    assert mapped["p1_a1"][0] == "r5_b_dev_p1_a1_c0_retry1"
    del parity["0"]
    manifest["r4_control_parity"] = parity
    (local_tmp_path / "r5_b_progress.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="parity missing"):
        analysis._r5_run_mapping(local_tmp_path, prefix)


def test_fresh_control_mapping_is_exact_and_uses_same_evidence_root(local_tmp_path):
    prefix = "r5_f"
    progress = _control_manifest("fresh_same_cache", prefix,
        r5_root="reports/v25_research_20261008_postupdate")
    policy, mapping = analysis._r5_control_mapping(progress, prefix)
    assert policy == "fresh_same_cache"
    assert mapping == {0: "r5_f_r4_control_p0", 1: "r5_f_r4_control_p1"}
    assert analysis._control_root(policy, local_tmp_path / "legacy", local_tmp_path) == local_tmp_path
    analysis._validate_declared_roots(progress,
        analysis.ROOT / "reports/v25_research_20261007",
        analysis.ROOT / "reports/v25_research_20261008_postupdate")
    with pytest.raises(ValueError, match="Caller evidence roots differ"):
        analysis._validate_declared_roots(progress,
            analysis.ROOT / "reports/v25_research_20261007", analysis.ROOT / "reports/not_approved")


def test_legacy_control_mapping_uses_fixed_r4_evidence_root(local_tmp_path):
    progress = _control_manifest("legacy_r4", "r5_a")
    policy, mapping = analysis._r5_control_mapping(progress, "r5_a")
    assert policy == "legacy_r4"
    assert mapping == analysis.R4_RUNS
    assert analysis._control_root(policy, local_tmp_path / "legacy", local_tmp_path) == local_tmp_path / "legacy"


def test_manifest_cannot_choose_arbitrary_r5_evidence_root():
    progress = _control_manifest("fresh_same_cache", "r5_f",
        r5_root="reports/external_or_arbitrary")
    with pytest.raises(ValueError, match="R5 evidence root is not approved"):
        analysis._r5_control_mapping(progress, "r5_f")


@pytest.mark.parametrize("policy,mapping_override,root_override", [
    ("fresh_same_cache", {"0": "../outside", "1": "r5_f_r4_control_p1"}, None),
    ("fresh_same_cache", None, "../outside"),
    ("legacy_r4", {"0": "r5_a_r4_control_p0", "1": analysis.R4_RUNS[1]}, None),
])
def test_control_mapping_or_evidence_root_policy_drift_fails_closed(
        policy, mapping_override, root_override):
    progress = _control_manifest(policy, "r5_f" if policy == "fresh_same_cache" else "r5_a")
    if mapping_override is not None:
        progress["control_mapping"] = mapping_override
    if root_override is not None:
        progress["r4_control_provenance"]["0"]["evidence_root"] = root_override
    with pytest.raises(ValueError, match="control mapping|control provenance"):
        analysis._r5_control_mapping(progress, "r5_f" if policy == "fresh_same_cache" else "r5_a")


def test_cross_run_cache_and_runtime_must_match():
    first = {"name": "a", "signature": {"runtime": {"terminal64.exe": "a"},
        "tick_cache": [{"month": 202512, "sha256": "a"}]}}
    second = {"name": "b", "signature": {"runtime": {"terminal64.exe": "b"},
        "tick_cache": [{"month": 202512, "sha256": "a"}]}}
    with pytest.raises(ValueError, match="Runtime differs"):
        analysis._validate_cross_run_environment([first, second])
    second["signature"]["runtime"] = first["signature"]["runtime"]
    second["signature"]["tick_cache"] = [{"month": 202512, "sha256": "different"}]
    with pytest.raises(ValueError, match="Tick cache manifest differs"):
        analysis._validate_cross_run_environment([first, second])


def test_flat_bar_can_have_unavailable_close_location():
    row = _signal("flat")
    row.update(signal_bar_open="100", signal_bar_high="100", signal_bar_low="100",
               signal_bar_close="100", signal_body_atr="0", close_location_from_low="")
    assert analysis.validate_signals([row], "flat", 0)[0]["_features"] is True
