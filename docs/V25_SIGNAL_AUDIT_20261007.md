# V25 signal audit from V24

Date: 2026-10-07. Scope: local source and existing native evidence only. No VM, account, EA, EX5, configuration, or Git mutation. Baseline V24.

## Checked conclusion

V24 is already trend-following, not inverted. Blindly changing sells into buys is unsupported. The five-month V24 baseline loses $165.23, but its sell positions contribute +$149.85 while buys contribute -$315.08. Entry quality and regime transitions need native testing. Direction alone does not establish edge.

## Evidence checked directly

Source `AegisPredator_v24.mq5`:

- Lines 60-64 create M5 EMA20, EMA50, ATR14 and M1 EMA9, EMA20.
- Lines 108-109 reject initialization when `InpFadeBreakouts=true`. The remaining inversion branch at 411-414 cannot run in an initialized V24.
- Line 405 overwrites the legacy Donchian signal with `ProposedSignal(atr)` before execution. Legacy Donchian calculation is not the active V24 entry rule.
- Lines 490-492 read closed M5 shift 1, EMA20 shift 6, and closed M1 shift 1. No active-bar trend claim.
- Lines 497-498 return BUY only when M5 EMA20 > EMA50, EMA20 > its value five completed M5 bars earlier, separation >= 0.1 M5 ATR, M1 EMA9 > EMA20, and the closed M1 candle touches EMA9 then closes above it with a bullish body.
- Lines 499-500 mirror those rules for SELL. Short local rallies can coexist with a bearish lagging M5 trend. This is possible by design, not proof of incorrect order routing.
- Line 496 rejects entry spread > 0.1 M1 ATR and midpoint distance from closed signal candle > 0.5 M1 ATR. The disabled fixed spread guard does not mean no spread protection.
- Lines 419-420 set risk distance to max(1.5 M1 ATR, 150 points) and TP to 2R. Lines 437 and 459 route BUY/SELL as sign indicates.
- Lines 212-229 use a 60-M1-bar holding cap. No BE adjustment in production V24. Lines 268-305 preserve the earlier breaker, including known gross-profit-only streak accounting and fail-open `HistorySelect` behavior. This audit does not propose or apply breaker changes.

Production binary parity evidence: `reports/v23_tuning_20261006/v24_demo_20261006_v24_parity.json`, `passed=true`. Native V24 report matches tested proposed-best run on 5,904 ordered economic rows and nine native metrics. Same 1,476 positions, 58,118,739 ticks, 143,336 bars and 100% real-tick history.

Economics source: `reports/v23_tuning_20261006/runs/complete5m_batch1_descriptive_best_proposed/complete5m_batch1_descriptive_best_proposed_deals.csv`. Grouped opening and closing deals by position ID using reviewed `research/analyze_v23_backtest.py:48-85`. Entry attempt joined by actual opening deal ticket to `_raw.csv`. All 1,476 positions joined, no missing or duplicate ticket match. Aggregate trade count and net reconciled to native HTML report.

Period: [2026-05-01, 2026-10-01), fixed lot 0.01, deposit $10,000, leverage 1:200, native real ticks, 200ms execution delay. Structural results are not a forecast for the small demo account.

### Direction and month

| Entry direction | Positions | Wins | Win rate | Net USD | Net PF |
| --- | ---: | ---: | ---: | ---: | ---: |
| BUY | 617 | 190 | 30.79% | -315.08 | 0.8237 |
| SELL | 859 | 300 | 34.92% | +149.85 | 1.0588 |
| All | 1,476 | 490 | 33.20% | -165.23 | 0.9619 |

Months use closing timestamps encoded in broker clock, not an asserted UTC conversion.

| Month | Buy count | Buy net USD | Sell count | Sell net USD | Total net USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-05 | 159 | -158.50 | 228 | -52.96 | -211.46 |
| 2026-06 | 158 | -173.22 | 307 | +16.52 | -156.70 |
| 2026-07 | 118 | +34.98 | 124 | +34.18 | +69.16 |
| 2026-08 | 107 | +17.27 | 90 | +35.76 | +53.03 |
| 2026-09 | 75 | -35.61 | 110 | +116.35 | +80.74 |

Sell-only is a research ablation, not an established fix. Selective deletion of historical buy trades does not reproduce subsequent occupancy and breaker paths.

### Exit economics and costs

| Exported reason | Positions | Net USD |
| --- | ---: | ---: |
| 4, SL | 967 | -4,298.38 |
| 5, TP | 462 | +4,073.31 |
| 3, expert close | 47 | +59.84 |

All 967 SL closes are losses because baseline BE is off. Expert close reason does not by itself distinguish time exits from forced end-of-test exits. Inspect comment/journal before claiming all 47 are time exits.

Deal profit summed -$164.29, commission $0.00, swap -$0.94, fee $0.00, net -$165.23. Deal profit already embeds spread through executable buy/sell prices. It is **not gross alpha before spread**. Exported cost fields alone cannot produce a no-spread counterfactual. Broker is MetaQuotes-Demo, not XM. An XM live recommendation would need XM symbol specifications and costs.

Mean winning position +$8.5142, mean losing position -$4.3988. Winning/losing amounts vary with ATR. Win rate by itself is insufficient.

Entry quote spread / ATR: mean 0.06995, maximum 0.1. This verifies the existing relative cost gate in the matched entry snapshots. It is not the final fill spread and does not estimate exact all-in round-trip cost.

