"""Generate isolated V23 tuning harness from hash-guarded frozen benchmark.

Mechanical generation only. Does not edit the production EA or VM.
"""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/V23_BacktestBenchmark.mq5"
OUT = ROOT / "research/V23_TuningBenchmark.mq5"
EXPECTED = "F60340E10AC59EC6E300068A44946424D33BA382A2C640E94AB97B9DC41C0183"


def generate():
    raw = BASE.read_bytes()
    if sha256(raw).hexdigest().upper() != EXPECTED:
        raise ValueError("Frozen V23 benchmark changed")
    text = raw.decode("utf-8").replace("\r\n", "\n")
    extension = (ROOT / "research/v23_tuning_extension.mqh").read_text(encoding="utf-8")
    changes = (
        ('input string InpRunTag = "bench";', 'input string InpRunTag = "bench";\n' + extension),
        ('bool BenchInit()\n{', 'bool BenchInit()\n{\n   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;'),
        ('   if(fresh)\n      FileWrite(rawFile,', '   if(fresh && rawFile!=INVALID_HANDLE)\n      FileWrite(rawFile,'),
        ('   OriginalOnTick();', '   ObservePath();\n   OriginalOnTick();\n   ObservePath();'),
        ('double OnTester()\n{', 'double OnTester()\n{\n   if(MQLInfoInteger(MQL_OPTIMIZATION)) return ExportOptimizationFrame();\n   ExportPaths();'),
        ('   if(!BenchInit()) return INIT_FAILED;', '   if(!BenchInit()) return INIT_FAILED;\n   if(!InitExperiment()) return INIT_FAILED;'),
        ('   if(atrHandle != INVALID_HANDLE)\n   {', '   ReleaseExperiment();\n   if(atrHandle != INVALID_HANDLE)\n   {'),
        ('void ManageOpenPositions()\n{', 'void ManageOpenPositions()\n{\n   ManageBreakEven();'),
        ('   if(signal == 0)\n      { benchGate="no_signal"; return; }',
         '   if(InpExperimentMode==2) signal=ProposedSignal(atr);\n   if(signal == 0)\n      { benchGate="no_signal"; return; }'),
        ('   if(InpFadeBreakouts)\n   {', '   if(InpFadeBreakouts && InpExperimentMode!=2)\n   {'),
        ('   double tpDistance = slDistance * InpTakeProfitRRMul;',
         '   double tpDistance = slDistance * EffectiveTPR();'),
    )
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError(f"Expected one replacement: {old}")
        text = text.replace(old, new, 1)
    return text


if __name__ == "__main__":
    OUT.write_text(generate(), encoding="utf-8")
    print(f"Generated tester-only harness: {OUT}")
