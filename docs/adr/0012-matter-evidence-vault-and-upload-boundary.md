# ADR 0012: Matter Evidence Vault and Safe Upload Boundary

- Status: Accepted
- Date: 2026-08-06
- Accepted: 2026-08-06

## Context

Casework Phase 3 introduces matter-scoped evidence records, safe binary upload,
original and derived provenance, human evidence review, and associations between
evidence and playbook checklist items.

ADR 0004 supplies an immutable content-addressed byte store and the
`provenance_artifacts` identity. It does not define the casework evidence domain,
the upload trust boundary, evidence review, derived-evidence relationships, or
playbook-checklist association. Uploads were also outside the earlier MVP
implementation scope and therefore require an explicit architectural decision.

The existing immutable store remains required platform infrastructure and must
be reused rather than duplicated. Evidence content is untrusted data, never an
instruction. The evidence boundary remains limited to L0-L2 and grants no
external-action authority.

This decision is prospective from 2026-08-06. It authorises a future, separately
bounded Phase 3 implementation task within the decisions below. It does not
begin implementation, approve a branch or migration, or authorise publication
or merge of future implementation work.

## Decision

### 1. Existing storage reuse

The future implementation will reuse `LocalArtifactStore` and the existing
`provenance_artifacts` identity. It will not create a separate byte-storage
subsystem.

Immutable bytes are published and verified before database registration. If
database registration later fails, the verified content-addressed blob remains
available for retry, consistent with ADR 0004. Garbage collection of verified
unreferenced blobs remains deferred. No overwrite or deletion interface is
authorised.

### 2. Matter-scoped evidence identity

Phase 3 will introduce a casework evidence domain. Every evidence read and
write requires an authoritative `matter_id`. An artifact hash or evidence UUID
alone is never sufficient for a public lookup.

The database design and matter-scoped repository boundary must prevent:

- cross-matter reads;
- cross-matter evidence relationships;
- cross-matter checklist links; and
- caller-selected matter ownership.

### 3. Initial file allowlist

The initial allowlist is exactly:

| File family | Canonical media type | Accepted extension |
|---|---|---|
| PNG | `image/png` | `.png` |
| JPEG | `image/jpeg` | `.jpg`, `.jpeg` |
| MP4 | `video/mp4` | `.mp4` |
| Strict UTF-8 text | `text/plain` | `.txt` |

All other types are rejected by default. The following are explicitly outside
the initial allowlist:

- PDF;
- ZIP, TAR, GZIP, RAR, 7z, and all other archives;
- Office documents;
- executables and scripts;
- HTML, XML, and SVG;
- email containers;
- disk images; and
- unknown binary formats.

Adding another type requires a separately approved architecture or bounded
policy decision.

### 4. Deterministic file-family validation

The future implementation will use bounded, deterministic validation written
with the Python standard library. No new dependency is approved.

Validation must compare the declared media type, the deterministically detected
file family, and the caller filename extension. All three must be mutually
consistent.

This validation is a bounded file-family check only. It does not establish:

- full media decodability;
- absence of malware;
- evidentiary authenticity;
- image or video accuracy;
- OCR or plate-number accuracy;
- biometric identity; or
- legal sufficiency.

### 5. Upload size and stream rules

The maximum artifact size is exactly `104857600` bytes (100 MiB).
`expected_byte_size` is mandatory and must be an integer greater than zero and
no greater than `104857600`.

The byte stream must:

- be processed incrementally without full-file buffering;
- stop immediately after exceeding the approved limit;
- fail if fewer or more bytes are received than expected;
- fail on empty input;
- fail closed on interruption or read failure; and
- calculate SHA-256 while streaming.

### 6. Caller filename policy

The caller filename is metadata only. It never controls filesystem paths,
storage keys, temporary paths, artifact identity, or database identity.

An accepted filename must:

- be normalised to Unicode NFC;
- be nonblank;
- contain no NUL or control character;
- contain no slash or backslash;
- not equal `.` or `..`;
- contain no absolute path, Windows drive prefix, UNC path, or extended UNC
  path;
- be no more than 255 bytes when UTF-8 encoded; and
- use an extension consistent with the detected media type.

Unsafe filenames are rejected rather than silently sanitised.

### 7. Evidence roles, kinds, and review states

The evidence roles are:

- `ORIGINAL`;
- `DERIVED`.

The evidence kinds are:

