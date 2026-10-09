# Research Candidate R4 native outcome

Not a V25 release. No deployment performed.

Historical qualification: **False**. Promotion: **False**.
Ten complete calendar months:2025-12-01 to2026-10-01 exclusive, broker clock.
May-September previously inspected. Historical confirmation is not genuinely unseen OOS.

## V24 baseline and candidate

| Metric | Frozen V24 | Rejected descriptive candidate |
| --- | ---: | ---: |
| trades | 3768 | 202 |
| wins | 1242 | 106 |
| losses | 2526 | 96 |
| win_rate_pct | 32.96 | 52.48 |
| net | 130.0 | -2.68 |
| net_profit_factor | 1.0096 | 0.9955 |
| native_equity_dd_pct | 5.71 | 1.64 |
| commission | 0.0 | 0.0 |
| swap | -3.39 | -0.05 |
| fee | 0.0 | 0.0 |

Structural capital$10,000, fixed0.01lot, leverage1:200, real ticks,200ms delay. These results are not a prediction for$70 or for XM.
Deal profit already includes bid/ask fill economics. Explicit charges are separate, do not subtract spread twice.

## Monthly net USD

| Broker month | V24 | Candidate |
| --- | ---: | ---: |
| 2025-12 | -181.67 | -31.52 |
| 2026-01 | 373.53 | 50.31 |
| 2026-02 | -277.23 | 70.57 |
| 2026-03 | 462.55 | 8.67 |
| 2026-04 | -81.95 | -5.94 |
| 2026-05 | -211.46 | 6.73 |
| 2026-06 | -156.70 | 26.18 |
| 2026-07 | 69.16 | 9.84 |
| 2026-08 | 53.03 | 12.65 |
| 2026-09 | 80.74 | -150.17 |

## Development and selection

Frozen R2 exhaustion signal. 16 bounded SL/TP configurations; hold60/BEoff unchanged.
- exhaustion_exit_ablation preset0 SL1.0ATR TP0.75R: net-55.02, PF0.8988, positions348, DD0.99%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.0ATR TP1.0R: net-17.81, PF0.9705, positions346, DD1.05%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.0ATR TP1.5R: net-19.81, PF0.9721, positions340, DD1.0%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.0ATR TP2.0R: net-27.71, PF0.9643, positions334, DD1.14%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.5ATR TP0.75R: net12.13, PF1.0159, positions351, DD1.08%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.5ATR TP1.0R: net54.85, PF1.063, positions351, DD0.89%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.5ATR TP1.5R: net54.93, PF1.0534, positions344, DD1.19%, eligible=False.
- exhaustion_exit_ablation preset0 SL1.5ATR TP2.0R: net41.97, PF1.0369, positions339, DD1.28%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.0ATR TP0.75R: net-9.83, PF0.9591, positions156, DD0.55%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.0ATR TP1.0R: net10.65, PF1.0396, positions156, DD0.45%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.0ATR TP1.5R: net18.68, PF1.0588, positions155, DD0.42%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.0ATR TP2.0R: net-24.36, PF0.934, positions154, DD0.67%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.5ATR TP0.75R: net77.27, PF1.2524, positions156, DD0.41%, eligible=True.
- exhaustion_exit_ablation preset1 SL1.5ATR TP1.0R: net98.82, PF1.2759, positions156, DD0.47%, eligible=True.
- exhaustion_exit_ablation preset1 SL1.5ATR TP1.5R: net38.71, PF1.082, positions156, DD0.85%, eligible=False.
- exhaustion_exit_ablation preset1 SL1.5ATR TP2.0R: net7.61, PF1.0142, positions156, DD0.95%, eligible=False.
- Validation candidates: 2.
- Validation qualified: 0.
- Native baseline parity: {'passed': True, 'native_rows': 15072, 'metrics': ['Total Net Profit', 'Gross Profit', 'Gross Loss', 'Total Trades', 'Ticks', 'Bars', 'History Quality', 'Equity Drawdown Maximal', 'Balance Drawdown Maximal'], 'includes_2025': True}.

## Fixed-signal exit matrix

