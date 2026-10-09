"""Three fixed continuation-quality treatments, exact controls first."""
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
SOURCE = "research/ResearchCandidate_R8.mq5"
SOURCE_SHA = "03CD489C2C51BDA9F87CA88AA231FFF25206071BFFDBA73ACDDCFD1597431974"
CONTROL_SOURCE = "research/ResearchControl_R1_R8.mq5"
CONTROL_SHA = "961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B"
R1_SOURCE = ROOT / "research/ResearchCandidate_R1.mq5"
R1_SHA = "0C866807B3E81B14130E342085D3FD7C5CC6C03F9CF60307F3A6DA8F8112DEC2"
PRODUCTION_RUN = "r5_d_production_v24"


def parameters(k, e):
    return dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0,
                InpRequireEfficiency=bool(k), InpRequireNearMean=bool(e))


def configurations():
    return [(1, parameters(k, e), f"k{k}_e{e}")
            for k, e in product((0, 1), repeat=2) if k or e]


def execute(name, mode, params, *, tester_login, evidence_base=BASE,
            start=native.START, end=native.END, deposit=10000, delay=200):
    return native.execute(name, mode, params, candidate_source=SOURCE,
        tester_login=tester_login, evidence_base=evidence_base,
        start=start, end=end, deposit=deposit, delay=delay)


def qualify(result, n=150, pf=1.20):
    return native.qualify(result, n, pf)


