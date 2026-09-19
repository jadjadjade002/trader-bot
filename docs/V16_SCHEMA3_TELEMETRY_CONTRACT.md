# Institutional Telemetry Specification: V16 Schema 3 Telemetry Contract

**Contract Version**: `3.0.0`  
**System**: QuantumTitan v16 Velocity M1 Scalper  
**Symbol**: `XAUUSD`  
**Base Timeframe**: `PERIOD_M1` (Secondary HTF: `PERIOD_M5`)  
**Target Execution Environment**: Strictly Read-Only Telemetry Collection & Offline Replay  
**Governing Code**: `QuantumTitan_v16_Velocity.mq5` (v16.55)  
**Historical Predecessors**:
- Schema 1 (`v16.20`): Basic M1 bar features and exploratory forward metrics.
- Schema 2 (`v16.31` / `v16.32`): Microsecond tick-path extremes and first-passage grids (`QuantumTitan_V16_TickPathCollector.mq5`).

---

## 1. Executive Summary & Problem Statement

### 1.1 The Parity Resolution Deficit of Schema 2
Schema 2 successfully recorded microsecond-level tick paths and first-passage grids across a 15-bar forward horizon. However, Schema 2 omitted critical internal state variables required by `QuantumTitan_v16_Velocity.mq5`:
1. **Multi-Timeframe Trend State**: M5 EMA20 and M5 EMA50 values and trend direction.
2. **M1 Trend Baseline**: M1 EMA14 and M1 EMA50 values, distance to EMA14, and EMA touch status.
3. **SMC Turtle Soup Footprint**: 30-bar swing high/low lookback prices and rejection wick ratios.
4. **Imbalance Confluence**: 3-bar Fair Value Gap (FVG) metrics (`rates[0]` vs `rates[2]`).
5. **Momentum Regime**: LazyBear Squeeze Momentum indicators (Bollinger Bands vs Keltner Channels, Donchian midpoint linear regression slope).
6. **Execution Gates**: Dynamic account equity/drawdown state, position concurrency, post-exit cooldown, loss-streak pause, and native MQL5 Economic Calendar news lockout state.

Because these fields were absent, Schema-2 telemetry was **strictly unresolvable for full-source entry parity** (forcing offline audits into either a 100% fail-closed block or an unverified proxy heuristic).

### 1.2 Schema 3 Mission
Schema 3 establishes an immutable, read-only telemetry contract that captures the complete frozen decision state of `QuantumTitan_v16_Velocity.mq5` at the instant an M1 bar closes, alongside microsecond executable quote paths. This enables **100% deterministic entry parity replay** without modifying live EA behavior, risking accounts, or inventing data.

---

## 2. Formal Invariants & No-Lookahead Guarantees

Every Schema 3 data collector and audit engine must enforce the following formal invariants:

### Invariant 1: Completed-Bar Signal Freezing (Zero Active-Bar Leakage)
- Signal features must be computed **exclusively** from completed bars. In MQL5 array-as-series terms, Bar 0 is active and incomplete; all signal features, indicator buffers, swing lookbacks, and FVG comparisons must be derived from Bar 1 (`rates[1]`) through Bar 31 (`rates[31]`).
- The completed bar's open epoch timestamp is designated as `signal_bar_epoch`.
- The entry tick observing the new quote must satisfy:
  $$\text{entry\_tick\_time\_msc} \ge (\text{signal\_bar\_epoch} + 60) \times 1000$$
- Any record where $\text{entry\_tick\_time\_msc} < (\text{signal\_bar\_epoch} + 60) \times 1000$ represents active-bar leakage and **must immediately fail closed**.

### Invariant 2: Monotonic Temporal Progression
- Within any single record, timestamps must be strictly monotonic:
  $$(\text{signal\_bar\_epoch} \times 1000) < \text{entry\_tick\_time\_msc} \le \text{horizon\_end\_time\_msc}$$
- For all forward observation timestamps $T \in \{\text{fav\_msc}, \text{adv\_msc}, \text{recross\_msc}, \text{mfe\_time\_msc}, \text{mae\_time\_msc}\}$:
  $$\text{entry\_tick\_time\_msc} \le T \le \text{horizon\_end\_time\_msc}$$
- Across records in an audit partition, `signal_bar_epoch` must be strictly monotonically increasing. Duplicate or out-of-order signal epochs are rejected.

### Invariant 3: Price Bar Geometry & Mathematical Sanity
- Completed bar prices must obey basic Euclidean candle invariants:
  $$\text{bar\_low} \le \min(\text{bar\_open}, \text{bar\_close}) \le \max(\text{bar\_open}, \text{bar\_close}) \le \text{bar\_high}$$
  $$\text{bar\_range\_points} = \frac{\text{bar\_high} - \text{bar\_low}}{\text{POINT}} > 0$$
