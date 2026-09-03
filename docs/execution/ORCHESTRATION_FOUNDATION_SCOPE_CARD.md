# Orchestration Foundation Scope Card

**Branch:** `feat/orchestration-foundation` (based on `feat/phase-5-grounded-answer-api` @ `44138ab`)
**Governing decision:** [ADR 0016](../adr/0016-agent-orchestration-foundation.md) (Proposed)
**Authority level:** L0 — deterministic, read-only, no I/O
**Status:** implemented, validated, reviewed by the Codex review worker; **not merged**, awaiting ADR acceptance and an explicit merge instruction

## Goal

Make the rules that govern multi-agent work on this repository executable
instead of remembered. A bounded task contract becomes a type; a worker role
becomes a configuration that denies writes by default; task states become a
total, deterministic machine; worker output becomes untrusted data that is
validated before it is believed.

## Delivered

| Path | Purpose |
|---|---|
| `src/legal_ai/orchestration/types.py` | Roles, access modes, task states, message types, the `ProductCapability` deny list, the autonomy vocabulary |
| `src/legal_ai/orchestration/errors.py` | Typed orchestration failures |
| `src/legal_ai/orchestration/roles.py` | Role configuration; default-deny write access; rejecting path normalisation |
| `src/legal_ai/orchestration/contracts.py` | `BoundedTaskContract`, `WorkerMessage`, `WorkerResult`, `AcceptedWorkerResult`, `validate_worker_result` |
| `src/legal_ai/orchestration/state_machine.py` | Total task lifecycle transitions with dependency and bounded-retry guards |
| `src/legal_ai/orchestration/graph.py` | Bounded acyclic DAG, stable topological order, `ready_task_ids` |
| `src/legal_ai/orchestration/approvals.py` | The owner autonomy boundary recorded 2026-09-03, fail-closed |
| `src/legal_ai/orchestration/__init__.py` | Package export surface |
| `tests/orchestration/` | 94 deterministic unit tests — no network, no clock, no database |
| `docs/adr/0016-agent-orchestration-foundation.md` | Decision record |
| `docs/adr/README.md` | One appended index line |
| `docs/execution/ORCHESTRATION_FOUNDATION_SCOPE_CARD.md` | This card |

## Out of scope — deliberately not done

Contract Builder · any tool for the product's legal-answering model · database
persistence of orchestration state · authentication · corpus expansion · live
retrieval · any change to a Phase 0–5 module or to existing API behaviour · any
L2+ authority · calling the Orca CLI or any network from the package · pushing,
merging or tagging.

## Acceptance criteria

1. A bounded task contract without acceptance criteria cannot be constructed. — **met**
2. A contract above L1 authority, or naming any `ProductCapability`, is refused at construction. — **met**
3. Every role's default configuration denies write access. — **met**
4. Write access widens only through an exact canonical path allowlist; traversal, absolute, drive-qualified, non-NFC, control-character, reserved-device-name and trailing dot/space spellings are refused. — **met**
5. The task state machine is total: every state is enumerated, `COMPLETED` is terminal, an undeclared edge is refused. — **met**
6. `READY` requires satisfied dependencies; retries are bounded, and the exported guard enforces the ceiling without a contract. — **met**
7. A worker result naming another task, claiming an ungranted role, or reporting a file outside its allowlist is rejected — including when the outcome is `FAILED`. — **met**
8. `AcceptedWorkerResult` cannot be forged by direct construction or `model_validate`. — **met**
9. The DAG is bounded, acyclic, and stably ordered; `ready_task_ids` requires a state map covering exactly the graph. — **met**
10. An activity the approval boundary does not recognise is protected, not autonomous. — **met**
11. Existing API behaviour is unchanged and no existing test changes. — **met**
12. All repository gates pass. — **met**

## Validation

```
uv run ruff check .                  # All checks passed!
uv run ruff format --check .         # 174 files already formatted
uv run mypy .                        # Success: no issues found in 174 source files
uv run pytest -m "not integration"   # 1021 passed, 46 skipped, 100 deselected
```

No test opens a socket, reads a clock, or touches a database. The package
performs no I/O at all.

## Orchestration record

