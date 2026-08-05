# MVP Execution Profile — v3-MVP (FINAL)

**Product name:** Grounded Australian Small-Business Legislation Research Assistant
**Status:** Official execution profile. This is the last planning document. All further project output is code, tests, evidence, and ADRs.
**Repository location:** `docs/execution/MVP_ROADMAP.md`

> This roadmap supersedes the delivery sequence of the Master Blueprint, but does not supersede its security, grounding, privacy, provenance, evaluation or non-lawyer requirements.

---

## 1. Document Hierarchy

```text
LEGAL_AI_MASTER_BLUEPRINT.md   → North Star architecture (unchanged)
PROJECT_GOVERNANCE.md             → Full Root Constitution (unchanged, ~100 lines)
docs/execution/MVP_ROADMAP.md     → This file: current execution scope
docs/adr/0001-product-purpose.md  → Portfolio-quality internal prototype
ENGINEERING_WORKFLOW.md           → Short practical engineering workflow
Repository workflow controls     → Path-scoped review rules
```

## 2. Product Purpose (ADR 0001 content)

**Current purpose:** Portfolio-quality internal prototype for Alirad.
- Portfolio asset demonstrating AI engineering, legal RAG, retrieval, evaluation, and security discipline.
- Internal research tool for learning and preliminary review of official sources.
- NOT for final legal decisions. NOT used with real client information in MVP.

**Future option:** Commercial product — architectural option only, gated behind a separate legal, privacy and security review (Australian lawyer review, advice-boundary assessment, PIA, ToU, privacy policy, provider due diligence, identity/access, incident response, security testing, professional-risk analysis).

## 3. MVP Definition

A user asks a legal research question limited to the indexed corpus. The system:
1. Retrieves only from indexed **official sources** (Federal Register of Legislation API; WA legislation).
2. Answers only from the retrieved evidence packet; every proposition carries citation + pinpoint (Act, provision, compilation/version date, source URL).
3. Fails closed: retrieval failure, verification failure, or out-of-corpus question → explicit refusal, never model-memory answering.
4. Permanent UI notices: non-lawyer disclaimer + `This prototype answers only questions supported by its currently indexed corpus.`

## 4. Corpus (pilot)

**Commonwealth:**
- Australian Consumer Law (Sch 2, Competition and Consumer Act 2010)
- Privacy Act 1988
- GST Act — selected parts only
- Fair Work Act 2009 — only pre-defined selected parts, if needed

**Western Australia:**
- Sale of Goods Act 1895 (WA)
- Fair Trading Act 2010 (WA)
- One or two Acts tied to a concrete use case

**Excluded from MVP:** full Corporations Act, full Fair Work Act, case law, regulations (deferred; require citator/context infrastructure).

## 5. Architecture: Grounded Generation Pipeline (NOT an agent)

```text
Question
→ deterministic retrieval (metadata filters + lexical; vector only if eval-justified)
→ evidence packet {source_id, act, provision, text, version, url, sha256}
→ one structured model call (provider-neutral interface)
→ deterministic validator (existence + pinpoint integrity)
→ optional independent verification call (entailment)
→ answer or refusal
```

Model has: no tool selection, no browser, no shell, no email, no persistent memory, no pipeline self-modification, no external actions.

**Provider-neutral interface:**
```python
class LegalAnswerModel(Protocol):
    async def answer(self, request: GroundedAnswerRequest) -> GroundedAnswer: ...
```
Adapters: one configured provider + mock adapter for tests. Final provider selection by eval (grounded quality, citation discipline, refusal quality, latency, cost, privacy/retention terms, structured-output reliability) — not reputation.

## 6. Legislative Structure Model

Preserve statutory hierarchy; never flatten to arbitrary token chunks:

```text
Act → Chapter → Part → Division → Section → {Subsection, Paragraph, Note}
plus: definitions, schedules, tables, notes, cross-references, headings, amendment history
```

- **Primary retrieval unit:** section or schedule clause
- **Child units:** subsections/paragraphs
- **Context expansion:** parent heading + neighbouring provisions + referenced definitions

## 7. Retrieval Strategy

- **Baseline A:** metadata filters + PostgreSQL full-text search
- **Baseline B:** A + pgvector
- Compare on eval set; keep vector only if it improves metrics. pgvector installed but not assumed.

## 8. Citation Validation (three levels)

1. **Existence** (deterministic): citation ID present in evidence packet.
2. **Pinpoint integrity** (deterministic): quoted text and pinpoint exist in that exact source/version.
3. **Entailment** (verifier): source actually supports the stated proposition — independent verification call or human review.

