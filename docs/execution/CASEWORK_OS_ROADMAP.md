# Casework OS — Execution Roadmap

**Status:** Active for Casework workstreams only (does not replace `MVP_ROADMAP.md`)
**Date:** 2026-07-28
**Governing ADR:** [0009 — Casework OS product pivot](../adr/0009-casework-os-product-pivot.md) (Accepted 2026-07-28)
**Audit evidence:** [CASEWORK_OS_AUDIT.md](CASEWORK_OS_AUDIT.md)

## Precedence

Authority order remains: `PROJECT_GOVERNANCE.md` → `docs/execution/MVP_ROADMAP.md` (including
§11A) → `ENGINEERING_WORKFLOW.md` → approved task instructions → other repository
documents. `LEGAL_AI_MASTER_BLUEPRINT.md` is the north-star architecture and
does not override that order.

This document applies **only to Casework workstreams**. The grounded-research
sprint plan in `MVP_ROADMAP.md` §12 remains the binding profile for shared
platform research work. ADR 0009 and §11A place Casework Phase 1 foundation
**in scope to plan**; Phase 1 product code still requires a separate bounded
phase plan. Phases 2–12 remain not started and separately gated.

Shared research substrate work (Federal Register, WA sources, provenance,
parsing, retrieval, evidence packets) continues as reusable platform capability
and must not be deleted, replaced, renamed, or weakened to make room for
casework.

---

## Non-negotiable product principles (all phases)

1. **Generic Casework Core** plus **versioned, jurisdiction-bound playbooks**.
2. Unsupported cases → **`RESEARCH_AND_DRAFT_ONLY`** (research, organise, draft
   only; no external action; human review required).
3. First bounded operational playbook: **`wa_motor_property_damage_v1`**.
4. **Deterministic explicit state machine** before any Temporal (or other
   durable-engine) ADR.
5. **Artifact-bound human approvals** for sensitive actions; drafts marked DRAFT.
6. **No autonomous** admission, settlement, signature, court filing, police
   submission, insurance submission, or external communication.
7. **Official-source** legal research with provenance and fail-closed behaviour.
8. **Matter isolation**, privacy, audit, idempotency, and evidence integrity.
9. Every phase has **acceptance criteria** and **safety gates**; one phase per
   reviewable PR.

L3+ capabilities require a dedicated ADR and controls (see ADR 0009 §D).

---

## Cross-cutting release gates

- Citation ID validity: 100%
- Source URL validity: 100%
- Version metadata present where required: 100%
- Unsupported legal claim escaping validation: 0%
- Cross-jurisdiction contamination: 0%
- Cross-matter data leakage: 0%
- Unauthorised sensitive external action: 0%
- Duplicate external send: 0%
- Mutated-artifact approval acceptance: 0%
- Correct fail-closed behaviour for missing controls: 100%

---

## Phase plan

### Phase 0 — Repository audit and product-pivot decision

**Status:** Completed (documentation/governance finalisation).
**Scope:** documentation and owner-authorised §11A amendment only.
**Deliverables:** audit, this roadmap, ADR 0009 (Accepted), implementation
ledger, ADR index, `MVP_ROADMAP.md` §11A.
**Acceptance criteria:**
- ADR 0009 distinguishes long-term direction, Phase 0 docs, Phase 1 gate, L3+ gate.
- No `src/`, `tests/`, or `alembic/` product-code changes.
- Lint/format/type/unit checks remain green.

**Safety gates:** no product code; no credentials; no Phase 1 implementation start.

### Phase 1 — Generic matter core

**Status:** Completed.
**Scope:** typed matter, party, fact, issue, risk, case-type models; PostgreSQL
schema and migrations; deterministic state machine; matter-isolated
repositories; audit-event foundation; unit and integration tests.
**Out of scope:** model, email, UI, external network; live external actions;
production deployment; real client data; OAuth; email sending; insurance or
police submissions; settlement; admission; signature; court filing; L3+.
**Acceptance criteria:**
- Matter-scoped repository APIs require matter identity.
- Invalid state transitions rejected and logged.
- Integration tests prove no cross-matter retrieval.
- Migration upgrade/downgrade covered where applicable.

**Safety gates:** synthetic data only; fail closed if audit sink unavailable in
paths that require it; no L3+ surfaces.

### Phase 2 — Playbook registry and WA motor playbook

**Status:** Completed.
**Scope:** versioned playbook interface; registry; supported/unsupported
routing; `wa_motor_property_damage_v1`; mandatory intake; disqualifiers
including injury and court proceedings; evidence checklist; state-transition
rules; action policy; synthetic evaluation cases.
**Out of scope:** external sending.
**Acceptance criteria:**
- Injury/court/unsupported cases route to `RESEARCH_AND_DRAFT_ONLY`.
- Playbook version and effective date recorded on matter.
- Synthetic eval cases cover supported and disqualifying scenarios.

**Safety gates:** no improvised playbooks at runtime; no external dispatch.

### Phase 3 — Evidence vault extension

**Status:** Not Started; separately gated. An accepted architecture decision
and a bounded implementation task are required before implementation.
**Scope:** matter-scoped evidence records; original/derived relationships; safe
upload boundary; immutable storage reuse; provenance; checklist integration;
synthetic image/video metadata fixtures; negative security tests.
**Out of scope:** computer-vision claims of plate accuracy unless separately
evaluated.
**Acceptance criteria:**
- Originals immutable; SHA-256 streaming; MIME/type validation; no overwrite.
- Derived artifacts record source hash, operation, tool version.
- Path traversal and caller-filename path injection rejected.

