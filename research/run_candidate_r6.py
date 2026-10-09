"""Run exactly four preregistered R6 cells; never classify them as a release."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from itertools import product
from pathlib import Path
import re

from research import run_v25_native as native
from research.candidate_release_evidence import evaluate as evaluate_robustness
from research.run_v23_tuning import save

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "research/ResearchCandidate_R6.mq5"
R5_SOURCE_SHA = "98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494"
BASE = ROOT / "reports/v25_research_20261008"
OLD_BASE = ROOT / "reports/v25_research_20261007"
POSTUPDATE_BASE = ROOT / "reports/v25_research_20261008_postupdate"
APPROVED_BASES = {BASE.resolve(), POSTUPDATE_BASE.resolve()}
HEX64 = re.compile(r"[0-9A-Fa-f]{64}\Z")


def validate_tester_login(value):
    if type(value) is not int or value<=0:
        raise ValueError("Fresh R6 native run requires an explicit positive integer tester login")
    return value


def configurations():
    """Four fixed cells; no R5 alignment parameter in candidate overrides."""
    return [
        (mode, dict(InpEntryStrength=preset, InpStopLossATRMul=1.5,
                    InpTakeProfitRRMul=2.0),
         f"{'f' if mode == 6 else 'v'}{preset}")
        for mode, preset in product((6, 7), (0, 1))
    ]


def qualify(row, min_trades=150, pf=1.20):
    return native.qualify(row, min_trades, pf)


def _months(start="2025.12.01", end="2026.10.01"):
    result=[]
    y,m=map(int,start[:7].split(".")); ey,em=map(int,end[:7].split("."))
    while (y,m)<(ey,em):
        result.append(y*100+m)
        y,m=(y+1,1) if m==12 else (y,m+1)
    return result


def _sha_shape(value):
    return isinstance(value,str) and HEX64.fullmatch(value) is not None


def accepted_r5_mode0(expected_login=None, *, evidence_base=None):
    """Ask native backend to exact-signature validate an existing R5 control."""
    run_base=BASE if evidence_base is None else Path(evidence_base)
    runs=run_base/"runs"
    if not runs.is_dir():
        return None
    if __import__("hashlib").sha256((ROOT/"research/ResearchCandidate_R5.mq5").read_bytes()).hexdigest().upper()!=R5_SOURCE_SHA:
        raise ValueError("Final R5 source SHA changed; cannot reuse R5 mode-0 control")
    candidates=[]
    for folder in sorted(list(runs.glob("r5_*_baseline"))+list(runs.glob("r5_*_baseline_retry[12]"))):
        accepted=folder/"accepted.json"
        if accepted.is_file():
            try:
                # execute returns existing result only when full native signature,
                # source, SET, runtime, cache, and requested-login provenance match.
                result=native.execute(folder.name,mode=0,overrides={},candidate_source="research/ResearchCandidate_R5.mq5",
                    evidence_base=run_base,tester_login=expected_login)
            except (ValueError,KeyError,TypeError):
                continue
            candidates.append(result)
    if len(candidates)>1:
        raise ValueError("Multiple valid accepted R5 mode-0 controls; resolve provenance before R6")
    return candidates[0] if candidates else None


def accepted_v24_production(expected_login=None):
    path=OLD_BASE/"runs"/"r1_b_production_v24"/"accepted.json"
    if not path.is_file():
        raise ValueError("Accepted V24 production control missing; cannot establish fallback parity")
    # Original V24 control keeps its saved default tester provenance.
    return native.execute("r1_b_production_v24",production=True,evidence_base=OLD_BASE)


def execute(name, mode, overrides=None, *, start=native.START, end=native.END,
            deposit=10000, delay=200, tester_login=None, evidence_base=None):
    """R6 adapter is supplied by root; this wrapper fixes output/provenance scope."""
    validate_tester_login(tester_login)
    return native.execute(name,mode,overrides or {},start=start,end=end,deposit=deposit,
                          delay=delay,candidate_source=SOURCE,evidence_base=BASE if evidence_base is None else evidence_base,
                          tester_login=tester_login)


def cross_family_duplicate_status():
    """Report unavailable unless complete old-family event exports all exist."""
    missing=[]
    legacy=OLD_BASE/"runs"
    for stem,count in (("r1_b_dev_",3),("r2_a_dev_",10),("r3_a_dev_",6)):
        matches=sorted(p for p in legacy.glob(stem+"*") if p.is_dir() and (p/"accepted.json").is_file())
        if len(matches)<count:
            missing.append(dict(family=stem.rstrip("_*"),expected_runs=count,accepted_runs=len(matches)))
        for folder in matches:
            signal=folder/f"{folder.name}_signals.csv"
            if not signal.is_file():
                missing.append(dict(family=stem.rstrip("_*"),run=folder.name,event_export="missing"))
    if missing:
        return dict(available=False,reason="Incomplete prior-family event exports; duplicate rate not computed",
                    missing=missing,method="same signal-bar broker timestamp + side; no inferred events")
    return dict(available=False,reason="Prior-family exports require schema audit before comparison",
                missing=[],method="same signal-bar broker timestamp + side; no inferred events")


def _call(name,mode,params,*,start=native.START,end=native.END,delay=200,deposit=10000,tester_login=None,evidence_base=None):
    return execute(name,mode,params,start=start,end=end,delay=delay,deposit=deposit,
                   tester_login=tester_login,evidence_base=evidence_base)


def run_all(prefix="r6_a",tester_login=None,*,evidence_base=None):
    validate_tester_login(tester_login)
    if not re.fullmatch(r"r6_[A-Za-z0-9_]+",prefix):
        raise ValueError("R6 run prefix must start r6_ and contain safe characters")
    run_base=BASE.resolve() if evidence_base is None else Path(evidence_base).resolve()
    if run_base not in APPROVED_BASES:
        raise ValueError("R6 evidence root must be default or approved postupdate root")
    progress=dict(project="Research Candidate R6, preregistered signal screen only",
        round_label="R6",source_sha=__import__("hashlib").sha256((ROOT/SOURCE).read_bytes()).hexdigest().upper(),
        development=[],validation=[],promotion=False,qualified=False,genuinely_unseen_oos=False,
        tester_connection_login=tester_login,
        cross_family_duplicates=cross_family_duplicate_status(),
        selection_lock=None,release_status="NOT_A_RELEASE",
        evidence_root=run_base.relative_to(ROOT.resolve()).as_posix())

    # Always run R6 mode 0 and compare ordered economics to a strictly validated
    # accepted R5 mode-0 control, otherwise to the frozen V24 production control.
    r5_control=accepted_r5_mode0(tester_login,evidence_base=run_base)
    production=None if r5_control is not None else accepted_v24_production()
    baseline=_call(f"{prefix}_baseline",0,{},tester_login=tester_login,evidence_base=run_base)
    if r5_control is not None:
        progress["parity_control"]="accepted_R5_mode0"
        progress["parity_control_run"]=r5_control["evidence_run"]
        progress["parity_control_root"]=run_base.relative_to(ROOT.resolve()).as_posix()
        progress["parity"]=native.parity(r5_control,baseline,evidence_base=run_base,production_base=run_base)
    else:
        progress["parity_control"]="accepted_V24_production_fallback"
        progress["parity_control_run"]=production["evidence_run"]
        progress["parity_control_root"]=OLD_BASE.relative_to(ROOT.resolve()).as_posix()
        progress["parity"]=native.parity(production,baseline,evidence_base=run_base,production_base=OLD_BASE)
    if progress["parity"].get("passed") is not True:
        raise ValueError("R6 exact mode-0 native parity failed; stop batch")
    progress["baseline"]=baseline
    save(run_base/f"{prefix}_progress.json",progress)

    def checked_call(*args,**kwargs):
        result=_call(*args,evidence_base=run_base,**kwargs)
        native.verify_environment(baseline,result,evidence_base=run_base)
        return result

    for mode,params,tag in configurations():
        result=checked_call(f"{prefix}_dev_{tag}",mode,params,end=native.DEV_END,tester_login=tester_login)
        progress["development"].append(dict(mode=mode,parameters=params,config_tag=tag,
            result=result,eligible=qualify(result),native_fixture_checks=result.get("native_mql_fixture_checks")))
        save(run_base/f"{prefix}_progress.json",progress)

    dev_survivors=[r for r in progress["development"] if r["eligible"]]
    shortlist=sorted(dev_survivors,key=lambda r:(r["mode"],r["parameters"]["InpEntryStrength"]))
    progress["development_shortlist"]=[dict(mode=x["mode"],parameters=x["parameters"],config_tag=x["config_tag"]) for x in shortlist]
    save(run_base/f"{prefix}_progress.json",progress)
    for item in shortlist:
        result=checked_call(f"{prefix}_val_{item['config_tag']}",item["mode"],item["parameters"],
            start=native.DEV_END,end=native.VAL_END,tester_login=tester_login)
        progress["validation"].append(dict(mode=item["mode"],parameters=item["parameters"],
            config_tag=item["config_tag"],result=result,eligible=qualify(result,40)))
        save(run_base/f"{prefix}_progress.json",progress)

    val_survivors=[x for x in progress["validation"] if x["eligible"]]
    if not val_survivors:
        pool=dev_survivors or progress["development"]
        best=max(pool,key=lambda x:(x["result"]["net"],-x["result"]["native_equity_dd_pct"],x["config_tag"]))
        progress["failure_reason"]="No validation-qualified candidate; descriptive full-period replay only"
        progress["descriptive_failed_candidate"]=dict(mode=best["mode"],parameters=best["parameters"],
            selected_from="development_only",result=checked_call(f"{prefix}_descriptive10m",best["mode"],
                best["parameters"],tester_login=tester_login),eligible=False,promotion=False)
    else:
        chosen=min(val_survivors,key=lambda x:(x["result"]["native_equity_dd_pct"],
            -x["result"]["net"],x["config_tag"]))
        lock=dict(mode=chosen["mode"],parameters=chosen["parameters"],config_tag=chosen["config_tag"],
            selected_using="validation_dd_then_net_then_stable_id",locked_utc=datetime.now(timezone.utc).isoformat(),
            reselect_after_confirmation=False)
        lockpath=run_base/f"{prefix}_selection_lock.json"
        if lockpath.exists():
            previous=json.loads(lockpath.read_text(encoding="utf-8"))
            if (previous.get("mode"),previous.get("parameters"),previous.get("config_tag"))!=(lock["mode"],lock["parameters"],lock["config_tag"]):
                raise ValueError("R6 selection lock changed; no reselection")
            lock=previous
        else:
            save(lockpath,lock)
        progress["selection_lock"]=lock
        confirm=checked_call(f"{prefix}_confirmation",lock["mode"],lock["parameters"],
            start=native.VAL_END,tester_login=tester_login)
        full=checked_call(f"{prefix}_locked10m",lock["mode"],lock["parameters"],tester_login=tester_login)
        positive_months=sum(m["net"]>0 for m in full["monthly"].values())
        baseline_net=baseline["net"]
        historical=(qualify(confirm,40,1.10) and qualify(full,150,1.15)
            and positive_months>=7 and full["net"]>baseline_net
            and full["native_equity_dd_pct"]<=baseline["native_equity_dd_pct"])
        stress70=checked_call(f"{prefix}_capital70",lock["mode"],lock["parameters"],deposit=70,tester_login=tester_login)
        delay500=checked_call(f"{prefix}_delay500",lock["mode"],lock["parameters"],delay=500,tester_login=tester_login)
        robustness=evaluate_robustness(dict(qualified=historical,full=full,
                                            delay500=delay500,capital70=stress70))
        progress.update(confirmation=confirm,full=full,positive_months=positive_months,
            historical_candidate_passed=historical,economic_robustness=robustness,
            economic_robustness_passed=robustness["historically_robust"],
            qualified=historical and robustness["historically_robust"],promotion=False,capital70=stress70,delay500=delay500,
            prospective_confirmation="NOT_ESTABLISHED_HISTORICAL_DATA_CONTAMINATED")
    progress["release_status"]="NOT_A_RELEASE"
    save(run_base/f"{prefix}_complete.json",progress)
    print(f"COMPLETE R6 qualified={progress['qualified']} promotion=False",flush=True)
    return progress


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--prefix",default="r6_a")
    parser.add_argument("--activate",action="store_true",help="run the bounded isolated native R6 plan")
    parser.add_argument("--tester-login",type=int,required=True,help="confirmed positive demo login for fresh isolated R6 runs")
    parser.add_argument("--evidence-root",type=Path,default=BASE,
                        help="default or approved postupdate native evidence root")
    args=parser.parse_args()
    if args.tester_login is not None and args.tester_login<=0:
        parser.error("--tester-login must be a positive account number")
    if not args.activate:
        parser.error("R6 inactive; review the four fixed cells, then pass --activate")
    if args.tester_login is None:
        parser.error("fresh native R6 runs require --tester-login with a positive account number")
    with native.lab_lease():
        run_all(args.prefix,args.tester_login,evidence_base=args.evidence_root)