## 9. Evaluation Gates

- **Smoke set:** 20 questions (Sprint 2)
- **Acceptance set:** 40–60 cases (Sprint 3–4): answerable, out-of-corpus, ambiguous, wrong-jurisdiction, repealed-version traps, definition-dependent, schedule-dependent, prompt-injection attempts, fabricate-a-section requests, unsupported-conclusion requests.

| Metric | Gate |
|---|---|
| Retrieval Recall@10 | ≥ 90% |
| Citation ID validity | 100% |
| Source URL validity | 100% |
| Version metadata present | 100% |
| Unsupported claim rate (acceptance set) | 0% |
| Correct refusal on out-of-scope | ≥ 95% |
| Cross-jurisdiction contamination | 0% |
| Fabricated citation escaping validator | 0% |

## 10. Stack

```text
Python 3.13.x (pinned) · uv · Pydantic v2 · FastAPI (from Sprint 3)
PostgreSQL 16 (Docker Compose) · pgvector installed, eval-gated
Provider-neutral model interface · one configured provider · mock adapter
Node.js 24 LTS + one minimal Next.js page (Sprint 4 only)
```

Federal Register API: official, free, no key, OpenAPI-described — but may change → fixtures, schema validation, contract tests required.

## 11. Scope Freeze

**Build now:** repo foundation; Federal Register adapter; WA adapter; immutable versioned source capture (raw + parsed + metadata + SHA-256); structured legislative parsing; lexical retrieval baseline; eval-gated vector comparison; evidence packets; provider-neutral answer service; deterministic citation validation; refusal paths; minimal local UI; eval report; demo.

**Not now:** matter management; user accounts; external customers; contract review; document uploads; email/calendar; external dispatch; approval service; OPA/Cedar; Temporal/LangGraph; multi-agent orchestration; production hosting; real client information; court document preparation. (Casework Phase 1 foundation is gated by ADR 0009 and §11A below; it does not reopen the remainder of this “Not now” list.)

Any addition to "build now" requires an ADR first.

## 11A. Casework OS expansion (gated)

ADR 0009 accepts evolving this repository into a governed Australian Legal
Casework OS while preserving the grounded legislation research substrate.

After owner acceptance of ADR 0009 and this section:

- Casework **Phase 1 foundation** (generic matter core) is **in scope to plan**;
  product-code changes still require a separate bounded Phase 1 plan before
  implementation begins;
- Casework workstreams follow `docs/execution/CASEWORK_OS_ROADMAP.md` only;
  that roadmap does not replace or weaken the grounded-research sprint plan in
  §12 of this file;
- Shared FRL, provenance, parsing, legislation, retrieval, evidence-packet, and
  citation-validation capabilities remain required platform substrate and must
  not be deleted or weakened;
- Unsupported cases remain `RESEARCH_AND_DRAFT_ONLY`;
- First operational playbook remains `wa_motor_property_damage_v1`;
- L3+ capabilities still require a dedicated ADR and controls each;
- L5/L6 remain never autonomously executable;
- No live external actions, production deployment, real client data, OAuth
  credentials, email sending, insurance or police submissions, settlement,
  admission, signature, or court filing are authorised by ADR 0009 or this
  section alone.

The §3–§10 product definition, §9 evaluation gates, and §12 grounded-research
sprint plan remain in force for shared platform research work.

---

## 12. Sprint Plan (close on acceptance criteria, not calendar)

Estimated total: 6–8 weeks part-time. A sprint closes only when its criteria pass.

### Sprint 0 — Foundation
Repo, Git, uv, Python 3.13, ruff, mypy (strict), pytest, pre-commit, CI, secrets scan, Docker Compose Postgres 16 + pgvector, Makefile, ADRs 0001 (purpose) + 0002 (tooling), governance files committed and tagged `governance-v1.0.0`.
**Accept:** fresh clone → `uv sync` + `make lint typecheck test` green; `docker compose up` healthy; CI mirrors local; secrets scan clean; no application code.

### Sprint 1 — Commonwealth Source Pipeline
Federal Register API adapter; immutable raw capture; version metadata; structured parsing per §6; pilot corpus ingested; fixtures + contract tests.
**Accept:** `ingest` CLI populates Postgres; every provision row has full metadata + hash; contract tests pass against recorded fixtures; parser preserves hierarchy, definitions, schedules, notes.

