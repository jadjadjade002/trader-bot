"""Unit tests for V16 Diagnostic Report."""

import tempfile
import unittest
from pathlib import Path

from research.v16_diagnostic_report import parse_v16_log, read_log_text


SAMPLE_V16_LOG = """CS	0	00:00:03.301	QuantumTitan_v16_Velocity (XAUUSD,M1)	[M1 Velocity] SELL BREAKEVEN LOCKED: Profit 93.0 pts -> SL set to 4394.04000
RN	0	00:00:39.885	QuantumTitan_v16_Velocity (XAUUSD,M1)	[Velocity Safety] Deal #10151930251 closed; cooldown started.
FE	0	01:01:04.353	QuantumTitan_v16_Velocity (XAUUSD,M1)	⚡ [M1 Velocity] BUY SCALP OPENED @ 4408.09000 | SL: 4405.49000 (-260 pts) | TP: 4409.89000 (+180 pts) | Lot: 0.01
RM	0	00:32:45.127	QuantumTitan_v16_Apex (XAUUSD,M1)	[QuantumTitan v16.00] DEAL CLOSED #10152170667 (Magic: 991601, M1 ULTRA SCALPER): Net PnL: +$1.50 (Profit: $1.50, Swap: $0.00, Comm: $0.00)
HG	0	01:25:42.511	QuantumTitan_v16_Apex (XAUUSD,M1)	[QuantumTitan v16.00] DEAL CLOSED #10152718496 (Magic: 991601, M1 ULTRA SCALPER): Net PnL: $-4.16 (Profit: $-4.16, Swap: $0.00, Comm: $0.00)
QP	0	01:27:00.827	QuantumTitan_v16_Apex (XAUUSD,M1)	[TrailingSafety] Ticket #10432309725: Hard Breakeven LOCKED at 4415.71000 (+0.3R)
KM	0	01:27:01.274	QuantumTitan_v16_Apex (XAUUSD,M1)	[TrailingSafety] Ticket #10432309725: Hard TTP Trail SL lowered to 4415.45000 (Peak: 4414.19000)
"""


class TestV16DiagnosticReport(unittest.TestCase):
    def test_v16_utf16_reading(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            f.write(SAMPLE_V16_LOG.encode("utf-16"))
            temp_path = Path(f.name)

        try:
            read_back = read_log_text(temp_path)
            self.assertIn("SELL BREAKEVEN LOCKED", read_back)
            self.assertIn("⚡", read_back)
        finally:
            temp_path.unlink()

    def test_v16_parsing_and_explicit_pnl(self):
        rep = parse_v16_log(SAMPLE_V16_LOG)

        self.assertIn("QuantumTitan_v16_Velocity", rep["eas"])
        self.assertIn("QuantumTitan_v16_Apex", rep["eas"])

        vel = rep["eas"]["QuantumTitan_v16_Velocity"]
        apex = rep["eas"]["QuantumTitan_v16_Apex"]

        # Velocity checks
        self.assertEqual(vel["open_count"], 1)
        self.assertEqual(vel["close_count"], 1)
        self.assertEqual(vel["breakeven_count"], 1)
        # Velocity deal notice has NO explicit PnL in text -> must be 0 explicit PnL deals and None sum
        self.assertEqual(vel["explicit_pnl_deals_count"], 0)
        self.assertIsNone(vel["explicit_pnl_sum"])

        # Apex checks
        self.assertEqual(apex["close_count"], 2)
        self.assertEqual(apex["explicit_pnl_deals_count"], 2)
        # Net PnL: +1.50 and -4.16 -> sum = -2.66
        self.assertAlmostEqual(apex["explicit_pnl_sum"], -2.66, places=2)

        # Overall
        self.assertTrue(rep["overall_summary"]["explicit_log_pnl_only"])
        self.assertEqual(rep["overall_summary"]["account_pnl_provenance"], "unknown_requires_broker_history_statement")

    def test_no_explicit_pnl_returns_null(self):
        log = "CS\t0\t00:00:03.301\tQuantumTitan_v16_Velocity (XAUUSD,M1)\t[Velocity Safety] Deal #100 closed; cooldown started.\n"
        rep = parse_v16_log(log)
        vel = rep["eas"]["QuantumTitan_v16_Velocity"]
        self.assertEqual(vel["explicit_pnl_deals_count"], 0)
        self.assertIsNone(vel["explicit_pnl_sum"])
        self.assertTrue(vel["explicit_log_pnl_only"])
        self.assertIsNone(rep["overall_summary"]["total_explicit_pnl"])


if __name__ == "__main__":
    unittest.main()
