# Scope Card — Scope boundary enforcement

Branch: `feat/scope-boundary-enforcement`
Base ref: `feat/per-proposition-answers`
Date: 2026-09-09
Owner: Ali Rad

## Problem

MVP_ROADMAP section 11 puts contract review, document review/uploads, and court
document preparation out of scope by name. But nothing in code enforced it.
Across both live campaigns (`LIVE_ADVERSARIAL_RUN.md` S1-S4, and round 2 family
B in `LIVE_ADVERSARIAL_RUN_2.md`) the live model refused every contract-review
and drafting probe while the mock answered them all. The boundary was model
goodwill, not a control: a model swap, prompt drift, or provider fallback would
leak. All four probes have valid in-corpus queries, so retrieval and validation
pass and only the model's own compliance stood between the request and an answer.

## Change

Classify the request kind deterministically from the question text and refuse
before the answer model is called, matching the existing out-of-corpus and
jurisdiction refusals: zero model calls, near-zero latency, audited.

- `legal_ai/answering/scope.py`: `classify_request_kind(question) -> RequestKind`
  (`RESEARCH` / `DOCUMENT_REVIEW` / `DOCUMENT_DRAFTING`). Literal,
  case-insensitive patterns for the two out-of-scope shapes the campaigns
  exercised — review/advise on a supplied instrument (review this contract,
  should I sign, "my contract says", advise my client, whether … void, pasting)
  and drafting one (draft/prepare/write a letter/notice, letter of demand, make
  it ready to send). Conservative by design: it matches the act being asked for,
  not a mere mention of a contract, so a research question that names a contract
  is unaffected.
- `GroundedAnswerService.answer` runs the classifier first. A non-`RESEARCH`
  kind audits the refusal and returns `AnswerRefused(REQUEST_OUT_OF_SCOPE)`
  before any retrieval or model call.
- `WaResearchService.audit_refusal(query, code)` records a pre-retrieval refusal
  through the same audit sink and event shape as an evaluated refusal
  (fail-closed: an audit failure yields `RESEARCH_TERMINATED`).
- New codes `ResearchRefusalCode.REQUEST_OUT_OF_SCOPE` (audited) and
  `AnswerRefusalCode.REQUEST_OUT_OF_SCOPE` (its own API code; a normal 200
  REFUSED, like `RESEARCH_REFUSED`).

## Non-goals / constraints

- **Do not touch the answer-model prompts.** A prompt is not a control. No
  change to `SYSTEM_PROMPT` or `VERIFIER_SYSTEM_PROMPT`.
- The classifier fails open to the rest of the pipeline on a miss; it never
  weakens any downstream check. A false negative still faces retrieval,
  validation, and entailment. It is a deterministic pre-filter, not the only
  line of defence.
- Read-only elsewhere in `src/`.

## Tests (written first, shown failing against the leaking mock)

`tests/answering/test_scope_boundary.py`, from the S1-S4 bodies verbatim:
- each probe refuses `REQUEST_OUT_OF_SCOPE` on the mock configuration that
  answered them live;
- the refusal makes zero model calls (an exploding model double is never
  called);
- the refusal is audited as a `REFUSED` event with `REQUEST_OUT_OF_SCOPE` and no
  citation;
- legitimate research questions are not caught (they still answer on the mock);
- classifier unit checks for the probes and for research questions.

Before implementation these failed (the mock answered S1-S4; the classifier did
not exist).

## Residual limitation and review-gate findings

A deterministic classifier over free-text English is a **mitigation, not a
complete control**: it cannot be proven un-bypassable, because a novel paraphrase
it has not seen is a false negative by construction. This is inherent to the
deterministic, prompt-free approach this task specified, and it is why the gate's
core objection ("regex is bypassable") is correct in principle. The design owns
that limitation rather than hiding it:

- It closes the **demonstrated** leak (the mock answering S1-S4) and the concrete
  bypasses the gate named across two rounds — analyze/check/assess/vet/look over,
  draw up/write me/prepare, can/should I sign/accept, advise me on my …, is my …
  fair/enforceable — with zero false positives on legitimate research about
  validity, enforceability, or contracts in the abstract.
- Input is normalised before matching (NFKC fold, zero-width strip, whitespace
  collapse), denying the cheapest obfuscations (homoglyphs, zero-width joiners).
- A false negative is **not** a downstream bypass of grounding: a review/drafting
  request that slips the classifier still faces retrieval, citation validation,
  and per-proposition entailment, none of which this weakens. On the live chain
  such a request produces no groundable proposition and refuses anyway (both
  campaigns showed this); the classifier's job is to make that refusal a precise,
  pre-model, audited `REQUEST_OUT_OF_SCOPE` and to close the mock-style leak.
- **Query-field vector (gate SCOPE-002):** out-of-scope intent cannot be smuggled
  through `act_title`/`provision_identifier` to obtain an answer. Those fields
  must resolve to a recorded WA act/provision or the request is refused
  (`RETRIEVAL_MISSING`); a non-legislation title never reaches the model. The gate
  is classified over the question, which is the only field that can carry a
  review/drafting instruction and still ground.

An **un-bypassable** scope control (a learned intent classifier, or a structured
question contract that forbids free text) is a different class of work than a
deterministic pre-filter and is out of scope for this bounded task; it would be a
separate ADR-gated decision. If the owner judges the residual false-negative risk
unacceptable, that is the follow-up.

## Definition of done

ruff, ruff format --check, mypy, pytest, then the DeepSeek review gate. Then
re-run S1-S4 against both the mock and the live chain and show both refuse.
