# R10 capital-70 attribution — 2026-10-08

## Result

R10 failed frozen development sample floor and is not V25-qualified or deployable. In the 6-month development window, cash-risk veto mode produced 3 trades, net **+$1.05**, PF **1.2983**, equity max DD **5.91%**. It needed at least 150 trades; only 1 win and 2 losses occurred. The 10-month descriptive run remained exactly 3 trades, all in December 2025, then no trades through September 2026. This sparse result cannot establish a robust edge.

## Revalidated evidence

Offline `run_candidate_r10_capital70.validate_result` passed for all four saved R10 runs after the stop calculation was corrected to mirror MQL binary-double order exactly. The former failure at `2025.12.01 02:53:00` was Decimal-vs-IEEE rounding, not a source change or a relaxed price tolerance. All raw/signal rows join 1:1; native report, signatures, accepted artifacts, cash close accounting, fixtures, and risk checks passed. The audit summaries are in [`r10_70_a_attribution.json`](../reports/v25_research_20261008_capital70/r10_70_a_attribution.json).

| Run | Period | Trades / W-L | Net / PF | Equity max DD | Risk diagnostics |
|---|---|---:|---:|---:|---|
| `r10_70_a_parity` (mode 0, V24) | 10m | 98 / 30-68 | -$59.37 / 0.7654 | 88.11% | Exact production parity; final balance $10.63 |
| `r10_70_a_control_dev` (mode 1, veto off) | 6m | 56 / 14-42 | -$59.30 / 0.7253 | 89.51% | 6,832 margin blocks; final balance $10.70 |
| `r10_70_a_veto_dev` (mode 1, veto on) | 6m | 3 / 1-2 | +$1.05 / 1.2983 | 5.91% | 7,007 evaluated; 7,004 vetoes; 3 order attempts |
| `r10_70_a_descriptive10m` (mode 1, veto on) | 10m | 3 / 1-2 | +$1.05 / 1.2983 | 5.91% | 9,227 evaluated; 9,224 vetoes; 3 order attempts |

Control and veto arms share development interval and frozen mode-1 inputs; performance difference is descriptive, not proof that vetoed entries would have lost. R10 did not rerun its own full-period veto-OFF arm. The accepted R9 hold60 descriptive parent reference does exist (56 trades, -$59.30, same economic configuration), and R10 OFF development matched that parent exactly. Distinguish this existing full-period parent reference from an actual full-period R10 OFF parity test, which was not performed. The mode-0 V24 comparison is not a counterfactual for mode 1.

## What diagnostics support

Clarification: minimum stop geometry is150 points =1.50 quote-price units at
exported point0.01. This is not itself a guaranteed dollar loss. Dollar estimates
below come from actual native OrderCalcProfit diagnostics.

With $70 initial deposit, 1:500 leverage, 0.01 lot, 2 ATR stop multiplier, $1.50 minimum stop distance, and 2.5% of current equity as risk ceiling, the veto acted as a strong trade-frequency constraint. In full descriptive run, its 9,224 vetoes spanned all months: Dec 2025 838; Jan 1,212; Feb 1,423; Mar 1,533; Apr 1,092; May 906; Jun 1,199; Jul 459; Aug 286; Sep 276. Reported account-currency stop-risk estimates among vetoes ranged **$1.78–$118.15**, median **$5.84**; starting ceiling was $1.75 and later ceiling $1.7763 after three trades. These are the EA’s native `OrderCalcProfit` estimates, not estimates reconstructed from exported tick value.

All 3 admitted trades were buys in Dec 2025. Their logged ATRs were 0.7564, 0.8929, and 0.8386; native risk estimates were $1.52, $1.79, and $1.68 versus contemporaneous ceilings $1.75, $1.8643, and $1.8178. Two closed at stops for -$1.86 and -$1.66; the winner hit TP for +$4.57. One realized stop loss exceeded its logged planned cash risk by $0.07, illustrating that a planned cap is not a guaranteed maximum realized loss. No larger stop-fill exception occurred in these three trades.

Native deal accounting reported commission, swap, and fee all $0.00. Spread was embedded in executable bid/ask and deal prices; among evaluated full-period candidate events, raw spread ranged $0.00–$1.54, median $0.17. No separate spread-to-cash conversion is claimed. Veto mode had zero margin-block rows; its eligible candidate stream was cut by cash risk before orders. The six-month veto-off control had 6,832 margin blocks, while mode-0 full-period V24 had 14,299. V24’s trading and decline were concentrated in Dec 2025 (98 trades, -$59.37); there were no trades in later months after capital fell to $10.63. Veto-on likewise traded only in Dec, but because almost all later candidates exceeded the cap, not because the feed stopped: all 286,859 M1 rows were present and validated.

## Limits and disposition

The veto materially reduced exposure, but its low sample prohibits claims of robust profitable entries. R9's accepted full-period hold60 reference exists; no separate full-period R10 OFF parity test was rerun. Do not count vetoes as saved losses or imagine counterfactual fills. Native history covers 1 Dec 2025–1 Oct 2026 with 100% real ticks; this remains historical tester evidence, not unseen OOS or live/demo deployment evidence. Qualification, promotion, and V25 status remain **false**. The independent reviewer revalidated all four R10 records offline after the narrow audit-arithmetic repair and confirmed FAILED disposition. Preserve all runs and failures.
