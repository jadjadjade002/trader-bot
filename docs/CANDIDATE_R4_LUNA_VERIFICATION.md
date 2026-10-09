# Candidate R4 Luna source audit

Date: 2026-10-07

## Scope and basis

Read-only comparison of `research/build_candidate_r4.py`, generated `research/ResearchCandidate_R4.mq5`, existing `tests/test_candidate_r4.py`, `docs/CANDIDATE_R4_EXIT_PROTOCOL.md`, frozen `research/ResearchCandidate_R2.mq5`, and accepted native artifacts. This review launched no compiler, native tester, or runner and did not use a VM, account, or deployment. Source checks alone establish no compilation or fixture execution; accepted records below provide later execution evidence.

## Findings

**Previously reported input contract gap is resolved.** First audit found validator omitted locks for ATR period, Donchian period, and MagicNumber. Builder now rejects values other than ATR 14, Donchian 20, and Magic 992300 (`research/build_candidate_r4.py:53-57`); generated source contains same guards (`research/ResearchCandidate_R4.mq5:112-114`). These lock the mode-5 ATR signal/exit sizing (`:329-333`, `:381-385`, `:788`, `:1059-1060`), mode-0 Donchian signal (`:1007-1017`), and managed-position/accounting identity (`:606`, `:782`, `:873-878`, `:923`). Regression guard is in `tests/test_candidate_r4_luna_review.py:52-61`.

**Source transformation remains bounded.** Builder hash-pins R2 source to `74AC68D78650411B1364AA2EF6E18FD375928D0C528CBC23085C95867F1354FD` and replaces validation, artifact metadata, and fixture log prefixes only (`research/build_candidate_r4.py:7-10,35-69`). Existing test compares generated output with R4 and compares signal, tick, trade-management, accounting, and fixture functions between R2/R4 (`tests/test_candidate_r4.py:30-52`). R4 exhaustion is dispatched only for mode 5 (`research/ResearchCandidate_R4.mq5:381-385`); predicate body matches frozen R2 (`research/ResearchCandidate_R2.mq5:322-335`, `research/ResearchCandidate_R4.mq5:329-342`). SL/TP sizing equations stay common and unchanged (`research/ResearchCandidate_R2.mq5:1052-1053`, `research/ResearchCandidate_R4.mq5:1059-1060`).

**Fixture source and accepted native passes verified.** Fixture function body and assertion prefix transformation are source-level identical (`research/ResearchCandidate_R2.mq5:498-574`, `research/ResearchCandidate_R4.mq5:498-574`; R2/R4 prefix labels differ by design). There are 23 syntactic `R2Assert` call sites, with the `k=1..3` loop adding two executions, so runtime count is 25. R4 `OnInit` gates startup on `RunR2FixtureTests()` (`:738-741`). Native adapter requires an exact `R4_NATIVE_FIXTURES_PASS checks=25 preset=N` journal marker (`research/run_v25_native.py:350-355`); every accepted baseline, development, validation, and descriptive result records 25 checks.

## Frozen activation condition

The R3 accepted outcome table records six development rows, each below 150 positions, all ineligible, and zero validation candidates (`docs/CANDIDATE_R3_RESULTS_r3_a.md:42-56`). Separate Luna reconciliation confirms the same six counts and that none meets the frozen screen (`docs/CANDIDATE_R3_LUNA_VERIFICATION.md:23-34`). Therefore R4 protocol's “only if no R3 development configuration survives” condition is met (`docs/CANDIDATE_R4_EXIT_PROTOCOL.md:9`).

## Runner audit against clarified protocol

