# R3 validation

## Decision

R3 Session-VWAP Statistical Fade passed its training-frequency guards but failed its frozen validation quality gates. It is abandoned without parameter promotion or modification. No execution EA or deployment is permitted.

## Data

The cross-year tester export was split into two isolated real-tick runs because MT5 stopped the first cross-year run at December 31. The two strict, nonoverlapping exports were merged into 106,268 ordered XAUUSD M1 bars covering 2025-12-08 through 2026-03-27. The research code produced 24,420 valid contiguous-session states. Eight focused R3 tests passed.

## Results

All nominal training guards passed with 322, 320, 316, and 367 opportunities. The four nominal validation folds produced 122 trades and USD 81.37 proxy net, 194 trades and USD -38.02, 173 trades and USD 29.68, and 154 trades and USD -54.91. Only two folds were profitable.

The concatenated nominal stream produced 643 trades, USD 18.12 proxy net, 0.0282 expectancy per trade, profit factor 1.017, and 68.91% drawdown. At 1.5 times observed spread it retained only USD 2.90 net and profit factor 1.003. The strict robustness variant lost USD 23.66 with profit factor 0.969.

R3 passed frequency, positive nominal expectancy, concentration, and stressed-spread sign. It failed profit factor 1.10, drawdown 20%, three profitable folds, and strict-variant robustness.

## Stopping rule

R3 cannot be inverted, retuned, filtered, or rerun on the exposed validation windows. It does not justify v21.
