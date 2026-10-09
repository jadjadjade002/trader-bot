# R9 capital-70 independent review

Review scope: accepted artifacts under `reports/v25_research_20261008_capital70`; no terminal, account, or credential access. This is research evidence only, not a V25 qualification or deployment approval.

## Provenance and controls

- Accepted production and mode-0 baseline both used deposit USD 70, leverage `1:500`, XAUUSD M1, 100% real ticks, 2025.12.01–2026.10.01, delay 200 ms, explicit lab login `113802049`, and verified tick-cache hashes.
- Production-to-baseline native parity passed: 392 HTML rows checked, including net/gross profit/loss, trades, ticks, bars, history quality, and balance/equity drawdown. All ten month records matched.
- R9 mode-1 runs used pinned R1 reporting-control source SHA-256 `961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B` and EX5 SHA-256 `2F59FC1F06CDAFF468F137ACF650C4198CE4BDB68CC6962551CFEBDBC46535CE`. Runtime hashes and cache verification were consistent across accepted evidence.
- Independent `validate_capital_result` passed for production, baseline, both development runs, and both descriptive full-period runs. Deal-ledger accounting reconciled against accepted native reports. Stopout flag remained false; exported reports showed no native stopout.

## Outcomes

| Run | Trades | Net | PF | Equity DD | Final balance | +$0.20 cost stress | Positive months |
|---|---:|---:|---:|---:|---:|---:|---:|
| USD70 V24 production / mode-0 baseline | 98 | -$59.37 | 0.7654 | 88.11% | $10.63 | -$78.97 | 0/10 |
| Hold 60 development | 56 | -$59.30 | 0.7253 | 89.51% | $10.70 | -$70.50 | 0/6 |
| Hold 90 development | 58 | -$64.71 | 0.7180 | 94.81% | $5.29 | -$76.31 | 0/6 |
| Hold 60 descriptive full period | 56 | -$59.30 | 0.7253 | 89.51% | $10.70 | -$70.50 | 0/10 |
| Hold 90 descriptive full period | 58 | -$64.71 | 0.7180 | 94.81% | $5.29 | -$76.31 | 0/10 |

Each full-period treatment booked all losses in December 2025; subsequent monthly records were present but zero-trade/zero-net. Raw `*_raw.csv` exports recorded 9,052 unique `margin_block` rows for hold60 and 9,045 for hold90 (6,832 hold60 and 6,825 hold90 in their development windows). Uniqueness checked by `(bar, tick_msc)`. The paired `*_signals.csv` files mirror those gate rows; counts are not added twice. Journals corroborate the gate, e.g. required margin exceeded 70% of free margin. Thus “no stopout” does not mean adequate $70 margin capacity: thousands of further candidate entries were blocked.

## Decision

Hold 90 failed development; no validation, selection lock, confirmation, or promotion occurred. Both holds lost nearly the full USD 70, breached frozen PF/DD/cost screens, and suffered extensive margin gating. R9 is not qualified and must not be deployed. No threshold, treatment, or evidence filter was changed for this review.