- Wick decomposition must satisfy:
  $$\text{bar\_lower\_wick\_points} = \frac{\min(\text{bar\_open}, \text{bar\_close}) - \text{bar\_low}}{\text{POINT}} \ge 0$$
  $$\text{bar\_upper\_wick\_points} = \frac{\text{bar\_high} - \max(\text{bar\_open}, \text{bar\_close})}{\text{POINT}} \ge 0$$
  $$\text{bar\_lower\_wick\_ratio} = \frac{\text{bar\_lower\_wick\_points}}{\text{bar\_range\_points}} \in [0.0, 1.0]$$
  $$\text{bar\_upper\_wick\_ratio} = \frac{\text{bar\_upper\_wick\_points}}{\text{bar\_range\_points}} \in [0.0, 1.0]$$

### Invariant 4: Microsecond Executable Quote Discipline
- To avoid execution optimism, spread friction is strictly accounted for:
  - **BUY Orders**: Enter at $Ask_{\text{entry}}$, exit against $Bid_{\text{tick}}$.
  - **SELL Orders**: Enter at $Bid_{\text{entry}}$, exit against $Ask_{\text{tick}}$.
- Favorable excursion (MFE) and adverse excursion (MAE) are measured using the executable exit side relative to the entry fill price.

### Invariant 5: Collector Version Stratification & Single-Source Purity
- Datasets must not combine records from disparate schemas or collector versions.
- Schema 1 records (`schema_version == "1"`), Schema 2 records (`schema_version == "2"`), and Schema 3 records (`schema_version == "3"`) must reside in segregated directories.
- Any batch evaluation containing mixed `schema_version` or mixed `collector_version` must fail closed.

### Invariant 6: Explicit Availability Tagging for Account and External State
- When a read-only telemetry collector operates on a dedicated chart or isolated terminal without direct access to account balances, deal history, or calendar events:
  - Account fields must set `account_state_available = 0` and record `UNAVAILABLE`.
  - Trade concurrency fields must set `trade_state_available = 0` and record `UNAVAILABLE`.
  - News calendar fields must set `news_state_available = 0` and record `UNAVAILABLE`.
- In strict audit mode, any record with `*_available == 0` is classified as `PARITY_UNRESOLVABLE` and fails closed. Replay cannot fabricate uncaptured account or broker states.

---

## 3. Exact Schema 3 CSV Header

The authoritative, single-line Schema 3 header is defined below:

