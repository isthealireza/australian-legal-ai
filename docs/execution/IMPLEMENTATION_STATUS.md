# Implementation Status — Phase Ledger

**Last updated:** 2026-08-07

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **Completed** (merged to `main` @ `8766468e00be2dc79b7eda08baec713d5356654d`, PR #9) |
| Phase 2 — Playbook registry and WA motor playbook | **Completed** (merged to `main` @ `3faad98e6fdb3a3c6a6fa40439717fa0dc66d942`, PR #11) |
| Phase 3 — Evidence vault extension | **Completed** (merged to `main` @ `bb587538afed8e96c116d9952ae3dad0217c1534`, PR #17) |
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
- ADR 0010: **Accepted** (2026-08-04); prospectively authorises the bounded
  Phase 2 implementation for completion and merge review from that date
- ADR 0012: **Accepted** (2026-08-06); Matter Evidence Vault and Safe Upload
  Boundary
- Phase 1 Generic Casework Core: **Completed** on `main`
- Phase 2 Versioned Playbook Framework: **Completed** on `main` via PR #11 @
  `3faad98e6fdb3a3c6a6fa40439717fa0dc66d942`
- Phase 2 WA motor scope is limited to parked/unattended vehicle property
  damage; unsupported and definition-disqualified matters fail closed to
  `RESEARCH_AND_DRAFT_ONLY` where the pinned definition requires it
- Phase 2 boundaries respected: L0–L2 only; no product playbook activation; no
  LLM, email, OAuth, external actions, FastAPI/UI, pgvector, production
  deployment, real client data, or L3+ execution
- `wa_motor_property_damage_v1` seeded as validated **DRAFT** only
- Phase 3 Matter Evidence Vault: **Completed** on `main` via PR #17 @
  `bb587538afed8e96c116d9952ae3dad0217c1534`
- Phase 3 completed: matter-scoped evidence vault; reuse of the immutable
  content-addressed provenance artifact store; safe bounded upload validation;
  PNG/JPEG/MP4/strict UTF-8 initial allowlist; original and derived evidence
  provenance; single-source derivation; human terminal evidence review;
  pinned-version checklist associations; matter isolation; fail-closed audit
  behaviour; closed-matter write restrictions; Alembic head `0007_evidence_vault`
- Phase 3 did **not** add: Phase 4 research or evidence packets; PDF/archive
  support; OCR; computer vision; biometric processing; malware-safety claims;
  authenticity/admissibility assessment; live model interpretation; UI or
  FastAPI; email/external dispatch; OAuth; production object storage; cloud
  deployment; real client data; or L3+ authority

## Phase 2 implementation branch and baseline (historical)

- **Historical feature branch:** `feat/phase-2-playbook-framework`
- **Starting main SHA:** `5498cfd6e246e03defc4bfbf2b0b709780c0b3d4`
- **Merge commit:** `3faad98e6fdb3a3c6a6fa40439717fa0dc66d942` (PR #11)
- **Implementation CI:** GitHub Actions run `31020315828` completed successfully
  on the merge commit, including secret scan, lint, formatting, strict mypy,
  unit tests, and PostgreSQL integration tests
- **Alembic source head:** `0006_playbook_framework`
- **Completion ledger:** PR #12 merged to `main` @
  `960793410fc33c40501e3a92adb6ee41b6669eb7`

## Phase 3 implementation branch and baseline (historical)

- **Historical feature branch:** `feat/phase-3-evidence-vault`
- **Starting main SHA:** `fa89313f6c0524227f0305c48bae294332822ae1`
- **Implementation commit:** `7d3c7ba641f75d59190276f77ab6d00a99467a84`
- **Implementation PR:** #17
- **Merge commit:** `bb587538afed8e96c116d9952ae3dad0217c1534`
- **Post-merge CI:** GitHub Actions run `31162082164` completed successfully
  on the merge commit
- **Alembic source head:** `0007_evidence_vault`
- **Validated implementation evidence:**
  - unit tests: 639 passed, 1 skipped;
  - PostgreSQL integration tests: 144 passed;
  - focused evidence suite: 44 passed;
  - migration regression suite: 18 passed;
  - Ruff passed;
  - formatting check passed;
  - strict mypy passed;
  - full-history secret scan passed.

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

1. No product playbook may become ACTIVE until Phase 4 grounding gate is met.
2. Every L3+ capability remains blocked until a dedicated ADR and controls exist.

## Exact next action

Phase 3 is **Completed**. Phase 4 remains **Not Started**. This ledger update
does not authorise Phase 4 implementation. Phase 4 requires a separately
owner-authorised architecture or planning task before any implementation work.
No current authorization exists for Phase 4 code.
