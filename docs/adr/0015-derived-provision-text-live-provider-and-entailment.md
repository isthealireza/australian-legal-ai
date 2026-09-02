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

## Addendum — external review findings and remediation (2026-09-02)

The DeepSeek review gate returned `BLOCKED` on the first run of this change.
Both findings were accepted as valid and are fixed.

**`ENTAILMENT_SILENT_SKIP` (high, `api/main.py`).** With
`LEGAL_AI_VERIFY_ENTAILMENT` enabled but no provider credential,
`_resolve_verifier` returned `None` and the service answered anyway — silently
dropping a safety check that had been explicitly requested. That is a fail-open,
and the resulting answer is indistinguishable from one that passed level 3.

Fixed by `_configuration_error`: a requested verifier that cannot be built now
stops the service. Every research request returns HTTP 503 with the typed code
`VERIFIER_NOT_CONFIGURED`, and `/api/health` reports `corpus_configured: false`.
Covered by `test_requested_entailment_without_credentials_refuses_every_request`.

**`VERIFIER_UNBOUNDED_PROVISION` (medium, `answering/verification.py`).** The
verifier sent `provision_text` to the provider with no length bound, while the
answer adapter truncates at `MAX_PROVISION_CHARS`. A derived provision may be up
to 1 MiB, so the two paths disagreed about egress.

Fixed by applying the same bound in the verifier. Covered by
`test_oversized_provision_text_is_bounded_before_egress`.

The gate also identified three missing tests, all now present: the two above,
plus `test_health_reports_a_configured_verifier`.

Two points from the gate's `scope_risks` are recorded here rather than fixed,
because they are properties of the design rather than defects, and both are
already stated in the Consequences section above: a live provider introduces
third-party availability and retention exposure, and level 3 currently uses the
same provider as the answer model, so it is independent in prompt and call but
not in vendor. Making the verifier a genuinely different provider is worth doing
before any reliance on level 3.

`.env.example` was excluded from the review bundle. The gate refuses to send any
file whose name begins with `.env` to an external service, which is correct; that
one file in this change is therefore unreviewed by the gate.

## Addendum 2 — second review round (2026-09-02)

The re-run returned `BLOCKED` again, with two new findings. Both accepted and
fixed.

**`ENTAILMENT_VERDICT_PREFIX_ACCEPTANCE` (high,
`answering/verification.py`).** The verifier accepted any reply beginning with
`SUPPORTED`, so a hedged verdict such as "SUPPORTED, in part" read as a clean
pass. Level 3 is now an exact match on `SUPPORTED` or `NOT_SUPPORTED` after
stripping and upper-casing; anything else raises `VerifierUnavailable` and
refuses. The verifier prompt now also states that any other reply is discarded.

**`REVIEW_GATE_SECRET_REDACTION_INCOMPLETE` (medium,
`scripts/deepseek_review.py`).** The gate's redaction covered several
credential shapes but not `OPENROUTER_API_KEY`, which this change introduces to
the repository. Since the gate transmits a diff to a third party, that was a
real egress risk. Redaction now covers the `sk-or-v1-` token shape and any
`*_API_KEY` assignment.

Both fixes carry tests, including the hedged-verdict cases and the redaction
shapes. The branch now also carries `scripts/deepseek_review.py` and
`tests/review/test_deepseek_review.py`, which originated in the separate
review-gate task: committing the repaired script without its tests would have
left a mandatory control untested on this branch.

## Addendum 3 — third review round (2026-09-02)

Three findings. Two were defects introduced by the previous remediation; all
three are addressed.

**`REDACTION_CORRUPTS_REVIEW_BUNDLE` (critical,
`scripts/deepseek_review.py`).** Addendum 2 broadened the secret-assignment
pattern to `[A-Z0-9_]*API_KEY` while leaving the `(?i)` flag in place, so the
pattern also matched ordinary lower-case identifiers — `api_key: str`,
`self._config.api_key` — and rewrote them inside the diff being reviewed. The
reviewer was reading corrupted evidence. This was a regression caused by the
fix for `REVIEW_GATE_SECRET_REDACTION_INCOMPLETE`.

The assignment pattern is now case-sensitive and upper-case only, which still
covers every environment-variable form while leaving code untouched. Two
regression tests were added: ordinary identifiers must survive redaction
unchanged, and four real source files must still parse as valid Python after
being redacted.

**`ENTAILMENT_SILENT_SKIP_WHEN_NO_PROVISION` (high,
`answering/service.py`).** `_verify` returned `None` when a verifier was
configured but no derived provision text resolved, silently skipping level 3.
This is the same class of fail-open as `ENTAILMENT_SILENT_SKIP` and was missed
when that one was fixed. A configured verifier with nothing to verify against
now refuses with `ENTAILMENT_UNAVAILABLE`.

**`INCOMPLETE_REVIEW_ENV_FILE_EXCLUDED` (medium).** The gate will not transmit
`.env*` files, and that policy is left intact. Instead the complete
`.env.example` diff is now reproduced in the scope card, which the gate does
receive as the requirements document, so the content is reviewed without
changing what the gate is willing to send. The diff is additive, contains no
credential, and every added value is blank except `LEGAL_AI_ANSWER_MODEL=mock`.

## Addendum 4 — fourth review round (2026-09-02)

Three findings, none a regression from the previous round. All fixed.