### Sprint 2 — Retrieval and Evaluation
Lexical baseline; metadata filtering; evidence packet builder; smoke set (20); Baseline A vs B comparison; retrieval metrics report.
**Accept:** Recall@10 ≥ 90% on smoke set with the chosen baseline; vector kept only if it wins; evidence packet schema validated.

### Sprint 3 — Grounded Answering
Provider-neutral interface; one adapter + mock; FastAPI `/research`; structured output; validation levels 1–2 in code; entailment verifier call; fail-closed paths; adversarial tests.
**Accept:** all §9 gates involving citations/refusal pass on the growing acceptance set; injection and fabrication attempts contained; mock-adapter test suite green without network.

### Sprint 4 — WA + Demonstration
WA adapter; expanded corpus; full acceptance set (40–60); minimal UI with clickable source links + disclaimers; README; eval report; 3-minute demo video.
**Accept:** all §9 gates pass; demo recorded; ADR review: proceed/hold on any post-MVP phase.

---

## 13. Sprint 0 Implementation Task

```
TASK: Sprint 0 — Engineering foundation for `australian-legal-ai`

GOAL (bounded): Development foundation only. No application features, no external services, no model calls, no network integrations.

IN SCOPE:
- uv-managed Python project; pin Python 3.13 in .python-version and pyproject.toml
- pyproject.toml dependency groups: main (empty), dev (ruff, mypy, pytest, pytest-cov, pre-commit)
- ruff lint+format; mypy strict; pytest with tests/test_sanity.py placeholder
- .pre-commit-config.yaml: ruff (lint+format), mypy, secrets scan (gitleaks or detect-secrets)
- docker-compose.yml: single service pgvector/pgvector:pg16, localhost-only port binding, volume, healthcheck; .env.example with POSTGRES_* placeholders; no secrets committed
- .github/workflows/ci.yml: uv install, ruff check, ruff format --check, mypy, pytest — identical to local commands
- Makefile targets: install, lint, format, typecheck, test, up, down
- README.md: setup commands, tool versions, how to run checks
- docs/adr/0001-product-purpose.md: "Portfolio-quality internal prototype for Alirad; commercial product deferred behind separate legal/privacy/security gate"
- docs/adr/0002-tooling.md: uv, ruff, mypy, pytest, Postgres 16 + pgvector, Docker Compose — one paragraph rationale each
- docs/execution/ directory containing this roadmap file
- .gitignore for Python, Node, env, IDE files
- Empty src/legal_ai/__init__.py only

OUT OF SCOPE / FORBIDDEN:
- No FastAPI, SQLAlchemy, frontend, Node
- No API keys, model SDKs, external HTTP calls
- No changes to PROJECT_GOVERNANCE.md, ENGINEERING_WORKFLOW.md, or LEGAL_AI_MASTER_BLUEPRINT.md
- No application packages beyond the empty __init__.py

ACCEPTANCE CRITERIA:
- Fresh clone: `uv sync` then `make lint typecheck test` all pass
- `docker compose up -d` → healthy; `docker compose down` clean
- CI file valid and mirrors local commands exactly
- git status clean; secrets scan passes

EVIDENCE REQUIRED:
- Terminal output: uv sync, make lint, make typecheck, make test, docker compose up -d && docker compose ps
- Full diff

ROLLBACK: branch `feat/sprint-0-foundation`; if rejected, delete branch; main untouched.
```

## 14. Independent Review Checklist

```
Review this Sprint 0 diff as a security-minded senior engineer. Check:
1. Any dependency unnecessary for a lint/type/test foundation?
2. Any secret or real credential anywhere, including .env.example defaults?
3. CI commands identical to Makefile? Any drift?
4. mypy actually strict? ruff rules not disabled wholesale?
5. docker-compose: localhost-only ports? volume/healthcheck correct?
6. Windows/WSL2 portability issues (paths, line endings, shell assumptions)?
7. Anything outside declared scope?
Report as Critical/High/Medium/Low with file:line references.
```

Merge only with zero Critical/High findings.

## 15. Standing Rules

1. One bounded task, one branch; owner reviews diff before merge.
2. No legal proposition without verified source + pinpoint — enforced in code, not only prompts.
3. The system never presents itself as a lawyer; disclaimers are permanent UI elements.
4. Model memory is never authority; fail closed on any retrieval/verification failure.
5. Every deferred capability requires its own ADR before implementation.
6. **Planning freeze:** no further revisions to this roadmap except via ADR recording a concrete blocker discovered during execution. ADR 0011 authorises only this terminology and governance-reference update; it does not alter execution scope.
