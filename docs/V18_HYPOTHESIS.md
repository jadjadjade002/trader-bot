# QuantumTitan v18 research hypothesis

v18 is a separate candidate. It does not modify v17 and it is not deployed.

The hypothesis is that a completed M1 candle which sweeps a recent local high
or low and then reclaims it can offer a better entry than the mixed v17 signal.
The candidate rejects large shock candles, rejects M5 ADX above 35, requires a
directional M5 EMA relationship, and uses the sweep candle for a structural
stop. It permits only one XAUUSD position at 0.01 lot and has no grid and no
RiskGuardian.

The development configuration uses broker time 18:00 to 02:00, an 8 minute
maximum holding time, a 0.75 reward to risk target, and a 0.70R break-even
threshold. These values are a fixed research hypothesis, not optimized against
holdout data.

The v18 source has been created and its PowerShell scripts parse successfully.
MetaEditor compilation is still pending because the local execution quota was
exhausted during this run. No performance result is valid until the compiler
self-tests pass and the isolated real-tick development test completes.
