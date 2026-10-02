import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from research.v25_forward_gate import (
    FROZEN_BINARY_SHA256,
    FROZEN_SOURCE_SHA256,
    evaluate,
)


class V25ForwardGateTests(unittest.TestCase):
    def sample(self, first_date="2026-09-29"):
        trades = []
        start = datetime.fromisoformat(first_date)
        for i in range(30):
            day = start + timedelta(days=i // 3)
            trades.append({"open": day.replace(hour=18).isoformat(), "net": 1.0})
        return {"closed": trades, "net": 30.0,
                "native": {"Profit Factor": "2.00", "Equity Drawdown Relative": "5.0% (10.0)"}}

    def evaluate_mocked(self, sample, metadata=None):
        metadata = metadata or {"sourceSha256": FROZEN_SOURCE_SHA256,
                                "binarySha256": FROZEN_BINARY_SHA256}
        with patch("research.v25_forward_gate.analyze", return_value=sample), \
             patch.object(Path, "read_text", return_value=json.dumps(metadata)):
            return evaluate(Path("report.htm"), Path("metadata.json"))

    def test_rejects_pre_freeze_trades(self):
        result = self.evaluate_mocked(self.sample("2026-09-01"))
        self.assertIn("REUSED_PRE_FREEZE_TRADE", result["reasons"])
        self.assertFalse(result["deployment_approved"])

    def test_post_freeze_can_only_be_reviewable(self):
        result = self.evaluate_mocked(self.sample())
        self.assertEqual(result["status"], "REVIEWABLE_NOT_DEPLOY_APPROVED")
        self.assertFalse(result["deployment_approved"])

    def test_hash_mismatch_blocks(self):
        result = self.evaluate_mocked(self.sample(), {"sourceSha256": "wrong", "binarySha256": "wrong"})
        self.assertIn("SOURCE_HASH_MISMATCH", result["reasons"])
        self.assertIn("BINARY_HASH_MISMATCH", result["reasons"])


if __name__ == "__main__":
    unittest.main()