R4 runner constructs exactly 16 unique mode-5 rows (2 presets × 2 SL × 4 TP) with stable tags `5_{preset}_sl{SL}_tp{TP}`, decimal points replaced by `p` (`research/run_candidate_r4.py:12-17`). Activation checks the R3 label, parity pass, six unique mode/preset rows, and that every row is ineligible and fails `qualify` (`:20-30`); it reads the fixed accepted-summary path before acquiring the native-lab lease (`:33-41`). Shared runner evaluates each development row, applies the 150-trade/PF1.20/net-positive gate, and limits the development shortlist to three per family ranked by DD, net, then parameters (`research/run_candidate_r2.py:28-38`; qualification function in `research/run_v25_native.py:411-413`). R4 has one family, so this yields at most three shortlisted rows. It writes a selection-lock JSON before confirmation and checks it has not changed (`research/run_candidate_r2.py:46-62`). This matches clarified protocol: matrix remains frozen; top-three finalist selection may use development/validation only; confirmation and full-period outcomes cannot reselect (`docs/CANDIDATE_R4_EXIT_PROTOCOL.md:9,23`).

When no validation survivor exists, generic flow runs a descriptive full-period replay of the development-only maximum (`research/run_candidate_r2.py:71-76`). Clarified R4 protocol explicitly permits this as rejected descriptive evidence, without promotion (`docs/CANDIDATE_R4_EXIT_PROTOCOL.md:23-25`). If no development row qualifies, the same branch runs this one descriptive replay but no validation, selection lock, confirmation, or capital/stress qualification, matching the protocol's stop condition (`:25`).

Native adapter permits R4 mode 0/5 only and builds SET overrides for candidate source (`research/run_v25_native.py:72-84,242-259`). It checks runtime/tick-cache presence before launch, preserves SET/INI and run artifacts, disables live trading, uses real-tick mode (`:251-320`), then checks fixture marker, history/tick errors, source/binary/runtime/cache hashes, native report quality, and deal reconciliation (`:350-405`). The adapter hashes source and existing `.ex5` separately but does not establish that binary was compiled from that source (`:252-259,368-370`); parent owns compilation evidence. No launch occurred during this audit.

## Partial accepted-run audit

Read accepted JSON and exported HTML reports only. Snapshot is partial: baseline and five of 16 development rows are accepted; do not treat this as completed matrix or infer a winner. Every accepted R4 row has `native_mql_fixture_checks=25`, `History Quality=100% real ticks`, R4 source SHA `AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320`, and binary SHA `1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9`. Current accepted development rows are preset 0 / SL 1.0 / TP 0.75, 1.0, 1.5, 2.0 with net/PF/positions respectively `-$55.02/0.8988/348`, `-$17.81/0.9705/346`, `-$19.81/0.9721/340`, `-$27.71/0.9643/334`; and preset 0 / SL 1.5 / TP 0.75 at `+$12.13/1.0159/351`. All five currently fail the development gate: first four have negative net; fifth PF is below 1.20. No qualification conclusion until all 16 accepted.

The accepted R4 mode-0 baseline reports 25 fixtures and 100% real ticks. Its ordered native trade sequence exactly equals both accepted `r1_b_production_v24` and `r2_a_baseline` exports (15,072 rows each); net `$130.00`, 3,768 trades, and 132,841,964 native ticks match. Current source file SHA matches accepted R4 source SHA. R4 baseline observed 132,829,154 EA callbacks versus 132,841,964 native ticks; accepted coverage correctly marks callback-based observations and does not claim interior gap-free proof. The five then-current development rows each report 85,002,339 native ticks; callback observations range 85,001,563–85,001,595 and remain below raw ticks, so they are likewise not full tick coverage.

Historical snapshot note: at this initial five-row snapshot, both fixed-exit controls were pending. Both controls were later accepted and independently matched to R2, as recorded below. No launch or process inspection performed here.

### Follow-up: preset-0 fixed-exit parity control

The accepted R4 mode-5 / preset-0 / SL 1.5 / TP 2.0 control is identical to accepted R2 `r2_a_dev_5_0` across the ordered tester report rows (1,356 rows), deal export SHA256 (`7976FD850201E77B86F63B55C3FA581B78F028EA849492CB41367FF2AC1678D2`), and exported `signals`, `raw`, `paths`, `equity`, and `be` CSV hashes. Both summarize to net `$41.97`, PF `1.0369`, 339 positions; coverage has 85,002,339 raw ticks and 85,001,584 EA callbacks. R4 accepted record reports 25 fixtures and 100% real ticks. The R2 original source/binary hashes differ from R4 as expected because R4 changes validator/metadata/log prefix; matched trade and diagnostic exports verify behavioral parity for this frozen control.

