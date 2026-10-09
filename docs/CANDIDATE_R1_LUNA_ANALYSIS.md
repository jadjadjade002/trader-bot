# R1 development readout

Scope: accepted native continuation, reclaim, and breakout optimizer results, development window 2025-12-01 through 2026-06-01 (Dec 2025–May 2026). Historical later periods are excluded from this analysis. Accepted means evidence record reconciled; no result establishes a qualifying or promotable configuration.

## Evidence

Primary sources: accepted native development records `reports/v25_research_20261007/runs/r1_b_dev_continuation/accepted.json`, `reports/v25_research_20261007/runs/r1_b_dev_reclaim/accepted.json`, and `reports/v25_research_20261007/runs/r1_b_dev_breakout/accepted.json` (all Dec–May window). The three records contain 108 configurations total, six monthly observations per pass, verified tick-cache hashes, no terminal cache-read warnings, and reconciliation of all 36 rows per family to native XML. Protocol context: `docs/V25_RESEARCH_PROTOCOL_20261007.md`.

- The continuation grid contains 36 configurations: SL ATR 1.0/1.5/2.0 × TP R 1.0/1.5/2.0/3.0 × entry strength 0/1/2. BE is off. All configurations show six monthly tick observations from December through May, with first and last ticks within the protocol's monthly edge allowance.
- 10/36 configurations have positive development net. None meets the protocol's development gate of net > 0, net PF ≥ 1.20, and at least 150 positions. Every configuration has at least 1,797 positions, so PF is the failing gate for positive rows.
- Best raw net is +$808.41 at SL 2.0 ATR, TP 3R, strength 2: PF 1.09, 1,797 positions, equity DD 4.42%. This is an unqualified development result, not a selected candidate.
- At TP 1R, all nine configurations lose; average net is -$850.09. TP 2R has four positive rows and average net -$229.99. TP 3R has five positive rows and average net -$33.14. Wider targets were less weak in this grid, but no TP group meets qualification.
- Strength 2 has only 2/12 positive rows and lowest mean net (-$461.36) of the three strengths; its high raw winner is isolated. At TP 3R, positives increase with stop width: SL1.0 0/3 (mean -$511.56), SL1.5 2/3 (mean +$30.77), SL2.0 3/3 (mean +$381.36). Within SL 2.0 / TP 3R, net is +$238.76 / +$96.92 / +$808.41 at strength 0/1/2; PF is 1.02 / 1.01 / 1.09, positions are 2,013 / 1,931 / 1,797, and DD is 7.64% / 8.14% / 4.42%. At SL 1.5 / TP 3R / strength 2, net falls to -$44.66 (PF 0.9945; DD 5.27%). This neighborhood is mixed; raw-best ranking alone overstates stability.
- No directional or market-regime breakdown exists in this optimization CSV. Coverage records tick observation counts and monthly edges, not trade attribution. Thus this grid cannot identify whether Buy/Sell or a specific volatility/trend regime drives the losses.

## Interpretation and bounded hypotheses

1. **Continuation entries may need more payoff room.** Evidence: every TP 1R row is negative; average loss narrows at 2R and 3R, while TP 3R has the highest fraction of positive rows. This is a grid-level association, not proof that target distance caused improvement.
2. **The strictest candle preset may help only in a narrow wide-stop corner.** Evidence: strength 2 has just 2/12 positive rows and worst mean net across strengths, despite producing the top row at SL 2 / TP 3. Same TP/strength at SL1.5 is -$44.66. Evidence does not support a broad strength-2 improvement.
3. **Wider stop and target combinations look less weak, but remain below gate.** Evidence: all three SL2 / TP3 combinations are positive, while changing to SL1.5 / TP3 / strength2 drops net below zero. The corresponding PF values remain 1.01–1.09 at SL2 / TP3. Treat this as a local cluster for diagnosis, not a parameter recommendation.

## Next research direction

No continuation configuration qualifies for validation under the frozen protocol. Do not promote the raw best row or widen this completed grid after seeing its outcomes. Keep Aug–Sep confirmation outcomes out of feature choice, and label reused May–Sep history as contaminated rather than unseen.

## Reclaim development results

