"""Generate the tester-only R7 low-target ablation from pinned R4 source."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "research" / "ResearchCandidate_R4.mq5"
OUTPUT = ROOT / "research" / "ResearchCandidate_R7.mq5"
PARENT_SHA256 = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected one replacement anchor, found {count}: {old[:90]!r}")
    return text.replace(old, new, 1)


def function(text: str, name: str) -> str:
    """Return a complete MQL function by balanced-brace scan."""
    match = re.search(
        rf"(?m)^[\t ]*(?:[\w*&]+[\t ]+)+{re.escape(name)}[\t ]*\([^;{{}}]*\)\s*\{{",
        text,
    )
    if not match:
        raise ValueError(f"missing function {name}")
    start = match.start()
    brace = match.end() - 1
    depth = 0
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise ValueError(f"unterminated function {name}")


def build(source: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    text = source
    text = replace_once(text, '#property version   "24.93"', '#property version   "24.97"')
    text = replace_once(
        text,
        "Research Candidate R4 exit ablation, tester-only. R2 exhaustion signal frozen. Not a V25 release.",
        "Research Candidate R7 low-target ablation, tester-only. R2 exhaustion signal frozen. Not a V25 release.",
    )
    text = replace_once(
        text,
        "bool validStop=(InpStopLossATRMul==1.0 || InpStopLossATRMul==1.5);",
        "bool validStop=(InpStopLossATRMul==1.5);",
    )
    text = replace_once(
        text,
        "bool validTarget=(InpTakeProfitRRMul==0.75 || InpTakeProfitRRMul==1.0\n                     || InpTakeProfitRRMul==1.5 || InpTakeProfitRRMul==2.0);",
        "bool validTarget=(R7TargetAllowed(InpTakeProfitRRMul) && InpTakeProfitRRMul!=2.0);",
    )
    text = replace_once(
        text,
        "double tpDistance = slDistance * InpTakeProfitRRMul;",
        "double tpDistance = R7TargetDistance(slDistance,InpTakeProfitRRMul);",
    )
    helper = '''bool R7TargetAllowed(const double targetR)
{
   return(MathIsValidNumber(targetR) && (targetR==0.5 || targetR==0.6
          || targetR==1.0 || targetR==2.0));
}

double R7TargetDistance(const double slDistance,const double targetR)
{
   if(!MathIsValidNumber(slDistance) || slDistance<=0.0 || !R7TargetAllowed(targetR))
      return(0.0);
   return(slDistance*targetR);
}

'''
    marker = "bool ValidateR2Inputs()"
    if text.count(marker) != 1:
        raise ValueError("expected one ValidateR2Inputs declaration anchor")
    text = text.replace(marker, helper + marker, 1)
    fixture_anchor = 'if(ok) Print("R4_NATIVE_FIXTURES_PASS checks=",r2FixtureChecks," preset=",InpEntryStrength);'
    fixtures = '''   ok=R2Assert(R7TargetAllowed(0.5),"R7_TARGET_05_ALLOWED") && ok;
   ok=R2Assert(R7TargetAllowed(0.6),"R7_TARGET_06_ALLOWED") && ok;
   ok=R2Assert(!R7TargetAllowed(0.75),"R7_TARGET_075_REJECTED") && ok;
   ok=R2Assert(!R7TargetAllowed(-1.0),"R7_TARGET_NEGATIVE_REJECTED") && ok;
   ok=R2Assert(MathAbs(R7TargetDistance(4.0,0.5)-2.0)<1e-10,"R7_TP_DISTANCE_05") && ok;
   ok=R2Assert(MathAbs(R7TargetDistance(5.0,0.6)-3.0)<1e-10,"R7_TP_DISTANCE_06") && ok;
'''
    text = replace_once(text, fixture_anchor, fixtures + fixture_anchor)
    text = text.replace("R4_NATIVE_FIXTURE_FAIL", "R7_NATIVE_FIXTURE_FAIL")
    text = text.replace("R4_NATIVE_FIXTURES_PASS", "R7_NATIVE_FIXTURES_PASS")
    if text.count("TP=%.2f (2.0R)") != 2:
        raise ValueError("expected exactly two inherited hard-coded TP log labels")
    text = text.replace("TP=%.2f (2.0R)", "TP=%.2f (ConfiguredR)")
    for frozen_name in ("OnTick", "CandidateR2Signal", "R2Exhaustion"):
        if function(source, frozen_name) != function(text, frozen_name):
            raise ValueError(f"R7 generation changed frozen function {frozen_name}")
    original_parent = function(source, "OriginalOnTick")
    expected_original = replace_once(
        original_parent,
        "double tpDistance = slDistance * InpTakeProfitRRMul;",
        "double tpDistance = R7TargetDistance(slDistance,InpTakeProfitRRMul);",
    )
    expected_original = expected_original.replace("TP=%.2f (2.0R)", "TP=%.2f (ConfiguredR)")
    if function(text, "OriginalOnTick") != expected_original:
        raise ValueError("R7 generation changed OriginalOnTick beyond TP-distance wiring")
    return text


def main() -> None:
    raw = PARENT.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != PARENT_SHA256:
        raise SystemExit(f"pinned R4 source SHA mismatch: {digest}")
    generated = build(raw.decode("utf-8-sig"))
    OUTPUT.write_text(generated, encoding="utf-8", newline="\n")
    print(f"generated={OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(generated.encode()).hexdigest().upper()}")


if __name__ == "__main__":
    main()