R4 accepted signature source/binary SHA values match actual current files: source `AE6C436EC0E39F2F1DEA242CCEE0E7FAA54867239FBA782222DF15A4D4497320`, EX5 `1F3C99D36A11D12690F5231B0ABE430EF0E6C4C6F511A7AEBB066CEB0E3315A9`. `reports/candidate_r4_compile.log` records compilation of `research/ResearchCandidate_R4.mq5` with 0 errors and 0 warnings. Log itself contains no source/binary digest, so identity evidence is the accepted signature-to-current-file hashes plus the compiler's source-path/result record; it does not provide a cryptographic compiler-output link.

Historical snapshot note: this nine-row audit was partial and all nine rows then available failed the development gate. Superseded by the accepted 16-row matrix below; do not use earlier pending counts as current status.

### Follow-up: full accepted development matrix and preset-1 control

Later snapshot contains accepted JSON and exports for all 16 unique preregistered rows. Independently parsed every deals export: required header present; position grouping closes cleanly; net, net PF, and position count agree with `accepted.json`; one `$10,000` deposit cash row reconciles; final balance equals deposit plus net. For every row the signature is mode 5, the exact frozen parameter triple and Dec–May window, production=false, optimization=false, deposit `$10,000`, delay 200 ms, and shared expected source/binary SHA. Every row has 25 native fixtures, 100% real ticks, six monthly coverage records with complete month edges, callback totals matching the exports and below native tick totals. All 16 parameter triples appear once; no gaps or duplicates. Audit script output: `accepted=16`, `unique=16`, `expected=16`, `missing=[]`, `extra=[]`, `errors=[]`.

The preset-1 fixed-exit control (`mode5`, entry strength 1, SL 1.5, TP 2.0) exactly matches R2 `r2_a_dev_5_1`: ordered native report rows equal (624 each); deal CSV SHA256 equal (`36B591D071CA9A560505CE5F3065F37E7D5BB74E7880ACAE9E0C7C9BBF8B6A9E`); signals, raw, paths, equity, and BE CSV hashes equal. Both give `$7.61`, PF `1.0142`, 156 positions. Preset-0 fixed-exit control parity is recorded above.

Independent development re-ranking from accepted rows yields two eligible rows, ordered by the frozen DD/net/parameter key: preset 1 / SL1.5 / TP0.75 (DD 0.41%, net `$77.27`), then preset 1 / SL1.5 / TP1.0 (DD 0.47%, net `$98.82`). Saved `development_shortlist` matches exactly. This is development/validation workflow evidence, not a winner or final profitability conclusion.

### Follow-up: validation shortlist reconciliation

Both accepted validation rows match the same parameter triples and R4 source/binary hashes, report 25 fixtures and 100% real ticks, and use the frozen June–July window. Independently parsed deals, schema, fees, cash deposit, final balance, and two-month coverage; both reconcile with no discrepancies. Preset 1 / SL1.5 / TP0.75 gives net `$21.26`, PF `1.4834`, 28 positions; preset 1 / SL1.5 / TP1.0 gives net `$36.02`, PF `1.7633`, 28 positions. Both are positive but undersampled against validation's minimum 40 positions; neither qualifies, and no selection lock is created. Development-qualified rows therefore have positive validation samples but remain unqualified due to count. Full-period descriptive replay is now independently audited below.

## Completed qualification-path audit

### Development matrix

All 16 rows passed artifact, deal-accounting, and monthly-coverage reconciliation. Two pass the frozen development screen (`net>0`, PF≥1.20, positions≥150); the other 14 fail at least one of those row gates. Rows below report net USD / net PF / positions.

