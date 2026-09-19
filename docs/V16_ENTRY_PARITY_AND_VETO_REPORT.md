# Institutional Research Report: V16 Entry-Parity Replay and Observational Entry-Veto Study

**Project**: QuantumTitan v16 Velocity M1 Scalper  
**Symbol**: XAUUSD  
**Timeframe**: M1  
**Execution Environment**: Strictly Read-Only Local Research  
**Data Sources**:
- `QuantumTitan_v16_Velocity.mq5` (v16.55 Source Code)
- `QuantumTitan_V16_TickPathCollector.mq5` (v16.31 Collector Source)
- `data/V16TickTelemetry_XAUUSD_M1_20260914.csv` (Schema-2 Telemetry)
- `deploy/v16_20260910_mql5.log` (Live MT5 Deployment Log)
**Governance Verdict**: `RESEARCH_ONLY`  
**Deployment Status**: `BLOCKED`

---

## 1. Executive Summary & Audit Corrections

### Core Research Focus
Investigate entry conditions, trade management dynamics, and observational filter rules on XAUUSD M1 without fabricating unproven claims or assumptions.

### Key Audit Standards Enforced
1. **Close/Cooldown Logs Do Not Prove TP/SL/BE/PnL**:
   - `deploy/v16_20260910_mql5.log` contains log entries recording that a close deal event occurred (`[Velocity Safety] Deal #... closed`).
   - **Critical Audit Rule**: Console close and cooldown logs only prove that a position was closed; they do **NOT** prove the execution exit type (TP, SL, BE, trailing stop, or manual) or realized PnL. Official broker trade ledger statements are strictly required to verify realized profits/losses.
   - Unpaired lines in deploy logs are recorded explicitly as `UNMATCHED` (audit identified 1 unmatched close record).
2. **Full Parity Unresolvable from Telemetry Alone**:
   - Schema-2 tick telemetry captures M1 indicators (EMA9, EMA20, RSI14, ATR14, LinReg slope).
   - It **lacks** HTF M5 EMAs (EMA20/50), 30-bar swing high/low lookbacks, 3-bar FVG history, live account equity/drawdown state, and MQL5 Calendar news lockout state (`IsInHighImpactNews`).
   - Consequently, deterministic full-source entry parity is **strictly unresolvable** from telemetry alone.
3. **Proxy Labels Are Observable-Only**:
   - Replay outcomes (TP, SL, BE, TIMEOUT) calculated from price tick extremes within the 15-bar observation window represent **observable-only proxy labels** based on forward quote extremes, not actual broker execution or live fills.
4. **Mandatory 15-Minute Label-Horizon Embargo**:
   - Each trade observation horizon is 15 minutes (900 seconds).
   - To eliminate forward label leakage between train and validation partitions, an explicit 15-minute embargo ($900\text{s}$) is enforced. Rows whose entry time falls within 15 minutes of the training split cutoff (7 rows) are excluded from validation.
5. **Veto Coverage Ceiling ($\le 50\%$) and Sample Floors**:
   - Any candidate entry filter blocking $> 50\%$ of trades is automatically disqualified (`REJECTED_EXCESSIVE_COVERAGE`) to prevent trivial trade suppression.
   - Minimum split sample floors ($\ge 20$ samples per partition) are strictly enforced (Train: $n=63$, Validation: $n=28$).
6. **Collector 16.31 Threshold Data is Exploratory Only**:
   - All collector signal thresholds (e.g. `signal_score < 10.0`, linreg slope thresholds) are classified as `EXPLORATORY_ONLY`.
7. **Zero Causal Claims**:
   - All evaluations measure historical observational correlations under proxy path assumptions. No claims of causal proof or guarantee are made.

---

## 2. V16 Velocity Entry Logic: Source Traceability Matrix

Every entry condition in `QuantumTitan_v16_Velocity.mq5` mapped line-by-line:

