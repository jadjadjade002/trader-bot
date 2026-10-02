# V25: use existing data before collecting more

Date: 2026-09-28. Scope: research only. No EA deployment or account changes.

## Evidence already available

- V21 snapshot `data/v21_check_20260928_124506`: 16,417 XAUUSD M1 bars, 16 broker sessions, 92 non-OK rows, 22 time gaps. Reproduced with `research/v25_forensics.py`. The collector is MetaQuotes-Demo, not XM.
- V21 preregistered whipsaw veto: 907 probes; vetoed whipsaw rate 18.60%, kept 20.69%; separation -2.09 percentage points. Coverage 61.6%, outside its 10–40% gate. Do not promote this veto.
- V16.56 demo forensics: 12 exits, 4 wins, net -$20.68. Winners were locked near entry while eight losers hit full stops. Exit change alone is not sufficient because subsequent V16.58 entry variants failed validation.
- V25 native MetaQuotes-Demo real-tick test: $60 development 0 trades and validation 1 trade -$0.93. At $200, development 21 trades +$7.75, validation 16 trades -$0.25. V25 is a risk-hardened baseline, not a demonstrated positive edge.
- V23's published local report is not reproducible as the shipped EA's exact policy. The conservative V21 bar proxy for the default inverted/no-spread-guard setting gives 149 trades, -$114.77, PF 0.686. Proxy is diagnostic, not actual fill PnL.

## External sources worth using

1. Dukascopy historical-data export: bid/ask quotes and volume. Source: https://www.dukascopy.com/api/data/get/historical-data-export . Use to **falsify** a frozen signal on longer, independent price history, not to claim XM execution PnL.
2. MT5 Strategy Tester with broker real ticks. Source: https://www.mql5.com/en/docs/runtime/testing . Audit the report's real-tick coverage; the tester can generate ticks where broker tick history is absent. Use the intended broker's symbol contract and trading costs for a final executable-policy test.
3. Bailey et al., *The Probability of Backtest Overfitting*: https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253 . Treat repeated threshold/indicator searches on already-inspected history as development, not untouched validation.

## Next experiment, fixed sequence

1. **Feasibility first:** run the existing read-only `V25_ContractProbe` on an XM demo terminal, if one is supplied. Record XAUUSD contract size, minimum lot/step, tick value, spread, stop level, margin and `OrderCalcProfit` for a 2-ATR stop. On $60 equity with a 3% loss veto, any minimum-lot stop estimate above $1.80 means the strategy must skip that trade. Do not weaken the cap just to produce trades. MetaQuotes-Demo values cannot answer the XM question.
2. **Independent historical falsification:** freeze one exact strategy source and settings hash before downloading or viewing a new Dukascopy period. Preserve its bid/ask timestamps and UTC mapping. Test the frozen policy once on a chronological later period, including realistic costs and worst-case ambiguous stop/target ordering. Any change after looking at results creates a new candidate and requires a new untouched period.
3. **Broker-parity test:** run the identical policy on the intended broker's real ticks. Compare signal timestamps, accepted/vetoed orders, spread, stop distances, fills, and net PnL. Any large disagreement is a data/execution mismatch to resolve, not a parameter-tuning opportunity.
4. **Prospective demo:** only after the prior stages show feasible sizing and positive after-cost results, freeze EA/binary/settings and observe new trades. Positive historical results alone do not authorize deployment or establish a stable profit rate.

## Decision now

Do not wait for another arbitrary V21 bar/session count before investigating. Existing evidence already rejects V21's current veto and does not validate V25 or V23. The highest-value unresolved check is **XM minimum-lot risk feasibility**, followed by one independent historical falsification of a frozen policy. No claim of profitable daily returns is supported yet.
