# R4 validation and historical-search stop

## Decision

R4 M1 EMA State Transition failed its frozen strong gates. It is abandoned and the historical strategy-family search is stopped. The partially favorable nominal result cannot justify v21 because the full protocol did not pass.

## Data and verification

The isolated real-tick exporter produced 109,681 ordered XAUUSD M1 bars from 2025-08-11 through 2025-11-28, consistent with the requested November 30 weekend end. Eight focused R4 tests passed.

## Results

Nominal training counts were 28, 39, 49, and 51. Fold one failed the required minimum of 35 and its validation stayed closed. The other three validation folds produced 22 trades and USD 12.35 proxy net, 29 trades and USD 1.01, and 18 trades and USD 2.37. All three opened nominal folds were positive.

The opened nominal stream contained 69 trades, USD 15.73 proxy net, profit factor 1.452, 14.92% drawdown, and positive expectancy after twice observed spread. However, the protocol required all four training guards, 70 trades, 10 trades in every fold, four profitable validation folds, and daily t-statistic at least 2.50. Its daily t-statistic was only 1.014.

Robustness also failed. EMA 5/20 lost USD 0.76 with profit factor 0.987. EMA 8/32 produced only 41 trades, below the required 50, and did not have three profitable validation folds.

## Required next phase

R4 may not be loosened, promoted, inverted, or rerun on exposed windows. No further historical family may be introduced on the periods used by R1 through R4. The next evidence must come from execution/data-quality diagnostics and genuinely future untouched forward collection. Version 16 on the VM remains unchanged, and no R17–R20 or research candidate is eligible for deployment.
