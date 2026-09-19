# QuantumTitan v20 post-hoc exploratory hypothesis

## Mechanism

Version 20 is explicitly a post-hoc exploratory inversion of v19, not a confirmatory test. On the first eligible tick of a new XAUUSD M1 bar, it sells when `Close[1]` is strictly above the maximum of `High[2..4]`, treating the upper breakout as exhaustion, and buys when `Close[1]` is strictly below the minimum of `Low[2..4]`, treating the lower breakout as exhaustion. Equality has no signal and the signal expires after ten seconds.

All v19 controls remain frozen: fixed `0.01` lot, magic `992001`, one frozen ATR(14) for both protected SL and TP, three-minute maximum hold, 18:00-02:00 session, 01:57 entry cutoff, 60-second cooldown, spread and stop limits, account-wide XAU mutex, canonical XAU exposure blocking, entry-linked closing-deal ownership, and isolated manifest/report validation.

## Frozen decision gates

Run one development test with real ticks and 200 ms execution delay. The post-hoc candidate passes only if every gate holds:

- At least 140 trades.
- Net profit is positive.
- Profit factor is at least 1.10.
- Relative equity drawdown is no greater than 20%.
- Zero safety violations.

Any failure terminates strategy iteration and requires building the data-export pipeline before further research. There are no parameter changes and no holdout run.
