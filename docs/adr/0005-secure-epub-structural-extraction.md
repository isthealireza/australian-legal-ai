# ADR 0005: Secure EPUB structural extraction

- Status: Accepted
- Date: 2026-07-23

## Context

Sprint 1.3 needs deterministic structural input before any legal-semantic
classification can begin. The checked-in Federal Register metadata fixtures for
the Privacy Act 1988 and Competition and Consumer Act 2010 each expose an EPUB
primary rendition. EPUB is therefore the first machine-readable format at this
parsing seam.

PDF remains an immutable provenance artifact but is deferred as a parsing
format. Its page-oriented layout, reading-order ambiguity, font encoding, and
pinpoint reconstruction require separate dependencies, fixtures, and security
decisions. This sprint does not infer structure from rendered page position.

## Decision

Implement a synchronous, read-only EPUB 3 structural extractor using only the
Python standard library and existing Pydantic v2. The public parser accepts a
filesystem `Path` to an immutable artifact-vault blob, its expected lowercase
SHA-256, and an explicit caller-created limits model. It returns frozen, strict
models containing package metadata, spine documents, generic structural text
blocks, and deterministic source locators.

The parser first rejects symlinks, non-regular files, empty artifacts, malformed
expected hashes, hash mismatches, and artifacts beyond the caller's archive
limit. SHA-256 is calculated incrementally from the artifact bytes. No filename
or database metadata substitutes for this verification.

## Archive and XML safety

The ZIP is opened read-only and never extracted to disk. `ZipFile.extract()` and
`extractall()` are not used. The EPUB `mimetype` entry must be first, stored, and
contain exactly `application/epub+zip`.

Every archive entry is validated before content parsing. Absolute, drive,
UNC-style, backslash-ambiguous, empty-component, dot-component, parent-traversal,
canonically duplicated, encrypted, symlink, and special-file entries fail
closed. The caller supplies hard limits for archive bytes, entry count,
per-entry uncompressed bytes, total uncompressed bytes, compression ratio,
XHTML block count, and text characters per block. Entry bytes are read directly
into bounded memory only after directory validation.

XML bytes are bounded by their ZIP-entry limits before standard-library
`ElementTree` parsing. Only UTF-8 XML is accepted so declaration scanning cannot
be bypassed through an alternate byte encoding. DOCTYPE and ENTITY declarations,
external SYSTEM or PUBLIC identifiers, and non-declaration processing
instructions are rejected.
The parser performs no XInclude, schema, stylesheet, CSS, JavaScript, external
entity, network, or filesystem reference loading.

## Supported package and structural subset

The accepted subset is deliberately narrow: EPUB container version 1.0, exactly
one local usable rootfile, an EPUB 3.0 OPF package, local manifest targets,
stored or deflated ZIP entries, and ordered XHTML spine items declared as
`application/xhtml+xml`. Missing targets, duplicate manifest IDs, duplicate
spine references, remote targets, non-XHTML spine items, malformed required
package data, and duplicate XHTML element IDs fail closed.

The parser emits generic blocks only for headings, paragraphs, list items,
definition terms and descriptions, block quotes, preformatted blocks, captions,
and table header/data cells. It preserves document order, Unicode punctuation,
inline text order, IDs, class tokens, EPUB type, and language. Layout whitespace
is collapsed deterministically without rewriting words or punctuation.

Container-like blocks such as list items and table cells own descendant
paragraph text, so the same text is not emitted twice. Nested peer blocks remain
separate. Head content, scripts, styles, comments, hidden content, and EPUB
navigation-control subtrees such as tables of contents are not emitted. Generic
`nav` elements with substantive structural blocks remain eligible. No CSS or
JavaScript is interpreted.

Each block locator begins with its normalized internal EPUB href. An explicit
element ID is used when present; otherwise the locator uses a deterministic
one-based structural element path. No upstream anchor is invented. Repeated
parsing of the same bytes and limits produces identical model serialization.

## Consequences and residual limitations

This sprint produces only an ordered in-memory representation. It adds no
database persistence, migration, parser output store, retrieval, pgvector use,
embedding, model call, legal-answering behavior, or external service.

The blocks carry no legal meaning. Acts, Parts, Divisions, Sections,
Subsections, Paragraphs, Schedules, definitions, amendments, repeals, and
pinpoints derived from legal hierarchy remain deferred to Sprint 1.3B.

Unsupported features include additional rootfiles, EPUB package versions other
than 3.0, container versions other than 1.0, remote resources, encrypted ZIPs,
non-UTF-8 XML, non-XHTML spine content, non-stored/non-deflated compression, and
broader EPUB rendition, fallback, media-overlay, scripting, styling, and
navigation behavior.
Some otherwise valid EPUB publications may therefore be rejected.

Caller-selected finite limits bound but do not eliminate CPU and memory use.
The immutable artifact vault is assumed to prevent concurrent source mutation
after hash verification. PDF and DOCX parsing, disk extraction, semantic legal
classification, and automated cleanup are not introduced by this decision.
