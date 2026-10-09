# R11 single one-bar-persistence experiment

Preregistered before any R11 native outcome, 2026-10-08. Not V25.

R9 longer holds did not fix SELL losses. R10 fixed2.5% planned-stop veto
preserved capital but admitted only3 historical positions and failed the frozen
sample floor. Neither establishes profitable entry evidence. Test a distinct
entry-timing hypothesis, not a combined filter or retrospective long-only rule.

## Fixed hypothesis

Parent: immutable `research/ResearchControl_R1_R8.mq5`. Default delayOFF retains
the exact parent's economic logic. Mode0/P0/SL1.5ATR/TP2R/hold60/delayOFF must
match accepted USD70 V24 full-period native economics. Mode1/P2/SL2ATR/TP3R/
hold60/delayOFF must match accepted R9 hold60 development exactly.

The sole treatment is `InpDelayOneBar=true`, symmetric BUY and SELL. At an
otherwise signal-evaluable fresh active M1 bar b, save the completed signal
bar s=b-60, side, decision quote and closed ATR. Do not place an order. Due time
is b+60=s+120. At exactly the next fresh active M1 bar, require its completed
M1 bar s+60, retained closed M5/M1 trend alignment, and BUY close above closed
EMA9 or SELL close below closed EMA9. No active/future candle enters the rule.
Then attempt once using current closed ATR and inherited executable quote,
SL/TP geometry, fixed lot and execution guards.

Unavailable history, wrong trend/EMA side, skipped due bar, occupied/cooldown/
other blocked due event, or rejected order consumes/expires the pending event.
No late fill, replacement, same-callback fallback, retry or persisted pending
state across restart. A later independent fresh bar can arm a new signal.
Report all armed/expired/confirmed/blocked events; they are not saved losses.
Arming occurs before the order-side margin check, so an armed signal is not
proof that its original order would have been executable.

No R10 risk cap, side removal, BE, grid, martingale, extra entry threshold,
hold/TP/SL change, lot scaling or topup. Existing breaker and guards unchanged.

## Isolation and native conditions

All new runs USD70 / leverage1:500, fixed0.01 lot, XAUUSD M1, MetaQuotes-Demo,
100% real ticks, 200ms native execution, local agents only. Root alone launches
under lab lease and process-idle guard in `.mt5-v23-tuning.local`. Protected
existing desktop V24 window/account/settings/process/data remain untouched.
No VM/SSH, key/credential reads, Git mutation or demo/live trading deployment.

Clean compile and reviewed source/binary hashes must be pinned before launch.
Final source SHA256:
`F19DDB56768BD1E02F05DA4FA859F3E428561CECB006FD103967EC072184D246`.
Final binary SHA256:
`C51AAFEE1E84D3050312F2B3010A1B57EFC4638505A97EF7CEE3ECB1ED320AB0`.
Compile log `research/ResearchCandidate_R11.r11_70_a_compile_clean.log`:
zero errors, zero warnings. Initial warning log preserved; only a pure-helper
parameter was renamed to remove global-name shadowing before this clean compile.
All19 deterministic native fixtures must pass. Validate actual native SET/INI,
HTML capital/quality, symbol/time specs, complete deals/cash, exact raw/signal
join and pending-event state audit. Controls precede any treatment.

## Frozen progression and falsification

Development Dec2025-May2026: net>0, PF>=1.20, N>=150, no native stopout,
positive extra$0.20 per-position accounting sensitivity. Also report drawdown,
all sides, monthly participation, expired events and actual time/SL/TP exits.
If development fails, run only one descriptive full10m arm and preserve FAILED.
It cannot rescue the development gate. No tuning the delay after outcomes.

Only after development passes: validation Jun-Jul2026 net>0/PF>=1.20/N>=40.
Only after validation passes: durable aware selection lock pins treatment,
source/binary/capital before actual confirmation starts. Confirmation Aug-Sep
net>0/PF>=1.10/N>=40. Full10m Dec1,2025-Oct1,2026 net>0/PF>=1.15/N>=150,
at least7 positive months, net above USD70 V24 and native equityDD no worse.
Native500ms full replay net>0/PF>=1.10/N>=150. No stopout and positive extra$0.20
sensitivity in each required screen; report extra$0.50. Accounting sensitivities
are not native spread experiments or compounded balances.

All windows already inspected across prior research. A pass is retrospective,
not genuinely unseen OOS or guaranteed future profit. No reselection from
confirmation. Runner leaves qualified=false and promotion=false pending external
independent review. No automatic V25 naming, installation or deployment.
