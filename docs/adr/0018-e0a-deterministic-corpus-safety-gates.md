# ADR 0018: E0-A — Deterministic Corpus-Safety Gates

- Status: Proposed
- Date: 2026-09-03
- Accepted: not yet accepted — owner authorisation required before merge
- Builds on: [ADR 0013](0013-phase-4-research-evidence-packets.md), [ADR 0014](0014-phase-4-slice-2-section-text-records.md), [ADR 0017](0017-wa-corpus-expansion-invariants.md)
- Implements: the E0-A slice defined in ADR 0017 §9
- Base: `feat/e1-golden-regression-harness`. This slice is stacked on the E1 golden harness, which is unmerged.

## Context

ADR 0017 recorded eight defects that make WA corpus expansion riskier than it
looks, and split them into what is routine deterministic engineering and what
needs an owner decision. E0-A is the first, narrowest implementation slice: the
three defects that need no legal judgement and change no answer that the corpus
can currently produce.

Each of the three could produce a *confidently wrong citation* — not a refusal,
not an error, but a validated evidence packet naming the wrong law. That is the
worst failure mode this system has, because every downstream control trusts a
validated packet.

1. **Provision resolution took the first match.** `_find_provision` looped
   `source.provisions` and returned the first whose normalised identifier *or*
   pinpoint matched the request. Two provisions matching one request meant the
   order of a manifest decided which law was cited.
2. **Section body text had no integrity check on any data path.** ADR 0014 §3
   recorded `text_sha256` and stated plainly that `_load_sections` does not
   recompute it, delegating verification to "tests and, in the future, a
   verification pipeline". `verified=False` was the documented safety default
   with nothing to enforce it. This was safe only while nothing consumed
   section text, and it is the gate that has to exist before the first consumer.
3. **A companion sections file could describe a different document.** The file
   records `source_id` and `source_document_sha256`, and `_load_sections`
   discarded both, reading only the `sections` array. A sections file paired by
   filename stem with an unrelated manifest would load, and its records could
   pass every per-section check that E0-A adds. `main` has no parent-digest
   chain; the chaining ADR 0015 designed exists only on an unmerged branch.

Defect 3 was found by the Codex review of the E0 specification, not by the
specification itself. Without it, the digest gate in defect 2 would have been
partly illusory: a section could be genuinely verified and genuinely
digest-consistent, and still belong to another Act.

## Decision

### 1. Provision resolution refuses ambiguity instead of ordering it

`_find_provisions` (`validation.py:105`) returns **every** provision the request
matches. `validate_recorded_source` then maps zero matches to
`CITATION_NOT_FOUND` — unchanged — and more than one to `PROVISION_AMBIGUOUS`.
No first-match path remains.

Two properties are deliberate:

- **Ambiguity is per request, not per source.** A manifest may contain a
  collision that a given request does not touch; that request is still
  answered. Refusing the whole source would fail closed further than the defect
  warrants and would break sources that are fine for the question asked.
- **It catches collisions where no record is duplicated.** If provision *A* has
  pinpoint `section 55` and provision *B* has identifier `section 55`, neither
  record is a duplicate, yet the request `section 55` matches both. This is the
  case a naive duplicate check misses.

### 2. A section verification gate, in fixed order

`src/legal_ai/research/sections.py` is the sanctioned path from a
`RecordedWaSource` to section text a consumer may read. Five checks, in this
order, each with its own typed refusal:

1. the companion file must claim this exact document — `SECTION_SOURCE_MISMATCH`;
2. the identifier must resolve to exactly one section — `SECTION_TEXT_MISSING`
   for none, `SECTION_AMBIGUOUS` for more than one;
3. the identifier must be declared by exactly one manifest provision —
   `SECTION_NOT_IN_MANIFEST`;
4. `verified` must be exactly `True` — `SECTION_NOT_VERIFIED`;
5. the recomputed digest must equal the recorded digest —
   `SECTION_TEXT_HASH_MISMATCH`.

Order is part of the contract. A file describing a different document is refused
before any record inside it is examined, so a mis-bound file cannot be probed
through the later codes. `verified` is checked before the digest so that text
nobody has verified is refused on that ground rather than incidentally.

