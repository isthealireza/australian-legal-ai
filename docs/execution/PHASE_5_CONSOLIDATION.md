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

## Known open items NOT in this stack

- The temporal/version gap (answers from the snapshot without a currency caveat).
- The extraction-boundary defect and its Schedule-collision guard.
- 8 further WA Acts parked on `feat/corpus-batch-2`.

## Readiness

A prototype. The corpus is mock-free but has not been reviewed at scale. This is
not a production legal service and must not make final legal decisions.
