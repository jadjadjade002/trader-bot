# QuantumTitan v19 development hypothesis

## Mechanism

Version 19 tests one closed-bar XAUUSD M1 breakout mechanism. On the first eligible tick of a new bar, it buys only when `Close[1]` is strictly above the maximum of `High[2..4]`, or sells only when `Close[1]` is strictly below the minimum of `Low[2..4]`. Equality produces no signal. The signal expires ten seconds after the new bar opens.

The entry-time ATR(14) value from the completed bar is frozen. Both protected stop and target are one ATR from the requested entry, rounded outward to the symbol tick size. There is no breakeven, trailing, grid, or martingale behavior.

## Safety and lifecycle

The candidate uses magic `991901` and a fixed `0.01` lot. Non-tester use is demo-only. An account-wide terminal Global Variable provides an atomic entry mutex, and symbols whose canonical uppercase name contains `XAUUSD` block concurrent entry across broker suffix aliases. The EA manages only its own magic, stops new entries at 01:57 broker time, closes its own position at or after 02:00 on the first tradable tick, enforces a three-minute maximum hold, and restores the 60-second post-exit cooldown by linking closing deals—including manual exits—to their original magic-tagged entry deal after restart.

Every entry must have nonzero SL and TP, pass volume, margin, tick-size, spread, broker stop/freeze-distance, and order checks, and receive an accepted trade retcode. Spread is capped at 40 points and at 20% of the frozen one-ATR target. Stop distance is capped at 450 points.

## Single development decision

Run exactly one development backtest with real ticks and 200 ms execution delay. Continue the candidate only if all criteria pass:

- At least 140 trades.
- Positive net-cost expectancy.
- Profit factor at least 1.10.
- Relative equity drawdown no greater than 20%.
- Zero safety violations.

Failure of any criterion terminates v19. There is no holdout run and no parameter sweep.
