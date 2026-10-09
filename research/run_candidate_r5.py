"""Run the four frozen R5-C0 cells; C1 stays unrun until schedule is verified."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from itertools import product
from pathlib import Path

from research import run_v25_native as native
from research.run_v23_tuning import save
from research.candidate_release_evidence import evaluate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "research/ResearchCandidate_R5.mq5"
R4_SOURCE = "research/ResearchCandidate_R4.mq5"
BASE = ROOT / "reports/v25_research_20261008"
OLD_BASE = ROOT / "reports/v25_research_20261007"
POSTUPDATE_BASE = ROOT / "reports/v25_research_20261008_postupdate"
APPROVED_R5_BASES = {BASE.resolve(), POSTUPDATE_BASE.resolve()}


def configurations():
    """Fixed P0/P1 x A0/A1, all C0, SL1.5ATR and TP1R."""
    return [
        (5, dict(InpEntryStrength=preset, InpStopLossATRMul=1.5,
                 InpTakeProfitRRMul=1.0, InpRequireM1Alignment=aligned),
         f"p{preset}_a{int(aligned)}_c0")
        for preset, aligned in product((0, 1), (False, True))
    ]


def execute(*args, evidence_base=BASE, **kwargs):
    """Keep all R5 reports, runs, and runtime freeze under isolated evidence root."""
    return native.execute(*args, evidence_base=evidence_base, **kwargs)


def parameter_key(item):
    return tuple(sorted(item["parameters"].items()))


def qualify(row, min_trades=150, pf=1.20):
    return native.qualify(row, min_trades, pf)


def _r4_control_provenance(name: str, result: dict, evidence_root: Path, *,
                           policy: str, native_run_id: str | None):
    root = evidence_root.resolve()
    if root not in {OLD_BASE.resolve(), *APPROVED_R5_BASES}:
        raise ValueError("R4 control root is not an approved fixed evidence root")
    accepted_path = root / "runs" / name / "accepted.json"
    if not accepted_path.is_file():
        raise ValueError(f"R4 control accepted record missing: {name}")
    accepted = json.loads(accepted_path.read_text(encoding="utf-8-sig"))
    signature = accepted.get("signature") if isinstance(accepted, dict) else None
    accepted_result = accepted.get("result") if isinstance(accepted, dict) else None
    source_sha = hashlib.sha256((ROOT / R4_SOURCE).read_bytes()).hexdigest().upper()
    if (not isinstance(signature, dict) or not isinstance(accepted_result, dict)
            or accepted_result.get("evidence_run") != name
            or result.get("evidence_run") != name or signature.get("source_sha") != source_sha):
        raise ValueError(f"R4 control accepted signature/source mismatch: {name}")
    signature_sha = hashlib.sha256(json.dumps(signature, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest().upper()
    return dict(kind="accepted_reuse" if policy == "legacy_r4" else "fresh_native",
        evidence_run=name, evidence_root=root.relative_to(ROOT).as_posix(),
        source_sha256=source_sha, signature_sha256=signature_sha,
        native_run_id=native_run_id)


def run_all(prefix: str, tester_login: int | None = None, *, fresh_controls: bool = False,
            evidence_base: Path | None = None):
    if not prefix.startswith("r5_"):
        raise ValueError("R5 RunTag prefix contract requires r5_ prefix")
    if type(tester_login) is not int or tester_login <= 0:
        raise ValueError("tester_login must be a positive integer")
    run_base = BASE.resolve() if evidence_base is None else Path(evidence_base).resolve()
    if run_base not in APPROVED_R5_BASES:
        raise ValueError("R5 evidence root must be reports/v25_research_20261008 or the approved postupdate root")
    r5_root_rel = run_base.relative_to(ROOT.resolve()).as_posix()
    control_policy = "fresh_same_cache" if fresh_controls else "legacy_r4"
    control_mapping = {str(preset): (f"{prefix}_r4_control_p{preset}" if fresh_controls
        else f"r4_a_dev_5_{preset}_sl1p5_tp1p0") for preset in (0, 1)}
    progress = dict(project="Research Candidate R5, not V25 release", round_label="R5",
                    schedule_status="UNRUN_SCHEDULE_UNVERIFIED",
                    unrun_configs=["R5-P0-A0-C1", "R5-P0-A1-C1", "R5-P1-A0-C1", "R5-P1-A1-C1"],
                    development=[], validation=[], r4_control_parity={}, qualified=False, promotion=False,
                    genuinely_unseen_oos=False, control_policy=control_policy,
                    control_mapping=control_mapping,
                    control_roots={"baseline_production": "r5_base" if fresh_controls else "r4_base",
                                   "r4_controls": "r5_base" if fresh_controls else "r4_base"},
                    evidence_roots={"r4_base": "reports/v25_research_20261007",
                                    "r5_base": r5_root_rel},
                    r4_control_provenance={})
    if fresh_controls:
        production_name = f"{prefix}_production_v24"
        production_root = run_base
        production = execute(production_name, production=True, evidence_base=run_base,
                             tester_login=tester_login)
    else:
        production_name = "r1_b_production_v24"
        production_root = OLD_BASE
        production = execute(production_name, production=True, evidence_base=OLD_BASE)
    progress["baseline_control_run"] = production_name
    baseline = execute(f"{prefix}_baseline", mode=0, candidate_source=SOURCE,
                       tester_login=tester_login, evidence_base=run_base)
    baseline_parity = native.parity(production, baseline,
        evidence_base=run_base, production_base=production_root)
    if baseline_parity.get("passed") is not True:
        raise ValueError("R5 mode0 baseline did not exactly reconcile with production V24")
    native.verify_environment(production, baseline, evidence_base=run_base,
                              reference_base=production_root)
    progress.update(baseline=baseline, parity=baseline_parity)
    save(run_base / f"{prefix}_progress.json", progress)

    def checked_execute(*args, **kwargs):
        kwargs.setdefault("evidence_base", run_base)
        result = execute(*args, **kwargs)
        native.verify_environment(baseline, result, evidence_base=run_base)
        return result

    for mode, params, config_tag in configurations():
        result = checked_execute(f"{prefix}_dev_{config_tag}", mode, params,
                                end=native.DEV_END, candidate_source=SOURCE,
                                tester_login=tester_login, evidence_base=run_base)
        progress["development"].append(dict(mode=mode, parameters=params,
            config_tag=config_tag, result=result, eligible=qualify(result)))
        save(run_base / f"{prefix}_progress.json", progress)
        if mode == 5 and not params["InpRequireM1Alignment"]:
            preset = params["InpEntryStrength"]
            control_name = control_mapping[str(preset)]
            if fresh_controls:
                control_root = run_base
                control = native.execute(control_name, mode=5,
                    overrides=dict(InpEntryStrength=preset, InpStopLossATRMul=1.5,
                                   InpTakeProfitRRMul=1.0), end=native.DEV_END,
                    candidate_source=R4_SOURCE, evidence_base=run_base,
                    tester_login=tester_login)
            else:
                control_root = OLD_BASE
                control = native.execute(control_name, mode=5,
                    overrides=dict(InpEntryStrength=preset, InpStopLossATRMul=1.5,
                                   InpTakeProfitRRMul=1.0), end=native.DEV_END,
                    candidate_source=R4_SOURCE, evidence_base=OLD_BASE)
            reconciliation = native.parity(control, result, evidence_base=run_base,
                                           production_base=control_root)
            if reconciliation.get("passed") is not True:
                raise ValueError(f"R5 A0 parity failed against accepted R4 control {control_name}")
            progress["r4_control_parity"][str(preset)] = dict(
                r4_control=control_name, r5_run=result["evidence_run"],
                control_root="r5_base" if fresh_controls else "r4_base", **reconciliation)
            control_provenance = _r4_control_provenance(control_name, control, control_root,
                policy=control_policy, native_run_id=control_name if fresh_controls else None)
            progress["r4_control_provenance"][str(preset)] = control_provenance
            progress["r4_control_parity"][str(preset)]["control_provenance"] = control_provenance
            save(run_base / f"{prefix}_progress.json", progress)

    shortlist = sorted((row for row in progress["development"] if row["eligible"]),
        key=lambda row: (row["result"]["native_equity_dd_pct"],
                         -row["result"]["net"], parameter_key(row)))[:3]
    progress["development_shortlist"] = [dict(mode=x["mode"], parameters=x["parameters"],
                                               config_tag=x["config_tag"]) for x in shortlist]
    save(run_base / f"{prefix}_progress.json", progress)
    for item in shortlist:
        result = checked_execute(f"{prefix}_val_{item['config_tag']}", item["mode"],
            item["parameters"], start=native.DEV_END, end=native.VAL_END,
            candidate_source=SOURCE, tester_login=tester_login, evidence_base=run_base)
        progress["validation"].append(dict(mode=item["mode"], parameters=item["parameters"],
                                          result=result, eligible=qualify(result, 40)))
        save(run_base / f"{prefix}_progress.json", progress)

    survivors = [row for row in progress["validation"] if row["eligible"]]
    if survivors:
        chosen = min(survivors, key=lambda row: (row["result"]["native_equity_dd_pct"],
            -row["result"]["net"], row["mode"], parameter_key(row)))
        lock = dict(mode=chosen["mode"], parameters=chosen["parameters"],
            selected_using="development_and_validation_only",
            locked_utc=datetime.now(timezone.utc).isoformat(), reselect_after_confirmation=False)
        lock_path = run_base / f"{prefix}_selection_lock.json"
        if lock_path.exists():
            prior = json.loads(lock_path.read_text())
            if prior["mode"] != lock["mode"] or prior["parameters"] != lock["parameters"]:
                raise ValueError("R5 selection lock changed")
            lock = prior
        else:
            save(lock_path, lock)
        progress["selection_lock"] = lock
        confirm = checked_execute(f"{prefix}_confirmation", lock["mode"], lock["parameters"],
            start=native.VAL_END, candidate_source=SOURCE, tester_login=tester_login,
            evidence_base=run_base)
        full = checked_execute(f"{prefix}_locked10m", lock["mode"], lock["parameters"],
            candidate_source=SOURCE, tester_login=tester_login, evidence_base=run_base)
        positive_months = sum(month["net"] > 0 for month in full["monthly"].values())
        progress.update(confirmation=confirm, full=full, positive_months=positive_months,
            qualified=qualify(confirm, 40, 1.10) and qualify(full, 150, 1.15)
                and positive_months >= 7 and full["net"] > baseline["net"]
                and full["native_equity_dd_pct"] <= baseline["native_equity_dd_pct"],
            capital70=checked_execute(f"{prefix}_capital70", lock["mode"], lock["parameters"],
                deposit=70, candidate_source=SOURCE, tester_login=tester_login, evidence_base=run_base),
            baseline70=checked_execute(f"{prefix}_baseline70", deposit=70, candidate_source=SOURCE,
                               tester_login=tester_login, evidence_base=run_base),
            delay500=checked_execute(f"{prefix}_delay500", lock["mode"], lock["parameters"],
                delay=500, candidate_source=SOURCE, tester_login=tester_login,
                evidence_base=run_base))
    elif progress["development"]:
        best = max(progress["development"], key=lambda row: (row["result"]["net"],
                    -row["result"]["native_equity_dd_pct"]))
        progress["failure_reason"] = "No development/validation-qualified candidate"
        progress["descriptive_failed_candidate"] = dict(mode=best["mode"],
            parameters=best["parameters"], selection="Development-only maximum, failed",
            result=checked_execute(f"{prefix}_descriptive10m", best["mode"],
                best["parameters"], candidate_source=SOURCE, tester_login=tester_login,
                evidence_base=run_base))
    progress["release_evidence"] = evaluate(progress)
    progress["release_evidence"]["promotion"] = False
    progress["release_evidence"]["schedule_status"] = "UNRUN_SCHEDULE_UNVERIFIED"
    save(run_base / f"{prefix}_complete.json", progress)
    print(f"COMPLETE R5 qualified={progress['qualified']} promotion=False schedule=C1_UNRUN_SCHEDULE_UNVERIFIED", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="r5_a")
    parser.add_argument("--tester-login", type=int, required=True,
                        help="confirmed positive demo login for fresh isolated R5 runs")
    parser.add_argument("--evidence-root", type=Path, default=BASE,
                        help="approved isolated R5 evidence root; default preserves existing root")
    parser.add_argument("--fresh-controls", action="store_true",
                        help="run new same-cache V24 and R4 controls in isolated R5 evidence root")
    parser.add_argument("--activate", action="store_true",
                        help="explicitly authorize bounded isolated native R5 runs")
    args = parser.parse_args()
    if not args.activate:
        parser.error("R5 inactive; pass --activate after review of the frozen four-cell plan")
    with native.lab_lease():
        run_all(args.prefix, tester_login=args.tester_login,
                fresh_controls=args.fresh_controls, evidence_base=args.evidence_root)