Same signal predicate, different exit/occupancy paths. Net differences are native strategy outcomes, not matched per-trade counterfactuals.

| Preset | SL ATR | TP R | Positions | Win % | Net USD | PF | DD % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1.0 | 0.75 | 348 | 53.16 | -55.02 | 0.8988 | 0.99 |
| 0 | 1.0 | 1.0 | 346 | 47.98 | -17.81 | 0.9705 | 1.05 |
| 0 | 1.0 | 1.5 | 340 | 37.94 | -19.81 | 0.9721 | 1.0 |
| 0 | 1.0 | 2.0 | 334 | 32.04 | -27.71 | 0.9643 | 1.14 |
| 0 | 1.5 | 0.75 | 351 | 56.41 | 12.13 | 1.0159 | 1.08 |
| 0 | 1.5 | 1.0 | 351 | 49.57 | 54.85 | 1.063 | 0.89 |
| 0 | 1.5 | 1.5 | 344 | 39.83 | 54.93 | 1.0534 | 1.19 |
| 0 | 1.5 | 2.0 | 339 | 33.63 | 41.97 | 1.0369 | 1.28 |
| 1 | 1.0 | 0.75 | 156 | 55.77 | -9.83 | 0.9591 | 0.55 |
| 1 | 1.0 | 1.0 | 156 | 50.0 | 10.65 | 1.0396 | 0.45 |
| 1 | 1.0 | 1.5 | 155 | 40.65 | 18.68 | 1.0588 | 0.42 |
| 1 | 1.0 | 2.0 | 154 | 31.17 | -24.36 | 0.934 | 0.67 |
| 1 | 1.5 | 0.75 | 156 | 59.62 | 77.27 | 1.2524 | 0.41 |
| 1 | 1.5 | 1.0 | 156 | 51.92 | 98.82 | 1.2759 | 0.47 |
| 1 | 1.5 | 1.5 | 156 | 37.82 | 38.71 | 1.082 | 0.85 |
| 1 | 1.5 | 2.0 | 156 | 31.41 | 7.61 | 1.0142 | 0.95 |

### Development direction and actual exits

Reason 3=Expert, 4=SL, 5=TP, 6=stopout. Side and exit columns below are separate margins, not a side-by-exit causal table.

| Config | BUY n / net | SELL n / net | Expert n / net | SL n / net | TP n / net |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5_0_sl1p0_tp0p75 | 192 / -19.09 | 156 / -35.93 | 0 / 0.00 | 163 / -543.79 | 185 / 488.77 |
| 5_0_sl1p0_tp1p0 | 192 / 6.20 | 154 / -24.01 | 0 / 0.00 | 180 / -604.10 | 166 / 586.29 |
| 5_0_sl1p0_tp1p5 | 188 / -18.79 | 152 / -1.02 | 0 / 0.00 | 211 / -710.16 | 129 / 690.35 |
| 5_0_sl1p0_tp2p0 | 184 / -32.15 | 150 / 4.44 | 0 / 0.00 | 227 / -777.20 | 107 / 749.49 |
| 5_0_sl1p5_tp0p75 | 194 / -18.80 | 157 / 30.93 | 0 / 0.00 | 153 / -762.45 | 198 / 774.58 |
| 5_0_sl1p5_tp1p0 | 194 / -15.47 | 157 / 70.32 | 0 / 0.00 | 177 / -870.05 | 174 / 924.90 |
| 5_0_sl1p5_tp1p5 | 189 / -43.82 | 155 / 98.75 | 0 / 0.00 | 207 / -1028.20 | 137 / 1083.13 |
| 5_0_sl1p5_tp2p0 | 186 / -72.50 | 153 / 114.47 | 2 / 1.81 | 224 / -1133.19 | 113 / 1173.35 |
| 5_1_sl1p0_tp0p75 | 88 / 2.54 | 68 / -12.37 | 0 / 0.00 | 69 / -240.52 | 87 / 230.69 |
| 5_1_sl1p0_tp1p0 | 88 / 22.95 | 68 / -12.30 | 0 / 0.00 | 78 / -269.24 | 78 / 279.89 |
| 5_1_sl1p0_tp1p5 | 87 / 34.98 | 68 / -16.30 | 0 / 0.00 | 92 / -317.78 | 63 / 336.46 |
| 5_1_sl1p0_tp2p0 | 86 / 11.76 | 68 / -36.12 | 0 / 0.00 | 106 / -369.07 | 48 / 344.71 |
| 5_1_sl1p5_tp0p75 | 88 / 18.34 | 68 / 58.93 | 0 / 0.00 | 63 / -306.15 | 93 / 383.42 |
| 5_1_sl1p5_tp1p0 | 88 / 30.52 | 68 / 68.30 | 0 / 0.00 | 75 / -358.19 | 81 / 457.01 |
| 5_1_sl1p5_tp1p5 | 88 / -12.84 | 68 / 51.55 | 0 / 0.00 | 97 / -471.87 | 59 / 510.58 |
| 5_1_sl1p5_tp2p0 | 88 / -39.24 | 68 / 46.85 | 1 / 5.66 | 107 / -537.04 | 48 / 538.99 |

