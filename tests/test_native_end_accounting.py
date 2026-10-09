from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_end_accounting", ROOT / "research/native_end_accounting.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE = "research/ResearchCandidate_R8.mq5"
END = "2026.05.02"


def ms(text):
    return int(datetime.strptime(text, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)


def ledger(*, close_profit=1.0, close_time="2026.05.01 00:01:00"):
    close_msc = ms(close_time)
    rows = [
        dict(ticket="1", position="0", time_msc=str(close_msc - 20_000), type="2", entry="0", reason="0",
             magic="0", symbol="", volume="0", price="0", profit="10000", commission="0", swap="0",
             fee="0", comment="Initial Deposit"),
        dict(ticket="2", position="77", time_msc=str(close_msc - 10_000), type="0", entry="0", reason="0",
             magic="992300", symbol="XAUUSD", volume="0.01", price="99", profit="0", commission="0",
             swap="0", fee="0", comment="R8"),
        dict(ticket="3", position="77", time_msc=str(close_msc), type="1", entry="1", reason="0",
             magic="0", symbol="XAUUSD", volume="0.01", price="100", profit=str(close_profit),
             commission="0", swap="0", fee="0", comment="end of test"),
    ]
    final = 10000 + close_profit
    native_rows = [[close_time, "3", "XAUUSD", "sell", "out", "0.01", "100", "3", "0", "0",
                    str(close_profit), str(final), "end of test"]]
    journal = (f"{close_time} position closed due end of test at 100 [#77 buy 0.01 XAUUSD 99 100]\n"
               f"{close_time} deal #3 sell 0.01 XAUUSD at 100 done (based on order #3)")
    specs = dict(last_tick=str(close_msc - 1), final_balance=str(final))
    metrics = {"Total Deals": "2", "Total Trades": "1", "Total Net Profit": str(close_profit)}
    return rows, metrics, native_rows, specs, journal


def parse(args=None, *, source=SOURCE):
    args = args or ledger()
    return module.parse_verified_native_deals(args[0], args[1], args[2], args[3], args[4],
                                              end=END, deposit=10000, candidate_source=source)


@pytest.mark.parametrize("source", [SOURCE, "research/ResearchCandidate_R10.mq5",
                                   "research/ResearchCandidate_R11.mq5",
                                   "research/ResearchCandidate_R12.mq5"])
def test_exact_terminal_close_included_without_mutating_original_ledger(source):
    args = ledger(close_profit=-2.25)
    before = deepcopy(args[0])
    trades, cash, audit = parse(args, source=source)
    assert args[0] == before
    assert len(trades) == 1 and trades[0]["net"] == pytest.approx(-2.25)
    assert len(cash) == 1 and cash[0]["net"] == pytest.approx(10000)
    assert audit["verified"] is True and audit["tickets"] == [3]


@pytest.mark.parametrize("change", [
    "ticket", "position", "clock", "type", "entry", "reason", "magic", "symbol", "volume", "price",
    "profit", "commission", "swap", "fee", "comment",
])
def test_terminal_close_raw_deal_mutations_fail_closed(change):
    args = ledger()
    row = args[0][2]
    replacements = {
        "ticket": "4", "position": "78", "clock": str(int(row["time_msc"]) + 5000), "type": "0",
        "entry": "0", "reason": "1", "magic": "3", "symbol": "OTHER", "volume": "0.02",
        "price": "101", "profit": "2", "commission": "-0.1", "swap": "-0.1", "fee": "0.01",
        "comment": "manual",
    }
    key = "time_msc" if change == "clock" else change
    row[key] = replacements[change]
    with pytest.raises(ValueError):
        parse(args)


@pytest.mark.parametrize("change", ["missing", "duplicate", "economics", "balance", "side", "timestamp"])
def test_native_html_must_match_exact_close(change):
    args = ledger()
    if change == "missing":
        args[2].clear()
    elif change == "duplicate":
        args[2].append(list(args[2][0]))
    elif change == "economics":
        args[2][0][10] = "1.1"
    elif change == "balance":
        args[2][0][11] = "10001.02"
    elif change == "side":
        args[2][0][3] = "buy"
    else:
        args[2][0][0] = "2026.05.01 00:01:01"
    with pytest.raises(ValueError):
        parse(args)


def test_missing_or_mismatched_close_journal_fails_but_identical_duplicate_is_allowed():
    args = list(ledger())
    args[4] = args[4].splitlines()[0]
    with pytest.raises(ValueError):
        parse(args)
    args = list(ledger())
    args[4] += "\n" + args[4].splitlines()[0]
    assert parse(args)[2]["verified"]
    args = list(ledger())
    args[4] = args[4].replace("at 100", "at 101")
    with pytest.raises(ValueError):
        parse(args)
    args = list(ledger())
    args[4] = args[4].replace("deal #3 sell 0.01", "deal #4 sell 0.01")
    with pytest.raises(ValueError):
        parse(args)


@pytest.mark.parametrize("mutate", ["foreign_final", "nonowned_open", "partial_close", "second_position",
                                     "open_after_close", "last_tick_after_close", "close_at_end"])
def test_unsupported_or_unbounded_terminal_ledger_rejected(mutate):
    args = ledger()
    if mutate == "foreign_final":
        args[0][2]["ticket"] = "9"
    elif mutate == "nonowned_open":
        args[0][1]["magic"] = "0"
    elif mutate == "partial_close":
        args[0][2]["volume"] = "0.005"
    elif mutate == "second_position":
        extra = dict(args[0][1]); extra.update(ticket="4", position="88", time_msc=str(int(args[0][1]["time_msc"]) + 1))
        args[0].insert(2, extra)
    elif mutate == "open_after_close":
        args[0][1]["time_msc"] = str(int(args[0][2]["time_msc"]) + 1)
    elif mutate == "last_tick_after_close":
        args[3]["last_tick"] = str(int(args[0][2]["time_msc"]) + 1)
    else:
        args[0][2]["time_msc"] = str(ms(END + " 00:00:00"))
    with pytest.raises(ValueError):
        parse(args)


def test_cash_adjustments_counts_net_final_balance_and_unreported_fee_are_checked():
    args = ledger()
    args[0][0]["profit"] = "9999"
    with pytest.raises(ValueError):
        parse(args)
    args = ledger()
    args[1]["Total Deals"] = "3"
    with pytest.raises(ValueError):
        parse(args)
    args = ledger()
    args[1]["Total Trades"] = "2"
    with pytest.raises(ValueError):
        parse(args)
    args = ledger()
    args[0][2]["profit"] = "1.1"
    with pytest.raises(ValueError):
        parse(args)
    args = ledger()
    args[0][2]["fee"] = "0.01"
    args[1]["Total Net Profit"] = "1.01"
    args[3]["final_balance"] = "10001.01"
    args[2][0][10] = "1.01"
    args[2][0][11] = "10001.01"
    with pytest.raises(ValueError):
        parse(args)
    args = ledger()
    args[0].append(dict(args[0][0], ticket="4", time_msc=str(int(args[0][0]["time_msc"]) + 1),
                        profit="1", comment="unexplained cash adjustment"))
    with pytest.raises(ValueError):
        parse(args)


def test_multiple_foreign_trading_rows_rejected():
    args = ledger()
    other = dict(args[0][2], ticket="4", position="78", time_msc=str(int(args[0][2]["time_msc"]) + 1))
    args[0].append(other)
    with pytest.raises(ValueError):
        parse(args)


def test_unreviewed_source_keeps_strict_default_parser():
    args = ledger()
    with pytest.raises(ValueError):
        parse(args, source="research/OtherCandidate.mq5")


def test_default_parser_never_accepts_native_end_without_external_proof():
    with pytest.raises(ValueError, match="Foreign trading deal"):
        module.parse_deals(ledger()[0])
    with pytest.raises(ValueError, match="Invalid verified native-end"):
        module.parse_deals(ledger()[0], native_end_tickets=frozenset((2, 3)))


@pytest.mark.parametrize("field", ["Total Deals", "Total Trades"])
def test_fractional_native_counts_rejected(field):
    args = ledger()
    args[1][field] = str(float(args[1][field]) + .1)
    with pytest.raises(ValueError):
        parse(args)


def test_duplicate_journal_with_one_conflicting_line_is_rejected():
    args = list(ledger())
    args[4] += "\n" + args[4].splitlines()[0].replace("at 100", "at 101")
    with pytest.raises(ValueError):
        parse(args)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "not-a-number"])
def test_nonfinite_native_values_fail_closed(value):
    args = ledger()
    args[0][2]["price"] = value
    with pytest.raises(ValueError):
        parse(args)
