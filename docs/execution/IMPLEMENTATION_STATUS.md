# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **Completed** (merged to `main` @ `8766468e00be2dc79b7eda08baec713d5356654d`, PR #9) |
| Phase 2 — Playbook registry and WA motor playbook | **Implementation Complete; Merge Pending** |
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
- Phase 1 Generic Casework Core: **Completed** on `main`
- Phase 2 Versioned Playbook Framework: implemented on `feat/phase-2-playbook-framework`
- Phase 2 boundaries respected: L0–L2 only; no product playbook activation; no LLM,
  email, OAuth, external actions, FastAPI/UI, pgvector, production deployment, real
  client data, or L3+ execution
- `wa_motor_property_damage_v1` seeded as validated **DRAFT** only
- Phase 3: **Not Started**

## Branch and baseline

- **Branch:** `feat/phase-2-playbook-framework`
- **Starting main SHA:** `5498cfd6e246e03defc4bfbf2b0b709780c0b3d4`
- **Alembic source head:** `0006_playbook_framework`
- **Status rule:** do not mark Phase 2 **Completed** until the implementation PR
  is merged; then update the ledger on `main` via a docs-only follow-up

## Grounding security boundary

Grounding is application-enforced via `FailClosedGroundingGate` on every
activation path. PostgreSQL enforces lifecycle and payload immutability but
does not validate legal grounding. Privileged direct database access is outside
the application policy boundary.

## Local validation evidence (implementation branch)

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
uv run --locked pytest -q --ignore=tests/integration
LEGAL_AI_TEST_DATABASE_URL=... uv run --locked pytest -q tests/integration
```

Integration suite executed against disposable `postgres:16-alpine`.

## Blockers and approval gates

1. Push/PR/merge require separate owner publication authorisation.
2. Phase 2 **Completed** only after merge + docs follow-up on `main`.
3. No product playbook may become ACTIVE until Phase 4 grounding gate is met.
4. Every L3+ capability blocked until a dedicated ADR and controls exist.

## Exact next action

Owner review and publication of `feat/phase-2-playbook-framework`. Do not start
Phase 3. Do not push or open a PR without separate authorisation.
