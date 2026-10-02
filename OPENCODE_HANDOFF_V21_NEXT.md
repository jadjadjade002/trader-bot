# Opencode Handoff: V21 Next Work

You are working in `D:\project\trader-bot`.

Use a cheap/free model. Keep output concise in Thai.

Goal: continue V21 research infrastructure without touching live V16 or deploying any EA.

Hard rules:
- Do not touch, stop, retune, or redeploy V16.
- Protected V16 account: `112334471`.
- V21 Research account: `5055724796`.
- V21.67 failed and must not be deployed.
- Do not deploy anything new.
- Use `apply_patch` for manual edits.
- Do not reset git or revert user changes.

Current known status:
- V21 tests pass: 8/8.
- Collector is healthy on VM.
- Latest broker timestamp: `2026-09-10T03:52:00`.
- Sample counts: Sep 09 = 156 rows, Sep 10 = 174 rows.
- Latest health row: `HEALTHY`.
- `write_errors=0`, `duplicate_skips=0`.
- `gap_count=120` is recorded and should not be repaired.
- Current V21 decision: `INCONCLUSIVE_ACQUISITION_INCOMPLETE`.

Immediate tasks:
1. Add a daily markdown report command for V21.
   - It should read real collected files from a given QTForward directory.
   - It should call existing audit/whipsaw/decision code where possible.
   - It should output a concise markdown status:
     - run id
     - latest broker timestamp
     - row count by broker date
     - health summary if health file exists
     - decision status
     - failed/incomplete gates
     - next action
   - Suggested file: `research/v21_daily_report.py`

2. Add focused tests.
   - Cover small/incomplete dataset.
   - Cover session crossing midnight.
   - Cover health file summary with gaps and no write errors.
   - Suggested file: `tests/test_v21_daily_report.py`

3. Start offline V22 candidate research note.
   - No code deployment.
   - Use lessons from V17 and V21.67 failures.
   - Focus on ideas that might reduce gap/session risk and overtrading.
   - Suggested file: `docs/V22_RESEARCH_NOTES.md`
   - Keep it clear that V22 is only a candidate, not approved for live/demo execution.

4. Run tests:
   ```powershell
   python -m unittest tests.test_v21_dataset_audit tests.test_v21_whipsaw tests.test_v21_decision tests.test_v21_daily_report
   ```

Return:
- files changed
- tests pass/fail
- any remaining risk
- next best action

Style:
- Thai
- Short
- No em dashes
- No semicolons