**Safety gates:** no silent deletion; prompt-injection content treated as data.

### Phase 4 — Research and evidence packets

**Scope:** official-source registry; allowlisted WA service/police and
dispute-resolution adapters or recorded fixtures; evidence-packet schema;
citation existence and pinpoint validation; currency/jurisdiction gates where
supported; refusal paths; research evaluation set.
**Out of scope:** model-memory fallback.
**Acceptance criteria:**
- Legal propositions carry required provenance fields.
- Missing retrieval/validation → refusal.
- Reuses existing FRL/provenance/legislation capabilities.

**Safety gates:** 100% citation ID / URL gates on eval set; 0%
cross-jurisdiction contamination.

### Phase 5 — Drafting with mock model

**Scope:** provider-neutral model protocol; deterministic prompt/input builder;
strict structured output; mock adapter; draft versioning and provenance; output
validation; unsupported-claim rejection; prompt-injection tests.
**Out of scope:** live provider until credential/privacy gate.
**Acceptance criteria:**
- Schema-invalid model output rejected.
- Drafts marked DRAFT with provenance to evidence packet / playbook version.
- Injection fixtures do not alter system instructions.

**Safety gates:** no unrestricted tools on the product model; no live network
to providers in this phase.

### Phase 6 — Approval service

**Scope:** artifact-bound approval records; recipient/destination binding;
single-use default; expiry; revocation; mutation invalidation; anti-replay;
policy checks; full tests.
**Out of scope:** email send.
**Acceptance criteria:**
- Content/recipient/attachment mutation invalidates approval.
- Expired and replayed approvals rejected.
- Conversational sentiment is not an approval.

**Safety gates:** no external side effects from approval issuance alone.

### Phase 7 — Communication ingestion and draft replies

**Scope:** provider-neutral email interface; recorded fixtures; mock inbox;
thread-to-matter linking; request extraction; waiting-party classification;
response draft; follow-up task; audit.
**Out of scope:** production OAuth and sending.
**Acceptance criteria:**
- Threads link to exactly one matter unless policy denies.
- Prompt injection in email bodies treated as data.
- Drafts require Phase 6 approval before any future send path.

**Safety gates:** no production mailboxes; no send capability enabled.

### Phase 8 — Approved email sending

**Scope:** mock sending first; idempotency; outbox; retry policy; exact
approval enforcement; duplicate-send tests; recipient/attachment mutation
rejection; delivery-result audit.
**Out of scope:** live OAuth until owner credential gate.
**Acceptance criteria:**
- Dedicated L3/L4 ADR accepted before any non-mock send path is enabled.
- Duplicate send prevented by idempotency key.
- Missing approval/audit/outbox → fail closed.

**Safety gates:** stop at OAuth/provider-credential gate; never autonomously
send admissions, settlements, filings, or regulator complaints.

### Phase 9 — Durable workflow ADR and implementation

**Scope:** evaluate whether explicit state machine + worker is sufficient. If
durable multi-day needs justify Temporal: create ADR; workflow port; Activities
for side effects; Signals for approval and inbound mail; durable timers; replay
and recovery tests; large payloads outside history.
**Acceptance criteria:**
- Temporal (or alternative) only after approved ADR.
- Workflow code deterministic; side effects in Activities; Activities idempotent.
- Replay and worker-recovery tests pass.

**Safety gates:** do not run LangGraph and Temporal together initially; no
large evidence in workflow history.

### Phase 10 — Private-alpha API and UI

**Scope:** FastAPI endpoints; authentication boundary; stable OpenAPI; minimal
Next.js UI; approval centre; evidence, communication, and audit views;
permanent non-lawyer and corpus/playbook notices; end-to-end tests.
**Out of scope:** public deployment.
**Acceptance criteria:**
- Permanent disclaimer not dismissible.
- Approval centre shows exact artifact, recipient, and attachments.
- E2E tests cover refusal and unsupported-case paths.

**Safety gates:** no public self-signup; synthetic/public data only.

### Phase 11 — Live model evaluation

**Scope:** only after owner-provided credential and provider review — one
provider adapter; redacted inputs; acceptance evaluation; compare to
mock/golden expectations; measure unsupported claims, citation discipline,
refusal quality, latency, cost.
**Acceptance criteria:**
- Provider-neutral domain code unchanged in behaviour contracts.
- Eval gates in this document met or gaps reported without bypassing controls.

**Safety gates:** no unrestricted tools; redaction before model calls.

### Phase 12 — Private-alpha deployment preparation

**Scope:** Docker images; manifests; migrations; backups; restore test;
incident runbook; privacy checklist; threat model; monitoring with redaction;
rollback; restricted-access plan.
**Acceptance criteria:**
- Restore test documented; rollback instructions present.
- Australian-region placement documented where selected.

**Safety gates:** stop before external deployment; request owner approval.

---

## Follow-on owner actions (requiring explicit owner action)

1. Approve a separate bounded Phase 1 plan before any Phase 1 product code.
2. Approve provider accounts, OAuth, credentials, and any private-alpha deploy.
3. Approve any use of real personal information (default remains synthetic/public).
4. Approve a dedicated ADR before every L3+ capability.
5. Merge this branch via normal review when ready (push/PR only when authorised).
