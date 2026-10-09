"""Conditional six-config research round. Reuses audited isolated execution."""
import argparse
import json
from research.run_candidate_r2 import run_all
from research.run_v25_native import BASE, lab_lease

SOURCE = "research/ResearchCandidate_R3.mq5"
FAMILIES = {1: "blowoff_fade", 2: "internal_range", 3: "efficient_flag"}


def activation_ok(evidence):
    rows = evidence.get("development", [])
    return len(rows) == 10 and all(r.get("eligible") is False for r in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r3_a")
    args = parser.parse_args()
    evidence = json.loads((BASE / "r2_a_complete.json").read_text())
    if not activation_ok(evidence):
        raise ValueError("R3 inactive: R2 screening incomplete or a development survivor exists")
    with lab_lease():
        run_all(args.prefix, SOURCE, FAMILIES, "R3")