```csv
schema_version,collector_version,run_id,symbol,signal_bar_epoch,signal_bar_iso,entry_tick_time_msc,horizon_end_time_msc,broker_utc_offset_seconds,session_label,bar_open,bar_high,bar_low,bar_close,bar_range_points,bar_tick_volume,bar_lower_wick_points,bar_upper_wick_points,bar_lower_wick_ratio,bar_upper_wick_ratio,m5_ema20,m5_ema50,m5_trend_bullish,m5_trend_bearish,m1_ema14,m1_ema50,m1_ema_distance_points,m1_ema_touched_buy,m1_ema_touched_sell,swing_high_30,swing_low_30,sweep_buy_detected,sweep_sell_detected,bar2_high,bar2_low,fvg_bullish,fvg_bearish,rsi,atr_points,linreg_slope_current,linreg_slope_previous,sqz_bb_middle,sqz_bb_upper,sqz_bb_lower,sqz_kc_upper,sqz_kc_lower,sqz_is_squeeze_on,sqz_is_breakout,sqz_momentum,sqz_prev_momentum,sqz_is_momentum_bullish,sqz_is_momentum_bearish,signal_side,account_state_available,account_balance,account_equity,account_daily_start_equity,daily_drawdown_pct,daily_loss_tripped,trade_state_available,active_position_count,last_deal_exit_time_msc,post_exit_cooldown_active,cooldown_bars_remaining,consecutive_losses,loss_streak_cooldown_active,news_state_available,news_filter_enabled,in_news_window,news_event_name,entry_bid,entry_ask,entry_spread_points,spread_mean_points,spread_max_points,spread_p95_points,buy_mfe_points,buy_mae_points,sell_mfe_points,sell_mae_points,buy_mfe_time_msc,buy_mae_time_msc,sell_mfe_time_msc,sell_mae_time_msc,buy_fav_15_msc,buy_fav_20_msc,buy_fav_30_msc,buy_fav_50_msc,buy_fav_85_msc,buy_fav_100_msc,buy_fav_130_msc,buy_fav_150_msc,buy_fav_180_msc,buy_fav_200_msc,buy_fav_220_msc,buy_fav_240_msc,sell_fav_15_msc,sell_fav_20_msc,sell_fav_30_msc,sell_fav_50_msc,sell_fav_85_msc,sell_fav_100_msc,sell_fav_130_msc,sell_fav_150_msc,sell_fav_180_msc,sell_fav_200_msc,sell_fav_220_msc,sell_fav_240_msc,buy_adv_15_msc,buy_adv_20_msc,buy_adv_30_msc,buy_adv_50_msc,buy_adv_85_msc,buy_adv_100_msc,buy_adv_130_msc,buy_adv_180_msc,buy_adv_220_msc,buy_adv_260_msc,sell_adv_15_msc,sell_adv_20_msc,sell_adv_30_msc,sell_adv_50_msc,sell_adv_85_msc,sell_adv_100_msc,sell_adv_130_msc,sell_adv_180_msc,sell_adv_220_msc,sell_adv_260_msc,buy_be_t50_l0_recross_msc,buy_be_t50_l10_recross_msc,buy_be_t50_l15_recross_msc,buy_be_t50_l20_recross_msc,buy_be_t50_l30_recross_msc,buy_be_t75_l0_recross_msc,buy_be_t75_l10_recross_msc,buy_be_t75_l15_recross_msc,buy_be_t75_l20_recross_msc,buy_be_t75_l30_recross_msc,buy_be_t85_l0_recross_msc,buy_be_t85_l10_recross_msc,buy_be_t85_l15_recross_msc,buy_be_t85_l20_recross_msc,buy_be_t85_l30_recross_msc,buy_be_t100_l0_recross_msc,buy_be_t100_l10_recross_msc,buy_be_t100_l15_recross_msc,buy_be_t100_l20_recross_msc,buy_be_t100_l30_recross_msc,buy_be_t130_l0_recross_msc,buy_be_t130_l10_recross_msc,buy_be_t130_l15_recross_msc,buy_be_t130_l20_recross_msc,buy_be_t130_l30_recross_msc,buy_be_t150_l0_recross_msc,buy_be_t150_l10_recross_msc,buy_be_t150_l15_recross_msc,buy_be_t150_l20_recross_msc,buy_be_t150_l30_recross_msc,sell_be_t50_l0_recross_msc,sell_be_t50_l10_recross_msc,sell_be_t50_l15_recross_msc,sell_be_t50_l20_recross_msc,sell_be_t50_l30_recross_msc,sell_be_t75_l0_recross_msc,sell_be_t75_l10_recross_msc,sell_be_t75_l15_recross_msc,sell_be_t75_l20_recross_msc,sell_be_t75_l30_recross_msc,sell_be_t85_l0_recross_msc,sell_be_t85_l10_recross_msc,sell_be_t85_l15_recross_msc,sell_be_t85_l20_recross_msc,sell_be_t85_l30_recross_msc,sell_be_t100_l0_recross_msc,sell_be_t100_l10_recross_msc,sell_be_t100_l15_recross_msc,sell_be_t100_l20_recross_msc,sell_be_t100_l30_recross_msc,sell_be_t130_l0_recross_msc,sell_be_t130_l10_recross_msc,sell_be_t130_l15_recross_msc,sell_be_t130_l20_recross_msc,sell_be_t130_l30_recross_msc,sell_be_t150_l0_recross_msc,sell_be_t150_l10_recross_msc,sell_be_t150_l15_recross_msc,sell_be_t150_l20_recross_msc,sell_be_t150_l30_recross_msc,observed_tick_count,completed_bar_count,largest_tick_gap_msc,missing_bar_count,disconnect_seen,rollover_seen,label_status,quality_flags
```

Total field count: **180 columns**.

---

## 4. Comprehensive Field Dictionary & Traceability

### Group 1: Identity & Timing (Columns 1–10)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `schema_version` | String | Const `"3"` | Must be strictly `"3"`. Rejects `"1"` or `"2"`. | Schema versioning |
| `collector_version` | String | SemVer `"16.xx"` | Version of collector (e.g. `"16.40"`). Single-version per batch. | Collector metadata |
| `run_id` | String | Alpha-numeric | Unique run / process identifier. | Collector instance |
| `symbol` | String | Token | Instrument symbol (`"XAUUSD"`). | `_Symbol` |
| `signal_bar_epoch` | Integer | Seconds | Unix epoch of completed Bar 1 open. | `iTime(_Symbol, PERIOD_M1, 1)` |
| `signal_bar_iso` | String | ISO 8601 | Human-readable UTC/broker timestamp `YYYY-MM-DDTHH:MM:SS`. | `TimeToStruct` |
| `entry_tick_time_msc` | Integer | Milliseconds | Unix millisecond timestamp of first tick post bar-close. $\ge \text{epoch}\times 1000 + 60000$. | `TimeCurrent_msc` |
| `horizon_end_time_msc`| Integer | Milliseconds | Unix millisecond timestamp when 15 completed bars elapsed. | Bar 15 close tick time |
| `broker_utc_offset_seconds` | Integer | Seconds | Broker timezone offset relative to UTC (e.g. `10800` for UTC+3). | Timezone calculation |
| `session_label` | String | Enum | `"ASIA"`, `"LONDON"`, `"NY_AM"`, `"NY_PM"`, or `"ROLLOVER"`. | Intraday session filter |