### Local price regime attribution

`research/v25_signal_audit.py` computes prior five closed-M1-bar close delta, divides by entry ATR, then signs it by entry direction. Requires every intervening minute contiguous. Threshold +/-0.25 ATR is a fixed descriptive audit choice, not an optimized signal. No future values used. All positions classifiable in this dataset.

| Prior five-bar impulse | Positions | Net USD | Net PF |
| --- | ---: | ---: | ---: |
| Aligned with trade, >= +0.25 ATR | 798 | -130.20 | 0.9435 |
| Opposed to trade, <= -0.25 ATR | 382 | -80.69 | 0.9322 |
| Between thresholds | 296 | +45.66 | 1.0541 |

Aligned BUY: 340 positions, -$150.14. Opposed BUY: 150 positions, -$110.83. Opposed SELL: 232 positions, +$30.14. Thus buying simply because recent M1 rose cannot be called a sufficient fix. These are actual position subsets, not replayed strategies.

Exact M5 EMA values, slope, trend age, and efficiency were not exported in the existing raw ledger. Cannot independently reconstruct exact M5 transition state per losing entry without a feature replay or augmented native run.

Sampled path ledger `_paths.csv` has 1,476 matched position IDs. Of 967 SL positions, 411 reached sampled MFE >=0.5R, 191 >=1R, 138 >=1.2R, 67 >=1.5R. 107 never showed sampled positive MFE. Observation is callback sampled, not exact full tick path. Does not establish a BE counterfactual. Existing native BE trials at SL1.5/TP2 worsened full net from -$165.23 to -$319.48 at 0.8R and -$341.72 at 1.2R. Earlier BE is not presently supported.

## Hypotheses to test, not claims

Keep symmetric BUY/SELL rules, lot 0.01, same one-position policy, same costs, same breaker and same 60-bar holding cap initially. Do not stack all new filters before separate ablations.

1. **V24 pullback with fresh local-regime agreement.** Add closed M1 EMA9 slope over two bars and five-bar signed impulse >= 0 or 0.25 ATR, plus last closed M5 close on the trend side of M5 EMA20. Tests whether lagging EMA20/EMA50 authorizes a stale trend. Bounded axes: impulse {0, 0.25}, M5 slope lookback {2, 5}, fixed M5 separation 0.1 ATR. Four configs. Audit aligned subsets remain negative, so this hypothesis may fail.
2. **Trend-confirmed continuation breakout.** Same closed M5 direction and cost gate. Replace immediate EMA9 reclaim with closed M1 close beyond prior N fully closed-bar high/low in the same direction, with close margin 0 or 0.1 ATR and normalized close location >=0.6. Never fade. Bounded axes: N {10, 20}, margin {0, 0.1}. Four configs. Old unfiltered normal breakout was negative, so M5 regime and confirmation must demonstrate incremental edge.
3. **Two-stage pullback confirmation with anti-exhaustion.** After V24 closed pullback/reclaim, arm direction for at most two bars. Enter only after a later closed candle exceeds the reclaim candle high/low in trend direction. Reject close distance from M1 EMA20 beyond {0.75, 1.25} ATR. One-shot setup, expiry and cancelled trend specified before implementation. Bounded axes: max confirmation age {1, 2}, stretch {0.75, 1.25}. Four configs. Delay can reduce false reclaims or worsen entry price. Native execution resolves the tradeoff.

Run baseline plus 12 entry configs before exit tuning. For the best predeclared development-screen candidates only, vary SL ATR {1.0, 1.5, 2.0}, TP R {1.5, 2.0, 2.5}, BE {off, 1.5R} with fixed 0.05R lock and no trail. This is 18 exit configs per shortlisted entry family, not an unrestricted search. BE branch needs its own tested implementation and must not change frozen V24 baseline.

The orchestrator may choose a smaller documented grid before observing results. Do not expand post-hoc until some configuration wins. Prefer broad stable neighboring parameter values over a solitary maximum.

## Ten-month confirmation requirements

Latest ten complete calendar months on client date 2026-10-07: [2025-12-01, 2026-10-01). Actual real-tick coverage must be verified before claiming ten months. Missing history, generated replacement ticks or truncated runs block the claim.

May through September have already been inspected and selected against. They cannot become a fresh holdout merely by relabeling them. A ten-month full-period replay can verify reproducibility and breadth, not unbiased future profitability. Record every period already used during candidate selection. Earlier unseen months can give retrospective robustness evidence only after inventory confirms they were not previously used. Strongest independent confirmation remains a predeclared forward period after candidate freeze.

Require net after all costs >0, improvement over frozen V24 under identical costs and dates, adequate trades in every scored partition, stable nearby parameters, no one-month dependence, no foreign positions/cash adjustment, no capital-path concealment. Use same native real ticks and broker-specific cost stress. Report failures honestly. Never label a merely less-negative candidate profitable.

## Reproduction

Read-only command:

```powershell
python research/v25_signal_audit.py
python -m unittest tests.test_v25_signal_audit -v
```

Focused tests: six passed. Cover sign symmetry, threshold boundary, null/unknown distinction, invalid ATR, nonfinite features and unsupported directions. Native aggregate and entry joins validated by actual audit run. This is not full repository test coverage or a native test of new hypotheses.
