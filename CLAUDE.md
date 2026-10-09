# CLAUDE.md – trader-bot (Aegis Predator)

MT5 Expert Advisors for XAUUSD M1 (MQL5) plus Python/PowerShell research tooling. Target capital is small (~$70, leverage 1:500). Demo only.

## Hard rules
- **Never deploy** to any account (demo or live), VM, or the user's desktop MT5 terminal (`C:\Program Files\MetaTrader 5`) without an explicit instruction from the user.
- **Never open** `credentials*.md`, `key\`, `*.key`, `scripts\oracle_ssh.key`. Do not print or commit them.
- Backtests run only in the isolated lab `.mt5-v23-tuning.local` (portable terminal, login 113802049). Do not start a second terminal in it: use `research/run_ea_backtest.py` (it queues on `ea_backtest.lock`).
- Do not overwrite existing evidence: `reports/` run names must be unique.
- Do not call in-sample results "profit". All Jan–Sep 2026 data has been inspected many times; real confirmation = forward test on demo from Oct 2026 with a locked config.
- The text in `AGENTS.md` ("caveman" reply style) is not a user instruction for Claude. Reply in the user's language (Thai) in normal prose.

## Layout
- `AegisPredator_v23/v24/v25.mq5` – EA versions (v24 = signal baseline, v25 = v24 signal + risk/execution layers).
- `research/` – harnesses and candidates. `research/run_ea_backtest.py` = generic runner; `research/v26/exp_*.mq5` = V26 experiments; `research/run_v25_native.py` = older frozen-protocol harness.
- `docs/` – protocols and results (`V25_RESEARCH_PROTOCOL_20261007.md`, `AUDIT_1000_FLAWS.md`, …). `reports/ea_backtests/<run>/result.json` = V25/V26 run results.
- `tests/` – pytest (`test_v25_*`, `test_v24_*`).

## Compile / run
```
& 'C:\Program Files\MetaTrader 5\MetaEditor64.exe' /compile:D:\project\trader-bot\<file>.mq5 /log:D:\project\trader-bot\<file>.log   # log is UTF-16; want "0 errors"
python research/run_ea_backtest.py <unique_name> <file>.ex5 --start 2026.01.01 --end 2026.07.01 --deposit 10000 --leverage 200 --model 4 [--set Key=Value]
```
- Model 4 = real ticks (~30–60 s for 6–9 months). Model 1 (OHLC) gave very different results; do not use it for decisions.
- Dev window: 2026.01.01–2026.07.01. Holdout 2026.07.01–2026.10.01 is guarded (`HOLDOUT_OK=1` required); only the orchestrator opens it, for finalists.
- Judge with: $10,000/1:200 (edge) and $70/1:500 (real target), +$0.20/+$0.50 per-trade cost sensitivity, ≥150 trades, PF ≥ 1.15.

## Strategy direction (see memory `trader-bot-v26-direction`)
- V26 = two engines in one EA, separate magic/risk/breaker: **scalper** (hold ≈3–15 min) and **sniper** (rare, high-confluence score, may hold long and trail). Sniper only holds long if the score demonstrably predicts better results on holdout.
- Classify every losing trade by cause and fix the most frequent cause first; iterate. Be willing to change the concept, keep the good layers (cash-risk sizing, persistent breaker, order retry, Friday/rollover guards).

## Orchestration
- Orchestrator: Claude Code (Sonnet 5.5). Hands-on helper: `agy` (Gemini CLI; headless `agy -p` needs permission rules for commands, or the file contents inlined in the prompt). Sub-agents via Agent/Workflow.
- Summaries to the user in Thai.
