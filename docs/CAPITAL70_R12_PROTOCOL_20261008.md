# R12 closed-breakout retest and structural-risk policy

Preregistered before source implementation and any R12 native outcome, 2026-10-08.
Research mechanism study only, not V25. R11 has been independently reconciled:
125 positions, net -59.53 USD, PF0.8555, all fills December2025, final balance10.47.
All four saved runs passed root and independent accounting/lifecycle validation.

## Frozen policy and control

One coupled policy, not a claim identifying separate entry, stop or risk effects.
Use a tester-only clone of the pinned R10 source, itself an exact economic clone
of `ResearchControl_R1_R8.mq5` when its risk veto is OFF. Replace the single R10
input with `InpStructuralRetest=false`; policyOFF bypasses all new economic logic.
Mode0/P0/SL1.5ATR/TP2R/hold60/OFF must match USD70 V24 full10m exactly. Mode1/
P2/SL2ATR/TP3R/hold60/OFF must match R9 hold60 development exactly. The only new
treatment is mode1 with `InpStructuralRetest=true`. No threshold grid or retuning.

All new runs: USD70, 1:500, fixed0.01 lot, XAUUSD M1, MetaQuotes-Demo, local
native real-tick tester, initial200ms execution. Preserve existing margin,
session/spread settings and four-loss/90-minute breaker. No BE, trailing,
martingale, grid, side removal, topup, smaller lot or protected-window changes.

## Closed-bar entry

At first callback of active M1 bar B, s1=B-60, s2=B-120 and s3=B-180 must exist
and be contiguous completed bars. Data absence/gaps fail closed. Require finite
positive ATR14 and EMA9 at shifts1 and2; inherited current closed trend d must
be +1 or -1. Only Bid-chart symbols (`SYMBOL_CHART_MODE==SYMBOL_CHART_MODE_BID`)
are supported. Never interpret Last or Ask candles as Bid candles.

L=s3.high for BUY, s3.low for SELL. Setup s2: directional body, body/ATR(s2)
>=0.30, directional close location>=0.80, 0<range<=2*ATR(s2), close breaks L
by strictly more than0.10*ATR(s2), close on correct side of EMA9(s2).
Retest s1: BUY low<=L and bullish close>L and >EMA9(s1); SELL high>=L and bearish
close<L and <EMA9(s1). Side must agree with inherited ClosedTrendDirection().
Require spread<=0.10*ATR(s1) and midpoint distance to s1.close<=0.50*ATR(s1).
Recheck these quote conditions at actual pre-order quote, not just signal quote.
No pending state, delay, active features, fallback, resignal or retry. Later
independent completed bars may form new setups. No hypothetical setup PnL.

## Structural stops and executable quotes

Use same captured positive Bid/Ask throughout geometry, margin check, native
risk estimate and order request. BUY entry Ask, SELL entry Bid. On Bid candles:
BUY SL=floor_to_tick(s1.low-tick). SELL SL=ceil_to_tick(s1.high+(Ask-Bid)+tick).
SELL spread adjustment translates a Bid invalidation level to an Ask-triggered
stop at current spread, not guaranteed future spread. Do not use unadjusted Bid
high as Ask invalidation. Outward rounding uses exact MQL binary64 operations.

R=entry-to-rounded-SL distance>0. TP BUY=ceil_to_tick(Ask+3*R),
SELL=floor_to_tick(Bid-3*R). The structural policy deliberately replaces the
ATR/minimum150-point stop floor; the inherited input150 remains frozen for OFF
parity only. Do not clip/widen the structural stop or claim this is unchanged
exit geometry. Fixed3R and hold60 are not optimized from R12 results.

Read stop/freeze properties through success-returning SymbolInfoInteger calls,
reject errors or negative values. Conservatively require BOTH stop and target
distances from current close quote to be >=max(stops,freeze)*point+tick:
BUY checks Bid-SL and TP-Bid; SELL checks SL-Ask and Ask-TP. Freeze restriction
here is an explicit conservative policy, not a claim it mandates initial
placement. Do not widen stops to pass. Equality to this extra-tick boundary
passes, values below reject. Minimum native stop boundary alone is insufficient.

Call actual OrderCalcProfit at fixed0.01 lot, captured entry and exact SL.
Finite negative result only, planned loss<=0.025*current equity, initial cap1.75
USD. No tick-value conversion. Missing quote/geometry/equity/calculation fails
closed. Planned risk is not a realized-loss guarantee. Slippage, gaps, spread,
commission, fees and swap remain realized native accounting. Existing margin
check remains mandatory. No compensating risk or lot changes after failure.

## Evidence required before native launch

Root decides implementation now under continuing research authorization, not
deployment authorization. Final reviewed source/binary pins required. Compile
zero errors/warnings, deterministic native mirrored setup/retest/SL/TP/broker
boundary/risk fixtures plus real BUY/SELL OrderCalcProfit smoke checks required.
Exact fixture count must be pinned after review, never an arbitrary regex range.
Keep parent economic functions exact except conditional ON hooks/reporting.

Export actual completed setup/retest times/OHLC/ATR/EMA/level, signal and decision
quotes, trend, geometry, dynamic stop/freeze properties, equity, native planned
risk/cap, calculation validity, rejection reason and order identities. Exact
CSV schema and per-row auditor must be reviewed before native launch. Join raw
and diagnostics1:1, audit every evaluated event, reconstruct stop/target using
actual decision quotes, reconcile successful attempts to native owned positions.
Do not impute outcomes to censored held/breaker events or cash/broker vetoes.

Only research lab `.mt5-v23-tuning.local`, root launch under lease and idle
process guard. Existing desktop V24 account/chart/settings/process/data untouched.
No VM/SSH, key/credential reads or Git mutations. No demo EA installation yet.

## Frozen progression

Controls first, then ONE ON development Dec2025-May2026. Require net>0,
PF>=1.20, N>=150, no stopout, positive extra0.20USD/position sensitivity.
Failure allows only ONE descriptive full10m treatment, retains FAILED. No rescue
by full results, extra cells, changed risk cap or lowered sample floor.

If development passes: Jun-Jul2026 validation net>0/PF>=1.20/N>=40. If passes,
durable aware source/binary/inputs/capital lock strictly before actual Aug-Sep
confirmation start. Confirmation net>0/PF>=1.10/N>=40. Full10m Dec1,2025-Oct1,
2026 net>0/PF>=1.15/N>=150, >=7 positive months, net above capital70 V24 and
native equityDD no worse. Native500ms full net>0/PF>=1.10/N>=150. No stopout and
positive extra0.20USD sensitivity in all required screens. Report extra0.50USD,
all sides/months/exits/participation, worst losses, broker/cash/margin rejects.

Every window already inspected. Retrospective evidence only, not unseen OOS.
Accounting sensitivity is not native spread replay or compounded equity.
Runner keeps qualified=false/promotion=false pending independent review. No
automatic V25 name or deployment. Success cannot be promised by protocol.

## Primary reference checks

[MQL5 symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)
defines Bid/Last chart mode, minimum stop distance, freeze distance, point and
minimum price tick. [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit)
returns estimated account-currency profit under current market conditions.
The official [close-quote distance explanation](https://www.mql5.com/en/book/automation/symbols/symbols_spreads_levels)
specifies Bid for BUY protective levels and Ask for SELL protective levels.
These API facts do not establish this strategy's profitability.
