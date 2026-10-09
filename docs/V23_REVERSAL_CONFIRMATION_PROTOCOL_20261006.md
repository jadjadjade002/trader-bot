# V23 reversal confirmation experiment

Recorded before running this candidate on 2026-10-06. Research only.

## Hypothesis

V23 sells after an upward breakout followed by a bullish retest, and buys after a downward breakout followed by a bearish retest. A failed-breakout fade should instead require a completed candle moving back into the channel in the intended trade direction. This is a testable structural change, not a promise of positive expectancy.

Freeze one candidate, `reversal_confirmation`, with no threshold sweep:

- Sell: original breakout close above Donchian high, retest within the original 0.5 ATR tolerance, retest close strictly inside the channel and below its own open.
- Buy: original breakout close below Donchian low, retest within the original 0.5 ATR tolerance, retest close strictly inside the channel and above its own open.
- Entry: next bar's observed first bid/ask. Features use completed candles only. Spread, entry gap and active-bar OHLC do not select this candidate.

Use the frozen May-September native raw snapshots for exploratory screening. Primary endpoint is 15-minute calendar markout after quoted entry/exit spread, with broker-day bootstrap interval. Five and 60 minutes are secondary. Missing minute windows are rejected. Report every month and sample size. Require primary mean > 0, lower 95% bound > 0, >=100 matched candidates, and at least four of five monthly sums > 0 to advance to native strategy testing.

These dates have already been examined for related hypotheses, so passing does not establish out-of-sample profitability. Failure rejects this candidate without tuning it. A passing candidate needs native real-tick testing with the unchanged V23 exits, complete costs and a newly frozen untouched period before deployment. Existing close-back forward observations can still diagnose the old hypothesis but do not hold up candidate research.

## Result recorded after execution

Status: **REJECTED**. Raw candidates: 1,961. The 15-minute primary endpoint matched 1,937 continuous windows over 109 broker days. Mean midquote move +0.1119411461, quoted spread drag 0.2745740836, after-spread mean -0.1626329375 XAUUSD quote units per signal. Positive markouts: 49.6644%. Day-block 95% mean interval: [-0.4584106305, +0.1412574553]. These are price changes, not account dollars or native trade win rate.

| Horizon | Matched | Mean after quoted spread | Positive markouts |
|---|---:|---:|---:|
| 5 minutes | 1,953 | -0.1943369176 | 46.8510% |
| 15 minutes | 1,937 | -0.1626329375 | 49.6644% |
| 60 minutes | 1,871 | -0.3695189738 | 50.1871% |

Primary monthly sums: May +85.57, June -33.90, July -157.81, August -187.04, September -21.84. Only 1/5 months positive. The raw sum of overlapping signal markouts is not a portfolio equity curve.

All 1,961 candidate entries were already present in the 1,963-entry old close-back set with identical trade direction. The reversal requirement removed two entries and created none. Therefore this is practically the same historical entry set, not an independent improved model.

Reproduction from repository root:

```powershell
python -m research.screen_v23_reversal_confirmation reports/v23_backtest_20261004/runs/fade_10000/fade_10000_raw.csv
python -m unittest tests/test_v23_signal_markouts.py tests/test_v23_v21_forward.py tests/test_v23_reversal_confirmation.py -v
```

The 11 focused tests passed. Candidate Python source SHA-256: `1822CB86E0E9B27603EEE0BBF75D3B8F5E023F15002AC87FC142342D620F3193`. No native strategy result exists for this candidate. No live EA, breaker, account or VM was changed.
