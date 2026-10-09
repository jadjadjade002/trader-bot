# Research Candidate R2 native outcome

Not a V25 release. No deployment performed.

Historical qualification: **False**. Promotion: **False**.
Ten complete calendar months:2025-12-01 to2026-10-01 exclusive, broker clock.
May-September previously inspected. Historical confirmation is not genuinely unseen OOS.

## V24 baseline and candidate

| Metric | Frozen V24 | Rejected descriptive candidate |
| --- | ---: | ---: |
| trades | 3768 | 2434 |
| wins | 1242 | 800 |
| losses | 2526 | 1634 |
| win_rate_pct | 32.96 | 32.87 |
| net | 130.0 | 185.09 |
| net_profit_factor | 1.0096 | 1.0215 |
| native_equity_dd_pct | 5.71 | 5.49 |
| commission | 0.0 | 0.0 |
| swap | -3.39 | -2.31 |
| fee | 0.0 | 0.0 |

Structural capital$10,000, fixed0.01lot, leverage1:200, real ticks,200ms delay. These results are not a prediction for$70 or for XM.
Deal profit already includes bid/ask fill economics. Explicit charges are separate, do not subtract spread twice.

## Monthly net USD

| Broker month | V24 | Candidate |
| --- | ---: | ---: |
| 2025-12 | -181.67 | -21.49 |
| 2026-01 | 373.53 | 228.36 |
| 2026-02 | -277.23 | 77.42 |
| 2026-03 | 462.55 | 368.51 |
| 2026-04 | -81.95 | -175.62 |
| 2026-05 | -211.46 | -303.27 |
| 2026-06 | -156.70 | 121.14 |
| 2026-07 | 69.16 | -48.69 |
| 2026-08 | 53.03 | 27.70 |
| 2026-09 | 80.74 | -88.97 |

## Development and selection

Fixed SL1.5ATR/TP2R/hold60/BEoff. 10 entry configurations, not an exit optimizer.
- deeper_pullback preset0: net81.88, PF1.0122, positions1812, DD4.51%, eligible=False.
- deeper_pullback preset1: net173.91, PF1.0264, positions1776, DD4.75%, eligible=False.
- compression preset0: net-208.46, PF0.9084, positions562, DD3.25%, eligible=False.
- compression preset1: net-73.63, PF0.9646, positions526, DD2.44%, eligible=False.
- range_reversal preset0: net-86.97, PF0.6794, positions75, DD1.34%, eligible=False.
- range_reversal preset1: net-66.91, PF0.6858, positions57, DD1.02%, eligible=False.
- break_retest preset0: net-3.56, PF0.9836, positions59, DD0.63%, eligible=False.
- break_retest preset1: net13.15, PF1.0656, positions56, DD0.58%, eligible=False.
- exhaustion preset0: net41.97, PF1.0369, positions339, DD1.28%, eligible=False.
- exhaustion preset1: net7.61, PF1.0142, positions156, DD0.95%, eligible=False.
- Validation candidates: 0.
- Validation qualified: 0.
- Native baseline parity: {'passed': True, 'native_rows': 15072, 'metrics': ['Total Net Profit', 'Gross Profit', 'Gross Loss', 'Total Trades', 'Ticks', 'Bars', 'History Quality', 'Equity Drawdown Maximal', 'Balance Drawdown Maximal'], 'includes_2025': True}.

No development/validation-qualified candidate
Whole-period replay is a development-only descriptive maximum. It failed the qualification path and must not become a release.
```json
{
  "InpEntryStrength": 1
}
```

## Additional-cost stress

- Baseline: {'0.2': -623.6, '0.5': -1754.0}
- Candidate: {'0.2': -301.71, '0.5': -1031.91}
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
Source evidence: reports/v25_research_20261007/r2_a_complete.json
