# ADR 0009: Casework OS product pivot and first operational vertical

- Status: Accepted
- Date: 2026-07-28
- Accepted: 2026-07-28

## Context

The repository today is a grounded Australian legislation research foundation:
Sprint 0 engineering controls plus Sprint 1.x Federal Register contract work,
immutable provenance, secure EPUB extraction, and deterministic legislation
hierarchy recognition through paragraphs. The official execution profile in
`docs/execution/MVP_ROADMAP.md` defines a grounded small-business legislation
research assistant and previously froze matter management, document uploads,
email, external dispatch, approval services, and Temporal out of scope until an
ADR authorised expansion.

The Master Blueprint already describes matter management, playbooks, approvals,
and L0–L6 action authority as the long-term product direction. The Australian
Legal Casework OS aligns with that north star while remaining a
portfolio-quality internal prototype: no real client data, no final legal
advice, and no autonomous L5/L6 actions. This system is not a law firm, not an
admitted lawyer, and must not provide independent legal representation or final
legal decisions.

A separate repository is unnecessary. No architectural blocker requires
migration. The existing legal-source, provenance, database, security, and test
infrastructure must be preserved and reused as shared platform capabilities.

## Acceptance effect

Owner acceptance of this ADR on 2026-07-28 authorises:

1. the **governed Casework OS product direction** described below; and
2. **Phase 1 foundation work only** (generic matter core), subject to a
   separate bounded Phase 1 plan before any product-code changes, and subject
   to `docs/execution/MVP_ROADMAP.md` §11A.

This acceptance does **not** authorise:

- live external actions;
- production deployment;
- real client data;
- OAuth credentials;
- email sending;
- insurance submissions;
- police submissions;
- settlement decisions;
- admission of liability;
- signatures;
- court or tribunal filing;
- L3+ execution;
- L5 or L6 autonomy.

Separate ADRs, artifact-bound approvals, and owner credential gates remain
mandatory for every L3+ capability. L5/L6 remain never autonomously executable.

## Approval boundaries (mandatory reading)

This ADR separates four approval layers. They must not be collapsed.

### A. Long-term product direction (accepted)

Acceptance of this ADR approves the **long-term direction** to evolve this
repository into a governed Australian Legal Casework OS: Generic Casework Core
plus versioned, jurisdiction-bound playbooks, with
`wa_motor_property_damage_v1` as the first intended operational vertical and
`RESEARCH_AND_DRAFT_ONLY` for unsupported cases.

### B. Phase 0 documentation (completed by this finalisation)

Phase 0 is documentation only: this ADR, the Casework OS audit, the Casework
roadmap, the implementation ledger, the ADR index entry, and the owner-authorised
`MVP_ROADMAP.md` §11A amendment. Phase 0 does **not** include product code.

### C. Phase 1 foundation (approved to plan; not started)

Acceptance of this ADR together with `MVP_ROADMAP.md` §11A places Casework
Phase 1 foundation work **in scope to plan**. Phase 1 product-code changes
under `src/`, `tests/`, or `alembic/` must not begin until a separate bounded
Phase 1 plan is approved. This ADR does not itself start Phase 1
implementation.

### D. Dedicated approval and controls for every L3+ capability

Acceptance of this ADR does **not** authorise L3+ capabilities. Every L3+
capability (including email send, evidence upload to external parties, insurer
or police submission assistance that leaves the system boundary, or any other
external dispatch) requires:

- a dedicated ADR;
- artifact-bound authenticated approvals;
- idempotency, outbox, and audit controls;
- fail-closed behaviour when controls are unavailable;
- owner credential / OAuth / provider gates where applicable.

L5/L6 actions remain never autonomously executable. No autonomous admission of
liability, settlement decision, signature, court or tribunal filing, police
submission, insurance submission, or external communication is authorised by
this ADR.

## Decision

1. **Extend this repository in place.** Do not create a new repository, do not
   replace the existing codebase, and do not rebuild from scratch.

2. **Preserve shared research substrate.** Federal Register contract code,
   immutable provenance store, EPUB parser, legislation structure modules,
   security controls, and tests remain first-class platform capabilities.
   Casework modules are additive. Do not delete, replace, rename, or weaken them.

3. **Adopt a two-layer product shape:**
   - Generic Casework Core (matters, parties, facts, evidence, timelines,
     tasks, deadlines, communications, research findings, drafts, approvals,
     actions, audit, closure).
   - Versioned Case-Type Playbooks that bound jurisdiction, facts,
     disqualifiers, sources, evidence checklists, states, tools, approvals,
     templates, evaluations, and refusal behaviour.

4. **First operational playbook:** `wa_motor_property_damage_v1`
   - Western Australia;
   - parked or unattended vehicle property damage;
   - identifiable or unidentified other vehicle;
   - evidence may include video, photographs, plate number, witnesses, repair
     quotations, and correspondence;
   - insurer claim and WA Police reporting assistance as draft/support only;
   - no personal injury;
   - no court or tribunal proceeding;
   - no legal representation;
   - no autonomous submission;
   - no admission of liability;
   - no settlement acceptance or rejection.

5. **Unsupported cases** enter `RESEARCH_AND_DRAFT_ONLY`. The system may explain
   missing information, research allowlisted official sources, create non-final
   issue lists and draft-only plans, recommend qualified human review, and
   propose new playbook specifications. It must not send communications,
   submit forms, calculate legally critical deadlines from model judgment,
   state definitive legal conclusions, or auto-create production playbooks.

6. **Workflow:** implement an explicit typed state machine first. Do not adopt
   Temporal, LangGraph, or another orchestration framework without a later ADR
   justified by durable multi-day waits, approval signals, and recovery needs.

7. **Approvals and grounding:** drafts are marked DRAFT; sensitive actions use
   artifact-bound human approvals; legal propositions require official-source
   research with provenance and fail-closed refusal; matters are isolated;
   privacy, audit, idempotency, and evidence integrity are mandatory design
   constraints for later phases.

8. **Action authority:** preserve L0–L6. See Approval boundary D for L3+.

## Consequences

- Phase 0 documentation and this Accepted ADR record the Casework OS direction.
- `MVP_ROADMAP.md` §11A gates Casework Phase 1 as in scope to plan; grounded
  research sprints remain shared platform work.
- `CASEWORK_OS_ROADMAP.md` applies only to Casework workstreams.
- Phase 1 implementation still requires a separate bounded phase plan.
- Later phases add modular packages under `src/legal_ai/` without deleting the
  legislation pipeline.
- Evaluation and release gates remain fail-closed.
- ADR number 0009 is reserved for this Casework OS pivot.
