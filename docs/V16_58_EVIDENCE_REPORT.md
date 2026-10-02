# V16.56 Loss Forensics and V16.58 Research Verdict

Date: 2026-09-22

## Live demo evidence

Account `112882967` started at `$60.00` and closed 12 V16.56 trades at `$39.32`.

- Wins: 4, total `+$1.57`
- Losses: 8, total `-$22.25`
- Net: `-$20.68`
- Win rate: `33.33%`
- Average win: `$0.39`
- Average loss: `-$2.78`
- Profit factor: `0.071`
- Break-even win rate at the observed payoff: about `87.63%`

All four winners reached roughly `+$1.56` to `+$1.88` before the EA moved SL near entry and eventually realized only `+$0.34` to `+$0.50`. All eight losses reached their initial SL.

Eleven of twelve entries came from `WICK_PULLBACK`. That setup won three and lost eight. The evidence therefore rejects both assumptions that the entry rule was already selective enough and that the profit lock was preserving meaningful reward.

## Proven code causes

1. Stage 1 was a fixed lock relative to entry, not a trail behind the best price.
2. The runtime preset disabled stage 2 and stage 3, so SL stayed near entry after larger favorable moves.
3. The old momentum state compared a regression slope with a raw price deviation and included a forming-bar value in its calculation.
4. The original wick rule accepted weak candles and used `wick OR FVG`, producing many low-quality pullbacks.
5. RiskGuardian and daily drawdown protection were disabled in the live preset. This amplified loss size but did not create the bad signal edge.

## V16.58 causal tests

All tests used XAUUSD M1, `$60` deposit, `0.01` lot, 1:500 leverage, MT5 real ticks, and 200 ms execution delay.

### Exit ablation, 2026-08-03 through 2026-08-08

| Exit policy | Trades | Win rate | Net |
|---|---:|---:|---:|
| Legacy profit lock | 11 | 27.27% | `-$11.11` |
| Delayed lock at 1R | 11 | 27.27% | `-$11.86` |
| Peak trail after 1R | 11 | 27.27% | `-$8.65` |
| No profit lock, initial SL/TP only | 11 | 27.27% | `-$0.12` |

Conclusion: the profit-lock design materially reduced payoff. Removing it almost reached break-even in this small sample, but did not repair entry quality.

### Entry tests with no profit lock

| Entry policy | Period | Trades | Win rate | Net | Verdict |
|---|---|---:|---:|---:|---|
| Wick OR FVG | Development | 40 | 35.00% | `+$4.45` | Continue once |
| Wick OR FVG | Holdout | 27 | 18.52% | `-$20.22` | Reject |
| Wick AND FVG | Development | 13 | 38.46% | `+$3.56` | Continue once |
| Wick AND FVG | Validation | 13 | 7.69% | `-$16.51` | Reject |
| EMA reclaim + KER | Development | 13 | 61.54% | `+$23.26` | Apparent in-sample edge |
| EMA reclaim + KER | Validation | 5 | 20.00% | `-$3.66` | Reject as overfit |
| Breakout then retest | Development | 36 | 25.00% | `-$12.72` | Reject |
| Breakout then retest | Validation | 25 | 12.00% | `-$23.39` | Reject |

No V16.58 policy passed validation. V16.58 is research code and must not be deployed.

## V21 forward evidence

Latest read-only VM snapshot:

- 11,499 valid M1 bars
- 11 of 15 broker sessions
- Health `HEALTHY`
- 0 malformed rows, 0 duplicate rows, 0 write errors
- 588 eligible V21 probes

The preregistered V21 whipsaw veto is currently directionally wrong:

- Vetoed whipsaw rate: `19.67%`
- Kept whipsaw rate: `20.72%`
- Separation: `-1.05 percentage points`

Acquisition remains incomplete and the hypothesis does not currently support promotion.

## Best surviving research lead

Historical R4 EMA state-transition research did not pass every original gate, but its frozen nominal EMA 6/24 rule was evaluated on the new V21 live stream without changing the formula:

- Period: 2026-09-09 through 2026-09-22
- Trades: 12
- Net proxy: `+$4.80`
- Expectancy: `+$0.40/trade`
- Profit factor: `1.91`
- Max drawdown proxy: `5.24%`
- At 2x spread stress: `+$3.18`, PF `1.54`
- Evidence days: 7

This is promising but not proof. Twelve trades are too few for deployment. Next engineering candidate should implement exact R4 execution semantics in MT5, then run real-tick development, validation, untouched holdout, and execution-stress tests.

## V16.59 MT5 implementation result

`QuantumTitan_v16_59_R4StateTransition.mq5` implements the frozen R4 EMA 6/24 rule with a three-completed-bar hold, no BE, and no trailing. Compilation completed with 0 errors and 0 warnings. Six focused contract tests pass.

| Window | Trades | Win rate | Net | PF | Max equity DD |
|---|---:|---:|---:|---:|---:|
| Development 2026-08-03 to 2026-08-21 | 22 | 63.64% | `+$7.92` | 1.66 | 13.20% |
| Validation 2026-08-24 to 2026-09-08 | 21 | 28.57% | `-$5.13` | 0.78 | 28.23% |
| Confirmation 2026-09-09 to 2026-09-18 | 10 | 50.00% | `+$2.81` | 1.49 | 5.76% |

Across all three windows: 53 trades, 47.17% wins, `+$5.60`, PF `1.14`, average win `$1.85`, average loss `-$1.45`. Aggregate results are mildly positive, but the independent validation window is negative and drawdown is too high. V16.59 is the strongest current lead, but it does not pass deployment gates.

## Safety state

The live demo terminal remains with Algo Trading disabled. V16.57 is loaded as a safety hotfix but is not enabled. No V16.58 candidate was deployed.
