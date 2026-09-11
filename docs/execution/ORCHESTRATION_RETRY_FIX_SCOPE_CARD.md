# Fix Scope Card — orchestration retry off-by-one (ORCH-001)

**Branch:** `fix/orchestration-retry-off-by-one`
**Base:** `fa9ace1` (integrate merge tip, where ORCH-001 was recorded)
**Governing decisions:** [ADR 0016](../adr/0016-agent-orchestration-foundation.md) (accepted)
**Status:** implemented, gates green; review gate pending

## Goal

Fix the retry-guard off-by-one in `src/legal_ai/orchestration/state_machine.py`.
`max_attempts = N` must allow exactly `N` attempts (including the final one).

## Defect

- **File/line:** `src/legal_ai/orchestration/state_machine.py` — the
  `current is TaskState.FAILED and target is TaskState.READY` guard used
  `attempt >= max_attempts`, so with `max_attempts = 3` only attempts 1..2
  could retry. The final configured attempt never ran.
- **Recorded as:** ORCH-001 in the integration-merge scope card.

## Fix

Changed the guard condition from `attempt >= max_attempts` to
`attempt > max_attempts`, so the `max_attempts`-th attempt is permitted and a
retry beyond the ceiling is still rejected. The general guard
(`attempt > max_attempts` at the top of the function) already enforced the
ceiling; this was the redundant, incorrect retry-specific check.

## Tests (regression-first, red then green)

- `tests/orchestration/test_state_machine.py::test_exact_retry_attempt_counts`
  — parametrized over `max_attempts` of 1, 2 and 3, asserting every configured
  attempt is allowed and one past the ceiling is rejected.
  **Shown failing before the fix**: all 3 parametrized cases raised
  `retry allowance exhausted (3/3)` when `attempt == max_attempts`. After the
  fix all 3 pass.
- `test_retry_allowance_is_bounded` — corrected: it previously *asserted* the
  buggy behaviour (`attempt=3, max_attempts=3` must raise). It now rejects
  `attempt=4` with `"exceeds max_attempts"`.

## Changed files

- `src/legal_ai/orchestration/state_machine.py` (1-line condition change)
- `tests/orchestration/test_state_machine.py` (regression test + corrected
  enshrined-bug test)

## Out of scope

No change to any other file, no feature work, no refactor of other guards.

## Validation

```
uv run ruff check .           # All checks passed
uv run ruff format --check . # 188 files already formatted
uv run mypy .                # Success: no issues found in 188 source files
uv run pytest -m "not integration" -q  # 1199 passed, 49 skipped, 100 deselected
```

## Rollback

Revert commit `4585c13` (or `git checkout fa9ace1 -- <the two files>`). The
guard and test both return to the previous state; no other file is affected.