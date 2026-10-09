# Debate Round 1 - Antigravity (Claude)

Written: 2026-10-06 ~01:40 +07. Source read directly: `AegisPredator_v23.mq5` lines 180-260 and 300-360.
Not verified by me: the 6 backtest sets (comparison.json is ~14 MB; I only read its first 800 lines, which are market-probe data). Net figures below are quoted from the other agent and marked [UNVERIFIED].

## Claim 1 - Breaker never resets the streak (CONFIRMED from code, extends the other agent's point)

Mechanism (lines 204-240):
- L207: `TimeCurrent() < cooldownUntil` blocks during cooldown.
- L216-229: walks deals newest to oldest, counts `profit < 0`, stops at first `profit > 0`. Nothing resets this count; it is re-derived from history every call.
- L231: re-trigger needs `latestOutTicket != lastBreakerDealTicket`. After a cooldown expires, the latest closed deal is still the one that triggered, so the condition is false and the function returns false -> trading resumes.
- The next closed loss has a new ticket, `losses` is already >= N, so it triggers again immediately.
- Result: after the first trigger (N losses), each cooldown cycle adds roughly 1 loss. This is consistent with 12 in a row.

Additional defects the other agent did not list:
- **L209-210 fail-open:** `HistorySelect` failure returns `false` ("breaker not active") -> trading allowed. Must be fail-closed.
- **L226-228 uses `DEAL_PROFIT` only:** commission, swap and fee are ignored, so a deal that is net negative but has profit >= 0 breaks the streak. A deal with profit == 0 neither counts nor breaks.
- **L220:** filters by magic only, not symbol.
- **State is in memory** (`cooldownUntil`, `lastBreakerDealTicket`): an EA restart clears the cooldown.
- A position can still be open while the breaker is evaluated; I did not read the position-limit code, so I make no claim about how many can open after a cooldown.

Proposed fix (not applied):
1. Replace the cooldown with a lock: when the streak (or a daily/equity loss cap) triggers, set `tradingLocked = true` until a defined reset (next server day, or manual). Persist via `GlobalVariableSet`.
2. Compute streak per `DEAL_POSITION_ID`, net = profit + commission + swap + fee.
3. `HistorySelect` failure -> block new entries, keep managing open positions.

## Claim 2 - Entry is not a false-breakout detector (CONFIRMED, with a sharper reading)

Lines 332-348:
- Bullish pattern = `breakClose > donchianHigh` AND `retestLow >= donchianHigh - 0.5*ATR` AND `retestClose > retestOpen`.
- That is a **successful hold** above the level with a bullish retest candle, i.e. continuation confirmation.
- `InpFadeBreakouts` then flips the sign (L345-347) so the bot sells exactly after the market confirmed the breakout.
- Nothing requires price to have come back inside the range. So "fade of a false breakout" is the label, not what is tested.

Where I partly disagree with the other agent: I would not say the current rule is "unproven"; the code shows it is **structurally contrarian to its own confirmation candle**. A close-back variant (retest close < donchianHigh for the bullish case) at least matches the stated hypothesis. It is still a hypothesis.

## Claim 3 - Backtest evidence [UNVERIFIED by me]

Quoted: original 2,987 trades, net -1,342.34 (parity block, lines 2-9 I did read). Close-back variant 1,436 trades, net -464.50 [not seen by me].
- Fewer losses is not edge. Needed: gross before costs, cost per trade, and expectancy per trade for each set. If gross <= 0, the result is cost drag on a no-edge rule.
- Per-trade: -464.50/1436 = -0.32; -1342.34/2987 = -0.45. Both negative.

## Proposed pass criteria (set BEFORE running)

- Net (profit+commission+swap+fee) > 0 on an out-of-sample window not used to choose parameters.
- Profit factor > 1.2 and >= 300 trades.
- One change per run: (a) close-back only; (b) then ATR filter; (c) then volume filter. No combining and no picking the best of many.

## Questions for the other side

1. Do you agree the breaker defect is the confirmed `lastBreakerDealTicket` logic at L231, not time-based reset?
2. Can you show gross vs cost per trade for the close-back run?
3. What out-of-sample window will you use?
