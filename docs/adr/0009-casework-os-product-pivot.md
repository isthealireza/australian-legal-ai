# ADR 0009: Casework OS product pivot and first operational vertical

- Status: Proposed
- Date: 2026-07-28

## Context

The repository today is a grounded Australian legislation research foundation:
Sprint 0 engineering controls plus Sprint 1.x Federal Register contract work,
immutable provenance, secure EPUB extraction, and deterministic legislation
hierarchy recognition through paragraphs. The official execution profile in
`docs/execution/MVP_ROADMAP.md` defines a grounded small-business legislation
research assistant and freezes matter management, document uploads, email,
external dispatch, approval services, and Temporal out of scope until an ADR
authorises expansion.

The Master Blueprint already describes matter management, playbooks, approvals,
and L0–L6 action authority as the long-term product direction. The proposed
Australian Legal Casework OS aligns with that north star while remaining a
portfolio-quality internal prototype: no real client data, no final legal
advice, and no autonomous L5/L6 actions.

A separate repository is unnecessary. No architectural blocker requires
migration. The existing legal-source, provenance, database, security, and test
infrastructure must be preserved and reused as shared platform capabilities.

## Approval boundaries (mandatory reading)

This ADR separates four approval layers. They must not be collapsed.

### A. Long-term product direction (proposed by this ADR)

Acceptance of this ADR (via PR review into `main`) approves the **long-term
direction** to evolve this repository into a governed Australian Legal Casework
OS: Generic Casework Core plus versioned, jurisdiction-bound playbooks, with
`wa_motor_property_damage_v1` as the first intended operational vertical and
`RESEARCH_AND_DRAFT_ONLY` for unsupported cases.

### B. Phase 0 documentation only (authorised now on this branch)

Phase 0 may create and merge **documentation only**: this ADR, the Casework OS
audit, the proposed Casework roadmap, the implementation ledger, and the ADR
index entry. Phase 0 does **not** authorise product code, schema changes,
integrations, model calls, credentials, or UI.

### C. Future approval required before Phase 1 product code

Phase 1 product code is **not** authorised by this ADR alone. Before any
casework implementation under `src/`, `tests/`, or `alembic/`:

1. this ADR must be Accepted on `main`; and
2. the repository owner must explicitly approve a separate amendment to
   `docs/execution/MVP_ROADMAP.md` (and any related protected-governance wording
   they authorise) so Phase 1 is in-scope under repository precedence.

Until both conditions are met, agents must not start Phase 1.

### D. Future dedicated approval and controls for every L3+ capability

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

- Phase 0 delivers audit, roadmap proposal, ledger, and this ADR only.
- Later phases add modular packages under `src/legal_ai/` without deleting the
  legislation pipeline.
- Evaluation and release gates remain fail-closed.
- `MVP_ROADMAP.md` remains the official execution profile until the owner
  separately amends it.
- ADR number 0009 is reserved for this Casework OS pivot.