### Group 2: Completed Bar 1 OHLC & Geometry (Columns 11–20)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `bar_open` | Float | Price ($) | Completed Bar 1 Open price. | `rates[0].open` (L766) |
| `bar_high` | Float | Price ($) | Completed Bar 1 High price. | `rates[0].high` (L766) |
| `bar_low` | Float | Price ($) | Completed Bar 1 Low price. | `rates[0].low` (L766) |
| `bar_close` | Float | Price ($) | Completed Bar 1 Close price. | `rates[0].close` (L766) |
| `bar_range_points` | Float | Points ($0.01) | `(bar_high - bar_low) / 0.01`. Must be $>0$. | `barRange` (L767) |
| `bar_tick_volume` | Integer | Count | Tick volume of completed Bar 1. | `rates[0].tick_volume` |
| `bar_lower_wick_points` | Float | Points | `(min(open, close) - low) / 0.01`. Must be $\ge 0$. | `lowerWick` (L770) |
| `bar_upper_wick_points` | Float | Points | `(high - max(open, close)) / 0.01`. Must be $\ge 0$. | `upperWick` (L771) |
| `bar_lower_wick_ratio` | Float | Ratio $[0,1]$ | `lower_wick_points / range_points`. | `lowerWickRatio` (L772) |
| `bar_upper_wick_ratio` | Float | Ratio $[0,1]$ | `upper_wick_points / range_points`. | `upperWickRatio` (L773) |

### Group 3: Multi-Timeframe M5 & M1 Moving Averages (Columns 21–29)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `m5_ema20` | Float | Price ($) | HTF M5 Fast EMA (Period 20) value at bar close. | `m5FastEma[0]` (L42, L702, L786) |
| `m5_ema50` | Float | Price ($) | HTF M5 Slow EMA (Period 50) value at bar close. | `m5SlowEma[0]` (L43, L702, L786) |
| `m5_trend_bullish` | Integer | Boolean `0` or `1` | `1` if `m5_ema20 > m5_ema50`, else `0`. | `m5Bullish` (L786) |
| `m5_trend_bearish` | Integer | Boolean `0` or `1` | `1` if `m5_ema20 < m5_ema50`, else `0`. | `m5Bearish` (L787) |
| `m1_ema14` | Float | Price ($) | M1 Fast EMA (Period 14) value at bar close. | `fastEma[0]` (L40, L702, L798) |
| `m1_ema50` | Float | Price ($) | M1 Slow EMA (Period 50) baseline value at bar close. | `slowEma[0]` (L41, L702, L798) |
| `m1_ema_distance_points` | Float | Points | `abs(bar_close - m1_ema14) / 0.01`. Must be $\le 40$ for retest. | `withinValueZone` (L801, L825) |
| `m1_ema_touched_buy` | Integer | Boolean `0` or `1` | `1` if `bar_low <= m1_ema14 + 0.15` ($15$ pts buffer). | `touchedFastEma` (L800) |
| `m1_ema_touched_sell` | Integer | Boolean `0` or `1` | `1` if `bar_high >= m1_ema14 - 0.15` ($15$ pts buffer). | `touchedFastEma` (L824) |

### Group 4: SMC Turtle Soup Swing & 3-Bar FVG (Columns 30–37)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `swing_high_30` | Float | Price ($) | Highest high of preceding 30 bars (`rates[1..30]`). | `swingHigh` (L248–254) |
| `swing_low_30` | Float | Price ($) | Lowest low of preceding 30 bars (`rates[1..30]`). | `swingLow` (L249–254) |
| `sweep_buy_detected` | Integer | Boolean `0` or `1` | `1` if `bar_low < swing_low` and `bar_close > swing_low` and `wick >= 0.30`. | `outIsSweepBuy` (L263–267) |
| `sweep_sell_detected` | Integer | Boolean `0` or `1` | `1` if `bar_high > swing_high` and `bar_close < swing_high` and `wick >= 0.30`. | `outIsSweepSell` (L269–274) |
| `bar2_high` | Float | Price ($) | High of Bar 3 (`rates[2].high` in MQL5 series). | `rates[2].high` (L289) |
| `bar2_low` | Float | Price ($) | Low of Bar 3 (`rates[2].low` in MQL5 series). | `rates[2].low` (L295) |
| `fvg_bullish` | Integer | Boolean `0` or `1` | `1` if `bar_low > bar2_high` (imbalance gap up). | `outBullishFvg` (L289–292) |
| `fvg_bearish` | Integer | Boolean `0` or `1` | `1` if `bar_high < bar2_low` (imbalance gap down). | `outBearishFvg` (L295–298) |

