# ADR 0006: Deterministic federal legislation hierarchy recognition

- Status: Accepted
- Date: 2026-07-23

## Context

Sprint 1.3A produces an ordered `ParsedEpubDocument` containing generic XHTML
text blocks with exact source locators and no legal meaning. Sprint 1.3B1 needs
a deterministic structural seam for a deliberately bounded subset of
Commonwealth legislation before later work can model finer provision content.

The EPUB is an official-source, machine-readable rendition and useful parsing
input. It is not, by that fact alone, treated as the court-authorised
representation of the legislation. The immutable authorised PDF remains a
separate provenance artifact, and later verification rules must retain that
distinction.

## Decision

Implement a synchronous, pure, offline transformation from
`ParsedEpubDocument` to a strict, frozen `StructuredLegislationDocument`. The
transformation performs no filesystem, network, database, retrieval, embedding,
or model access and does not reopen the EPUB artifact.

The output is a flat ordered tuple with exactly one output block for every input
block. Each output block copies the source spine index, source block ordinal,
locator, generic kind, XHTML tag, normalized text, element ID, class tuple,
EPUB type, and language. It adds a zero-based global ordinal, a bounded
structural role, an optional recognized identifier and title, an optional parent
heading ordinal, and an optional active-container heading ordinal. No source
block is dropped, merged, split, duplicated, or substantively rewritten.

Recognized structural headings use their own global ordinal as their active
container. Their parent ordinal identifies the nearest owning higher-level
heading. Content and unclassified headings use the deepest active legal
container. Diagnostics for unclassified headings contain only a bounded code,
global ordinal, and source locator; they do not duplicate document text.

## Candidate and grammar boundary

Only generic `heading` blocks whose original XHTML tag is exactly `h1` through
`h6` are candidates. CSS class names and EPUB types do not create legal
structure. Candidate text is matched as a complete string after deterministic
layout-whitespace collapse. The original normalized text remains unchanged in
the output.

The recognizer supports Chapter, Part, Division, Subdivision, Section,
Schedule, Parts/Divisions/Subdivisions inside a Schedule, Schedule Clauses, and
the exact `Endnotes` boundary. Em dash U+2014 and en dash U+2013 are the only
title separators. ASCII hyphen remains available inside supported Chapter and
Part numeric identifiers and is not a title separator.

Chapter and Part numeric identifiers may contain numeric hyphen components and
up to three uppercase ASCII suffix letters. Parts also accept canonical Roman
numerals and a bounded uppercase suffix. A wholly canonical Roman identifier is
accepted first; otherwise the longest canonical Roman prefix followed by one to
three uppercase ASCII letters is accepted, including suffix letters that are
also Roman-numeral characters. Divisions and Schedules accept a numeric
identifier with up to three uppercase suffix letters. Subdivisions accept one
to three uppercase ASCII letters. Sections and Schedule Clauses accept digits
followed by up to three uppercase ASCII letters, require a non-empty title
separated by layout whitespace, and support four-digit identifiers. Provision
recognition is syntax-only; there is no general calendar-year heuristic. The
exact synthetic ambiguity example `2026 annual overview` is conservatively left
unclassified to satisfy this bounded Sprint contract. That exact exception is
not a date or semantic classification and does not apply to similar headings.

Unsupported or incomplete candidate text becomes `unclassified_heading` as a
whole. The recognizer does not partially classify, guess, use substring
searches, correct numbering, infer missing levels, or require sequential or
unique provision numbering.

## Hierarchy state machine

The main-body hierarchy is Chapter → Part → Division → Subdivision → Section.
A Part belongs to an active Chapter. A Division falls back from Part to Chapter.
A Subdivision falls back from Division to Part to Chapter. A Section belongs to
the deepest active main-body container. Each new heading clears only the lower
main-body levels specified by that hierarchy; a new Chapter also exits and
clears Schedule state.

A Schedule is top-level and clears the entire main-body hierarchy. While a
Schedule is active, Part, Division, and Subdivision headings receive distinct
Schedule roles, and numeric or alphanumeric provision headings become Schedule
Clauses rather than Sections. Schedule parent fallbacks mirror the main body but
never leave the active Schedule. A new Schedule clears the previous Schedule's
lower state. Duplicate clause numbers in separate Schedules are allowed.

The exact candidate heading `Endnotes` receives `endnotes_heading`, has no legal
parent, clears all main-body and Schedule state, and enters a terminal endnotes
region. After that boundary, candidate headings remain present as
`unclassified_heading` and cannot create legal structure; non-heading blocks
remain content with no legal container.

## Consequences and deferred work

This decision recognizes document hierarchy only. It adds no subsection,
paragraph, subparagraph, definition, note, example, table-as-law, amendment,
repealed-state, commencement, citation, cross-reference, offence, penalty,
obligation, power, right, or legal-conclusion semantics. Text such as
`6 Repealed` is only Section 6 with the title `Repealed`.

There is no database persistence, migration, provenance-repository access,
retrieval, embedding, model call, API, CLI, frontend, or external service.
Class-name heuristics are excluded because no checked-in source evidence has
authorised them.

The grammar is intentionally conservative and may leave valid but unsupported
Federal Register headings unclassified. It also assumes the Sprint 1.3A parser
has already validated and ordered the input models. Sprint 1.3B2 must use a new
bounded task and evidence before adding finer subsection, paragraph, definition,
or other provision semantics, expanding heading grammar, or introducing source
specific heuristics.
