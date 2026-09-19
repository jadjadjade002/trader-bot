import tempfile
import unittest
from pathlib import Path
from research.v16_velocity_live_report import parse_expert_logs, parse_terminal_logs, build_report

def _log(path, lines):
    path.write_text("\n".join(lines), encoding="utf-16")

class VelocityReportTests(unittest.TestCase):
 def test_utf16_parse_pair_and_estimate(self):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); exd=root/'experts'; ted=root/'terminal'; exd.mkdir(); ted.mkdir(); ex=exd/'20260913.log'; te=ted/'20260913.log'
        _log(ex,["AA\t0\t01:00:00.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t⚡ [M1 Velocity] BUY SCALP OPENED @ 4400.00000 | SL: 4397.40000 (-260 pts) | TP: 4401.80000 (+180 pts) | Lot: 0.01", "AA\t0\t01:00:01.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[M1 Velocity] BUY BREAKEVEN LOCKED: Profit 90.0 pts -> SL set to 4400.15000", "AA\t0\t01:00:02.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[Velocity Safety] Deal #2 closed; cooldown started."])
        _log(te,["AA\t0\t01:00:00.000\tTrades\t'112334471': deal #1 buy 0.01 XAUUSD at 4400.00 done (based on order #9)", "AA\t0\t01:00:02.000\tTrades\t'112334471': deal #2 sell 0.01 XAUUSD at 4401.80 done (based on order #10)"])
        self.assertEqual(len(parse_expert_logs([ex])),3)
        self.assertEqual(len(parse_terminal_logs([te])),2)
        r=build_report([ex],[te],tolerance=.01)
        self.assertEqual(r['metrics']['matched'],1)
        self.assertEqual(r['positions'][0]['class'],'TP')
        self.assertAlmostEqual(r['positions'][0]['price_pnl_estimate'],1.8)

 def test_account_filter_and_unknown_close(self):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); exd=root/'experts'; ted=root/'terminal'; exd.mkdir(); ted.mkdir(); ex=exd/'20260913.log'; te=ted/'20260913.log'
        _log(ex,["AA\t0\t01:00:00.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[M1 Velocity] SELL SCALP OPENED @ 4400 | SL: 4402.6 | TP: 4398.2 | Lot: 0.01", "AA\t0\t01:00:01.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[Velocity Safety] Deal #9 closed"])
        _log(te,["AA\t0\t01:00:00.000\tTrades\t'112334471': deal #8 sell 0.01 XAUUSD at 4400 done (based on order #1)", "AA\t0\t01:00:01.000\tTrades\t'112334471': deal #9 buy 0.01 XAUUSD at 4400 done (based on order #2)", "AA\t0\t01:00:03.000\tTrades\t'1': deal #10 buy 0.01 XAUUSD at 4400 done (based on order #3)"])
        r=build_report([ex],[te]); self.assertEqual(r['metrics']['matched'],1); self.assertEqual(r['positions'][0]['class'],'FLAT')

 def test_new_open_supersedes_active(self):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); exd=root/'experts'; ted=root/'terminal'; exd.mkdir(); ted.mkdir(); ex=exd/'20260913.log'; te=ted/'20260913.log'
        _log(ex,["AA\t0\t01:00:00.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[M1 Velocity] BUY SCALP OPENED @ 4400 | SL: 4397.4 | TP: 4401.8 | Lot: 0.01", "AA\t0\t01:00:01.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[M1 Velocity] BUY SCALP OPENED @ 4402 | SL: 4399.4 | TP: 4403.8 | Lot: 0.01", "AA\t0\t01:00:02.000\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[Velocity Safety] Deal #2 closed"])
        _log(te,["AA\t0\t01:00:00.000\tTrades\t'112334471': deal #1 buy 0.01 XAUUSD at 4400 done (based on order #1)", "AA\t0\t01:00:01.000\tTrades\t'112334471': deal #2 buy 0.01 XAUUSD at 4402 done (based on order #2)", "AA\t0\t01:00:02.000\tTrades\t'112334471': deal #3 sell 0.01 XAUUSD at 4403.8 done (based on order #3)"])
        r=build_report([ex],[te]); self.assertEqual(r['metrics']['matched'],1); self.assertEqual(r['positions'][0]['entry_deal'],'2'); self.assertEqual(r['metrics']['unmatched']['superseded_open_without_close'],1)

if __name__ == '__main__': unittest.main()
