import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
V25_FILE = ROOT / "AegisPredator_v25.mq5"
V24_FILE = ROOT / "AegisPredator_v24.mq5"


def extract_function_body(text: str, func_name: str) -> str:
    """Extract function body by locating function definition and brace matching."""
    match = re.search(rf"\b[A-Za-z0-9_]+\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{", text)
    if not match:
        raise ValueError(f"Function definition for {func_name} not found")
    open_brace = match.end() - 1
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace : i + 1]
    raise ValueError(f"Unmatched braces in {func_name}")


class TestV25EA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v25_text = V25_FILE.read_text(encoding="utf-8")
        cls.v24_text = V24_FILE.read_text(encoding="utf-8")

    def test_compiles_looking_structure(self):
        """(a) Structure contains OnInit, OnTick, and OnDeinit."""
        for handler in ("OnInit", "OnTick", "OnDeinit"):
            self.assertIn(handler, self.v25_text)
            self.assertRegex(self.v25_text, rf"\b{handler}\s*\(")

    def test_proposed_signal_byte_identical_to_v24(self):
        """(b) Function body of ProposedSignal is byte-identical to AegisPredator_v24.mq5."""
        body_v25 = extract_function_body(self.v25_text, "ProposedSignal")
        body_v24 = extract_function_body(self.v24_text, "ProposedSignal")
        self.assertEqual(body_v25.encode("utf-8"), body_v24.encode("utf-8"))

    def test_magic_number_not_992300(self):
        """(c) InpMagicNumber != 992300."""
        match = re.search(r"\bInpMagicNumber\s*=\s*(\d+)", self.v25_text)
        self.assertIsNotNone(match, "InpMagicNumber input definition not found")
        magic = int(match.group(1))
        self.assertNotEqual(magic, 992300)

    def test_no_donchian_or_fade_breakouts(self):
        """(d) No leftover Donchian or InpFadeBreakouts identifiers."""
        self.assertNotIn("Donchian", self.v25_text)
        self.assertNotIn("InpFadeBreakouts", self.v25_text)

    def test_open_trade_has_open_position_before_retry(self):
        """(e) HasOpenPosition() is called before a retry in OpenTrade (string-order check)."""
        open_trade_body = extract_function_body(self.v25_text, "OpenTrade")
        hop_idx = open_trade_body.find("HasOpenPosition()")
        self.assertNotEqual(hop_idx, -1, "HasOpenPosition() not found in OpenTrade")

        order_idx = open_trade_body.find("trade.Buy")
        self.assertNotEqual(order_idx, -1, "trade.Buy not found in OpenTrade")
        self.assertLess(hop_idx, order_idx, "HasOpenPosition() must be checked before order send in loop")

        retry_idx = open_trade_body.find("RetryableRetcode")
        self.assertNotEqual(retry_idx, -1, "RetryableRetcode not found in OpenTrade")
        self.assertLess(hop_idx, retry_idx, "HasOpenPosition() must be checked before retry handling")

    def test_no_v23_label_text(self):
        """(f) The file contains no 'V23' label text."""
        string_literals = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', self.v25_text)
        v23_strings = [s for s in string_literals if "V23" in s]
        self.assertEqual(v23_strings, [], f"Found V23 in string literal / label: {v23_strings}")
        self.assertNotIn("AegisPredator V23", self.v25_text)
        self.assertNotIn("V23 Status", self.v25_text)


if __name__ == "__main__":
    unittest.main()
