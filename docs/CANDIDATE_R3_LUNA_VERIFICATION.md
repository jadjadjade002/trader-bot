# R3 Luna verification review

Date: 2026-10-07

## Scope and evidence

Reviewed the frozen-source builder, R3 signal extension, MQL fixture source, native runner/accounting paths, and existing static tests. This is a source audit. Python static checks do not execute or compile MQL; only an accepted native run with the fixture pass marker proves those MQL assertions ran.

The R3 builder hash-pins V24, benchmark, and tuning sources (`research/build_candidate_r3.py:8-10,42-43`), preserves V24 management functions through the generated harness, and replaces the signal call only (`research/build_candidate_r3.py:74-77`). Input guard fixes the R3 exits/risk and disables BE-related variant axes (`research/candidate_r3_signal_extension.mqh:13-25`). Closed M1/M5 histories start at shift 1, verify latest-closed timestamp, contiguous bar spacing, finite OHLC, and bar shape (`research/candidate_r3_signal_extension.mqh:38-61,191-210`). Quote gates use bid/ask spread and midpoint chase; range and ATR checks are present (`:64-89`).

The three predicates implement the plan's preset-only axes and signed mirrors: blow-off (`:99-131`), internal range rejection (`:133-155`), and efficient flag (`:157-185`). Native fixture source asserts both-side mirrors, representative rejection cases, quote gates, and nonpositive/zero cases (`research/candidate_r3_native_tests.mqh:19-64`). Builder requires fixtures from `OnInit` (`research/build_candidate_r3.py:75`); runner rejects any fixture failure or missing preset-matched pass marker (`research/run_v25_native.py:350-353`). Existing accepted `r3_a_dev_1_0` records 16 fixture checks. That is evidence one native execution reached the marker, not an independent MQL compile audit.

## Parity and accounting

The runner's parity routine compares V24 and mode-0 report economics and the ordered native trade rows (`research/run_v25_native.py:419-427`). Existing integrity test checks generated harness equality and preservation of V24 signal, history, circuit-breaker, position-management, margin, and initialization functions (`tests/test_candidate_r3_integrity.py:14-20`). This is a strong source-level parity guard; the actual pass result must be read from the R3 baseline acceptance/progress record for that run.

Optimization accounting groups BUY/SELL deal legs by position ID and sums profit, commission, swap, and fee (`research/candidate_r3_signal_extension.mqh:229-253`). Standalone run accounting independently parses completed position legs, reconciles position count/net with native report and final balance, and applies extra-cost sensitivity once per completed position (`research/run_v25_native.py:374-402`; `research/analyze_v23_backtest.py:44-101`). Spread is already reflected in executable fills and is not subtracted again.

Coverage is based on EA callbacks, explicitly labeled as not every native tick and with interior gap freedom unproven (`research/run_v25_native.py:100-132`). Accepted sampled run `r3_a_dev_1_0` reports six month edges present, 85,002,335 callbacks vs 85,002,339 native ticks, and records the four skipped callbacks; do not describe this as proof of every-tick or interior gap-free coverage.

## Limits / finding

All six accepted development records were independently reconciled against their deal CSV, coverage CSV, and SET tag. Each reports 16 native fixture checks, six development months, one $10,000 deposit cash adjustment, and an `evidence_run` matching its actual artifact/run tag. The second A preset was accepted under retry tag `r3_a_dev_1_1_retry1` (original run folder has no accepted record).

| Family / preset | Positions | Net | Net PF | Callback shortfall vs native ticks |
| --- | ---: | ---: | ---: | ---: |
| A / 0 | 1 | $3.27 | undefined (no losses) | 4 |
| A / 1 | 1 | $3.27 | undefined (no losses) | 4 |
| B / 0 | 33 | -$7.65 | 0.9345 | 65 |
| B / 1 | 12 | -$25.44 | 0.5299 | 26 |
| C / 0 | 3 | $17.02 | 4.5093 | 7 |
| C / 1 | 1 | $13.61 | undefined (no losses) | 3 |

None meets the frozen screen: minimum 150 positions, PF >= 1.20, and net > $0. C / preset 0's PF 4.5093 comes from only 3 positions. All six are rejected development candidates; no validation or selection is warranted. Retain V24 unless future protocol permits fresh candidate work and genuinely fresh confirmation.

## Descriptive 10-month replay audit

Separately audited `r3_a_descriptive10m` after its accepted record appeared. It is mode 3 / preset 0, with matching `evidence_run` and SET `InpRunTag`; journal contains the required `R3_NATIVE_FIXTURES_PASS checks=16 preset=0` marker. Deal CSV independently groups to 4 completed positions / 8 deals / +$24.85, PF 6.1237, reconciles with accepted totals, and includes one $10,000 deposit cash adjustment. Ten coverage rows sum to 132,841,956 EA callbacks against 132,841,964 native ticks; interior gap-free coverage remains unproven. Four positions occurred in only three months: March, April, and June 2026.

This is the development-only maximum replayed across already inspected history, explicitly rejected with no validation. PF 6.1237 on four positions and three active months is not meaningful evidence for promotion. The run does not alter the six-config failure, qualify a candidate, or provide unseen OOS confirmation.

Tests added here are static source-contract checks only. No native tester, compiler, VM, account, credentials, or production artifact was touched by this review.