### Group 5: Oscillators & Squeeze Momentum (Columns 38–53)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `rsi` | Float | Index $[0, 100]$ | M1 RSI (Period 14) on completed bar. | `rsiVal[0]` (L792, L804, L816) |
| `atr_points` | Float | Points | M1 ATR (Period 14) in points. Bounds $[50, 650]$. | `currentAtrPts` (L740, L743) |
| `linreg_slope_current` | Float | Slope | Current LinReg slope of closing prices. | Linear regression slope |
| `linreg_slope_previous` | Float | Slope | Prior bar LinReg slope. | Linear regression slope |
| `sqz_bb_middle` | Float | Price ($) | Bollinger Bands SMA(20) middle line. | `bbMiddle[0]` (L140) |
| `sqz_bb_upper` | Float | Price ($) | Bollinger Bands upper line ($+2.0\sigma$). | `bbUpper[0]` (L140) |
| `sqz_bb_lower` | Float | Price ($) | Bollinger Bands lower line ($-2.0\sigma$). | `bbLower[0]` (L140) |
| `sqz_kc_upper` | Float | Price ($) | Keltner Channel upper line ($\text{SMA} + 1.5\times\text{ATR}_{20}$). | `kcUpper` (L149) |
| `sqz_kc_lower` | Float | Price ($) | Keltner Channel lower line ($\text{SMA} - 1.5\times\text{ATR}_{20}$). | `kcLower` (L150) |
| `sqz_is_squeeze_on` | Integer | Boolean `0` or `1` | `1` if BB is compressed inside KC. | `state.isSqueezeOn` (L152) |
| `sqz_is_breakout` | Integer | Boolean `0` or `1` | `1` if squeeze was on previous bar and released this bar. | `state.isBreakout` (L157) |
| `sqz_momentum` | Float | Momentum | LinReg slope of Donchian delta array (20 bars). | `state.momentum` (L180) |
| `sqz_prev_momentum` | Float | Momentum | Previous Donchian delta value. | `state.prevMomentum` (L181) |
| `sqz_is_momentum_bullish` | Integer | Boolean `0` or `1` | `1` if `momentum > 0` and `momentum >= prev_momentum`. | `state.isMomentumBullish` (L183) |
| `sqz_is_momentum_bearish` | Integer | Boolean `0` or `1` | `1` if `momentum < 0` and `momentum <= prev_momentum`. | `state.isMomentumBearish` (L184) |
| `signal_side` | String | Enum | `"BUY"`, `"SELL"`, or `"NONE"` (as emitted by collector). | Collector signal classification |

### Group 6: Account State & Circuit Breakers (Columns 54–59)
*Marked `UNAVAILABLE` unless captured by an authorized live collector.*
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `account_state_available` | Integer | Boolean `0` or `1` | `1` if captured from broker; `0` if collector is read-only isolated. | Execution gate check |
| `account_balance` | Float/Str | Balance ($) or `"UNAVAILABLE"` | Account balance at bar close. | `AccountInfoDouble(ACCOUNT_BALANCE)` |
| `account_equity` | Float/Str | Equity ($) or `"UNAVAILABLE"` | Account equity at bar close. | `AccountInfoDouble(ACCOUNT_EQUITY)` |
| `account_daily_start_equity` | Float/Str | Equity ($) or `"UNAVAILABLE"` | Baseline equity recorded at 00:00 server time. | `g_dayInitialEquity` (L95, L441) |
| `daily_drawdown_pct` | Float/Str | Percent or `"UNAVAILABLE"` | `(daily_start_equity - equity) / daily_start_equity * 100`. | `currentDrawdown` (L451) |
| `daily_loss_tripped` | Int/Str | Boolean or `"UNAVAILABLE"` | `1` if `daily_drawdown_pct >= 5.0%`. Fails closed if 1. | `IsDailyLossBreakerTripped` (L437, L719) |

### Group 7: Trade Concurrency, Cooldown & Loss Streak (Columns 60–66)
*Marked `UNAVAILABLE` unless captured by an authorized live collector.*
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `trade_state_available` | Integer | Boolean `0` or `1` | `1` if open trades & deals ledger captured; `0` if unavailable. | Execution gate check |
| `active_position_count` | Int/Str | Count or `"UNAVAILABLE"` | Number of open positions with magic `991602`. Max 1 allowed. | `activeTrades` (L306, L721) |
| `last_deal_exit_time_msc`| Int/Str | Msc or `"UNAVAILABLE"` | Millisecond time of last position close. | `g_lastExitTime` (L93, L377) |
| `post_exit_cooldown_active` | Int/Str | Boolean or `"UNAVAILABLE"` | `1` if 2 full M1 bars have not elapsed since exit. | `IsPostExitCooldownActive` (L375, L722) |
| `cooldown_bars_remaining` | Int/Str | Bars or `"UNAVAILABLE"` | Number of bars remaining in post-exit cooldown (`[0, 2]`). | `InpCooldownBars` (L64) |
| `consecutive_losses` | Int/Str | Count or `"UNAVAILABLE"` | Consecutive losing scalps recorded in deal history. | `g_consecutiveLosses` (L98, L389) |
| `loss_streak_cooldown_active` | Int/Str | Boolean or `"UNAVAILABLE"` | `1` if 15-minute anti-revenge pause is active ($\ge 2$ losses). | `IsLossStreakCooldownActive` (L387, L725) |

