"""Bounded R7 exit-only screen. Controls precede all four new cells."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from itertools import product
from pathlib import Path
import re

from research import run_v25_native as native
from research.candidate_release_evidence import evaluate
from research.run_v23_tuning import save

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports/v25_research_20261008_postupdate"
SOURCE = "research/ResearchCandidate_R7.mq5"
R4_SOURCE = "research/ResearchCandidate_R4.mq5"
R4_SHA = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"
CONTROL_RUNS = {0: "r5_d_r4_control_p0", 1: "r5_d_r4_control_p1"}
PRODUCTION_RUN = "r5_d_production_v24"


def configurations():
    return [(5, dict(InpEntryStrength=p, InpStopLossATRMul=1.5,
                     InpTakeProfitRRMul=tp), f"p{p}_tp{str(tp).replace('.', 'p')}")
            for p, tp in product((0, 1), (0.5, 0.6))]


def execute(name, mode, parameters, *, tester_login, evidence_base=BASE,
            start=native.START, end=native.END, deposit=10000, delay=200):
    return native.execute(name, mode, parameters, candidate_source=SOURCE,
                          tester_login=tester_login, evidence_base=evidence_base,
                          start=start, end=end, deposit=deposit, delay=delay)


def qualify(result, min_trades=150, pf=1.20):
    return native.qualify(result, min_trades, pf)


def run_all(prefix="r7_a", tester_login=None, *, evidence_base=BASE):
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R7 needs an explicit positive integer demo tester login")
    if not re.fullmatch(r"r7_[A-Za-z0-9_]+", prefix):
        raise ValueError("R7 prefix must start r7_ with safe characters")
    run_base = Path(evidence_base).resolve()
    if run_base != BASE.resolve():
        raise ValueError("R7 evidence root must be approved postupdate root")
    if hashlib.sha256((ROOT/R4_SOURCE).read_bytes()).hexdigest().upper() != R4_SHA:
        raise ValueError("Pinned R4 source changed")
    # Controls must already be accepted. Never create a different control while
    # claiming it is the frozen accepted record.
    for control_name in (PRODUCTION_RUN, *CONTROL_RUNS.values()):
        if not (run_base/"runs"/control_name/"accepted.json").is_file():
            raise ValueError(f"Accepted R7 reference control missing: {control_name}")
    production = native.execute(PRODUCTION_RUN, production=True,
                                tester_login=tester_login, evidence_base=run_base)
    progress = dict(round_label="R7", project="Research R7, not V25 release",
        source_sha=hashlib.sha256((ROOT/SOURCE).read_bytes()).hexdigest().upper(),
        development=[], validation=[], control_parity={}, qualified=False,
        promotion=False, genuinely_unseen_oos=False, selection_lock=None,
        tester_connection_login=tester_login,
        evidence_root=run_base.relative_to(ROOT.resolve()).as_posix(),
        baseline_control_run=PRODUCTION_RUN, control_mapping=CONTROL_RUNS,
        release_status="NOT_A_RELEASE")
    baseline = execute(f"{prefix}_baseline", 0, {}, tester_login=tester_login,
                       evidence_base=run_base)
    parity = native.parity(production, baseline, evidence_base=run_base,
                           production_base=run_base)
    if parity.get("passed") is not True:
        raise ValueError("R7 exact V24 mode0 parity failed")
    progress.update(baseline=baseline, parity=parity)

    def checked_execute(*args, **kwargs):
        result = execute(*args, tester_login=tester_login, evidence_base=run_base, **kwargs)
        native.verify_environment(baseline, result, evidence_base=run_base)
        return result

    # Both entry controls precede any new-cell execution or outcome selection.
    for preset in (0, 1):
        params = dict(InpEntryStrength=preset, InpStopLossATRMul=1.5, InpTakeProfitRRMul=1.0)
        reference = native.execute(CONTROL_RUNS[preset], 5, params, end=native.DEV_END,
            candidate_source=R4_SOURCE, tester_login=tester_login, evidence_base=run_base)
        control = checked_execute(f"{prefix}_tp1_control_p{preset}", 5, params, end=native.DEV_END)
        comparison = native.parity(reference, control, evidence_base=run_base, production_base=run_base)
        if comparison.get("passed") is not True:
            raise ValueError(f"R7 TP1 P{preset} exact R4 parity failed")
        progress["control_parity"][str(preset)] = dict(reference=reference["evidence_run"],
            result=control, comparison=comparison)
        save(run_base/f"{prefix}_progress.json", progress)

    for mode, params, tag in configurations():
        result = checked_execute(f"{prefix}_dev_{tag}", mode, params, end=native.DEV_END)
        progress["development"].append(dict(mode=mode, parameters=params,
            config_tag=tag, result=result, eligible=qualify(result)))
        save(run_base/f"{prefix}_progress.json", progress)
    survivors = [x for x in progress["development"] if x["eligible"]]
    progress["development_shortlist"] = [dict(mode=x["mode"], parameters=x["parameters"],
        config_tag=x["config_tag"]) for x in survivors]
    save(run_base/f"{prefix}_progress.json", progress)
    for item in survivors:
        result = checked_execute(f"{prefix}_val_{item['config_tag']}", item["mode"], item["parameters"],
                                 start=native.DEV_END, end=native.VAL_END)
        progress["validation"].append(dict(mode=item["mode"], parameters=item["parameters"],
            config_tag=item["config_tag"], result=result, eligible=qualify(result, 40)))
        save(run_base/f"{prefix}_progress.json", progress)
    qualified_val = [x for x in progress["validation"] if x["eligible"]]
    if not qualified_val:
        chosen = max(survivors or progress["development"], key=lambda x:(x["result"]["net"],
                     -x["result"]["native_equity_dd_pct"], x["config_tag"]))
        progress["failure_reason"] = "No validation-qualified cell, descriptive replay only"
        progress["descriptive_failed_candidate"] = dict(mode=chosen["mode"],
            parameters=chosen["parameters"], config_tag=chosen["config_tag"],
            selected_from="development_only", eligible=False, promotion=False,
            result=checked_execute(f"{prefix}_descriptive10m", chosen["mode"], chosen["parameters"]))
    else:
        chosen = min(qualified_val, key=lambda x:(x["result"]["native_equity_dd_pct"],
                     -x["result"]["net"], x["config_tag"]))
        lock = dict(mode=chosen["mode"], parameters=chosen["parameters"], config_tag=chosen["config_tag"],
            selected_using="validation_dd_then_net_then_stable_id", reselect_after_confirmation=False,
            locked_utc=datetime.now(timezone.utc).isoformat())
        lockpath = run_base/f"{prefix}_selection_lock.json"
        if lockpath.exists():
            previous = json.loads(lockpath.read_text(encoding="utf-8"))
            if any(previous.get(k) != lock[k] for k in ("mode", "parameters", "config_tag")):
                raise ValueError("R7 selection changed, no reselection")
            lock = previous
        else:
            save(lockpath, lock)
        progress["selection_lock"] = lock
        save(run_base/f"{prefix}_progress.json", progress)
        confirm = checked_execute(f"{prefix}_confirmation", lock["mode"], lock["parameters"], start=native.VAL_END)
        full = checked_execute(f"{prefix}_locked10m", lock["mode"], lock["parameters"])
        positive_months = sum(x["net"] > 0 for x in full["monthly"].values())
        historical = (qualify(confirm, 40, 1.10) and qualify(full, 150, 1.15)
            and positive_months >= 7 and full["net"] > baseline["net"]
            and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"])
        capital70 = checked_execute(f"{prefix}_capital70", lock["mode"], lock["parameters"], deposit=70)
        delay500 = checked_execute(f"{prefix}_delay500", lock["mode"], lock["parameters"], delay=500)
        robustness = evaluate(dict(qualified=historical, full=full, delay500=delay500, capital70=capital70))
        progress.update(confirmation=confirm, full=full, positive_months=positive_months,
            historical_candidate_passed=historical, capital70=capital70, delay500=delay500,
            economic_robustness=robustness, economic_robustness_passed=robustness["historically_robust"],
            qualified=historical and robustness["historically_robust"], promotion=False,
            prospective_confirmation="NOT_ESTABLISHED_HISTORICAL_DATA_CONTAMINATED")
    save(run_base/f"{prefix}_complete.json", progress)
    print(f"COMPLETE R7 qualified={progress['qualified']} promotion=False", flush=True)
    return progress


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r7_a")
    parser.add_argument("--tester-login", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=BASE)
    args = parser.parse_args()
    if not args.activate:
        parser.error("Review preregistered four cells then pass --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login, evidence_base=args.evidence_root)
