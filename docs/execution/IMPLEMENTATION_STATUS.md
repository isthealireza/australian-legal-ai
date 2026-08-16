# Implementation Status — Phase Ledger

**Last updated:** 2026-08-15

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **Completed** (merged to `main` @ `8766468e00be2dc79b7eda08baec713d5356654d`, PR #9) |
| Phase 2 — Playbook registry and WA motor playbook | **Completed** (merged to `main` @ `3faad98e6fdb3a3c6a6fa40439717fa0dc66d942`, PR #11) |
| Phase 3 — Evidence vault extension | **Completed** (merged to `main` @ `bb587538afed8e96c116d9952ae3dad0217c1534`, PR #17) |
| Phase 4 — Research and evidence packets | **Slice 1 Completed** (merged to `main` @ `d758ae7769282aedd188705ac2de8b432880d1a3`, PR #22); Slice 2 **Not Started** and not authorised — see "Phase 4 Slice 1 implementation" below |
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
- ADR 0013: **Accepted** (2026-08-11); Phase 4 Research and Evidence Packets —
  first slice
- Phase 4 Slice 1 WA Research and Evidence Packets: **Completed** on `main` via
  PR #22 @ `d758ae7769282aedd188705ac2de8b432880d1a3`
- Phase 4 Slice 2 is **not authorised**. It requires a separate owner-approved
  bounded scope and a separate architecture decision before any planning or
  implementation work begins

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

## Phase 4 fixture-recording prerequisite (completed)

This records a completed, bounded, documentation-and-fixture **prerequisite**
only. It was **not** Phase 4 implementation. The Phase 4 Slice 1 implementation
that followed it is recorded separately in "Phase 4 Slice 1 implementation
(completed)" below.

- The bounded Phase 4 WA fixture-recording task is **complete**.
- **PR #20** was merged into `main`.
- **Merge commit:** `d6899e65a803b0322532e0c49bb33d7f808a2633`.
- The recorded fixture is the **byte-exact consolidated Road Traffic Act 1974
  (WA) PDF**, version `14-t0-00`.
- Sections **55** and **56** are recorded as **manifest pinpoints** only.
- Fixture **SHA-256:**
  `61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525`.
- The closed HTTPS hostname allowlist contains exactly:
  - `legislation.wa.gov.au`
  - `www.legislation.wa.gov.au`
- The recorded fixture **is not a live legal-currency service**.
- **Section-level extraction and validation remain unimplemented.**
- This task implemented **no** live retrieval adapter, runtime network path,
  model use, persistence, database or object-store write, migration, Evidence
  Vault write, playbook activation, external action, API, or UI.

## Phase 4 Slice 1 implementation (completed)

The bounded, owner-authorised Phase 4 Slice 1 implementation task is
**Completed** and **merged to `main`**.

- **Historical feature branch:** `feat/phase-4-slice-1`
- **Base commit:** `159a695d4a2916bcc8384a9b6275a2d36e8cd5a3`
- **Implementation PR:** #22
- **Reviewed PR head:** `c7ced535d0dea98a1a3e518f3a9a2f3fd20ff089`
- **Merge commit:** `d758ae7769282aedd188705ac2de8b432880d1a3`
- **Implementation record:** [Phase 4 Slice 1 Implementation](PHASE_4_SLICE_1_IMPLEMENTATION.md)
- **Added surface:** standalone deterministic research module
  `src/legal_ai/research/`; test-only in-memory audit sinks
  `tests/support/research_audit.py`; unit, integration, negative, and
  adversarial tests under `tests/research/`
- **Validated implementation evidence:** Ruff passed; formatting check passed;
  strict mypy passed (127 source files); 821 passed, 144 skipped (baseline was
  640 passed, 144 skipped; the 144 skips are the PostgreSQL integration suite,
  which this slice does not touch)
- **Recorded fixture unchanged:** SHA-256
  `61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525`
- **No Alembic change:** source head remains `0007_evidence_vault`

### Preserved limitations

- Validation covers the **byte-exact whole-Act consolidated PDF**; SHA-256 is
  recomputed against those exact bytes.
- Sections **55** and **56** are recorded as **manifest pinpoints only**.
- **No section-body text was extracted**, and **no section-body validation is
  claimed**. Citation existence and pinpoint integrity are validated against the
  recorded manifest pinpoints. Section-level body-text extraction remains
  deferred: it would require a PDF parsing dependency, and new dependencies are
  prohibited.
- The recorded fixture **is not a live legal-currency service**. It is a
  point-in-time snapshot and may not reflect later amendments.
- **No live retrieval or runtime network path exists.**
- This task implemented **no** model use, persistence, database or object-store
  write, migration, Evidence Vault write, `source_document_captures` write,
  production audit storage, playbook activation, external action, email, OAuth,
  API, UI, deployment, new dependency, or L3+ authority.
- `FailClosedGroundingGate` is untouched and remains refuse-closed. No product
  playbook may become ACTIVE on the basis of this slice.

### Phase 4 Slice 2

Phase 4 Slice 2 is **Not Started** and **not currently authorised**. It requires
a separate owner-approved bounded scope and a separate architecture decision
before any planning or implementation work begins. Completion of Slice 1 does
not authorise Slice 2.

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

Phase 3 is **Completed**. The Phase 4 WA fixture-recording prerequisite is
**Completed** (PR #20). **Phase 4 Slice 1 is Completed and merged to `main`**
via PR #22 @ `d758ae7769282aedd188705ac2de8b432880d1a3`, reviewed at PR head
`c7ced535d0dea98a1a3e518f3a9a2f3fd20ff089`. No implementation work remains open
for Slice 1.

**No Phase 4 Slice 2 implementation is currently authorised**, and no later
phase is authorised. Slice 2 requires a separate owner-approved bounded scope
and a separate architecture decision before any planning or implementation work
begins. Per `AGENTS.md`, the next phase does not start merely because the
previous phase merged.

The next action is therefore an owner decision, not engineering work. Three
boundaries carry forward for that decision:

1. section-level body-text extraction and validation remain deferred (they
   require a PDF parsing dependency, which is prohibited without a separate
   decision);
2. live retrieval, durable WA capture, and production audit storage remain
   deferred to separate owner-approved decisions; and
3. the recorded fixture is not a live legal-currency service, so an
   authoritative currency source remains an open owner decision.
