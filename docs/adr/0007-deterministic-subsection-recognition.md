# ADR 0007: Deterministic subsection and Schedule subclause recognition

- Status: Accepted
- Date: 2026-07-23

## Context

Sprint 1.3B1 produces a flat, ordered `StructuredLegislationDocument` with a
bounded Commonwealth legislation hierarchy and an active legal-container
ordinal for every block. Sprint 1.3B2A needs to recognise numeric subsection
markers beneath main-body Sections and the same marker shape as Schedule
Subclauses beneath Schedule Clauses, without reopening the EPUB or changing the
meaning of any B1 role.

Paragraph and subparagraph markers such as `(a)` and `(i)` are not safe to add
through the same rule. In particular, `(i)` can be a paragraph or a
subparagraph depending on hierarchy not established by this task. Assigning a
meaning from its spelling alone would invent structure.

## Decision

Implement a synchronous, pure, offline second-stage transformation from
`StructuredLegislationDocument` to a strict, frozen
`SubstructuredLegislationDocument`. The transformer has no filesystem,
network, database, persistence, retrieval, embedding, or model access. It does
not accept raw EPUB, XML, paths, URLs, bytes, dictionaries, or repositories.

The output contains exactly one block for every B1 input block in identical
global order. Every B1 field is copied unchanged, including source ordinals and
locator, generic block kind, XHTML metadata, original normalized text,
structural role, identifier and title, parent ordinal, and active-container
ordinal. No block is split, merged, duplicated, dropped, or rewritten.
Existing B1 structure diagnostics are retained unchanged in a separate typed
tuple from diagnostics emitted by this transformation, preserving their stage
and bounded code set.

Only a generic `paragraph` block is a candidate. A heading, list item, table
cell, definition term or description, blockquote, preformatted block, or
caption cannot become a subsection or Schedule Subclause. CSS classes, element
IDs, EPUB types, indentation, locators, and surrounding wording do not create
substructure.

Candidate text is matched as a complete string after deterministic
layout-whitespace collapse. The grammar is a literal opening parenthesis, an
identifier `[1-9][0-9]{0,2}[A-Z]{0,2}`, a literal closing parenthesis, required
layout whitespace, and non-empty substantive text. This accepts identifiers
such as `1`, `12`, `1A`, and `12AA`. It rejects zero, leading zeroes, lowercase
or excessive suffixes, more than three digits, decimals, brackets, incomplete
parentheses, bodyless markers, alphabetic markers, and nested markers. The
identifier and derived remaining text are preserved without semantic
rewriting, while the complete original text remains separately unchanged.

When the B1 active container is a `section_heading`, a recognised candidate is
a `subsection` whose parent is that Section. When the active container is a
`schedule_clause_heading`, it is instead a `schedule_subclause` whose parent is
that Schedule Clause. The two roles are distinct, and neither changes the
existing Section or Schedule Clause role. A supported-shaped marker elsewhere
remains role `none` and does not mutate state.

## Effective content-container invariant

The B1 active-container ordinal is immutable in the enriched output. A separate
effective content-container ordinal records the finer boundary:

- a recognised subsection or Schedule Subclause uses its own global ordinal;
- subsequent content uses the active subsection or Schedule Subclause;
- content before the first recognised marker uses its B1 active container;
- structural headings retain their documented B1 container behavior;
- unsupported candidates do not replace the current effective container; and
- content after Endnotes has no effective legal container.

This separation keeps the B1 contract stable while making the finer content
attachment explicit and deterministic.

## State and diagnostics

A new Section replaces any active subsection. New Chapter, Part, Division,
Subdivision, Section, or Schedule headings clear subsection state. A new
Schedule Clause replaces any active Schedule Subclause. New Schedule, Schedule
Part, Schedule Division, Schedule Subdivision, or Schedule Clause headings
clear Schedule Subclause state. The existing Chapter transition exits Schedule
mode and clears Schedule Subclause state. Endnotes clears both states and is a
terminal boundary for this transformation. State continues across spine
documents in global block order.

Unsupported marker-like paragraphs beneath a valid Section or Schedule Clause
remain role `none`, do not clear active substructure, and may receive a bounded
diagnostic. Supported-shaped markers outside those provisions may also receive
a diagnostic. Diagnostics are ordered and limited to at most one per input
block. They contain only a bounded code, global ordinal, and source locator,
not source text or document contents.

Recognition makes no sequence, uniqueness, date, year, numbering-gap, or legal
meaning assumption. Repeated identifiers and numbering gaps are accepted.

## Consequences and deferred work

The result is deterministic and serializes identically for identical B1 input.
It adds only the roles `none`, `subsection`, and `schedule_subclause`. It does
not recognise paragraphs or subparagraphs, so `(a)` and `(i)` remain ordinary
content until Sprint 1.3B2B can establish their hierarchy without ambiguity.

No definition, note, example, amendment, repealed-state, citation,
cross-reference, obligation, right, power, offence, or other legal meaning is
assigned. No persistence, provenance change, retrieval, embedding, API, CLI,
frontend, background job, or model call is introduced.

The bounded grammar may leave valid source variants unsupported, and the
transformer relies on the ordering and active-container invariants guaranteed
by a valid B1 document. Expanding marker grammar, adding paragraph and
subparagraph hierarchy, or interpreting additional provision structures
requires a separately bounded Sprint 1.3B2B decision with representative
evidence.
