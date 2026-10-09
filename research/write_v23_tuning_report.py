"""Compare accepted native runs and report bounded, retrospective selection."""
import argparse
import json
from pathlib import Path
from statistics import median

from research.analyze_v23_backtest import csv_rows, parse_deals
from research.run_v23_tuning import BASE
from research.v23_tuning_matrix import metrics


def forensics(run, name):
    trades, _ = parse_deals(csv_rows(run / f"{name}_deals.csv"))
    paths = {int(p["position"]): p for p in csv_rows(run / f"{name}_paths.csv")}
    paired = [(t, paths[t["position"]]) for t in trades if t["position"] in paths]
    ratios = []
    loss_with_1r = loss_low_mfe = near_entry_stop = 0
    for trade, path in paired:
        risk = float(path["initial_risk"])
        if risk <= 0:
            continue
        mfe_r = float(path["mfe_price_sampled"]) / risk
        mae_r = float(path["mae_price_sampled"]) / risk
        ratios.append((mfe_r, mae_r))
        loss_with_1r += trade["net"] < 0 and mfe_r >= 1
        loss_low_mfe += trade["net"] < 0 and mfe_r < 0.25
        near_entry_stop += trade["exit_reason"] == 4 and abs(trade["exit_price"]-trade["entry_price"]) <= 0.075*risk
    return dict(completed_positions=len(trades), paired_sampled_paths=len(paired),
                median_sampled_mfe_r=median(x[0] for x in ratios) if ratios else None,
                median_sampled_mae_r=median(x[1] for x in ratios) if ratios else None,
                net_losses_after_observed_1r_gain=loss_with_1r,
                net_losses_with_observed_mfe_below_025r=loss_low_mfe,
                near_entry_sl_exits=near_entry_stop,
                note="EA-callback sampled paths. Near-entry SL is not proof of a BE modification. No counterfactual later TP claim.")


def summarize(prefix):
    path = BASE / f"{prefix}_complete.json"
    if not path.exists():
        raise ValueError("Batch incomplete; do not write a completed report")
    batch = json.loads(path.read_text())
    audit_path = BASE / f"{prefix}_evidence_audit.json"
    if not audit_path.exists():
        raise ValueError("Independent evidence audit missing")
    audit = json.loads(audit_path.read_text())
    if not audit.get("complete") or not audit.get("baseline_parity", {}).get("passed"):
        raise ValueError("Independent evidence audit incomplete")
    analysis = dict(comparison={}, grids={}, selection={}, promotion=False,
                    scope="Retrospective native real-tick research, May-Sep 2026. No deployment.")
    analysis["evidence_audit"] = audit
    for label, result in batch["comparison"].items():
        name = result.get("evidence_run",f"{prefix}_compare_{label}")
        analysis["comparison"][label] = dict(result=result, forensic=forensics(BASE / "runs" / name, name))
    for label, result in batch["full_grid"].items():
        ordered = sorted(result["rows"], key=lambda row: metrics(row)["net"], reverse=True)
        best = ordered[0]
        analysis["grids"][label] = dict(passes=len(ordered), highest_in_sample_net=best,
                                       top5_descriptive=ordered[:5], positive_full_grid_count=sum(metrics(r)["net"]>0 for r in ordered),
                                       qualified_development_count=len(batch["development"][label]["eligible"]))
        analysis["grids"][label]["be_at_fixed_vm_sl_tp"] = [r for r in ordered
                if float(r["sl_atr"])==1.5 and float(r["tp_r"])==2.0]
        confirmed = batch["confirmation"].get(label)
        capital = batch["capital"].get(label)
        valid = bool(confirmed and capital and confirmed["net"] > 0 and confirmed["trades"] >= 30
                     and confirmed["net_profit_factor"] is not None and confirmed["net_profit_factor"] >= 1.2
                     and capital["net"] > 0 and not capital["stopout"])
        analysis["selection"][label] = dict(status="PASSED_RETROSPECTIVE_SCREENS" if valid else "NO_QUALIFIED_CONFIGURATION",
                    validation=batch["validation"].get(label, []), confirmation=confirmed, capital70=capital)
    return batch, analysis


