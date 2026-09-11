# ADR 0019: E2 — The WA Staging and Promotion Pipeline

- Status: Proposed
- Date: 2026-09-10
- Accepted: not yet accepted — owner authorisation required before merge
- Builds on: [ADR 0013](0013-phase-4-research-evidence-packets.md), [ADR 0014](0014-phase-4-slice-2-section-text-records.md), [ADR 0017](0017-wa-corpus-expansion-invariants.md), [ADR 0018](0018-e0a-deterministic-corpus-safety-gates.md)
- Implements: phase **E2** from ADR 0017 §4
- Base: `feat/e0a-corpus-safety-gates`, itself stacked on the E1 golden harness.

## Context

The owner approved the **C1 batch**: Road Traffic (Vehicles) Act 2012, version
`01-j0-00`, verified page-side as in force with currency start 7 October 2024.

ADR 0017 §5 requires that a source be captured, staged, manifested, extracted,
human-verified and only then promoted into the active corpus root. When the
candidate inventory first drafted that batch it listed the promoted fixture
files directly, and review classified that as blocking: writing straight into
the active root would satisfy every acceptance criterion while bypassing the
promotion control itself. E2 is that control, built.

**This slice adds no legal content.** It captures nothing, promotes nothing, and
changes no fixture. It is the tooling that makes a later capture safe.

## Decision

### 1. The tooling lives outside the product package

Everything is under `scripts/wa_ingest/`, not `src/legal_ai/`. The product
package must never gain an ingestion, extraction or capture capability
(`PROJECT_GOVERNANCE.md` §7, `ENGINEERING_WORKFLOW.md` §13), and the cleanest
way to guarantee that is for the code not to be in it. Nothing in `src/` imports
this package.

### 2. Nothing fetches

`stage` takes a path to a file the operator has **already downloaded** from the
official source. There is no URL parameter and no HTTP client anywhere in the
pipeline.

This is a deliberate design choice rather than an omission. The act of capture
carries the judgement about what is authoritative, so it belongs to a person.
It also means no code path in this repository can retrieve legislation, which is
a stronger property than any allowlist.

The URL is still validated at staging against the same rules the runtime
applies — https, allowlisted WALW host, default port, no credentials — so a
capture that would later fail validation fails before the bytes are staged.

### 3. Determinism

Digests and byte lengths are recomputed from the file on disk and never accepted
as inputs, so a manifest cannot claim a digest its own bytes do not have. JSON
is written with sorted keys, two-space indent and LF endings, so the same inputs
produce byte-identical files. `slug_for_title` reproduces the existing corpus
convention exactly.

### 4. The extraction tool is recorded, and mismatches are refused

ADR 0014 §6 extracted the recorded ss 55–56 text with `pdftotext` from
**poppler-utils**. The `pdftotext` on the current workstation is **Xpdf 4.06**.
This is not a footnote: the two implementations lay text out differently, so the
same PDF produces different text and therefore different `text_sha256` values.
A sections file that does not say which tool produced it cannot be reproduced.

Three consequences are built in:

- `detect_tool` identifies the implementation from its banner and **refuses an
  unrecognised one** rather than guessing.
- Every sections file records the implementation, version, arguments and the
  normalisation applied.
- `require_tool` refuses any implementation other than poppler-utils unless the
  operator passes `--expect-tool` to accept the divergence deliberately.

A practical wrinkle worth recording: Xpdf's `pdftotext -v` writes its banner to
stderr and exits **99**. Version probing therefore ignores the exit code and
reads both streams, while extraction proper still demands exit 0. This was found
by smoke-testing the real binary, not by reading its documentation.

### 5. Normalisation changes nothing inside a line

Line endings become LF, trailing whitespace is stripped per line, runs of blank
lines collapse to one, and the result is stripped at both ends — exactly ADR
0014 §6 and nothing more. No spelling, punctuation or content correction of any
kind. The text must remain the source's, not the tool's opinion of it. A test
pins that a line containing an em dash, a curly apostrophe and smart quotes
passes through byte-identical.

### 6. `verified` cannot be set by anything automated

`build_sections_file` writes `verified: false` for every record and has **no
parameter that could express otherwise**. Gate G2 is a human act; the tooling's
role is to make it impossible to skip, not to perform it.

### 7. Promotion refuses by default

`check_promotion` returns a typed `PromotionRefusal` or a plan, and `promote`
writes into the active root only on a plan. Sixteen refusal reasons cover
staging completeness, digest integrity, section-to-manifest binding, section
digests, duplicate identifiers, tool recording, and the ADR 0017 invariants I7,
I9 and I11.

Two of them cannot be satisfied by correct engineering, which is the point:

- **`OWNER_APPROVAL_MISSING` / `OWNER_APPROVAL_MISMATCH`** — gate G1. An
  approval record must name an approver and match the manifest's `source_id`,
  URL, version suffix, currency start, retrieval timestamp and digest field for
  field. Approving one capture must not silently approve another.
- **`SECTION_VERIFIED_WITHOUT_RECORD`** — gate G2. A `verified: true` section
  requires a record naming who compared it, against what, and when.

The approval record stays in staging and is **not** copied into the corpus: it
is evidence about a decision, not corpus content.

### 8. One shared-config change

`pyproject.toml` gains `pythonpath = ["."]` under `[tool.pytest.ini_options]` so
the tooling under `scripts/` is importable by its tests. `legal_ai` itself
continues to resolve through the editable install. This is the only change
outside `scripts/`, `tests/ingestion/` and `docs/`, and it is declarative rather
than `sys.path` manipulation inside a conftest.

## Consequences

**Kept.** No legal content, no fixture change, no corpus change. No `src/` file
changes. The E1 golden harness, E0-A and every existing test are untouched. The
product gains no capability of any kind.

**Gained.** The promotion control ADR 0017 required now exists and refuses, and
the poppler-versus-Xpdf divergence is caught before it can silently produce a
corpus whose two instruments were extracted by different tools.

**Cost.** A pipeline with nothing yet run through it. Its correctness rests on
99 synthetic tests until the owner performs a real capture. That is the right
trade against capturing legal content before the gates exist.

**Deliberately excluded.** Capture, promotion, any fixture, any legal content,
the repealed/superseded policy, as-at semantics, `source_id` slug binding, and
Contract Builder.

## Owner gates still required

- **G1** official-source acceptance for the C1 capture.
- **G2** human verification of every extracted section.
- Acceptance of this ADR, and of ADRs 0017 and 0018, all still `Proposed`.
- Merge approval.
- The **repealed/superseded policy**, still deferred and now more pressing: a
  second Act brings a second independent currency lineage, and a repealed
  source still validates into a legal packet today.

## Evidence gap

No independent review of this slice exists. Orca orchestration was unavailable
when it was built — the coordinator terminal that hosted the earlier runs was
gone, so no Run could be created and no Codex reviewer dispatched. Every prior
slice in this programme carried a read-only Codex review; this one does not.
The OpenCode/DeepSeek evaluator has delivered no findings at any point.

## Rollback

Delete `scripts/wa_ingest/`, `scripts/__init__.py`, `tests/ingestion/`, this
ADR, its index line, the runbook, and revert the one `pyproject.toml` line. No
migration, no fixture, no corpus and no persisted state is involved.
