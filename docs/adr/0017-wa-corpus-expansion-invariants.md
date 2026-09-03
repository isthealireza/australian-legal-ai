# ADR 0017: WA Corpus Expansion — Invariants, Phases and Gates

- Status: Proposed
- Date: 2026-09-03
- Accepted: not yet accepted — owner authorisation required before merge
- Builds on: [ADR 0013](0013-phase-4-research-evidence-packets.md), [ADR 0014](0014-phase-4-slice-2-section-text-records.md), [ADR 0016](0016-agent-orchestration-foundation.md)
- Governed by: `PROJECT_GOVERNANCE.md` §2, §4, §8, §9; `ENGINEERING_WORKFLOW.md` §1–4, §11–14

## Context

The recorded WA corpus is one Act: Road Traffic Act 1974 (WA), consolidated
version `14-t0-00`, with ss 55–56 recorded as manifest pinpoints and, since
ADR 0014, as extracted section body text. The owner intends to support more
verified WA road-traffic and vehicle-law provisions.

Every phase of that expansion will make the same safety claim — that ss 55–56
still behave exactly as they do today. Nothing in the repository currently
states what "exactly as they do today" means in one place, and five structural
properties of the current implementation make expansion riskier than it looks:

1. `RecordedWaCorpus.select` (`corpus.py:141-159`) matches a normalised Act
   title and nothing else. Zero matches refuse as `RETRIEVAL_MISSING`; two or
   more raise `AmbiguousSelection` → `SELECTION_AMBIGUOUS`. The corpus holds
   **one manifest per Act title**.
2. `ResearchQuery` (`models.py:113-121`) has no version and no as-at date, so a
   second compilation of the same Act is not addressable even in principle.
3. `_find_provision` (`validation.py:105-117`) returns the **first** match.
   Duplicate provisions resolve by list order, silently.
4. `REPEALED` is a *known* status. `validate_recorded_source` refuses only
   `UNKNOWN` (`validation.py:162-170`, `models.py:151-156`), so a repealed
   source validates into a legal packet today.
5. Section digests are never recomputed on the data path. ADR 0014 §3 says so
   explicitly and defers integrity to "tests and, in the future, a verification
   pipeline". `sections` never reaches `WaEvidencePacket`, and no consumer
   exists on `main`.

Points 3, 4 and 5 are live defects independent of expansion. Expansion turns
each of them from unlikely into probable.

This ADR records the invariant set, the phase plan and the gates. **This slice
adds no corpus content and changes no production code.** It delivers the
golden regression harness and this record, in that order, so that every later
phase has something concrete to be measured against.

## Decision

### 1. The golden harness comes before anything else

`tests/research/test_golden_ss_55_56.py` freezes the recorded state of
ss 55–56 in one clearly-marked `GOLDEN CONSTANTS` block: source identity,
official URL, version, legal status, both dates, retrieval timestamp, the
whole-instrument digest and byte length, the exact provision list, both
headings, the section records, the audit event shape and count, and the typed
refusal codes for near-miss and wrong-pinpoint lookups.

Section body text is frozen by **SHA-256 and exact character length**. The text
is never reproduced in the test module. This pins the bytes without copying
statutory text into source control a second time, and the length makes a
truncated or silently re-extracted record visible.

A failure in that module means recorded behaviour moved. It is never to be
resolved by editing the constants to match; it is a defect or a separately
authorised corpus change.

### 2. Invariants

**Existing, must not weaken.**

- **I1** Exact unmodified source bytes; the digest is recomputed at validation
  (`validation.py:192`) and must equal the recorded value.
- **I2** HTTPS, allowlisted host, port 443 or none, no credentials in the URL
  (`validation.py:69-86`, `types.py:16-21`).
- **I3** `source_system == "wa_legislation"` and
  `jurisdiction == act_jurisdiction == "WA"`.
- **I4** A source version suffix **or** a compilation date is present.
- **I5** Status is known, and `status_date <= retrieved_at.date()`.
- **I6** Check order is fixed and total: identity and allowlisting, then
  provenance, then content integrity, then citation, then pinpoint. A source
  that fails integrity never reports a citation-level result.

**New, required before the corpus grows.**

- **I7** The active corpus root holds exactly one manifest per normalised Act
  title. Superseded versions live **outside** the injected root, because
  `_load_entries` globs recursively (`corpus.py:113`) and an in-root archive
  would immediately make every lookup ambiguous.
- **I8** `sha256(text.encode("utf-8")) == text_sha256`, recomputed at the
  section trust boundary rather than only in tests.
- **I9** Every section identifier binds to exactly one manifest provision, and
  section identifiers are unique within a file.
- **I10** `verified` is exactly Python `True` (`corpus.py:212` is an identity
  check, not a truthiness check). Every other value is `False`.
- **I11** No two manifest provisions may normalise to the same identifier or
  pinpoint. This closes the first-match hole in `_find_provision`.
- **I12** An explicit repealed and superseded policy, decided by the owner.

**Citation, quote and entailment.**

- **I13** Citation existence in the evidence packet — deterministic; exists.
- **I14** Pinpoint integrity against the exact source version — deterministic;
  exists.
