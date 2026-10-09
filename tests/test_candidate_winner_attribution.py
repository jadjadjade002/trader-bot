import copy
import tempfile
import unittest
from pathlib import Path

from research.candidate_winner_attribution import analyze_records, _unique_trade_map


TPS = (0.75, 1.0, 1.5, 2.0)


def deal(ticket, position, time_msc, side_type, entry, reason, *, price=100.0,
         volume=0.01, profit=0.0, commission=0.0, swap=0.0, fee=0.0,
         magic=992300, symbol="XAUUSD"):
    return {"ticket": str(ticket), "position": str(position), "time_msc": str(time_msc),
            "type": str(side_type), "entry": str(entry), "reason": str(reason),
            "magic": str(magic), "symbol": symbol, "volume": str(volume), "price": str(price),
            "profit": str(profit), "commission": str(commission), "swap": str(swap),
            "fee": str(fee), "comment": ""}


def settings(tp):
    return {
        "InpEnableSessionGuard": "false", "InpEnableSpreadGuard": "false",
        "InpEnableMarginGuard": "true", "InpEnableHardSL": "true",
        "InpStartHour": "11", "InpEndHour": "16", "InpMaxSpreadPts": "25",
        "InpMaxHoldBars": "60", "InpDonchianPeriod": "20", "InpATRPeriod": "14",
        "InpStopLossATRMul": "1.5", "InpTakeProfitRRMul": str(tp),
        "InpMinSLPoints": "150", "InpLotSize": "0.01", "InpFadeBreakouts": "false",
        "InpMagicNumber": "992300", "InpTargetAccount": "0",
        "InpEnableCircuitBreaker": "true", "InpMaxConsecutiveLosses": "4",
        "InpCooldownMinutes": "90", "InpRunTag": f"tp{tp}",
        "InpExperimentMode": "5", "InpEntryStrength": "1",
    }


def signature(tp, *, end="2026.06.01"):
    months = [202512, 202601, 202602, 202603, 202604, 202605]
    if end == "2026.10.01":
        months += [202606, 202607, 202608, 202609]
    return {"start": "2025.12.01", "end": end, "mode": 5,
            "overrides": {"InpEntryStrength": 1, "InpStopLossATRMul": 1.5,
                           "InpTakeProfitRRMul": tp},
            "deposit": 10000, "delay_ms": 200, "optimize": False,
            "production": False,
            "source_sha": "AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320",
            "binary_sha": "1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9",
            "set_sha": "c" * 64,
            "runtime": {"terminal64.exe": "d" * 64, "metatester64.exe": "e" * 64},
            "tick_cache": [{"month": month, "bytes": 100 + index,
                            "sha256": f"{month:064x}"}
                           for index, month in enumerate(months)]}


def accepted(trades, net, tp, *, end="2026.06.01"):
    total = f"{net:.2f}"
    return {"signature": signature(tp, end=end),
            "result": {"evidence_run": "fixture", "trades": trades, "net": net,
                       "final_balance": 10000 + net,
                       "native_equity_dd_pct": 0.10,
                       "native": {"Symbol": "XAUUSD", "History Quality": "100% real ticks",
                                  "Period": f"M1 (2025.12.01 - {end})",
                                  "Initial Deposit": "10 000.00", "Leverage": "1:200",
                                  "Equity Drawdown Maximal": "10.00 (0.10%)",
                                  "Total Trades": str(trades), "Total Deals": str(2 * trades),
                                  "Total Net Profit": total}}}


def ledger(rows):
    return [deal(1, 0, 1, 2, 0, 0, volume=0, profit=10000, magic=0, symbol=""), *rows]


def position_rows(pid, opened, *, entry_price=100.0, volume=0.01, exit_reason=5,
                  profit=0.20, commission=-0.01, swap=-0.02, fee=-0.01):
    exit_type = 1 if exit_reason in (4, 5, 6) else 1
    return [deal(pid * 10, pid, opened, 0, 0, 3, price=entry_price, volume=volume),
            deal(pid * 10 + 1, pid, opened + 1000, exit_type, 1, exit_reason,
                 price=101.0 if exit_reason == 5 else 99.0, volume=volume,
                 profit=profit, commission=commission, swap=swap, fee=fee)]


