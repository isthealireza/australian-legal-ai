# ADR 0013: Phase 4 Research and Evidence Packets — First Slice

- Status: Accepted
- Date: 2026-08-11
- Accepted: 2026-08-11 (owner-approved)

## Context

Phase 4 introduces deterministic legal research and evidence-packet validation
for the WA parked/unattended motor-property-damage vertical. Phases 0–3 are
complete: the generic matter core, the versioned playbook framework
(`wa_motor_property_damage_v1` seeded as validated DRAFT only), and the matter
evidence vault. No product playbook may become ACTIVE until the Phase 4
grounding gate is met, and `FailClosedGroundingGate` refuses on every activation
path.

`PROJECT_GOVERNANCE.md` requires that every legal proposition be tied to a
verified official source with a pinpoint, that deterministic operations
(hashing, parsing, citation existence and pinpoint checks, source-version
comparison) never be performed by a model, and that every dependent action stop
if a required control — including the audit sink — is unavailable.

The existing `federal_register`-only provenance schema
(`source_document_captures.source_system`) does not describe a WA evidence
contract and is not reused as one. This decision records a bounded, prospective
first slice. It authorises no implementation by itself; a separate owner
authorisation is required before any code change.

## Decision

### 1. First slice architecture — standalone research module

The Phase 4 first slice is **Option 1: a standalone research module**. It
provides deterministic retrieval (metadata filters and a lexical baseline), the
WA evidence-packet builder, the deterministic validator, and a typed refusal
path. It reuses existing legislation, provenance, and grounding capabilities
rather than duplicating them. It is not implemented as an extension of the
playbook grounding subsystem.

### 2. Authority classification and hard boundaries

The first slice is **L0 — deterministic, read-only research and validation**,
exercised on **recorded fixtures and a test harness only**. It has:

- no production wiring;
- no live retrieval;
- no database or object-store persistence;
- no migrations;
- no Evidence Vault writes;
- no `source_document_captures` writes;
- no playbook activation;
- no external actions; and
- no model use of any kind.

A successful validation may produce **only a validated evidence packet**. It
must never activate a playbook, mutate a store, or trigger a downstream action.
`FailClosedGroundingGate` remains mandatory and refuse-closed; this slice does
not replace or relax it. "No store writes" means no Evidence Vault,
`source_document_captures`, database, or object-store writes; the in-memory
test audit sink in §5 is not persistence.

### 3. Sole fixture source

The only approved recorded-fixture source for the first slice is:

- `source_system` = `wa_legislation`; and
- an HTTPS URL whose host is exactly one of the following closed two-host
  allowlist:
  - `legislation.wa.gov.au`; or
  - `www.legislation.wa.gov.au`.

The `www.legislation.wa.gov.au` host is included because the official WA
Legislation homepage and the resolved official document URLs use it. The
allowlist is closed and exact: no other host is permitted, wildcard subdomains
are not permitted, and no arbitrary subdomain is trusted. HTTPS is required.
Recorded URLs are kept faithful to the official source and are not rewritten
from `www.legislation.wa.gov.au` to the apex host. This is recorded-fixture
metadata only. It is not authorisation for live retrieval, network access, or
ingestion.

### 4. WA evidence-packet contract and deterministic validation

The WA evidence-packet is a new, WA-specific, in-memory contract, distinct from
the federal provenance schema. Every field below is required, and the validator
checks each one deterministically:

- `source_id` — packet identity;
- `source_system` — must equal `wa_legislation`;
- `jurisdiction` — must equal `WA`;
- `official_source_url` — an HTTPS URL whose host is exactly one of the closed
  two-host allowlist `legislation.wa.gov.au` or `www.legislation.wa.gov.au`
  (§3); no wildcard or other subdomain;
- `title` / Act identity — the named instrument;
- provision identifier and pinpoint — the cited provision and pinpoint
  reference;
- source version or compilation date — one required provenance field,
  satisfied by either an exact source version or an exact compilation date;
- effective/commencement/repeal status, plus the relevant status date where
  available — a separate required field;
- source text/content — sufficient to validate the pinpoint;
- `retrieved_at` — a well-formed retrieval timestamp; and
- `sha256` — recomputed against the exact source content and matched.

Citation existence, pinpoint validation, and hash recomputation are not
possible unless these fields are present. Any missing or invalid field causes
total refusal. No packet is emitted partial.

Absence, invalidity, or `UNKNOWN` state of both the source version and the
compilation date must refuse; either one, exact and valid, satisfies that field.
A missing, invalid, or `UNKNOWN` effective/commencement/repeal status, or
relevant status date, must also refuse.

### 5. ResearchAuditSink and refusal contract

Audit events are received through an injected `ResearchAuditSink` interface. For
the first slice it is **in-memory and test-harness-only**; there is no
production wiring and no persistent audit storage.

Both successful validation and normal refusal **attempt a structured audit event
before returning**. A normal refusal carries a typed reason code (for example
`RETRIEVAL_MISSING`, `CITATION_NOT_FOUND`, `PINPOINT_MISMATCH`,
`JURISDICTION_MISMATCH`, `SOURCE_NOT_ALLOWLISTED`, `VERSION_MISSING`,
`STATUS_UNKNOWN`, `HASH_MISMATCH`, `FIELD_MISSING`) and returns no partial legal
proposition, no citation, and no best-effort result.

If the audit sink is **absent, unavailable, or the write fails**, validation
stops with a terminal typed `AUDIT_SINK_UNAVAILABLE` failure. It emits no
validated packet, no legal proposition, no citation, and no partial result, and
it does not claim that an audit event was emitted. There is no degraded path.

### 6. Explicitly deferred

The following remain explicitly deferred to separate, owner-approved decisions
and bounded tasks:

- live WA source adapters and any live retrieval;
- durable WA capture (runtime or database persistence);
- any change to the `source_document_captures` `source_system` constraint;
- migrations for WA capture; and
- production audit storage.

## Alternatives considered

### Option 2 — extend the playbook grounding gate

Deferred. Building the builder and validator inside the playbook grounding
subsystem would couple research logic to playbook internals and complicate
rollback. A standalone module keeps an isolated, independently testable
fail-closed surface.

### Reuse the federal provenance schema for WA

Rejected. The `federal_register`-only provenance schema does not describe a WA
evidence contract and must not be represented as reusable for WA persistence.

### Live WA adapters in the first slice

Deferred. Recorded fixtures keep the first slice deterministic, offline, and
free of ingestion and network risk. Live adapters require a separate owner
decision.

## Consequences

Positive consequences:

- the first slice is deterministic, offline, and fail-closed;
- the WA evidence-packet contract is explicit and separate from federal
  provenance;
- validation cannot emit a partial or unaudited result; and
- no persistence, migration, external action, or model use is introduced.

Costs and limitations:

- the fixture source is intentionally narrow (`wa_legislation`, with a closed
  two-host allowlist of `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au`);
- recorded fixtures are not live legal currency;
- the in-memory audit sink is test-harness-only and not durable; and
- live retrieval, durable capture, and production audit storage remain
  deferred.

Phase 4 remains Not Started until a separate bounded implementation task is
explicitly authorised. That future task must preserve `PROJECT_GOVERNANCE.md`,
`ENGINEERING_WORKFLOW.md`, prior ADRs, and every boundary in this decision.
