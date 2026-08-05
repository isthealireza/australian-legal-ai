# Casework OS — Phase 0 Repository Audit

**Status:** Phase 0 evidence (documentation only)
**Audit date:** 2026-07-28
**Baseline commit:** `1ef936fab780f5d03867a3c9beffa4e5fd859b47` (`origin/main`)
**Branch for this deliverable:** `docs/phase-0-casework-os-audit`
**Related decision:** [ADR 0009](../adr/0009-casework-os-product-pivot.md)

This document distinguishes what exists today from what is only planned.
ADR 0009 is Accepted (2026-07-28) and `MVP_ROADMAP.md` §11A is in force.
Phase 1 foundation is **approved to plan only**. Product-code changes remain
blocked until a separate bounded Phase 1 plan is approved. This audit does not
authorise live external actions, production deployment, real client data,
OAuth, email sending, insurance or police submissions, settlement, admission,
signature, court filing, L3+ execution, or L5/L6 autonomy.

Repository facts were re-verified against `origin/main` before writing. ADR
number 0009 was confirmed unused on `origin/main` at Phase 0 start (latest
accepted ADR then: 0008).

---

## 1. Architecture map (current)

```text
src/legal_ai/
  sources/frl/       Federal Register HTTP contract client + typed models
  provenance/        Content-addressed blob store + PostgreSQL metadata repo
  db/                SQLAlchemy Core schema for provenance tables
  parsing/           Secure EPUB structural extraction
  legislation/       Deterministic hierarchy → subsections → paragraphs

alembic/versions/    0004_immutable_provenance
tests/               Unit + optional Postgres integration tests
docs/adr/            0001–0008 accepted on main; 0009 proposed (this phase)
```

Logical data flow today:

```text
FRL fixtures/client
  → provenance capture metadata + SHA-256 blob store
Parsed EPUB
  → structured legislation blocks
  → subsections / schedule subclauses
  → unambiguous paragraphs
```

Trusted runtime ownership today is limited to deterministic parsing, hashing,
schema validation, and fail-closed store publication. There is no workflow
engine, model runtime, email integration, or matter isolation layer.

---

## 2. Capability map

### Exists and tested

| Capability | Location | Notes |
|---|---|---|
| Engineering foundation | Sprint 0 | uv, Ruff, Mypy strict, Pytest, pre-commit, CI, Docker Compose Postgres 16 |
| FRL contract boundary | `sources/frl/` | Recorded fixtures; tests do not call live hosts |
| Immutable provenance | `provenance/`, `db/`, Alembic 0004 | Content-addressed keys; no caller filenames in paths |
| Secure EPUB parse | `parsing/` | Typed limits; security/unsupported feature errors |
| Legislation hierarchy | `legislation/structure.py` | Act → Chapter/Part/Division/Section/Schedule |
| Subsections | `legislation/subsections.py` | Deterministic; fail-closed on unsupported markers |
| Paragraphs | `legislation/paragraphs.py` | Alphabetic only; Roman markers ambiguous/fail-closed |

### Planned only (not implemented)

| Capability | Target phase |
|---|---|
| Matter / party / fact / issue models | Phase 1 |
| Playbook registry + WA motor playbook | Phase 2 |
| Matter-scoped evidence vault extension | Phase 3 |
| Evidence packets + citation validation | Phase 4 |
| Provider-neutral drafting with mock model | Phase 5 |
| Artifact-bound approval service | Phase 6 |
| Email ingestion / approved send | Phases 7–8 |
| Durable workflow engine (if justified) | Phase 9 |
| Private-alpha API + UI | Phase 10 |
| Live model evaluation | Phase 11 |
| Deployment preparation | Phase 12 |
| WA legislation adapter, ingest CLI, retrieval | Continues as shared research substrate work |
| FastAPI answering endpoint | Deferred until research + casework contracts stabilize |

---

## 3. Gap analysis against Casework OS target

| Target area | Gap |
|---|---|
| Generic casework core | No matter, party, fact, timeline, task, deadline, or closure modules |
| Playbooks | No registry, versioning, or `wa_motor_property_damage_v1` |
| State machine | No matter states or validated transitions |
| Evidence vault for user uploads | Provenance exists for official captures; no matter-scoped upload boundary or derived-artifact graph for case evidence |
| Research packets | No evidence-packet schema or citation existence/pinpoint validators |
| Approvals / actions | No approval records, outbox, or idempotent execution |
| Communications | No email port, mocks, or send path |
| Privacy controls for case data | Synthetic-data rule exists in governance; no classification/redaction pipeline in code |
| UI | None |
| Evaluation set for motor vertical | None |

Reuse path: keep `sources/`, `provenance/`, `parsing/`, and `legislation/` as
shared research capabilities consumed by casework research findings later.
Do not delete, replace, rename, or weaken them.

