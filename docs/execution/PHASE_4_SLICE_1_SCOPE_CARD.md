# Phase 4 Slice 1 — Scope Card: WA Research and Evidence Packets

**Status:** Documentation only. Not Started.
**Date:** 2026-08-11
**Governing ADR:** [0013 — Phase 4 Research and Evidence Packets](../adr/0013-phase-4-research-evidence-packets.md) (Accepted 2026-08-11)

> **This Scope Card defines a future bounded implementation task. It does not
> itself authorise implementation.** A separate owner authorisation is required
> before any code change, branch, test run, or artifact beyond this document.

## Objective

Define the first bounded Phase 4 slice: a standalone, deterministic,
read-only research module that builds and validates WA evidence packets from
recorded fixtures under a test harness, with typed refusal and fail-closed
audit behaviour, per ADR 0013. The slice proves citation existence and pinpoint
integrity against exact source content without any persistence, live retrieval,
or model use.

## Allowed future implementation surface

Subject to a separate owner authorisation, a future task may create:

- a standalone research module (deterministic retrieval over recorded fixtures:
  metadata filters and a lexical baseline);
- the WA evidence-packet contract and its deterministic validator (citation
  existence, pinpoint integrity, hash recomputation against exact source
  content);
- an injected `ResearchAuditSink` interface with an in-memory, test-harness-only
  implementation;
- the typed refusal contract, including terminal `AUDIT_SINK_UNAVAILABLE`;
- recorded WA fixtures sourced only from `source_system` `wa_legislation` and
  HTTPS host `legislation.wa.gov.au`, committed as durable version-controlled
  test data; and
- unit and integration tests over those fixtures.

## Prohibited surface

The future task must not add, and this slice does not authorise:

- live retrieval, network access, or ingestion;
- database or object-store persistence; migrations;
- Evidence Vault writes or `source_document_captures` writes;
- durable WA capture of any kind;
- playbook activation or any change to playbook definitions;
- any external action, dispatch, email, OAuth, or UI/FastAPI work;
- model calls or model-based interpretation;
- any change to the `source_document_captures` `source_system` constraint;
- production audit storage; or
- new dependencies, services, or L3+ authority.

## Authority boundary

L0 — deterministic, read-only research and validation on recorded fixtures and
a test harness only. A successful validation produces only a validated evidence
packet; it never activates a playbook, mutates a store, or triggers a
downstream action. `FailClosedGroundingGate` remains mandatory and
refuse-closed and is neither replaced nor relaxed. "No store writes" means no
Evidence Vault, `source_document_captures`, database, or object-store writes;
the in-memory test audit sink is not persistence.

## Acceptance criteria

- Every validated evidence packet carries all required packet fields:
  `source_id`, `source_system`, `jurisdiction`, `official_source_url`,
  title/Act identity, provision identifier and pinpoint, a source version or
  compilation date (either one, exact and valid), effective/commencement/repeal
  status plus relevant status date where available, source text/content,
  `retrieved_at`, and `sha256`.
- Missing or invalid data on any field yields total refusal; no legal
  proposition, citation, partial result, or best-effort result is returned.
- Absence, invalidity, or `UNKNOWN` state of both the source version and the
  compilation date refuses; either one, exact and valid, satisfies that field. A
  missing, invalid, or `UNKNOWN` effective/commencement/repeal status or relevant
  status date refuses.
- `sha256` is recomputed against the exact source content and must match.
- Only `wa_legislation` / `legislation.wa.gov.au` fixtures pass the source
  allowlist; all other sources refuse.
- Both successful validation and normal refusal attempt an audit event before
  returning; an absent, unavailable, or failing sink yields terminal
  `AUDIT_SINK_UNAVAILABLE` with no packet, proposition, citation, or partial
  result, and no claim that an event was emitted.
- 100% citation ID / URL / version / status gate pass on the evaluation set.
- 0% cross-jurisdiction contamination.

## Test matrix

| Test type | Coverage |
|---|---|
| Unit | Packet-field validation; citation existence and pinpoint checks; hash recomputation; typed refusal codes; audit-sink failure path |
| Integration | End-to-end pipeline over durable recorded WA fixtures |
| Negative / refusal | Missing field; non-WA jurisdiction; non-allowlisted source or host; version missing; `UNKNOWN` status; hash mismatch; failed pinpoint; audit sink absent/unavailable |
| Adversarial | Fabricated provision; out-of-corpus question; wrong-jurisdiction trap; injected instructions in fixture content treated as data |

## Risks

- Recorded fixtures are not live legal currency; the effective/status fields
  reflect fixture metadata, not a live authoritative currency source.
- The fixture source allowlist is intentionally narrow and may not represent
  all WA source families.
- The in-memory audit sink is test-harness-only and provides no durable audit
  trail.
- Scope creep toward live retrieval or persistence would breach ADR 0013 and
  must be refused.

## Rollback

The slice is additive and isolated (a standalone module plus tests and
fixtures). Rollback is removal of the new module, its tests, and its fixtures.
There are no migrations, no schema changes, and no persisted data to reverse.

## Reviewer focus

- Confirm L0 read-only boundary and absence of persistence, migration, live
  retrieval, Evidence Vault writes, playbook activation, external action, and
  model use.
- Confirm the full packet contract and deterministic validation, including
  hash recomputation against exact source content.
- Confirm the sole fixture source (`wa_legislation` / `legislation.wa.gov.au`).
- Confirm fail-closed audit behaviour and terminal `AUDIT_SINK_UNAVAILABLE`.
- Confirm no partial result is ever emitted on refusal.
- Confirm provider-neutral wording and no new dependencies.

## Definition of done

- Deterministic validation and refusal implemented per ADR 0013 with full unit,
  integration, negative, and adversarial tests passing.
- All governance checks green (lint, format, strict type check, tests).
- No prohibited surface introduced; out-of-scope files untouched.
- Acceptance criteria and release gates met, with evidence recorded in the task
  report.
- Separate owner authorisation obtained before implementation begins, and
  normal review and owner merge completed before any merge to `main`.

## Open owner decisions

- Approval to begin implementation of this slice.
- Fixture-only first slice versus future live adapters.
- Future WA source-system persistence and migration decision.
- Authoritative currency source for effective/status determination.
