# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **Implementation Complete; Merge Pending** |
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

- ADR 0009: **Accepted** (2026-07-28)
- `MVP_ROADMAP.md` §11A: Casework Phase 1 foundation authorised after approved plan
- Phase 1 final corrected plan: implemented on `feat/phase-1-casework-core`
- Phase 1 boundaries: Generic Casework Core only (L0–L2); no playbooks, LLM, email,
  evidence binaries, FastAPI/UI, pgvector, L3+, or real client data
- Phase 2: **Not Started**

## Branch and baseline

- **Branch:** `feat/phase-1-casework-core`
- **Starting main SHA:** `9cd74bad53f774dabaf976cbd47325335bf133d9`
- **Status rule:** do not mark Phase 1 **Completed** until the implementation PR is
  merged; then update the ledger on `main` via a docs-only follow-up with PR number
  and merge SHA

## Local validation evidence (implementation branch)

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
uv run --locked pytest -q --ignore=tests/integration
LEGAL_AI_TEST_DATABASE_URL=... uv run --locked pytest -q tests/integration
```

Integration suite executed against disposable `postgres:16-alpine` on localhost.

## Blockers and approval gates

1. Push/PR/merge require separate owner publication authorisation.
2. Phase 1 **Completed** only after merge + docs follow-up on `main`.
3. Every L3+ capability blocked until a dedicated ADR and controls exist.

## Exact next action

Owner review and publication of `feat/phase-1-casework-core`. Do not start Phase 2.