- `IMAGE`;
- `VIDEO`;
- `TEXT`.

Phase 3 has no generic `OTHER` or `OTHER_ALLOWED` kind.

The review states are:

- `UPLOADED`;
- `REVIEW_ACCEPTED`;
- `REVIEW_REJECTED`.

The only approved transitions are `UPLOADED` to `REVIEW_ACCEPTED` and
`UPLOADED` to `REVIEW_REJECTED`. Both terminal states remain terminal in Phase
3.

Review status records a human evidence-review decision only. It does not
establish legal authenticity, relevance, admissibility, truth, or sufficiency.

### 8. Original and derived evidence

Every derived evidence record has exactly one immediate source evidence record.
Longer provenance chains use repeated single-source derivations. Multi-source
derivations are deferred.

Every derivation records:

- matter identity;
- source evidence identity and source artifact SHA-256;
- derived evidence identity and derived artifact SHA-256;
- operation code and operation version;
- processor version;
- whether the operation was deterministic;
- an optional canonical parameter hash; and
- actor and timestamp.

Processor version is product-runtime provenance and must remain technically
precise.

The future implementation must prevent cross-matter derivation, missing source
records, cycles, update, deletion, and derived records whose output hash equals
the source hash.

Phase 3 registers provenance for externally produced derivatives. It does not
implement image processing, transcoding, redaction, thumbnail creation, frame
extraction, OCR, or computer vision. Metadata extraction alone is metadata and
is not a derived artifact.

### 9. Caller-supplied media metadata

Caller-supplied media metadata may be stored only as bounded, typed, explicitly
unverified, non-authoritative metadata.

The initially approved fields are:

- `IMAGE`: `width_px`, `height_px`;
- `VIDEO`: `width_px`, `height_px`, `duration_ms`.

Values must be positive integers within implementation-defined safe bounds.
The total serialised metadata must not exceed 4096 bytes.

Caller-supplied media metadata must never determine legal conclusions,
establish authenticity, update matter facts automatically, change authority,
mark checklist sufficiency, or be represented as detected or verified
metadata. Phase 3 tests may use synthetic fixtures only.

### 10. Checklist integration

Evidence may be associated with an item in the matter's currently pinned,
immutable playbook version. The association preserves:

- `matter_id`;
- `evidence_id`;
- the exact `playbook_version_id`;
- the exact `checklist_item_id`;
- actor; and
- timestamp.

The association is immutable historical provenance. It must not use mutable
live checklist-state rows as permanent identity. Historical links remain
attached to the playbook version current when the link was created, including
after a later playbook upgrade.

Creating an association must not automatically mark an item `PROVIDED` or
`NOT_APPLICABLE`, mark evidence legally sufficient, activate a playbook, modify
the playbook definition, or begin Phase 4 grounding work.

### 11. Matter status and authority

Authorised L0 operations are matter-scoped evidence metadata reads and
matter-scoped provenance traversal.

Authorised L1 operations for open matters are:

- upload and registration of internal evidence;
- registration of an approved derived relationship;
- recording a human review decision; and
- creation of an approved checklist association.

Closed matters permit authorised L0 metadata reads. They deny uploads,
derivations, review changes, new checklist links, mutation, and deletion.

Unsupported and `RESEARCH_AND_DRAFT_ONLY` matters may store internal evidence
at L1. Storage grants no external-action authority, does not make a matter
supported, does not permit checklist linkage without a valid authoritative
pin, and does not activate a playbook.

### 12. Immutability, update, and deletion

Original evidence identity, artifact identity, metadata, provenance,
derivation, and checklist links are immutable. No evidence delete API or silent
deletion is authorised. Direct database update or delete attempts must fail.

The only mutable business field permitted in Phase 3 is the controlled
`UPLOADED`-to-terminal review transition, together with row-version advancement
and review metadata.

Deletion, retention expiry, legal hold, and garbage collection require a future
separate decision.

### 13. Audit and transaction semantics

Successful business state and ordinary audit events must commit atomically.
Required ordinary events, as applicable, are:

- `EVIDENCE_UPLOAD_ACCEPTED`;
- `EVIDENCE_REGISTERED`;
- `EVIDENCE_DUPLICATE_REUSED`;
- `EVIDENCE_REVIEW_RECORDED`;
- `EVIDENCE_DERIVATION_REGISTERED`;
- `EVIDENCE_CHECKLIST_LINKED`; and
- `EVIDENCE_PROVENANCE_CONFLICT`.

