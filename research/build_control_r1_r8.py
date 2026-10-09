"""Generate R8's R1 reporting control from hash-pinned R1 source."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research" / "ResearchCandidate_R1.mq5"
OUTPUT = ROOT / "research" / "ResearchControl_R1_R8.mq5"
PARENT_SHA256 = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
OLD_VERSION = '#property version   "24.90"'
NEW_VERSION = '#property version   "24.91"'
OLD_DESCRIPTION = '#property description "Research Candidate R1, tester-only. Not a V25 release. Profitability unverified."'
NEW_DESCRIPTION = '#property description "Research Control R1 for R8 export integrity, tester-only. Not a V25 release."'
OLD_EXPORT = "bool historyOK=HistorySelect(0,TimeCurrent());"
NEW_EXPORT = "bool historyOK=HistorySelect(0,D'3000.12.31 23:59:59');"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Expected one exact anchor, found {text.count(old)}: {old!r}")
    return text.replace(old, new, 1)


def function(text: str, name: str) -> str:
    match = re.search(
        rf"(?m)^[ \t]*(?:[\w*&]+[ \t]+)+{re.escape(name)}[ \t]*\([^;{{}}]*\)\s*\{{",
        text,
    )
    if not match:
        raise ValueError(f"Missing function: {name}")
    start, brace = match.start(), match.end() - 1
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError(f"Unterminated function: {name}")


def build(source: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    if source.count(OLD_EXPORT) != 1:
        raise ValueError("Expected one post-run deals-export HistorySelect anchor")
    text = replace_once(source, OLD_VERSION, NEW_VERSION)
    text = replace_once(text, OLD_DESCRIPTION, NEW_DESCRIPTION)
    text = replace_once(text, OLD_EXPORT, NEW_EXPORT)
    expected = source.replace(OLD_VERSION, NEW_VERSION, 1)
    expected = expected.replace(OLD_DESCRIPTION, NEW_DESCRIPTION, 1)
    expected = expected.replace(OLD_EXPORT, NEW_EXPORT, 1)
    if text != expected:
        raise ValueError("R8 R1 control differs beyond metadata and post-run export bound")
    if text.count(NEW_EXPORT) != 1 or text.count(OLD_EXPORT):
        raise ValueError("R8 export-bound occurrence count changed")
    for name in ("OnTick", "OnInit", "OnDeinit", "OriginalOnTick", "CandidateSignal",
                 "ManageOpenPositions", "HasOpenPosition", "CheckMargin",
                 "IsCircuitBreakerActive", "ExportOptimizationFrame"):
        if function(source, name) != function(text, name):
            raise ValueError(f"R8 reporting control changed frozen function: {name}")
    expected_tester = replace_once(function(source, "OnTester"), OLD_EXPORT, NEW_EXPORT)
    if function(text, "OnTester") != expected_tester:
        raise ValueError("OnTester changed beyond its post-run export upper bound")
    if "if(!HistorySelect(0,TimeCurrent()))return -DBL_MAX;" not in function(text, "ExportOptimizationFrame"):
        raise ValueError("Optimization fitness HistorySelect changed")
    return text


def main() -> None:
    raw = PARENT.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != PARENT_SHA256:
        raise SystemExit(f"Pinned R1 source SHA256 mismatch: {digest}")
    generated = build(raw.decode("utf-8-sig"))
    OUTPUT.write_text(generated, encoding="utf-8", newline="\n")
    print(f"generated={OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(generated.encode()).hexdigest().upper()}")


if __name__ == "__main__":
    main()
