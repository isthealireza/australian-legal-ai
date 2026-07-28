# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **Completed** (merged to `main` @ `8766468e00be2dc79b7eda08baec713d5356654d`, PR #9) |
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
- Phase 1 Generic Casework Core: **Completed** on `main`
- Phase 1 boundaries respected: L0–L2 only; no playbooks, LLM, email, OAuth,
  external actions, FastAPI/UI, pgvector, production deployment, real client data,
  or L3+ execution
- Phase 2: **Not Started**

## Phase 1 completion evidence

- **Implementation PR:** [#9](https://github.com/isthealireza/australian-legal-ai/pull/9)
- **PR URL:** https://github.com/isthealireza/australian-legal-ai/pull/9
- **Merge commit:** `8766468e00be2dc79b7eda08baec713d5356654d`
- **Merged at:** 2026-07-28T04:02:20Z
- **Successful CI run:** [30325948037](https://github.com/isthealireza/australian-legal-ai/actions/runs/30325948037) — conclusion **success**
- **CI URL:** https://github.com/isthealireza/australian-legal-ai/actions/runs/30325948037
- **Unit tests (implementation / PR #9):** 556 passed, 1 skipped
- **PostgreSQL integration (implementation / PR #9):** 40 passed
- **Ruff, formatting, Mypy, Gitleaks:** passed on PR #9 CI
- **Alembic source head:** `0005_casework_core`

### Capabilities completed

- Generic Casework Core (matters, parties, facts, issues, tasks, deadlines, audit)
- Matter isolation implemented and tested (direct and indirect cross-matter attacks)
- Audit immutability enforced in application transactions and by PostgreSQL triggers
- Optimistic concurrency, state machine, and L0–L2 authority gates

## Blockers and approval gates

1. Phase 2 planning and implementation require separate owner authorisation.
2. Every L3+ capability blocked until a dedicated ADR and controls exist.

## Exact next action

Do not start Phase 2 until separately authorised. No deployment or non-test
database migration is authorised by Phase 1 completion.
