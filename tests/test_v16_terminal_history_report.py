import tempfile
import unittest
from pathlib import Path

from research.v16_terminal_history_report import parse_paths


ACCOUNT = "112334471"


def line(message: str) -> str:
    return f"AA\t0\t12:00:00.000\tTrades\t'{ACCOUNT}': {message}"


class TerminalHistoryReportTests(unittest.TestCase):
    def parse(self, lines: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "20260913.log"
            path.write_text("\n".join(lines), encoding="utf-16")
            return parse_paths([path])

    def test_reconstructs_tp_and_ignores_other_account(self):
        report = self.parse([
            line("market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("accepted market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("deal #1 buy 0.01 XAUUSD at 100.00 done (based on order #10)"),
            line("deal #2 sell 0.01 XAUUSD at 101.00 done (based on order #11)"),
            "AA\t0\t12:00:00.000\tTrades\t'999': deal #3 buy 1 XAUUSD at 1 done (based on order #1)",
        ])
        position = report["positions"][0]
        self.assertEqual(position["exit_kind"], "TP")
        self.assertEqual(position["price_pnl"], 0.01)
        self.assertEqual(report["summary"]["unmatched_records"], 0)

    def test_classifies_be_lock_and_trailing_from_accepted_sl(self):
        report = self.parse([
            line("market sell 0.01 XAUUSD sl: 103.00 tp: 97.00"),
            line("deal #1 sell 0.01 XAUUSD at 100.00 done (based on order #10)"),
            line("accepted modify #10 sell 0.01 XAUUSD sl: 103.00, tp: 97.00 -> sl: 99.90, tp: 97.00"),
            line("deal #2 buy 0.01 XAUUSD at 99.90 done (based on order #12)"),
            line("market buy 0.01 XAUUSD sl: 197.00 tp: 203.00"),
            line("deal #3 buy 0.01 XAUUSD at 200.00 done (based on order #20)"),
            line("accepted modify #20 buy 0.01 XAUUSD sl: 197.00, tp: 203.00 -> sl: 201.00, tp: 203.00"),
            line("deal #4 sell 0.01 XAUUSD at 201.00 done (based on order #21)"),
        ])
        self.assertEqual([p["exit_kind"] for p in report["positions"]], ["BE_LOCK", "TRAILING"])

    def test_close_command_beats_price_inference(self):
        report = self.parse([
            line("market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("deal #1 buy 0.01 XAUUSD at 100.00 done (based on order #10)"),
            line("market sell 0.01 XAUUSD, close #10 buy 0.01 XAUUSD 100.00"),
            line("deal #2 sell 0.01 XAUUSD at 101.00 done (based on order #11)"),
        ])
        self.assertEqual(report["positions"][0]["exit_kind"], "MANUAL")

    def test_explicit_close_ticket_beats_multiple_grid_candidates(self):
        report = self.parse([
            line("market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("accepted market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("deal #1 buy 0.01 XAUUSD at 100.00 done (based on order #10)"),
            line("market buy 0.01 XAUUSD sl: 199.00 tp: 201.00"),
            line("deal #2 buy 0.01 XAUUSD at 200.00 done (based on order #20)"),
            line("market sell 0.01 XAUUSD, close #20 buy 0.01 XAUUSD 200.00"),
            line("accepted market sell 0.01 XAUUSD, close #20 buy 0.01 XAUUSD 200.00"),
            line("deal #3 sell 0.01 XAUUSD at 200.50 done (based on order #30)"),
        ])
        first, second = report["positions"]
        self.assertIsNone(first["exit_deal"])
        self.assertEqual(second["exit_deal"], 3)
        self.assertEqual(second["exit_kind"], "MANUAL")
        self.assertEqual(report["summary"]["unmatched_records"], 0)

    def test_accepted_market_response_is_not_a_second_entry_request(self):
        report = self.parse([
            line("market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("accepted market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("deal #1 buy 0.01 XAUUSD at 100.00 done (based on order #10)"),
        ])
        self.assertEqual(report["summary"]["opened"], 1)
        self.assertEqual(report["summary"]["unmatched_records"], 0)

    def test_fails_closed_for_ambiguous_exit(self):
        report = self.parse([
            line("market buy 0.01 XAUUSD sl: 99.00 tp: 101.00"),
            line("deal #1 buy 0.01 XAUUSD at 100.00 done (based on order #10)"),
            line("market buy 0.01 XAUUSD sl: 199.00 tp: 201.00"),
            line("deal #2 buy 0.01 XAUUSD at 200.00 done (based on order #20)"),
            line("deal #3 sell 0.01 XAUUSD at 150.00 done (based on order #30)"),
        ])
        self.assertEqual(report["summary"]["closed"], 0)
        self.assertEqual(report["unmatched_records"][0]["kind"], "deal_unmatched_or_ambiguous")


if __name__ == "__main__":
    unittest.main()
