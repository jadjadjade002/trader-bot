import unittest

from research.candidate_exhaustion_diagnostic import analyze_records


def deal(ticket, position, time_msc, side_type, entry, reason, *, volume=0.1,
         profit=0.0, commission=0.0, swap=0.0, fee=0.0, magic=992300, symbol="XAUUSD"):
    return {"ticket": str(ticket), "position": str(position), "time_msc": str(time_msc),
            "type": str(side_type), "entry": str(entry), "reason": str(reason),
            "magic": str(magic), "symbol": symbol, "volume": str(volume),
            "price": "100.0", "profit": str(profit), "commission": str(commission),
            "swap": str(swap), "fee": str(fee), "comment": ""}


def accepted(trades=1, net=0.14):
    return {"signature": {"start": "2025.12.01", "end": "2026.06.01", "mode": 5,
                           "overrides": {"InpEntryStrength": 0}, "deposit": 10000,
                           "optimize": False, "production": False, "delay_ms": 200},
            "result": {"trades": trades, "net": net, "native": {
                "Total Trades": str(trades), "Total Net Profit": str(net),
                "Gross Profit": "0.20", "Gross Loss": "0.00", "Profit Factor": "finite",
                "Period": "M1 (2025.12.01 - 2026.06.01)"}}}


def partial_trade_rows(*, swap=-0.03):
    return [
        deal(1, 0, 1, 2, 0, 0, volume=0, profit=10000, magic=0, symbol=""),
        deal(2, 2, 1000, 0, 0, 3, volume=.2, commission=-.01),
        deal(3, 2, 2000, 1, 1, 5, volume=.05, profit=.05, fee=-.01),
        deal(4, 2, 2500, 1, 1, 5, volume=.15, profit=.15, swap=swap, fee=-.01),
    ]


def path(position=2, *, risk=1.0, mfe=.5, mae=.25, opened=1):
    return {"position": str(position), "opened": str(opened), "entry": "100",
            "initial_risk": str(risk), "mfe_price_sampled": str(mfe),
            "mae_price_sampled": str(mae), "mfe_time_msc": "1500", "mae_time_msc": "1800"}


def run(deals=None, paths=None, accepted_result=None):
    deals = partial_trade_rows() if deals is None else deals
    paths = [path()] if paths is None else paths
    meta = accepted() if accepted_result is None else accepted_result
    return analyze_records(meta, deals, paths, 0)


class ExhaustionDiagnosticTests(unittest.TestCase):
    def test_valid_aggregation_includes_partial_exit_charges_and_sampled_paths(self):
        # Profit .20, charges -.06, net .14; two exit deals must make one position.
        result = run()
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["net_from_positions"], .14)
        self.assertEqual(result["deal_profit_positive_before_charges"], .2)
        self.assertEqual(result["commission"], -.01)
        self.assertEqual(result["swap"], -.03)
        self.assertEqual(result["fee"], -.02)
        self.assertEqual(result["side_exit"]["buy/reason_5"]["count"], 1)
        self.assertEqual(result["sampled_mfe_r"]["median"], .5)


    def test_gross_profitable_position_can_be_net_loser_and_pf_uses_net(self):
        deals = [
            deal(1, 0, 1, 2, 0, 0, volume=0, profit=10000, magic=0, symbol=""),
            deal(2, 2, 1000, 0, 0, 3, commission=-.30),
            deal(3, 2, 2000, 1, 1, 5, profit=.20),
        ]
        result = run(deals=deals, accepted_result=accepted(net=-.1))
        cell = result["side_exit"]["buy/reason_5"]
        self.assertEqual(result["deal_profit_positive_before_charges"], .2)
        self.assertEqual(result["net_from_positions"], -.1)
        self.assertEqual((cell["wins"], cell["losses"]), (0, 1))
        self.assertEqual((cell["net_wins"], cell["net_losses"]), (0, -.1))
        self.assertEqual(cell["pf"], 0)


    def test_nonfinite_deal_number_rejected(self):
        deals = partial_trade_rows()
        deals[-1]["profit"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            run(deals=deals, accepted_result=accepted(net=.0))


    def test_missing_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "Path coverage mismatch"):
            run(paths=[])


    def test_duplicate_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate path"):
            run(paths=[path(), path()])


    def test_nonpositive_path_risk_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid path"):
            run(paths=[path(risk=0)])


    def test_foreign_trading_deal_rejected_by_audited_parser(self):
        deals = partial_trade_rows()
        deals[1]["magic"] = "123"
        with self.assertRaisesRegex(ValueError, "Foreign trading deal"):
            run(deals=deals)


    def test_accepted_count_or_native_net_mismatch_rejected(self):
        bad = accepted()
        bad["result"]["trades"] = 2
        with self.assertRaisesRegex(ValueError, "trade count"):
            run(accepted_result=bad)
        bad = accepted()
        bad["result"]["native"]["Total Net Profit"] = ".20"
        with self.assertRaisesRegex(ValueError, "net does not reconcile"):
            run(accepted_result=bad)


    def test_reversed_timestamps_rejected(self):
        deals = partial_trade_rows()
        deals[-1]["time_msc"] = "500"
        with self.assertRaisesRegex(ValueError, "Exit without matching position"):
            run(deals=deals, accepted_result=accepted(net=.14))

    def test_fractional_reported_trade_count_rejected(self):
        bad = accepted()
        bad["result"]["trades"] = 1.5
        with self.assertRaisesRegex(ValueError, "integer count"):
            run(accepted_result=bad)

    def test_nonfinite_path_data_rejected(self):
        bad_path = path()
        bad_path["mfe_price_sampled"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            run(paths=[bad_path])

    def test_preentry_sample_count_and_lag_reported(self):
        deals = partial_trade_rows()
        deals[1]["time_msc"] = "1710"
        result = run(deals=deals, accepted_result=accepted(net=.14))
        self.assertEqual(result["sample_events_before_entry_deal"]["mfe"],
                         {"count": 1, "earliest_lag_ms": 210})
        self.assertEqual(result["sample_events_before_entry_deal"]["mae"],
                         {"count": 0, "earliest_lag_ms": None})

    def test_sample_before_path_open_second_floor_rejected(self):
        deals = partial_trade_rows()
        deals[1]["time_msc"] = "2000"
        bad_path = path(opened=2)
        bad_path["mfe_time_msc"] = "1500"
        with self.assertRaisesRegex(ValueError, "timestamp outside position"):
            run(deals=deals, paths=[bad_path], accepted_result=accepted(net=.14))


if __name__ == "__main__":
    unittest.main()
