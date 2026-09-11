# Phase 5 consolidation — integrate/main-2026-09-09

Base ref: `main` (6f47c3f). HEAD: `feat/scope-boundary-enforcement` (9f6f60e),
0 behind / 40 ahead of main, main a direct ancestor. This is a consolidation of
a linear stack, not a merge negotiation.

This document is the requirements/description for the end-to-end review of the
whole 40-commit stack (production source under `src/`). It is the first review
of the stack as one unit; each task was already reviewed individually.

## What the stack delivers

- **Live provider chain with independent entailment verification.** A
  provider-neutral answer service over an ordered chain
  (`openrouter+deepseek+openrouter`) with level-3 entailment run on a *different*
  provider than the one that answered, so a model never marks its own work.
  Every failure path is fail-closed to a typed refusal.
- **Per-proposition answers.** The level-3 decision is per proposition, not per
  answer: supported propositions are returned with their citations; an
  unsupported or unverifiable one is dropped and named with its reason; a wholly
  unsupported answer still refuses entirely. The withheld statement text is never
  rendered into a response.
- **Deterministic scope enforcement.** Contract/document review and drafting
  requests (MVP_ROADMAP section 11) are classified from the question text and
  refused before any retrieval or model call, with `REQUEST_OUT_OF_SCOPE`,
  audited like every other refusal.
- **The WA corpus and single-command ingestion path.** Six recorded WA Acts /
  19 provisions as digest-chained fixtures, with `scripts/ingest_wa_act.py`
  as the single-command ingestion path.

## Review scope

Production source only (`src/`, 27 files, no binary). Tests, docs, and fixtures
are excluded from the reviewed diff because the full 40-commit diff (1.9 MB, 158
files, including binary PDFs) exceeds the gate's 300 KB text-only limit; they are
covered by the passing DoD suite (ruff, ruff format, mypy, pytest).

## Accepted residuals already recorded (do not re-litigate)

- `partial-omission-legal-completeness` — owner decision, deferred, in
  `ENTAILMENT_FALSE_NEGATIVE_FIX_SCOPE_CARD.md`.
- `SCOPE-001` / `SCOPE-002` / `SCOPE-003` — tracked residuals in
  `SCOPE_BOUNDARY_ENFORCEMENT_SCOPE_CARD.md`.

## Stack-level review gate — reviewed-and-rejected findings (2026-09-09)

The DeepSeek gate was run once against `main` as base ref, reviewing the whole
40-commit change (production source under `src/`) as one unit — the first review
of the stack end to end. It returned `BLOCKED` on three high findings. All three
were reviewed and **rejected** by the owner (Ali Rad, 2026-09-09) with the
evidence below. They are recorded here so a later stack-level review does not
raise them cold.

- **OPENROUTER_BASE_PATH_MISHANDLING — rejected, factually wrong.** The gate
  claimed `client.stream("POST", "/chat/completions")` with base_url
  `https://openrouter.ai/api/v1` drops the `/api/v1` prefix (an `urljoin`
  behaviour). `httpx` does not do this: `httpx.Client(base_url=".../api/v1")
  .build_request("POST", "/chat/completions").url` is
  `https://openrouter.ai/api/v1/chat/completions` — the prefix is preserved
  (verified on httpx 0.28.1). Corroborated operationally: the OpenRouter chain
  answered and billed real usage across every live campaign in this stack
  (`LIVE_ADVERSARIAL_RUN.md`, `LIVE_ADVERSARIAL_RUN_2.md`, and the per-answer
  cost measurement). No code change.

- **STATE_MACHINE_RETRY_BYPASS — rejected, re-litigates an accepted ADR fix.**
  The gate wanted the retry guard reverted from `attempt > max_attempts` to
  `attempt >= max_attempts`. The `>` form is the deliberate ORCH-001 fix
  (`ORCHESTRATION_RETRY_FIX_SCOPE_CARD.md`; ADR 0016 accepted): `max_attempts = N`
  must allow exactly N attempts, and `>=` was the off-by-one that gave only
  N − 1. The ceiling is still enforced — the top-of-function guard rejects
  `attempt > max_attempts`, and a retry to attempt N + 1 is refused. The exact
  boundary the gate calls untested is covered by
  `tests/orchestration/test_state_machine.py::test_exact_retry_attempt_counts`
  (parametrised over max_attempts 1/2/3). Reverting would reintroduce the bug and
  fail that test. No code change.

- **AUDIT_FAILURE_HTTP_200 — rejected, documented and previously reviewed.** The
  gate wanted `RESEARCH_TERMINATED` mapped to HTTP 503. The research route
  documents the opposite by design: a refusal is a correct, successful outcome of
  the contract and returns 200 with an explicit `REFUSED` body; only a service
  that cannot be configured is a 503 server-side unavailability. A terminal
  audit-sink failure is fail-closed (it refuses; it never answers, leaks, or
  emits a citation). This behaviour shipped and passed the Phase 5 route review.
  Revisiting the 200-vs-503 choice for a runtime audit failure is a reasonable
  future refinement, not a regression introduced by this stack. No code change.

Note on review scope: tests, docs, and fixtures were outside the reviewed diff
(the full 40-commit diff is 1.9 MB / 158 files including binary PDFs, over the
gate's 300 KB text-only limit); they are covered by the passing DoD suite.

## Known open items NOT in this stack

- The temporal/version gap (answers from the snapshot without a currency caveat).
- The extraction-boundary defect and its Schedule-collision guard.
- 8 further WA Acts parked on `feat/corpus-batch-2`.

## Readiness

A prototype. The corpus is mock-free but has not been reviewed at scale. This is
not a production legal service and must not make final legal decisions.