def record(tp, rows, *, net=None):
    position_count = len(rows) // 2
    # Fixture runs use equal economics per position unless explicitly adjusted.
    actual_net = sum(float(r["profit"]) + float(r["commission"]) + float(r["swap"])
                     + float(r["fee"]) for r in rows)
    if net is not None:
        actual_net = net
    return {"tp": tp, "accepted": accepted(position_count, actual_net, tp),
            "deal_rows": ledger(rows), "settings": settings(tp)}


def fixture_records():
    # Two common entries, one reference-only, one treatment-only per TP.
    base = [*position_rows(10, 1764551000000, exit_reason=5, profit=0.20),
            *position_rows(11, 1764552000000, entry_price=102.0, exit_reason=4,
                           profit=-0.30),
            *position_rows(12, 1764553000000, entry_price=103.0, exit_reason=4,
                           profit=-0.20)]
    records = [record(0.75, base)]
    for tp, treatment_reason in zip(TPS[1:], (4, 5, 4)):
        rows = [*position_rows(10, 1764551000000, exit_reason=treatment_reason,
                               profit=0.10 if treatment_reason == 4 else 0.30,
                               swap=-0.04),
                *position_rows(11, 1764552000000, entry_price=102.0, exit_reason=5,
                               profit=0.25),
                *position_rows(13, 1764554000000, entry_price=104.0, exit_reason=5,
                               profit=0.30)]
        records.append(record(tp, rows))
    return records


def ten_month_record():
    rows = position_rows(99, 1780000000000, exit_reason=4, profit=-141.64,
                         commission=0.0, swap=-0.05, fee=0.0)
    result = accepted(1, -141.69, 1.0, end="2026.10.01")
    result["result"]["native"]["Period"] = "M1 (2025.12.01 - 2026.10.01)"
    result["result"]["native"]["Total Trades"] = "1"
    result["result"]["native"]["Total Deals"] = "2"
    result["result"]["native"]["Total Net Profit"] = "-141.69"
    result["result"]["native"]["Equity Drawdown Maximal"] = "141.69 (1.42%)"
    result["result"]["net"] = -141.69
    result["result"]["final_balance"] = 9858.31
    result["result"]["native_equity_dd_pct"] = 1.42
    result["deal_rows"] = ledger(rows)
    result["_settings"] = settings(1.0)
    return result


