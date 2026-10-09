import unittest
from pathlib import Path

from scripts.v24_vm_upgrade import patch_chart


class V24DeploymentTests(unittest.TestCase):
    def chart(self):
        return "\n".join(("name=AegisPredator_v23", "path=Experts\\AegisPredator_v23.ex5",
            "InpFadeBreakouts=true", "InpTargetAccount=5056497798", "InpMagicNumber=992300",
            "InpLotSize=0.01", "InpStopLossATRMul=1.5", "InpTakeProfitRRMul=2.0",
            "InpEnableCircuitBreaker=true", "InpMaxConsecutiveLosses=4", "InpCooldownMinutes=90"))

    def test_only_expert_name_path_and_fade_change(self):
        old=self.chart()
        new=patch_chart(old)
        self.assertEqual(new.replace("AegisPredator_v24", "AegisPredator_v23")
                         .replace("InpFadeBreakouts=false", "InpFadeBreakouts=true"), old)

    def test_changed_account_rejected(self):
        with self.assertRaisesRegex(ValueError,"changed"):
            patch_chart(self.chart().replace("5056497798", "112334471"))

    def test_changed_config_rejected(self):
        with self.assertRaisesRegex(ValueError,"changed"):
            patch_chart(self.chart().replace("InpStopLossATRMul=1.5", "InpStopLossATRMul=2.0"))

    def test_duplicate_expert_rejected(self):
        with self.assertRaisesRegex(ValueError,"exactly one"):
            patch_chart(self.chart()+"\nname=AegisPredator_v23")

    def test_no_blanket_process_kill_or_position_close(self):
        text=Path("scripts/v24_vm_upgrade.py").read_text(encoding="utf-8")
        for forbidden in ("pkill", "killall", "SIGKILL", "PositionClose", "OrderSend", "os.kill("):
            self.assertNotIn(forbidden,text)
        self.assertIn('WM_DELETE_WINDOW',text)
        self.assertIn('other_terminal_pids_after',text)
