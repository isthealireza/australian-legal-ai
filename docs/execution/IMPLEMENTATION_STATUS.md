# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** |
| Phase 1 — Generic matter core | **Approved to plan; Not Started** |
| Phase 2 — Playbook registry and WA motor playbook | Not Started |
| Phase 3 — Evidence vault extension | Not Started |
| Phase 4 — Research and evidence packets | Not Started |
| Phase 5 — Drafting with mock model | Not Started |
| Phase 6 — Approval service | Not Started |
| Phase 7 — Communication ingestion and draft replies | Not Started |
| Phase 8 — Approved email sending | Not Started |
| Phase 9 — Durable workflow ADR and implementation | Not Started |
| Phase 10 — Private-alpha API and UI | Not Started |
| Phase 11 — Live model evaluation | Not Started |
| Phase 12 — Private-alpha deployment preparation | Not Started |

## Current approved scope

- ADR 0009: **Accepted** (owner-approved 2026-07-28)
- Phase 0 documentation: **Completed**
- `MVP_ROADMAP.md` §11A: owner-authorised Casework expansion gate
- Phase 1: **Approved to plan only**. Implementation requires a separate
  bounded Phase 1 plan before any product-code changes under `src/`, `tests/`,
  or `alembic/`.
- Phases 2–12: Not Started
- No live external actions, production deployment, real client data, OAuth,
  email sending, insurance/police submissions, settlement, admission,
  signature, court filing, L3+ execution, or L5/L6 autonomy

## Branch and baseline

- **Branch:** `docs/phase-0-casework-os-audit`
- **Baseline commit:** `1ef936fab780f5d03867a3c9beffa4e5fd859b47` (`origin/main`)
- **Phase 0 docs commit:** `cd78afdd5fc3a607975ccb8b88a373af3fab22e8`
- **Finalisation commit:** recorded after this ledger update is committed

## Blockers and approval gates

1. Phase 1 product code blocked until a separate bounded Phase 1 plan is
   approved (ADR 0009 + §11A authorise planning only).
2. Every L3+ capability blocked until a dedicated ADR and controls exist.
3. Live providers, OAuth, real personal data, and external deployment require
   explicit owner gates.
4. No autonomous admission, settlement, signature, court filing, police
   submission, insurance submission, or external communication.

## Authority precedence (confirmed)

```text
CLAUDE.md
  → docs/execution/MVP_ROADMAP.md (incl. §11A)
  → AGENTS.md
  → LEGAL_AI_MASTER_BLUEPRINT.md (north star; does not override CLAUDE/MVP)
  → ADR 0009 (Accepted Casework direction + Phase 1 foundation gate)
  → docs/execution/CASEWORK_OS_ROADMAP.md (Casework workstreams only)
  → task / phase plans
```

## Decisions (Phase 0)

- Extend repository in place; preserve FRL, provenance, EPUB, legislation modules
- First operational playbook: `wa_motor_property_damage_v1`
- Explicit state machine before any Temporal ADR
- L3+ external actions remain gated behind dedicated ADRs and owner credentials
- System is not a lawyer and must not independently represent, determine
  liability, admit, settle, sign, file, submit, or send sensitive externals

## Validation evidence

Commands required before Phase 0 finalisation commit:

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
uv run --locked pytest -q --ignore=tests/integration
git diff --check
git diff main...HEAD --stat
```

Expected unit-test baseline from Phase 0 docs commit: 509 passed, 1 skipped
(integration tests skipped; require disposable Postgres).

Finalisation validation (2026-07-28, before this commit):

```text
uv run --locked ruff check .                         → All checks passed
uv run --locked ruff format --check .                → 41 files already formatted
uv run --locked mypy .                               → Success: 41 source files
uv run --locked pytest -q --ignore=tests/integration → 509 passed, 1 skipped
```

## Residual risks

- Stale README relative to implemented Sprint 1.x code (intentionally unchanged)
- Phase 1 must not begin without a separate bounded plan
- L3/L4 email phases must not ship without dedicated controls
- Integration/CI database coverage remains thin for future matter isolation

## Exact next action

Stop. Do not start Phase 1 implementation. Next owner/agent step is a separate
Phase 1 plan only, after this branch is reviewed.
