"""Verify a native tester's terminal liquidation, never rewrite or drop a deal."""
from __future__ import annotations

from datetime import datetime
import re

from research.analyze_v23_backtest import bucket, finite, parse_deals, timestamp

ALLOWED_SOURCES = frozenset(("research/ResearchCandidate_R8.mq5",
                            "research/ResearchControl_R1_R8.mq5",
                            "research/ResearchCandidate_R10.mq5",
                            "research/ResearchCandidate_R11.mq5",
                            "research/ResearchCandidate_R12.mq5"))


def need(ok, message):
    if not ok:
        raise ValueError("Native end-close verification: " + message)


def parse_verified_native_deals(rows, native_metrics, native_rows, specs, journal, *,
                                end, deposit, candidate_source):
    """Return trades, cash, audit. Exception limited to explicit reporting clones.

    Numeric epoch formatting compares the same broker-coded coordinate system.
    Nothing here establishes the actual broker timezone or reads future signals.
    """
    if candidate_source not in ALLOWED_SOURCES:
        trades, cash = parse_deals(rows)
        return trades, cash, dict(verified=False, tickets=[])
    foreign = [r for r in rows if int(r["type"]) in (0, 1) and int(r["magic"]) != 992300]
    tickets = set()
    proof = dict(verified=False, tickets=[])
    if foreign:
        need(len(foreign) == 1, "multiple foreign trading deals")
        d = foreign[0]
        ticket, pos, clock = (int(d[k]) for k in ("ticket", "position", "time_msc"))
        need(ticket > 0 and pos > 0 and int(d["magic"]) == 0 and int(d["reason"]) == 0
             and int(d["entry"]) == 1 and d["symbol"] == "XAUUSD"
             and d["comment"] == "end of test", "not the exact native terminal-close form")
        need(ticket == max(int(r["ticket"]) for r in rows)
             and clock == max(int(r["time_msc"]) for r in rows), "close not final ledger event")
        last_tick = int(specs["last_tick"])
        # Requested tester calendar date and displayed deal date use the same
        # broker-coded clock. Compare naive displayed calendars, not real UTC.
        limit = datetime.strptime(end, "%Y.%m.%d")
        need(0 < last_tick < clock and timestamp(clock) < limit,
             "close outside post-quote requested interval")
        openings = [r for r in rows if int(r["type"]) in (0, 1)
                    and int(r["position"]) == pos and int(r["entry"]) == 0]
        exits = [r for r in rows if int(r["type"]) in (0, 1)
                 and int(r["position"]) == pos and int(r["entry"]) != 0]
        need(len(openings) == 1 and len(exits) == 1, "ambiguous owner or partial/add-on exit")
        owner = openings[0]
        need(int(owner["magic"]) == 992300 and owner["symbol"] == "XAUUSD"
             and int(owner["time_msc"]) < clock and int(owner["type"]) != int(d["type"])
             and finite(owner["volume"]) == finite(d["volume"]) == .01,
             "ownership, side, time or full volume mismatch")
        side = "buy" if int(d["type"]) == 0 else "sell"
        owner_side = "buy" if int(owner["type"]) == 0 else "sell"
        displayed = timestamp(clock).strftime("%Y.%m.%d %H:%M:%S")
        matching = [r for r in native_rows if len(r) == 13 and r[1] == str(ticket) and r[4] == "out"]
        need(len(matching) == 1, "missing or duplicate native HTML exit")
        html = matching[0]
        need(html[0] == displayed and html[2] == d["symbol"] and html[3] == side
             and html[7] == str(ticket) and html[12] == "end of test", "HTML identity mismatch")
        for column, key in ((5, "volume"), (6, "price"), (8, "commission"), (9, "swap"), (10, "profit")):
            need(abs(finite(html[column])-finite(d[key])) <= 1e-8, "HTML economics mismatch: " + key)
        need(finite(d["fee"]) == 0.0, "unreported end-close fee")
        need(abs(finite(html[11])-finite(specs["final_balance"])) <= .0051, "HTML final balance mismatch")
        close_pattern = (r"(20\d\d\.\d\d\.\d\d \d\d:\d\d:\d\d)\s+position closed due end of test at "
                         r"([\d.]+) \[#(\d+) (buy|sell) ([\d.]+) XAUUSD ([\d.]+)[^\]\r\n]*\]")
        close_lines = [m for m in re.findall(close_pattern, journal) if m[2] == str(pos)]
        need(bool(close_lines), "native liquidation journal missing")
        need(all(m[0] == displayed and finite(m[1]) == finite(d["price"])
                 and m[3] == owner_side and finite(m[4]) == finite(d["volume"])
                 and finite(m[5]) == finite(owner["price"]) for m in close_lines),
             "native liquidation journal mismatch")
        deal_pattern = (r"(20\d\d\.\d\d\.\d\d \d\d:\d\d:\d\d)\s+deal #" + str(ticket)
                        + r" (buy|sell) ([\d.]+) XAUUSD at ([\d.]+) done \(based on order #(\d+)\)")
        deal_lines = re.findall(deal_pattern, journal)
        need(bool(deal_lines) and all(m[0] == displayed and m[1] == side
             and finite(m[2]) == finite(d["volume"]) and finite(m[3]) == finite(d["price"])
             and m[4] == str(ticket) for m in deal_lines), "native close deal/order journal mismatch")
        tickets.add(ticket)
        proof = dict(verified=True, tickets=[ticket], position=pos,
                     raw_magic=int(d["magic"]), raw_reason=int(d["reason"]),
                     close_time_msc=clock, last_observed_tick_msc=last_tick,
                     scope="Native tester end-close only. Original ledger unchanged.")
    trades, cash = parse_deals(rows, native_end_tickets=frozenset(tickets))
    economic_count = sum(int(r["type"]) in (0, 1) for r in rows)
    need(economic_count == finite(native_metrics["Total Deals"]), "native deal-count mismatch")
    need(len(cash) == 1 and cash[0]["type"] == 2 and abs(cash[0]["net"]-deposit) <= .0051,
         "cash/deposit adjustment mismatch")
    summary = bucket(trades)
    need(summary["trades"] == finite(native_metrics["Total Trades"])
         and abs(summary["net"]-finite(native_metrics["Total Net Profit"])) <= .0051,
         "native position count/net mismatch")
    need(abs(finite(specs["final_balance"])-deposit-summary["net"]) <= .0051,
         "native final balance mismatch")
    return trades, cash, proof
