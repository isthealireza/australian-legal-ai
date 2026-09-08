# ADR 0019: Phase 5 Grounded Answering and the Read-Only Research API

- Status: Proposed
- Date: 2026-09-02
- Accepted: not yet accepted — owner authorisation required before merge

## Context

Phase 4 Slice 1 merged a deterministic, read-only WA research module
(ADR 0013). It produces a validated `WaEvidencePacket` or refuses totally. It
has no caller: nothing in the repository turns a question into an answer, and
the only way to observe the module is `scripts/demo_research.py`.

`docs/execution/MVP_ROADMAP.md` section 5 specifies the intended shape — a
grounded generation pipeline that is explicitly **not an agent** — and defines
the `LegalAnswerModel` protocol together with a mock adapter for tests. Section
8 specifies three levels of citation validation. Neither exists in code.
Phase 5 (drafting with a mock model) and Phase 10 (private-alpha API and UI) are
both recorded as Not Started.

The owner has asked for a usable system now, structured like a conventional
FastAPI application, reusing the merged grounded components.

An external reference implementation (`Paparusi/legal-ai-agent`) was assessed as
a source of structure. Its **layout** is conventional and worth following: an
application factory, a `routes/` package, a health endpoint, and a static
single-page interface. Its **architecture** is not adoptable. It is a tool-using
agent whose model chooses whether to consult sources and whose prompts cite
statutes directly; that is the exact path forbidden by
`ENGINEERING_WORKFLOW.md` red lines 11 and 13. No code from it is imported.

## Decision

### 1. Scope and authority

Two additive packages and one static interface:

- `src/legal_ai/answering/` — the provider-neutral answer-model contract, a
  deterministic mock adapter, deterministic citation validation, audit sinks,
  and the pipeline that composes them.
- `src/legal_ai/api/` — a FastAPI application factory exposing exactly two
  endpoints over that pipeline.
- `static/` — a single-page interface carrying the required notices.

Authority level **L0**: deterministic, read-only. The service performs no live
retrieval, no persistence, no database access, no email, no external action, and
no state change of any kind. It reads recorded fixtures beneath an injected root
and appends audit events.

No existing module is modified. The whole slice is removed by deleting the two
packages, the `static/` directory, their tests, and two dependency lines.

### 2. The model is confined by the protocol, not by instruction

`LegalAnswerModel` has exactly one method taking exactly one
`GroundedAnswerRequest`. That request carries the question and the fields of one
already-validated packet. There is no tool list, no browser, no shell, no
network handle, no filesystem handle, and no persistent memory, because the
protocol provides nowhere to put them. Compliance with red line 13 is a property
of the type signature rather than of a prompt.

### 3. Model output is untrusted until validated

`ModelDraft` is untrusted data. Levels 1 and 2 of MVP_ROADMAP section 8 are
implemented deterministically in `answering/validation.py`:

- **Existence** — the asserted `source_id` and `sha256` must equal the packet's.
- **Pinpoint integrity** — the asserted provision identifier and pinpoint must
  equal the packet's.
- **Quote integrity** — an optional quote must be a literal byte-substring of
  the verified `source_content`.

Validation is all-or-nothing: one unsupported proposition refuses the entire
answer. Rendered citations are constructed from **packet** fields, never from
model-asserted ones, so a model cannot restate an Act title, version, or URL.

Level 3 (entailment) is **not** implemented and is deferred to Phase 11.

### 4. Refusal cannot leak legal content

`AnswerRefused` carries a typed code and has no propositions attribute at all,
mirroring the Phase 4 result contract. A refusal is rendered as an explicit
refusal in both the API response and the interface, never as an empty answer.

### 5. Audit sinks usable outside the test harness

ADR 0013 section 5 left the sink in-memory and test-only. Serving requests needs
one that outlives a request, so two are added: a JSON Lines sink writing beneath
an injected path, and a standard-library logging sink. Both raise on failure,
which `WaResearchService` already treats as terminal `AUDIT_SINK_UNAVAILABLE`.
An unwritable audit trail therefore stops the answer.

### 6. The mock adapter is the default

`MockAnswerModel` restates identity fields from the packet it was handed. It is
not a language model and does not paraphrase. Selecting a live provider remains
Phase 11 work, gated behind the evaluation metrics in MVP_ROADMAP section 9.

### 7. Explicitly out of scope

No live provider, no entailment verification, no vector retrieval, no database,
no authentication, no matter or casework surface, no evidence-vault surface, no
playbook activation, no crawler or ingestion, no deployment, no real client
data, no Commonwealth corpus, and no L1+ authority.

## Consequences

The repository gains a runnable, demonstrable system whose refusals are visible,
and Phase 5 is satisfied in a way that Phase 10 can build on. Two runtime
dependencies are added (`fastapi`, `uvicorn`).

The pilot corpus remains one recorded WA Act, so almost every real question
refuses. That is the intended behaviour, not a defect, but it means the system
is demonstrable rather than useful until the corpus grows.

`.env.example` does not yet list `LEGAL_AI_WA_CORPUS_ROOT` or
`LEGAL_AI_RESEARCH_AUDIT_LOG`; that file carries another task's uncommitted
changes and was deliberately left untouched.
