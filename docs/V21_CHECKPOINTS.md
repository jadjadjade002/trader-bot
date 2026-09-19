# V21 Collector checkpoints and stop rules

The V21 Forward Collector is kept running because it is the only currently
sealed source that can answer its frozen question. It sends no orders and must
not alter the v16 account or its terminal.

## Immediate operating checkpoint

At each inspection, require the current health row to be `HEALTHY`, connected,
synchronized, zero write errors, zero duplicate skips, and a fresh completed
bar. A nonzero gap count is recorded, not repaired: market closures can create
gaps and the outcome analysis will reject probes requiring contiguous bars.
Any unhealthy state is an operations incident, not evidence for or against the
hypothesis.

## Decision checkpoints

Run `python research/v21_decision.py <collector-data-directory> --output
research/v21_decision_snapshot.json` after 5, 10, and 15 broker-session dates,
and at the sealed end time of 2026-10-07 15:00 broker time. The script reports
`INCONCLUSIVE_ACQUISITION_INCOMPLETE` before both 1,000 valid probes and 15
session dates. It cannot promote an EA.

At 15 dates, any failed quality gate is a final failure of this frozen V21
hypothesis. We do not retune its feature, threshold, session, label, cadence,
or exit to rescue it. A pass permits only a separately authorized execution
experiment on a different stream.

## Parallel work that does not wait for the Collector

V21.67 has already been rejected by its native real-tick result: 40 trades,
50% wins, net -$53.51, and 106.80% relative equity drawdown. Its fatal gap
loss showed that a 10-minute hold and a broker stop cannot guarantee an exit
when the market has no executable quote. No threshold tuning or deployment is
allowed from that exposed test.

The active engineering work is therefore restricted to execution safety and
research infrastructure: complete order lifecycle checks, session-gap
containment requirements, and reproducible data decisions. It does not create
another live EA or touch V16.