| Condition ID | Rule & Threshold | Source Function | Line References | Reconstructible in Telemetry Schema 2? | Missing Fields in Schema 2 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `COND_DAILY_LOSS` | Daily drawdown circuit breaker (5% floor) | `IsDailyLossBreakerTripped` | L437–459, 719 | **No** (Requires account state) | `live_account_balance_equity`, `daily_pnl_state` |
| `COND_FRIDAY_LOCKOUT` | Block entries after Friday 20:00 server | `IsFridayLockoutActive` | L464–470, 720 | **Yes** (Evaluated from timestamp) | None |
| `COND_CONCURRENCY` | Max 1 open position per magic number | `GetActivePositionCount` | L306–328, 721 | **No** (Requires open trade ledger) | `live_open_positions_state` |
| `COND_COOLDOWN` | 2-bar post-exit cooldown | `IsPostExitCooldownActive` | L375–382, 722 | **No** (Requires deal close history) | `deal_history_close_time`, `cooldown_bar_state` |
| `COND_LOSS_STREAK` | 15-min pause after 2 consecutive losses | `IsLossStreakCooldownActive` | L387–401, 724–734 | **No** (Requires deal ledger) | `deal_history_loss_streak_count` |
| `COND_NEWS_LOCKOUT` | MQL5 calendar news lockout window | `IsInHighImpactNews` | L192–237, 736 | **No** (Requires MQL5 Calendar) | `mql5_economic_calendar_events`, `IsInHighImpactNews_state` |
| `COND_ATR_MIN` | Minimum ATR floor: ATR(14) >= 50.0 pts | `OnTick` | L740 | **Yes** | None |
| `COND_ATR_MAX` | Volatility shock ceiling: ATR(14) <= 650.0 pts | `OnTick` | L743–751 | **Yes** | None |
| `COND_SPREAD_MAX` | Max entry spread: spread <= 60.0 pts | `OnTick` | L755–756 | **Yes** | None |
| `COND_BAR_DISCIPLINE` | Signal evaluated only on completed Bar 1 | `OnTick` | L759–760 | **Yes** | None |
| `COND_SETUP1_SMC` | Turtle Soup: 30-bar swing sweep + 30% wick + RSI | `DetectLiquiditySweep` | L242–277, 789–796, 813–820 | **No** (Fail-closed) | `30_bar_swing_high_low`, `bar1_open_high_low`, `htf_m5_ema_20_50` |
| `COND_SETUP2_RETEST` | M5+M1 Trend Retest: Fast EMA touch, 40pt zone, FVG/Wick, Sqz Mom | `DetectFVG`, `CalculateSqueezeMomentum` | L138–187, 282–300, 797–811, 821–835 | **No** (Fail-closed) | `htf_m5_ema_20_50`, `m1_ema_14_50`, `bar_high_low`, `3_bar_fvg_lookback`, `sqz_donchian_momentum` |

### Parity Verdict
- **Strict Mode (`--mode strict_fail_closed`)**: Fails closed (100% blocked, 0 passed) due to missing HTF M5 EMAs, 30-bar swing OHLC, 3-bar FVG history, account state, and news calendar state.
- **Proxy Mode (`--mode proxy`)**: Evaluates observable single-bar macro conditions (`ATR [50, 650]`, `Spread <= 60`, `RSI [35, 65]`, `Session != ROLLOVER`) as observable-only proxies.

---

## 3. Microsecond Tick Path Resolution Engine (Observable-Only Proxies)

### Quote Protocol (Bid/Ask Spread Discipline)
To prevent execution optimism, spread friction is strictly accounted for:
- **BUY Order**:
  - Enters at Ask: $P_{entry} = Ask_{entry}$
  - Exits at Bid: $P_{exit} = Bid_{tick}$
  - Favorable move: $M_{fav} = Bid_{tick} - Ask_{entry}$
  - Adverse move: $M_{adv} = Ask_{entry} - Bid_{tick}$
- **SELL Order**:
  - Enters at Bid: $P_{entry} = Bid_{entry}$
  - Exits at Ask: $P_{exit} = Ask_{tick}$
  - Favorable move: $M_{fav} = Bid_{entry} - Ask_{tick}$
  - Adverse move: $M_{adv} = Ask_{tick} - Bid_{entry}$

### Chronological Path Event Order
1. **Initial SL**: Adverse price move reaches $SL$ before BE trigger is reached.
2. **Breakeven (BE)**: Favorable price move reaches $BE_{trig}$ (arming BE), followed by pullback to or below $BE_{lock}$ prior to reaching TP.
3. **Take Profit (TP)**: Favorable price move reaches $TP$ prior to initial SL and prior to BE recross.
4. **Timeout**: No terminal level touched within 15-bar horizon (15 minutes).

---