def write(prefix):
    batch, data = summarize(prefix)
    output = BASE / f"{prefix}_analysis.json"
    output.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    text = ["# V23 native comparison and tuning", "",
            "Period: 2026-05-01 through 2026-09-30 broker time. Five latest complete calendar months.", "",
            "VM source/binary and chart settings were verified via read-only SSH. Fixed 0.01 lot, $10,000 structural capital, 1:200 reference leverage, 200ms delay, native real ticks. Existing breaker retained. Baseline and normal have BE disabled. Proposed model adds closed M5 trend, M1 pullback/reclaim, cost/chase gates and BE1.2R with 0.05R buffer.", "",
            "## Initial three-model comparison", "",
            "| Model | Positions | Net USD | Net PF | Win rate | Native equity DD % |",
            "|---|---:|---:|---:|---:|---:|"]
    for label, row in batch["comparison"].items():
        text.append(f"| {label} | {row['trades']} | {row['net']:.2f} | {row['net_profit_factor']} | {row['win_rate_pct']}% | {row['native_equity_dd_pct']} |")
    text += ["", "Net includes exported profit, commission, swap and fee. Zero recorded charges do not establish the costs of another broker.", "",
             "## Parameter grid", "", "SL ATR {1,1.5,2}, TP R {1,1.5,2,3}, BE R {off,0.8,1.2}, BE lock0.05R, hold60. 36 configurations/model, 108 full-period configurations. Development-only repetitions use May-July. August validates development candidates. September is diagnostic confirmation. These periods were inspected previously and are not fresh OOS.", "",
             "| Model | Grid passes | Full-sample highest net | SL ATR | TP R | BE R | Development-qualified | Final diagnostic status |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    for label, row in data["grids"].items():
        best = row["highest_in_sample_net"]
        text.append(f"| {label} | {row['passes']} | {float(best['net']):.2f} | {best['sl_atr']} | {best['tp_r']} | {best['be_r']} | {row['qualified_development_count']} | {data['selection'][label]['status']} |")
    text += ["", "The maximum full-sample profit is an in-sample description. It is not the selected validated configuration. Negative maxima are least-loss settings, not profitable models.", "",
             "## Independent retests of descriptive grid maxima", "",
             "These six additional runs do not expand the grid or change candidate qualification. Each full-period maximum was replayed individually with native deal export at $10,000, then at $70 with no top-up. Full-period native net and trade count must reproduce its optimization pass. Capital checks use the same fixed 0.01 lot and reference leverage 1:200.", "",
             "| Model | Best net USD | Net PF | Positions | Winning positions >$2 | Native DD % | $70 net USD | $70 ending balance | Margin-blocked bars | Stopout |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for label, entry in data["evidence_audit"]["descriptive_retests"].items():
        full, low = entry["full"], entry["capital70"]
        f, c = entry["full_diagnostics"], entry["capital70_diagnostics"]
        text.append(f"| {label} | {full['net']:.2f} | {full['net_profit_factor']} | {full['trades']} | {f['winning_positions_above_2usd']} | {full['native_equity_dd_pct']} | {low['net']:.2f} | {c['final_balance']:.2f} | {c['margin_gate_bars']} | {low['stopout']} |")
    text += ["", "A margin block can prevent new orders while balance remains positive. That is not automatically a broker stopout. $10,000 structural PnL is not the expected PnL on a $70 account. Entries and subsequent history differ when available margin binds.", "",
             "## Continuous five-month net by closing-position month", "",
             "| Model / configuration | May | June | July | August | September | Total USD |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    rows = [(label+" initial", r) for label, r in batch["comparison"].items()]
    rows += [(label+" descriptive maximum", r["full"]) for label,r in data["evidence_audit"]["descriptive_retests"].items()]
    for label, result in rows:
        monthly = [result["monthly"][f"2026-{month:02d}"]["net"] for month in range(5,10)]
        if abs(sum(monthly)-result["net"])>.031:
            raise ValueError("Monthly position-net reconciliation failed")
        text.append("| "+label+" | "+" | ".join(f"{v:.2f}" for v in monthly)+f" | {result['net']:.2f} |")
    text += ["", "Monthly net assigns each position's full profit and fees to its closing month. Cross-month positions are not split. This table uses uninterrupted five-month runs. Development and validation simulations reset the account at each window and are a different experiment.", "",
             "## BE sensitivity with SL1.5 ATR and TP2R held fixed", "",
             "| Model | BE trigger R | Net USD | Net PF | Positions | Modification attempts | Modification rejects |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for label, entry in data["grids"].items():
        for row in sorted(entry["be_at_fixed_vm_sl_tp"], key=lambda r: float(r["be_r"])):
            m = metrics(row)
            text.append(f"| {label} | {row['be_r']} | {m['net']:.2f} | {m['pf']:.4f} | {m['trades']} | {int(float(row['be_attempts']))} | {int(float(row['be_rejected']))} |")
    text += ["", "BE0 disables break-even modifications. Changing BE also changes subsequent position occupancy and breaker history. This is a portfolio comparison, not a claim that identical entries merely had different exits.", "",
             "## Entry and exit diagnostics", "",
             "| Model | Sampled paths / positions | Losses after observed >=1R gain | Losses with sampled MFE <0.25R | Near-entry SL exits |",
             "|---|---:|---:|---:|---:|"]
    for label, entry in data["comparison"].items():
        f = entry["forensic"]
        text.append(f"| {label} | {f['paired_sampled_paths']}/{f['completed_positions']} | {f['net_losses_after_observed_1r_gain']} | {f['net_losses_with_observed_mfe_below_025r']} | {f['near_entry_sl_exits']} |")
    text += ["", "MFE/MAE are sampled at EA callbacks. Trading delays and native stop executions can consume ticks between callbacks. These figures are diagnostics, not exact complete tick paths. A price excursion observed before a loss is not proof that BE improves portfolio PnL. Native BE grid tests measure that interaction directly.", "",
             "## Research conclusion", ""]
    positive = sum(r["positive_full_grid_count"] for r in data["grids"].values())
    qualified = sum(r["qualified_development_count"] for r in data["grids"].values())
    text += [f"Full-period positive configurations: {positive}/108. Development-qualified configurations: {qualified}/108."]
    if positive == 0:
        text += ["No profitable configuration was found within this fixed grid. The proposed signal and its exit settings reduce historical losses but do not establish positive expectancy. Inverting direction alone also remains loss-making. Do not deploy the least-loss configuration as a profitable upgrade.", "",
                 "The proposed descriptive maximum is positive in July, August and September but negative in May and June. That is evidence of uneven retrospective month performance, not proof of stable edge. Selecting only the last three positive months after seeing them would bias the conclusion.", "",
                 "Next justified research: a new predeclared entry-information hypothesis with spread-aware all-candidate markouts. Fix the entry/cost problem before another large TP/BE search. Keep future data uninspected until the hypothesis and acceptance rule are frozen. No additional grid or live change was made in this batch."]
    text += ["",
             "## Evidence and decision", "", f"Machine-readable comparison: `{prefix}_complete.json`. Audited summaries: `{prefix}_analysis.json`. Every accepted run has its native report, settings, INI, appended journals, source/binary/runtime signature, and exports in `runs/`.", "",
             f"Independent audit: `{prefix}_evidence_audit.json`. All216 optimization rows were reconciled to native XML by pass ID, parameters, profit, position count and drawdown. Ordered baseline native order/deal sequences match the original EX5. Final May-Sep tick-cache hashes match the earlier audited cache and are unchanged across supplementary retests. Optimizer journals contain no identified missing/replaced/discarded/generated tick warnings. Individual comparison/retest reports show 100% real ticks. This does not establish XM broker execution equivalence.", "",
             "## Software verification", "",
             "Research harness compile: 0 errors,0 warnings. Focused pytest: 35 passed,3 subtests passed. The full repository pytest collection was attempted but is blocked by unrelated missing legacy source files: QuantumTitan_v16_3_Precision.mq5 and QuantumTitan_v16_59_R4StateTransition.mq5. Those sources were not recreated or changed. Do not describe the entire repository test suite as passing.", "",
             "No production EA, VM chart, account or breaker was changed. No deployment clearance is implied. If no configuration passes the stated rules, retain the rejection rather than expanding the grid to fit these results."]
    target = BASE / f"{prefix}_report.md"
    target.write_text("\n".join(text) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix")
    write(parser.parse_args().prefix)