def run_all(prefix="r8_b", tester_login=None, *, evidence_base=BASE):
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("R8 needs an explicit positive integer demo tester login")
    if not re.fullmatch(r"r8_[A-Za-z0-9_]+", prefix):
        raise ValueError("R8 prefix must start r8_ with safe characters")
    run_base = Path(evidence_base).resolve()
    if run_base != BASE.resolve():
        raise ValueError("R8 evidence root must be approved postupdate root")
    if hashlib.sha256(R1_SOURCE.read_bytes()).hexdigest().upper() != R1_SHA:
        raise ValueError("Pinned R1 source changed")
    for relative, expected in ((SOURCE, SOURCE_SHA), (CONTROL_SOURCE, CONTROL_SHA)):
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest().upper() != expected:
            raise ValueError("Pinned R8 reporting source changed")
    if not (run_base/"runs"/PRODUCTION_RUN/"accepted.json").is_file():
        raise ValueError("Accepted V24 reference missing")
    production = native.execute(PRODUCTION_RUN, production=True,
                                tester_login=tester_login, evidence_base=run_base)
    baseline = execute(f"{prefix}_baseline", 0, {}, tester_login=tester_login, evidence_base=run_base)
    comparison = native.parity(production, baseline, evidence_base=run_base, production_base=run_base)
    if comparison.get("passed") is not True:
        raise ValueError("R8 exact V24 mode0 parity failed")
    progress = dict(round_label="R8", project="Research R8, not V25 release", promotion=False,
        qualified=False, release_status="NOT_A_RELEASE", genuinely_unseen_oos=False,
        post_selection_mechanism_research=True, source_sha=hashlib.sha256((ROOT/SOURCE).read_bytes()).hexdigest().upper(),
        export_revision="POST_TEST_COMPLETE_HISTORY_RANGE", immutable_r1_parent_sha=R1_SHA,
        reporting_control_source=CONTROL_SOURCE, reporting_control_sha=CONTROL_SHA,
        tester_connection_login=tester_login, evidence_root=run_base.relative_to(ROOT.resolve()).as_posix(),
        baseline=baseline, parity=comparison, baseline_control_run=PRODUCTION_RUN,
        development=[], validation=[], selection_lock=None)

    def checked_execute(*args, **kwargs):
        result = execute(*args, tester_login=tester_login, evidence_base=run_base, **kwargs)
        native.verify_environment(baseline, result, evidence_base=run_base)
        return result

    # Fresh reporting-only R1 clone on this runtime/cache. Parent remains immutable.
    # Extended post-test export captures native liquidation beyond last quote time.
    r1_control = native.execute(f"{prefix}_r1_control", 1,
        dict(InpEntryStrength=2, InpStopLossATRMul=2.0, InpTakeProfitRRMul=3.0),
        end=native.DEV_END, tester_login=tester_login, evidence_base=run_base,
        candidate_source=CONTROL_SOURCE)
    native.verify_environment(baseline, r1_control, evidence_base=run_base)
    control = checked_execute(f"{prefix}_control_k0_e0", 1, parameters(0, 0), end=native.DEV_END)
    control_comparison = native.parity(r1_control, control, evidence_base=run_base, production_base=run_base)
    if control_comparison.get("passed") is not True:
        raise ValueError("R8 off/off exact R1 control parity failed")
    progress.update(control=control, r1_control=r1_control, control_parity=control_comparison)
    save(run_base/f"{prefix}_progress.json", progress)

    for mode, params, tag in configurations():
        result = checked_execute(f"{prefix}_dev_{tag}", mode, params, end=native.DEV_END)
        progress["development"].append(dict(mode=mode, parameters=params, config_tag=tag,
                                             result=result, eligible=qualify(result)))
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
    survivors_val = [x for x in progress["validation"] if x["eligible"]]
    if not survivors_val:
        chosen = max(survivors or progress["development"], key=lambda x:(x["result"]["net"],
                     -x["result"]["native_equity_dd_pct"], x["config_tag"]))
        progress["failure_reason"] = "No validation-qualified cell, descriptive replay only"
        progress["descriptive_failed_candidate"] = dict(mode=chosen["mode"], parameters=chosen["parameters"],
            config_tag=chosen["config_tag"], selected_from="development_only", eligible=False, promotion=False,
            result=checked_execute(f"{prefix}_descriptive10m", chosen["mode"], chosen["parameters"]))
    else:
        chosen = min(survivors_val, key=lambda x:(x["result"]["native_equity_dd_pct"],
                     -x["result"]["net"], x["config_tag"]))
        lock = dict(mode=chosen["mode"], parameters=chosen["parameters"], config_tag=chosen["config_tag"],
            selected_using="validation_dd_then_net_then_stable_id", reselect_after_confirmation=False,
            locked_utc=datetime.now(timezone.utc).isoformat())
        lockpath = run_base/f"{prefix}_selection_lock.json"
        if lockpath.exists():
            previous = json.loads(lockpath.read_text(encoding="utf-8"))
            if any(previous.get(k) != lock[k] for k in ("mode", "parameters", "config_tag")):
                raise ValueError("R8 selection changed, no reselection")
            lock = previous
        else:
            save(lockpath, lock)
        progress["selection_lock"] = lock
        save(run_base/f"{prefix}_progress.json", progress)
        confirm = checked_execute(f"{prefix}_confirmation", lock["mode"], lock["parameters"], start=native.VAL_END)
        full = checked_execute(f"{prefix}_locked10m", lock["mode"], lock["parameters"])
        positive_months = sum(x["net"] > 0 for x in full["monthly"].values())
        historical = (qualify(confirm, 40, 1.10) and qualify(full, 150, 1.15) and positive_months >= 7
            and full["net"] > baseline["net"] and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"])
        capital70 = checked_execute(f"{prefix}_capital70", lock["mode"], lock["parameters"], deposit=70)
        delay500 = checked_execute(f"{prefix}_delay500", lock["mode"], lock["parameters"], delay=500)
        robustness = evaluate(dict(qualified=historical, full=full, capital70=capital70, delay500=delay500))
        progress.update(confirmation=confirm, full=full, positive_months=positive_months,
            historical_candidate_passed=historical, capital70=capital70, delay500=delay500,
            economic_robustness=robustness, economic_robustness_passed=robustness["historically_robust"],
            qualified=historical and robustness["historically_robust"], promotion=False,
            prospective_confirmation="NOT_ESTABLISHED_HISTORICAL_DATA_CONTAMINATED")
    save(run_base/f"{prefix}_complete.json", progress)
    print(f"COMPLETE R8 qualified={progress['qualified']} promotion=False", flush=True)
    return progress


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r8_b")
    parser.add_argument("--tester-login", type=int, required=True)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=BASE)
    args = parser.parse_args()
    if not args.activate:
        parser.error("Review preregistered three treatments then pass --activate")
    with native.lab_lease():
        run_all(args.prefix, args.tester_login, evidence_base=args.evidence_root)
