# QuantumTitan v17 validation record

## Scope

v17 is a demo-only XAUUSD M1 research EA with a fixed 0.01 lot. It does not
use RiskGuardian, grids, Martingale, or multiple simultaneous gold positions.
The target of 10 to 20 winning overnight trades is unverified and is not a
deployment criterion.

## Hardening completed

- Stop selection is explicit: fixed, structural, or hybrid. An oversized stop
  rejects the setup rather than clipping the stop inside the rejection candle.
- Macro filtering fails closed when the H1 indicator value is not ready.
- Break-even and micro-trailing issue no more than one modification request per
  tick, and result codes are written to the journal.
- The test runner freezes all v17 inputs and records SHA-256 fingerprints for
  source, binary, signal module, and signal tests beside the report.
- The runner verifies that the generated report was refreshed by the current
  tester process.

## Native MT5 results

Both runs used MetaQuotes-Demo XAUUSD M1, 100% real ticks, 200 ms execution
delay, USD 50 deposit, 1:500 leverage, v17 mode 0, hybrid stop mode, and the
same source fingerprint recorded in the adjacent metadata files.

Development, 2026-08-03 to 2026-08-22: 198 closed trades, 118 net-cost wins
(59.60%), net PnL -$41.42, profit factor 0.69, and relative equity drawdown
84.23%.

Holdout, 2026-08-24 to 2026-09-08: 144 closed trades, 84 net-cost wins
(58.33%), net PnL -$43.20, profit factor 0.61, and relative equity drawdown
86.66%.

The report parser counts wins after commission, swap, and fees. Native MT5's
gross profit-trade count can therefore be higher than the net-cost win count.

For the broker-time overnight window 18:00 to 02:00, the holdout average was
5.1 qualifying entries per weekday window, and zero of ten complete windows
met all three target conditions: 10 to 20 trades, at least 80% net-cost wins,
and positive net PnL.

## Decision

v17 is not suitable for deployment or forward demo operation in this form.
The next strategy candidate must have a written hypothesis and be evaluated on
a fresh training and holdout split without using the holdout result to tune it.
