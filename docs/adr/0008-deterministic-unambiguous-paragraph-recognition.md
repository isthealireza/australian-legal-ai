# ADR 0008: Deterministic unambiguous paragraph recognition

- Status: Accepted
- Date: 2026-07-23

## Context

Sprint 1.3B2A produces an ordered `SubstructuredLegislationDocument` with
main-body Subsections, Schedule Subclauses, and a separate effective legal
content-container ordinal. Sprint 1.3B2B1 needs to recognise only alphabetic
paragraph markers whose text is unambiguous at this layer, without reopening
the EPUB or changing any B1 or B2A classification.

Lowercase Roman markers cannot safely be classified from marker text alone.
For example, `(i)` may be a paragraph in one hierarchy or a subparagraph in
another. Its position after `(h)`, or beneath an active paragraph, does not
prove either meaning. Sequence-based inference would therefore invent legal
structure.

## Decision

Implement a synchronous, pure, offline transformation from
`SubstructuredLegislationDocument` to a strict, frozen
`ParagraphStructuredLegislationDocument`. The transformer performs no
filesystem, network, database, persistence, retrieval, embedding, or model
access. It accepts no raw EPUB, XML, path, URL, bytes, dictionary, or
repository input.

The output contains exactly one block for every B2A input block in identical
global order. Every original EPUB field, B1 structural field, B2A substructure
field, B1 active-container ordinal, and B2A effective-content-container ordinal
is copied unchanged. No block is split, merged, duplicated, dropped, or
rewritten. Existing B1 and B2A diagnostics are copied unchanged into separate
typed tuples; paragraph-layer diagnostics remain a third distinct stage.

Only a generic `paragraph` block with B2A substructure role `none` is a
candidate. Headings, unclassified headings, list items, table headers or cells,
definition terms or descriptions, blockquotes, preformatted blocks, and
captions cannot become legal paragraphs. CSS classes, element IDs, EPUB types,
locators, indentation, wording, and sequence do not create paragraph meaning.

## Marker grammar and Roman ambiguity

Candidate text is matched as a complete string after deterministic
layout-whitespace collapse. The supported identifier grammar is one to three
lowercase ASCII letters, enclosed in literal ASCII parentheses, followed by
required layout whitespace and non-empty substantive text. This admits markers
such as `(a)`, `(b)`, `(h)`, `(j)`, `(aa)`, `(ab)`, and `(aaa)` while preserving
the exact identifier, derived text punctuation, and complete original text.

Any identifier composed solely of lowercase Roman-numeral characters
`i`, `v`, `x`, `l`, `c`, `d`, and `m` fails closed as Roman-ambiguous. This
includes canonical and plausibly canonical forms such as `i`, `ii`, `iv`,
`viii`, `ix`, `x`, `xi`, `xv`, and `xx`. Roman-like tokens are not assigned
paragraph or subparagraph meaning, regardless of preceding markers or active
state. Uppercase, numeric, mixed-case, mixed alphanumeric, excessive-length,
malformed, nested, prefixed, or bodyless markers are also unsupported.

## Parent and state rules

A recognised main-body paragraph requires a B2A effective container that is a
Section or Subsection. Its parent is the referenced Subsection when present,
otherwise the referenced Section. A recognised Schedule paragraph requires a
Schedule Clause or Schedule Subclause and uses that referenced block as its
parent. Main-body and Schedule paragraphs receive distinct roles.

A recognised paragraph becomes the active paragraph for subsequent ordinary
content and is replaced by the next recognised paragraph. Chapter, Part,
Division, Subdivision, Section, Subsection, and Schedule boundaries clear
main-body paragraph state. Schedule, Schedule Part, Schedule Division,
Schedule Subdivision, Schedule Clause, Schedule Subclause, and the existing
Chapter exit clear Schedule paragraph state. Endnotes clears all paragraph
state permanently. Unclassified headings do not clear state when B1 and B2A
define no legal transition. State continues across spine documents in global
block order.

Unsupported and Roman-ambiguous markers remain role `none`, remain present
exactly once, do not become containers, and do not clear active paragraph
state. Repeated identifiers and alphabetic gaps are permitted; no uniqueness,
sequence, date, or numbering correction is imposed.

## Final effective content-container invariant

The B2A effective-content-container ordinal remains unchanged. A separate final
effective content-container ordinal records the paragraph layer:

- a recognised main-body or Schedule paragraph uses its own global ordinal;
- subsequent ordinary content uses the active paragraph;
- content before the first paragraph uses its B2A effective container;
- structural headings and B2A substructures retain B2A container behavior;
- unsupported candidates do not replace active state; and
- content after Endnotes has no effective legal container.

This preserves the previous layer while making paragraph attachment explicit
and deterministic.

## Diagnostics and consequences

Paragraph-layer diagnostics are ordered, source-linked, and bounded to at most
one per input block. They may distinguish a supported marker outside a valid
provision, an unsupported marker-like paragraph, and a Roman-ambiguous marker.
Each record contains only a bounded code, global ordinal, and source locator;
it does not copy source text or document contents.

The transformation serializes identically for identical B2A input. Its role
set is limited to `none`, `paragraph`, and `schedule_paragraph`. It introduces
no subparagraph, definition, note, example, amendment, repealed-state,
citation, cross-reference, obligation, right, power, offence, penalty, or
other legal meaning. It adds no persistence, retrieval, embedding, API, CLI,
frontend, background job, or model call.

The grammar is deliberately conservative and will leave Roman-like and other
source variants unclassified. Before Sprint 1.3B2B2 may recognise
subparagraphs or disambiguate Roman markers, it requires representative
official-source evidence establishing the relevant parent hierarchy and tests
showing that the rule does not rely on marker sequence or wording alone.
