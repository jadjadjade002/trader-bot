"""Generate R4 exit-ablation harness from hash-frozen R2 source."""
from hashlib import sha256
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
R2_SOURCE = ROOT / "research/ResearchCandidate_R2.mq5"
OUT = ROOT / "research/ResearchCandidate_R4.mq5"
EXPECTED_R2_SHA256 = "74AC68D78650411B1364AA2EF6E18FD375928D0C528CBC23085C95867F1354FD"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Expected exactly one frozen replacement: " + old[:100])
    return text.replace(old, new, 1)


def function(text: str, name: str) -> str:
    signature = r"^(?:void|bool|int|double|long|ulong)\s+" + re.escape(name) + r"\([^\n]*\)\s*\{"
    match = re.search(signature, text, re.M)
    count = len(re.findall(r"^(?:void|bool|int|double|long|ulong)\s+" + re.escape(name) + r"\(", text, re.M))
    if match is None or count != 1:
        raise ValueError("Expected exactly one function: " + name)
    start = match.start()
    left = text.index("{", start)
    depth, right = 1, left
    while depth:
        right += 1
        if right >= len(text):
            raise ValueError("Unclosed function: " + name)
        depth += (text[right] == "{") - (text[right] == "}")
    return text[start:right + 1]


def generate() -> str:
    raw = R2_SOURCE.read_bytes()
    if sha256(raw).hexdigest().upper() != EXPECTED_R2_SHA256:
        raise ValueError("Hash-frozen R2 source changed")
    source = raw.decode("utf-8").replace("\r\n", "\n")
    old_validation = function(source, "ValidateR2Inputs")
    new_validation = '''bool ValidateR2Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   bool validStop=(InpStopLossATRMul==1.0 || InpStopLossATRMul==1.5);
   bool validTarget=(InpTakeProfitRRMul==0.75 || InpTakeProfitRRMul==1.0
                     || InpTakeProfitRRMul==1.5 || InpTakeProfitRRMul==2.0);
   bool parity=(InpExperimentMode==0 && InpEntryStrength==0
                && InpStopLossATRMul==1.5 && InpTakeProfitRRMul==2.0);
   bool exhaustion=(InpExperimentMode==5 && InpEntryStrength>=0 && InpEntryStrength<=1
                    && validStop && validTarget);
   if((!parity && !exhaustion) || InpExperimentMode<0 || InpExperimentMode>5
      || InpEntryStrength<0 || InpEntryStrength>1 || InpFadeBreakouts
      || InpMaxHoldBars!=60 || InpEnableHardSL!=true || InpEnableMarginGuard!=true
      || InpEnableCircuitBreaker!=true || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90
      || InpMinSLPoints!=150 || InpLotSize!=0.01 || InpATRPeriod!=14
      || InpDonchianPeriod!=20 || InpMagicNumber!=992300 || InpEnableSessionGuard!=false
      || InpEnableSpreadGuard!=false || InpTargetAccount!=0) return false;
   return true;
}'''
    source = replace_once(source, old_validation, new_validation)
    source = replace_once(source, '#property version   "24.91"', '#property version   "24.93"')
    source = replace_once(
        source,
        '#property description "Research Candidate R2, tester-only. Fixed V24 economics. Not a V25 release."',
        '#property description "Research Candidate R4 exit ablation, tester-only. R2 exhaustion signal frozen. Not a V25 release."',
    )
    source = replace_once(source, "R2_NATIVE_FIXTURE_FAIL", "R4_NATIVE_FIXTURE_FAIL")
    source = replace_once(source, "R2_NATIVE_FIXTURES_PASS", "R4_NATIVE_FIXTURES_PASS")
    return source


if __name__ == "__main__":
    OUT.write_text(generate(), encoding="utf-8", newline="\n")
    print("Generated R4 exit-ablation harness from hash-frozen R2 source.")
