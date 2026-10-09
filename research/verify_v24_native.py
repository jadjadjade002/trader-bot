"""Native five-month economic parity for the packaged V24 production binary."""
import argparse
import json
from research.run_v23_tuning import BASE, execute, save, ROOT, sha
from research.finalize_v23_tuning import native_sequence, cache_manifest


def verify(prefix):
    audit = json.loads((BASE / "complete5m_batch1_evidence_audit.json").read_text())
    if not audit.get("complete"):
        raise ValueError("Proposed model native evidence incomplete")
    before = cache_manifest()
    expected = audit["descriptive_retests"]["proposed"]["full"]
    reference = expected["evidence_run"]
    result = execute(prefix+"_packaging_parity", mode=2, original=True,
                     source_override="AegisPredator_v24.mq5")
    name = result["evidence_run"]
    for key in ("Total Trades", "Total Net Profit", "Gross Profit", "Gross Loss", "Ticks", "Bars",
                "History Quality", "Equity Drawdown Maximal", "Balance Drawdown Maximal"):
        if result["native"][key] != expected["native"][key]:
            raise ValueError("Packaged V24 parity differs: "+key)
    actual = native_sequence(BASE / "runs" / name, name)
    normalized = [[v.replace("AegisPredator V24", "AegisPredator V23") for v in row] for row in actual]
    if normalized != native_sequence(BASE / "runs" / reference, reference):
        raise ValueError("V24 ordered native economics differ from tested proposed model")
    if before != cache_manifest():
        raise ValueError("Tick cache changed during V24 verification")
    output = dict(passed=True, native=result["native"], economic_rows=len(actual),
        note="Ordered economics match; only V24 order-comment version label normalized.",
        reference_run=reference, v24_run=name, source_sha=sha(ROOT / "AegisPredator_v24.mq5"),
        binary_sha=sha(ROOT / "AegisPredator_v24.ex5"), tick_cache=before)
    save(BASE / f"{prefix}_v24_parity.json", output)
    print("V24 NATIVE PACKAGING PARITY PASSED", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("prefix")
    verify(p.parse_args().prefix)
