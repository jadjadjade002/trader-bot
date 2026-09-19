# R2 validation

## Decision

R2 Trend Pullback Continuation was terminated at its preregistered training-viability guard. No validation fold was evaluated, no MT5 execution EA was created, and no deployment was performed.

## Data integrity

The isolated local MT5 exporter produced 105,149 completed XAUUSD M1 bars for 2026-04-06 through 2026-07-26 broker time using real ticks and 200 ms execution delay. Nonempty monthly tick caches for April, May, June, and July were verified after the run. The dataset contains 21,027 complete M5 buckets and 7,007 complete M15 buckets.

## Training viability

The nominal `S=0.10` variant required at least 35 training opportunities in every four-week fold before its following validation window could be opened. It produced 26, 26, 25, and 30 opportunities across folds one through four. Every fold failed the minimum.

Consequently, all validation fields remained unopened and empty. Aggregate validation trade count is zero by design, not because the system found zero validation signals. Six focused implementation tests passed.

## Stopping rule

R2 is abandoned without weakening its filters, changing its session or holding period, promoting a sensitivity variant, or reusing its unopened windows for post-hoc tuning. A subsequent attempt must use a materially different mechanism and a previously unused interval ending before 2026-04-06.
