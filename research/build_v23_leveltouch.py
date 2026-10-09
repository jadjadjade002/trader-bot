"""Build an isolated, tester-only V23 level-touch candidate from frozen telemetry harness."""

from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research" / "V23_BacktestBenchmark.mq5"
OUT = ROOT / "research" / "V23_LevelTouchBenchmark.mq5"
EXPECTED_SHA256 = "F60340E10AC59EC6E300068A44946424D33BA382A2C640E94AB97B9DC41C0183"

raw = BASE.read_bytes()
if sha256(raw).hexdigest().upper() != EXPECTED_SHA256:
    raise RuntimeError("Frozen V23 benchmark source changed. Refuse to generate candidate.")
source = raw.decode("utf-8")

changes = (
    (
        "input bool InpRequireCloseBackInside = false;",
        "input bool InpRequireCloseBackInside = false;\n"
        "input bool InpRequireLevelTouch = true; // Tester-only signal experiment",
    ),
    (
        "&& (InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose > retestOpen))",
        "&& (InpRequireLevelTouch ? (retestLow <= donchianHigh && retestClose > donchianHigh && retestClose > retestOpen) : "
        "(InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose > retestOpen)))",
    ),
    (
        "&& (InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose < retestOpen))",
        "&& (InpRequireLevelTouch ? (retestHigh >= donchianLow && retestClose < donchianLow && retestClose < retestOpen) : "
        "(InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose < retestOpen)))",
    ),
)
for old, new in changes:
    if source.count(old) != 1:
        raise RuntimeError(f"Expected exactly one match: {old}")
    source = source.replace(old, new, 1)

OUT.write_text(source, encoding="utf-8")
print(f"Generated tester-only candidate: {OUT}")
