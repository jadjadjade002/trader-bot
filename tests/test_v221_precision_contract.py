"""Static safety contract for the V22.1 Precision candidate."""

import re
import unittest
from pathlib import Path


class TestV221PrecisionContract(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent.parent
        self.source_file = root / "QuantumTitan_v22_1_Precision.mq5"
        self.assertTrue(self.source_file.exists(), "V22.1 candidate source missing")
        self.source = self.source_file.read_text(encoding="utf-8", errors="replace")

    def body(self, name):
        match = re.search(
            r"\b(?:bool|void|double|int|string|ulong)\s+" + re.escape(name)
            + r"\s*\([^)]*\)\s*\{",
            self.source,
        )
        self.assertIsNotNone(match, f"Missing function: {name}")
        depth = 1
        for index in range(match.end(), len(self.source)):
            if self.source[index] == "{":
                depth += 1
            elif self.source[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.source[match.end():index]
        self.fail(f"Unclosed function: {name}")

    def test_account_wide_xau_mutex_sees_all_magics_and_pending_orders(self):
        mutex = self.body("HasAccountWideXauExposure")
        self.assertIn("PositionsTotal()", mutex)
        self.assertIn("OrdersTotal()", mutex)
        self.assertIn("PositionGetString(POSITION_SYMBOL)", mutex)
        self.assertIn("OrderGetString(ORDER_SYMBOL)", mutex)
        self.assertNotIn("POSITION_MAGIC", mutex)
        self.assertNotIn("ORDER_MAGIC", mutex)
        tick = self.body("OnTick")
        self.assertIn("HasAccountWideXauExposure()", tick)
        self.assertIn("AcquireEntryMutex()", tick)
        self.assertIn("ReleaseEntryMutex()", tick)

    def test_minimum_lot_cash_risk_cap_precedes_both_order_calls(self):
        self.assertRegex(self.source, r"InpMaxRiskMoney\s*=\s*(?:1(?:\.\d+)?|2(?:\.0+)?)\s*;")
        risk = self.body("IsRiskMoneyAllowed")
        self.assertIn("OrderCalcProfit", risk)
        self.assertIn("MathAbs(projected)", risk)
        self.assertIn("InpMaxRiskMoney", risk)
        tick = self.body("OnTick")
        risk_at = [m.start() for m in re.finditer(r"IsRiskMoneyAllowed\s*\(", tick)]
        self.assertGreaterEqual(len(risk_at), 2)
        self.assertLess(risk_at[0], tick.find("g_trade.Buy"))
        self.assertLess(risk_at[-1], tick.find("g_trade.Sell"))

    def test_directional_di_is_rejection_gate_not_score_bonus(self):
        conviction = self.body("EvaluateConviction")
        self.assertIn("CopyBuffer(g_handleAdx, 1", conviction)
        self.assertIn("CopyBuffer(g_handleAdx, 2", conviction)
        self.assertRegex(conviction, r"ORDER_TYPE_BUY\s*&&\s*adxPlusDI\[1\]\s*>\s*adxMinusDI\[1\]")
        self.assertRegex(conviction, r"ORDER_TYPE_SELL\s*&&\s*adxMinusDI\[1\]\s*>\s*adxPlusDI\[1\]")
        self.assertRegex(conviction, r"REJECT_DIRECTIONAL_ADX[^}]*return\s+0")

    def test_pullback_rejection_and_chase_cap_are_mandatory(self):
        conviction = self.body("EvaluateConviction")
        self.assertIn("REJECT_STRICT_PULLBACK", conviction)
        self.assertRegex(conviction, r"(?:rates\[1\]\.low|rates\[1\]\.high)[^;]*zone")
        self.assertRegex(conviction, re.compile(r"Wick", re.IGNORECASE))
        self.assertNotIn("TrendContinuation", conviction)
        self.assertNotIn("BearishBar+12", conviction)
        self.assertNotIn("BullishBar+12", conviction)
        self.assertIn("InpMaxChaseAtr", self.source)
        self.assertRegex(conviction, r"chaseDistance\s*>\s*atrBuf\[0\]\s*\*\s*InpMaxChaseAtr")
        self.assertRegex(conviction, r"REJECT_CHASE_DISTANCE[^}]*return\s+0")

    def test_stop_distance_cap_is_rejection_gate(self):
        self.assertRegex(self.source, r"InpMaxStopPoints\s*=\s*[1-9]\d{1,2}(?:\.0+)?\s*;")
        tick = self.body("OnTick")
        self.assertRegex(tick, r"buySlPoints\s*>\s*InpMaxStopPoints[^}]*return\s*;")
        self.assertRegex(tick, r"sellSlPoints\s*>\s*InpMaxStopPoints[^}]*return\s*;")

    def test_setup_fingerprint_is_terminal_shared_and_checked_before_orders(self):
        key = self.body("BuildSetupKey")
        # M5 and M15 use different structure TFs (M30/H1).  Including that
        # bar would let both charts consume the same H4 macro setup after the
        # first position closes.  The key therefore needs a shared macro bar.
        self.assertIn("PERIOD_H4", key)
        self.assertIn("orderType", key)
        self.assertIn("macroBar", key)
        self.assertNotIn("structureBar", key)
        tick = self.body("OnTick")
        self.assertIn("BuildSetupKey", tick)
        seen = self.body("WasSetupConsumed")
        mark = self.body("MarkSetupConsumed")
        self.assertIn("GlobalVariableCheck", seen)
        self.assertIn("GlobalVariableSet", mark)
        self.assertIn("WasSetupConsumed(setupKey)", tick)
        self.assertEqual(tick.count("MarkSetupConsumed(setupKey)"), 2)

    def test_shared_daily_cash_loss_cap_includes_all_eas_and_precedes_orders(self):
        self.assertRegex(self.source, r"InpMaxDailyLossMoney\s*=\s*[34](?:\.\d+)?\s*;")
        cap = self.body("IsDailyLossBreakerTripped")
        history = self.body("ComputeDayStartingEquity")
        self.assertIn("ComputeDayStartingEquity", cap)
        self.assertIn("HistorySelect", history)
        self.assertIn("HistoryDealGetDouble", history)
        self.assertIn("DEAL_PROFIT", history)
        self.assertIn("DEAL_COMMISSION", history)
        self.assertIn("DEAL_SWAP", history)
        self.assertNotIn("DEAL_MAGIC", history)
        self.assertIn("InpMaxDailyLossMoney", cap)
        tick = self.body("OnTick")
        cap_at = tick.find("IsDailyLossBreakerTripped")
        self.assertGreaterEqual(cap_at, 0)
        self.assertLess(cap_at, tick.find("g_trade.Buy"))
        self.assertLess(cap_at, tick.find("g_trade.Sell"))


if __name__ == "__main__":
    unittest.main()
