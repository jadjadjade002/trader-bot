# Capital-70 preparation handoff

Date: 2026-10-08, Asia/Bangkok. R9, R10 and R11 native USD70 experiments completed.
Status: `R11_FAILED_R12_STRUCTURAL_POLICY_IN_PREPARATION`. No V25 qualification or deployment.

## Current continuation

User manually authenticated research demo113802049. Normal research-only close
freed the isolated tester lab. Protected V24 remained open and received no input.
Root ran prefix `r9_70_a`: production70, mode0 baseline, two development arms,
and two descriptive ten-month arms. All six runs have accepted native evidence.
Production/mode0 parity passed. Both development arms failed frozen gates, so
no validation, confirmation, lock, V25 naming or deployment occurred.

Evidence: `reports/v25_research_20261008_capital70/r9_70_a_complete.json` and
its six run directories. These are retrospective backtests, not demo-account
realized PnL or future-profit evidence. Independent review and event attribution
are recorded separately. Earlier preparation/blocking notes below are historical.

Focused suite after resume-lock chronology hardening: 210 passed, 13 subtests
passed. Timestamp-aware selection lock must strictly predate the actual
confirmation started.json, including retry run identity. Current fresh run did
not reach confirmation and its already-imported runner was unaffected.

R10 single fixed2.5% current-equity planned-stop veto completed, prefix
`r10_70_a`. Actual native source/binary and USD70/1:500 settings pinned; mode0
full10m and vetoOFF development both matched their accepted controls exactly.
VetoON development and descriptive full10m: 3 positions, 1 win/2 losses,
net +$1.05, PF1.2983, native equityDD5.91%, final balance$71.05. Only December
had fills; later months had none. Development failed frozen N>=150 gate.
No validation, confirmation, selection lock, qualification or deployment.
Full-period raw/diagnostic audit: 286859 exact 1:1 rows, 9227 valid native
risk calculations, 9224 vetoes, 3 order attempts, zero calculation failures,
margin blocks or unresolved serialized threshold ambiguities. +$0.20 sensitivity
leaves+$0.45, +$0.50 leaves-$0.45. These are accounting sensitivities, not native
spread stress or future-profit forecasts. Three positions cannot establish edge.

Preserved interruption: `r10_70_a_wrapper_interruption.json`. Native development
ledger completed before the offline stop auditor rejected one ideal-Decimal
reconstruction. Exact original MQL binary64 operation order reproduced actual
SL4226.10 rather than Decimal4226.09. Narrow auditor fix plus BUY/SELL regressions
and independent offline revalidation resolved it. Equity2dp/cap4dp reporting
rounding was also modeled explicitly. No EA, outcome or strategy gate changed.
Resume reused all three accepted native records and ran only the remaining
descriptive full10m. All final four risk audits passed. Focused suite280 tests
and13 subtests passed; not the full repository suite.

R11 one-bar persistence completed, prefix `r11_70_a`. All four saved native
records passed root and independent revalidation of actual capital/leverage,
runtime/cache/source/binary/settings, exact19 fixtures, ordered owned deals,
cash/net/fees, and per-bar pending lifecycle. Mode0 full10m matched USD70 V24
exactly (392 native ordered rows); delayOFF development matched R9 hold60
exactly (224 rows). DelayON dev/full:125 positions,34 wins,91 losses, net-$59.53,
PF0.8555, native equityDD90.29%, final balance$10.47. All125 fills December2025;
later nine months zero fills, not nine successful tested trading months.
Full audit:286859 joined rows,7798 armed=125 fills+7673 expiries, no censoring.
Expiries:6836 margin blocks,788 EMA9 close,46 trend mismatch,3 skipped bars.
BUY68 net+$34.13, SELL57 net-$93.66; these are descriptive, not paired effects
or a justification for a selected BUY-only bot. Additional$0.20/position leaves
-$84.53. Development FAILED, no validation/lock/confirmation or deployment.
See `docs/CAPITAL70_R11_REVIEW_20261008.md` and attribution report for details.

Next bounded research preregistered in `docs/CAPITAL70_R12_PROTOCOL_20261008.md`:
one symmetric closed-breakout/retest plus natural-invalidation structural stop
policy, fixed2.5% native planned cash-risk cap. This is a disclosed coupled policy,
not another unbounded ATR/TP/side search. Current-spread translation is required
for SELL Ask-trigger stops on Bid candles. New ON geometry replaces150-point
ATR floor; OFF remains exact parent parity. Compile, independent source/adapter
review, native fixtures and raw/diagnostic structural auditing precede launch.
All new tests stay USD70/1:500; existing desktop V24 remains untouched. R11
attribution's advisory extension filter is not selected or run. Root instead
chose this separately preregistered capital-feasibility mechanism study.
Failure remains failure, no V25 label or automatic deployment.