**`REVIEW_GATE_SYMLINK_EXFILTRATION` (critical,
`scripts/deepseek_review.py`).** The gate accepted a symlink whose target
resolved inside the repository. A tracked link could therefore present an
innocuous path in the allowlist while pointing at `.env.local` or
`.git/config`, so the operator could not tell from the allowlist what would
actually be transmitted. No symlink is now accepted as a review input, and a
symlinked parent directory is refused too. This was a pre-existing property of
the gate rather than something this branch introduced, but the branch now
carries that file.

**`UNBOUNDED_MODEL_PROPOSITION_COUNT` (high,
`answering/providers/openrouter.py`).** The adapter parsed the provider's
`propositions` list with no limit, so a compromised or runaway provider
response could force unbounded work before the downstream validator rejected
it. The count is now bounded by `MAX_PROPOSITIONS` before anything is built.

**`UNHANDLED_OVERSIZED_QUESTION_VALIDATION_ERROR` (high,
`api/routes/research.py`).** `question` was an unbounded `str` in the request
schema, so an over-long value passed the HTTP boundary and then raised a
`ValidationError` inside the pipeline when `GroundedAnswerRequest` was
constructed — surfacing as a 500 rather than a refusal or a 422. Request fields
now carry bounds mirroring the domain contract, so an over-long or empty field
is a 422. Request construction inside the pipeline is additionally wrapped, so
no validation error can escape as an unhandled exception.

The symlink policy has two tests: one exercising a real symlink, which skips
where the OS withholds the privilege, and one asserting the decision directly
so the policy is provable on Windows as well.

## Addendum 5 — fifth review round (2026-09-02)

Three findings, all fixed. One required resolving a direct conflict between two
earlier findings.

**`LIVE_PROVIDER_WITHOUT_ENTAILMENT` (high, `api/main.py`).** Selecting the
live provider did not require `LEGAL_AI_VERIFY_ENTAILMENT`. Levels 1 and 2
constrain the *citation* — that it points at the retrieved provision, and that
any quote is really present. Neither constrains the *statement*. A mock adapter
cannot invent a statement because it only restates packet fields; a live
generative model can. Selecting `openrouter` without a verifier is now a
configuration error, refused with
`ENTAILMENT_REQUIRED_FOR_LIVE_MODEL` and HTTP 503. This tightens section 5
above: level 3 remains optional for the mock, and is mandatory for a live model.

**`UI_URL_SCHEME_NOT_VALIDATED` (medium, `static/app.js`).** The interface set
`link.href` from the citation URL without re-checking the scheme. The server
cannot emit anything but an allowlisted HTTPS legislation URL —
`validate_wa_official_source_url` enforces that before a packet can exist — so
this was defence in depth rather than a live hole. The check is added anyway,
and a non-HTTP(S) value now renders as inert text.

**`REVIEW_GATE_SECRET_REDACTION_LOWERCASE_GAP` (medium,
`scripts/deepseek_review.py`).** This finding directly opposes
`REDACTION_CORRUPTS_REVIEW_BUNDLE` from round 3: one demanded that lower-case
secret assignments be redacted, the other that lower-case identifiers not be.
Matching on the *name* cannot satisfy both.

Resolved by matching on the **value**: a lower-case assignment is redacted only
when its value is a quoted literal of at least twelve characters, which
`api_key = "sk-..."` is and `api_key: str` is not. A case-sensitive exclusion
additionally preserves quoted `UPPER_SNAKE` literals, which are
environment-variable names rather than credentials. Tests assert both
directions, and that four real source files still parse as valid Python after
redaction.

## Addendum 6 — sixth review round, and where the loop stands (2026-09-02)

Two findings, both in the review gate itself rather than in the Phase 5
deliverable. Both fixed.

**`REVIEW_GATE_PRIVATE_KEY_REDACTION_INCOMPLETE` (critical).** The PEM
private-key pattern lacked `re.DOTALL`, so it could never match a key spanning
multiple lines — which every PEM key does. A private key committed anywhere in
an allowlisted path would have been transmitted in full. The pattern now uses
`(?is)`. This was pre-existing in the gate, not introduced by this branch.

**`REVIEW_GATE_LOWERCASE_UNQUOTED_SECRET_GAP` (high).** The lower-case rule
only matched quoted values, so `api_key=sk-live-...` in an env-style file passed
through. A rule for unquoted values is added, requiring the value to contain a
character no Python identifier or attribute path can hold (`-`, `+`, `/`, `=`).

A residual gap is recorded honestly rather than papered over: an unquoted value
that is a bare identifier-shaped word, such as `api_key=supersecretvalue`, is
**not** redacted by the name-based rules. In a diff it is genuinely
indistinguishable from `api_key=some_variable`, and matching it would
reintroduce `REDACTION_CORRUPTS_REVIEW_BUNDLE`. The token-shape pattern remains
the backstop for real credential formats, which all contain such characters.

### State of the gate

Six runs, `BLOCKED` every time, fifteen findings, all remediated with tests.
The rounds show a clear shift: rounds 1–2 found genuine fail-opens in the Phase
5 pipeline, round 3 caught a regression this remediation itself introduced, and
rounds 4–6 have progressively moved into hardening of the gate script — code
that arrived with the separate review-gate task.

The gate is an adversarial reviewer with no termination condition: each pass
over a large diff surfaces further hardening. `CLAUDE.md` is unambiguous that a
`BLOCKED` verdict is a failed gate and must never be read as a pass, so **this
branch is not merge-ready**, and that judgement is the owner's to make rather
than something further iteration can settle on its own.
