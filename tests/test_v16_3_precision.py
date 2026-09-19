"""Structural regression checks only; do not substitute for MT5 execution/backtests."""
import re
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "QuantumTitan_v16_3_Precision.mq5").read_text(encoding="utf-8")


class PrecisionStructure(unittest.TestCase):
    def test_candidate_defaults(self):
        defaults = {"InpMagicNumber": 991613, "InpBaseLot": .01,
                    "InpTakeProfitPoints": 220, "InpStopLossPoints": 220,
                    "InpBreakevenTriggerPts": 130, "InpBreakevenLockPts": 20,
                    "InpMaxSpreadPoints": 35, "InpCooldownBars": 2}
        for name, expected in defaults.items():
            self.assertEqual(float(re.search(rf"input \w+ {name}=([\d.]+);", SOURCE)[1]), expected)

    def test_m1_demo_guard(self):
        self.assertIn("if(_Period!=PERIOD_M1) return INIT_PARAMETERS_INCORRECT;", SOURCE)
        self.assertIn("!=ACCOUNT_TRADE_MODE_DEMO", SOURCE)

    def test_account_symbol_allowlist(self):
        self.assertIn("input ulong InpAllowedAccount=112468807;", SOURCE)
        self.assertNotIn("112334471", SOURCE)
        self.assertIn("!MQLInfoInteger(MQL_TESTER)", SOURCE)
        self.assertIn("InpAllowedAccount==0 || (ulong)AccountInfoInteger(ACCOUNT_LOGIN)!=InpAllowedAccount", SOURCE)
        self.assertIn('input string InpSymbolPrefix="XAUUSD";', SOURCE)
        self.assertIn("StringLen(InpSymbolPrefix)==0 || StringFind(_Symbol,InpSymbolPrefix)!=0", SOURCE)

    def test_closed_bar_buffers_and_rates(self):
        calls = re.findall(r"CopyBuffer\(([^;]+)\)", SOURCE)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("handle,buffer,1,count,out"))
        calls = re.findall(r"CopyRates\(([^;]+)\)", SOURCE)
        self.assertTrue(all(c.startswith("_Symbol,PERIOD_M1,1,") for c in calls))
        self.assertIn("ArraySetAsSeries(out,true)", SOURCE)
        self.assertIn("out[i]==EMPTY_VALUE", SOURCE)

    def test_fail_closed(self):
        self.assertIn("ZeroMemory(state)", SOURCE)
        self.assertIn("!CalculateSqueezeMomentum(sqz)) return;", SOURCE)
        self.assertIn("CopyBuffer(handle,buffer,1,count,out)!=count) return false;", SOURCE)

    def test_slopes_same_units_different_windows(self):
        self.assertIn("state.momentum=LinRegSlope(delta,length,0)", SOURCE)
        self.assertIn("state.prevMomentum=LinRegSlope(delta,length,1)", SOURCE)
        self.assertIn("src[offset+length-1-i]", SOURCE)
        self.assertIn("basis[k]", SOURCE)
        self.assertIn("int needed=length+InpKCLength", SOURCE)
        self.assertNotIn("prevMomentum=delta", SOURCE)

    def test_broker_execution_checks(self):
        for text in ("SYMBOL_TRADE_STOPS_LEVEL", "SYMBOL_TRADE_FREEZE_LEVEL",
                     "SYMBOL_TRADE_TICK_SIZE", "SYMBOL_VOLUME_STEP",
                     "SetTypeFillingBySymbol", "SetAsyncMode(false)"):
            self.assertIn(text, SOURCE)
        self.assertRegex(SOURCE, r"if\(sent && code==TRADE_RETCODE_DONE\)\s+PrintFormat\(\"\[Precision\] BE LOCKED")

    def test_ticket_snapshot_not_moving_sl(self):
        self.assertIn("g_entries[i].ticket==ticket", SOURCE)
        self.assertIn('HistoryOrderGetDouble(entryOrder,ORDER_SL)', SOURCE)
        self.assertIn('GlobalVariableCheck(StateKey(ticket,"ready"))', SOURCE)
        manage = SOURCE.split("void ManagePositions", 1)[1].split("bool SessionAllowed", 1)[0]
        self.assertIn("if(gain<s.beTrigger) continue;", manage)
        self.assertIn("PositionModify(ticket,sl,s.tp)", manage)
        self.assertNotIn("InpBreakeven", manage)

    def test_single_entry_lock_and_cooldown(self):
        self.assertIn("g_entryPending || ActiveForMagic()>0", SOURCE)
        self.assertIn("GlobalVariableSetOnCondition(g_lockKey,1.0,0.0)", SOURCE)
        self.assertIn("OrdersTotal()", SOURCE)
        self.assertIn("POSITION_MAGIC)==InpMagicNumber", SOURCE)
        self.assertIn("iBarShift(_Symbol,PERIOD_M1,lastExit,false)<InpCooldownBars", SOURCE)
        self.assertIn("ACCOUNT_MARGIN_MODE_RETAIL_HEDGING && PositionSelect(_Symbol)", SOURCE)
        self.assertEqual(SOURCE.count("g_trade.Buy("), 1)
        self.assertEqual(SOURCE.count("g_trade.Sell("), 1)

    def test_exit_cost_logging_and_manual_ownership(self):
        for prop in ("DEAL_PROFIT", "DEAL_COMMISSION", "DEAL_SWAP", "DEAL_FEE", "DEAL_ENTRY_OUT_BY"):
            self.assertIn(prop, SOURCE)
        self.assertIn("profit+commission+swap+fee", SOURCE)
        self.assertIn("HistorySelectByPosition(positionId)", SOURCE)

    def test_local_guards_no_shared_risk_guardian(self):
        self.assertNotIn("RiskGuardian", SOURCE)
        self.assertIn("lots+InpBaseLot>InpMaxAccountLots", SOURCE)
        self.assertIn("ACCOUNT_EQUITY)<InpHardEquityFloor", SOURCE)

    def test_persistence_isolation_cleanup(self):
        self.assertIn('"P163_%I64d_%I64u_",AccountInfoInteger(ACCOUNT_LOGIN),InpMagicNumber', SOURCE)
        self.assertIn('if(StringFind(key,prefix)!=0) continue;', SOURCE)
        self.assertIn('if(ticket>0 && !PositionSelectByTicket(ticket)) GlobalVariableDel(key);', SOURCE)
        self.assertIn('ArrayRemove(g_entries,i,1)', SOURCE)


if __name__ == "__main__":
    unittest.main()
