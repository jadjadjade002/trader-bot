from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research/ResearchCandidate_R1.mq5"
GENERATOR = ROOT / "research/build_control_r1_r8.py"
PINNED = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
spec = importlib.util.spec_from_file_location("build_control_r1_r8", GENERATOR)
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(builder)


def source_text() -> str:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest().upper() == PINNED
    return raw.decode("utf-8-sig").replace("\r\n", "\n")


def test_exact_pinned_parent_and_only_three_metadata_export_replacements():
    before = PARENT.read_bytes()
    parent = source_text()
    clone = builder.build(parent)
    assert PARENT.read_bytes() == before
    expected = parent.replace(builder.OLD_VERSION, builder.NEW_VERSION, 1)
    expected = expected.replace(builder.OLD_DESCRIPTION, builder.NEW_DESCRIPTION, 1)
    expected = expected.replace(builder.OLD_EXPORT, builder.NEW_EXPORT, 1)
    assert clone == expected


def test_online_and_optimization_behavior_functions_are_byte_identical():
    parent, clone = source_text(), builder.build(source_text())
    for name in ("OnTick", "OnInit", "OnDeinit", "OriginalOnTick", "CandidateSignal",
                 "ManageOpenPositions", "HasOpenPosition", "CheckMargin",
                 "IsCircuitBreakerActive", "ExportOptimizationFrame"):
        assert builder.function(parent, name) == builder.function(clone, name)
    assert "if(!HistorySelect(0,TimeCurrent()))return -DBL_MAX;" in builder.function(clone, "ExportOptimizationFrame")


def test_only_post_run_on_tester_export_uses_fixed_upper_bound():
    parent, clone = source_text(), builder.build(source_text())
    assert parent.count(builder.OLD_EXPORT) == 1
    assert clone.count(builder.OLD_EXPORT) == 0
    assert clone.count(builder.NEW_EXPORT) == 1
    expected = builder.replace_once(builder.function(parent, "OnTester"), builder.OLD_EXPORT, builder.NEW_EXPORT)
    assert builder.function(clone, "OnTester") == expected


def test_forced_close_after_last_quote_is_in_export_range_not_online_logic():
    last_quote = datetime.fromisoformat("2026-05-29T22:59:59")
    forced_close = datetime.fromisoformat("2026-05-29T23:55:00.020")
    export_upper = datetime.fromisoformat("3000-12-31T23:59:59")
    assert forced_close > last_quote
    assert forced_close <= export_upper
    clone = builder.build(source_text())
    assert builder.NEW_EXPORT in builder.function(clone, "OnTester")
    assert builder.function(clone, "OnTick") == builder.function(source_text(), "OnTick")


def test_generator_rejects_parent_drift_and_ambiguous_export_anchor():
    with pytest.raises(ValueError, match="post-run deals-export"):
        builder.build(source_text().replace(builder.OLD_EXPORT, "bool historyOK=true;"))
    with pytest.raises(ValueError, match="Expected one exact anchor"):
        builder.replace_once(source_text() + builder.OLD_VERSION, builder.OLD_VERSION, builder.NEW_VERSION)


def test_metadata_is_tester_only_and_does_not_relabel_release():
    clone = builder.build(source_text())
    assert builder.NEW_VERSION in clone
    assert "Research Control R1 for R8 export integrity, tester-only. Not a V25 release." in clone
    assert "Profitability unverified" not in clone
