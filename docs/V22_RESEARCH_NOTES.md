# V22 Candidate Research Notes

**Status: Candidate only — not approved for live/demo execution.**

## Lessons from V17 and V21.67

- V17: development and holdout both failed economically. The signal produced
  many trades but did not overcome spread, execution drag, and adverse movement:
  development ended near 59.6% wins with negative net PnL and PF below 1.0;
  holdout ended near 58.3% wins with negative net PnL and PF below 1.0. The
  lesson is that raw win rate is not enough when average loss and trading cost
  dominate average win.
- V21.67: 40 trades, 50% wins, net -$53.51, 106.80% relative equity drawdown;
  fatal gap loss showed 10-minute hold and broker stop cannot guarantee exit when
  market has no executable quote. No threshold tuning or deployment allowed from
  this exposed test.

## Goals for V22 candidate

Ideas that might reduce risk and overtrading without retuning the frozen V21
feature/threshold/label/cadence:

1. **Gap-aware probe eligibility**
   - Skip probes where the 20-bar path crosses a known gap (gap_count recorded
     but not repaired — market closures create legitimate gaps).
   - Document gaps per session; require probes to be contiguous within the
     session window.

2. **Session contraction**
   - Only count bars within the 18:00–01:56 window toward the 15-session minimum.
   - Bars outside the window do not extend the session count.

3. **Overtrading guard**
   - Maximum consecutive kept (non-vetoed) probes before a mandatory pause.
   - If kept_whipsaw_rate exceeds a threshold for N consecutive sessions, flag
     for review (separate from the observational gates).
   - Any future execution candidate should prove expected value after spread and
     slippage, not just label separation.

4. **Concentration monitoring**
   - Track vetoed-label session concentration in real time.
   - If concentration approaches 20% limit, document and consider pausing.

5. **Label efficiency review**
   - Verify that whipsaw3 >= 1.25x kept_rate and absolute separation >= 5pp
     hold across rolling 4-week windows before committing to a full 15-session
     run.

## V22 next steps (conditional)

- V22 research proceeds only after V21 achieves a PASS on all observational gates.
- Any V22 code changes must not touch V16 account or terminal.
- V22 is a separately authorized experiment on a separate stream.

*These notes are for offline planning only. No V22 EA or strategy will be deployed
without explicit authorization.*
