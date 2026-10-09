import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.v25_forensics import metrics, simulate


class V25ForensicsTests(unittest.TestCase):
    def synthetic(self):
        rows = []
        for i in range(25):
            rows.append(dict(time_broker_epoch=1000 + 60 * i,
                             time=pd.Timestamp("2026-09-14 11:00") + pd.Timedelta(minutes=i),
                             continuous=True, flags="OK", open=100.0,
                             high=100.1, low=99.9, close=100.0,
                             open_bid=100.0, open_ask=100.1,
                             open_spread_points=10, bar_spread_points=10))
        df = pd.DataFrame(rows)
        df.loc[24, "low"] = 98.0  # An SL hit on the entry bar.
        return df

    def test_entry_bar_stop_is_not_skipped(self):
        df = self.synthetic()
        signal = np.zeros(len(df), dtype=np.int8)
        signal[23] = 1
        atr = np.ones(len(df))
        with patch("research.v25_forensics.v23_signals", return_value=(signal, atr)):
            trades = simulate(df, invert=False, max_entry_spread=25)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["reason"], "STOP_OR_COLLISION")
        self.assertEqual(trades[0]["entry_time"], trades[0]["exit_time"])
        self.assertLess(trades[0]["pnl"], 0)
        self.assertEqual(metrics(trades)["entry_bar_exits"], 1)

    def test_spread_guard_uses_unstressed_observation(self):
        df = self.synthetic()
        signal = np.zeros(len(df), dtype=np.int8)
        signal[23] = 1
        atr = np.ones(len(df))
        with patch("research.v25_forensics.v23_signals", return_value=(signal, atr)):
            base = simulate(df, invert=False, max_entry_spread=25)
            stress = simulate(df, invert=False, max_entry_spread=25, spread_stress=2)
        self.assertEqual(len(base), len(stress))
        self.assertEqual(len(base), 1)

    def test_v25_ea_has_mandatory_risk_and_no_profit_lock(self):
        code = (Path(__file__).parents[1] / "versions" / "QuantumTitan_v25_EvidenceFirst.mq5").read_text(encoding="utf-8")
        for token in ("InpEnableTrading=false", "InpMaxRiskPercent", "InpMaxDailyLossPercent",
                      "OrderCalcProfit", "OrderCalcMargin", "AnySymbolPosition", "V25 BLOCK"):
            self.assertIn(token, code)
        self.assertNotIn("PositionModify", code)
        self.assertNotIn("InpInvertSignals", code)

    def test_contract_probe_is_read_only(self):
        code = (Path(__file__).parents[1] / "versions" / "V25_ContractProbe.mq5").read_text(encoding="utf-8")
        for token in ("SYMBOL_TRADE_CONTRACT_SIZE", "SYMBOL_VOLUME_MIN", "SYMBOL_VOLUME_STEP",
                      "OrderCalcProfit", "OrderCalcMargin"):
            self.assertIn(token, code)
        for forbidden in ("OrderSend", "PositionModify", "trade.Buy", "trade.Sell", "FileOpen", "WebRequest"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