`verified` is compared by identity, matching the loader's `entry.get("verified")
is True` (`corpus.py`). `"yes"`, `"true"`, `1`, `0`, `[]` and an arbitrary object
are all refusals. A failed digest is never overridden by human verification.

### 3. Section records are bound to their parent document

`_load_sections` now returns a private `_SectionsFile` carrying the sections plus
the file's declared `source_id` and `source_document_sha256`. `_read` attaches
those to `RecordedWaSource` as two new **defaulted** fields,
`sections_source_id` and `sections_source_document_sha256`. The gate refuses
unless both are present and equal the source's own `source_id` and `sha256`.

`_load_sections` keeps its ADR 0014 §4 semantics **exactly**: it still never
raises, still returns an empty result for a missing, oversized, unreadable,
non-JSON, non-mapping or malformed file, and still silently skips individual
entries missing `identifier`, `text` or `text_sha256`. Only the return *type*
changed, and it is private.

Absence is a refusal, not a pass. A sections file that declared no binding is
refused, because a file that does not say which document it describes cannot be
trusted to describe this one.

### 4. What `VerifiedSection` proves, and what it does not

`VerifiedSection` re-runs the digest check in its own model validator, so direct
construction and `model_validate` both raise on a mismatch.

It proves less than its name suggests, and the docstring says so rather than
implying otherwise:

- **Self-evident on any instance** — the text matches `text_sha256`.
- **Not self-evident** — the parent binding, the manifest declaration, and the
  `verified` flag. Those are properties of the *source*, not of the fields the
  type carries, so they cannot be re-derived from an instance. They are proven
  only by provenance: by having come from `verify_section`.
- **Two Pydantic bypasses** — neither `model_copy` nor `model_construct` runs
  validators, and `model_construct` is a documented validation bypass that can
  produce an instance whose digest does not match at all. Neither is
  preventable from inside the model. Both are pinned by tests so the limit stays
  visible.

A future consumer must therefore accept `VerifiedSection` values only from
`verify_section` and must not treat the type alone as authority.

### 5. Seven new refusal codes

| Code | Meaning |
|---|---|
| `PROVISION_AMBIGUOUS` | the request matches more than one recorded provision |
| `SECTION_SOURCE_MISMATCH` | the sections file declares no binding, or names a different source or parent digest |
| `SECTION_TEXT_MISSING` | no section record for the requested identifier |
| `SECTION_AMBIGUOUS` | more than one section record shares the identifier |
| `SECTION_NOT_IN_MANIFEST` | no single manifest provision declares the identifier |
| `SECTION_NOT_VERIFIED` | `verified` is not exactly `True` |
| `SECTION_TEXT_HASH_MISMATCH` | the recomputed section digest disagrees with the record |

None is mapped onto an existing code. ADR 0017 §3 already ruled that out:
conflating them would make the audit trail state the wrong reason for a
refusal. In particular a section-text digest failure is **not**
`HASH_MISMATCH`, which means whole-instrument integrity.

Adding enum members is backward compatible here because nothing in `src/` or
`tests/` matches exhaustively on or iterates `ResearchRefusalCode`.

### 6. No consumer is added

E0-A builds the gate and stops. Nothing calls `verify_section` in production
code. This is deliberate: both recorded sections carry `verified: false`, so the
gate refuses them, which is the correct state until a human has compared the
extracted text against the official document. That is gate **G2** in ADR 0017
and E0-A must not pre-empt it.

The consequence, stated plainly: the gate's correctness rests on its own tests
until a consumer exists.

## Compatibility

**ss 55–56 are unchanged.** The recorded manifest holds exactly two provisions
whose four normalised forms are pairwise distinct, so `PROVISION_AMBIGUOUS` is
unreachable for it. The recorded companion file does declare the correct
`source_id` and `source_document_sha256`, so binding is not the blocker for it
either; the sections refuse only on `SECTION_NOT_VERIFIED`, which is the
intended state.

**The E1 golden harness passes unmodified**, as do `test_sections.py`,
`test_recorded_fixture.py` and `test_corpus.py`. The harness reads
`source.sections` directly and is unaffected by a gate it does not call.

**Existing builders keep working.** The two new `RecordedWaSource` fields are
defaulted, so every synthetic builder in `tests/research/conftest.py` and every
inline manifest builder constructs unchanged.

The one behavioural change is provision resolution, and it alters results only
where a request matches more than one provision — which no current fixture or
synthetic builder produces.

## Validation

```
uv run ruff check .                  All checks passed!
uv run ruff format --check .         147 files already formatted
uv run mypy .                        Success: no issues found in 147 source files
uv run pytest -m "not integration"   995 passed, 45 skipped, 100 deselected
```

CI on `ubuntu-latest`: 998 unit tests and 144 PostgreSQL integration tests pass.
The two `tests/research/test_sections.py` symlink tests fail on the Windows
development workstation with `OSError [WinError 1314]` because creating a
symlink needs a privilege the shell does not hold. They are pre-existing on
`main`, they fail while creating the symlink before any corpus behaviour runs,
and CI runs them successfully.

No added test uses a network, a live provider, a secret, a clock or a database.

## Review and the OpenCode report gap

**Codex, read-only.** Confirmed no scope breach, correct fail-closed behaviour
in provision resolution, correct gate ordering and semantics, and complete
parent binding with ADR 0014 loader semantics preserved. It raised one blocking
finding that was correct: the `VerifiedSection` docstring overclaimed what
holding an instance proves. §4 above and the corrected docstring are the
response.

**OpenCode/DeepSeek, read-only — no report delivered.** The independent
second-opinion evaluation did not complete. Its first attempt halted on an
exhausted OpenRouter credit limit. A refreshed credential worked and it ran on
`deepseek/deepseek-v4-flash-0731` to roughly 70.8K context, but it was stopped
by an owner speed decision before reporting, and was deliberately not retried to
avoid consuming credit. Its worktree was verified clean; it wrote nothing.

The consequence is recorded rather than smoothed over: **E0-A rests on a single
reviewer.** The question that evaluation was commissioned to answer — which
deterministic corpus-safety hole remains open after this slice — has no
independent answer. The same gap applies to ADR 0017.

## Owner-gated decisions still required

E0-A deliberately decides none of these. They are listed so that merging this
slice is not mistaken for settling them.

- **Repealed and superseded policy — DEFERRED.** A repealed source still
  validates into a legal packet today: `_legal_status` classifies `REPEALED`
  and only `UNKNOWN` refuses. This is the highest-value defect on the ADR 0017
  list and it remains live. Choosing among P-strict, P-asat and P-marked is a
  legal-content judgement and `ProtectedDecision.GOVERNANCE_CONTROL_CHANGE`
  (ADR 0017 gate G3).
- **As-at and version selection semantics — DEFERRED** to E4. `ResearchQuery`
  still gains no version or as-at field.
- **`version.currency_end` and `act.assent_date` — DEFERRED.** Both are recorded
  in the manifest and read nowhere. Reading them is entangled with the policy
  decision above.
- **Date-consistency ordering — DEFERRED.** Whether `currency_start` must
  precede `status_date`, and `assent_date` precede `currency_start`, is a light
  legal-semantics judgement, not pure engineering.
- **`source_id` component binding — DEFERRED.** Withdrawn from E0-A during
  review: slug agreement between `source_id` and `act.title` does not hold for
  existing synthetic builders, so it cannot be added without editing existing
  tests.
- **Approval of the seven refusal codes — REQUIRED.** ADR 0017 gate G4 reserves
  any new refusal code, and any change to the fixed check order, to the owner.
- **Acceptance of this ADR, and merge — REQUIRED** (gates G5, G6).

## Consequences

**Kept.** Fail-closed refusal, deterministic citation and provenance, the fixed
check order, the permanent disclaimer and the audit controls are untouched. No
fixture, no legal content, no corpus change, no consumer, no product-model tool,
no API, provider, authentication or database surface.

**Gained.** Three paths to a confidently wrong citation are closed, and the
section trust boundary exists before the first consumer rather than after it.

**Cost.** A gate with no caller. Seven codes that no production path yet emits.
And an honest limit on `VerifiedSection`: it is authority by provenance, not by
type.

**Explicitly excluded.** Contract Builder. Any legal content. Repealed,
superseded and as-at policy. Version selection. `source_id` slug binding. Any
L2+ authority.

## Rollback

Revert `c303e39`, `8254e6c` and `f8593de`, or drop
`feat/e0a-corpus-safety-gates`. Deleting `src/legal_ai/research/sections.py`,
`tests/research/test_provision_ambiguity.py`,
`tests/research/test_section_verification.py`, this ADR and its index line, then
reverting the `types.py`, `validation.py`, `corpus.py`, `models.py` and
`__init__.py` changes, restores the tree exactly.

No migration runs, no fixture changes, no persisted state exists, and nothing
imports the new gate, so removal leaves no residue.