## Completed in this continuation

1. User-directed new capital profile: every new native run USD70 / leverage1:500.
   Old USD10,000/1:200 evidence and signatures remain unchanged. The backend now
   records new leverage in signatures, propagates it through retries, writes the
   requested native INI and verifies actual native HTML/spec leverage and deposit.
2. `research/run_candidate_r9_capital70.py`: bounded hold60/90 continuation
   contrast, V24 production/mode0 capital70 parity first, development then
   validation then durable lock before confirmation. No reselection, no deployment.
   Independent review remains required even if all mocked or actual screens pass.
3. `tests/test_candidate_capital70.py`: rejects leverage/capital drift, reuse of
   1:200 evidence, changed actual INI/report/settings, redeposit, hidden stopout,
   failed parity and invalid identity. Controls-first and lock ordering covered.
4. Finished the previously pending read-only R8 event-level attribution. Actual
   report `reports/v25_research_20261008_postupdate/r8_b_attribution.json` labels
   itself `ATTRIBUTION_ONLY_NOT_RELEASE_QUALIFICATION`. Three factor-arm total
   net deltas versus off/off: -427.24, -489.35, -1037.47 USD. Exact paired entries
   have zero exit-economic delta. All remaining differences reconcile to actual
   unmatched entries and changed occupancy. No losses removed or saved-loss
   counterfactual claimed. Updated `docs/CANDIDATE_R8_RESULTS_r8_b.md` accordingly.
5. Pinned preflight passed: production, immutable R1, reviewed R1 reporting
   clone and R8 parity binaries/sources unchanged. Current runtime and complete
   ten-month cache exactly match the accepted postupdate reference.

## Verification

Focused suite: **205 passed, 13 subtests passed**, 1.69 seconds. Includes capital70,
R9 adapter, native-login signature compatibility, R8 runner/analysis, reviewed
native end-accounting and R1 runner tests. This is not a full repository suite or
new native profit evidence. Python compile checks passed for changed modules.

Default pytest temporary root failed in the restricted sandbox. A fresh unique
workspace-local basetemp resolved it. Final suite above passed. An early new mock
fixture used PF1.10 as a supposed failed confirmation, but 1.10 is the frozen
inclusive pass threshold. Corrected the mock to PF1.00, not the production gate.

## Isolation and blocking condition

No input, account switch, EA replacement, Algo Trading change, restart or close
was performed on protected existing V24:
`C:/Program Files/MetaTrader 5/terminal64.exe`, account10013053330, XAUUSD M1.
Production V24 source/binary hashes remain the frozen baseline hashes.

Read-only window selection identified the separate research executable
`D:/project/trader-bot/.mt5-v23-tuning.local/terminal64.exe`. Accessibility shows
its Login dialog for research account113802049 / MetaQuotes-Demo. Password entry
is left to the user under the computer-use skill. No auth fields were edited,
credentials read/extracted or security changes attempted. An asynchronous request
asked the user to log into this research window without sending the password.

Native process-idle guard must remain active. Once authenticated, observe the
research terminal again, ensure no research positions/active tester, then close
only this returned research window normally so CLI tester can lease the lab.
Do not kill or close the protected V24 process. Do not claim login from existence
of Config/accounts.dat alone.

Three existing Luna agents remain quota-blocked until17:16 Bangkok. No fresh
independent-agent review is claimed. Antigravity bridge advisory timed out after
50 seconds, no response and no successful debate claimed. Main completed the
preparation and checks above without waiting for those services.

## Next actual action after user login

Review `docs/CAPITAL70_RESEARCH_PROTOCOL_20261008.md`. Main-only native command:

```powershell
python -m research.run_candidate_r9_capital70 --tester-login 113802049 --prefix r9_70_a --activate
```

If the user authenticated a different research demo, use that confirmed research
login, never the protected V24 account. Sandbox may require approval for the
read-only process-identity check and launching this isolated installed executable.
Do not bypass denied access. No account-password parameter is accepted here.

Persist failed native runs untouched. If a broker stopout uses unexpected system
deal magic, do not relax foreign-deal rejection blindly. Reconcile exact owned
position, native report, broker-close reason, journal and cash before interpreting
capital survival. No USD70 net, winrate or profit projection exists yet.
