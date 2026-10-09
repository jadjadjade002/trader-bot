# R10 planned original-stop cash-risk experiment

Frozen before any R10 native outcome, 2026-10-08. Research only, not V25.
R9 hold60/90 both failed at USD70, depleted equity and stopped obtaining fills
because fixed0.01 lot failed margin checks. No broker stopout occurred. This
motivates measuring planned loss against available equity, not a profitability
claim. Failed R9 evidence stays intact.

## Single hypothesis and isolation

Compare the unchanged R9 continuation P2/SL2ATR/TP3R/hold60 with a single added
planned-stop loss veto at 2.5% current equity. Fixed0.01 lot, original outward
rounded SL, unchanged TP/entry/breaker/session/spread/margin settings. No risk-cap
sweep, stop squeezing, lot scaling, additional side filter or quote-stability
filter. One exact intended Ask/Bid is used for SL, OrderCalcProfit and the order
request. No second quote inside the risk helper. Future fill/stop slippage,
commissions, gaps and spread widening are not capped by this estimate.

All new native runs: USD70 / leverage1:500, XAUUSD M1, 100% real ticks, 200ms
execution, local agents only, no cloud/remote. Research lab only
`.mt5-v23-tuning.local`. Protected open V24 process, account, chart, parameters
and data directory must not be touched. No VM/SSH, credential extraction or Git
mutation. Only root launches native tests, under the lab lease/process-idle guard.

## Reviewed artifacts

Parent remains `research/ResearchControl_R1_R8.mq5`:
`961756D0742CAF124FE5EADF1ABD7D0AB62082FC92B831DAF0B16F9727E9140B`.
R10 source `research/ResearchCandidate_R10.mq5`:
`8B1BC2B768326FCD305672BAD9B6EBB2879DFF94170C7B0F8315BF29A02C5E68`.
Binary:
`4085FCE15A7E3EAD8928031BA4467C6EEA6B14CA63B60B307794A8A715BAF819`.
Compile log `research/ResearchCandidate_R10.r10_70_a_compile.log`: zero errors,
zero warnings. Nine source-contract tests prove the parent execution body differs
only by disabled/enabled risk hooks and OnTester only by four diagnostic spec
fields. Independent review found and helped remove the original quote mismatch.

Source only accepts mode0 P0/SL1.5/TP2/hold60/vetoOFF or mode1
P2/SL2/TP3/hold60/vetoOFF-or-ON. Other execution/guard inputs are fixed. Tester
initialization requires 10 deterministic MQL fixtures. First valid native tick
must pass actual no-order BUY and SELL OrderCalcProfit smoke tests. No mocked
tests are profit evidence. Invalid risk calculation/price/SL/equity fails closed.

## Run order and gate contract

1. Revalidate accepted R9 capital70 production/baseline/control and all pins.
2. R10 mode0 full10m must exactly match accepted production70 native sequence.
3. R10 vetoOFF development must exactly match accepted R9 hold60 development.
4. One vetoON development replay. No treatment until both parity checks pass.
5. Only if development qualifies, run validation. Otherwise one full10m
   descriptive vetoON replay remains rejected and cannot rescue the gate.
6. Only if validation qualifies, lock exact source/binary/settings/capital before
   confirmation. Timestamp-aware lock must strictly predate actual confirmation
   started.json, including retries. No reselection.

Dates/floors unchanged from capital70 R9 protocol: development Dec2025-May2026
net>0/PF>=1.20/N>=150, validation Jun-Jul2026 net>0/PF>=1.20/N>=40,
historical confirmation Aug-Sep2026 net>0/PF>=1.10/N>=40, full10m net>0/PF>=1.15/
N>=150/at least7 positive months/net above USD70 V24/native equityDD no worse
than USD70 V24. No stopout, positive extra$0.20 per-position accounting sensitivity
required. Native500ms full replay must net>0/PF>=1.10/N>=150. Report extra$0.50
sensitivity. Accounting stress is not native altered spread or compounded equity.

Actual HTML/SET/INI/spec/signatures and complete deal/cash ledger must reconcile.
Report all risk vetoes, calculation failures, margin blocks, idle months and
actual openings/exits. Rejected opportunities are not "saved losses". Exact native
end-close exception keeps its full existing ownership/HTML/journal proof. No
foreign or stopout deal may be silently accepted under that exception.

All dates already inspected. Even a pass is retrospective/post-selection, not
unseen OOS or guaranteed future profit. Runner always leaves qualified=false
and promotion=false. Independent review remains required. No auto naming,
installation or deployment of V25. New strategy hypotheses require separate
predeclaration and preserve this failed/passed result untouched.

## Audit implementation notes, no trading/gate changes

Per-bar verification uses actual exported point/digits/tick_size and risk
fraction/enabled specs, exact unique raw/signal joins, source-order binary64
outward stop reconstruction, same-side decision quote, order/veto consistency
and strict failure gates. Risk-cap comparison to serialized equity accounts for
equity2-decimal and cap4-decimal reporting (maximum discrepancy0.000175; bound
0.000176). Threshold comparison separately reports overlapping four-decimal
uncertainty, never flips a reported native decision. Risk audits are derived
artifacts beside, not modifications of, native accepted evidence.

An original Decimal-ideal stop reconstruction rejected a native development
row. Original MQL arithmetic reproduced the actual stop; the narrow offline
auditor was corrected and independently revalidated. Interruption evidence
retained. Trading source/binary/capital/config/gates never changed after outcomes.
