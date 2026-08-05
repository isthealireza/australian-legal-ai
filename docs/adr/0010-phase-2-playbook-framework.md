# ADR 0010: Phase 2 playbook framework

- Status: Accepted
- Date: 2026-08-04
- Accepted: 2026-08-04

## Context

ADR 0009 accepted the Casework OS product direction and authorised Phase 1
foundation work only. It identified `wa_motor_property_damage_v1` as the first
intended operational vertical, but it did not authorise Phase 2 implementation.

The owner decision recorded here is prospective. Phase 2 was not authorised
before 2026-08-04. This ADR authorises the bounded Phase 2 implementation for
completion and merge review from that date onward; it does not retrospectively
authorise earlier work or itself authorise publication or merge.

## Decision

Phase 2 is approved with the following scope and boundaries:

1. Provide a deterministic, versioned playbook framework and a validated DRAFT
   definition for `wa_motor_property_damage_v1`. This prospective approval
   includes the existing Phase 2 registry, pinning schema, and migration 0006
   as presented on `feat/phase-2-playbook-framework` for completion and merge
   review; it does not imply that their earlier development was authorised.
2. Limit that playbook to Western Australian motor-vehicle property damage in
   which the affected vehicle was parked or unattended. Missing evidence of
   that fact is `UNKNOWN`, must not assign the playbook, and must fail closed.
3. Derive eligibility, disqualification, and routing from the pinned immutable
   playbook version. Caller-provided routing authority is not trusted. Keep
   required fields, allowed matter transitions, and required human approvals
   versioned in that definition for enforcement in their roadmap-authorised
   phases.
4. Route unsupported matters and matching disqualifiers to
   `RESEARCH_AND_DRAFT_ONLY` where the pinned definition requires it. That
   state grants no external-action authority.
5. Record substantive policy refusals as durable `ACTION_DENIED` audit
   evidence in an independent transaction after the denied business
   transaction rolls back. Denial auditing may record only denial evidence; if
   it cannot be persisted, the operation raises `PlaybookAuditWriteFailed` and
   no business-state mutation is committed.
6. Keep successful state changes and their ordinary audit evidence atomic.
7. Preserve deterministic, fail-closed handling, tenant isolation, immutable
   version pinning, and L0-L2 authority limits.

## Explicit exclusions

This decision does not authorise:

- any playbook beyond the parked/unattended WA motor-property-damage vertical;
- LLM or model-answering capability;
- user-interface work;
- email, OAuth, external dispatch, or live external actions;
- L3 or higher action authority;
- additional schema changes or database migrations beyond the reviewed Phase 2
  migration 0006, or new dependencies;
- activation of the DRAFT playbook before the existing grounding gates are
  satisfied;
- Phase 3 or later work.

ADR 0009's prohibitions and the repository's grounding, citation, privacy,
audit, and approval controls remain in force.

## Consequences

- Phase 2 may proceed to completion and merge review within this bounded scope.
- Unsupported or disqualified matters fail closed into
  `RESEARCH_AND_DRAFT_ONLY` only when the governing versioned definition
  requires that route.
- Validation errors, optimistic-concurrency conflicts, and programming errors
  are not reclassified or blanket-audited as substantive policy refusals.
- Publication and merge remain separate owner-controlled actions.
- Phase 2 is not complete until it is merged and the implementation ledger is
  updated on `main`.
