# ADR 0015: Derived Provision Text, a Live Provider, and Entailment Verification

- Status: Proposed
- Date: 2026-09-02
- Accepted: not yet accepted — owner authorisation required before merge
- Builds on: [ADR 0013](0013-phase-4-research-evidence-packets.md), [ADR 0014](0014-phase-5-grounded-answering-and-read-only-api.md)

## Context

ADR 0014 delivered the grounded answering pipeline with a mock adapter. It
worked, but it could not be useful, for one structural reason: a validated
`WaEvidencePacket` carries the bytes of a *whole instrument*. For the pilot
corpus that is a 1.29 MB consolidated PDF, 263 pages. No model can be handed
that, so the mock could only restate identity fields, and any live provider
would have had nothing to reason over.

Two further gaps remained. MVP_ROADMAP section 8 specifies three levels of
citation validation and only levels 1 and 2 existed. Section 5 specifies a
provider-neutral interface with a real adapter behind it, and only the mock
existed.

The owner has supplied credentials and asked for a finished, usable system.

## Decision

### 1. Provision text is derived offline and digest-chained

`scripts/derive_wa_provisions.py` is an operator tool, run by a human. It
verifies the parent PDF digest against its manifest before reading anything,
extracts one section at a time, and writes the text plus a manifest recording
both the parent digest and the text's own digest.

`answering/provisions.py` is the read side and trusts nothing. It resolves
derived text only when the recorded parent digest equals the digest of the
packet in hand, the provision identity matches, and the text file's digest
matches its manifest. Any mismatch resolves to `None`, and the pipeline then
answers from identity fields alone. Derived text is data, never instruction.

This deliberately does not extend the Phase 4 corpus. `RecordedWaCorpus`
selects one source per Act title and would treat sibling manifests as an
ambiguous selection, so provision text is a sidecar resolved *after* a packet
has been validated, not a second thing to retrieve.

### 2. Derivation transformations are recorded, not silent

Extraction applies two transformations, both listed in every manifest:
removal of repeated page furniture, and reflow of layout-wrapped lines into one
line per structural unit.

The reflow is load-bearing rather than cosmetic. A consolidated PDF wraps text
to the page, so one subsection arrives broken mid-sentence. Any ordinary
quotation of the provision would then fail a byte-exact substring check, and
every otherwise-correct answer would be refused. The fix belongs in the
derivation, because the line breaks are page layout and not part of the
provision. The alternative — relaxing quote validation to ignore whitespace —
was rejected: it would weaken the one check that catches a fabricated quote.

Derived text is labelled as derived. The official source remains the parent PDF,
and every citation still carries that PDF's digest and URL.

### 3. A live provider whose citations it cannot influence

`answering/providers/openrouter.py` is the first live adapter. The model is
shown one provision's verified text and asked only for statements and optional
verbatim quotes. It is **never** asked for a citation: `source_id`, `sha256`,
provision identifier, and pinpoint are filled in by the adapter from the packet
the request was built from. Citation spoofing is therefore structurally
impossible rather than merely detected, and the quote is still checked
byte-for-byte downstream.

The adapter declines when no verified provision text is available, rather than
reasoning from a heading. Every failure raises `AnswerModelUnavailable`, which
the pipeline converts into a refusal.

### 4. The mock remains the default, and a credential is not a switch

`LEGAL_AI_ANSWER_MODEL` must be set to `openrouter` explicitly. An
`OPENROUTER_API_KEY` present in the environment does **not** switch on a live
provider, and an unrecognised value falls back to the mock. Phase 11 provider
selection by evaluation is unchanged by this decision; this adds the adapter,
not the conclusion of that evaluation.

### 5. Level 3 entailment is a separate call

`answering/verification.py` implements MVP_ROADMAP section 8 level 3. Levels 1
and 2 prove a citation points at the provision retrieved and that a quote is
present in it; neither proves the provision *supports the statement made about
it*. That check is a second call with its own prompt, because the model that
wrote the statement is not asked to mark its own work.

It is optional and off by default (`LEGAL_AI_VERIFY_ENTAILMENT`). When enabled,
`NOT_SUPPORTED` refuses the whole answer, and so does an unreachable verifier or
an unparseable verdict. An unavailable check never reads as a pass.

### 6. Review-gate repair

`scripts/deepseek_review.py` could not run: its model candidate list predated
the provider's current lineup, and its 30-second read timeout was far shorter
than a whole-diff review takes. Both are corrected. Nothing about what the gate
checks, or how its verdict is interpreted, is changed — the repair makes a
mandatory gate executable rather than weakening it.

### 7. Out of scope

No live retrieval of legal sources at request time · no database · no
authentication · no corpus expansion beyond provisions of the already-recorded
Act · no Commonwealth sources · no vector retrieval · no deployment · no real
client data · no L1+ authority · no change to any Phase 0–4 module.

## Consequences

The system now answers real questions with real statutory text, and its quotes
are verifiable against a digest that chains back to official bytes. Level 3 is
available for the cases where a plausible-sounding statement is not actually
supported.

`pypdf` is added as a runtime dependency, used only by the operator tool.

Two costs are worth stating plainly. Derived text is a transformation of the
official PDF, so it carries a small, documented risk of extraction error that
the parent digest cannot detect — a reviewer should spot-check derived text
against the official source before any reliance. And enabling a live provider
makes answers depend on a third party's availability, latency, and retention
terms; the provider due-diligence requirement in ADR 0001's future-commercial
gate is untouched by this decision.
