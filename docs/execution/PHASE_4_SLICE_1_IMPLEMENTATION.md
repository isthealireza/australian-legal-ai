# Phase 4 Slice 1 — Implementation Record: WA Research and Evidence Packets

**Status:** **Completed** — merged to `main`.
**Date:** 2026-08-15
**Implementation PR:** #22
**Reviewed PR head:** `c7ced535d0dea98a1a3e518f3a9a2f3fd20ff089`
**Merge commit:** `d758ae7769282aedd188705ac2de8b432880d1a3`
**Historical feature branch:** `feat/phase-4-slice-1` (base
`159a695d4a2916bcc8384a9b6275a2d36e8cd5a3`)
**Governing ADR:** [0013 — Phase 4 Research and Evidence Packets](../adr/0013-phase-4-research-evidence-packets.md)
**Scope Card:** [Phase 4 Slice 1 Scope Card](PHASE_4_SLICE_1_SCOPE_CARD.md)

This records the bounded, owner-authorised implementation of the Phase 4 first
slice, as reviewed at PR head `c7ced535d0dea98a1a3e518f3a9a2f3fd20ff089` and
merged via PR #22. It documents what was built and, equally, what was
deliberately not built.

Phase 4 Slice 1 is complete. **No Phase 4 Slice 2 implementation is currently
authorised**; see [Status after merge](#status-after-merge).

## What was implemented

A standalone, deterministic, read-only research module at
`src/legal_ai/research/`. It builds and validates WA evidence packets from the
durable recorded fixture already committed to `main`, under a test harness only.

| File | Responsibility |
|---|---|
| `types.py` | Closed WA vocabularies: refusal codes, terminal code, legal status, source-system and jurisdiction constants, the closed two-host allowlist |
| `errors.py` | Typed boundary errors (`ResearchError`, `RecordedCorpusError`, `AmbiguousSelection`, `ResearchAuditSinkUnavailable`) |
| `models.py` | The WA evidence-packet contract, the query contract, and the untrusted recorded-source records |
| `corpus.py` | Deterministic recorded-fixture loading and selection beneath an injected root |
| `validation.py` | The deterministic validator |
| `audit.py` | The injected `ResearchAuditSink` interface and the structured audit event |
| `service.py` | Fail-closed orchestration and the typed result contract |

The in-memory audit sinks live in `tests/support/research_audit.py`: they are
test-harness-only and are never imported by production code.

## Packet contract

A validated `WaEvidencePacket` carries `source_id`, `source_system`
(`wa_legislation`), `jurisdiction` (`WA`), the faithful `official_source_url`,
Act identity (title, WA jurisdiction, Act number), provision identifier,
pinpoint, provision heading, source version and/or compilation date, legal
status, status date, the exact source content, `retrieved_at`, `sha256`, and the
`audit_result`.

Three invariants are enforced by the type system rather than by convention:

1. `audit_result` admits exactly one value (`RECORDED`), so no packet can exist
   without a recorded audit event.
2. `ResearchRefused` and `ResearchTerminated` have no `packet` attribute at all,
   so no refusal can return a partial packet, a citation, or a proposition.
3. The packet model recomputes SHA-256 over its own content on construction, so
   no packet can hold a digest inconsistent with its bytes.

## Deterministic validation

Every check is deterministic code; no model is involved anywhere in the module.
Check order is fixed and total — a source must prove it is an allowlisted,
identifiable WA source, then that its provenance is exact, then that its content
is intact, and only then is the citation looked up:

1. **Source identity** — `source_system` must equal `wa_legislation`;
   `jurisdiction` and the Act's own jurisdiction must both equal `WA`;
   `source_id` and Act title must be present and exact.
2. **Host allowlist** — HTTPS only, host exactly `legislation.wa.gov.au` or
   `www.legislation.wa.gov.au`, no wildcard subdomain, no userinfo, no
   non-443 port. Recorded `www` URLs are kept faithful and are never rewritten.
3. **Provenance** — a source version or a compilation date, either one exact and
   valid; a known effective/commencement/repeal status consistent with the
   recorded in-force flag; and a valid status date that does not postdate
   retrieval.
4. **Integrity** — non-empty content, a well-formed UTC `retrieved_at`, and
   SHA-256 recomputed over the exact recorded bytes and matched.
5. **Citation existence** — the requested provision must match a recorded
   provision's identifier or pinpoint exactly (after whitespace and case
   normalisation).
6. **Pinpoint integrity** — the requested pinpoint must match that provision's
   recorded pinpoint exactly.

Packets are built from recorded values, never from requested values.

## Refusal and audit behaviour

Ordinary refusals are total and carry a typed code: `RETRIEVAL_MISSING`,
`SELECTION_AMBIGUOUS`, `FIELD_MISSING`, `FIELD_INVALID`,
`SOURCE_SYSTEM_MISMATCH`, `JURISDICTION_MISMATCH`, `SOURCE_NOT_ALLOWLISTED`,
`VERSION_MISSING`, `STATUS_UNKNOWN`, `STATUS_DATE_INVALID`,
`CITATION_NOT_FOUND`, `PINPOINT_MISMATCH`, `HASH_MISMATCH`.

Both a validated outcome and an ordinary refusal attempt a structured audit
event before returning. A refusal event carries the typed code and deliberately
carries no `source_id` and no digest: a refusal emits no citation, not even into
the audit trail.

