import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "QuantumTitan_V16_TickPathCollector.mq5"


class TickPathCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        match = re.search(r'BAR_HEADER="([^"]+)";', cls.text)
        cls.header = next(csv.reader([match.group(1)])) if match else []

    def test_source_exists_and_compiler_clean_log(self):
        self.assertTrue(SOURCE.is_file())
        log = (ROOT / "v16_tick_compile.log").read_text(encoding="utf-16")
        self.assertIn("Result: 0 errors, 0 warnings", log)

    def test_no_trading_or_account_surface(self):
        forbidden = [
            r"\b(?:OrderSend|OrderCheck|OrderGet\w*|PositionGet\w*|PositionSelect\w*|HistoryDeal\w*|HistoryOrder\w*)\s*\(",
            r"\b(?:CTrade|MqlTrade\w*|OnTrade\w*|WebRequest)\b",
            r"#\s*(?:include|import|define)\b",
            r"\b(?:AccountInfo\w*|FILE_COMMON)\b",
        ]
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, self.text), pattern)

    def test_symbol_and_period_guard(self):
        self.assertIn('if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || _Point<=0) return INIT_FAILED;', self.text)

    def test_schema_contains_required_observations(self):
        required = {
            "signal_bar_epoch", "entry_tick_time_msc", "horizon_end_time_msc",
            "signal_side", "signal_score", "linreg_slope_current", "ema_fast", "rsi",
            "entry_bid", "entry_ask", "spread_p95_points",
            "buy_mfe_points", "buy_mae_points", "sell_mfe_points", "sell_mae_points",
            "buy_fav_130_msc", "sell_fav_130_msc", "buy_adv_260_msc", "sell_adv_260_msc",
            "observed_tick_count", "largest_tick_gap_msc", "label_status", "quality_flags",
        }
        self.assertTrue(required.issubset(set(self.header)))
        self.assertEqual(len(self.header), len(set(self.header)))

    def test_allowed_labels_present(self):
        for value in ("COMPLETE", "INVALID_GAP", "INVALID_DISCONNECT", "INVALID_ROLLOVER", "INCOMPLETE_HORIZON"):
            self.assertIn(value, self.text)

    def test_no_lookahead_and_incomplete_discard(self):
        self.assertIn("entryTick.time_msc", self.text)
        self.assertIn("if(activeBar==0)", self.text)
        self.assertIn("INCOMPLETE_HORIZON records intentionally remain memory-only", self.text)
        self.assertNotIn("FileWriteString(name", self.text)

    def test_first_passage_levels_and_executable_quotes(self):
        self.assertIn("buyMove=PointSteps(tick.bid-p.entryAsk)", self.text)
        self.assertIn("sellMove=PointSteps(p.entryBid-tick.ask)", self.text)
        self.assertIn("buyAdvMove=PointSteps(p.entryAsk-tick.bid)", self.text)
        self.assertIn("sellAdvMove=PointSteps(tick.ask-p.entryBid)", self.text)
        self.assertIn("MathRound(priceDelta/_Point)", self.text)
        self.assertIn("const int FAVOR_LEVELS[12]", self.text)
        self.assertIn("const int ADVERSE_LEVELS[10]", self.text)

    def test_be_recross_is_recorded_after_trigger(self):
        for column in (
            "buy_be_t75_l15_recross_msc", "buy_be_t85_l15_recross_msc",
            "buy_be_t130_l20_recross_msc", "sell_be_t75_l15_recross_msc",
            "sell_be_t85_l15_recross_msc", "sell_be_t130_l20_recross_msc",
        ):
            self.assertIn(column, self.header)
        self.assertIn("buyBeArmed[trigger]", self.text)
        self.assertIn("sellBeArmed[trigger]", self.text)
        self.assertIn("buyMove<=BE_LOCK_LEVELS[lock]", self.text)
        self.assertIn("sellMove<=BE_LOCK_LEVELS[lock]", self.text)
        self.assertIn("BE_TRIGGER_COUNT*BE_LOCK_COUNT", self.text)

    def test_schema_bumped_for_executable_price_fix(self):
        self.assertIn('const string SCHEMA_VERSION="2";', self.text)
        self.assertIn('const string COLLECTOR_VERSION="16.32";', self.text)

    def test_horizon_and_daily_private_output(self):
        self.assertIn("const int HORIZON_BARS=15", self.text)
        self.assertIn('const string DATA_DIR="V16TickResearch\\\\"', self.text)
        self.assertIn("V16TickTelemetry_XAUUSD_M1_", self.text)
        self.assertIn("FolderCreate(\"V16TickResearch\")", self.text)

    def test_invalid_quality_is_fail_closed(self):
        self.assertIn('if(p.disconnect) return "INVALID_DISCONNECT";', self.text)
        self.assertIn('if(p.missingBars>0) return "INVALID_GAP";', self.text)
        self.assertIn('if(p.rollover) return "INVALID_ROLLOVER";', self.text)
        self.assertIn('return "COMPLETE";', self.text)
        self.assertNotIn('Flush(0,"COMPLETE"', self.text)

    def test_quality_flags_do_not_prefix_ok_to_error_tokens(self):
        self.assertNotIn('flags+=(flags=="OK"', self.text)
        self.assertIn('flags=(flags=="OK" ? "DISCONNECT" : flags+"|DISCONNECT")', self.text)
        self.assertIn('flags=(flags=="OK" ? "ROLLOVER" : flags+"|ROLLOVER")', self.text)
        self.assertIn('flags=(flags=="OK" ? "SPREAD_HIST_CAP" : flags+"|SPREAD_HIST_CAP")', self.text)

    def test_horizon_boundary_does_not_include_next_bar_tick(self):
        on_tick = re.search(r"void OnTick\(\)\s*\{(.*?)\n\}", self.text, re.S)
        self.assertIsNotNone(on_tick)
        body = on_tick.group(1)
        advance = body.index("AdvanceCompletedBar(lastTickMsc)")
        update = body.index("UpdatePath(queue[i],tick)")
        self.assertLess(advance, update)
        self.assertIn("queue[0].horizonEndMsc=horizonEndMsc", self.text)

    def test_disconnect_and_rollover_are_observed_over_full_horizon(self):
        self.assertIn("EventSetTimer(1)", self.text)
        self.assertIn("void OnTimer()", self.text)
        self.assertIn("TerminalInfoInteger(TERMINAL_CONNECTED)", self.text)
        self.assertIn('if(SessionLabel(tick.time)=="ROLLOVER") p.rollover=true;', self.text)
        self.assertIn("EventKillTimer()", self.text)

    def test_previous_slope_is_one_bar_shift_not_disjoint_window(self):
        self.assertIn("Slope(r,copied,copied-10,10)", self.text)
        self.assertIn("Slope(r,copied,copied-11,10)", self.text)
        self.assertNotIn("Slope(r,copied,copied-20,10)", self.text)

    def test_spread_p95_uses_full_horizon_histogram(self):
        self.assertIn("spreadHistogram[2001]", self.text)
        self.assertIn("p.spreadHistogram[spreadBin]++", self.text)
        self.assertIn("0.95*(double)p.observedTicks", self.text)
        self.assertNotIn("p.spreadCount<256", self.text)
        self.assertIn("int spreadBin=(int)spread", self.text)
        self.assertNotIn("MathCeil(spread)", self.text)

    def test_session_boundaries_include_uk_and_us_dst(self):
        self.assertIn("bool IsUkSummer", self.text)
        self.assertIn("bool IsUsSummer", self.text)
        self.assertIn("15*3600+1800", self.text)
        self.assertIn("16*3600+1800", self.text)


if __name__ == "__main__":
    unittest.main()
