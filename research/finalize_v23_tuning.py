"""Independent native evidence audit and bounded descriptive finalist retests.

Does not promote a candidate or expand the parameter grid. No VM access.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from research.analyze_v23_backtest import csv_rows, parse_deals, report_rows, finite
from research.run_v23_tuning import BASE, LAB, ROOT, execute, save, sha
from research.v23_tuning_matrix import MODE_NAMES, SL_VALUES, TP_VALUES, BE_VALUES, metrics

NS = {"s": "urn:schemas-microsoft-com:office:spreadsheet"}


def audit_grid(folder, name, frames):
    root = ET.parse(folder / f"{name}.xml").getroot()
    rows = [[cell.find("s:Data", NS).text for cell in row.findall("s:Cell", NS)]
            for row in root.findall(".//s:Table/s:Row", NS)]
    native = [dict(zip(rows[0], row)) for row in rows[1:]]
    by_pass = {int(row["Pass"]): row for row in native}
    if len(native) != 36 or len(by_pass) != 36 or len(frames) != 36:
        raise ValueError("Native XML grid incomplete or duplicated")
    for frame in frames:
        row = by_pass[int(frame["pass"])]
        tp_index, be_index = int(row["InpTPGridIndex"]), int(row["InpBEGridIndex"])
        if not 0 <= tp_index < len(TP_VALUES) or not 0 <= be_index < len(BE_VALUES):
            raise ValueError("Native optimization index out of range")
        if abs(finite(row["Profit"]) - finite(frame["net"])) > .021:
            raise ValueError("XML profit differs from optimization frame")
        if int(row["Trades"]) != int(finite(frame["positions"])):
            raise ValueError("XML trade count differs from optimization frame")
        if abs(finite(row["Equity DD %"]) - finite(frame["equity_dd_pct"])) > .00011:
            raise ValueError("XML drawdown differs from optimization frame")
        if (finite(row["InpStopLossATRMul"]), TP_VALUES[tp_index],
                BE_VALUES[be_index]) != (
                float(frame["sl_atr"]), float(frame["tp_r"]), float(frame["be_r"])):
            raise ValueError("XML optimized inputs differ from optimization frame")
    journal = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("journal_*.txt"))
    if re.search(r"no real ticks|generated ticks|ticks?[^\n]*(?:discarded|replaced|missing)", journal, re.I):
        raise ValueError("Optimization tick-quality warning")
    return dict(native_rows=len(native), exact_parameter_matches=len(frames),
                monetary_tolerance_usd=.021, equity_dd_tolerance_percentage_points=.00011)


def cache_manifest():
    folder = LAB / "bases/MetaQuotes-Demo/ticks/XAUUSD"
    result = []
    for month in range(5, 10):
        p = folder / f"2026{month:02d}.tkc"
        result.append(dict(name=p.name, bytes=p.stat().st_size, sha256=sha(p)))
    return result


def native_sequence(folder, name):
    _, rows = report_rows(folder / f"{name}.htm")
    return [r for r in rows if r and r[0].startswith("2026.") and any(v in ("buy", "sell") for v in r)]


def diagnose(result):
    name = result["evidence_run"]
    folder = BASE / "runs" / name
    raw = csv_rows(folder / f"{name}_raw.csv")
    trades, cash = parse_deals(csv_rows(folder / f"{name}_deals.csv"))
    signature = json.loads((folder / "accepted.json").read_text())["signature"]
    if len(cash) != 1 or cash[0]["type"] != 2 or abs(cash[0]["net"] - signature["deposit"]) > .021:
        raise ValueError("Unexpected cash adjustment")
    gates = dict(Counter(r["gate"] for r in raw))
    journal = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("journal_*.txt"))
    specs = {r["key"]: r["value"] for r in csv_rows(folder / f"{name}_spec.csv")}
    return dict(candidate_gate_counts=gates, margin_gate_bars=gates.get("margin", 0),
                final_balance=float(specs["final_balance"]), first_tick=specs["first_tick"],
                last_tick=specs["last_tick"], last_position_close=trades[-1]["close"] if trades else None,
                native_stopout=result["stopout"], stopout_journal=bool("stop out" in journal.lower() or "stopout" in journal.lower()),
                winning_positions_above_1usd=sum(t["net"] > 1 for t in trades),
                winning_positions_above_2usd=sum(t["net"] > 2 for t in trades),
                average_net_per_position=result["net"] / len(trades) if trades else None,
                forced_end_exits=sum("end of test" in t["comment"].lower() for t in trades),
                forced_end_net=sum(t["net"] for t in trades if "end of test" in t["comment"].lower()))


def finalize(prefix):
    complete = BASE / f"{prefix}_complete.json"
    if not complete.exists():
        raise ValueError("Primary batch incomplete")
    batch = json.loads(complete.read_text())
    audit = dict(grid={}, descriptive_retests={}, promotion=False)
    before = cache_manifest()
    previous = json.loads((ROOT / "reports/v23_backtest_20261004/runs/original_full_reference/tick_cache_manifest.json").read_text())
    expected = [r for r in previous if r["name"].endswith(".tkc")]
    if before != expected:
        raise ValueError("May-Sep tick-cache hashes differ from previously audited cache")
    original_name = next((p.parent.name for p in sorted((BASE / "runs").glob(f"{prefix}_original_parity*/accepted.json"))), None)
    original = json.loads((BASE / "runs" / original_name / "accepted.json").read_text())
    baseline_name = batch["comparison"]["vm_fade"].get("evidence_run", f"{prefix}_compare_vm_fade")
    if native_sequence(BASE / "runs" / original_name, original_name) != native_sequence(BASE / "runs" / baseline_name, baseline_name):
        raise ValueError("Original binary native order/deal sequence differs from harness")
    a = original["result"]["native"]
    b = batch["comparison"]["vm_fade"]["native"]
    for key in ("Total Trades", "Total Net Profit", "Ticks", "Bars", "History Quality", "Equity Drawdown Maximal", "Balance Drawdown Maximal"):
        if a[key] != b[key]:
            raise ValueError(f"Original binary full parity differs: {key}")
    audit["baseline_parity"] = dict(passed=True, original_run=original_name,
            harness_run=baseline_name, comparison="Ordered native HTML orders/deals and seven native metrics")
    for kind in ("full_grid", "development"):
        for label, result in batch[kind].items():
            name = result["evidence_run"]
            audit["grid"][f"{kind}_{label}"] = audit_grid(BASE / "runs" / name, name, result["rows"])
    save(BASE / f"{prefix}_evidence_audit.json", audit)
    for mode, label in MODE_NAMES.items():
        best = max(batch["full_grid"][label]["rows"], key=lambda row: metrics(row)["net"])
        params = dict(InpStopLossATRMul=float(best["sl_atr"]),
                      InpTakeProfitRRMul=float(best["tp_r"]), InpBETriggerR=float(best["be_r"]))
        full = execute(f"{prefix}_descriptive_best_{label}", mode, params)
        if abs(full["net"] - float(best["net"])) > .03 or full["trades"] != int(float(best["positions"])):
            raise ValueError("Descriptive grid winner failed independent native retest")
        capital = execute(f"{prefix}_descriptive_best70_{label}", mode, params, deposit=70)
        audit["descriptive_retests"][label] = dict(parameters=params, full=full, capital70=capital,
                full_diagnostics=diagnose(full), capital70_diagnostics=diagnose(capital),
                note="Chosen by full-sample highest net only. Not validated or deployment-approved.")
        save(BASE / f"{prefix}_evidence_audit.json", audit)
    after = cache_manifest()
    if before != after:
        raise ValueError("Tick cache changed during descriptive retests")
    audit["tick_cache"] = dict(before=before, after=after, matches_prior_audit=True)
    audit["complete"] = True
    save(BASE / f"{prefix}_evidence_audit.json", audit)
    print("FINAL EVIDENCE AUDIT COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix")
    finalize(parser.parse_args().prefix)