| Preset | SL ATR | TP R | Net / PF / positions | Dev screen |
| ---: | ---: | ---: | ---: | --- |
| 0 | 1.0 | 0.75 | -55.02 / 0.8988 / 348 | Fail |
| 0 | 1.0 | 1.0 | -17.81 / 0.9705 / 346 | Fail |
| 0 | 1.0 | 1.5 | -19.81 / 0.9721 / 340 | Fail |
| 0 | 1.0 | 2.0 | -27.71 / 0.9643 / 334 | Fail |
| 0 | 1.5 | 0.75 | 12.13 / 1.0159 / 351 | Fail |
| 0 | 1.5 | 1.0 | 54.85 / 1.0630 / 351 | Fail |
| 0 | 1.5 | 1.5 | 54.93 / 1.0534 / 344 | Fail |
| 0 | 1.5 | 2.0 | 41.97 / 1.0369 / 339 | Fail |
| 1 | 1.0 | 0.75 | -9.83 / 0.9591 / 156 | Fail |
| 1 | 1.0 | 1.0 | 10.65 / 1.0396 / 156 | Fail |
| 1 | 1.0 | 1.5 | 18.68 / 1.0588 / 155 | Fail |
| 1 | 1.0 | 2.0 | -24.36 / 0.9340 / 154 | Fail |
| 1 | 1.5 | 0.75 | 77.27 / 1.2524 / 156 | Pass dev; validation count fail |
| 1 | 1.5 | 1.0 | 98.82 / 1.2759 / 156 | Pass dev; validation count fail |
| 1 | 1.5 | 1.5 | 38.71 / 1.0820 / 156 | Fail |
| 1 | 1.5 | 2.0 | 7.61 / 1.0142 / 156 | Fail |

The two development qualifiers proceed to validation per frozen shortlist order. Both validation samples are positive, with PF above 1, but contain only 28 positions each, below minimum 40. Thus neither is validation-eligible; this is positive but undersampled evidence, not a qualified finalist. No selection lock was created.

### Rejected descriptive replay

The permitted development-only maximum was preset 1 / SL1.5 / TP1.0, matching the top development net `$98.82`. Complete record marks it `Development-only maximum, rejected, not release eligible`. Independent deal parsing matches native report and accepted JSON: 202 positions, 106 wins / 96 losses, net `-$2.68`, PF `0.9955`, profit `-$2.63`, commission `$0`, swap `-$0.05`, fee `$0`, equity DD `1.64%`. Ten calendar months have complete edge coverage and 100% real ticks; 132,841,546 EA callbacks versus 132,841,964 native ticks, 418 callbacks skipped by execution, with interior gap-free coverage explicitly unproven. Seven of ten monthly nets were positive (Dec `-31.52`, Jan `+50.31`, Feb `+70.57`, Mar `+8.67`, Apr `-5.94`, May `+6.73`, Jun `+26.18`, Jul `+9.84`, Aug `+12.65`, Sep `-150.17`). This is negative on the tested full-period sample and fails the gate; it does not establish a general negative edge.

Fixed additional-cost arithmetic independently reconciles: 202 completed positions × `$0.20` gives `-$43.08` net, and × `$0.50` gives `-$103.68`. These are arithmetic stresses on fixed completed trades, not native spread/timing simulations. No `capital70`, `baseline70`, or `delay500` run folders exist; completion record has no corresponding result fields. It records no development/validation-qualified candidate, `qualified=false`, `promotion=false`, and no selection lock. No winner or release candidate is established.

## Review conclusion

R4 source and validator match the frozen contract; all 25 native predicates ran per accepted initialization. All 16 rows reconcile; two pass development, but both validation rows are positive and undersampled at 28 versus 40 required. The required rejected descriptive replay is negative on its full-period sample and does not establish a general negative edge. No final qualified candidate, promotion, selection lock, or capital/stress run exists. Mode-0 and both fixed-exit controls match frozen R2 exactly. Compilation reports 0 errors/0 warnings; accepted/current source and EX5 fingerprints match, with compiler log providing source path and result but no digest link.