### Group 8: Economic News Calendar State (Columns 67–70)
*Marked `UNAVAILABLE` unless captured by an authorized live collector.*
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `news_state_available` | Integer | Boolean `0` or `1` | `1` if MQL5 Calendar API is captured; `0` if unavailable. | Execution gate check |
| `news_filter_enabled` | Int/Str | Boolean or `"UNAVAILABLE"` | `1` if `InpUseNewsFilter == true`. Default in V16 is `false`. | `InpUseNewsFilter` (L28) |
| `in_news_window` | Int/Str | Boolean or `"UNAVAILABLE"` | `1` if current time is within high-impact USD buffer. | `IsInHighImpactNews` (L192, L737) |
| `news_event_name` | String | Event Name or `"UNAVAILABLE"`| Name of high-impact USD economic catalyst. | `outEventName` (L223) |

### Group 9: Entry Quotes & Spread Dynamics (Columns 71–76)
| Field | Type | Unit / Format | Description & Invariant | MQL5 Velocity Traceability |
| :--- | :--- | :--- | :--- | :--- |
| `entry_bid` | Float | Price ($) | Executable Bid price at first tick after bar close. | `bid` (L755, L841) |
| `entry_ask` | Float | Price ($) | Executable Ask price at first tick after bar close. | `ask` (L755, L841) |
| `entry_spread_points` | Float | Points | `(entry_ask - entry_bid) / 0.01`. Ceiling $\le 60$ pts. | `currentSpread` (L755) |
| `spread_mean_points` | Float | Points | Mean spread across the 15-bar forward horizon. | Horizon tick statistics |
| `spread_max_points` | Float | Points | Peak spread recorded during horizon. | Horizon tick statistics |
| `spread_p95_points` | Float | Points | 95th percentile spread during horizon. | Horizon tick statistics |

### Group 10: Forward Tick Path Extremes (Columns 77–84)
| Field | Type | Unit / Format | Description & Invariant |
| :--- | :--- | :--- | :--- |
| `buy_mfe_points` | Float | Points | Maximum favorable excursion for Buy ($Bid_{\max} - Ask_{\text{entry}}$). |
| `buy_mae_points` | Float | Points | Maximum adverse excursion for Buy ($Ask_{\text{entry}} - Bid_{\min}$). |
| `sell_mfe_points` | Float | Points | Maximum favorable excursion for Sell ($Bid_{\text{entry}} - Ask_{\min}$). |
| `sell_mae_points` | Float | Points | Maximum adverse excursion for Sell ($Ask_{\max} - Bid_{\text{entry}}$). |
| `buy_mfe_time_msc` | Integer | Milliseconds | Unix millisecond timestamp when Buy peak MFE occurred. |
| `buy_mae_time_msc` | Integer | Milliseconds | Unix millisecond timestamp when Buy worst MAE occurred. |
| `sell_mfe_time_msc` | Integer | Milliseconds | Unix millisecond timestamp when Sell peak MFE occurred. |
| `sell_mae_time_msc` | Integer | Milliseconds | Unix millisecond timestamp when Sell worst MAE occurred. |

### Group 11: First-Passage Favorable & Adverse Grids (Columns 85–128)
- 12 Favorable levels for Buy and Sell: `15, 20, 30, 50, 85, 100, 130, 150, 180, 200, 220, 240` points.
  - Columns: `buy_fav_<level>_msc`, `sell_fav_<level>_msc`
- 10 Adverse levels for Buy and Sell: `15, 20, 30, 50, 85, 100, 130, 180, 220, 260` points.
  - Columns: `buy_adv_<level>_msc`, `sell_adv_<level>_msc`
- Invariant: Values are Unix millisecond timestamps when executable price first touched or crossed the barrier. A value remains empty/null if the barrier was never touched.

### Group 12: Break-Even Recross Grids (Columns 129–188)
- Break-Even trigger grid: `50, 75, 85, 100, 130, 150` points.
- Break-Even lock grid: `0, 10, 15, 20, 30` points.
- 30 Buy combinations: `buy_be_t<trig>_l<lock>_recross_msc`
- 30 Sell combinations: `sell_be_t<trig>_l<lock>_recross_msc`
- Invariant: Records the earliest millisecond timestamp when price returned to or crossed the locked break-even price **after** having first touched the activation trigger. Null if trigger never armed or lock was never recrossed.

