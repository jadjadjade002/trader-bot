# v21 research protocol: prospective Velocity whipsaw gate

## Status

Research only. v21 is not an EA, does not send orders, and changes nothing in v16. It uses the existing observed-only Forward Collector run `FWD_20260909_4W` as its acquisition layer. No v16 account, terminal profile, or live configuration is to be touched for this study.

The historical v17-v20 and R1-R4 results motivate the question but are excluded from estimation and validation. In particular, this study must not use any data before 2026-09-09, including the v17 holdout ending 2026-09-08.

## Frozen hypothesis

Velocity full-stop losses may reduce when a low-efficiency M1 path identifies a near-term whipsaw regime. Apex is excluded because its observed sample is too small for a redesign.

For every fixed eligible probe, let `t` be its completed M1 bar. Calculate `path20 = sum(abs(close[k] - close[k-1]), k=t-19..t)` and `displacement20 = abs(close[t] - close[t-20])`. The sole frozen feature is `efficiency20 = displacement20 / path20`. A zero path, missing bar, nonconsecutive history, or non-OK quality flag makes the probe unavailable. The research gate vetoes when `efficiency20 <= 0.25`.

The delayed label uses only the next three completed bars: `forward_path3 = sum(abs(close[t+j] - close[t+j-1]), j=1..3)`, `forward_efficiency3 = abs(close[t+3] - close[t]) / forward_path3`, and `whipsaw3 = forward_efficiency3 <= 0.25 and forward_path3 >= 0.25 * ATR14[t]`. A probe is sampled every four minutes from 18:00 through 01:56 broker time. These feature, label, cadence, and thresholds are fixed prospective choices. There are no parameter sweeps, session filters, subgroups, or replacement rules.

## Acquisition and integrity lock

The collector observes only completed M1 bars, never backfills history, and ends at broker time `2026-10-07T15:00:00`. Run the local audit before any outcome work:

```powershell
python research/v21_dataset_audit.py <collector-data-directory> --output research/v21_acquisition_manifest.json
```

The audit rejects wrong identity/schema, data outside the sealed window, malformed quotes/OHLC, duplicate or unordered timestamps, and records a content hash, observed gaps, and flags. A failed audit makes the study inconclusive until the cause is documented. It must not be repaired by importing historical bars.

## Shadow ledgers

After the outcome-masked operational shakedown, freeze this protocol, source/configuration hashes, and the acquisition manifest. The sealed analyzer creates causal features and delayed labels only. It does not simulate orders or make any profitability claim. A future, separately authorized execution study would need independent baseline and candidate ledgers because deleting rejected baseline trades changes later eligibility.

## Decision plan

The research run requires at least 1,000 probes over 15 broker-session dates. Veto coverage must be 10% to 40%, vetoed whipsaw prevalence at least 1.25 times kept prevalence, absolute separation at least five percentage points, positive separation in at least three of four chronological weekly blocks, and no session contributing more than 20% of vetoed whipsaw labels. Every integrity check must pass.

A failed gate fails v21. Insufficient coverage or integrity is inconclusive. A pass permits only a separately authorized execution experiment on another untouched stream. It never authorizes automatic deployment.
