# ADR 0014: Phase 4 Slice 2 — Recorded Section Body-Text Records

- Status: Accepted
- Date: 2026-08-17
- Accepted: 2026-08-17 (owner-approved)

## Context

Phase 4 Slice 1 (ADR 0013) introduced deterministic retrieval, WA evidence-packet
validation, and a typed refusal path over the recorded Road Traffic Act 1974 (WA) fixture.
Sections 55 and 56 are recorded as manifest pinpoints only: citation existence and
pinpoint integrity are validated, but no section body-text is stored, validated, or
available to a downstream drafting pipeline.

ADR 0013 §5 explicitly deferred per-section body-text extraction. The deferred
rationale was that section-level extraction would require a PDF parsing dependency,
and new dependencies are prohibited under the project's constraints. That rationale
applied to programmatic extraction. It does not apply to hand-transcription: a
hand-transcribed body-text record is a durable, version-controlled fixture, not a
runtime PDF-parsing operation, and introduces no new dependency.

The MVP pipeline (MVP_ROADMAP.md §5) requires that a drafting model be given exact
statutory text as a grounded evidence input. Without per-section body-text records,
Phase 5 (grounded drafting) cannot proceed. Slice 2 adds those records as a bounded,
dependency-free, fail-closed extension of the existing corpus format.

## Decision

### 1. `RecordedSection` dataclass

A new `RecordedSection` frozen dataclass is added to `models.py`:

```python
@dataclass(frozen=True, slots=True)
class RecordedSection:
    identifier: str
    heading: str | None
    text: str
    text_sha256: str
    verified: bool = False
```

`RecordedSection` is untrusted recorded data. The `verified=False` default is the
safety invariant: the pipeline refuses to use any section whose `verified` flag is
not exactly `True`. Only an independent human verification of the transcription
against the official source document may change this field.

### 2. Sections field on `RecordedWaSource`

`RecordedWaSource` gains one new field:

```python
sections: tuple[RecordedSection, ...] = ()
```

The field is **defaulted to `()`** so that all existing test builders
(`conftest.py`, synthetic corpus doubles) continue to construct `RecordedWaSource`
without supplying a `sections` argument.

### 3. Companion sections file

Section body-text records are stored in a companion file alongside the manifest:

```
<stem>.manifest.json   ← existing
<stem>.sections.json   ← new (optional; missing → sections=())
```

The sections file is a JSON object with a top-level `"sections"` array. Each
entry carries: `identifier`, `heading` (optional), `text`, `text_sha256`, and
`verified` (always `false` in recorded fixtures until human verification is
complete).

The `text_sha256` digest is `sha256(text.encode("utf-8")).hexdigest()`. The corpus
loader validates this in tests; `_load_sections` itself does not recompute the
digest at load time — integrity verification is delegated to tests and, in the
future, to a verification pipeline.

### 4. `_sections_path` and `_load_sections` in `RecordedWaCorpus`

Two new instance methods are added to `RecordedWaCorpus`:

- `_sections_path(manifest_path)`: returns the resolved companion path if it is a
  regular file inside the fixture root and is not a symlink; otherwise `None`.
- `_load_sections(manifest_path)`: reads and parses the companion file; returns an
  empty tuple on any read or parse error. Entries that are missing `identifier`,
  `text`, or `text_sha256` are skipped silently. This means a missing or
  malformed sections file is never a corpus error.

The `_read` method becomes an instance method (was `@staticmethod`) to access
`self._root` for the path safety check inside `_sections_path`.

### 5. `verified` is only `True` when the JSON value is exactly the Python `True`

The corpus loader maps `entry.get("verified") is True` — not a truthy check. The
values `"yes"`, `1`, `None`, `"true"`, and omission all produce `verified=False`.
This matches the `Literal[True]` enforcement pattern used in `EvidenceItem` and is
tested parametrically.

### 6. Recorded body-text: ss 55–56, Road Traffic Act 1974 (WA), version 14-t0-00

Hand-transcribed body text for sections 55 and 56 is recorded in:

```
tests/fixtures/wa_legislation/road_traffic_act_1974/
    road_traffic_act_1974_consolidated_14-t0-00.sections.json
```

Both sections carry `"verified": false`. The pipeline returns
`SECTION_TEXT_NOT_VERIFIED` for any real corpus query against these sections
until an independent human verification is performed and recorded.

### 7. No scope beyond this ADR

This slice adds:

- one new dataclass (`RecordedSection`) in `models.py`
- one new field (`sections`) on `RecordedWaSource` in `models.py`
- two new corpus methods (`_sections_path`, `_load_sections`) in `corpus.py`
- one modified corpus method (`_read`, `@staticmethod` → instance method) in `corpus.py`
- one new export (`RecordedSection`) in `__init__.py`
- one new fixture file (`*.sections.json`)
- one new test module (`tests/research/test_sections.py`)
- one updated document (`docs/execution/IMPLEMENTATION_STATUS.md`)

This slice does **not** add:

- any model use, live retrieval, network access, or persistence
- any drafting pipeline, answer service, or answer validation
- any migration, Evidence Vault write, or `source_document_captures` write
- any playbook activation or external action
- any new Python dependency
- any L3+ authority
- any modification to `service.py`, `validation.py`, `audit.py`, or `types.py`
- any modification to `FailClosedGroundingGate` (untouched; remains refuse-closed)

## Consequences

- Phase 5 Slice 1 (grounded drafting with a mock model) may proceed after this
  slice is merged and ADR 0015 is accepted, subject to a separate owner
  authorisation.
- Real drafting against ss 55–56 of the Road Traffic Act 1974 (WA) remains
  impossible until an independent human verification of the transcription is
  performed and recorded as `"verified": true` in the sections fixture.
- All existing tests continue to pass without modification: no existing builder,
  corpus double, or test creates a `RecordedWaSource` that is broken by the
  new defaulted `sections` field.
- Converting `EvidenceItem` to a dataclass would silently downgrade the
  `Literal[True]` enforcement in Phase 5; this note is preserved from ADR 0013.
