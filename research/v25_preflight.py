"""Read-only broker-history acquisition in the existing isolated local lab.

Does not access SSH, VM, account secrets or running production terminals.
Runtime files are authored by the existing native execution helper.
"""
from pathlib import Path
import argparse
import json
from research import run_v23_tuning as native

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/v25_research_20261007"
SOURCE_HASH = "5CCB2A9A694D69542E5A996EB24708B344ABA8ECE75D6BA7BB166040AB53A17E"
BINARY_HASH = "5A11086D05F7AA5C4E0B3D806B58BFF446BE08CC0EC8A48944A7681D42A539AF"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="v25_history10m")
    args = parser.parse_args()
    if native.sha(ROOT / "AegisPredator_v24.mq5") != SOURCE_HASH:
        raise ValueError("V24 baseline source changed")
    if native.sha(ROOT / "AegisPredator_v24.ex5") != BINARY_HASH:
        raise ValueError("V24 baseline binary changed")
    native.BASE = BASE
    result = native.execute(args.prefix, overrides={"InpFadeBreakouts": "false"},
                            start="2025.12.01", end="2026.10.01", original=True,
                            source_override="AegisPredator_v24.mq5", timeout=1800)
    cache = native.LAB / "bases/MetaQuotes-Demo/ticks/XAUUSD"
    months = ["202512"] + [f"2026{x:02d}" for x in range(1, 10)]
    missing = [m for m in months if not (cache / f"{m}.tkc").exists()]
    manifest = [dict(month=m, bytes=(cache / f"{m}.tkc").stat().st_size,
                     sha256=native.sha(cache / f"{m}.tkc")) for m in months if m not in missing]
    native.save(BASE / f"{args.prefix}_history.json",
                dict(result=result, cache=manifest, missing=missing,
                     note="Cache existence is not per-month real-tick coverage proof."))
    if missing:
        raise ValueError(f"Ten-month tick cache missing: {missing}")
    print(json.dumps(dict(preflight=True, native=result["native"], months=len(manifest))))


if __name__ == "__main__":
    main()