### Group 13: Quality & Audit Telemetry (Columns 189–196)
| Field | Type | Unit / Format | Description & Invariant |
| :--- | :--- | :--- | :--- |
| `observed_tick_count` | Integer | Count | Total ticks processed during the 15-bar horizon. Must be $>0$. |
| `completed_bar_count` | Integer | Count | Completed M1 bars observed. Must be exactly 15 for `COMPLETE`. |
| `largest_tick_gap_msc`| Integer | Milliseconds | Largest interval between consecutive ticks in milliseconds. |
| `missing_bar_count` | Integer | Count | Count of expected bars that did not form. Must be 0 for `COMPLETE`. |
| `disconnect_seen` | Integer | Boolean `0` or `1` | `1` if terminal disconnected during horizon. |
| `rollover_seen` | Integer | Boolean `0` or `1` | `1` if horizon crossed the 23:55–00:05 rollover spread shock window. |
| `label_status` | String | Enum | `"COMPLETE"`, `"INVALID_GAP"`, `"INVALID_DISCONNECT"`, `"INVALID_ROLLOVER"`, or `"INCOMPLETE_HORIZON"`. |
| `quality_flags` | String | Flags | Delimited quality flags (e.g. `"OK"`, `"OKROLLOVER"`, `"GAP"`). |

---

## 5. Deterministic V16 Velocity Entry Parity Algorithm

With Schema 3, offline replay of V16 entry decisions becomes **100% deterministic**. The algorithm mirrors `QuantumTitan_v16_Velocity.mq5` lines 718–835:

```
FUNCTION EvaluateV16EntryParity(row):
    // 1. Hard Circuit Breakers & Risk Filters
    IF row.account_state_available == 1 AND row.daily_loss_tripped == 1:
        RETURN NO_TRADE("DAILY_LOSS_BREAKER")
    IF IsFridayAfterCutoff(row.signal_bar_iso, cutoff_hour=20):
        RETURN NO_TRADE("FRIDAY_LOCKOUT")
    IF row.trade_state_available == 1 AND row.active_position_count > 0:
        RETURN NO_TRADE("CONCURRENCY_BLOCKED")
    IF row.trade_state_available == 1 AND row.post_exit_cooldown_active == 1:
        RETURN NO_TRADE("POST_EXIT_COOLDOWN")
    IF row.trade_state_available == 1 AND row.loss_streak_cooldown_active == 1:
        RETURN NO_TRADE("LOSS_STREAK_COOLDOWN")
    IF row.news_state_available == 1 AND row.news_filter_enabled == 1 AND row.in_news_window == 1:
        RETURN NO_TRADE("NEWS_LOCKOUT")

    // 2. Volatility & Spread Regime
    IF row.atr_points < 50.0:
        RETURN NO_TRADE("DEAD_MARKET_ATR")
    IF row.atr_points > 650.0:
        RETURN NO_TRADE("VOLATILITY_SHOCK_CEILING")
    IF row.entry_spread_points > 60.0:
        RETURN NO_TRADE("SPREAD_EXCEEDED")

    // 3. Multi-Timeframe Trend State
    m5_bullish = (row.m5_ema20 > row.m5_ema50)
    m5_bearish = (row.m5_ema20 < row.m5_ema50)

    // 4. BUY SETUP 1: Trend-Locked SMC Liquidity Sweep (Turtle Soup)
    sweep_buy_trend_ok = (m5_bullish AND row.bar_close > row.m1_ema50)
    IF row.sweep_buy_detected == 1 AND sweep_buy_trend_ok AND (row.rsi >= 35.0 AND row.rsi <= 55.0):
        RETURN SIGNAL_BUY("SMC_SWEEP_BUY")

    // 5. BUY SETUP 2: Trend Retest + Value Zone + FVG / Wick Confluence
    IF m5_bullish AND row.m1_ema14 > row.m1_ema50 AND row.bar_close > row.m1_ema50:
        touched_fast_ema = (row.m1_ema_touched_buy == 1)
        within_value_zone = (row.m1_ema_distance_points <= 40.0)
        rejection_wick = (row.bar_lower_wick_ratio >= 0.30 AND row.bar_close >= (row.bar_open - 0.05))
        mom_ok = (row.sqz_momentum > -0.05)
        rsi_ok = (row.rsi >= 42.0 AND row.rsi <= 58.0)
        
        IF touched_fast_ema AND within_value_zone AND (rejection_wick OR row.fvg_bullish == 1) AND mom_ok AND rsi_ok:
            reason = "FVG_PULLBACK_BUY" IF row.fvg_bullish == 1 ELSE "WICK_PULLBACK_BUY"
            RETURN SIGNAL_BUY(reason)

    // 6. SELL SETUP 1: Trend-Locked SMC Liquidity Sweep (Turtle Soup)
    sweep_sell_trend_ok = (m5_bearish AND row.bar_close < row.m1_ema50)
    IF row.sweep_sell_detected == 1 AND sweep_sell_trend_ok AND (row.rsi >= 45.0 AND row.rsi <= 65.0):
        RETURN SIGNAL_SELL("SMC_SWEEP_SELL")

    // 7. SELL SETUP 2: Trend Retest + Value Zone + FVG / Wick Confluence
    IF m5_bearish AND row.m1_ema14 < row.m1_ema50 AND row.bar_close < row.m1_ema50:
        touched_fast_ema = (row.m1_ema_touched_sell == 1)
        within_value_zone = (row.m1_ema_distance_points <= 40.0)
        rejection_wick = (row.bar_upper_wick_ratio >= 0.30 AND row.bar_close <= (row.bar_open + 0.05))
        mom_ok = (row.sqz_momentum < 0.05)
        rsi_ok = (row.rsi >= 42.0 AND row.rsi <= 58.0)
        
        IF touched_fast_ema AND within_value_zone AND (rejection_wick OR row.fvg_bearish == 1) AND mom_ok AND rsi_ok:
            reason = "FVG_PULLBACK_SELL" IF row.fvg_bearish == 1 ELSE "WICK_PULLBACK_SELL"
            RETURN SIGNAL_SELL(reason)

    RETURN NO_TRADE("NO_SETUP_MATCH")
```

