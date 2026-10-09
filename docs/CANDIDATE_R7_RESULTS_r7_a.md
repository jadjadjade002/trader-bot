# R7 actual results, no V25

Native complete manifest: `reports/v25_research_20261008_postupdate/r7_a_complete.json`. Independently re-audited ledger attribution: `r7_a_attribution.json` in the same root. Ten accepted native runs,31 actual MQL fixtures per run. V24 mode0 and both R4 TP1 controls reproduced exact ordered economics under build6246 and identical monthly cache records.

| Development cell | Positions | Net USD | Net PF | Win rate | Eligible |
| --- | --- | --- | --- | --- | --- |
| P0 TP0.5R | 354 | -33.83 | 0.9461 | 63.28% | No |
| P0 TP0.6R | 353 | 25.08 | 1.0378 | 61.47% | No |
| P1 TP0.5R | 156 | 54.17 | 1.2292 | 67.95% | Yes |
| P1 TP0.6R | 156 | 60.96 | 1.2273 | 64.10% | Yes |

Validation P1/0.5R:28 positions,$8.51,PF1.2237. P1/0.6R:28 positions,$17.78,PF1.4674. Both fail the40-position floor. No qualified selection lock or confirmation. Descriptive full-period selection was based on development only.

P1/0.6R descriptive ten months:202 positions,$73.61,PF1.2128,WR64.36%,native equity DD0.34%,six positive months. Extra$0.20 accounting stress=$33.21, extra$0.50=-$27.39. Buy114 net-$6.81, sell88 net$80.42. Do not select sell-only after this inspection. $70 and500 ms native stresses were not run for this unqualified candidate. These are fixed0.01-lot structural$10,000/1:200 tests, not actual$70/1:500 performance or brokerXM results.

Monthly net: Dec-2.80, Jan32.06, Feb45.68, Mar-17.45, Apr7.15, May-3.68, Jun10.73, Jul7.05, Aug0.11, Sep-5.24. Native exits:72 SL positions net-$345.88,130 TP positions net$419.49. Whole-period net below V24$130.00 and fewer than7 positive months independently fail existing gates.

## Why more winning trades did not improve development profit

P1 pairs exactly156 entries against TP1, with no unmatched entries. At TP0.6,19 original SL positions became TP, improving their combined net by$143.31. But81 original winners collected less, losing$181.17 of payout. Total development change=-$37.86. At TP0.5,25 SL-to-TP changes add$180.66, but81 reduced winners lose$225.31, total-$44.65. Every remaining loss retained.

P0 pairs351 original entries. TP0.5 adds3 unmatched new entries, TP0.6 adds2. Total deltas include these occupancy changes: -$88.68 and-$29.77 respectively. No counterfactual profit inferred from sampled MFE.

## Actual whole-period paired audit

Main independently repeated the full same-cache audit after Luna attribution. Fresh R5 `r5_d_descriptive10m` is the P1/A0 TP1 comparator. Its27 fixtures, exact source/binary/normalized UTF16 SET/signature, actual HTML, one cash deposit,202-position ledger, spec final balance and all raw ResultDeal event joins reconcile. R7's corresponding31-fixture evidence reconciles identically. Runtime and all ten monthly cache records match. All202 executed entries pair exactly, no unmatched entries.

R5 net-$2.68 versus R7$73.61, total improvement$76.29. Native transitions:72 SL-to-SL unchanged,$0 delta.24 SL-to-TP positions add$309.74.106 TP-to-TP positions lose$233.45 of payout. These are actual replay outcomes, not inferred MFE.

The named short has exactly the same opening in both runs: Sep1 22:53:00.238,0.01lot,sell4327.48. TP1 exited Sep2 01:00:00.037 at4469.17,SL reason4,net-$141.74. TP0.6 exited Sep1 22:58:52.358 at4325.11,TP reason5,net$2.37. This single pair contributes$144.11,188.90% of the total improvement. Other201 paired trades change net by-$67.82. This is attribution, not loss removal or adjusted strategy performance.

Thus aggregate improvement does not establish a more accurate entry signal. The uniform smaller target happened to remove exposure to this historical quote-gap event. It does not prove future closure protection, feed corruption, or broker-session applicability. Actual losses remain in both native totals. The SET signature validates normalized logical UTF16 text with LF, not a claim that Windows CRLF file bytes match that signature.

## Decision

Stop further target sweeps here. R7 contains genuine positive historical aggregate evidence for one candidate, but not frozen release qualification, consistency, operating-capital proof or future-profit assurance. Keep research name R7. No VM/account trading changes or deployment.
