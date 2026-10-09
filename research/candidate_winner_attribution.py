#!/usr/bin/env python3
"""Evidence-only paired attribution for the accepted R4 preset-1 TP sweep.

This summarizes actual native trades. It does not simulate alternate exits or
impute outcomes for unmatched entries.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import fmean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.analyze_v23_backtest import bucket, csv_rows, finite, parse_deals, report_rows

REPORT = ROOT / "reports/v25_research_20261007"
COMPLETE = REPORT / "r4_a_complete.json"
TP_VALUES = (0.75, 1.0, 1.5, 2.0)
START, END = "2025.12.01", "2026.06.01"
EXPECTED_OVERRIDES = {
    "InpEntryStrength": 1,
    "InpStopLossATRMul": 1.5,
}
EXPECTED_SOURCE_SHA = "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320"
EXPECTED_BINARY_SHA = "1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9"
LOT = 0.01
EPS = 1e-8


def _same_number(actual, expected, field):
    if abs(finite(actual) - expected) > 1e-10:
        raise ValueError(f"Mismatch for {field}: expected {expected}")


def _count(value, field):
    number = finite(value)
    if number < 0 or not number.is_integer():
        raise ValueError(f"Invalid integer count for {field}")
    return int(number)


def _integer(value, field):
    number = finite(value)
    if not number.is_integer():
        raise ValueError(f"Invalid integer {field}")
    return int(number)


def _entry_key(trade):
    """Exact native entry identity, deliberately without fuzzy tolerances."""
    return (_integer(trade["open_msc"], "entry timestamp"), trade["direction"], finite(trade["entry_price"]),
            finite(trade["volume"]))


def _unique_trade_map(trades, label):
    result = {}
    for trade in trades:
        key = _entry_key(trade)
        if key in result:
            raise ValueError(f"Duplicate exact entry key in {label}: {key!r}")
        result[key] = trade
    return result


def _validate_signature(accepted, tp, *, end=END):
    if "signature" not in accepted:
        raise ValueError("Accepted run signature missing; cannot establish frozen run controls")
    sig = accepted["signature"]
    required = {"start": START, "end": end, "mode": 5, "deposit": 10000,
                "delay_ms": 200, "optimize": False, "production": False}
    for key, expected in required.items():
        if sig.get(key) != expected:
            raise ValueError(f"Accepted signature mismatch for {key}: expected {expected!r}")
    overrides = sig.get("overrides")
    if not isinstance(overrides, dict):
        raise ValueError("Accepted signature overrides missing")
    expected = {**EXPECTED_OVERRIDES, "InpTakeProfitRRMul": tp}
    if set(overrides) != set(expected):
        raise ValueError("Accepted signature override keys differ from frozen TP sweep")
    for key, value in expected.items():
        if finite(overrides[key]) != value:
            raise ValueError(f"Accepted signature mismatch for {key}: expected {value!r}")
    if not sig.get("source_sha"):
        raise ValueError("Accepted source_sha missing; source identity unavailable")
    if sig["source_sha"] != EXPECTED_SOURCE_SHA or sig.get("binary_sha") != EXPECTED_BINARY_SHA:
        raise ValueError("Accepted source SHA/binary SHA differs from frozen native diagnostic")
    runtime = sig.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {"terminal64.exe", "metatester64.exe"}:
        raise ValueError("Accepted runtime identity malformed")
    if any(not isinstance(v, str) or re.fullmatch(r"[0-9A-Fa-f]{64}", v) is None
           for v in runtime.values()):
        raise ValueError("Accepted runtime SHA malformed")
    expected_months = ([202512, 202601, 202602, 202603, 202604, 202605]
                       if end == END else
                       [202512, 202601, 202602, 202603, 202604, 202605,
                        202606, 202607, 202608, 202609])
    cache = sig.get("tick_cache")
    if not isinstance(cache, list) or [x.get("month") for x in cache if isinstance(x, dict)] != expected_months:
        raise ValueError("Accepted tick cache month sequence malformed")
    for item in cache:
        if set(item) != {"month", "bytes", "sha256"}:
            raise ValueError("Accepted tick cache entry malformed")
        if _count(item["bytes"], "tick cache bytes") <= 0 or \
                not isinstance(item["sha256"], str) or re.fullmatch(r"[0-9A-Fa-f]{64}", item["sha256"]) is None:
            raise ValueError("Accepted tick cache identity malformed")
    if not isinstance(sig.get("set_sha"), str) or re.fullmatch(r"[0-9A-Fa-f]{64}", sig["set_sha"]) is None:
        raise ValueError("Accepted set_sha malformed")
    return sig


def _validate_settings(settings, tp):
    expected_settings = {"InpExperimentMode": 5, "InpEntryStrength": 1,
                       "InpStopLossATRMul": 1.5, "InpTakeProfitRRMul": tp,
                       "InpLotSize": LOT, "InpMaxHoldBars": 60,
                       "InpMinSLPoints": 150, "InpATRPeriod": 14,
                       "InpDonchianPeriod": 20, "InpEnableSessionGuard": "false",
                       "InpEnableSpreadGuard": "false", "InpEnableMarginGuard": "true",
                       "InpEnableHardSL": "true", "InpStartHour": 11, "InpEndHour": 16,
                       "InpMaxSpreadPts": 25, "InpFadeBreakouts": "false",
                       "InpMagicNumber": 992300, "InpTargetAccount": 0,
                       "InpEnableCircuitBreaker": "true", "InpMaxConsecutiveLosses": 4,
                       "InpCooldownMinutes": 90}
    allowed = set(expected_settings) | {"InpRunTag"}
    if "_set_sha" in settings:
        allowed.add("_set_sha")
    if set(settings) != allowed:
        raise ValueError("Native settings keys differ from frozen TP sweep")
    if not settings["InpRunTag"]:
        raise ValueError("Native setting missing: InpRunTag")
    for key, value in expected_settings.items():
        if key not in settings:
            raise ValueError(f"Native setting missing: {key}")
        actual = settings[key]
        if isinstance(value, str):
            if actual.lower() != value:
                raise ValueError(f"Native setting mismatch for {key}: expected {value!r}")
        else:
            _same_number(actual, value, key)
    return settings


def _settings_from_run(folder, stem, tp):
    set_path = folder / f"{stem}.set"
    if not set_path.is_file():
        raise ValueError(f"Native settings file missing: {set_path}")
    settings = {}
    raw = set_path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        decoded = raw.decode("utf-16", errors="strict")
    else:
        decoded = raw.decode("utf-8-sig", errors="strict")
    for line in decoded.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError(f"Malformed native setting line: {line!r}")
        key, value = line.split("=", 1)
        if key in settings:
            raise ValueError(f"Duplicate native setting: {key}")
        settings[key] = value
    _validate_settings(settings, tp)
    # Runner hashes normalized text after universal newline conversion, UTF-16 BOM included.
    settings["_set_sha"] = hashlib.sha256(decoded.replace("\r\n", "\n").encode("utf-16")).hexdigest()
    return settings


def _validate_run(accepted, deal_rows, settings, tp, report_metrics=None, *, end=END):
    sig = _validate_signature(accepted, tp, end=end)
    _validate_settings(settings, tp)
    for row in deal_rows:
        if int(finite(row.get("type", -1))) in (0, 1) and int(finite(row.get("entry", -1))) == 0:
            _same_number(row.get("volume"), LOT, "entry volume/lot")
    trades, cash = parse_deals(deal_rows)
    if not trades:
        raise ValueError("Native deal ledger contains no positions")
    for trade in trades:
        if len(trade["deals"]) != 2:
            raise ValueError("Partial exits unsupported for paired reason analysis")
        _same_number(trade["volume"], LOT, "entry volume/lot")
        opened, closed = trade["open_msc"], trade["close_msc"]
        if opened <= 0 or closed < opened:
            raise ValueError("Invalid native position timestamps")
        if finite(trade["entry_price"]) <= 0 or finite(trade["exit_price"]) <= 0 or finite(trade["volume"]) <= 0:
            raise ValueError("Native position price and volume must be positive")
        if trade["direction"] not in ("buy", "sell"):
            raise ValueError("Invalid native position direction")
        if not (START.replace(".", "-") <= trade["open"][:10] < end.replace(".", "-") and
                START.replace(".", "-") <= trade["close"][:10] < end.replace(".", "-")):
            raise ValueError("Native position timestamp outside accepted period")
    derived_stopouts = sum(t["exit_reason"] == 6 for t in trades)
    supplied_stopouts = accepted.get("result", {}).get("native_stopout")
    if supplied_stopouts is not None:
        if isinstance(supplied_stopouts, bool):
            if supplied_stopouts != bool(derived_stopouts):
                raise ValueError("Ledger stopout reasons do not reconcile to accepted native stopout flag")
        elif _count(supplied_stopouts, "native stopouts") != derived_stopouts:
            raise ValueError("Ledger stopout reasons do not reconcile to accepted native stopout count")
    deposit = finite(sig["deposit"])
    if len(cash) != 1 or cash[0]["type"] != 2 or abs(cash[0]["net"] - deposit) > .021:
        raise ValueError("Expected exactly one initial deposit and no other cash adjustment")

    result = accepted.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("native"), dict):
        raise ValueError("Accepted native result missing")
    native = result["native"]
    required_native = ("Symbol", "History Quality", "Period", "Initial Deposit", "Leverage",
                       "Total Trades", "Total Deals", "Total Net Profit", "Equity Drawdown Maximal")
    if any(key not in native for key in required_native):
        raise ValueError("Accepted native report lacks required reconciliation field")
    if native.get("Symbol") != "XAUUSD" or native.get("History Quality") != "100% real ticks":
        raise ValueError("Native report symbol/history quality mismatch")
    if native.get("Period") != f"M1 ({START} - {end})":
        raise ValueError("Native report period mismatch")
    if native.get("Initial Deposit") != "10 000.00":
        raise ValueError("Native report deposit mismatch")
    if native.get("Leverage") != "1:200":
        raise ValueError("Native report leverage mismatch")
    if report_metrics is not None:
        for key in ("Symbol", "Period", "History Quality", "Total Trades", "Total Deals", "Total Net Profit", "Initial Deposit", "Leverage", "Equity Drawdown Maximal"):
            if key not in report_metrics:
                raise ValueError(f"Native HTML report lacks required metric: {key}")
        if report_metrics["History Quality"] != "100% real ticks":
            raise ValueError("Native HTML report is not 100% real ticks")
        if _count(report_metrics["Total Trades"], "HTML native trades") != _count(native["Total Trades"], "accepted native trades"):
            raise ValueError("Accepted and HTML native trade counts differ")
        if abs(finite(report_metrics["Total Net Profit"]) - finite(native["Total Net Profit"])) > .021:
            raise ValueError("Accepted and HTML native net differ")
        if report_metrics["Initial Deposit"] != native["Initial Deposit"] or \
                report_metrics["Leverage"] != native["Leverage"]:
            raise ValueError("Accepted and HTML native capital controls differ")
        for key in ("Symbol", "Period", "Equity Drawdown Maximal"):
            if report_metrics[key] != native[key]:
                raise ValueError(f"Accepted and HTML native {key} differ")
    derived = bucket(trades)
    if derived["trades"] != _count(result.get("trades"), "accepted trades"):
        raise ValueError("Ledger position count does not reconcile to accepted result")
    if derived["trades"] != _count(native.get("Total Trades"), "native trades"):
        raise ValueError("Ledger position count does not reconcile to native report")
    trading_deal_count = sum(int(finite(row["type"])) in (0, 1) for row in deal_rows)
    if trading_deal_count != _count(native.get("Total Deals"), "native deal count"):
        raise ValueError("Ledger deal count does not reconcile to native report")
    if report_metrics is not None and _count(report_metrics["Total Deals"], "HTML native deals") != trading_deal_count:
        raise ValueError("Accepted ledger and HTML native deal counts differ")
    accepted_net = finite(result.get("net"))
    native_net = finite(native.get("Total Net Profit"))
    if abs(derived["net"] - accepted_net) > .021 or abs(derived["net"] - native_net) > .021:
        raise ValueError("Ledger net does not reconcile to accepted/native report")
    final_balance = finite(result.get("final_balance"))
    if abs(final_balance - deposit - sum(t["net"] for t in trades)) > .021:
        raise ValueError("Ledger net does not reconcile to final balance")
    dd_match = re.search(r"\(([-+\d.]+)%\)", native["Equity Drawdown Maximal"])
    if dd_match is None:
        raise ValueError("Accepted native equity drawdown percentage malformed")
    native_dd_pct = finite(dd_match.group(1))
    accepted_dd_pct = finite(result.get("native_equity_dd_pct"))
    if native_dd_pct < 0 or accepted_dd_pct < 0 or abs(native_dd_pct - accepted_dd_pct) > .011:
        raise ValueError("Accepted native equity drawdown does not reconcile to report")
    # Native deal exports identify the actual lot. Accepted signatures don't.
    if settings.get("InpLotSize") is None:
        raise ValueError("Native settings do not establish fixed lot")
    if settings.get("_set_sha") is not None and settings["_set_sha"] != sig["set_sha"]:
        raise ValueError("Accepted set_sha does not match physical native settings file")
    return sig, trades, derived


def _monthly(trades):
    months = {}
    for trade in trades:
        month = trade["close"][:7]
        months.setdefault(month, []).append(trade)
    out = {}
    for month in sorted(months):
        item = bucket(months[month])
        item["sign"] = "positive" if item["net"] > .005 else "negative" if item["net"] < -.005 else "zero"
        out[month] = item
    return out


def _trade_quality(trades):
    nets = [finite(t["net"]) for t in trades]
    wins = [x for x in nets if x > EPS]
    losses = [x for x in nets if x < -EPS]
    zeros = [x for x in nets if abs(x) <= EPS]
    avg_win = fmean(wins) if wins else None
    avg_loss = fmean(losses) if losses else None
    pf_num = sum(wins)
    pf_den = -sum(losses)
    return {
        "trades": len(nets), "wins": len(wins), "losses": len(losses), "zero": len(zeros),
        "net": round(sum(nets), 2), "net_per_trade": (sum(nets) / len(nets)) if nets else None,
        "net_profit_factor": (pf_num / pf_den) if pf_den else None,
        "pf_status": "finite" if pf_den else "no_losses" if pf_num else "no_trades_or_zero_only",
        "avg_net_win": avg_win, "avg_net_loss": avg_loss,
        "break_even_win_rate_pct": (100 * abs(avg_loss) / (avg_win + abs(avg_loss)))
            if avg_win is not None and avg_loss is not None and avg_win + abs(avg_loss) > 0 else None,
        "break_even_win_rate_basis": "average net win/loss among nonzero net positions; decisive basis",
        "actual_win_rate_pct": 100 * len(wins) / len(nets) if nets else None,
        "actual_win_rate_basis": "net wins divided by all positions; zero-PnL positions remain in denominator",
        "decisive_win_rate_pct": 100 * len(wins) / (len(wins) + len(losses))
            if wins or losses else None,
        "decisive_win_rate_basis": "net wins divided by nonzero net positions",
        "adjusted_break_even_win_rate_all_positions_pct":
            (100 * abs(avg_loss) / (avg_win + abs(avg_loss)) * (len(wins) + len(losses)) / len(nets))
            if nets and avg_win is not None and avg_loss is not None and avg_win + abs(avg_loss) > 0
            else None,
    }


def _pair(reference, treatment):
    ref = _unique_trade_map(reference, "reference")
    cur = _unique_trade_map(treatment, "treatment")
    common = sorted(ref.keys() & cur.keys())
    ref_only = ref.keys() - cur.keys()
    cur_only = cur.keys() - ref.keys()
    deltas = [cur[key]["net"] - ref[key]["net"] for key in common]
    transition = Counter((int(ref[key]["exit_reason"]), int(cur[key]["exit_reason"])) for key in common)
    exit_names = {3: "expert_close", 4: "stop_loss", 5: "take_profit", 6: "stop_out"}
    delta_sum = sum(deltas)
    transition_economics = {}
    for (a, b), count in sorted(transition.items()):
        keys = [key for key in common
                if int(ref[key]["exit_reason"]) == a and int(cur[key]["exit_reason"]) == b]
        ref_net = sum(ref[key]["net"] for key in keys)
        treatment_net = sum(cur[key]["net"] for key in keys)
        transition_economics[f"{exit_names.get(a, f'reason_{a}')}->{exit_names.get(b, f'reason_{b}')}"] = {
            "count": count, "reference_net": round(ref_net, 2),
            "treatment_net": round(treatment_net, 2),
            "net_delta": round(treatment_net - ref_net, 2),
        }
    return {
        "common": len(common), "reference_only": len(ref_only), "treatment_only": len(cur_only),
        "paired_net_delta_treatment_minus_reference": {
            "n": len(deltas), "net": round(delta_sum, 2),
            "mean": fmean(deltas) if deltas else None,
            "median": median(deltas) if deltas else None,
            "positive": sum(v > EPS for v in deltas),
            "negative": sum(v < -EPS for v in deltas),
            "zero": sum(abs(v) <= EPS for v in deltas),
        },
        "exit_transitions": {
            f"{exit_names.get(a, f'reason_{a}')}->{exit_names.get(b, f'reason_{b}')}": count
            for (a, b), count in sorted(transition.items())
        },
        "exit_transition_economics": transition_economics,
        "total_net_delta_including_unmatched": round(sum(t["net"] for t in treatment) -
                                                       sum(t["net"] for t in reference), 2),
    }


def analyze_records(records, descriptive10m):
    """Analyze four accepted actual native ledgers. Exported for unit tests."""
    if not isinstance(records, (list, tuple)) or len(records) != 4:
        raise ValueError("Exactly four TP configurations required")
    by_tp = {}
    signatures, settings_by_tp, trades_by_tp = {}, {}, {}
    for record in records:
        tp = finite(record.get("tp"))
        if tp not in TP_VALUES or tp in by_tp:
            raise ValueError("TP configurations must be the four unique frozen values")
        sig, trades, derived = _validate_run(record.get("accepted", {}), record.get("deal_rows", []),
                                              record.get("settings", {}), tp,
                                              record.get("report_metrics"))
        by_tp[tp] = {"metrics": _trade_quality(trades), "monthly": _monthly(trades),
                     "source_sha": sig["source_sha"], "native_net": derived["net"]}
        signatures[tp] = sig
        settings_by_tp[tp] = record["settings"]
        trades_by_tp[tp] = trades
    if set(by_tp) != set(TP_VALUES):
        raise ValueError("Incomplete frozen TP configuration set")
    source_shas = {s["source_sha"] for s in signatures.values()}
    if len(source_shas) != 1:
        raise ValueError("Source SHA differs across TP configurations")
    for key in ("binary_sha", "runtime", "tick_cache"):
        if len({json.dumps(s[key], sort_keys=True) for s in signatures.values()}) != 1:
            raise ValueError(f"Accepted {key} differs across TP configurations")
    reference_settings = settings_by_tp[TP_VALUES[0]]
    reference_without_tp = {k: v for k, v in reference_settings.items()
                            if k not in ("InpTakeProfitRRMul", "InpRunTag", "_set_sha")}
    for tp, settings in settings_by_tp.items():
        if {k: v for k, v in settings.items()
                if k not in ("InpTakeProfitRRMul", "InpRunTag", "_set_sha")} != reference_without_tp:
            raise ValueError(f"Native settings controls differ outside TP for TP={tp}")
    ten_sig = _validate_signature(descriptive10m, 1.0, end="2026.10.01")
    if ten_sig["runtime"] != signatures[1.0]["runtime"]:
        raise ValueError("Descriptive ten-month runtime differs from development runtime")
    dev_cache = {x["month"]: (x["bytes"], x["sha256"]) for x in signatures[1.0]["tick_cache"]}
    ten_cache = {x["month"]: (x["bytes"], x["sha256"]) for x in ten_sig["tick_cache"]}
    if any(ten_cache[month] != identity for month, identity in dev_cache.items()):
        raise ValueError("Descriptive ten-month shared tick cache differs from development")
    ten_month = _validate_descriptive10m(descriptive10m)
    if ten_month["source_sha256"] != next(iter(source_shas)):
        raise ValueError("Descriptive ten-month source SHA differs from development source")
    pairs = {str(tp): _pair(trades_by_tp[TP_VALUES[0]], trades_by_tp[tp])
             for tp in TP_VALUES[1:]}
    direct_pair = _pair(trades_by_tp[2.0], trades_by_tp[1.0])
    return {
        "scope": "accepted R4 development native runs; actual observed trades only",
        "source_sha256": next(iter(source_shas)), "lot": LOT,
        "reference_tp_r": TP_VALUES[0], "configs": {str(k): by_tp[k] for k in TP_VALUES},
        "paired_vs_tp_0.75": pairs,
        "paired_tp_2_to_1": direct_pair,
        "ten_month_context": ten_month,
        "qualification": "No qualified V25; this attribution is descriptive and not a promotion test.",
        "selection_cause": "Unknown from these artifacts. Results show actual outcome differences, not why a config ranked or appeared to win.",
        "counterfactual_limit": "Matched entries compare actual exits; unmatched trades remain included in total net delta. No unmatched outcome is imputed.",
    }


def _validate_descriptive10m(accepted):
    sig = _validate_signature(accepted, 1.0, end="2026.10.01")
    # This source's diagnostic ten-month signature is separate from the six-month development.
    if sig["start"] != "2025.12.01" or sig["end"] != "2026.10.01":
        raise ValueError("Descriptive ten-month signature period mismatch")
    result = accepted["result"]
    settings = accepted.get("_settings", {})
    metrics = accepted.get("_report_metrics")
    if not settings:
        raise ValueError("Descriptive ten-month native settings missing")
    _, trades, derived = _validate_run(accepted, accepted["deal_rows"], settings, 1.0,
                                       metrics, end="2026.10.01")
    native = result["native"]
    stress = {"0.2": round(derived["net"] - .2 * len(trades), 2),
              "0.5": round(derived["net"] - .5 * len(trades), 2)}
    supplied_stress = result.get("extra_cost_stress")
    if supplied_stress is not None:
        if not isinstance(supplied_stress, dict):
            raise ValueError("Accepted extra-cost stress malformed")
        for key, value in stress.items():
            if key not in supplied_stress or abs(finite(supplied_stress[key]) - value) > .011:
                raise ValueError("Accepted extra-cost stress does not reconcile to ledger")
    worst = min(trades, key=lambda t: t["net"])
    return {
        "source_sha256": sig["source_sha"],
        "period": native.get("Period"), "trades": len(trades), "net": derived["net"],
        "net_profit_factor": _trade_quality(trades)["net_profit_factor"],
        "pf_status": _trade_quality(trades)["pf_status"],
        "native_equity_dd_pct": finite(result["native_equity_dd_pct"]),
        "native_stopout": result.get("native_stopout"),
        "stopout_reason6_positions": sum(t["exit_reason"] == 6 for t in trades),
        "extra_cost_stress": stress,
        "extra_cost_stress_basis": "accounting sensitivity: subtract stated incremental cost per closed position from observed ledger net",
        "positive_months": sum(v["net"] > .005 for v in _monthly(trades).values()),
        "negative_months": sum(v["net"] < -.005 for v in _monthly(trades).values()),
        "zero_months": sum(abs(v["net"]) <= .005 for v in _monthly(trades).values()),
        "worst_trade": {k: worst[k] for k in ("position", "open", "close", "direction", "entry_price",
                                               "exit_price", "exit_reason", "profit", "commission", "swap",
                                               "fee", "net")},
        "worst_trade_charges_included_in_net": True,
        "genuinely_unseen_oos": False,
    }


def _read_run(tp, evidence_run):
    folder = REPORT / "runs" / evidence_run
    accepted_path = folder / "accepted.json"
    accepted = json.loads(accepted_path.read_text(encoding="utf-8-sig"))
    if accepted.get("result", {}).get("evidence_run") != evidence_run:
        raise ValueError(f"Accepted evidence_run does not match selected run: {evidence_run}")
    stem = evidence_run
    settings = _settings_from_run(folder, stem, tp)
    report_metrics, _ = report_rows(folder / f"{stem}.htm")
    return {"tp": tp, "accepted": accepted,
            "deal_rows": csv_rows(folder / f"{stem}_deals.csv"), "settings": settings,
            "report_metrics": report_metrics}


def load_evidence():
    complete = json.loads(COMPLETE.read_text(encoding="utf-8-sig"))
    found = {}
    for entry in complete.get("development", []):
        params = entry.get("parameters", {})
        if entry.get("mode") == 5 and params.get("InpEntryStrength") == 1 and \
                params.get("InpStopLossATRMul") == 1.5 and params.get("InpTakeProfitRRMul") in TP_VALUES:
            tp = params["InpTakeProfitRRMul"]
            if tp in found:
                raise ValueError(f"Duplicate matching development config in complete report: TP={tp}")
            evidence_run = entry.get("result", {}).get("evidence_run")
            if not evidence_run:
                raise ValueError("Matching config lacks accepted evidence_run key")
            found[tp] = evidence_run
    if set(found) != set(TP_VALUES):
        raise ValueError(f"Expected four unique matching configs, found TP values {sorted(found)}")
    records = [_read_run(tp, found[tp]) for tp in TP_VALUES]
    folder = REPORT / "runs" / "r4_a_descriptive10m"
    accepted = json.loads((folder / "accepted.json").read_text(encoding="utf-8-sig"))
    if accepted.get("result", {}).get("evidence_run") != "r4_a_descriptive10m":
        raise ValueError("Ten-month evidence_run mismatch")
    accepted = dict(accepted)
    accepted["deal_rows"] = csv_rows(folder / "r4_a_descriptive10m_deals.csv")
    accepted["_settings"] = _settings_from_run(folder, "r4_a_descriptive10m", 1.0)
    accepted["_report_metrics"], _ = report_rows(folder / "r4_a_descriptive10m.htm")
    return records, accepted


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    records, ten_month = load_evidence()
    print(json.dumps(analyze_records(records, ten_month), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