An absent, unavailable, or failing sink returns terminal
`AUDIT_SINK_UNAVAILABLE` with no packet, citation, proposition, or partial
result, and with no claim that an event was emitted. There is no degraded path.

## Untrusted-data handling

Recorded manifests and recorded content are untrusted data. Values are compared,
hashed, or copied — never interpreted as instructions. Non-string manifest values
are not coerced, malformed provision entries are dropped rather than trusted, and
a manifest-declared content filename must be a plain basename resolving inside
the injected fixture root, so no recorded value can widen the read boundary or
skip a check. Adversarial tests cover injected instructions in manifest fields,
in provision metadata, and in the recorded content bytes.

## Scope limitation: pinpoint validation is against recorded pinpoints

The committed fixture is the **byte-exact whole-Act consolidated PDF**; sections
55 and 56 are recorded as **manifest pinpoints only**, and no section-level text
was extracted during the fixture-recording prerequisite.

Accordingly, in this slice:

- "exact source content" is the byte-exact recorded PDF content, which is
  precisely what the recorded SHA-256 covers, and hash recomputation is
  performed against those exact bytes;
- citation existence and pinpoint integrity are validated against the **recorded
  provision pinpoints**, per the authorised surface ("pinpoint validation for
  the recorded provisions").

**No section-body validation is claimed by this slice.** Nothing in the module
asserts that quoted or extracted section text has been checked against the Act's
section bodies, because no section-body text was extracted.

Validating a pinpoint against extracted **section body text** would require PDF
text extraction, which needs a PDF parsing dependency. New dependencies are
prohibited by ADR 0013, the Scope Card, and `ENGINEERING_WORKFLOW.md` §9, so
section-level extraction remains deferred, exactly as the fixture README states.
This is an owner decision to make before a slice that must prove quoted text
against section bodies.

The recorded fixture **is not a live legal-currency service**. It is a
point-in-time snapshot for deterministic testing and may not reflect amendments
made after its retrieval timestamp; the status and version fields reflect
recorded fixture metadata, not a live authoritative currency source.

## Boundaries respected

The slice adds no live retrieval, no runtime network path, and no HTTP client.
It adds no model call, model-based interpretation, database or object-store
persistence, migration, Evidence Vault write, `source_document_captures` write,
production audit storage, playbook activation, external action, email, OAuth,
API or FastAPI endpoint, UI, deployment, new dependency, or L3+ authority.
`FailClosedGroundingGate` is untouched and remains refuse-closed. The recorded
PDF and manifest bytes are unmodified. These boundaries are unchanged by the
merge.

## Validation evidence

```text
uv run --locked ruff check .          # All checks passed
uv run --locked ruff format --check . # 127 files already formatted
uv run --locked mypy .                # Success: no issues found in 127 source files
uv run --locked pytest                # 821 passed, 144 skipped
```

Baseline before the change was 640 passed / 144 skipped, so the slice adds 181
tests. The 144 skips are the PostgreSQL integration suite, which requires
`LEGAL_AI_TEST_DATABASE_URL`; this slice adds no database surface.

Fixture integrity was re-verified after implementation:
`61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525`.

## Test coverage

| Area | Coverage |
|---|---|
| Unit — packet contract | Required fields; frozen; extra fields forbidden; hash consistency; audit-result invariant; non-WA identity rejected |
| Unit — validation | Every refusal code; allowlist accept and reject; version/compilation-date rule; status and status-date rules; digest recomputation |
| Unit — corpus | Recorded metadata; exact bytes; deterministic selection; ambiguity; path containment; unusable manifests; no coercion |
| Unit — service | Audit-before-return on both paths; absent/unavailable/failing sink; no partial output; determinism |
| Integration | End-to-end over the recorded fixture for s 55 and s 56 |
| Negative | Missing and invalid fields; non-WA jurisdiction; wrong source system; non-allowlisted host; HTTP; missing version and date; unknown status; wrong status date; hash mismatch; pinpoint mismatch |
| Adversarial | Fabricated provisions; out-of-corpus requests; cross-jurisdiction traps; injected instructions in manifests, pinpoints, headings, and content bytes |

## Status after merge

Phase 4 Slice 1 is **Completed**. It was reviewed at PR head
`c7ced535d0dea98a1a3e518f3a9a2f3fd20ff089` and merged to `main` via PR #22 as
merge commit `d758ae7769282aedd188705ac2de8b432880d1a3`. No implementation work
remains open for this slice.

**No Phase 4 Slice 2 implementation is currently authorised.** Slice 2 requires
a separate owner-approved bounded scope and a separate architecture decision
before any planning or implementation work begins. Completion of Slice 1
authorises nothing further: per `AGENTS.md`, the next phase does not start
merely because the previous phase merged.

The deferrals recorded in ADR 0013 §6 stand unchanged — live WA source adapters
and live retrieval, durable WA capture, any change to the
`source_document_captures` `source_system` constraint, migrations for WA
capture, and production audit storage. Section-level body-text extraction and
validation, and an authoritative currency source for effective/status
determination, remain open owner decisions.

## Rollback

The slice is additive and isolated: a standalone module plus tests, with no
migrations, no schema changes, and no persisted data to reverse. Now that it is
merged, rollback is a revert of merge commit
`d758ae7769282aedd188705ac2de8b432880d1a3` on a dedicated branch under normal
review, which removes `src/legal_ai/research/`, `tests/research/`,
`tests/support/research_audit.py`, and this document, and restores the previous
ledger entry.