## 4. Empirical Deploy Log Analysis: Objective Observational Evidence

Audit of `deploy/v16_20260910_mql5.log` (14 total log events):

| Record # | Side | Open Time | Open Price | Close Time | Deal ID | Match Status | BE Armed During Trade? | Outcome Classification | Notes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| 0 | UNKNOWN | None | None | 00:00:39.885 | 10151930251 | `UNMATCHED` | No | `UNMATCHED_CLOSE` | Close event with no preceding open line |
| 1 | SELL | 00:01:41.092 | 4391.51 | 00:03:57.618 | 10151961825 | `PAIRED_CLOSE_OBSERVED` | Yes (4391.36) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 2 | SELL | 00:08:00.318 | 4392.24 | 00:09:24.390 | 10152000934 | `PAIRED_CLOSE_OBSERVED` | Yes (4391.94) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 3 | BUY  | 00:24:00.464 | 4396.33 | 00:27:48.382 | 10152131931 | `PAIRED_CLOSE_OBSERVED` | Yes (4396.48) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 4 | SELL | 00:32:00.581 | 4393.12 | 00:34:34.278 | 10152183027 | `PAIRED_CLOSE_OBSERVED` | Yes (4392.86) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 5 | BUY  | 00:43:00.356 | 4398.45 | 00:44:11.098 | 10152268672 | `PAIRED_CLOSE_OBSERVED` | Yes (4398.57) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 6 | BUY  | 00:48:00.301 | 4398.93 | 00:48:38.915 | 10152303927 | `PAIRED_CLOSE_OBSERVED` | Yes (4399.08) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 7 | BUY  | 00:51:00.291 | 4398.96 | 00:51:47.840 | 10152325227 | `PAIRED_CLOSE_OBSERVED` | Yes (4399.35) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 8 | BUY  | 00:52:47.743 | 4402.32 | 00:53:47.281 | 10152348564 | `PAIRED_CLOSE_OBSERVED` | Yes (4402.47) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 9 | BUY  | 01:00:00.313 | 4401.45 | 01:00:04.827 | 10152400577 | `PAIRED_CLOSE_OBSERVED` | Yes (4401.45) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 10 | BUY  | 01:01:04.353 | 4408.09 | 01:01:08.605 | 10152423146 | `PAIRED_CLOSE_OBSERVED` | No | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 11 | BUY  | 01:15:00.356 | 4413.17 | 01:15:45.804 | 10152626924 | `PAIRED_CLOSE_OBSERVED` | Yes (4413.23) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 12 | BUY  | 01:16:45.428 | 4413.88 | 01:18:26.877 | 10152649979 | `PAIRED_CLOSE_OBSERVED` | Yes (4414.03) | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |
| 13 | BUY  | 01:19:26.363 | 4415.06 | 01:20:28.438 | 10152669766 | `PAIRED_CLOSE_OBSERVED` | No | `CLOSE_OBSERVED_UNVERIFIED` | Exit reason & PnL unproven from log |