---

## 6. Audit & Fail-Closed Validation Protocols

The companion audit script `research/v16_schema3_audit.py` enforces fail-closed validation on any candidate telemetry dataset:

| Failure Mode | Audit Error Code | Trigger Condition | Enforcement Action |
| :--- | :--- | :--- | :--- |
| **Missing Header Fields** | `ERR_ABSENT_FIELD` | CSV header lacks any of the 180 canonical columns. | Dataset rejected immediately. Audit aborts. |
| **Invalid Schema Version** | `ERR_INVALID_SCHEMA` | `schema_version != "3"`. | Dataset rejected immediately. |
| **Mixed Collector Versions**| `ERR_MIXED_COLLECTORS` | Multiple distinct `collector_version` strings found in single file/partition. | Dataset rejected. Aggregation forbidden. |
| **Malformed Numeric Data** | `ERR_MALFORMED_FIELD` | Non-numeric or NaN/Inf in price, ratio, or indicator fields. | Record rejected. If strict, batch fails. |
| **Invalid Wick / Range** | `ERR_GEOMETRY_INVALID` | $Low > High$, $Open/Close \notin [Low, High]$, or wick ratio $\notin [0, 1]$. | Record rejected. |
| **Active-Bar Leakage** | `ERR_ACTIVE_BAR_LEAKAGE` | `entry_tick_time_msc < signal_bar_epoch * 1000 + 60000`. | Record rejected (lookahead violation). |
| **Non-Monotonic Times** | `ERR_NONMONOTONIC_TIME` | `entry_tick_time_msc > horizon_end_time_msc` or events outside horizon. | Record rejected. |
| **Invalid Label Status** | `ERR_INVALID_LABEL` | `label_status` not in permitted 5-state enum. | Record rejected. |
| **Parity Unresolvable** | `ERR_PARITY_UNRESOLVABLE` | Required state marked `UNAVAILABLE` or missing while evaluating replay. | In `--strict` mode, batch fails closed. |

---

## 7. Schema Evolution Matrix

| Capability | Schema 1 (`v16.20`) | Schema 2 (`v16.31/32`) | Schema 3 (`v16.40+`) |
| :--- | :---: | :---: | :---: |
| **Total Header Columns** | 19 | 142 | **180** |
| **Forward Horizon Tracking** | Bar-level | Microsecond Tick Grids | **Microsecond Tick Grids** |
| **First-Passage Fav/Adv Grids** | None | 12 Fav + 10 Adv | **12 Fav + 10 Adv** |
| **Break-Even Recross Grids** | None | $6\times 5 = 30$ levels | **$6\times 5 = 30$ levels** |
| **Completed Bar OHLC & Wicks** | Open/High/Low/Close | Range Only | **Full OHLC + 30% Wick Ratios** |
| **Multi-Timeframe M5 Trend** | None | None | **M5 EMA20 + M5 EMA50** |
| **M1 Fast/Slow Baseline** | Generic | Generic | **M1 EMA14 + M1 EMA50 + Touch** |
| **30-Bar Swing Lookback** | None | None | **Swing High/Low + Turtle Soup** |
| **3-Bar FVG Detection** | None | None | **Bar 1 vs Bar 3 Imbalance** |
| **LazyBear Squeeze Momentum** | None | None | **BB vs KC + Donchian Delta** |
| **Account & Concurrency State**| None | None | **Available Tag + Unavailable Flag** |
| **News Lockout State** | None | None | **Available Tag + Unavailable Flag** |
| **Deterministic Parity Replay** | No | No (Parity Deficit) | **Yes (100% Deterministic)** |

---

## 8. Governance & Operating Protocols

1. **Read-Only Invariant**: Telemetry collection and audit scripts must never execute orders, modify charts, or touch broker terminals outside the authorized research environment.
2. **Deterministic Certification**: No candidate filter, stop-loss adjustment, or take-profit optimization can be promoted to deployment consideration without passing the Schema 3 audit fail-closed pipeline with 0 errors across at least five contiguous liquid trading sessions.
3. **No Unproven Claims**: Proxy tick outcomes remain observational quotes until corroborated by official broker trade statement records.
