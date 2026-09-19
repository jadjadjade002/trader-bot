import tempfile
import unittest
from pathlib import Path

from research.v16_live_log_report import summarize


SAMPLE = """\
RS\t0\t00:01:41.092\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t⚡ [M1 Velocity] SELL SCALP OPENED @ 4391.51000 | SL: 4394.11000 (-260 pts) | TP: 4389.71000 (+180 pts) | Lot: 0.01
DM\t0\t00:02:22.145\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[M1 Velocity] SELL BREAKEVEN LOCKED: Profit 129.0 pts -> SL set to 4391.36000
RP\t0\t00:03:57.618\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[Velocity Safety] Deal #10151961825 closed; cooldown started.
CD\t0\t01:15:38.012\tQuantumTitan_v16_Apex (XAUUSD,M5)\t   • Adaptive Profile          : [M5 FAST INTRADAY] | Magic Number: 991605 | HTF Trend: PERIOD_H1
RM\t0\t00:32:45.127\tQuantumTitan_v16_Apex (XAUUSD,M1)\t[QuantumTitan v16.00] DEAL CLOSED #10152170667 (Magic: 991601, M1 ULTRA SCALPER): Net PnL: +$1.50 (Profit: $1.50, Swap: $0.00, Comm: $0.00)
"""


class V16LiveLogReportTests(unittest.TestCase):
    def test_summarizes_v16_events_from_utf16_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20260910.log"
            path.write_text(SAMPLE, encoding="utf-16")
            result = summarize([path])

        self.assertEqual(result["velocity_opens"], 1)
        self.assertEqual(result["velocity_sell_opens"], 1)
        self.assertEqual(result["velocity_closes"], 1)
        self.assertEqual(result["velocity_breakeven_locks"], 1)
        self.assertEqual(result["latest_velocity_open"]["side"], "SELL")
        self.assertEqual(result["latest_apex_profile"]["tf"], "M5")
        self.assertEqual(result["apex_explicit_closed_pnl"], 1.5)


if __name__ == "__main__":
    unittest.main()
