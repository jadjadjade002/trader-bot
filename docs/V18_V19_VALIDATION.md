# v18 and v19 development validation

## Decision

Neither candidate is eligible for holdout testing or deployment. Both remain local research artifacts. The running v16 VM was not changed.

## Fixed test conditions

The tests used XAUUSD M1, MetaQuotes-Demo real ticks, 200 ms execution delay, a USD 50 deposit, and the development period from 2026-08-03 through 2026-08-22. Results were reconciled from native MT5 reports with transaction costs included. Complete overnight windows were measured from 18:00 to 02:00 broker time.

## v18 sweep-reclaim branch

The original v18 baseline produced 32 completed trades, 10 net-cost wins, a 31.25% win rate, USD -32.62 net profit, native profit factor 0.36, 73.26% relative equity drawdown, and 2.21 trades per complete overnight window. None of 14 complete windows met the frequency, win-rate, and positive-net target together.

The predeclared ADX ceiling experiment at 25 produced 18 trades, a 27.78% win rate, USD -20.04 net profit, profit factor 0.326, and 1.21 trades per overnight window. It failed the positive-net and profit-factor gates and reduced opportunity count.

The final categorical ADX-removal test produced 35 trades, a 25.71% win rate, USD -43.03 net profit, and 2.50 trades per overnight window. It also supplied only three additional trades, below the required high-ADX subgroup evidence. The v18 branch is terminated without using holdout data or running a threshold sweep.

## v19 closing-breakout branch

Version 19 tested a materially different three-bar closing breakout with fixed 0.01 lot, one XAU exposure, one-ATR protected stop and target, a three-minute maximum hold, and no break-even, trailing, grid, martingale, or external risk module.

The single development run produced 119 trades, 48 net-cost wins, a 40.34% win rate, USD -43.11 net profit, native profit factor 0.562, 86.80% relative equity drawdown, and 8.14 trades per complete overnight window. None of 14 complete windows met all targets.

The candidate failed every advancement gate except basic runtime safety. It did not reach 140 trades, positive net expectancy, profit factor 1.10, or drawdown at or below 20%. The v19 branch is terminated without parameter tuning or holdout testing.

## Pipeline evidence

Both candidates compiled with zero errors and zero warnings. v19 self-tests passed 13 checks. The local tester confirmed 200 ms execution delay. The runner now verifies build-manifest hashes before copying a binary, follows MT5 relaunches by exact lab executable path, removes only exact same-run artifacts, rejects stale reports, and rejects reports with zero bars or unavailable history.

## Next research requirement

Another hand-tuned EA revision is not justified by these results. The next candidate should begin with a reusable development-data export and feature-analysis pipeline, then predeclare one simple mechanism before generating a new EA. This reduces blind iteration and makes overfitting easier to detect.
