# ADR 0016: Agent Orchestration Foundation

- Status: Proposed
- Date: 2026-09-03
- Accepted: not yet accepted — owner authorisation required before merge
- Builds on: [ADR 0011](0011-governance-and-engineering-terminology.md)
- Base: `main`. This slice is independent of the Phase 4/5 line; its only
  cross-module import is `legal_ai.casework.types` (Phase 1).
- Governed by: `PROJECT_GOVERNANCE.md` §9, `ENGINEERING_WORKFLOW.md` §1–4

## Context

More than one agent now works on this repository. Claude Code owns
implementation and coordination; Codex acts as a review worker; OpenCode running
DeepSeek acts as an evaluation worker. Coordination happens through Orca
orchestration Runs, Tasks and Dispatches.

That arrangement was working, but nothing in the repository described it. The
rules that keep it safe — one bounded task per contributor, two contributors
never holding write access to the same files, workers being review-only unless
a task names the exact files, worker output being untrusted until checked —
lived only in prose in `PROJECT_GOVERNANCE.md` and `ENGINEERING_WORKFLOW.md`,
and in whichever prompt happened to be typed that day.

Prose cannot fail closed. A rule that is not executable is a rule that is
followed only when someone remembers it.

`docs/execution/MVP_ROADMAP.md` §5 lists "multi-agent orchestration" under
**Not now**. That entry is about the *product*: it forbids the legal-answering
system from becoming a multi-agent runtime. This ADR does not touch it. What is
described here is a repository engineering-governance module, imported by
nothing in the answering pipeline or the HTTP API.

## Decision

### 1. A bounded task contract is a type, not a paragraph

`BoundedTaskContract` carries the fields `ENGINEERING_WORKFLOW.md` §1 already
requires — objective, in-scope and out-of-scope, acceptance criteria, rollback
instructions — plus the ones that make it enforceable: the role it authorises,
its access mode, and the exact repository-relative file allowlist. A contract
with no acceptance criteria cannot be constructed.

Two limits are enforced at construction:

- `authority_level` may not exceed **L1**. Coordinating engineering work is
  read-only research or an internal reversible action. A contract cannot quietly
  become the vehicle for an L2+ action.
- `granted_product_capabilities` must be empty. `ProductCapability` — shell,
  browser, email, unrestricted network, unrestricted filesystem, persistent
  memory, self-modification, Contract Builder — is a deny list, and naming any
  member is a construction error. This restates `ENGINEERING_WORKFLOW.md` §13
  and `PROJECT_GOVERNANCE.md` §7 as code.

### 2. Write access is denied by default and never widens implicitly

Every role's default configuration is `READ_ONLY` or `REVIEW_ONLY` with an empty
allowlist, including the coordinator's. A role writes only when a contract sets
`SCOPED_WRITE` *and* names the exact path.

The allowlist holds canonical repository-relative paths and is compared by exact
match. There are no globs and no prefix rules, so allowlisting
`docs/adr/0016-agent-orchestration-foundation.md` does not allowlist
`docs/adr/`.

Normalisation rejects rather than repairs. Traversal, absolute and
drive-qualified paths, backslashes, alternate data streams, non-NFC Unicode,
control characters, Windows reserved device names, and the trailing dot or space
that NTFS silently strips are all refused, because repairing a name is exactly
what would let an allowlist authorise a different file.

**Accepted limitation.** `normalise_repo_path` is pure and does no filesystem
I/O, so it does not resolve symlinks: on a case-insensitive filesystem, or where
an allowlisted path is a symlink, the name check alone can authorise a different
object. Resolving would make the function environment-dependent and
non-deterministic, which costs more than it buys here, because the name check is
not the only barrier — each worker runs in its own git worktree on its own
branch and cannot reach the coordinator's files at all. A future slice that
enforces the allowlist against a live working tree must add resolution there.

This is the executable form of `PROJECT_GOVERNANCE.md` §9.3: two contributors
never hold simultaneous write access to the same files.

### 3. Task state transitions are total and deterministic

`TaskState` mirrors the Orca task statuses, so a node in this module and the
Orca task row it corresponds to cannot disagree. Every edge is enumerated; an
unknown state has no outgoing edges and therefore fails closed. Two guards
apply: a task reaches `READY` only when every dependency has completed, and a
`FAILED` task re-enters `READY` only while its bounded retry allowance remains.
`COMPLETED` is terminal.

The guard enforces the retry ceiling itself rather than trusting
`BoundedTaskContract` to have capped it, because the function is exported and a
caller that never built a contract must not be able to grant itself more
attempts.

### 4. Worker messages and results are untrusted data

`WorkerMessage` and `WorkerResult` are the schemas for what comes back through
Orca. They are treated exactly as retrieved content is treated under
`PROJECT_GOVERNANCE.md` §6: data, never instruction.

The consistency check rejects a result naming another task, a result claiming
a role its contract did not grant, a read-only or review-only worker that
reports having modified anything, and any modified path outside the contract's
allowlist. A `FAILED` outcome is validated on the same terms — a worker cannot
escape its file scope by reporting failure.

`AcceptedWorkerResult` re-runs that check in its own validator rather than
relying on `validate_worker_result` being the only caller. A public frozen
Pydantic model has a public constructor, and `frozen` prevents mutation, not
construction; re-checking is what makes the type's guarantee true however it was
built. The one gap is Pydantic's: `model_copy` does not re-run validators, which
the type documents and a test pins.

### 5. The DAG is bounded and its order is stable

`build_task_graph` validates unique ids, resolvable dependencies, and acyclicity
at construction, and caps the graph at 32 tasks: a bounded slice has a bounded
plan, and a larger one is a scope change requiring owner approval. Ordering uses
Kahn's algorithm over lexicographically sorted ids, so the same set of contracts
always produces the same order. `ready_task_ids` requires a state map covering
exactly the graph, so a missing or stray state is an error rather than a silent
`False`.

### 6. The autonomy boundary is recorded, not remembered

`approvals.py` records the owner decision of 2026-09-03. Routine engineering —
task decomposition, worker dispatch, read-only review, test execution, bounded
retries, deterministic validation, in-scope documentation, integrating worker
findings — proceeds without pausing. Seven protected decisions never become
automatic: scope change, governance/security/grounding/fail-closed/privacy
control change, real client data or secrets, external publication or deployment,
merge to a protected branch, legal-content acceptance, and any action with
material external side effects.

`requires_owner_approval` fails closed: an activity it does not recognise is
protected, not autonomous.

## Consequences

**Kept.** Fail-closed legal grounding, deterministic citation and provenance,
the permanent disclaimer and the audit controls are untouched. No existing file
changes anywhere in `src/` or `tests/` — the diff against `main` adds new paths
only, plus one appended line in the ADR index. Nothing imports this package, so
every existing surface behaves identically.

**Gained.** The rules that keep multi-agent work safe are now executable and
tested, so violating one is a raised exception rather than a missed paragraph.

**Cost.** The module describes coordination; it does not perform it. Orca
remains the transport, and nothing here calls the Orca CLI or any network. A
future slice could bind the two, but that binding is not authorised here.

**Deliberately excluded.** Contract Builder. Any product-model tool. Database
persistence of orchestration state. Authentication. Corpus expansion. Any
change to Phase 0–5 behaviour. Any L2+ authority. Pushing, merging or tagging.

## Rollback

Delete `src/legal_ai/orchestration/`, `tests/orchestration/`, this ADR and
`docs/execution/ORCHESTRATION_FOUNDATION_SCOPE_CARD.md`. No other file changes,
no migration runs, and no existing behaviour depends on the package, so removal
is complete and leaves no residue.