class CandidateWinnerAttributionTests(unittest.TestCase):
    def test_actual_pairing_reports_transitions_unmatched_and_all_trade_delta(self):
        result = analyze_records(fixture_records(), ten_month_record())
        pair = result["paired_vs_tp_0.75"]["1.0"]
        self.assertEqual((pair["common"], pair["reference_only"], pair["treatment_only"]), (2, 1, 1))
        self.assertEqual(pair["exit_transitions"], {"take_profit->stop_loss": 1,
                                                    "stop_loss->take_profit": 1})
        self.assertEqual(pair["paired_net_delta_treatment_minus_reference"]["n"], 2)
        self.assertEqual(pair["total_net_delta_including_unmatched"], 0.93)
        transition_delta = sum(v["net_delta"] for v in pair["exit_transition_economics"].values())
        self.assertAlmostEqual(transition_delta,
                               pair["paired_net_delta_treatment_minus_reference"]["net"], places=2)
        self.assertEqual(sum(v["count"] for v in pair["exit_transition_economics"].values()),
                         pair["common"])
        self.assertEqual(result["paired_tp_2_to_1"]["common"], 3)
        self.assertEqual(result["ten_month_context"]["worst_trade"]["swap"], -0.05)
        self.assertEqual(result["ten_month_context"]["worst_trade"]["net"], -141.69)
        direct = result["paired_tp_2_to_1"]
        self.assertEqual(direct["common"], 3)

    def test_charge_aware_win_loss_break_even_and_zero_categories(self):
        rows = [*position_rows(1, 1764551000000, profit=0.20, commission=-0.03,
                               swap=-0.02, fee=-0.01),
                *position_rows(2, 1764552000000, entry_price=102, exit_reason=4,
                               profit=-0.10, commission=0.0, swap=0.0, fee=0.0),
                *position_rows(3, 1764553000000, entry_price=103, exit_reason=4,
                               profit=0.0, commission=0.0, swap=0.0, fee=0.0)]
        one = record(0.75, rows)
        records = [one]
        for tp in TPS[1:]:
            records.append(record(tp, copy.deepcopy(rows)))
        # Give each fixture distinct run economics but preserve complete signatures.
        result = analyze_records(records, ten_month_record())
        m = result["configs"]["0.75"]["metrics"]
        self.assertEqual((m["wins"], m["losses"], m["zero"]), (1, 1, 1))
        self.assertAlmostEqual(m["net_per_trade"], 0.04 / 3)
        self.assertAlmostEqual(m["break_even_win_rate_pct"], 100 * .1 / (.14 + .1))
        self.assertAlmostEqual(m["actual_win_rate_pct"], 100 / 3)
        self.assertEqual(m["decisive_win_rate_pct"], 50.0)
        self.assertIn("zero-PnL", m["actual_win_rate_basis"])
        self.assertAlmostEqual(m["adjusted_break_even_win_rate_all_positions_pct"],
                               100 * .1 / (.14 + .1) * 2 / 3)

    def test_rejects_nonfinite_values(self):
        records = fixture_records()
        records[0]["deal_rows"][1]["profit"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            analyze_records(records, ten_month_record())

    def test_rejects_duplicate_exact_entry_keys(self):
        trade = {"open_msc": 123, "direction": "buy", "entry_price": 100.0,
                 "volume": 0.01, "net": 1.0}
        with self.assertRaisesRegex(ValueError, "Duplicate exact entry key"):
            _unique_trade_map([trade, dict(trade)], "fixture")

    def test_rejects_fractional_entry_milliseconds(self):
        trade = {"open_msc": 123.5, "direction": "buy", "entry_price": 100.0,
                 "volume": 0.01, "net": 1.0}
        with self.assertRaisesRegex(ValueError, "Invalid integer entry timestamp"):
            _unique_trade_map([trade], "fixture")

    def test_rejects_duplicate_or_missing_configuration(self):
        records = fixture_records()
        records[-1]["tp"] = 1.5
        with self.assertRaisesRegex(ValueError, "unique frozen"):
            analyze_records(records, ten_month_record())

    def test_rejects_incomplete_signature_override(self):
        records = fixture_records()
        del records[0]["accepted"]["signature"]["overrides"]["InpStopLossATRMul"]
        with self.assertRaisesRegex(ValueError, "override keys"):
            analyze_records(records, ten_month_record())

    def test_rejects_malformed_runtime_cache_and_ten_month_drift(self):
        records = fixture_records()
        records[0]["accepted"]["signature"]["runtime"]["terminal64.exe"] = "bad"
        with self.assertRaisesRegex(ValueError, "runtime SHA"):
            analyze_records(records, ten_month_record())
        records = fixture_records()
        ten_month = ten_month_record()
        ten_month["signature"]["tick_cache"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "shared tick cache"):
            analyze_records(records, ten_month)
        ten_month = ten_month_record()
        ten_month["signature"]["runtime"]["terminal64.exe"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "runtime differs"):
            analyze_records(fixture_records(), ten_month)
        records = fixture_records()
        records[0]["accepted"]["signature"]["set_sha"] = "bad"
        with self.assertRaisesRegex(ValueError, "set_sha malformed"):
            analyze_records(records, ten_month_record())

    def test_rejects_nonfinite_accepted_result(self):
        records = fixture_records()
        records[0]["accepted"]["result"]["net"] = float("inf")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            analyze_records(records, ten_month_record())

    def test_rejects_source_and_non_tp_settings_mismatch(self):
        records = fixture_records()
        records[2]["accepted"]["signature"]["source_sha"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "source SHA/binary SHA"):
            analyze_records(records, ten_month_record())
        records = fixture_records()
        records[2]["settings"]["InpMaxHoldBars"] = "61"
        with self.assertRaisesRegex(ValueError, "InpMaxHoldBars"):
            analyze_records(records, ten_month_record())

    def test_rejects_wrong_lot_or_native_reconciliation(self):
        records = fixture_records()
        records[0]["deal_rows"][1]["volume"] = "0.02"
        with self.assertRaisesRegex(ValueError, "volume/lot"):
            analyze_records(records, ten_month_record())
        records = fixture_records()
        records[0]["accepted"]["result"]["native_equity_dd_pct"] = 3.0
        with self.assertRaisesRegex(ValueError, "drawdown does not reconcile"):
            analyze_records(records, ten_month_record())
        records = fixture_records()
        records[0]["accepted"]["result"]["native"]["Total Net Profit"] = "999"
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            analyze_records(records, ten_month_record())

    def test_rejects_extra_cash_adjustment(self):
        records = fixture_records()
        records[0]["deal_rows"].append(deal(999, 0, 9999999999999, 2, 0, 0,
                                             volume=0, profit=1, magic=0, symbol=""))
        with self.assertRaisesRegex(ValueError, "initial deposit"):
            analyze_records(records, ten_month_record())

    def test_no_loss_pf_is_null_and_zero_trade_metric_is_undefined(self):
        from research.candidate_winner_attribution import _trade_quality
        self.assertIsNone(_trade_quality([{"net": 1.0}])["net_profit_factor"])
        empty = _trade_quality([])
        self.assertIsNone(empty["net_per_trade"])
        self.assertIsNone(empty["break_even_win_rate_pct"])
        self.assertEqual(empty["pf_status"], "no_trades_or_zero_only")

    def test_set_files_decode_utf16_and_utf8_strictly_and_pin_controls(self):
        from research.candidate_winner_attribution import _settings_from_run
        for encoding in ("utf-16", "utf-8-sig"):
            content = "\n".join(f"{k}={v}" for k, v in settings(.75).items()) + "\n"
            with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                folder = Path(temp)
                (folder / "fixture.set").write_bytes(content.encode(encoding))
                parsed = _settings_from_run(folder, "fixture", .75)
                self.assertEqual(parsed["InpDonchianPeriod"], "20")
                (folder / "fixture.set").write_bytes(b"\xff\xfeI\x00n\x00p\x00")
                with self.assertRaises((UnicodeError, ValueError)):
                    _settings_from_run(folder, "fixture", .75)

    def test_rejects_partial_exit_and_invalid_close_timestamp(self):
        records = fixture_records()
        records[0]["deal_rows"][2]["volume"] = "0.005"
        records[0]["deal_rows"].insert(2, deal(888, 10, 1764551000500, 1, 1, 5,
                                                price=101, volume=.005, profit=.1))
        with self.assertRaisesRegex(ValueError, "Partial exits unsupported"):
            analyze_records(records, ten_month_record())
        records = fixture_records()
        records[0]["deal_rows"][2]["time_msc"] = "1764550999999"
        with self.assertRaises(ValueError):
            analyze_records(records, ten_month_record())

    def test_rejects_nonfrozen_source_and_timestamp_identity(self):
        records = fixture_records()
        records[0]["accepted"]["signature"]["source_sha"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "source SHA"):
            analyze_records(records, ten_month_record())

    def test_rejects_fixture_settings_that_differ_from_frozen_controls(self):
        records = fixture_records()
        records[0]["settings"]["InpFadeBreakouts"] = "true"
        with self.assertRaisesRegex(ValueError, "InpFadeBreakouts"):
            analyze_records(records, ten_month_record())

    def test_rejects_missing_descriptive_ten_month_settings(self):
        ten_month = ten_month_record()
        del ten_month["_settings"]
        with self.assertRaisesRegex(ValueError, "native settings missing"):
            analyze_records(fixture_records(), ten_month)

    def test_descriptive_cost_stress_derives_and_reconciles(self):
        ten_month = ten_month_record()
        result = analyze_records(fixture_records(), ten_month)
        self.assertEqual(result["ten_month_context"]["extra_cost_stress"], {"0.2": -141.89, "0.5": -142.19})
        ten_month["result"]["extra_cost_stress"] = {"0.2": -100, "0.5": -101}
        with self.assertRaisesRegex(ValueError, "extra-cost stress does not reconcile"):
            analyze_records(fixture_records(), ten_month)


if __name__ == "__main__":
    unittest.main()
