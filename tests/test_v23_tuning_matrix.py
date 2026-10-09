import unittest
from research.v23_tuning_matrix import grid, metrics, rank


class TuningMatrixTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(net=40, gross_net_wins=140, gross_net_losses=100, native_net=40,
                   positions=120, wins=60, equity_dd=20, equity_dd_pct=2)
        row.update(changes)
        return row

    def test_grid_bounded_unique_and_be_off_included(self):
        for mode in (0, 1, 2):
            rows = grid(mode)
            self.assertEqual(len(rows), 36)
            self.assertEqual(len({(r["sl_atr"], r["tp_r"], r["be_r"]) for r in rows}), 36)
            self.assertEqual(sum(r["be_r"] == 0 for r in rows), 12)

    def test_negative_and_underpowered_not_promoted(self):
        self.assertEqual(rank([self.row(net=-10, gross_net_wins=90, native_net=-10),
                              self.row(positions=20, wins=10)]), [])

    def test_no_loss_small_sample_is_not_infinite_pf_winner(self):
        self.assertIsNone(metrics(self.row(net=140, gross_net_losses=0, native_net=140))["pf"])
        self.assertEqual(rank([self.row(net=140, gross_net_losses=0, native_net=140)]), [])

    def test_accounting_and_nonfinite_rejected(self):
        for changes in ({"native_net": 50}, {"net": float("nan")}, {"positions": 20.5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                metrics(self.row(**changes))

    def test_drawdown_ranks_before_profit(self):
        low_dd = self.row()
        high_dd = self.row(net=100, gross_net_wins=200, native_net=100, equity_dd_pct=5)
        self.assertEqual(rank([high_dd, low_dd]), [low_dd, high_dd])
