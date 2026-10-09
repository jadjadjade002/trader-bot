"""Generate isolated tester-only R3 harness from hash-frozen V24."""
from hashlib import sha256
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/ResearchCandidate_R3.mq5"
EXPECTED = "5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E"
BENCH_HASH = "F60340E10AC59EC6E300068A44946424D33BA382A2C640E94AB97B9DC41C0183"
TUNING_HASH = "C4000295C76305056C417AD35D28E7D32EB7088006C6E76D213553024DF806B8"


def function(text, name):
    match = re.search(r"^(?:void|bool|int|double)\s+" + re.escape(name) + r"\([^\n]*\)\s*\{", text, re.M)
    if match is None:
        raise ValueError("Function missing: " + name)
    left = text.index("{", match.start())
    depth, right = 1, left
    while depth:
        right += 1
        if right >= len(text):
            raise ValueError("Unclosed function: " + name)
        depth += (text[right] == "{") - (text[right] == "}")
    return text[match.start():right + 1]


def frozen(path, expected):
    raw = (ROOT / path).read_bytes()
    if sha256(raw).hexdigest().upper() != expected:
        raise ValueError("Frozen artifact changed: " + path)
    return raw.decode("utf-8").replace("\r\n", "\n")


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected exactly one replacement: " + old)
    return text.replace(old, new, 1)


def generate():
    source = frozen("AegisPredator_v24.mq5", EXPECTED)
    bench = frozen("research/V23_BacktestBenchmark.mq5", BENCH_HASH)
    tuning = frozen("research/v23_tuning_extension.mqh", TUNING_HASH)
    extension = (ROOT / "research/candidate_r3_signal_extension.mqh").read_text(encoding="utf-8")
    extension += "\n" + (ROOT / "research/candidate_r3_native_tests.mqh").read_text(encoding="utf-8")

    # Keep existing path/equity instrumentation mechanical and unchanged.
    exports = function(bench, "OnTester")
    exports = replace_once(exports, "double OnTester()\n{", "double OnTester()\n{\n   if(MQLInfoInteger(MQL_OPTIMIZATION)) return ExportOptimizationFrame();\n   ExportPaths();")
    exports = replace_once(exports, "   ObserveEquity();", "   ObserveEquity();\n   ExportCoverageR3();\n   if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}")
    exports = replace_once(exports, "   return AccountInfoDouble(ACCOUNT_BALANCE);", "   return historyOK ? TesterStatistics(STAT_PROFIT) : -DBL_MAX;")
    common = "\n\n".join(function(tuning, name) for name in ("ObservePath", "ExportPaths"))
    globals_text = """
string benchGate="none";
bool benchAttempt=false;
int rawFile=INVALID_HANDLE;
datetime observedBar=0;
long seenTicks=0,firstTick=0,lastTick=0;
int monthIds[12];
double monthPeak[12],monthDD[12],monthDDPct[12];
long monthTicks[12],monthFirst[12],monthLast[12];
int monthN=0;
double overallPeak=0,overallDD=0;
long beModifyAttempts=0,beModifyRejected=0;
struct PathObservation
{
   ulong position;
   long opened;
   double entry,risk,mfe,mae;
   long mfeTime,maeTime;
};
PathObservation paths[];
"""
    source = replace_once(source, "void OnTick()", "void OriginalOnTick()")
    source = replace_once(source, "int OnInit()\n{", "int OnInit()\n{\n   if(!ValidateR3Inputs() || !RunR3FixtureTests() || !BenchInitR3()) return INIT_PARAMETERS_INCORRECT;")
    source = replace_once(source, "void OnDeinit(const int reason)\n{", "void OnDeinit(const int reason)\n{\n   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}\n   if(diagnosticFile!=INVALID_HANDLE){FileClose(diagnosticFile);diagnosticFile=INVALID_HANDLE;}")
    source = replace_once(source, "   signal=ProposedSignal(atr);", "   signal=CandidateR3Signal(atr);")
    source = replace_once(source, '      { V24Status("MANAGING_POSITION"); return; }', '      { benchGate="held_position"; V24Status("MANAGING_POSITION"); return; }')
    source = replace_once(source, '      { V24Status("CIRCUIT_BREAKER_PAUSE"); return; }', '      { benchGate="circuit_breaker"; V24Status("CIRCUIT_BREAKER_PAUSE"); return; }')
    source = replace_once(source, '      { V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }', '      { benchGate="no_signal"; V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }')
    source = replace_once(source, '   V24Status(signal==1 ? "BUY_CANDIDATE" : "SELL_CANDIDATE");', '   benchGate="signal";\n   V24Status(signal==1 ? "BUY_CANDIDATE" : "SELL_CANDIDATE");')
    for side, price in (("BUY", "ask"), ("SELL", "bid")):
        source = replace_once(
            source,
            f"      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_{side}, InpLotSize, {price})) return;",
            f'      if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_{side}, InpLotSize, {price})) {{ benchGate="margin_block"; return; }}',
        )
        marker = "      if(trade." + ("Buy" if side == "BUY" else "Sell") + "(InpLotSize"
        source = replace_once(source, marker, '      benchAttempt=true;benchGate="order_attempt";\n' + marker)
    source = replace_once(
        source,
        "ulong          lastBreakerDealTicket = 0;",
        "ulong          lastBreakerDealTicket = 0;\n" + globals_text + "\n" + extension + "\n"
        + function(bench, "ObserveEquity") + "\n" + common + "\n" + exports,
    )
    source = source.replace('"24.00"', '"24.92"', 1)
    source = source.replace("AegisPredator_v24.mq5", "ResearchCandidate_R3.mq5", 1)
    source = replace_once(
        source,
        '#property description "V24 demo research: closed M5 trend, M1 pullback/reclaim, TP2R, BE off. Historical net remains negative."',
        '#property description "Research Candidate R3, tester-only. Fixed V24 economics. Not a V25 release."',
    )
    return source


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generate(), encoding="utf-8")
    print("Generated isolated tester-only R3 harness. V24, R1 and R2 files untouched.")
