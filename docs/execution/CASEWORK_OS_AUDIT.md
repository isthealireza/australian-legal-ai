# Casework OS — Phase 0 Repository Audit

**Status:** Phase 0 evidence (documentation only)
**Audit date:** 2026-07-28
**Baseline commit:** `1ef936fab780f5d03867a3c9beffa4e5fd859b47` (`origin/main`)
**Branch for this deliverable:** `docs/phase-0-casework-os-audit`
**Related decision:** [ADR 0009](../adr/0009-casework-os-product-pivot.md)

This document distinguishes what exists today from what is only planned. It does
not authorise Phase 1 code. Product implementation remains blocked until ADR
0009 is Accepted on `main` and an owner-approved amendment to
`docs/execution/MVP_ROADMAP.md` lands.

Repository facts were re-verified against `origin/main` before writing. ADR
number 0009 was confirmed unused on `origin/main` (latest accepted ADR: 0008).

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

| Authority | Conflict / alignment |
|---|---|
| `MVP_ROADMAP.md` §11 Scope Freeze | **Conflict.** “Not now” lists matter management, document uploads, email/calendar, external dispatch, approval service, Temporal — all Casework OS targets. Any addition requires an ADR first; Phase 1 also needs an owner-approved roadmap amendment. |
| `MVP_ROADMAP.md` §3–5 | **Conflict.** Product defined as grounded Q&A research assistant, not case intake / playbook workflows. |
| `CLAUDE.md` §3 MVP note | **Conflict for later phases.** Only L0–L2 in MVP; L3+ needs dedicated ADR. Approved email send (Phases 7–8) is L3/L4. |
| `AGENTS.md` | **Constraint.** Protected files and existing ADRs must not be silently changed. New ADR 0009 is the authorised decision record for this pivot. |
| `LEGAL_AI_MASTER_BLUEPRINT.md` | **Aligned.** Matters, playbooks, approvals, L0–L6, fail-closed retrieval. |
| Grounding / fail-closed / no real client data | **Aligned.** Casework OS must preserve these; unsupported cases stay research-and-draft-only. |

**Smallest compliant path:** accept ADR 0009 → owner amends `MVP_ROADMAP.md` →
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
| `README.md` | Still describes Sprint 0 / package-metadata-only state; application modules exist |
| `docs/execution/MVP_ROADMAP.md` | Still sole execution profile; Casework roadmap is proposed separately and does not replace it yet |
| `docs/adr/README.md` | Updated in Phase 0 to index ADR 0009 |
| No `IMPLEMENTATION_STATUS.md` before Phase 0 | Created in this phase |

Do not rewrite protected governance files in Phase 0.

---

## 7. Protected files requiring owner approval before modification

Exact owner approval is required before changing:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `LEGAL_AI_MASTER_BLUEPRINT.md`
4. `docs/execution/MVP_ROADMAP.md`
5. Existing ADRs `0001`–`0008` (content)
6. Git tags (including `governance-v1.0.0`)

Phase 0 proposes ADR 0009 and companion execution docs only. Follow-on
roadmap supersession wording for `MVP_ROADMAP.md` is **proposed in the Phase 0
completion report, not applied to the file**.

---

## 8. Proposed Cursor rules and hooks (not implemented in Phase 0)

Documented for later review; Phase 0 does not create `.cursor/rules` or hooks:

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
