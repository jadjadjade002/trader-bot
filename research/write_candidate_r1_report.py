"""Render only accepted native evidence. No promotion from descriptive winners."""
import argparse
from collections import Counter
import json
from pathlib import Path
from research.run_v25_native import BASE, ROOT, MODE_NAMES
from research.analyze_v23_backtest import csv_rows, parse_deals, bucket


def write(prefix):
    path = BASE / f"{prefix}_complete.json"
    if not path.exists():
        raise ValueError("Native batch not complete")
    evidence = json.loads(path.read_text())
    r2 = isinstance(evidence["development"], list)
    round_label = evidence.get("round_label", "R2" if r2 else "R1")
    baseline = evidence["baseline"]
    full = evidence.get("full") or evidence["descriptive_failed_candidate"]["result"]
    label = "Locked candidate" if "selection_lock" in evidence else "Rejected descriptive candidate"
    lines = [f"# Research Candidate {round_label} native outcome", "", "Not a V25 release. No deployment performed.", "",
             f"Historical qualification: **{evidence['qualified']}**. Promotion: **False**.",
             "Ten complete calendar months:2025-12-01 to2026-10-01 exclusive, broker clock.",
             "May-September previously inspected. Historical confirmation is not genuinely unseen OOS.", "",
             "## V24 baseline and candidate", "",
             "| Metric | Frozen V24 | " + label + " |", "| --- | ---: | ---: |"]
    for key in ("trades", "wins", "losses", "win_rate_pct", "net", "net_profit_factor", "native_equity_dd_pct", "commission", "swap", "fee"):
        lines.append(f"| {key} | {baseline[key]} | {full[key]} |")
    lines += ["", "Structural capital$10,000, fixed0.01lot, leverage1:200, real ticks,200ms delay. These results are not a prediction for$70 or for XM.",
              "Deal profit already includes bid/ask fill economics. Explicit charges are separate, do not subtract spread twice.", "",
              "## Monthly net USD", "", "| Broker month | V24 | Candidate |", "| --- | ---: | ---: |"]
    for m in baseline["monthly"]:
        lines.append(f"| {m} | {baseline['monthly'][m]['net']:.2f} | {full['monthly'][m]['net']:.2f} |")
    lines += ["", "## Development and selection", ""]
    if r2:
        if round_label == "R4":
            from research.run_candidate_r4 import FAMILIES
        elif round_label == "R3":
            from research.run_candidate_r3 import FAMILIES
        else:
            from research.run_candidate_r2 import FAMILIES
        lines.append(f"Frozen R2 exhaustion signal. {len(evidence['development'])} bounded SL/TP configurations; hold60/BEoff unchanged." if round_label == "R4" else f"Fixed SL1.5ATR/TP2R/hold60/BEoff. {len(evidence['development'])} entry configurations, not an exit optimizer.")
        for item in evidence["development"]:
            result = item["result"]
            exits = (f" SL{item['parameters']['InpStopLossATRMul']}ATR TP{item['parameters']['InpTakeProfitRRMul']}R" if round_label == "R4" else "")
            lines.append(f"- {FAMILIES[item['mode']]} preset{item['parameters']['InpEntryStrength']}{exits}: net{result['net']:.2f}, PF{result['net_profit_factor']}, positions{result['trades']}, DD{result['native_equity_dd_pct']}%, eligible={item['eligible']}.")
    else:
        for mode, dev in evidence["development"].items():
            rows = dev["rows"]
            lines.append(f"- {MODE_NAMES[int(mode)]}: {len(rows)} audited native configs. Development max net{max(float(r['net']) for r in rows):.2f}USD.")
    lines += [f"- Validation candidates: {len(evidence['validation'])}.",
              f"- Validation qualified: {sum(r['eligible'] for r in evidence['validation'])}.",
              f"- Native baseline parity: {evidence['parity']}."]
    if round_label == "R4":
        lines += ["", "## Fixed-signal exit matrix", "",
                  "Same signal predicate, different exit/occupancy paths. Net differences are native strategy outcomes, not matched per-trade counterfactuals.", "",
                  "| Preset | SL ATR | TP R | Positions | Win % | Net USD | PF | DD % |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for item in evidence["development"]:
            p, r = item["parameters"], item["result"]
            lines.append(f"| {p['InpEntryStrength']} | {p['InpStopLossATRMul']} | {p['InpTakeProfitRRMul']} | {r['trades']} | {r['win_rate_pct']} | {r['net']:.2f} | {r['net_profit_factor']} | {r['native_equity_dd_pct']} |")
        lines += ["", "### Development direction and actual exits", "",
                  "Reason 3=Expert, 4=SL, 5=TP, 6=stopout. Side and exit columns below are separate margins, not a side-by-exit causal table.", "",
                  "| Config | BUY n / net | SELL n / net | Expert n / net | SL n / net | TP n / net |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
        def cell(row):
            return f"{row.get('trades', 0)} / {row.get('net', 0):.2f}"
        for item in evidence["development"]:
            r = item["result"]
            columns = [cell(r['sides'][s]) for s in ('buy', 'sell')] + [cell(r['exits'].get(k, {})) for k in ('3', '4', '5')]
            lines.append("| " + item['config_tag'] + " | " + " | ".join(columns) + " |")
        lines += ["", "### Six development months for every configuration", "",
                  "| Config | Dec | Jan | Feb | Mar | Apr | May |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for item in evidence["development"]:
            nets = [f"{item['result']['monthly'][m]['net']:.2f}" for m in ('2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05')]
            lines.append("| " + item['config_tag'] + " | " + " | ".join(nets) + " |")
    if "selection_lock" in evidence:
        lines += ["", "Selection saved before confirmation. No second candidate selected after failure.",
                  "```json", json.dumps(evidence["selection_lock"], indent=2), "```",
                  f"Confirmation net{evidence['confirmation']['net']:.2f}USD, PF{evidence['confirmation']['net_profit_factor']}."]
    else:
        lines += ["", evidence["failure_reason"],
                  "Whole-period replay is a development-only descriptive maximum. It failed the qualification path and must not become a release.",
                  "```json", json.dumps(evidence["descriptive_failed_candidate"]["parameters"], indent=2), "```"]
    lines += ["", "## Additional-cost stress", "",
              f"- Baseline: {baseline['extra_cost_stress']}", f"- Candidate: {full['extra_cost_stress']}",
              "Hypothetical extra0.20/0.50USD per completed0.01lot position. Fixed-trade accounting only, not native spread/timing simulation.", "",
              "## Separate robustness screen", "", "```json",
              json.dumps(evidence.get("release_evidence", {"historically_robust": False, "reason": "not evaluated"}), indent=2), "```", "",
              "## Evidence limits", "",
              "Monthly observations are EA callbacks. Execution delay can skip callbacks, so callback counts are not raw tick counts. All ten months and their edges checked. Interior market-gap-free history is not independently proven.",
              "Native real-tick quality, journal errors, monthly cache/source/binary/runtime hashes and ordered baseline economics audited separately. Static/Python tests do not establish strategy profitability.",
              f"Source evidence: reports/v25_research_20261007/{prefix}_complete.json", ""]
    output = ROOT / f"docs/CANDIDATE_{round_label}_RESULTS_{prefix}.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix")
    write(parser.parse_args().prefix)