- **I15** Quote containment: any quoted text must be a byte-exact substring of
  verified section text. **No quote field exists** in `ResearchQuery` or
  `WaEvidencePacket` today, so this is new contract surface needing its own
  refusal code. A quote failure must never be relabelled onto
  `CITATION_NOT_FOUND` or `PINPOINT_MISMATCH`.
- **I16** Entailment (level 3) is out of scope for corpus expansion and must not
  be weakened by it. When it arrives, its only admissible input is section text
  that is both `verified=True` and digest-checked at the point of use.

### 3. Six failure modes have no typed refusal code

These must not be mapped onto existing codes without an authorised contract
change, because conflating them would make an audit trail lie about why the
system refused:

| Failure | Today |
|---|---|
| Repealed or superseded source | validates |
| Duplicate exact provisions in one manifest | first match wins |
| Section text digest mismatch | no code |
| Section identifier absent from the manifest | no code |
| Manifest provision with no section; duplicate section identifiers; malformed sections file | no code |
| Quote not present in source | no code, and no quote contract |

### 4. Phases

| Phase | Scope | Adds legal content |
|---|---|---|
| **E1** Golden freeze | `tests/research/test_golden_ss_55_56.py`, this ADR | no |
| **E0** Invariant hardening | `research/types.py` (new codes), `validation.py` (I11, the I8 boundary), `corpus.py` (I9), `models.py`, `tests/research/` | no |
| **E2** Staging tooling | `scripts/` operator tools writing to staging only, never promoting | no |
| **E3** First additional Act | `tests/fixtures/wa_legislation/<act>/`, its own ADR | **yes** |
| **E4** Version lineage and as-at selection | `models.py`, `corpus.py`, `validation.py`, its own ADR | no |
| **E5** Quote contract | `models.py`, `validation.py`, `types.py`, its own ADR; blocked on a merged answering pipeline | no |

Order is **E1 → E0 → E2 → E3**, with E4 and E5 deferred. Freeze before
changing; harden before adding. Each phase is one bounded task, one branch, one
ADR, and is revertable on its own.

### 5. Ingestion pipeline for E2 and E3

Capture the official PDF over HTTPS from an allowlisted host, recording URL, UTC
retrieval time and digest. Stage it under a staging root, never the active one.
Generate the manifest deterministically. Extract section text offline with
`pdftotext -layout`, as ADR 0014 §6 established, recording the poppler version
because extraction reproducibility depends on it. Then the human verification
gate. Then promotion.

No step involves a model. Ingestion, hashing, digest chaining, selection,
pinpoint matching and quote checking are deterministic code, permanently
(`PROJECT_GOVERNANCE.md` §2.3).

### 6. Feature flag and rollback

The corpus root is already an injected constructor argument, so the real gate is
**root selection, not a boolean**: an expanded corpus is a different root that
must be opted into, defaulting to the current fixture root. Section consumption
sits behind a second, independent flag defaulting off; even when on, the
per-section `verified=True` and digest gates still apply.

A flag may only narrow capability. No flag may weaken a refusal, and an
unparseable value resolves to the most restrictive branch rather than the
permissive one.

Rollback is a fixture revert: corpus content is version-controlled, there is no
migration and no database. Promotion is additive and superseded versions live
outside the root, so reverting the active pointer restores prior behaviour. The
golden harness is the tripwire — if any ss 55–56 assertion moves, the promotion
is rejected.

### 7. Mandatory owner gates

None of these is autonomous under the boundary recorded in
`orchestration/approvals.py`:

- **G1** Official-source verification and acceptance of every new source URL,
  version and retrieval — `LEGAL_CONTENT_ACCEPTANCE`.
- **G2** Human legal-content acceptance: flipping `verified: true` requires an
  independent human comparison against the official document. Never automated,
  never model-assisted.
- **G3** The repealed and superseded policy — `GOVERNANCE_CONTROL_CHANGE`.
- **G4** Any new refusal code, or any change to the fixed check order.
- **G5** Acceptance of each phase's ADR.
- **G6** Merge to a protected branch.

Digest, provenance, citation, quote and entailment checks (I1, I8, I13–I16) and
the regression harness are gate conditions for every phase: a phase that cannot
demonstrate all of them passing does not proceed.

## Consequences

**Kept.** No production file changes in this slice. No corpus file changes. No
existing test changes. `research/`, `provenance/`, `legislation/` and
`sources/` behave identically, because the only addition is a test module that
reads the committed fixture.

**Gained.** The claim every later phase depends on is now a single executable
artefact rather than a sentence in a plan, and the six missing refusal codes are
recorded before they are needed rather than discovered during an expansion.

**Cost.** The golden harness deliberately duplicates some coverage in
`test_recorded_fixture.py` and `test_sections.py`. That duplication is the
point: those modules test behaviour and may legitimately evolve, while this one
exists to refuse drift.

**Deliberately excluded.** Contract Builder. Any corpus content. Any production
code change. Any new refusal code — recorded here, implemented in E0. Database,
authentication, API, provider settings, live retrieval, network, and any L2+
authority.

## Rollback

Delete `tests/research/test_golden_ss_55_56.py` and this ADR, and remove the one
appended line in `docs/adr/README.md`. Nothing imports either file and no
production behaviour depends on them, so removal is complete.
