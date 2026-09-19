import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("policy", ROOT / "tools" / "v16_tick_policy_report.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def row(self, **extra):
        base = {"schema_version": "2", "label_status": "COMPLETE", "entry_tick_time_msc": "1000",
                "horizon_end_time_msc": "2000", "disconnect_seen": "0", "rollover_seen": "0",
                "missing_bar_count": "0", "signal_bar_epoch": "1", "observed_tick_count": "1",
                "completed_bar_count": "15"}
        base.update(extra)
        return base

    def test_policy_uses_first_timestamp(self):
        r = self.row(buy_fav_180_msc="1300", buy_adv_260_msc="1500", buy_fav_85_msc="1200",
                     buy_be_t85_l15_recross_msc="1400")
        self.assertEqual(policy.reconstruct(r, "BUY", 180, 260, 85, 15)["outcome"], "TP")

    def test_be_requires_trigger_and_chronology(self):
        r = self.row(buy_be_t85_l15_recross_msc="1200")
        self.assertEqual(policy.reconstruct(r, "BUY", 180, 260, 85, 15)["outcome"], "INVALID")
        r["buy_fav_85_msc"] = "1300"
        self.assertEqual(policy.reconstruct(r, "BUY", 180, 260, 85, 15)["outcome"], "INVALID")

    def test_same_timestamp_fail_closed(self):
        r = self.row(buy_fav_180_msc="1300", buy_adv_260_msc="1300")
        self.assertEqual(policy.reconstruct(r, "BUY", 180, 260, 85, 15)["outcome"], "INVALID")

    def test_invalid_quality_rejected(self):
        ok, reason = policy.valid_row(self.row(label_status="INVALID_ROLLOVER"))
        self.assertFalse(ok)
        self.assertEqual(reason, "INVALID_ROLLOVER")


if __name__ == "__main__":
    unittest.main()