Accepted source: `reports/v25_research_20261007/runs/r1_b_dev_reclaim/accepted.json`; Dec 2025–May 2026 only.

- 15/36 configurations are positive; 0/36 reach the protocol gate. PF spans 0.8465–1.0640, below 1.20 throughout; all rows exceed 150 positions.
- Best configuration: SL 2 ATR / TP 3R / strength 1, net +$567.39, PF 1.0640, 1,728 positions, equity DD 4.74%.
- Its nearby TP3 rows give moderate support across stop widths at strength 1: SL1.0 +$93.10 / PF1.0144; SL1.5 +$290.07 / PF1.0376; SL2.0 +$567.39 / PF1.0640. At SL2 / TP3, strengths 0/1/2 net +$457.43 / +$567.39 / +$205.53, PF 1.0502 / 1.0640 / 1.0251, with all three positive. This is broader local consistency than a lone winning cell, but profitability remains weak and below gate.
- TP3 is strongest as a group: 7/9 positives and mean net +$209.69; TP2 has 5/9 positives and mean -$93.59. TP1.0 is 0/9 positive, mean -$753.85. Strength 2 is weaker overall: 3/12 positive and mean -$477.34, versus 6/12 and -$154.33 at strength 0, 6/12 and -$211.42 at strength 1.
- Lowest PF row: SL1 / TP1.5 / strength2, net -$1,053.95, PF 0.8465, 2,723 positions, DD 10.70%.
- Accepted optimization rows expose net, gross wins/losses, positions and DD, but no exit-reason breakdown. Therefore stop-loss versus take-profit exit attribution is unavailable here; "best exit configuration" above means the tested SL/TP/strength tuple only.

The reclaim family has a recognizable TP3 cluster, but no qualifying development candidate.

## Breakout development results

Accepted source: `reports/v25_research_20261007/runs/r1_b_dev_breakout/accepted.json`; Dec 2025–May 2026 only.

- 6/36 configurations are positive; 0/36 reach the protocol gate. PF spans 0.8647–1.0509, all below 1.20.
- Best net configuration: SL 2 ATR / TP 2R / strength 1, +$388.91, PF 1.0460, 1,762 positions, DD 5.25%. Highest PF is 1.0509; neither row qualifies.
- There is a modest local cluster at SL2 / TP2: strengths 0/1/2 all positive (+$140.53 / +$388.91 / +$197.61; PF 1.0153 / 1.0460 / 1.0269). Wider TP3 also has positives at SL2 / strengths1 and2 (+$300.97 / +$342.47), while SL1.5 / TP3 / strength1 is only +$54.55. Other TP1 and TP1.5 rows are all negative. The cluster supports a development association with wider stops and targets, while PF remains marginal.
- Lowest PF: SL1 / TP1.5 / strength1, net -$793.76, PF 0.8647, 2,411 positions, DD 9.38%.
- As with the other families, accepted optimizer rows have no exit-reason attribution.

## Cross-family read and next hypotheses

All 108 accepted development configurations are below the PF 1.20 gate. Positive counts: continuation 10/36 (max PF 1.0896), reclaim 15/36 (max PF 1.0640), breakout 6/36 (max PF 1.0509). Raw positive net or a locally consistent pocket is insufficient for promotion. Reclaim produced most positive rows; continuation produced the highest raw net; neither establishes a qualified family.

Optimizer summaries do not contain direction, trend/chop regime, breakout success/failure, or exit-reason attribution. So evidence cannot identify the "best regime" or establish BUY/SELL asymmetry. Bounded hypotheses for a separately preregistered development attribution study only: (1) the small positive pockets may be concentrated in persistent M5 trend with aligned M1 follow-through; (2) continuation and breakout losses may cluster in low-persistence chop or failed breaks; (3) the weaker result at narrow targets may reflect insufficient follow-through after entry. These are test ideas, not conclusions. Define completed-bar regime metrics and bins before examining trade outcomes; do not use Aug–Sep or descriptive 10-month results for feature choice.

This evidence does not show that the strategy has a BUY-side, SELL-side, or named-regime defect. It supports only the limited observations above. V25 remains a research label; no release or deployment conclusion follows.