Upload validation failures use `EVIDENCE_UPLOAD_REJECTED` with a bounded reason
code, including:

- `TYPE_NOT_ALLOWED`;
- `SIGNATURE_MALFORMED`;
- `DECLARED_TYPE_MISMATCH`;
- `EXTENSION_MISMATCH`;
- `EMPTY_INPUT`;
- `SIZE_LIMIT_EXCEEDED`;
- `UNSAFE_FILENAME`;
- `EXPECTED_SIZE_MISMATCH`; and
- `TRUNCATED_STREAM`.

`ACTION_DENIED` is reserved for authorisation or policy denial, including
cross-matter access, closed-matter writes, attempted mutation or deletion,
unauthorised checklist association, and authority-level denial.

Substantive rejections and authorisation denials are persisted through an
independent denial-only transaction after business-state rollback. Failure to
persist required denial evidence raises a typed evidence audit failure and
must never allow business mutation.

Pydantic validation errors, optimistic-concurrency failures, infrastructure
faults, and programming errors are not blanket-recorded as substantive policy
denials.

Audit metadata must not contain file bytes, extracted content, secrets, full
untrusted text, or unnecessary personal information.

### 14. Database enforcement boundary

The future PostgreSQL migration must enforce where practical:

- matter ownership;
- immutable identities;
- hash format and enumerated values;
- same-matter relationships;
- no delete and immutable fields;
- the controlled review-transition shape;
- single-source derivation and cycle prevention;
- checklist version and item membership; and
- safe downgrade refusal while Phase 3 data exists.

Application code must enforce:

- streaming and size limits;
- file-signature and filename rules;
- authority level and authoritative persisted matter state;
- closed-matter policy;
- rejection classification and audit orchestration; and
- no automatic legal sufficiency.

### 15. Migration direction

A separately authorised implementation may create migration
`0007_evidence_vault` with down revision `0006_playbook_framework`.

Downgrade must refuse while any Phase 3 evidence, derivation, or checklist-link
data exists. An empty downgrade may remove only objects introduced by migration
0007. It must not remove shared provenance artifact rows, immutable filesystem
blobs, or pre-existing casework or playbook records.

### 16. Explicit exclusions

This ADR does not authorise:

- PDF support or archive extraction;
- OCR, computer vision, plate recognition, facial recognition, or biometric
  processing;
- media decoding or malware-scanning claims;
- legal authenticity or evidence-admissibility assessment;
- live model calls or model-based evidence interpretation;
- Phase 4 research;
- UI or FastAPI work;
- email, external dispatch, or OAuth;
- production object storage or cloud deployment;
- real client data; or
- L3+ authority.

## Alternatives considered

### Extend ADR 0004 without a new ADR

Rejected. ADR 0004 defines immutable source-artifact storage but not the
casework evidence domain or upload trust boundary.

### Introduce separate evidence byte storage

Rejected. The existing immutable content-addressed store already satisfies the
byte-storage requirements, and duplication would create conflicting identity
and lifecycle rules.

### Add a general MIME-detection dependency

Deferred. The initial allowlist is small enough for bounded deterministic
standard-library validation. A broader type policy requires a separate
decision.

### Support multi-source derivation

Deferred. Single-source derivation keeps Phase 3 provenance bounded and
enforceable while still permitting longer chains.

### Permit PDF and archives

Deferred. These formats introduce broader parsing, active-content, recursive
container, and malformed-input risks outside the Phase 3 boundary.

## Consequences

Positive consequences:

- existing immutable storage and artifact identity are reused;
- evidence records and relationships are matter-isolated;
- upload validation is deterministic and fail-closed;
- original and derived provenance is explicit;
- checklist associations preserve pinned-version history;
- no new dependency is introduced; and
- no external-action authority is added.

Costs and limitations:

- the allowlist is intentionally narrow;
- file-family validation does not prove safety, authenticity, or decodability;
- verified unreferenced blobs may remain after database failure;
- no delete, retention, legal-hold, or garbage-collection lifecycle exists;
- single-source derivation excludes composite transformations;
- review status is not legal sufficiency; and
- production storage and content analysis remain deferred.

Phase 3 remains Not Started until a separate bounded implementation task is
explicitly authorised. That future task must preserve ADR 0004, ADR 0009, ADR
0010, repository governance, and every boundary in this decision.
