"""Bounded R2 exhaustion exit ablation, activated only after failed R3 screen."""
import argparse
from itertools import product
import json
from research.run_candidate_r2 import run_all
from research.run_v25_native import BASE, lab_lease, qualify

SOURCE = "research/ResearchCandidate_R4.mq5"
FAMILIES = {5: "exhaustion_exit_ablation"}


def configurations():
    def tag(value):
        return str(value).replace(".", "p")
    return [(5, dict(InpEntryStrength=preset, InpStopLossATRMul=stop, InpTakeProfitRRMul=target),
             f"5_{preset}_sl{tag(stop)}_tp{tag(target)}")
            for preset, stop, target in product((0, 1), (1.0, 1.5), (0.75, 1.0, 1.5, 2.0))]


def activation_ok(evidence):
    rows = evidence.get("development", [])
    expected = {(mode, preset) for mode in (1, 2, 3) for preset in (0, 1)}
    try:
        actual = {(r["mode"], r["parameters"]["InpEntryStrength"]) for r in rows}
        return (evidence.get("round_label") == "R3" and evidence.get("parity", {}).get("passed") is True
                and len(rows) == 6 and actual == expected
                and all(set(r["parameters"]) == {"InpEntryStrength"}
                        and r.get("eligible") is False and not qualify(r["result"]) for r in rows))
    except (KeyError, TypeError, ValueError):
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r4_a")
    args = parser.parse_args()
    evidence = json.loads((BASE / "r3_a_complete.json").read_text())
    if not activation_ok(evidence):
        raise ValueError("R4 inactive: R3 screening incomplete or a development survivor exists")
    with lab_lease():
        run_all(args.prefix, SOURCE, FAMILIES, "R4", configurations(), max_per_family=3)