### Six development months for every configuration

| Config | Dec | Jan | Feb | Mar | Apr | May |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5_0_sl1p0_tp0p75 | -1.06 | -41.59 | 57.52 | -97.23 | 28.49 | -1.15 |
| 5_0_sl1p0_tp1p0 | -0.90 | -24.56 | 65.06 | -84.03 | 26.36 | 0.26 |
| 5_0_sl1p0_tp1p5 | -9.87 | -41.57 | 70.04 | -75.59 | 10.79 | 26.39 |
| 5_0_sl1p0_tp2p0 | -25.44 | -32.75 | 50.94 | -36.06 | -6.68 | 22.28 |
| 5_0_sl1p5_tp0p75 | 14.23 | -1.52 | 60.05 | -68.07 | 1.68 | 5.76 |
| 5_0_sl1p5_tp1p0 | -14.75 | 4.80 | 95.74 | -44.37 | -13.13 | 26.56 |
| 5_0_sl1p5_tp1p5 | -26.44 | 12.54 | 87.08 | -3.60 | -34.61 | 19.96 |
| 5_0_sl1p5_tp2p0 | -1.51 | -49.32 | 120.84 | 15.38 | -2.31 | -41.11 |
| 5_1_sl1p0_tp0p75 | -9.14 | -11.81 | 49.33 | -50.27 | 7.78 | 4.28 |
| 5_1_sl1p0_tp1p0 | -10.93 | -0.11 | 52.06 | -40.83 | 15.13 | -4.67 |
| 5_1_sl1p0_tp1p5 | -17.64 | 1.73 | 44.94 | -21.31 | 7.48 | 3.48 |
| 5_1_sl1p0_tp2p0 | -46.84 | -7.54 | 26.81 | 3.04 | 1.62 | -1.45 |
| 5_1_sl1p5_tp0p75 | -14.59 | 26.58 | 55.89 | -4.62 | 12.67 | 1.34 |
| 5_1_sl1p5_tp1p0 | -31.52 | 50.31 | 70.57 | 8.67 | -5.94 | 6.73 |
| 5_1_sl1p5_tp1p5 | -64.89 | 50.66 | 56.81 | 9.52 | -13.40 | 0.01 |
| 5_1_sl1p5_tp2p0 | -62.65 | 0.54 | 65.78 | 40.08 | -5.36 | -30.78 |

No development/validation-qualified candidate
Whole-period replay is a development-only descriptive maximum. It failed the qualification path and must not become a release.
```json
{
  "InpEntryStrength": 1,
  "InpStopLossATRMul": 1.5,
  "InpTakeProfitRRMul": 1.0
}
```

## Additional-cost stress

- Baseline: {'0.2': -623.6, '0.5': -1754.0}
- Candidate: {'0.2': -43.08, '0.5': -103.68}
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
  "scope": "Locked candidate only. Rejected descriptive maximum excluded.",
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
Source evidence: reports/v25_research_20261007/r4_a_complete.json
