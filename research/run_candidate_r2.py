"""Predeclared ten signal configurations, common V24 exits, no deployment."""
import argparse
from datetime import datetime, timezone
import json
from research.run_v25_native import execute, parity, qualify, BASE, START, DEV_END, VAL_END, END, lab_lease
from research.run_v23_tuning import save
from research.candidate_release_evidence import evaluate

SOURCE = "research/ResearchCandidate_R2.mq5"
FAMILIES = {1: "deeper_pullback", 2: "compression", 3: "range_reversal", 4: "break_retest", 5: "exhaustion"}


def parameter_key(item):
    return tuple(sorted(item["parameters"].items()))


def run_all(prefix, source=SOURCE, families=None, label="R2", configurations=None, max_per_family=None):
    families = FAMILIES if families is None else families
    configurations = ([(mode, dict(InpEntryStrength=preset), f"{mode}_{preset}")
                       for mode in families for preset in (0, 1)]
                      if configurations is None else configurations)
    progress = dict(project=f"Research Candidate {label}, not V25 release", round_label=label, development=[], validation=[],
                    qualified=False, promotion=False, genuinely_unseen_oos=False)
    production = execute("r1_b_production_v24", production=True)
    baseline = execute(prefix + "_baseline", candidate_source=source)
    progress.update(baseline=baseline, parity=parity(production, baseline))
    save(BASE / f"{prefix}_progress.json", progress)
    for mode, params, config_tag in configurations:
        result = execute(f"{prefix}_dev_{config_tag}", mode, params, end=DEV_END, candidate_source=source)
        progress["development"].append(dict(mode=mode, parameters=params, config_tag=config_tag,
                                             result=result, eligible=qualify(result)))
        save(BASE / f"{prefix}_progress.json", progress)
    shortlist = [item for item in progress["development"] if item["eligible"]]
    if max_per_family is not None:
        shortlist = [item for mode in families for item in sorted(
            (r for r in shortlist if r["mode"] == mode),
            key=lambda r: (r["result"]["native_equity_dd_pct"], -r["result"]["net"], parameter_key(r)))[:max_per_family]]
    progress["development_shortlist"] = [dict(mode=r["mode"], parameters=r["parameters"], config_tag=r["config_tag"]) for r in shortlist]
    save(BASE / f"{prefix}_progress.json", progress)
    for item in shortlist:
        mode, params = item["mode"], item["parameters"]
        result = execute(f"{prefix}_val_{item['config_tag']}", mode, params,
                         start=DEV_END, end=VAL_END, candidate_source=source)
        progress["validation"].append(dict(mode=mode, parameters=params, result=result, eligible=qualify(result, 40)))
        save(BASE / f"{prefix}_progress.json", progress)
    survivors = [x for x in progress["validation"] if x["eligible"]]
    if survivors:
        chosen = min(survivors, key=lambda x: (x["result"]["native_equity_dd_pct"], -x["result"]["net"], x["mode"], parameter_key(x)))
        lock = dict(mode=chosen["mode"], parameters=chosen["parameters"],
                    selected_using="development_and_validation_only", locked_utc=datetime.now(timezone.utc).isoformat(),
                    reselect_after_confirmation=False)
        lockpath = BASE / f"{prefix}_selection_lock.json"
        if lockpath.exists():
            old = json.loads(lockpath.read_text())
            if old["mode"] != lock["mode"] or old["parameters"] != lock["parameters"]:
                raise ValueError("R2 selection lock changed")
            lock = old
        else:
            save(lockpath, lock)
        progress["selection_lock"] = lock
        confirm = execute(prefix + "_confirmation", lock["mode"], lock["parameters"], start=VAL_END, candidate_source=source)
        full = execute(prefix + "_locked10m", lock["mode"], lock["parameters"], candidate_source=source)
        positives = sum(m["net"] > 0 for m in full["monthly"].values())
        progress.update(confirmation=confirm, full=full, positive_months=positives,
                        qualified=qualify(confirm, 40, 1.1) and qualify(full, 150, 1.15)
                        and positives >= 7 and full["net"] > baseline["net"]
                        and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"],
                        capital70=execute(prefix + "_capital70", lock["mode"], lock["parameters"], deposit=70, candidate_source=source),
                        baseline70=execute(prefix + "_baseline70", deposit=70, candidate_source=source),
                        delay500=execute(prefix + "_delay500", lock["mode"], lock["parameters"], delay=500, candidate_source=source))
    else:
        chosen = max(progress["development"], key=lambda x: (x["result"]["net"], -x["result"]["native_equity_dd_pct"]))
        progress["failure_reason"] = "No development/validation-qualified candidate"
        progress["descriptive_failed_candidate"] = dict(mode=chosen["mode"], parameters=chosen["parameters"],
            selection="Development-only maximum, rejected, not release eligible",
            result=execute(prefix + "_descriptive10m", chosen["mode"], chosen["parameters"], candidate_source=source))
    progress["release_evidence"] = evaluate(progress)
    save(BASE / f"{prefix}_complete.json", progress)
    print(f"COMPLETE {label} qualified={progress['qualified']} promotion=False", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r2_a")
    args = parser.parse_args()
    with lab_lease():
        run_all(args.prefix)