### Log Audit Summary
- **Total Records Found**: 14
- **Paired Close Events**: 13
- **Unmatched Close Events**: 1 (Record #0, deal closed before log started)
- **Breakeven Armed Lines Observed**: 11 / 13 paired trades (84.6%)
- **Verified PnL**: Unproven from console logs alone (requires official broker account deal statement).

---

## 5. Telemetry Schema-2 Observational Entry-Veto Study

Conducted on `data/V16TickTelemetry_XAUUSD_M1_20260914.csv` (154 COMPLETE rows, 98 passing basic proxy filters).

### Temporal Partitioning (with 15-Minute Forward Embargo)
- **Total Usable Rows**: 98
- **Train Split**: 63 rows (2026-09-14T03:02:00 to 2026-09-14T04:36:00)
- **Embargo Rule**: validation entry must be strictly later than the latest actual train `horizon_end_time_msc`, not merely 900 seconds after a signal-bar timestamp.
- **Embargoed Rows**: rows whose entry occurs before that train-horizon boundary are excluded from validation.
- **Validation Split**: 28 rows (2026-09-14T04:51:00 to 2026-09-14T05:32:00)
- **Verification**: `$\min(Val\_EntryTimeMsc) > \max(Train\_HorizonEndTimeMsc)$`; this prevents overlapping forward-label windows.
- **Split Sample Floor**: Both splits satisfy the minimum sample size floor ($\ge 20$).

### Baseline Proxy Performance (No Vetoes)
- **Train (n=63)**: 17 TP, 25 SL, 21 BE. Net: **-3,125.0 pts** | Exp: **-49.60 pts/trade**
- **Validation (n=28)**: 8 TP, 15 SL, 5 BE. Net: **-2,385.0 pts** | Exp: **-85.18 pts/trade**

### Observational Candidate Evaluation Matrix (with Coverage $\le 50\%$ Ceiling)

| Candidate Veto Filter | Observational Rule | Train Coverage (Ceiling $\le 50\%$) | Train SL Removed | Train Exp $\Delta$ (pts/trade) | Val Coverage (Ceiling $\le 50\%$) | Val SL Removed | Val Exp $\Delta$ (pts/trade) | Evaluation Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Spread Ceiling (45 pts)** | `spread > 45.0` | 20 / 63 (31.8%) | 8 / 25 (32.0%) | **-8.31** | 6 / 28 (21.4%) | 3 / 15 (20.0%) | **+2.73** | `REJECTED_HYPOTHESIS` |
| **Dead Market ATR (<100 pts)** | `atr < 100.0` | 0 / 63 (0.0%) | 0 / 25 (0.0%) | **+0.00** | 0 / 28 (0.0%) | 0 / 15 (0.0%) | **+0.00** | `REJECTED_HYPOTHESIS` |
| **Volatility Shock ATR (>200 pts)**| `atr > 200.0` | 63 / 63 (100.0%)| 25 / 25 (100.0%)| **+49.60** | 18 / 28 (64.3%)| 11 / 15 (73.3%)| **-31.85** | `REJECTED_EXCESSIVE_COVERAGE` (>50%) |
| **Counter-Slope Momentum** | `BUY & slope<0 \| SELL & slope>0` | 16 / 63 (25.4%) | 5 / 25 (20.0%) | **-16.14** | 7 / 28 (25.0%) | 4 / 15 (26.7%) | **-9.82** | `REJECTED_HYPOTHESIS` |
| **RSI Overextended** | `BUY & RSI>60 \| SELL & RSI<40` | 18 / 63 (28.6%) | 7 / 25 (28.0%) | **+18.16** | 12 / 28 (42.9%) | 6 / 15 (40.0%) | **-2.88** | `REJECTED_HYPOTHESIS` (validation worsened) |
| **Weak Trend Score (<10 pts)** [Exploratory] | `score < 10.0` | 2 / 63 (3.2%) | 0 / 25 (0.0%) | **-7.53** | 5 / 28 (17.9%) | 2 / 15 (13.3%) | **-0.21** | `REJECTED_HYPOTHESIS` |
| **Rollover Session Veto** | `session == ROLLOVER` | 0 / 63 (0.0%) | 0 / 25 (0.0%) | **+0.00** | 0 / 28 (0.0%) | 0 / 15 (0.0%) | **+0.00** | `REJECTED_HYPOTHESIS` |

### Key Findings
1. **Disqualification of High ATR Veto**:
   - `VETO_HIGH_ATR_200` blocked 100% of trades in the training split and 64.3% in validation.
   - Enforcing the $\le 50\%$ coverage ceiling strictly disqualifies this filter from consideration.
2. **Exploratory Status of Collector Signals**:
   - Collector EMA separation score (<10 pts) showed negligible sample representation and is marked exploratory.
3. **Severe Structural Limitation**:
   - No standalone pre-entry filter can convert a negative expectancy system into positive profitability when trading under asymmetric payoff ($SL = -260\text{ pts}$, $BE = +15\text{ pts}$, $TP = +180\text{ pts}$) in the absence of verified HTF trend alignment.

---

## 6. Institutional Governance Verdict

- **Classification**: `RESEARCH_ONLY`
- **Deployment Status**: `BLOCKED`
- **Governance Reasons**:
  1. Telemetry is localized to a single Asian session (2026-09-14, 154 clean rows).
  2. Full entry parity is strictly unresolvable without M5 indicators, 30-bar swing lookback, 3-bar FVG history, account state, and news state.
  3. Close/cooldown logs do not prove TP/SL/BE/PnL without broker trade statements.
  4. Observational correlations under proxy assumptions do not constitute causal proof.
  5. Live deployment remains strictly prohibited under institutional risk rules.