Orca Run `run_e1fe1d6e711e`. Four-task DAG:

| Task | Owner | Deps | Outcome |
|---|---|---|---|
| `task_9683b5d3cfc7` T1 implement | Claude Code (coordinator) | — | completed |
| `task_a3c2a75a045c` T3 provider/model evaluation | OpenCode / DeepSeek, read-only | — | completed, dispatch `ctx_c90223019216` |
| `task_157ef6048749` T2 architecture/review/test review | Codex, review-only | T1 | completed, dispatch `ctx_e8323b1050eb` |
| `task_0e82401f66d6` T4 integrate | Claude Code (coordinator) | T2, T3 | completed |

Each worker ran in its own top-level git worktree on its own branch, so no
worker ever held write access to the coordinator's implementation files.

## Worker findings and disposition

**Codex (T2), review-only.** Three findings, all accepted and fixed in this
branch:

1. *Blocking* — `AcceptedWorkerResult` was a public frozen model, so it could be
   constructed directly without ever running the check the ADR claimed it
   proved. Fixed: the consistency check re-runs in the model validator.
2. *Blocking* — path authorisation was lexical and accepted trailing dot/space
   and non-NFC spellings, and never considered symlinks. Fixed for every
   name-level case; symlink resolution is recorded in ADR 0016 as an accepted
   limitation, because the module is pure and worktree isolation is the real
   barrier.
3. *Valid non-blocking* — the exported state-machine guard did not enforce the
   retry ceiling itself. Fixed: `MAX_ATTEMPTS_CEILING` moved to `types.py` and
   enforced in both places.

**OpenCode / DeepSeek (T3), read-only.** Evaluation of provider neutrality in
the Phase 5 answering module. Recorded here as **deferred**, not actioned: it
concerns Phase 5 files that are outside this task's scope. Its substantive
points, for whoever owns the next provider slice:

- The contract layer is genuinely provider-neutral; coupling to OpenRouter is
  concentrated in `api/main.py` `_resolve_model` / `_resolve_verifier`, the
  closed two-value `AnswerModelChoice` enum, and the verifier's reuse of the
  adapter's bounded-read helper. A swap within OpenAI-compatible wires is one
  adapter; a swap to a native SDK is a code change in four places.
- Recommended role split: drafting model, an independent entailment verifier,
  and an operator-only review model that never enters the product request path.
- No automatic cross-provider failover: a fallback chain would break audit
  identity and determinism.
- ADR 0015 records level-3 entailment as independent *in prompt and call* but
  not *in vendor*. That remains an open question for the owner.

**Correction to this task's own brief.** The T3 spec named
`answering/providers/registry.py` and `answering/providers/chain.py`. The worker
reported they do not exist, and it is right: they are untracked local files in
the `D:/Projects/australian-legal-ai` checkout and are on no branch. The spec
was written from a directory listing that included untracked files.

## Risks

- ADR 0016 is **Proposed**, not accepted. Merging before acceptance would breach
  `ENGINEERING_WORKFLOW.md` §2.
- The branch is stacked on the unmerged `feat/phase-5-grounded-answer-api`. It
  must not merge before Phase 5 does, or it will carry Phase 5 with it.
- The module describes coordination but does not enforce it at runtime. Nothing
  yet makes an Orca dispatch pass through `BoundedTaskContract`; that binding is
  a separate, unauthorised slice.
- `CLAUDE.md` and `AGENTS.md` are untracked, so a fresh worktree does not
  receive the review-gate instructions they carry. Out of scope to fix here;
  flagged for the owner.
- The DeepSeek review gate in `.claude/commands/deepseek-review.md` was not run
  for this slice. The external review used was the Codex review worker.

## Rollback

```
git checkout feat/orchestration-foundation
git revert 1c1ef32 <integration-commit>
# or simply drop the branch: it is unmerged and unpushed
git branch -D feat/orchestration-foundation
```

Deleting `src/legal_ai/orchestration/`, `tests/orchestration/`, ADR 0016, this
card and the one appended `docs/adr/README.md` line restores the tree exactly.
No migration runs, no data changes, and nothing imports the package, so removal
leaves no residue.
