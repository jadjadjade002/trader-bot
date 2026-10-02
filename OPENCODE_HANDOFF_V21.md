# Opencode Handoff: V21 Research Continuation

You are working in `D:\project\trader-bot`.

Goal: continue the V21 research workflow while preserving the live V16 setup. Be conservative, cheap with tokens, and do not deploy any new EA unless the user explicitly authorizes it later.

Hard rules:
- Do not touch, stop, retune, or redeploy V16.
- V16 account `112334471` is protected.
- V21 Research account `5055724796` is collector-only.
- Do not deploy V21.67. It failed engineering test badly and is research-only/rejected.
- Do not claim 80%+ win rate is guaranteed.
- Use `apply_patch` for manual code edits.
- Do not reset git or revert user changes.

Immediate task:
1. Verify the newly added V21 checkpoint tooling:
   - `research/v21_decision.py`
   - `tests/test_v21_decision.py`
   - `docs/V21_CHECKPOINTS.md`
2. Run the focused tests:
   ```powershell
   python -m unittest tests.test_v21_dataset_audit tests.test_v21_whipsaw tests.test_v21_decision
   ```
3. If tests fail, fix only the checkpoint/decision tooling.
4. Inspect live V21 collector health on the VM, read-only only:
   - SSH host: `ubuntu@161.118.255.178`
   - Key: `D:\project\trader-bot\key\ssh-key-2026-09-06.key`
   - V21 files path on VM:
     `/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v21 Research/MQL5/Files/QTForward/`
   - Check latest `health_*.csv` rows and M1 data counts.
5. Produce a concise status:
   - tests pass/fail
   - collector alive or not
   - latest broker timestamp
   - sample counts by date
   - whether V21 is pass/fail/inconclusive right now
   - next action

Known context:
- Existing V21 research protocol is in `docs/V21_RESEARCH_PROTOCOL.md`.
- Final V21 decision is frozen and requires enough forward-only data:
  - 1000 probes
  - 15 broker dates
  - veto coverage 10-40%
  - vetoed whipsaw prevalence >= 1.25x kept
  - absolute separation >= 5 percentage points
  - positive result in 3 of 4 chronological weeks
  - concentration <= 20%
  - integrity pass
- Current collector previously looked healthy:
  - run id `FWD_20260909_4W`
  - latest observed rows around `2026-09-10T03:21:00`
  - Sep09 lines around 156, Sep10 lines around 143
  - terminal process had been running for ~7 hours
- Gaps in the collector can be legitimate market/time gaps. Document them. Do not backfill.

Output style:
- Thai language.
- Very concise.
- No em dashes, no semicolons.
- Lead with the outcome.