---

## 4. Conflict analysis with governance and MVP scope

| Authority | Status after Phase 0 finalisation |
|---|---|
| `MVP_ROADMAP.md` §11 / §11A | **Resolved for Phase 1 planning.** §11 “Not now” retained; §11A gates Casework Phase 1 foundation as in scope to plan only. Remainder of “Not now” (email, dispatch, Temporal, production, real client data, etc.) stays frozen. |
| `MVP_ROADMAP.md` §3–5 / §12 | **Dual-track.** Grounded Q&A research remains shared platform work; Casework workstreams follow `CASEWORK_OS_ROADMAP.md` only. |
| `PROJECT_GOVERNANCE.md` §3 MVP note | **Preserved.** Only L0–L2 without dedicated ADR; L3+ still needs dedicated ADR. ADR 0009 does not authorise L3+. |
| `ENGINEERING_WORKFLOW.md` | **Preserved.** Protected files changed only under this owner authorisation (§11A + ADR acceptance). |
| `LEGAL_AI_MASTER_BLUEPRINT.md` | **Aligned.** Matters, playbooks, approvals, L0–L6, fail-closed retrieval. |
| Grounding / fail-closed / no real client data | **Aligned.** Unsupported cases stay `RESEARCH_AND_DRAFT_ONLY`. |

**Compliant path now:** ADR 0009 Accepted + §11A in force → separate Phase 1 plan →
implement modular `casework/` and `playbooks/` beside existing modules.

---

## 5. Dependency and security review

### Dependencies (`pyproject.toml`)

- Runtime: Alembic, httpx, Pydantic, Psycopg, SQLAlchemy — appropriate for
  modular monolith persistence and HTTP contract clients.
- Dev: Mypy, pre-commit, Pytest, pytest-cov, Ruff.
- No model SDK, email SDK, Temporal, FastAPI, or frontend packages yet.
- Phase 0 adds **no** new dependencies.

### Security observations

- Secrets scanning via gitleaks in CI and pre-commit.
- Provenance store rejects path traversal and caller-controlled filenames.
- EPUB parser has explicit security/unsupported feature errors.
- Tests use fixtures; FRL client tests avoid live network.
- Integration tests require explicit disposable Postgres URL — good isolation
  pattern for future matter-isolation tests.
- Gaps for Casework: matter-scoped RLS design, upload malware/type gates,
  approval anti-replay, outbound allowlists, redaction before model calls —
  all future phases.

---

## 6. Stale-documentation list

| Document | Issue |
|---|---|
| `README.md` | Still describes Sprint 0 / package-metadata-only state; application modules exist (intentionally unchanged in Phase 0) |
| `docs/execution/MVP_ROADMAP.md` | Now includes §11A Casework gate; grounded-research §12 remains in force for shared platform work |
| `docs/adr/README.md` | Indexes ADR 0009 as Accepted |
| `docs/execution/IMPLEMENTATION_STATUS.md` | Phase ledger for Casework phases |

---

## 7. Protected files requiring owner approval before modification

Exact owner approval remains required before changing:

1. `PROJECT_GOVERNANCE.md`
2. `ENGINEERING_WORKFLOW.md`
3. `LEGAL_AI_MASTER_BLUEPRINT.md`
4. `docs/execution/MVP_ROADMAP.md` (beyond the owner-authorised §11 / §11A edits in this finalisation)
5. Existing ADRs `0001`–`0008` (content)
6. Git tags (including `governance-v1.0.0`)

Phase 0 finalisation applies the owner-authorised §11A amendment and marks ADR
0009 Accepted. Further protected-file edits still require explicit owner
approval.

---

## 8. Proposed repository workflow controls (not implemented in Phase 0)

Documented for later review; Phase 0 does not create additional repository rules or hooks:

- Path-scoped rules for Python verification, migrations, evidence/provenance,
  integrations/network, approvals/actions, frontend privacy, and evals.
- Hooks to block commits to `main`, committed `.env`/keys, destructive
  filesystem or DB commands outside migration tests, unapproved governance
  edits, and to require tests for changed domain code.

Hooks are defence in depth and do not replace CI, review, or sandboxing.

---

## 9. Repository decision — blocker assessment

**No genuine architectural blocker requires a new repository.**

Evidence:

- Shared stack (Python 3.13, uv, Postgres, Pydantic, SQLAlchemy, Alembic)
  matches Casework OS target.
- Provenance and official-source seams are already the right substrate for
  research findings and evidence packets.
- Conflicts are governance/scope conflicts, resolved by ADR + roadmap
  amendment, not by repository migration.

---

## 10. Local verification snapshot (baseline audit)

Commands re-run after documentation on this branch are recorded in
`IMPLEMENTATION_STATUS.md` and the Phase 0 completion report.
