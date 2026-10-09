# Research Candidate R1 native outcome

Not a V25 release. No deployment performed.

Historical qualification: **False**. Promotion: **False**.
Ten complete calendar months:2025-12-01 to2026-10-01 exclusive, broker clock.
May-September previously inspected. Historical confirmation is not genuinely unseen OOS.

## V24 baseline and candidate

| Metric | Frozen V24 | Rejected descriptive candidate |
| --- | ---: | ---: |
| trades | 3768 | 2490 |
| wins | 1242 | 749 |
| losses | 2526 | 1741 |
| win_rate_pct | 32.96 | 30.08 |
| net | 130.0 | 547.26 |
| net_profit_factor | 1.0096 | 1.0457 |
| native_equity_dd_pct | 5.71 | 6.16 |
| commission | 0.0 | 0.0 |
| swap | -3.39 | -3.36 |
| fee | 0.0 | 0.0 |

Structural capital$10,000, fixed0.01lot, leverage1:200, real ticks,200ms delay. These results are not a prediction for$70 or for XM.
Deal profit already includes bid/ask fill economics. Explicit charges are separate, do not subtract spread twice.

## Monthly net USD

| Broker month | V24 | Candidate |
| --- | ---: | ---: |
| 2025-12 | -181.67 | 39.93 |
| 2026-01 | 373.53 | 560.17 |
| 2026-02 | -277.23 | -31.52 |
| 2026-03 | 462.55 | 525.96 |
| 2026-04 | -81.95 | -101.44 |
| 2026-05 | -211.46 | -184.69 |
| 2026-06 | -156.70 | -20.99 |
| 2026-07 | 69.16 | -31.36 |
| 2026-08 | 53.03 | -203.15 |
| 2026-09 | 80.74 | -5.65 |

## Development and selection

- continuation: 36 audited native configs. Development max net808.41USD.
- reclaim: 36 audited native configs. Development max net567.39USD.
- breakout: 36 audited native configs. Development max net388.91USD.
- Validation candidates: 0.
- Validation qualified: 0.
- Native baseline parity: {'passed': True, 'native_rows': 15072, 'metrics': ['Total Net Profit', 'Gross Profit', 'Gross Loss', 'Total Trades', 'Ticks', 'Bars', 'History Quality', 'Equity Drawdown Maximal', 'Balance Drawdown Maximal'], 'includes_2025': True}.

No development/validation-qualified candidate
Whole-period replay is a development-only descriptive maximum. It failed the qualification path and must not become a release.
```json
{
  "InpStopLossATRMul": 2.0,
  "InpTakeProfitRRMul": 3.0,
  "InpEntryStrength": 2
}
```

## Additional-cost stress

- Baseline: {'0.2': -623.6, '0.5': -1754.0}
- Candidate: {'0.2': 49.26, '0.5': -697.74}
Hypothetical extra0.20/0.50USD per completed0.01lot position. Fixed-trade accounting only, not native spread/timing simulation.

## Separate robustness screen

```json
{
  "checks": {
    "frozen_historical_screen": false,
    "extra_020_cost_net_positive": false,
    "delay500_net_positive": false,
    "delay500_pf_at_least_110": false,
    "capital70_net_positive": false,
    "capital70_no_stopout": false
  },
  "historically_robust": false,
  "independent_review_required": true,
  "genuinely_unseen_oos": false,
  "prospective_confirmation": "NOT_ESTABLISHED",
  "promotion": false,
  "reasons": [
    "frozen_historical_screen",
    "extra_020_cost_net_positive",
    "delay500_net_positive",
    "delay500_pf_at_least_110",
    "capital70_net_positive",
    "capital70_no_stopout"
  ]
}
```

## Evidence limits

Monthly observations are EA callbacks. Execution delay can skip callbacks, so callback counts are not raw tick counts. All ten months and their edges checked. Interior market-gap-free history is not independently proven.
Native real-tick quality, journal errors, monthly cache/source/binary/runtime hashes and ordered baseline economics audited separately. Static/Python tests do not establish strategy profitability.
Source evidence: reports/v25_research_20261007/r1_b_complete.json
